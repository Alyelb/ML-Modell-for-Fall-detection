/*
 * CleverSole  --  Sturzerkennung in der Einlegesohle
 * XIAO ESP32-C6 + MPU-6050/6500 (nur Sohle)
 *
 * Ablauf:
 *   TIEFSCHLAF  -- Aufwachen durch Bewegungsinterrupt der IMU
 *   AUFWAKEN    -- Schrittzaehler und Kalibrierung der Einbaulage
 *   AKTIV       -- nach der Kalibrierung: Fenster fuellen, Modell auswerten
 *   NACH ALARM  -- Liegelage pruefen und Sturzrichtung melden
 *   -> zurueck in den Tiefschlaf nach 2 Minuten ohne Bewegung
 *
 * Signalkette (muss der Trainingspipeline entsprechen):
 *   MPU 100 Hz, DLPF 44 Hz
 *     -> Drehung Sensor -> Trainingsrahmen (Kalibrierung)
 *     -> Mittelung ueber zwei Abtastwerte (Anti-Aliasing)
 *     -> 50 Hz, Fenster 100 x 6
 *     -> Z-Normalisierung je Kanal
 *     -> int8-Quantisierung
 *     -> CNN
 *     -> N-von-M-Voting
 */

#include <Wire.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <esp_sleep.h>
#include <driver/gpio.h>

// ---------------------------------------------------------------
//  KONFIGURATION
// ---------------------------------------------------------------
#define PIN_SDA        22
#define PIN_SCL        23
#define PIN_MPU_INT    1      // GPIO1, weckfaehig (LP-GPIO)
#define PIN_BATT_ADC   3      // GPIO3 -- frei, ADC-faehig

#define GERAETENAME    "CleverSole-01"

// Testmodus: 1 = jede Modellausgabe p ueber Serial und BLE (FFF2)
// ausgeben und keinen Tiefschlaf -- fuer Versuche. Im Einsatz 0.
#define TESTMODUS           0

// Kalibrierung der Einbaulage (siehe Abschnitt KALIBRIERUNG)
#define KALIB_AUTO          1       // 0 = nur Montagevorgabe aus modell.h
#define KALIB_RICHTUNG_AUTO 1       // Vorwaertsrichtung aus dem Gang;
                                    // 0 = aus der Montagevorgabe (X zu den Zehen)
#define KALIB_GYRO_MIN_DPS  40.0f   // nur deutliche Drehungen beim Gehen
#define KALIB_PROBEN        300     // Gyro-Proben mit deutlicher Drehung (~10-15 Schritte)
#define KALIB_MAX_SCHRITTE  60      // spaetestens dann mit dem Vorhandenen rechnen
#define KALIB_RUHE_PROBEN   100     // 1 s Stillstand fuer die Schwerkraft

// Sturzrichtung nach einem Alarm
#define LAGE_SUCHE_MS       15000   // so lange nach der Liegephase suchen
#define LAGE_RUHE_PROBEN    100     // 1 s Ruhe = Liegen

// Ablauflogik
#define SCHRITTE_START      10      // Inferenz erst nach so vielen Schritten
#define RUHE_BIS_SCHLAF_MS  120000  // 2 Minuten ohne Bewegung
#define INFERENZ_INTERVALL  10      // alle 10 neuen 50-Hz-Werte (0,2 s)

// Schrittzaehler
#define SCHRITT_SCHWELLE_G  1.35f
#define SCHRITT_MIN_MS      250     // Entprellung
#define RUHE_SCHWELLE_G     0.08f   // Abweichung von 1 g gilt als Ruhe

// Voting: 3 von 5 bei 0,2 s Schrittweite, Schwelle 0,5
// (vorlaeufig; an Sohlendaten zu bestaetigen)
#define VOTE_N              3
#define VOTE_M              5
#define VOTE_SCHWELLE       0.5f

// Batterie (LiPo)
#define BATT_LEER_MV        3300
#define BATT_VOLL_MV        4200
#define BATT_TEILER         2.0f

// ---------------------------------------------------------------
//  MPU-6050
// ---------------------------------------------------------------
#define MPU_ADDR       0x68
#define REG_SMPLRT_DIV 0x19
#define REG_CONFIG     0x1A
#define REG_GYRO_CFG   0x1B
#define REG_ACCEL_CFG  0x1C
#define REG_MOT_THR    0x1F
#define REG_MOT_DUR    0x20
#define REG_INT_PIN    0x37
#define REG_INT_ENABLE 0x38
#define REG_INT_STATUS 0x3A
#define REG_ACCEL_XOUT 0x3B
#define REG_PWR_MGMT_1 0x6B
#define REG_ACCEL_CFG2 0x1D    // nur MPU-6500/9250
#define REG_MOT_CTRL   0x69    // nur MPU-6500/9250
static uint8_t chip_id = 0;
// +-16 g  -> 2048 LSB/g ; +-2000 dps -> 16.384 LSB/(deg/s)
static const float ACC_LSB = 1.0f / 2048.0f;
static const float GYR_LSB = 1.0f / 16.384f;

// Einbaulage: R_akt dreht die Sensorachsen in den Rahmen, in dem das
// Modell trainiert wurde (x' vorwaerts, y' abwaerts, z' links).
// Startwert ist die Montagevorgabe aus modell.h; die Kalibrierung
// ersetzt sie nach dem Aufwachen. RTC-Speicher: bleibt im Tiefschlaf.
#include "modell.h"
static const float R_MONTAGE[3][3] = R_MONTAGE_WERTE;
RTC_DATA_ATTR static float R_akt[3][3] = R_MONTAGE_WERTE;
RTC_DATA_ATTR static bool  kalibriert_je = false;

static void drehen(const float R[3][3], const float *v, float *out) {
  float x = v[0], y = v[1], z = v[2];
  for (int i = 0; i < 3; i++)
    out[i] = R[i][0] * x + R[i][1] * y + R[i][2] * z;
}

// ---------------------------------------------------------------
//  FENSTER
// ---------------------------------------------------------------
#define FENSTER_LEN  100     // 2 s bei 50 Hz
#define KANAELE      6

static float  ring[FENSTER_LEN][KANAELE];
static int    ring_pos   = 0;
static int    ring_fuell = 0;

// Dezimation 100 -> 50 Hz
static float dezim_summe[KANAELE];
static int   dezim_zaehler = 0;

// ---------------------------------------------------------------
//  ZUSTAND
// ---------------------------------------------------------------
enum Zustand { AUFWAKEN, AKTIV };
static bool kalib_fertig = false;      // in diesem Wachzyklus kalibriert
RTC_DATA_ATTR static uint32_t alarme_gesamt = 0;
RTC_DATA_ATTR static uint32_t schlafzyklen  = 0;

static Zustand  zustand        = AUFWAKEN;
static uint32_t schritte       = 0;
static uint32_t letzterSchritt = 0;
static uint32_t letzteBewegung = 0;
static bool     ueberSchwelle  = false;
static uint8_t  vote_puffer[VOTE_M];
static int      vote_pos = 0;
static int      seit_inferenz = 0;

// ---------------------------------------------------------------
//  BLE
// ---------------------------------------------------------------
#define UUID_BATT_SVC  "0000180F-0000-1000-8000-00805F9B34FB"
#define UUID_BATT_LVL  "00002A19-0000-1000-8000-00805F9B34FB"
#define UUID_FALL_SVC  "0000FFF0-0000-1000-8000-00805F9B34FB"
#define UUID_FALL_CHR  "0000FFF1-0000-1000-8000-00805F9B34FB"
#define UUID_INFO_CHR  "0000FFF2-0000-1000-8000-00805F9B34FB"   // Lage, Test

static BLECharacteristic *chrBatterie = nullptr;
static BLECharacteristic *chrAlarm    = nullptr;
static BLECharacteristic *chrInfo     = nullptr;
static bool verbunden = false;

class ServerCB : public BLEServerCallbacks {
  void onConnect(BLEServer*)    override { verbunden = true;  }
  void onDisconnect(BLEServer* s) override {
    verbunden = false;
    s->startAdvertising();
  }
};

// ---------------------------------------------------------------
//  I2C-HILFSFUNKTIONEN
// ---------------------------------------------------------------
static void mpuSchreibe(uint8_t reg, uint8_t wert) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(wert);
  Wire.endTransmission();
}

static uint8_t mpuLese(uint8_t reg) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom((int)MPU_ADDR, 1);
  return Wire.available() ? Wire.read() : 0;
}

static bool mpuLeseMessung(float *out) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(REG_ACCEL_XOUT);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)MPU_ADDR, 14) != 14) return false;

  int16_t roh[7];
  for (int i = 0; i < 7; i++) {
    roh[i] = (int16_t)((Wire.read() << 8) | Wire.read());
  }
  // roh[3] ist die Temperatur und wird uebersprungen.
  // Ausgabe in Sensorachsen; gedreht wird erst in loop().
  out[0] = roh[0] * ACC_LSB;
  out[1] = roh[1] * ACC_LSB;
  out[2] = roh[2] * ACC_LSB;
  out[3] = roh[4] * GYR_LSB;
  out[4] = roh[5] * GYR_LSB;
  out[5] = roh[6] * GYR_LSB;
  return true;
}

// ---------------------------------------------------------------
//  MPU EINRICHTEN
// ---------------------------------------------------------------
static bool mpuInit() {
  mpuSchreibe(REG_PWR_MGMT_1, 0x80);     // Reset
  delay(100);
  mpuSchreibe(REG_PWR_MGMT_1, 0x01);     // PLL mit X-Gyro als Takt
  delay(50);

  chip_id = mpuLese(0x75);               // WHO_AM_I

  const char *name;
  switch (chip_id) {
    case 0x68: name = "MPU-6050"; break;
    case 0x70: name = "MPU-6500"; break;
    case 0x71: name = "MPU-9250"; break;
    default:   name = "unbekannt"; break;
  }
  Serial.printf("Sensor: %s (WHO_AM_I = 0x%02X)\n", name, chip_id);

  if (chip_id != 0x68 && chip_id != 0x70 && chip_id != 0x71) {
    return false;
  }

  // Gyro-DLPF 42 Hz. Interne Rate 1 kHz, SMPLRT_DIV = 9 -> 100 Hz.
  mpuSchreibe(REG_CONFIG,     0x03);
  mpuSchreibe(REG_SMPLRT_DIV, 9);

  mpuSchreibe(REG_ACCEL_CFG,  0x18);     // +-16 g
  mpuSchreibe(REG_GYRO_CFG,   0x18);     // +-2000 deg/s

  // Beim MPU-6050 gilt das DLPF aus REG_CONFIG fuer beide Sensoren.
  // Der MPU-6500 hat dagegen ein eigenes Register fuer den
  // Beschleunigungssensor; ohne diese Zeile bliebe dessen Filter bei
  // 460 Hz und das Anti-Aliasing vor der Dezimation auf 50 Hz fehlte.
  if (chip_id != 0x68) {
    mpuSchreibe(REG_ACCEL_CFG2, 0x03);   // Accel-DLPF 41 Hz
  }
  return true;
}

// Bewegungsinterrupt fuer das Aufwachen aus dem Tiefschlaf
static void mpuBewegungsInterrupt() {
  if (chip_id == 0x68) {
    // ---- MPU-6050 ----
    mpuSchreibe(REG_PWR_MGMT_1, 0x01);
    mpuSchreibe(REG_ACCEL_CFG,  0x18 | 0x07);
    mpuSchreibe(REG_MOT_THR,    2);
    mpuSchreibe(REG_MOT_DUR,    40);
    mpuSchreibe(REG_INT_PIN,    0x20);
    mpuSchreibe(REG_INT_ENABLE, 0x40);
  } else {
    // ---- MPU-6500/9250: vollstaendige Wake-on-Motion-Folge ----
    // Die Reihenfolge ist vorgeschrieben; einzelne Schritte
    // wegzulassen laesst den Interrupt stumm bleiben.
    mpuSchreibe(REG_PWR_MGMT_1, 0x00);   // aufwachen, kein Cycle
    delay(10);
    mpuSchreibe(0x6C, 0x07);             // PWR_MGMT_2: Gyro aus,
                                         // nur Beschleunigung
    mpuSchreibe(REG_ACCEL_CFG2, 0x01);   // Accel-DLPF 184 Hz
    mpuSchreibe(REG_INT_ENABLE, 0x40);   // WOM-Interrupt an
    mpuSchreibe(REG_MOT_CTRL,   0xC0);   // ACCEL_INTEL ein,
                                         // Vergleich mit Vorwert
    mpuSchreibe(REG_MOT_THR,    10);     // 10 x 4 mg = 40 mg
    mpuSchreibe(0x1E,           0x05);   // LP_ACCEL_ODR ~ 31 Hz
    mpuSchreibe(REG_INT_PIN,    0x20);   // Latch bis zum Auslesen
    mpuSchreibe(REG_PWR_MGMT_1, 0x20);   // CYCLE-Modus: der Sensor
                                         // misst nur noch stichprobenartig
  }
  delay(10);
  mpuLese(REG_INT_STATUS);               // Flag loeschen
}


static void schlafenGehen() {
  Serial.printf("Ruhe -> Tiefschlaf (Zyklus %lu)\n",
                (unsigned long)schlafzyklen);
  Serial.flush();

  schlafzyklen++;
  BLEDevice::deinit(true);
  mpuBewegungsInterrupt();

  pinMode(PIN_MPU_INT, INPUT_PULLDOWN);

  // Aufwachen durch den Sensor
  esp_deep_sleep_enable_gpio_wakeup(1ULL << PIN_MPU_INT,
                                    ESP_GPIO_WAKEUP_GPIO_HIGH);

  // Sicherheitsnetz: Auch ohne funktionierenden Interrupt wacht das
  // Geraet spaetestens nach 60 s auf, prueft kurz auf Bewegung und
  // legt sich sonst wieder schlafen. Ohne diesen Rueckfallweg waere
  // ein stummer Interrupt gleichbedeutend mit einem toten Geraet.
  esp_sleep_enable_timer_wakeup(60ULL * 1000000ULL);

  esp_deep_sleep_start();
}

// ---------------------------------------------------------------
//  BATTERIE
// ---------------------------------------------------------------
static uint8_t batterieProzent() {
  uint32_t summe = 0;
  for (int i = 0; i < 16; i++) summe += analogReadMilliVolts(PIN_BATT_ADC);
  float mv = (summe / 16.0f) * BATT_TEILER;

  if (mv <= BATT_LEER_MV) return 0;
  if (mv >= BATT_VOLL_MV) return 100;
  return (uint8_t)(100.0f * (mv - BATT_LEER_MV) /
                   (BATT_VOLL_MV - BATT_LEER_MV));
}

// ---------------------------------------------------------------
//  BLE EINRICHTEN
// ---------------------------------------------------------------
static void bleInit() {
  BLEDevice::init(GERAETENAME);
  BLEServer *server = BLEDevice::createServer();
  server->setCallbacks(new ServerCB());

  // Standard-Batteriedienst: Scanner zeigen den Ladestand direkt an
  BLEService *svcBatt = server->createService(UUID_BATT_SVC);
  chrBatterie = svcBatt->createCharacteristic(
      UUID_BATT_LVL,
      BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
  chrBatterie->addDescriptor(new BLE2902());
  svcBatt->start();

  BLEService *svcFall = server->createService(UUID_FALL_SVC);
  chrAlarm = svcFall->createCharacteristic(
      UUID_FALL_CHR,
      BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
  chrAlarm->addDescriptor(new BLE2902());
  chrInfo = svcFall->createCharacteristic(
      UUID_INFO_CHR,
      BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
  chrInfo->addDescriptor(new BLE2902());
  svcFall->start();

  BLEAdvertising *adv = BLEDevice::getAdvertising();
  adv->addServiceUUID(UUID_BATT_SVC);
  adv->addServiceUUID(UUID_FALL_SVC);

  // Name und Ladestand in die Werbedaten legen, damit beides schon
  // vor dem Verbinden sichtbar ist. Die MAC-Adresse laesst sich nicht
  // unterdruecken -- sie gehoert zum Protokoll --, Scanner zeigen
  // jedoch den Namen an, sobald einer vorhanden ist.
  uint8_t stand = batterieProzent();
  BLEAdvertisementData werbung;
  werbung.setName(GERAETENAME);
  werbung.setFlags(0x06);
   String hersteller;
  hersteller += (char)0xFF;      // Test-ID (0xFFFF)
  hersteller += (char)0xFF;
  hersteller += (char)stand;     // Ladestand in Prozent
  werbung.setManufacturerData(hersteller);
  adv->setAdvertisementData(werbung);

  adv->setScanResponse(true);
  BLEDevice::startAdvertising();

  chrBatterie->setValue(&stand, 1);
  Serial.printf("BLE aktiv als \"%s\", Batterie %u %%\n",
                GERAETENAME, stand);
}

static void bleInfoSenden(const char *msg) {
  Serial.println(msg);
  if (chrInfo) {
    chrInfo->setValue((uint8_t*)msg, strlen(msg));
    if (verbunden) chrInfo->notify();
  }
}

static void bleAlarmSenden(float wahrscheinlichkeit) {
  alarme_gesamt++;
  char msg[64];
  snprintf(msg, sizeof(msg), "STURZ p=%.2f n=%lu batt=%u",
           wahrscheinlichkeit, (unsigned long)alarme_gesamt,
           batterieProzent());
  Serial.println(msg);
  if (chrAlarm) {
    chrAlarm->setValue((uint8_t*)msg, strlen(msg));
    if (verbunden) chrAlarm->notify();
  }
}

// ---------------------------------------------------------------
//  SCHRITTZAEHLER
// ---------------------------------------------------------------
static void schrittPruefen(float betrag, uint32_t jetzt) {
  if (betrag > SCHRITT_SCHWELLE_G && !ueberSchwelle) {
    if (jetzt - letzterSchritt > SCHRITT_MIN_MS) {
      schritte++;
      letzterSchritt = jetzt;
      // Der Wechsel nach AKTIV erfolgt in loop(), sobald zusaetzlich
      // die Kalibrierung abgeschlossen ist.
    }
    ueberSchwelle = true;
  } else if (betrag < SCHRITT_SCHWELLE_G - 0.1f) {
    ueberSchwelle = false;            // Hysterese
  }
}

// ---------------------------------------------------------------
//  KALIBRIERUNG DER EINBAULAGE
// ---------------------------------------------------------------
// Ziel: R_akt so bestimmen, dass die Sensorachsen in den
// Trainingsrahmen (x' vorwaerts, y' abwaerts, z' links) fallen --
// unabhaengig davon, wie genau das Modul in der Sohle liegt.
//   1. Hochachse u: Schwerkraft im Stillstand (sonst Mittel beim Gehen).
//   2. Querachse r: Hauptdrehachse der Winkelgeschwindigkeit beim Gehen
//      (der Fuss dreht beim Abrollen und in der Schwungphase um die
//      Querachse), senkrecht zu u.
//   3. Vorzeichen: In der Schwungphase dreht das Bein vorwaerts; diese
//      Spitzen sind die groessten. Schiefe der Drehrate um r > 0
//      legt fest, dass r nach rechts zeigt. Vorwaerts f = u x r.
//      Auf den Knoechel-Pilotdaten (Gehen, Joggen) traf das in allen
//      Faellen zu; an der Sohle ist es noch zu pruefen.
// Faellt etwas davon aus, bleibt die Montagevorgabe aus modell.h.
static float kal_g_ruhe[3], kal_g_gang[3];
static int   kal_gang_n = 0, kal_ruhe_folge = 0;
static float kal_ruhe_summe[3];
static float kal_gyro[KALIB_PROBEN][3];
static int   kal_gyro_n = 0;
static bool  kal_g_ruhe_ok = false;

static float skalar(const float *a, const float *b) {
  return a[0]*b[0] + a[1]*b[1] + a[2]*b[2];
}
static void kreuz(const float *a, const float *b, float *c) {
  c[0] = a[1]*b[2] - a[2]*b[1];
  c[1] = a[2]*b[0] - a[0]*b[2];
  c[2] = a[0]*b[1] - a[1]*b[0];
}
static bool normieren(float *v) {
  float n = sqrtf(skalar(v, v));
  if (n < 1e-6f) return false;
  v[0] /= n; v[1] /= n; v[2] /= n;
  return true;
}

static void kalibProbe(const float *roh) {          // roh: Sensorachsen
  const float *a = roh, *w = roh + 3;
  float betrag_a = sqrtf(skalar(a, a));
  float betrag_w = sqrtf(skalar(w, w));

  // Stillstand: 1 s ohne Drehung bei ~1 g
  if (betrag_w < 10.0f && fabsf(betrag_a - 1.0f) < 0.06f) {
    for (int i = 0; i < 3; i++) kal_ruhe_summe[i] += a[i];
    if (++kal_ruhe_folge >= KALIB_RUHE_PROBEN) {
      for (int i = 0; i < 3; i++) kal_g_ruhe[i] = kal_ruhe_summe[i] / kal_ruhe_folge;
      kal_g_ruhe_ok = true;
      kal_ruhe_folge = 0;
      memset(kal_ruhe_summe, 0, sizeof(kal_ruhe_summe));
    }
  } else {
    kal_ruhe_folge = 0;
    memset(kal_ruhe_summe, 0, sizeof(kal_ruhe_summe));
  }
  // Gehen: Mittel der Beschleunigung ~ Schwerkraft; Gyro sammeln
  if (betrag_w > KALIB_GYRO_MIN_DPS && kal_gyro_n < KALIB_PROBEN) {
    for (int i = 0; i < 3; i++) {
      kal_gyro[kal_gyro_n][i] = w[i];
      kal_g_gang[i] += a[i];
    }
    kal_gyro_n++; kal_gang_n++;
  }
}

static bool kalibBerechnen() {
  if (kal_gyro_n < KALIB_PROBEN / 2) return false;
  float u[3];
  for (int i = 0; i < 3; i++)
    u[i] = kal_g_ruhe_ok ? kal_g_ruhe[i] : kal_g_gang[i] / kal_gang_n;
  if (!normieren(u)) return false;

  // Kovarianz der Drehrate, auf die Ebene senkrecht zu u projiziert
  float C[3][3] = {{0}};
  for (int k = 0; k < kal_gyro_n; k++) {
    float w[3], d = skalar(kal_gyro[k], u);
    for (int i = 0; i < 3; i++) w[i] = kal_gyro[k][i] - d * u[i];
    for (int i = 0; i < 3; i++)
      for (int j = 0; j < 3; j++) C[i][j] += w[i] * w[j];
  }
  // Hauptachse per Potenzmethode; Startvektor = Querachse der Montagevorgabe
  float r[3] = {R_MONTAGE[2][0], R_MONTAGE[2][1], R_MONTAGE[2][2]};
  float d0 = skalar(r, u);
  for (int i = 0; i < 3; i++) r[i] -= d0 * u[i];
  if (!normieren(r)) { r[0] = 1; r[1] = 0; r[2] = 0; }
  float lambda = 0;
  for (int it = 0; it < 50; it++) {
    float q[3];
    for (int i = 0; i < 3; i++) q[i] = C[i][0]*r[0] + C[i][1]*r[1] + C[i][2]*r[2];
    lambda = sqrtf(skalar(q, q));
    if (!normieren(q)) return false;
    memcpy(r, q, sizeof(r));
  }
  // Guete: Anteil der Drehung um die Querachse (Gehen ~ 0,7 und mehr)
  float spur = C[0][0] + C[1][1] + C[2][2];
  float anteil = (spur > 0) ? lambda / spur : 0;
  if (anteil < 0.5f) {
    Serial.printf("Kalibrierung: keine klare Querachse (%.2f) -- Vorgabe bleibt\n", anteil);
    return false;
  }

  // Vorzeichen der Querachse
  float f[3];
#if KALIB_RICHTUNG_AUTO
  double schiefe = 0;
  for (int k = 0; k < kal_gyro_n; k++) {
    double s = skalar(kal_gyro[k], r);
    schiefe += s * s * s;
  }
  if (schiefe < 0) { r[0] = -r[0]; r[1] = -r[1]; r[2] = -r[2]; }
  kreuz(u, r, f);                                    // vorwaerts = oben x rechts
#else
  kreuz(u, r, f);
  const float *x_vorgabe = R_MONTAGE[0];             // Sensorrichtung "vorwaerts"
  if (skalar(f, x_vorgabe) < 0) { f[0] = -f[0]; f[1] = -f[1]; f[2] = -f[2]; }
#endif
  if (!normieren(f)) return false;
  float links[3];
  kreuz(u, f, links);                                // oben x vorwaerts = links
  for (int j = 0; j < 3; j++) {
    R_akt[0][j] = f[j];          // x' vorwaerts
    R_akt[1][j] = -u[j];         // y' abwaerts
    R_akt[2][j] = links[j];      // z' links
  }
  kalibriert_je = true;
  float abw = acosf(fminf(1.0f, fmaxf(-1.0f, skalar(f, R_MONTAGE[0])))) * 57.2958f;
  Serial.printf("Kalibrierung ok: oben=(%.2f %.2f %.2f) vorn=(%.2f %.2f %.2f) "
                "Querachse %.0f %%, Abweichung zur Vorgabe %.0f Grad\n",
                u[0], u[1], u[2], f[0], f[1], f[2], anteil * 100, abw);
  return true;
}

// ---------------------------------------------------------------
//  STURZRICHTUNG AUS DER LIEGELAGE
// ---------------------------------------------------------------
// Nach einem Alarm wird die erste Ruhephase (1 s) gesucht und die
// Schwerkraft im Trainingsrahmen ausgewertet. Auf den Knoechel-
// Pilotdaten: vorwaerts x' ~ -0,9, rueckwaerts x' ~ +0,8,
// seitlich |z'| ~ 1. An der Sohle haengt die Lage zusaetzlich vom
// Sprunggelenk ab -- die Richtung ist eine Schaetzung.
static bool     lage_aktiv = false;
static uint32_t lage_start = 0;
static int      lage_folge = 0;
static float    lage_summe[3];

static void lageStarten(uint32_t jetzt) {
  lage_aktiv = true; lage_start = jetzt; lage_folge = 0;
  memset(lage_summe, 0, sizeof(lage_summe));
}

static void lagePruefen(const float *m, uint32_t jetzt) {   // m: gedreht
  if (!lage_aktiv) return;
  float betrag_a = sqrtf(skalar(m, m));
  float betrag_w = sqrtf(skalar(m + 3, m + 3));
  if (betrag_w < 15.0f && fabsf(betrag_a - 1.0f) < 0.1f) {
    for (int i = 0; i < 3; i++) lage_summe[i] += m[i];
    if (++lage_folge >= LAGE_RUHE_PROBEN) {
      float g[3];
      for (int i = 0; i < 3; i++) g[i] = lage_summe[i] / lage_folge;
      const char *richtung;
      if (g[1] < -0.8f)                        richtung = "aufrecht (kein Liegen)";
      else if (g[0] < -0.5f || g[1] > 0.5f)    richtung = "vorwaerts (Bauchlage)";
      else if (g[0] > 0.5f)                    richtung = "rueckwaerts (Rueckenlage)";
      else if (fabsf(g[2]) > 0.5f)             richtung = "seitlich";
      else                                     richtung = "unklar";
      char msg[96];
      snprintf(msg, sizeof(msg), "LAGE %s x=%.2f y=%.2f z=%.2f",
               richtung, g[0], g[1], g[2]);
      bleInfoSenden(msg);
      lage_aktiv = false;
    }
  } else {
    lage_folge = 0;
    memset(lage_summe, 0, sizeof(lage_summe));
  }
  if (lage_aktiv && jetzt - lage_start > LAGE_SUCHE_MS) {
    bleInfoSenden("LAGE keine Liegephase gefunden");
    lage_aktiv = false;
  }
}

// ---------------------------------------------------------------
//  TIEFSCHLAF
// ---------------------------------------------------------------


// ---------------------------------------------------------------
//  INFERENZ
// ---------------------------------------------------------------
// Modell: siehe modell.h (bereits oben eingebunden)

#if MODELL_VERFUEGBAR
  // Arduino-ESP32-Core 3.x bringt esp-tflite-micro mit. Fehlt der
  // Header, Bibliothek "Chirale_TensorFlowLite" installieren.
  #if __has_include(<Chirale_TensorFlowLite.h>)
    #include <Chirale_TensorFlowLite.h>
  #endif
  #include "tensorflow/lite/micro/micro_interpreter.h"
  #include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
  #include "tensorflow/lite/schema/schema_generated.h"

  constexpr int ARENA_GROESSE = 60 * 1024;
  static uint8_t arena[ARENA_GROESSE];
  static tflite::MicroInterpreter *interp = nullptr;
  static TfLiteTensor *eingang = nullptr;
  static TfLiteTensor *ausgang = nullptr;

  static bool modellInit() {
    const tflite::Model *m = tflite::GetModel(modell_tflite);
    if (m->version() != TFLITE_SCHEMA_VERSION) {
      Serial.println("Modell: falsche Schema-Version");
      return false;
    }
    // Genau die Operatoren aus modell.h (Kopfkommentar). Wird ein
    // anderes Modell eingespielt und fehlt hier ein Operator, schlaegt
    // AllocateTensors mit "Didn't find op" fehl.
    static tflite::MicroMutableOpResolver<10> resolver;
    resolver.AddConv2D();
    resolver.AddExpandDims();         // Conv1D -> Conv2D
    resolver.AddMaxPool2D();
    resolver.AddMean();               // GlobalAveragePooling
    resolver.AddFullyConnected();
    resolver.AddAdd();                // BatchNorm (nicht gefaltet)
    resolver.AddMul();
    resolver.AddLogistic();           // Sigmoid
    resolver.AddReshape();

    static tflite::MicroInterpreter statischer(
        m, resolver, arena, ARENA_GROESSE);
    interp = &statischer;
    if (interp->AllocateTensors() != kTfLiteOk) {
      Serial.println("AllocateTensors fehlgeschlagen - Arena zu klein?");
      return false;
    }
    eingang = interp->input(0);
    ausgang = interp->output(0);
    Serial.printf("Modell geladen. Arena benutzt: %u von %u Byte\n",
                  interp->arena_used_bytes(), ARENA_GROESSE);
    return true;
  }

  // Z-Normalisierung je Kanal, danach int8-Quantisierung.
  // Muss der Trainingspipeline exakt entsprechen.
  static float modellAuswerten() {
    float mittel[KANAELE] = {0}, streuung[KANAELE] = {0};

    for (int c = 0; c < KANAELE; c++) {
      for (int t = 0; t < FENSTER_LEN; t++) {
        mittel[c] += ring[(ring_pos + t) % FENSTER_LEN][c];
      }
      mittel[c] /= FENSTER_LEN;
    }
    for (int c = 0; c < KANAELE; c++) {
      for (int t = 0; t < FENSTER_LEN; t++) {
        float d = ring[(ring_pos + t) % FENSTER_LEN][c] - mittel[c];
        streuung[c] += d * d;
      }
      streuung[c] = sqrtf(streuung[c] / FENSTER_LEN) + 1e-8f;
    }

    const float  skala = eingang->params.scale;
    const int    null  = eingang->params.zero_point;
    int8_t      *ziel  = eingang->data.int8;

    for (int t = 0; t < FENSTER_LEN; t++) {
      int idx = (ring_pos + t) % FENSTER_LEN;
      for (int c = 0; c < KANAELE; c++) {
        float norm = (ring[idx][c] - mittel[c]) / streuung[c];
        int   q    = lroundf(norm / skala) + null;
        if (q < -128) q = -128;
        if (q >  127) q =  127;
        ziel[t * KANAELE + c] = (int8_t)q;
      }
    }

    if (interp->Invoke() != kTfLiteOk) return -1.0f;
    return (ausgang->data.int8[0] - ausgang->params.zero_point) *
           ausgang->params.scale;
  }
#else
  static bool  modellInit()      { return false; }
  static float modellAuswerten() { return -1.0f; }
#endif

// N-von-M-Voting
static bool votingAusloesen(float p) {
  vote_puffer[vote_pos] = (p > VOTE_SCHWELLE) ? 1 : 0;
  vote_pos = (vote_pos + 1) % VOTE_M;
  int summe = 0;
  for (int i = 0; i < VOTE_M; i++) summe += vote_puffer[i];
  return summe >= VOTE_N;
}

// ---------------------------------------------------------------
//  SETUP
// ---------------------------------------------------------------
static bool modellBereit = false;

void setup() {
  Serial.begin(115200);
  delay(1500);                    // USB-CDC braucht Zeit zur Anmeldung

  esp_sleep_wakeup_cause_t grund = esp_sleep_get_wakeup_cause();
  const char *grundText =
      (grund == ESP_SLEEP_WAKEUP_GPIO)  ? "Bewegung (INT)" :
      (grund == ESP_SLEEP_WAKEUP_TIMER) ? "Zeitgeber (Rueckfall)" :
                                          "Kaltstart";
  Serial.printf("\n--- CleverSole (%s, Zyklus %lu) ---\n",
                grundText, (unsigned long)schlafzyklen);

  Wire.begin(PIN_SDA, PIN_SCL);
  Wire.setClock(400000);

  if (!mpuInit()) {
    Serial.println("IMU nicht gefunden - Verkabelung pruefen.");
    while (true) delay(1000);
  }

  analogReadResolution(12);
  bleInit();
  modellBereit = modellInit();
  if (!modellBereit) {
    Serial.println("Kein Modell -- nur Schrittzaehlung und Schlaflogik.");
  }

  zustand        = AUFWAKEN;
  schritte       = 0;
  kalib_fertig   = !KALIB_AUTO;
  kal_gyro_n = kal_gang_n = kal_ruhe_folge = 0;
  kal_g_ruhe_ok = false;
  memset(kal_g_gang, 0, sizeof(kal_g_gang));
  memset(kal_ruhe_summe, 0, sizeof(kal_ruhe_summe));
  Serial.printf("Einbaulage: %s\n", kalibriert_je ?
                "letzte Kalibrierung (wird beim Gehen erneuert)" :
                "Montagevorgabe (wird beim Gehen kalibriert)");
#if TESTMODUS
  Serial.println("TESTMODUS: Ausgabe jeder Inferenz, kein Tiefschlaf");
  Serial.println("Format: T,<ms>,<p>,<Stimmen von 5>");
#endif
  letzteBewegung = millis();
  memset(vote_puffer, 0, sizeof(vote_puffer));
  memset(dezim_summe, 0, sizeof(dezim_summe));
}

// ---------------------------------------------------------------
//  HAUPTSCHLEIFE
// ---------------------------------------------------------------
void loop() {
  static uint32_t naechsteMessung = 0;
  static uint32_t letzteBatterie  = 0;
  uint32_t jetzt = millis();

  if (jetzt >= naechsteMessung) {
    naechsteMessung = jetzt + 10;        // 100 Hz

    float roh[KANAELE], messung[KANAELE];
    if (!mpuLeseMessung(roh)) return;

    // Kalibrierung laeuft auf Sensorachsen, solange noch nicht fertig
    if (!kalib_fertig) {
      kalibProbe(roh);
      if ((kal_gyro_n >= KALIB_PROBEN && schritte >= SCHRITTE_START) ||
          schritte >= KALIB_MAX_SCHRITTE) {
        if (!kalibBerechnen())
          Serial.println("Kalibrierung: Rueckfall auf vorherige Einbaulage");
        kalib_fertig = true;
        ring_fuell = 0;                    // Fenster mit neuer Lage fuellen
      }
    }
    drehen(R_akt, roh, messung);           // Beschleunigung
    drehen(R_akt, roh + 3, messung + 3);   // Winkelgeschwindigkeit
    lagePruefen(messung, jetzt);

    if (zustand == AUFWAKEN && kalib_fertig && schritte >= SCHRITTE_START) {
      zustand = AKTIV;
      Serial.printf("%lu Schritte, Einbaulage kalibriert -> Inferenz aktiv\n",
                    (unsigned long)schritte);
    }

    float betrag = sqrtf(messung[0]*messung[0] +
                         messung[1]*messung[1] +
                         messung[2]*messung[2]);

    if (fabsf(betrag - 1.0f) > RUHE_SCHWELLE_G) letzteBewegung = jetzt;
    schrittPruefen(betrag, jetzt);

    // Mittelung ueber zwei Werte: wirkt als einfaches Anti-Aliasing
    // vor der Dezimation auf 50 Hz. Die Trainingsdaten wurden mit
    // einem Polyphasenfilter heruntergetastet; diese Naeherung ist
    // auf den Pilotdaten zu ueberpruefen.
    for (int c = 0; c < KANAELE; c++) dezim_summe[c] += messung[c];
    if (++dezim_zaehler >= 2) {
      for (int c = 0; c < KANAELE; c++) {
        ring[ring_pos][c] = dezim_summe[c] / 2.0f;
        dezim_summe[c] = 0;
      }
      ring_pos = (ring_pos + 1) % FENSTER_LEN;
      if (ring_fuell < FENSTER_LEN) ring_fuell++;
      dezim_zaehler = 0;
      seit_inferenz++;

      if (zustand == AKTIV && modellBereit &&
          ring_fuell >= FENSTER_LEN &&
          seit_inferenz >= INFERENZ_INTERVALL) {
        seit_inferenz = 0;
        uint32_t t0 = micros();
        float p = modellAuswerten();
        uint32_t dauer = micros() - t0;

        bool alarm = (p >= 0) && votingAusloesen(p);
#if TESTMODUS
        (void)dauer;
        int stimmen = 0;
        for (int i = 0; i < VOTE_M; i++) stimmen += vote_puffer[i];
        char zeile[48];
        snprintf(zeile, sizeof(zeile), "T,%lu,%.3f,%d",
                 (unsigned long)jetzt, p, stimmen);
        bleInfoSenden(zeile);
#else
        static uint32_t zaehler = 0;
        if (++zaehler % 50 == 0) {
          Serial.printf("p=%.3f  Inferenz %lu us  Schritte %lu\n",
                        p, (unsigned long)dauer,
                        (unsigned long)schritte);
        }
#endif
        if (alarm) {
          bleAlarmSenden(p);
          memset(vote_puffer, 0, sizeof(vote_puffer));
          lageStarten(jetzt);
        }
      }
    }
  }

  if (jetzt - letzteBatterie > 30000) {
    letzteBatterie = jetzt;
    uint8_t stand = batterieProzent();
    if (chrBatterie) {
      chrBatterie->setValue(&stand, 1);
      if (verbunden) chrBatterie->notify();
    }
  }

#if !TESTMODUS
  if (jetzt - letzteBewegung > RUHE_BIS_SCHLAF_MS && !lage_aktiv) schlafenGehen();
#endif
}

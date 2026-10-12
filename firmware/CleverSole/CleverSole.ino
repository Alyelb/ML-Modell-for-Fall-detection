/*
 * CleverSole  --  Sturzerkennung in der Schuhsohle
 * ESP32-C6 + MPU-6050
 *
 * Ablauf:
 *   TIEFSCHLAF  -- Aufwachen durch Bewegungsinterrupt des MPU-6050
 *   AUFWAKEN    -- Schrittzaehler laeuft, noch keine Inferenz
 *   AKTIV       -- nach 10 Schritten: Fenster fuellen, Modell auswerten
 *   -> zurueck in den Tiefschlaf nach 2 Minuten ohne Bewegung
 *
 * Signalkette (muss der Trainingspipeline entsprechen):
 *   MPU 100 Hz, DLPF 44 Hz
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

// Ablauflogik
#define SCHRITTE_START      10      // Inferenz erst nach so vielen Schritten
#define RUHE_BIS_SCHLAF_MS  120000  // 2 Minuten ohne Bewegung
#define INFERENZ_INTERVALL  10      // alle 10 neuen 50-Hz-Werte (0,2 s)

// Schrittzaehler
#define SCHRITT_SCHWELLE_G  1.35f
#define SCHRITT_MIN_MS      250     // Entprellung
#define RUHE_SCHWELLE_G     0.08f   // Abweichung von 1 g gilt als Ruhe

// Voting: 3 von 5 bei 0,2 s Schrittweite, Schwelle 0,5
// (Pilotdaten Knoechel, Lower-Limb-Modell: 95-100 % der Stuerze
//  erkannt, Fehlalarm-Ereignisse gegenueber 1-von-1 etwa halbiert)
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

// Einbaulage: dreht die Sensorachsen in den Koordinatenrahmen, in dem
// das Modell trainiert wurde (Knoechel: Schwerkraft auf -Y, USB oben).
// Auswahl in modell.h (EINBAU_SOHLE).
#include "modell.h"
static const float R_EINBAU[3][3] = R_EINBAU_WERTE;

static void einbaulageAnwenden(float *v) {        // v[0..2]
  float x = v[0], y = v[1], z = v[2];
  for (int i = 0; i < 3; i++)
    v[i] = R_EINBAU[i][0] * x + R_EINBAU[i][1] * y + R_EINBAU[i][2] * z;
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

static BLECharacteristic *chrBatterie = nullptr;
static BLECharacteristic *chrAlarm    = nullptr;
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
  // roh[3] ist die Temperatur und wird uebersprungen
  out[0] = roh[0] * ACC_LSB;
  out[1] = roh[1] * ACC_LSB;
  out[2] = roh[2] * ACC_LSB;
  out[3] = roh[4] * GYR_LSB;
  out[4] = roh[5] * GYR_LSB;
  out[5] = roh[6] * GYR_LSB;
  einbaulageAnwenden(out);          // Beschleunigung
  einbaulageAnwenden(out + 3);      // Winkelgeschwindigkeit
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
      if (zustand == AUFWAKEN && schritte >= SCHRITTE_START) {
        zustand = AKTIV;
        Serial.printf("%lu Schritte erkannt -> Inferenz aktiv\n",
                      (unsigned long)schritte);
      }
    }
    ueberSchwelle = true;
  } else if (betrag < SCHRITT_SCHWELLE_G - 0.1f) {
    ueberSchwelle = false;            // Hysterese
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
    Serial.println("MPU-6050 nicht gefunden - Verkabelung pruefen.");
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

    float messung[KANAELE];
    if (!mpuLeseMessung(messung)) return;

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

        static uint32_t zaehler = 0;
        if (++zaehler % 50 == 0) {
          Serial.printf("p=%.3f  Inferenz %lu us  Schritte %lu\n",
                        p, (unsigned long)dauer,
                        (unsigned long)schritte);
        }
        if (p >= 0 && votingAusloesen(p)) {
          bleAlarmSenden(p);
          memset(vote_puffer, 0, sizeof(vote_puffer));
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

  if (jetzt - letzteBewegung > RUHE_BIS_SCHLAF_MS) schlafenGehen();
}

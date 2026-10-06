/*
 * DatenLogger  --  Pilotdaten mit der Zielhardware aufzeichnen
 *
 * Nimmt mit 100 Hz auf und legt die Rohwerte im internen Flash ab.
 * Aufgezeichnet werden ADC-Rohwerte, nicht umgerechnete Groessen:
 * Die Umrechnung und das Heruntertasten auf 50 Hz erfolgen spaeter
 * in Colab mit genau derselben Funktion wie beim Training. Wuerde
 * das Board bereits filtern, waere die Vorverarbeitung nicht mehr
 * identisch mit der Trainingspipeline.
 *
 * Bedienung per Handy (Bluetooth, empfohlen):
 *   App "Serial Bluetooth Terminal" (Android) bzw. "Bluefruit
 *   Connect" -> UART (iOS), Geraet "CleverSole-Logger" verbinden.
 *   Dieselben Befehle wie im Serial Monitor (siehe unten). So lassen
 *   sich mehrere Aktivitaeten nacheinander aufnehmen, ohne das Board
 *   abzunehmen. Ausgelesen wird weiterhin per USB.
 *
 * Ablauf einer Aufnahme per USB:
 *   1. Board per USB anschliessen, Serial Monitor oeffnen
 *   2. Position (p) und Aktivitaet (a) waehlen
 *   3. Serial Monitor schliessen, Board an Powerbank/Akku haengen
 *   4. BOOT-Taste druecken -> 5 s Vorlauf -> Aufnahme laeuft
 *      (alternativ "r" im Monitor, dann 10 s Vorlauf)
 *   5. Aktivitaet ausfuehren (bei Stuerzen mehrere Wiederholungen
 *      in einer Datei, je ca. 5 s ruhig liegen bleiben)
 *   6. BOOT-Taste erneut -> Aufnahme beendet, Datei geschlossen
 *      ERST DANN die Stromversorgung wechseln!
 *   7. Auslesen: tools/pilot_download.py (oder "d" im Monitor)
 *
 * Befehle:
 *   r  Aufnahme starten (mit Vorlauf)
 *   s  Aufnahme beenden
 *   d  Alle Aufnahmen als CSV ausgeben
 *   l  Aufnahmen auflisten
 *   x  Speicher loeschen
 *   p  Position waehlen
 *   a  naechste Aktivitaet    b  vorherige Aktivitaet
 *   ?  Menue
 */

#include <Wire.h>
#include <FS.h>
#include <LittleFS.h>
#include <Preferences.h>   // Auswahl ueberlebt Neustart/Stromwechsel
#include <stdarg.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

static Preferences prefs;

// ---------------------------------------------------------------
#define PIN_SDA        22
#define PIN_SCL        23

#define ABTASTRATE     100          // Hz
#define VORLAUF_S      10           // Sekunden zum Anlegen
#define MAX_DAUER_S    120          // Sicherheitsgrenze je Aufnahme
#define PIN_TASTER     9            // BOOT-Taste des ESP32-C6-DevKit
#define VORLAUF_TASTER_S 5          // Vorlauf beim Start per Taste
#define GERAETENAME    "CleverSole-Logger"

// ---------------------------------------------------------------
#define MPU_ADDR       0x68
#define REG_SMPLRT_DIV 0x19
#define REG_CONFIG     0x1A
#define REG_GYRO_CFG   0x1B
#define REG_ACCEL_CFG  0x1C
#define REG_ACCEL_CFG2 0x1D
#define REG_ACCEL_XOUT 0x3B
#define REG_PWR_MGMT_1 0x6B
#define REG_WHO_AM_I   0x75

static uint8_t chip_id = 0;

// ---------------------------------------------------------------
//  METADATEN
// ---------------------------------------------------------------
static const char *POSITIONEN[] = {"WAIST", "ANKLE", "FOOT_INSOLE",
                                   "SHIN", "SONSTIGE"};
static const char *AKTIVITAETEN[] = {
    "walking", "jogging", "stairs_up", "stairs_down",
    "sit_stand", "lying_down",
    "jumping", "pick_up", "sit_hard",
    "fall_forward", "fall_knees", "fall_backward", "fall_lateral",
    "fall_slip"};
static const int N_POS = sizeof(POSITIONEN)/sizeof(POSITIONEN[0]);
static const int N_AKT = sizeof(AKTIVITAETEN)/sizeof(AKTIVITAETEN[0]);

static int  pos_idx = 0;
static int  akt_idx = 0;
static int  aufnahme_nr = 0;

// ---------------------------------------------------------------
//  ZUSTAND
// ---------------------------------------------------------------
static bool     laeuft = false;
static File     datei;
static uint32_t start_ms = 0;
static uint32_t proben   = 0;
static uint32_t naechste = 0;

// ---------------------------------------------------------------
//  BLE  --  Nordic UART Service (Bedienung per Handy)
// ---------------------------------------------------------------
#define NUS_SVC "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define NUS_RX  "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"   // Handy -> Board
#define NUS_TX  "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"   // Board -> Handy

static BLECharacteristic *chrTX = nullptr;
static volatile bool ble_verbunden = false;

// Befehle vom Handy kommen im BLE-Task an. Ausgefuehrt werden sie erst
// in loop(), damit Dateizugriffe nicht aus zwei Tasks gleichzeitig
// erfolgen.
static char ble_puffer[32];
static volatile uint8_t ble_kopf = 0, ble_ende = 0;

class ServerCB : public BLEServerCallbacks {
  void onConnect(BLEServer*) override { ble_verbunden = true; }
  void onDisconnect(BLEServer *srv) override {
    ble_verbunden = false;
    srv->startAdvertising();
  }
};

class RxCB : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *c) override {
    String d = c->getValue();
    for (unsigned i = 0; i < d.length(); i++) {
      uint8_t n = (ble_kopf + 1) % sizeof(ble_puffer);
      if (n == ble_ende) break;              // Puffer voll
      ble_puffer[ble_kopf] = d[i];
      ble_kopf = n;
    }
  }
};

// Ausgabe gleichzeitig seriell und an das Handy
static void out(const char *fmt, ...) {
  char buf[200];
  va_list ap; va_start(ap, fmt);
  vsnprintf(buf, sizeof(buf), fmt, ap);
  va_end(ap);
  Serial.print(buf);
  if (ble_verbunden && chrTX) {
    size_t len = strlen(buf);
    for (size_t off = 0; off < len; off += 160) {
      size_t n = (len - off > 160) ? 160 : (len - off);
      chrTX->setValue((uint8_t*)(buf + off), n);
      chrTX->notify();
      delay(4);
    }
  }
}

static void bleStarten() {
  BLEDevice::init(GERAETENAME);
  BLEServer *srv = BLEDevice::createServer();
  srv->setCallbacks(new ServerCB());
  BLEService *svc = srv->createService(NUS_SVC);
  chrTX = svc->createCharacteristic(NUS_TX, BLECharacteristic::PROPERTY_NOTIFY);
  chrTX->addDescriptor(new BLE2902());
  BLECharacteristic *rx = svc->createCharacteristic(NUS_RX,
      BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  rx->setCallbacks(new RxCB());
  svc->start();
  BLEAdvertising *adv = BLEDevice::getAdvertising();
  adv->addServiceUUID(NUS_SVC);
  adv->setScanResponse(true);
  BLEDevice::startAdvertising();
}

// ---------------------------------------------------------------
//  I2C
// ---------------------------------------------------------------
static void mpuSchreibe(uint8_t reg, uint8_t wert) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg); Wire.write(wert);
  Wire.endTransmission();
}

static uint8_t mpuLese(uint8_t reg) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom((int)MPU_ADDR, 1);
  return Wire.available() ? Wire.read() : 0;
}

static bool mpuLeseAlles(int16_t *roh) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(REG_ACCEL_XOUT);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)MPU_ADDR, 14) != 14) return false;
  for (int i = 0; i < 7; i++) {
    roh[i] = (int16_t)((Wire.read() << 8) | Wire.read());
  }
  return true;
}

static bool mpuInit() {
  mpuSchreibe(REG_PWR_MGMT_1, 0x80); delay(100);
  mpuSchreibe(REG_PWR_MGMT_1, 0x01); delay(50);

  chip_id = mpuLese(REG_WHO_AM_I);
  if (chip_id != 0x68 && chip_id != 0x70 && chip_id != 0x71) return false;

  mpuSchreibe(REG_CONFIG,     0x03);   // DLPF 42 Hz
  mpuSchreibe(REG_SMPLRT_DIV, 9);      // 1000/(1+9) = 100 Hz
  mpuSchreibe(REG_ACCEL_CFG,  0x18);   // +-16 g
  mpuSchreibe(REG_GYRO_CFG,   0x18);   // +-2000 deg/s
  if (chip_id != 0x68) mpuSchreibe(REG_ACCEL_CFG2, 0x03);
  return true;
}

// ---------------------------------------------------------------
//  MENUE
// ---------------------------------------------------------------
static void menue() {
  out("\n");
  out("=========== DatenLogger ===========\n");
  out("  Sensor    : 0x%02X\n", chip_id);
  out("  Position  : %s\n", POSITIONEN[pos_idx]);
  out("  Aktivitaet: %s\n", AKTIVITAETEN[akt_idx]);
  out("  Speicher  : %u von %u kB belegt\n",
                (unsigned)(LittleFS.usedBytes()/1024),
                (unsigned)(LittleFS.totalBytes()/1024));
  out("-----------------------------------\n");
  out("  r  Aufnahme starten     s  beenden\n");
  out("  d  als CSV ausgeben     l  auflisten\n");
  out("  p  Position             a/b  Aktivitaet +/-\n");
  out("  x  Speicher loeschen    ?  Menue\n");
  out("  BOOT-Taste: Start / Stopp ohne Monitor\n");
  out("  Handy: Bluetooth \"%s\" (%s)\n", GERAETENAME,
      ble_verbunden ? "verbunden" : "nicht verbunden");
  out("===================================\n");
}

static void listeZeigen() {
  out("\nGespeicherte Aufnahmen:\n");
  File wurzel = LittleFS.open("/");
  File f = wurzel.openNextFile();
  int n = 0;
  while (f) {
    out("  %-28s %7u Byte  (~%u s)\n",
                  f.name(), (unsigned)f.size(),
                  (unsigned)(f.size() / 36 / ABTASTRATE));
    n++;
    f = wurzel.openNextFile();
  }
  if (!n) out("  (keine)\n");
}

// ---------------------------------------------------------------
//  AUFNAHME
// ---------------------------------------------------------------
static void aufnahmeStarten(int vorlauf_s) {
  if (laeuft) { out("Laeuft bereits.\n"); return; }

  out("\nPosition: %s | Aktivitaet: %s\n",
                POSITIONEN[pos_idx], AKTIVITAETEN[akt_idx]);
  out("Vorlauf %d s -- jetzt anlegen und USB abziehen.\n",
                vorlauf_s);
  for (int i = vorlauf_s; i > 0; i--) {
    out("  %d ...\n", i);
    delay(1000);
  }

  char name[48];
  snprintf(name, sizeof(name), "/%02d_%s_%s.csv",
           aufnahme_nr++, POSITIONEN[pos_idx], AKTIVITAETEN[akt_idx]);
  datei = LittleFS.open(name, FILE_WRITE);
  if (!datei) { out("Datei konnte nicht angelegt werden.\n"); return; }

  // Kopfzeile mit allen Angaben, die zur Auswertung noetig sind
  datei.printf("# position=%s activity=%s fs=%d range_acc=16g "
               "range_gyr=2000dps chip=0x%02X dlpf=42Hz\n",
               POSITIONEN[pos_idx], AKTIVITAETEN[akt_idx],
               ABTASTRATE, chip_id);
  datei.println("t_ms,ax,ay,az,gx,gy,gz");

  laeuft   = true;
  proben   = 0;
  start_ms = millis();
  naechste = start_ms;
  out(">>> AUFNAHME LAEUFT <<<\n");
}

static void aufnahmeBeenden() {
  if (!laeuft) return;
  laeuft = false;
  uint32_t dauer = millis() - start_ms;
  datei.close();
  out("\nBeendet: %lu Proben in %.1f s (%.1f Hz)\n",
                (unsigned long)proben, dauer / 1000.0f,
                proben * 1000.0f / dauer);
  menue();
}

// Gibt alle Dateien am Stueck aus. Der Text laesst sich aus dem
// Monitor kopieren und als CSV speichern.
static void alsCsvAusgeben() {
  File wurzel = LittleFS.open("/");
  File f = wurzel.openNextFile();
  if (!f) { Serial.println("Keine Aufnahmen vorhanden."); return; }

  while (f) {
    Serial.printf("\n===== DATEI: %s =====\n", f.name());
    while (f.available()) {
      Serial.write(f.read());
    }
    Serial.printf("===== ENDE: %s =====\n", f.name());
    f = wurzel.openNextFile();
  }
  Serial.println("\nAlles ausgegeben.");
}

// ---------------------------------------------------------------
static void befehl(char c) {
  switch (c) {
    case 'r': case 'R': aufnahmeStarten(VORLAUF_S); break;
    case 's': case 'S': aufnahmeBeenden(); break;
    case 'd': case 'D':
      if (laeuft) { out("Erst beenden (s).\n"); break; }
      if (ble_verbunden) out("Ausgabe nur ueber USB (pilot_download.py).\n");
      alsCsvAusgeben();
      break;
    case 'l': case 'L': listeZeigen(); break;
    case 'p': case 'P':
      pos_idx = (pos_idx + 1) % N_POS;
      prefs.putInt("pos", pos_idx);
      out("Position: %s\n", POSITIONEN[pos_idx]);
      break;
    case 'a': case 'A':
      akt_idx = (akt_idx + 1) % N_AKT;
      prefs.putInt("akt", akt_idx);
      out("Aktivitaet: %s\n", AKTIVITAETEN[akt_idx]);
      break;
    case 'b': case 'B':
      akt_idx = (akt_idx + N_AKT - 1) % N_AKT;
      prefs.putInt("akt", akt_idx);
      out("Aktivitaet: %s\n", AKTIVITAETEN[akt_idx]);
      break;
    case 'x': case 'X':
      if (laeuft) { out("Erst beenden (s).\n"); break; }
      LittleFS.format();
      aufnahme_nr = 0;
      out("Speicher geloescht.\n");
      break;
    case '?': menue(); break;
    default: break;
  }
}

// ---------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(1500);

  pinMode(PIN_TASTER, INPUT_PULLUP);
  Wire.begin(PIN_SDA, PIN_SCL);
  Wire.setClock(400000);

  if (!mpuInit()) {
    out("Sensor nicht erkannt (0x%02X)\n", chip_id);
    while (true) delay(1000);
  }
  if (!LittleFS.begin(true)) {
    out("Dateisystem nicht bereit.\n");
    while (true) delay(1000);
  }

  // Zuletzt gewaehlte Position/Aktivitaet wiederherstellen: Beim
  // Umstecken vom PC auf die Powerbank startet das Board neu.
  prefs.begin("logger", false);
  pos_idx = prefs.getInt("pos", 0) % N_POS;
  akt_idx = prefs.getInt("akt", 0) % N_AKT;

  // Fortlaufende Nummer aus den vorhandenen Dateien ableiten,
  // damit ein Neustart bestehende Aufnahmen nicht ueberschreibt.
  File wurzel = LittleFS.open("/");
  File f = wurzel.openNextFile();
  while (f) { aufnahme_nr++; f = wurzel.openNextFile(); }

  bleStarten();
  menue();
}

void loop() {
  while (Serial.available()) befehl(Serial.read());
  while (ble_ende != ble_kopf) {
    char c = ble_puffer[ble_ende];
    ble_ende = (ble_ende + 1) % sizeof(ble_puffer);
    befehl(c);
  }

  // BOOT-Taste: Start/Stopp ohne Serial Monitor (entprellt, Flanke)
  static bool     taste_vorher = HIGH;
  static uint32_t taste_ms     = 0;
  bool taste = digitalRead(PIN_TASTER);
  if (taste == LOW && taste_vorher == HIGH && millis() - taste_ms > 300) {
    taste_ms = millis();
    if (laeuft) aufnahmeBeenden();
    else        aufnahmeStarten(VORLAUF_TASTER_S);
  }
  taste_vorher = taste;

  if (!laeuft) return;

  uint32_t jetzt = millis();
  if (jetzt < naechste) return;
  naechste += 1000 / ABTASTRATE;

  int16_t roh[7];
  if (!mpuLeseAlles(roh)) return;

  // Rohwerte in LSB, Umrechnung erfolgt in Colab
  datei.printf("%lu,%d,%d,%d,%d,%d,%d\n",
               (unsigned long)(jetzt - start_ms),
               roh[0], roh[1], roh[2], roh[4], roh[5], roh[6]);
  proben++;
  // Regelmaessig auf den Flash schreiben: geht die Stromversorgung
  // waehrend der Aufnahme verloren, fehlt hoechstens 1 s.
  if (proben % ABTASTRATE == 0) datei.flush();

  if (proben % (ABTASTRATE * 10) == 0) {
    out("  %lu s aufgezeichnet\n",
                  (unsigned long)(proben / ABTASTRATE));
  }
  if (proben >= (uint32_t)ABTASTRATE * MAX_DAUER_S) {
    out("Maximale Dauer erreicht.\n");
    aufnahmeBeenden();
  }
}

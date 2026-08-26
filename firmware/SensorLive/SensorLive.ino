/*
 * SensorLive  --  Alle Messwerte im Klartext ausgeben
 *
 * Zeigt fortlaufend jeden verfuegbaren Messwert von MPU-6050/6500
 * und ESP32-C6 an, sowohl ueber die serielle Schnittstelle als auch
 * per Bluetooth.
 *
 * Auf dem Handy: nRF Connect -> CleverSole-Live verbinden ->
 * der Nordic-UART-Dienst wird erkannt und als Textfenster angezeigt.
 *
 * Befehle (seriell oder ueber Bluetooth):
 *   r  Rohwerte (LSB) statt physikalischer Einheiten
 *   s  Ausgabe anhalten / fortsetzen
 *   n  Nullpunkt der Drehrate neu bestimmen
 *   +  schneller,  -  langsamer
 *   k  Kopfzeile erneut ausgeben
 */

#include <Wire.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// ---------------------------------------------------------------
//  ANSCHLUESSE  --  an die eigene Verkabelung anpassen
// ---------------------------------------------------------------
#define PIN_SDA        22
#define PIN_SCL        23
#define PIN_MPU_INT     1
#define PIN_BATT_ADC    3
#define GERAETENAME    "CleverSole-Live"

// ---------------------------------------------------------------
//  MPU-REGISTER
// ---------------------------------------------------------------
#define MPU_ADDR       0x68
#define REG_SMPLRT_DIV 0x19
#define REG_CONFIG     0x1A
#define REG_GYRO_CFG   0x1B
#define REG_ACCEL_CFG  0x1C
#define REG_ACCEL_CFG2 0x1D
#define REG_INT_STATUS 0x3A
#define REG_ACCEL_XOUT 0x3B
#define REG_PWR_MGMT_1 0x6B
#define REG_WHO_AM_I   0x75

static const float ACC_LSB = 1.0f / 2048.0f;    // +-16 g
static const float GYR_LSB = 1.0f / 16.384f;    // +-2000 deg/s

static uint8_t chip_id = 0;
static const char *chip_name = "unbekannt";

// ---------------------------------------------------------------
//  EINSTELLUNGEN ZUR LAUFZEIT
// ---------------------------------------------------------------
static bool     rohwerte  = false;
static bool     pausiert  = false;
static uint32_t intervall = 200;      // ms zwischen zwei Ausgaben
static float    gyr_null[3] = {0, 0, 0};

// ---------------------------------------------------------------
//  BLE  --  Nordic UART Service
// ---------------------------------------------------------------
#define NUS_SVC "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define NUS_RX  "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"   // Handy -> Board
#define NUS_TX  "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"   // Board -> Handy

static BLECharacteristic *chrTX = nullptr;
static bool verbunden = false;

static void befehlAusfuehren(char c);

class ServerCB : public BLEServerCallbacks {
  void onConnect(BLEServer*) override {
    verbunden = true;
    Serial.println("[BLE] Handy verbunden");
  }
  void onDisconnect(BLEServer *s) override {
    verbunden = false;
    Serial.println("[BLE] Handy getrennt");
    s->startAdvertising();
  }
};

class RxCB : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *c) override {
    String daten = c->getValue();
    for (unsigned int i = 0; i < daten.length(); i++) {
      befehlAusfuehren(daten[i]);
    }
  }
};

// Gibt eine Zeile gleichzeitig seriell und ueber Bluetooth aus.
static void zeile(const char *fmt, ...) {
  char puffer[220];
  va_list args;
  va_start(args, fmt);
  vsnprintf(puffer, sizeof(puffer), fmt, args);
  va_end(args);

  Serial.println(puffer);
  if (verbunden && chrTX) {
    // BLE-Pakete sind begrenzt; laengere Zeilen werden aufgeteilt.
    size_t len = strlen(puffer);
    const size_t max = 180;
    for (size_t off = 0; off < len; off += max) {
      size_t n = (len - off > max) ? max : (len - off);
      chrTX->setValue((uint8_t*)(puffer + off), n);
      chrTX->notify();
      delay(3);
    }
    const char *nl = "\n";
    chrTX->setValue((uint8_t*)nl, 1);
    chrTX->notify();
  }
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

// Liest Beschleunigung, Temperatur und Drehrate in einem Zug.
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
  switch (chip_id) {
    case 0x68: chip_name = "MPU-6050"; break;
    case 0x70: chip_name = "MPU-6500"; break;
    case 0x71: chip_name = "MPU-9250"; break;
    default:   chip_name = "unbekannt"; return false;
  }

  mpuSchreibe(REG_CONFIG,     0x03);   // DLPF 42 Hz
  mpuSchreibe(REG_SMPLRT_DIV, 9);      // 100 Hz
  mpuSchreibe(REG_ACCEL_CFG,  0x18);   // +-16 g
  mpuSchreibe(REG_GYRO_CFG,   0x18);   // +-2000 deg/s
  if (chip_id != 0x68) mpuSchreibe(REG_ACCEL_CFG2, 0x03);
  return true;
}

// Die Temperaturformel unterscheidet sich zwischen den Baureihen.
static float mpuTemperatur(int16_t roh) {
  if (chip_id == 0x68) return roh / 340.0f + 36.53f;   // MPU-6050
  return roh / 333.87f + 21.0f;                        // MPU-6500/9250
}

// ---------------------------------------------------------------
//  NULLPUNKT DER DREHRATE
// ---------------------------------------------------------------
// Ein ruhender Gyroskop zeigt selten exakt null. Der Versatz wird
// einmal gemessen und danach abgezogen. Das Board muss dabei
// stillliegen.
static void gyroNullen() {
  zeile("Nullpunkt wird bestimmt -- Board 2 s ruhig halten ...");
  double summe[3] = {0, 0, 0};
  int gueltig = 0;
  for (int i = 0; i < 200; i++) {
    int16_t roh[7];
    if (mpuLeseAlles(roh)) {
      summe[0] += roh[4]; summe[1] += roh[5]; summe[2] += roh[6];
      gueltig++;
    }
    delay(10);
  }
  if (gueltig > 0) {
    for (int a = 0; a < 3; a++) {
      gyr_null[a] = (summe[a] / gueltig) * GYR_LSB;
    }
    zeile("Versatz: X=%+.2f  Y=%+.2f  Z=%+.2f deg/s",
          gyr_null[0], gyr_null[1], gyr_null[2]);
  }
}

// ---------------------------------------------------------------
//  BATTERIE
// ---------------------------------------------------------------
static uint32_t batterieMV() {
  uint32_t summe = 0;
  for (int i = 0; i < 8; i++) summe += analogReadMilliVolts(PIN_BATT_ADC);
  return (summe / 8) * 2;      // Spannungsteiler 2:1
}

// ---------------------------------------------------------------
//  BEFEHLE
// ---------------------------------------------------------------
static void kopfzeile();

static void befehlAusfuehren(char c) {
  switch (c) {
    case 'r': case 'R':
      rohwerte = !rohwerte;
      zeile("-> %s", rohwerte ? "Rohwerte (LSB)"
                              : "physikalische Einheiten");
      kopfzeile();
      break;
    case 's': case 'S':
      pausiert = !pausiert;
      zeile("-> %s", pausiert ? "angehalten" : "laeuft");
      break;
    case 'n': case 'N':
      gyroNullen();
      break;
    case '+':
      if (intervall > 50) intervall -= 50;
      zeile("-> Intervall %lu ms", (unsigned long)intervall);
      break;
    case '-':
      if (intervall < 2000) intervall += 50;
      zeile("-> Intervall %lu ms", (unsigned long)intervall);
      break;
    case 'k': case 'K':
      kopfzeile();
      break;
    default:
      break;
  }
}

static void kopfzeile() {
  if (rohwerte) {
    zeile("");
    zeile("   Zeit |    AccX    AccY    AccZ |    GyrX    GyrY    GyrZ |  Temp");
    zeile("     ms |                    LSB  |                   LSB   |   LSB");
    zeile("--------+-------------------------+-------------------------+-------");
  } else {
    zeile("");
    zeile("   Zeit |   AccX   AccY   AccZ    |a| |    GyrX     GyrY     GyrZ |  T-MPU  T-CPU |  Batt");
    zeile("      s |     g      g      g      g |          deg/s            |    C      C   |    mV");
    zeile("--------+----------------------------+---------------------------+---------------+-------");
  }
}

// ---------------------------------------------------------------
//  SETUP
// ---------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(1500);                  // USB-CDC braucht Zeit zur Anmeldung

  Serial.println("\n===== SensorLive =====");

  Wire.begin(PIN_SDA, PIN_SCL);
  Wire.setClock(400000);

  if (!mpuInit()) {
    Serial.printf("Kein bekannter Sensor (WHO_AM_I = 0x%02X)\n", chip_id);
    Serial.println("Verkabelung und Pin-Nummern pruefen.");
    while (true) delay(1000);
  }
  Serial.printf("Sensor: %s (0x%02X)\n", chip_name, chip_id);

  analogReadResolution(12);
  pinMode(PIN_MPU_INT, INPUT);

  // BLE mit Nordic-UART-Dienst
  BLEDevice::init(GERAETENAME);
  BLEServer *server = BLEDevice::createServer();
  server->setCallbacks(new ServerCB());

  BLEService *svc = server->createService(NUS_SVC);
  chrTX = svc->createCharacteristic(NUS_TX,
            BLECharacteristic::PROPERTY_NOTIFY);
  chrTX->addDescriptor(new BLE2902());
  BLECharacteristic *chrRX = svc->createCharacteristic(NUS_RX,
            BLECharacteristic::PROPERTY_WRITE |
            BLECharacteristic::PROPERTY_WRITE_NR);
  chrRX->setCallbacks(new RxCB());
  svc->start();

  BLEAdvertising *adv = BLEDevice::getAdvertising();
  adv->addServiceUUID(NUS_SVC);
  adv->setScanResponse(true);
  BLEDevice::startAdvertising();

  Serial.printf("BLE aktiv als \"%s\"\n", GERAETENAME);
  Serial.println("Handy: nRF Connect -> verbinden -> UART-Ansicht");
  Serial.println("Befehle: r s n + - k");

  gyroNullen();
  kopfzeile();
}

// ---------------------------------------------------------------
//  HAUPTSCHLEIFE
// ---------------------------------------------------------------
void loop() {
  // Befehle von der seriellen Schnittstelle
  while (Serial.available()) befehlAusfuehren(Serial.read());

  static uint32_t naechste = 0;
  static uint32_t zaehler  = 0;
  uint32_t jetzt = millis();
  if (pausiert || jetzt < naechste) return;
  naechste = jetzt + intervall;

  int16_t roh[7];
  if (!mpuLeseAlles(roh)) {
    zeile("!! I2C-Lesefehler -- Verbindung pruefen");
    delay(500);
    return;
  }

  if (rohwerte) {
    zeile("%7lu | %7d %7d %7d | %7d %7d %7d | %6d",
          (unsigned long)jetzt,
          roh[0], roh[1], roh[2], roh[4], roh[5], roh[6], roh[3]);
  } else {
    float ax = roh[0] * ACC_LSB;
    float ay = roh[1] * ACC_LSB;
    float az = roh[2] * ACC_LSB;
    float betrag = sqrtf(ax*ax + ay*ay + az*az);
    float gx = roh[4] * GYR_LSB - gyr_null[0];
    float gy = roh[5] * GYR_LSB - gyr_null[1];
    float gz = roh[6] * GYR_LSB - gyr_null[2];

    zeile("%7.1f | %6.3f %6.3f %6.3f %6.3f | %8.2f %8.2f %8.2f | "
          "%6.1f %6.1f | %5lu",
          jetzt / 1000.0f, ax, ay, az, betrag, gx, gy, gz,
          mpuTemperatur(roh[3]), temperatureRead(),
          (unsigned long)batterieMV());
  }

  // Alle 20 Zeilen die Kopfzeile wiederholen
  if (++zaehler % 20 == 0) kopfzeile();
}

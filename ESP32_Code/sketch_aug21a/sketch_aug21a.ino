#include <Wire.h>

// MPU-6050 Register
#define MPU_ADDR 0x68
#define PWR_MGMT_1 0x6B
#define SMPLRT_DIV 0x19
#define CONFIG_REG 0x1A
#define ACCEL_CONFIG 0x1C
#define GYRO_CONFIG 0x1B
#define ACCEL_XOUT_H 0x3B

// Conversion
const float ACC_SCALE = 16.0 / 32768.0;   // ±16g
const float GYR_SCALE = 2000.0 / 32768.0; // ±2000 dps

void writeRegister(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

void setup() {
  Serial.begin(115200);
  Wire.begin(6, 7);        // SDA=6, SCL=7 (ANPASSEN!)
  Wire.setClock(400000);   // 400 kHz I2C

  // Wake up
  writeRegister(PWR_MGMT_1, 0x00);
  delay(100);

  // Sample Rate = 1000 / (1 + 9) = 100 Hz
  writeRegister(SMPLRT_DIV, 9);

  // DLPF = 44 Hz Bandwidth (anti-aliasing)
  writeRegister(CONFIG_REG, 0x03);

  // Accel = ±16g
  writeRegister(ACCEL_CONFIG, 0x18);

  // Gyro = ±2000 dps
  writeRegister(GYRO_CONFIG, 0x18);

  Serial.println("acc_x,acc_y,acc_z,gyr_x,gyr_y,gyr_z");
}

void loop() {
  // 14 Bytes lesen: Acc(6) + Temp(2) + Gyr(6)
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(ACCEL_XOUT_H);
  Wire.endTransmission(false);
  Wire.requestFrom(MPU_ADDR, 14);

  int16_t ax = (Wire.read() << 8) | Wire.read();
  int16_t ay = (Wire.read() << 8) | Wire.read();
  int16_t az = (Wire.read() << 8) | Wire.read();
  Wire.read(); Wire.read(); // Temp ueberspringen
  int16_t gx = (Wire.read() << 8) | Wire.read();
  int16_t gy = (Wire.read() << 8) | Wire.read();
  int16_t gz = (Wire.read() << 8) | Wire.read();

  // In physikalische Einheiten
  float acc_x = ax * ACC_SCALE;
  float acc_y = ay * ACC_SCALE;
  float acc_z = az * ACC_SCALE;
  float gyr_x = gx * GYR_SCALE;
  float gyr_y = gy * GYR_SCALE;
  float gyr_z = gz * GYR_SCALE;

  Serial.printf("%.4f,%.4f,%.4f,%.2f,%.2f,%.2f\n",
                acc_x, acc_y, acc_z,
                gyr_x, gyr_y, gyr_z);

  delay(10); // ~100 Hz
}
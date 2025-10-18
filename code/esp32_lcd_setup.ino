// ESP32 LCD Library Setup Instructions
// Untuk menggunakan LCD I2C dengan ESP32

/*
LIBRARY YANG DIPERLUKAN:
1. LiquidCrystal_I2C by Frank de Brabander
   - Install via Arduino IDE Library Manager
   - Search: "LiquidCrystal I2C"

WIRING LCD I2C:
LCD I2C    ESP32
VCC   ->   3.3V atau 5V
GND   ->   GND
SDA   ->   GPIO21 (SDA)
SCL   ->   GPIO22 (SCL)

ADDRESS LCD:
- Biasanya 0x27 atau 0x3F
- Bisa scan dengan I2C Scanner

TESTING LCD:
1. Upload kode esp32_sensor_lcd.ino
2. Pastikan LCD menyala dan menampilkan teks
3. Jalankan python esp32_simple_bidirectional.py
4. Lihat hasil prediksi di LCD

TROUBLESHOOTING:
- Jika LCD tidak menyala: check wiring dan power
- Jika tidak ada teks: check address I2C (0x27 atau 0x3F)
- Jika teks tidak jelas: adjust contrast pot di LCD
*/

// I2C Scanner untuk mencari address LCD
#include <Wire.h>

void setup() {
  Wire.begin();
  Serial.begin(115200);
  Serial.println("\nI2C Scanner");
}

void loop() {
  byte error, address;
  int nDevices;

  Serial.println("Scanning...");

  nDevices = 0;
  for(address = 1; address < 127; address++ ) {
    Wire.beginTransmission(address);
    error = Wire.endTransmission();

    if (error == 0) {
      Serial.print("I2C device found at address 0x");
      if (address<16) 
        Serial.print("0");
      Serial.print(address,HEX);
      Serial.println("  !");

      nDevices++;
    }
    else if (error==4) {
      Serial.print("Unknown error at address 0x");
      if (address<16) 
        Serial.print("0");
      Serial.println(address,HEX);
    }    
  }
  if (nDevices == 0)
    Serial.println("No I2C devices found\n");
  else
    Serial.println("done\n");

  delay(5000);           // wait 5 seconds for next scan
}

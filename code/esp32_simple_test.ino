// ESP32 Simple Test Sender - Minimal Version untuk Testing
// Kirim data sensor sederhana ke laptop

// Pin definitions untuk 8 sensor MQ (sesuaikan dengan hardware Anda)
int sensorPins[8] = {34, 35, 32, 33, 25, 26, 27, 14};
String sensorNames[8] = {"MQ2", "MQ3", "MQ4", "MQ135", "MQ6", "MQ7", "MQ8", "MQ9"};

// Konstanta normalisasi
const int MAX_ESP32_ADC = 4095;
const int MAX_RASPBERRY_MCP = 65472;

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("ESP32 Simple Test Sender Ready");
  Serial.println("Format: SENSOR_DATA,val1,val2,val3,val4,val5,val6,val7,val8");
  Serial.println("Sending test data every 2 seconds...");
}

void loop() {
  // Baca semua sensor
  float sensorValues[8];
  for(int i = 0; i < 8; i++) {
    sensorValues[i] = analogRead(sensorPins[i]);
    delay(10); // Small delay between readings
  }
  
  // Normalisasi data untuk kompatibilitas dengan model Raspberry Pi
  float normalizedValues[8];
  for(int i = 0; i < 8; i++) {
    float raspberryCompatible = (sensorValues[i] / MAX_ESP32_ADC) * MAX_RASPBERRY_MCP;
    normalizedValues[i] = raspberryCompatible / MAX_RASPBERRY_MCP;
  }
  
  // Kirim data dalam format CSV
  String dataString = "SENSOR_DATA";
  for(int i = 0; i < 8; i++) {
    dataString += ",";
    dataString += String(normalizedValues[i], 6); // 6 decimal places
  }
  
  Serial.println(dataString);
  
  // Debug info - tampilkan raw values juga
  Serial.print("Raw values: ");
  for(int i = 0; i < 8; i++) {
    Serial.print(sensorNames[i]);
    Serial.print(":");
    Serial.print(sensorValues[i]);
    Serial.print(" ");
  }
  Serial.println();
  
  delay(2000); // Send every 2 seconds
}

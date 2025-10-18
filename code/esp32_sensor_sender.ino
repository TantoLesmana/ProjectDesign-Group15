// ESP32 Sensor Data Sender untuk TensorFlow Lite Processing
// Kirim data sensor ke laptop via Serial

// Pin definitions untuk 8 sensor MQ
int sensorPins[8] = {34, 35, 32, 33, 25, 26, 27, 14}; // Sesuaikan dengan pin yang digunakan
String sensorNames[8] = {"MQ2", "MQ3", "MQ4", "MQ135", "MQ6", "MQ7", "MQ8", "MQ9"};

// Konstanta normalisasi
const int MAX_ESP32_ADC = 4095;
const int MAX_RASPBERRY_MCP = 65472;

// Buffer untuk data
float sensorValues[8];
float normalizedValues[8];

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("ESP32 Sensor Data Sender Ready");
  Serial.println("Format: SENSOR_DATA,MQ2,MQ3,MQ4,MQ135,MQ6,MQ7,MQ8,MQ9");
  Serial.println("Press 'a' to send sensor data");
}

void loop() {
  // Baca semua sensor
  readAllSensors();
  
  // Normalisasi data untuk kompatibilitas dengan model Raspberry Pi
  normalizeSensorData();
  
  // Kirim data dalam format CSV
  sendSensorData();
  
  delay(1000); // Update setiap 1 detik
}

void readAllSensors() {
  for(int i = 0; i < 8; i++) {
    sensorValues[i] = analogRead(sensorPins[i]);
    delay(10); // Small delay between readings
  }
}

void normalizeSensorData() {
  for(int i = 0; i < 8; i++) {
    // Konversi ke format Raspberry Pi untuk kompatibilitas model
    float raspberryCompatible = (sensorValues[i] / MAX_ESP32_ADC) * MAX_RASPBERRY_MCP;
    normalizedValues[i] = raspberryCompatible / MAX_RASPBERRY_MCP;
  }
}

void sendSensorData() {
  // Format: SENSOR_DATA,val1,val2,val3,val4,val5,val6,val7,val8
  String dataString = "SENSOR_DATA";
  
  for(int i = 0; i < 8; i++) {
    dataString += ",";
    dataString += String(normalizedValues[i], 6); // 6 decimal places
  }
  
  Serial.println(dataString);
  
  // Debug info
  Serial.print("Raw values: ");
  for(int i = 0; i < 8; i++) {
    Serial.print(sensorNames[i]);
    Serial.print(":");
    Serial.print(sensorValues[i]);
    Serial.print(" ");
  }
  Serial.println();
}

// Fungsi untuk mengirim data saat ada input 'a'
void handleSerialInput() {
  if(Serial.available()) {
    String input = Serial.readString();
    input.trim();
    
    if(input == "a") {
      readAllSensors();
      normalizeSensorData();
      sendSensorData();
    }
  }
}

// ESP32 Sensor Data Sender + LCD Display untuk Prediksi
// Kirim data sensor ke laptop dan terima hasil prediksi untuk ditampilkan di LCD

#include <LiquidCrystal_I2C.h>
#include <Wire.h>

// Pin definitions untuk 8 sensor MQ
int sensorPins[8] = {34, 35, 32, 33, 25, 26, 27, 14};
String sensorNames[8] = {"MQ2", "MQ3", "MQ4", "MQ135", "MQ6", "MQ7", "MQ8", "MQ9"};

// Array untuk mencatat sensor yang terhubung
bool sensorConnected[8] = {false, false, false, false, false, false, false, false};

// Konstanta normalisasi
const int MAX_ESP32_ADC = 4095;
const int MAX_RASPBERRY_MCP = 65472;

// Threshold untuk deteksi sensor
const int SENSOR_CHECK_SAMPLES = 10;
const int SENSOR_VARIATION_THRESHOLD = 50; // Minimum variasi untuk menganggap sensor terhubung

// LCD Setup (I2C Address biasanya 0x27 atau 0x3F)
LiquidCrystal_I2C lcd(0x27, 16, 2); // Address, Columns, Rows
bool lcdConnected = false; // Flag untuk status koneksi LCD
int lcdAddress = 0x27; // Address LCD yang digunakan

// Variabel untuk prediksi
String predictionResult = "Waiting...";
String confidenceStr = "";
unsigned long lastPredictionTime = 0;
bool newPrediction = false;

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  // Initialize I2C dan cek LCD
  Wire.begin();
  checkLCDConnection();
  
  if(lcdConnected) {
    // Initialize LCD dengan error handling
    Wire.beginTransmission(lcdAddress);
    byte error = Wire.endTransmission();
    if(error == 0) {
      lcd.init();
      lcd.backlight();
      safeLCDClear();
      
      // Display startup message
      safeLCDSetCursor(0, 0);
      safeLCDPrint("Food Quality");
      safeLCDSetCursor(0, 1);
      safeLCDPrint("Assessment");
      delay(2000);
      
      // Cek sensor yang terhubung
      safeLCDClear();
      safeLCDSetCursor(0, 0);
      safeLCDPrint("Checking");
      safeLCDSetCursor(0, 1);
      safeLCDPrint("sensors...");
      delay(500);
    } else {
      Serial.println("Error: LCD tidak merespon setelah init");
      lcdConnected = false;
    }
  } else {
    Serial.println("LCD tidak terhubung - hanya output ke Serial Monitor");
  }
  
  checkConnectedSensors();
  
  if(lcdConnected) {
    // Display hasil deteksi sensor
    safeLCDClear();
    safeLCDSetCursor(0, 0);
    safeLCDPrint("Sensors OK");
    delay(2000);
    
    safeLCDClear();
    safeLCDSetCursor(0, 0);
    safeLCDPrint("Sending data...");
    safeLCDSetCursor(0, 1);
    safeLCDPrint("Waiting for AI");
  }
  
  Serial.println("ESP32 Sensor + LCD Ready");
  Serial.println("Format: SENSOR_DATA,val1,val2,val3,val4,val5,val6,val7,val8");
  Serial.println("Sending test data every 3 seconds...");
}

void loop() {
  // Baca hanya sensor yang terhubung
  float sensorValues[8];
  for(int i = 0; i < 8; i++) {
    if(sensorConnected[i]) {
      sensorValues[i] = analogRead(sensorPins[i]);
    } else {
      // Jika sensor tidak terhubung, gunakan nilai 0
      sensorValues[i] = 0;
    }
    delay(10); // Small delay between readings
  }
  
  // Normalisasi data untuk kompatibilitas dengan model Raspberry Pi
  float normalizedValues[8];
  for(int i = 0; i < 8; i++) {
    if(sensorConnected[i]) {
      float raspberryCompatible = (sensorValues[i] / MAX_ESP32_ADC) * MAX_RASPBERRY_MCP;
      normalizedValues[i] = raspberryCompatible / MAX_RASPBERRY_MCP;
    } else {
      normalizedValues[i] = 0.0; // Sensor tidak terhubung = 0
    }
  }
  
  // Kirim data dalam format CSV
  String dataString = "SENSOR_DATA";
  for(int i = 0; i < 8; i++) {
    dataString += ",";
    dataString += String(normalizedValues[i], 6); // 6 decimal places
  }
  
  Serial.println(dataString);
  
  // Debug info - tampilkan raw values juga (hanya yang terhubung)
  Serial.print("Raw values: ");
  for(int i = 0; i < 8; i++) {
    Serial.print(sensorNames[i]);
    if(sensorConnected[i]) {
      Serial.print(":");
      Serial.print(sensorValues[i]);
    } else {
      Serial.print(":DISCONNECTED");
    }
    Serial.print(" ");
  }
  Serial.println();
  
  // Check for incoming prediction data
  checkForPrediction();
  
  // Update LCD display
  updateLCD();
  
  delay(3000); // Send every 3 seconds
}

void checkLCDConnection() {
  Serial.println("\n=== Checking LCD I2C Connection ===");
  
  // Coba beberapa address I2C yang umum untuk LCD
  int commonAddresses[] = {0x27, 0x3F, 0x38, 0x20};
  int numAddresses = sizeof(commonAddresses) / sizeof(commonAddresses[0]);
  
  lcdConnected = false;
  
  for(int i = 0; i < numAddresses; i++) {
    Wire.beginTransmission(commonAddresses[i]);
    byte error = Wire.endTransmission();
    
    if(error == 0) {
      lcdAddress = commonAddresses[i];
      lcdConnected = true;
      Serial.print("LCD ditemukan di address: 0x");
      Serial.println(lcdAddress, HEX);
      
      // Update LCD object dengan address yang benar jika berbeda
      if(lcdAddress != 0x27) {
        // Re-initialize dengan address yang benar
        // Catatan: LiquidCrystal_I2C tidak support perubahan address dinamis
        // Jadi kita hanya update flag-nya
      }
      break;
    }
  }
  
  if(!lcdConnected) {
    Serial.println("LCD TIDAK DITEMUKAN!");
    Serial.println("Pastikan:");
    Serial.println("1. LCD terhubung ke SDA (GPIO 21) dan SCL (GPIO 22)");
    Serial.println("2. Power LCD sudah dihubungkan");
    Serial.println("3. Address I2C LCD benar (0x27 atau 0x3F)");
  }
  
  Serial.println();
}

// Wrapper untuk operasi LCD dengan error handling
void safeLCDClear() {
  if(!lcdConnected) return;
  Wire.beginTransmission(lcdAddress);
  byte error = Wire.endTransmission();
  if(error == 0) {
    lcd.clear();
  }
}

void safeLCDSetCursor(int col, int row) {
  if(!lcdConnected) return;
  Wire.beginTransmission(lcdAddress);
  byte error = Wire.endTransmission();
  if(error == 0) {
    lcd.setCursor(col, row);
  }
}

void safeLCDPrint(String text) {
  if(!lcdConnected) return;
  Wire.beginTransmission(lcdAddress);
  byte error = Wire.endTransmission();
  if(error == 0) {
    lcd.print(text);
  }
}

void checkConnectedSensors() {
  Serial.println("\n=== Checking Connected Sensors ===");
  
  for(int i = 0; i < 8; i++) {
    int readings[SENSOR_CHECK_SAMPLES];
    int minVal = 4095;
    int maxVal = 0;
    int sum = 0;
    
    // Baca beberapa sample untuk setiap sensor
    for(int j = 0; j < SENSOR_CHECK_SAMPLES; j++) {
      readings[j] = analogRead(sensorPins[i]);
      if(readings[j] < minVal) minVal = readings[j];
      if(readings[j] > maxVal) maxVal = readings[j];
      sum += readings[j];
      delay(20);
    }
    
    // Hitung variasi
    int variation = maxVal - minVal;
    int average = sum / SENSOR_CHECK_SAMPLES;
    
    // Sensor dianggap terhubung jika:
    // 1. Variasi >= threshold (menunjukkan aktivitas)
    // 2. Nilai tidak stuck di 0 atau 4095 (kemungkinan terhubung ke GND atau VCC tanpa sensor)
    bool isConnected = (variation >= SENSOR_VARIATION_THRESHOLD) && 
                       (average > 100 && average < 3900);
    
    sensorConnected[i] = isConnected;
    
    // Print status ke Serial
    Serial.print(sensorNames[i]);
    Serial.print(" (Pin ");
    Serial.print(sensorPins[i]);
    Serial.print("): ");
    if(isConnected) {
      Serial.print("CONNECTED - Avg: ");
      Serial.print(average);
      Serial.print(", Var: ");
      Serial.println(variation);
    } else {
      Serial.print("DISCONNECTED - Avg: ");
      Serial.print(average);
      Serial.print(", Var: ");
      Serial.println(variation);
    }
  }
  
  // Tampilkan ringkasan
  Serial.println("\n=== Sensor Status Summary ===");
  int connectedCount = 0;
  for(int i = 0; i < 8; i++) {
    if(sensorConnected[i]) {
      connectedCount++;
      Serial.print(sensorNames[i]);
      Serial.print(" ");
    }
  }
  Serial.print("\nTotal connected: ");
  Serial.print(connectedCount);
  Serial.println(" out of 8\n");
}

void checkForPrediction() {
  // Check if there's data from laptop
  if(Serial.available() > 0) {
    String incomingData = Serial.readStringUntil('\n');
    incomingData.trim();
    
    // Parse prediction data
    // Format expected: PREDICTION,class,confidence
    if(incomingData.startsWith("PREDICTION,")) {
      int firstComma = incomingData.indexOf(',');
      int secondComma = incomingData.indexOf(',', firstComma + 1);
      
      if(firstComma != -1 && secondComma != -1) {
        String classStr = incomingData.substring(firstComma + 1, secondComma);
        String confidence = incomingData.substring(secondComma + 1);
        
        // Convert class to readable text
        predictionResult = interpretPrediction(classStr);
        confidenceStr = confidence;
        newPrediction = true;
        lastPredictionTime = millis();
        
        Serial.println("Received prediction: " + predictionResult + " (" + confidenceStr + ")");
      }
    }
  }
}

String interpretPrediction(String classStr) {
  int classNum = classStr.toInt();
  
  switch(classNum) {
    case 0:
      return "FRESH";
    case 1:
      return "DEGRADED";
    case 2:
      return "ERROR";
    default:
      return "UNKNOWN";
  }
}

void updateLCD() {
  if(!lcdConnected) return; // Skip jika LCD tidak terhubung
  
  if(newPrediction) {
    safeLCDClear();
    
    // Line 1: Prediction result
    safeLCDSetCursor(0, 0);
    safeLCDPrint("Status: ");
    safeLCDPrint(predictionResult);
    
    // Line 2: Confidence
    safeLCDSetCursor(0, 1);
    safeLCDPrint("Conf: ");
    safeLCDPrint(confidenceStr);
    
    newPrediction = false;
  } else {
    // Show waiting message if no new prediction
    unsigned long currentTime = millis();
    if(currentTime - lastPredictionTime > 10000) { // 10 seconds timeout
      safeLCDClear();
      safeLCDSetCursor(0, 0);
      safeLCDPrint("Waiting for");
      safeLCDSetCursor(0, 1);
      safeLCDPrint("prediction...");
    }
  }
}

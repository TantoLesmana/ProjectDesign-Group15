// ESP32 Sensor Data Sender + LCD Display untuk Prediksi
// Kirim data sensor ke laptop dan terima hasil prediksi untuk ditampilkan di LCD

#include <LiquidCrystal_I2C.h>

// Pin definitions untuk 8 sensor MQ
int sensorPins[8] = {34, 35, 32, 33, 25, 26, 27, 14};
String sensorNames[8] = {"MQ2", "MQ3", "MQ4", "MQ135", "MQ6", "MQ7", "MQ8", "MQ9"};

// Konstanta normalisasi
const int MAX_ESP32_ADC = 4095;
const int MAX_RASPBERRY_MCP = 65472;

// LCD Setup (I2C Address biasanya 0x27 atau 0x3F)
LiquidCrystal_I2C lcd(0x27, 16, 2); // Address, Columns, Rows

// Variabel untuk prediksi
String predictionResult = "Waiting...";
String confidenceStr = "";
unsigned long lastPredictionTime = 0;
bool newPrediction = false;

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  // Initialize LCD
  lcd.init();
  lcd.backlight();
  lcd.clear();
  
  // Display startup message
  lcd.setCursor(0, 0);
  lcd.print("Food Quality");
  lcd.setCursor(0, 1);
  lcd.print("Assessment");
  delay(2000);
  
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Sending data...");
  lcd.setCursor(0, 1);
  lcd.print("Waiting for AI");
  
  Serial.println("ESP32 Sensor + LCD Ready");
  Serial.println("Format: SENSOR_DATA,val1,val2,val3,val4,val5,val6,val7,val8");
  Serial.println("Sending test data every 3 seconds...");
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
  
  // Check for incoming prediction data
  checkForPrediction();
  
  // Update LCD display
  updateLCD();
  
  delay(3000); // Send every 3 seconds
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
  if(newPrediction) {
    lcd.clear();
    
    // Line 1: Prediction result
    lcd.setCursor(0, 0);
    lcd.print("Status: ");
    lcd.print(predictionResult);
    
    // Line 2: Confidence
    lcd.setCursor(0, 1);
    lcd.print("Conf: ");
    lcd.print(confidenceStr);
    
    newPrediction = false;
  } else {
    // Show waiting message if no new prediction
    unsigned long currentTime = millis();
    if(currentTime - lastPredictionTime > 10000) { // 10 seconds timeout
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("Waiting for");
      lcd.setCursor(0, 1);
      lcd.print("prediction...");
    }
  }
}

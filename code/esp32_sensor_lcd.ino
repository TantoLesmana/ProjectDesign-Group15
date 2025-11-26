// ESP32 Sensor Data Sender + LCD Display untuk Prediksi
// Kirim data sensor ke laptop via WiFi REST API dan terima hasil prediksi untuk ditampilkan di LCD

#include <LiquidCrystal_I2C.h>
#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// Pin definitions untuk 2 sensor MQ
int sensorPins[2] = {34, 33};
String sensorNames[2] = {"MQ2", "MQ3"};

// Array untuk mencatat sensor yang terhubung
bool sensorConnected[2] = {false, false};

// Konstanta normalisasi
const int MAX_ESP32_ADC = 4095;
const int MAX_RASPBERRY_MCP = 65472;

// Threshold untuk deteksi sensor (tidak digunakan lagi, selalu baca pin 34)
const int SENSOR_CHECK_SAMPLES = 10;
const int SENSOR_VARIATION_THRESHOLD = 50; // Minimum variasi untuk menganggap sensor terhubung

// LCD Setup (I2C Address biasanya 0x27 atau 0x3F)
LiquidCrystal_I2C lcd(0x27, 16, 2); // Address, Columns, Rows
bool lcdConnected = false; // Flag untuk status koneksi LCD
int lcdAddress = 0x27; // Address LCD yang digunakan

// WiFi Configuration - UBAH SESUAI JARINGAN ANDA
const char* ssid = "S20FE";           // Ganti dengan SSID WiFi Anda
const char* password = "pppppppp";   // Ganti dengan password WiFi Anda

// Server Configuration - UBAH SESUAI IP LAPTOP ANDA
const char* serverURL = "http://10.100.98.250:5000/api/sensor-data";  // Ganti dengan IP laptop Anda

// WiFi status
bool wifiConnected = false;
unsigned long lastWiFiReconnectAttempt = 0;
const unsigned long WIFI_RECONNECT_INTERVAL = 30000; // 30 seconds

// Boot and watchdog
unsigned long bootTime = 0;
bool systemReady = false;
unsigned long lastWatchdogFeed = 0;
const unsigned long WATCHDOG_FEED_INTERVAL = 10000; // Feed watchdog every 10 seconds

// Variabel untuk prediksi
String predictionResult = "Waiting...";
String confidenceStr = "";
unsigned long lastPredictionTime = 0;
bool newPrediction = false;

void setup() {
  // CRITICAL: Delay lebih lama untuk memastikan boot sequence complete
  // Terutama penting saat boot tanpa USB (hanya Vin)
  delay(3000);  // Delay awal untuk stabilisasi power (diperpanjang ke 3 detik)
  
  // Initialize Serial - NON-BLOCKING
  // Jangan tunggu Serial ready karena bisa block saat tidak ada USB
  Serial.begin(115200);
  delay(100); // Small delay untuk Serial init, tapi tidak block
  
  // Tambahan delay untuk memastikan semua peripheral ready
  delay(1000);
  
  bootTime = millis();
  
  // Print boot info (jika Serial available)
  if(Serial) {
    Serial.println("\n\n==========================================");
    Serial.println("ESP32 Sensor + LCD + WiFi REST API");
    Serial.println("==========================================");
    Serial.print("Boot time: ");
    Serial.print(bootTime);
    Serial.println(" ms");
    Serial.println("Watchdog: Using software watchdog (feed in loop)");
  }
  
  // Initialize I2C FIRST (sebelum WiFi) untuk memastikan hardware ready
  Wire.begin();
  delay(100);
  
  // Initialize LCD early untuk status display
  checkLCDConnection();
  if(lcdConnected) {
    Wire.beginTransmission(lcdAddress);
    byte error = Wire.endTransmission();
    if(error == 0) {
      lcd.init();
      lcd.backlight();
      safeLCDClear();
      safeLCDSetCursor(0, 0);
      safeLCDPrint("Booting...");
      safeLCDSetCursor(0, 1);
      safeLCDPrint("Please wait");
    }
  }
  
  // Connect to WiFi dengan retry yang lebih robust
  // CRITICAL: Pastikan WiFi connect sebelum lanjut
  connectToWiFi();
  
  // Jika WiFi belum connect, coba sekali lagi dengan delay lebih lama
  if(!wifiConnected) {
    if(lcdConnected) {
      safeLCDClear();
      safeLCDSetCursor(0, 0);
      safeLCDPrint("WiFi Retry...");
      safeLCDSetCursor(0, 1);
      safeLCDPrint("Wait 5 sec");
    }
    delay(5000); // Tunggu 5 detik sebelum retry
    connectToWiFi();
  }
  
  // LCD sudah di-init di atas, sekarang update display
  if(lcdConnected) {
    safeLCDClear();
    safeLCDSetCursor(0, 0);
    safeLCDPrint("Food Quality");
    safeLCDSetCursor(0, 1);
    safeLCDPrint("Assessment");
    delay(1000);
    
    // Display WiFi status
    safeLCDClear();
    safeLCDSetCursor(0, 0);
    if(wifiConnected) {
      safeLCDPrint("WiFi: OK");
      safeLCDSetCursor(0, 1);
      String ipStr = WiFi.localIP().toString();
      // Tampilkan 2 octet terakhir IP
      int lastDot = ipStr.lastIndexOf('.');
      int secondLastDot = ipStr.lastIndexOf('.', lastDot - 1);
      if(secondLastDot > 0) {
        safeLCDPrint(ipStr.substring(secondLastDot + 1));
      } else {
        safeLCDPrint("Connected");
      }
    } else {
      safeLCDPrint("WiFi: FAIL");
      safeLCDSetCursor(0, 1);
      safeLCDPrint("Will retry...");
    }
    delay(2000);
  }
  
  // Set sensor sebagai terhubung (pin analog selalu bisa dibaca)
  sensorConnected[0] = true; // Pin 34 - MQ2
  sensorConnected[1] = true; // Pin 33 - MQ3
  
  // Test baca kedua pin untuk verifikasi
  int testValue1 = analogRead(sensorPins[0]);
  int testValue2 = analogRead(sensorPins[1]);
  Serial.print("Test read pin 34 (MQ2): ");
  Serial.println(testValue1);
  Serial.print("Test read pin 33 (MQ3): ");
  Serial.println(testValue2);
  
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
  
  // Mark system as ready
  systemReady = true;
  unsigned long setupTime = millis() - bootTime;
  
  if(Serial) {
    Serial.println("\n==========================================");
    Serial.println("ESP32 Sensor + LCD Ready");
    Serial.print("Setup completed in: ");
    Serial.print(setupTime);
    Serial.println(" ms");
    
    if(wifiConnected) {
      Serial.print("Server URL: ");
      Serial.println(serverURL);
      Serial.println("Sending data via HTTP POST every 3 seconds...");
    } else {
      Serial.println("⚠️ WiFi not connected - will retry in loop");
    }
    Serial.println("==========================================\n");
  }
  
  // Update LCD dengan status final
  if(lcdConnected) {
    safeLCDClear();
    if(wifiConnected) {
      safeLCDSetCursor(0, 0);
      safeLCDPrint("Ready!");
      safeLCDSetCursor(0, 1);
      safeLCDPrint("Sending data...");
    } else {
      safeLCDSetCursor(0, 0);
      safeLCDPrint("WiFi Error");
      safeLCDSetCursor(0, 1);
      safeLCDPrint("Retrying...");
    }
  }
}

void loop() {
  // Software watchdog: check jika loop stuck lebih dari 30 detik
  unsigned long currentTime = millis();
  if(currentTime - lastWatchdogFeed > 30000) {
    // Jika lebih dari 30 detik tanpa feed, kemungkinan stuck
    Serial.println("⚠️ Warning: Loop may be stuck, resetting...");
    delay(100);
    ESP.restart(); // Soft reset
  }
  lastWatchdogFeed = currentTime;
  
  // Pastikan system sudah ready
  if(!systemReady) {
    delay(100);
    return;
  }
  
  // Check WiFi connection and reconnect if needed
  // CRITICAL: Pastikan WiFi selalu connect sebelum kirim data
  if(WiFi.status() != WL_CONNECTED) {
    wifiConnected = false;
    unsigned long currentTime = millis();
    if(currentTime - lastWiFiReconnectAttempt >= WIFI_RECONNECT_INTERVAL) {
      if(Serial) {
        Serial.println("\n⚠️ WiFi disconnected. Attempting to reconnect...");
      }
      if(lcdConnected) {
        safeLCDClear();
        safeLCDSetCursor(0, 0);
        safeLCDPrint("WiFi Lost!");
        safeLCDSetCursor(0, 1);
        safeLCDPrint("Reconnecting...");
      }
      connectToWiFi();
      lastWiFiReconnectAttempt = currentTime;
    }
  } else {
    // WiFi connected - update flag
    if(!wifiConnected) {
      wifiConnected = true;
      if(Serial) {
        Serial.println("✅ WiFi connected!");
      }
      if(lcdConnected) {
        safeLCDClear();
        safeLCDSetCursor(0, 0);
        safeLCDPrint("WiFi: OK");
        safeLCDSetCursor(0, 1);
        safeLCDPrint("Connected!");
        delay(1000);
      }
    }
  }
  
  // Baca pin analog 34 dan 33 (selalu baca, tidak perlu cek sensorConnected)
  float sensorValues[2];
  for(int i = 0; i < 2; i++) {
    sensorValues[i] = analogRead(sensorPins[i]);
    delay(10); // Small delay between readings
  }
  
  // Normalisasi data untuk kompatibilitas dengan model Raspberry Pi
  float normalizedValues[2];
  for(int i = 0; i < 2; i++) {
    float raspberryCompatible = (sensorValues[i] / MAX_ESP32_ADC) * MAX_RASPBERRY_MCP;
    normalizedValues[i] = raspberryCompatible / MAX_RASPBERRY_MCP;
  }
  
  // Debug info - tampilkan raw values (jika Serial available)
  if(Serial) {
    Serial.print("Raw values: ");
    for(int i = 0; i < 2; i++) {
      Serial.print(sensorNames[i]);
      Serial.print(":");
      Serial.print(sensorValues[i]);
      Serial.print(" ");
    }
    Serial.println();
  }
  
  // CRITICAL: Kirim data via HTTP POST jika WiFi terhubung
  // Jangan skip hanya karena Serial tidak available
  if(wifiConnected && WiFi.status() == WL_CONNECTED) {
    sendSensorDataViaHTTP(normalizedValues);
  } else {
    if(Serial) {
      Serial.println("⚠️ Skipping HTTP request - WiFi not connected");
    }
    if(lcdConnected) {
      safeLCDSetCursor(0, 0);
      safeLCDPrint("No WiFi");
      safeLCDSetCursor(0, 1);
      safeLCDPrint("Retrying...");
    }
  }
  
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
  
  for(int i = 0; i < 2; i++) {
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
  for(int i = 0; i < 2; i++) {
    if(sensorConnected[i]) {
      connectedCount++;
      Serial.print(sensorNames[i]);
      Serial.print(" ");
    }
  }
  Serial.print("\nTotal connected: ");
  Serial.print(connectedCount);
  Serial.println(" out of 2\n");
}

void connectToWiFi() {
  if(Serial) {
    Serial.println("\n=== Connecting to WiFi ===");
    Serial.print("SSID: ");
    Serial.println(ssid);
  }
  
  // Disconnect previous connection if any
  WiFi.disconnect(true);
  delay(1000); // Delay lebih lama untuk memastikan disconnect complete
  
  // Set WiFi mode
  WiFi.mode(WIFI_STA);
  
  // Set WiFi power to maximum (untuk range yang lebih baik)
  WiFi.setTxPower(WIFI_POWER_19_5dBm);
  
  // Start connection
  WiFi.begin(ssid, password);
  
  // Retry dengan timeout yang lebih lama (40 detik untuk boot tanpa USB)
  int attempts = 0;
  int maxAttempts = 80;  // 80 x 500ms = 40 detik
  
  while(WiFi.status() != WL_CONNECTED && attempts < maxAttempts) {
    delay(500);
    if(Serial) {
      Serial.print(".");
    }
    attempts++;
    
    // Update LCD setiap 5 detik
    if(lcdConnected && attempts % 10 == 0) {
      safeLCDSetCursor(0, 1);
      safeLCDPrint("Connecting...");
    }
  }
  
  if(WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    if(Serial) {
      Serial.println("\n✅ WiFi Connected!");
      Serial.print("IP Address: ");
      Serial.println(WiFi.localIP());
      Serial.print("Signal Strength (RSSI): ");
      Serial.print(WiFi.RSSI());
      Serial.println(" dBm");
      Serial.print("Connection time: ");
      Serial.print(attempts * 500);
      Serial.println(" ms");
    }
    
    if(lcdConnected) {
      safeLCDClear();
      safeLCDSetCursor(0, 0);
      safeLCDPrint("WiFi: OK");
      safeLCDSetCursor(0, 1);
      String ipStr = WiFi.localIP().toString();
      // Show last 2 octets of IP
      int lastDot = ipStr.lastIndexOf('.');
      int secondLastDot = ipStr.lastIndexOf('.', lastDot - 1);
      if(secondLastDot > 0) {
        safeLCDPrint(ipStr.substring(secondLastDot + 1));
      } else {
        safeLCDPrint("Connected");
      }
      delay(2000);
    }
  } else {
    wifiConnected = false;
    if(Serial) {
      Serial.println("\n❌ WiFi Connection Failed!");
      Serial.print("Attempted for: ");
      Serial.print(attempts * 500);
      Serial.println(" ms");
      Serial.println("Please check:");
      Serial.println("1. SSID and password are correct");
      Serial.println("2. WiFi router is powered on");
      Serial.println("3. ESP32 is within range");
      Serial.println("4. Will retry in 30 seconds...");
    }
    
    if(lcdConnected) {
      safeLCDClear();
      safeLCDSetCursor(0, 0);
      safeLCDPrint("WiFi: FAIL");
      safeLCDSetCursor(0, 1);
      safeLCDPrint("Retry in 30s");
    }
  }
  if(Serial) {
    Serial.println();
  }
}

void sendSensorDataViaHTTP(float normalizedValues[2]) {
  if(!wifiConnected || WiFi.status() != WL_CONNECTED) {
    return;
  }
  
  HTTPClient http;
  
  // Prepare JSON payload
  StaticJsonDocument<200> doc;
  doc["sensors"] = JsonArray();
  for(int i = 0; i < 2; i++) {
    doc["sensors"].add(normalizedValues[i]);
  }
  
  String jsonPayload;
  serializeJson(doc, jsonPayload);
  
  if(Serial) {
    Serial.print("📤 Sending HTTP POST to: ");
    Serial.println(serverURL);
    Serial.print("Payload: ");
    Serial.println(jsonPayload);
  }
  
  // Start HTTP connection
  http.begin(serverURL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(15000); // 15 second timeout (lebih lama untuk network yang lambat)
  http.setConnectTimeout(8000); // 8 second connection timeout
  
  // Send POST request
  int httpResponseCode = http.POST(jsonPayload);
  
  if(httpResponseCode > 0) {
    if(Serial) {
      Serial.print("✅ HTTP Response code: ");
      Serial.println(httpResponseCode);
    }
    
    if(httpResponseCode == 200) {
      String response = http.getString();
      if(Serial) {
        Serial.print("📥 Response: ");
        Serial.println(response);
      }
      
      // Parse JSON response
      parsePredictionResponse(response);
    } else {
      if(Serial) {
        Serial.print("⚠️ HTTP Error: ");
        Serial.println(httpResponseCode);
        Serial.print("Response: ");
        Serial.println(http.getString());
      }
    }
  } else {
    if(Serial) {
      Serial.print("❌ HTTP Request failed: ");
      Serial.println(http.errorToString(httpResponseCode));
    }
    
    // Update LCD dengan error status
    if(lcdConnected) {
      safeLCDSetCursor(0, 0);
      safeLCDPrint("HTTP Error");
      safeLCDSetCursor(0, 1);
      safeLCDPrint("Retrying...");
    }
  }
  
  http.end();
}

void parsePredictionResponse(String jsonResponse) {
  StaticJsonDocument<200> doc;
  DeserializationError error = deserializeJson(doc, jsonResponse);
  
  if(error) {
    Serial.print("❌ JSON parsing failed: ");
    Serial.println(error.c_str());
    return;
  }
  
  // Extract prediction and confidence from JSON
  if(doc.containsKey("prediction") && doc.containsKey("confidence")) {
    int predictionClass = doc["prediction"];
    float confidence = doc["confidence"];
    
    // Convert class to readable text
    predictionResult = interpretPrediction(String(predictionClass));
    confidenceStr = String(confidence, 3);
    newPrediction = true;
    lastPredictionTime = millis();
    
    Serial.print("✅ Received prediction: ");
    Serial.print(predictionResult);
    Serial.print(" (");
    Serial.print(confidenceStr);
    Serial.println(")");
  } else {
    Serial.println("⚠️ Invalid response format - missing prediction or confidence");
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

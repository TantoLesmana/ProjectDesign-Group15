// ESP32 Sensor Data Sender untuk Prediksi
// Kirim data dari 8 sensor MQ ke laptop via WiFi REST API

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// Pin definitions untuk 8 sensor MQ dengan urutan yang diperbarui
int sensorPins[8] = {34, 35, 32, 14, 33, 25, 26, 27};
String sensorNames[8] = {"MQ2", "MQ3", "MQ4", "MQ135", "MQ6", "MQ7", "MQ8", "MQ9"};

// Array untuk mencatat sensor yang terhubung
bool sensorConnected[8] = {false, false, false, false, false, false, false, false};

// Konstanta normalisasi
const int MAX_ESP32_ADC = 4095;
const int MAX_RASPBERRY_MCP = 65472;

// Threshold untuk deteksi sensor
const int SENSOR_CHECK_SAMPLES = 10;
const int SENSOR_VARIATION_THRESHOLD = 50; // Minimum variasi untuk menganggap sensor terhubung

// WiFi Configuration - UBAH SESUAI JARINGAN ANDA
const char* ssid = "S20FE";           // Ganti dengan SSID WiFi Anda
const char* password = "pppppppp";   // Ganti dengan password WiFi Anda

// Server Configuration - UBAH SESUAI IP LAPTOP ANDA
const char* serverURL = "http://10.121.67.27:5000/api/sensor-data";  // Ganti dengan IP laptop Anda

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
  
  // Initialize Serial
  Serial.begin(115200);
  delay(100); // Small delay untuk Serial init
  
  // Tambahan delay untuk memastikan semua peripheral ready
  delay(1000);
  
  bootTime = millis();
  
  // Print boot info
  Serial.println("\n\n==========================================");
  Serial.println("ESP32 8 Sensor MQ + WiFi REST API");
  Serial.println("==========================================");
  Serial.print("Boot time: ");
  Serial.print(bootTime);
  Serial.println(" ms");
  Serial.println("Watchdog: Using software watchdog (feed in loop)");
  Serial.println("Sensor order: MQ2, MQ3, MQ4, MQ135, MQ6, MQ7, MQ8, MQ9");
  
  // Connect to WiFi dengan retry yang lebih robust
  connectToWiFi();
  
  // Jika WiFi belum connect, coba sekali lagi dengan delay lebih lama
  if(!wifiConnected) {
    Serial.println("WiFi Retry in 5 seconds...");
    delay(5000); // Tunggu 5 detik sebelum retry
    connectToWiFi();
  }
  
  // Deteksi sensor yang terhubung
  checkConnectedSensors();
  
  // Test baca semua pin untuk verifikasi
  Serial.println("\n=== Sensor Test Readings ===");
  for(int i = 0; i < 8; i++) {
    int testValue = analogRead(sensorPins[i]);
    Serial.print(sensorNames[i]);
    Serial.print(" (Pin ");
    Serial.print(sensorPins[i]);
    Serial.print("): ");
    Serial.print(testValue);
    Serial.print(" - ");
    Serial.println(sensorConnected[i] ? "CONNECTED" : "DISCONNECTED");
    delay(10);
  }
  
  // Mark system as ready
  systemReady = true;
  unsigned long setupTime = millis() - bootTime;
  
  Serial.println("\n==========================================");
  Serial.println("ESP32 8 Sensor MQ Ready");
  Serial.print("Setup completed in: ");
  Serial.print(setupTime);
  Serial.println(" ms");
  Serial.print("Connected sensors: ");
  int connectedCount = 0;
  for(int i = 0; i < 8; i++) {
    if(sensorConnected[i]) connectedCount++;
  }
  Serial.print(connectedCount);
  Serial.println(" out of 8");
  
  if(wifiConnected) {
    Serial.print("Server URL: ");
    Serial.println(serverURL);
    Serial.println("Sending data via HTTP POST every 3 seconds...");
  } else {
    Serial.println("⚠️ WiFi not connected - will retry in loop");
  }
  Serial.println("==========================================\n");
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
  if(WiFi.status() != WL_CONNECTED) {
    wifiConnected = false;
    unsigned long currentTime = millis();
    if(currentTime - lastWiFiReconnectAttempt >= WIFI_RECONNECT_INTERVAL) {
      Serial.println("\n⚠️ WiFi disconnected. Attempting to reconnect...");
      connectToWiFi();
      lastWiFiReconnectAttempt = currentTime;
    }
  } else {
    // WiFi connected - update flag
    if(!wifiConnected) {
      wifiConnected = true;
      Serial.println("✅ WiFi connected!");
    }
  }
  
  // Baca semua sensor MQ dengan urutan baru
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
  
  // Debug info - tampilkan raw values
  Serial.print("Raw sensor values: ");
  for(int i = 0; i < 8; i++) {
    Serial.print(sensorNames[i]);
    Serial.print(":");
    Serial.print(sensorValues[i]);
    Serial.print(" ");
  }
  Serial.println();
  
  // Kirim data via HTTP POST jika WiFi terhubung
  if(wifiConnected && WiFi.status() == WL_CONNECTED) {
    sendSensorDataViaHTTP(normalizedValues);
  } else {
    Serial.println("⚠️ Skipping HTTP request - WiFi not connected");
  }
  
  delay(3000); // Send every 3 seconds
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

void connectToWiFi() {
  Serial.println("\n=== Connecting to WiFi ===");
  Serial.print("SSID: ");
  Serial.println(ssid);
  
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
    Serial.print(".");
    attempts++;
  }
  
  if(WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    Serial.println("\n✅ WiFi Connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Signal Strength (RSSI): ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
    Serial.print("Connection time: ");
    Serial.print(attempts * 500);
    Serial.println(" ms");
  } else {
    wifiConnected = false;
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
  Serial.println();
}

void sendSensorDataViaHTTP(float normalizedValues[8]) {
  if(!wifiConnected || WiFi.status() != WL_CONNECTED) {
    return;
  }
  
  HTTPClient http;
  
  // Prepare JSON payload dengan 8 sensor
  StaticJsonDocument<300> doc; // Ukuran diperbesar untuk 8 sensor
  doc["sensors"] = JsonArray();
  for(int i = 0; i < 8; i++) {
    doc["sensors"].add(normalizedValues[i]);
  }
  
  String jsonPayload;
  serializeJson(doc, jsonPayload);
  
  Serial.print("📤 Sending HTTP POST to: ");
  Serial.println(serverURL);
  Serial.print("Payload: ");
  Serial.println(jsonPayload);
  
  // Start HTTP connection
  http.begin(serverURL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(15000); // 15 second timeout
  http.setConnectTimeout(8000); // 8 second connection timeout
  
  // Send POST request
  int httpResponseCode = http.POST(jsonPayload);
  
  if(httpResponseCode > 0) {
    Serial.print("✅ HTTP Response code: ");
    Serial.println(httpResponseCode);
    
    if(httpResponseCode == 200) {
      String response = http.getString();
      Serial.print("📥 Response: ");
      Serial.println(response);
      
      // Parse JSON response
      parsePredictionResponse(response);
    } else {
      Serial.print("⚠️ HTTP Error: ");
      Serial.println(httpResponseCode);
      Serial.print("Response: ");
      Serial.println(http.getString());
    }
  } else {
    Serial.print("❌ HTTP Request failed: ");
    Serial.println(http.errorToString(httpResponseCode));
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
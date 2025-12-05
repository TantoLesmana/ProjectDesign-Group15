#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <lvgl.h>
#include <TFT_eSPI.h>
#include <XPT2046_Touchscreen.h>
#include <time.h>

// Konfigurasi WiFi
const char* ssid = "S20FE";
const char* password = "pppppppp";

// Konfigurasi Server API
const char* serverURL = "http://10.121.67.27:5000"; // Ganti dengan IP server Anda
const char* lastPredictionEndpoint = "/api/last-prediction";

// Konfigurasi LCD dan Touchscreen
#define SCREEN_WIDTH 240
#define SCREEN_HEIGHT 320

// Touchscreen pins
#define XPT2046_IRQ 36
#define XPT2046_MOSI 32
#define XPT2046_MISO 39
#define XPT2046_CLK 25
#define XPT2046_CS 33

SPIClass touchscreenSPI = SPIClass(VSPI);
XPT2046_Touchscreen touchscreen(XPT2046_CS, XPT2046_IRQ);

// Buffer untuk LVGL
#define DRAW_BUF_SIZE (SCREEN_WIDTH * SCREEN_HEIGHT / 10 * (LV_COLOR_DEPTH / 8))
uint32_t draw_buf[DRAW_BUF_SIZE / 4];

// GUI OBJECTS
static lv_obj_t *labelStatus;
static lv_obj_t *labelNote;
static lv_obj_t *labelMQ2;
static lv_obj_t *labelMQ3;
static lv_obj_t *labelConfidence;
static lv_obj_t *labelTime;
static lv_obj_t *labelServerStatus;

// Variabel global
String lastPrediction = "N/A";
String lastConfidence = "N/A";
String mq2Value = "N/A";
String mq3Value = "N/A";
String lastUpdateTime = "N/A";
bool serverConnected = false;

// Timer untuk refresh data
unsigned long lastUpdate = 0;
const unsigned long updateInterval = 3000; // Update setiap 3 detik

// Touchscreen driver untuk LVGL
void touchscreen_read(lv_indev_t * indev, lv_indev_data_t * data) {
  static int lastX, lastY;
  
  if(touchscreen.tirqTouched() && touchscreen.touched()) {
    TS_Point p = touchscreen.getPoint();
    // Kalibrasi touchscreen sesuai dengan layar Anda
    int x = map(p.x, 200, 3700, 1, SCREEN_WIDTH);
    int y = map(p.y, 240, 3800, 1, SCREEN_HEIGHT);
    
    data->state = LV_INDEV_STATE_PRESSED;
    data->point.x = x;
    data->point.y = y;
    
    lastX = x;
    lastY = y;
  } else {
    data->state = LV_INDEV_STATE_RELEASED;
  }
}

// Handler untuk tombol refresh manual
static void btn_refresh_handler(lv_event_t *e) {
  lv_label_set_text(labelServerStatus, "Mengambil data...");
  fetchLastPrediction();
}

// Handler untuk tombol koneksi WiFi
static void btn_wifi_handler(lv_event_t *e) {
  if (WiFi.status() == WL_CONNECTED) {
    lv_label_set_text(labelServerStatus, "WiFi Connected!");
  } else {
    lv_label_set_text(labelServerStatus, "WiFi Disconnected");
    WiFi.begin(ssid, password);
  }
}

// Fungsi untuk mengambil data prediksi dari server
void fetchLastPrediction() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected!");
    serverConnected = false;
    lv_label_set_text(labelServerStatus, "WiFi Disconnected");
    return;
  }
  
  HTTPClient http;
  String url = String(serverURL) + String(lastPredictionEndpoint);
  
  Serial.println("Fetching from: " + url);
  
  http.begin(url);
  http.setTimeout(5000); // Timeout 5 detik
  
  int httpCode = http.GET();
  
  if (httpCode == HTTP_CODE_OK) {
    String payload = http.getString();
    Serial.println("Response: " + payload);
    
    // Parse JSON response
    DynamicJsonDocument doc(2048);
    DeserializationError error = deserializeJson(doc, payload);
    
    if (!error) {
      bool success = doc["success"];
      if (success) {
        JsonObject data = doc["data"];
        
        // Ambil data prediksi
        lastPrediction = data["prediction_label"].as<String>();
        lastConfidence = String(data["confidence"].as<float>(), 2);
        
        // Ambil data sensor
        JsonArray sensorData = data["sensor_data"];
        if (sensorData.size() >= 2) {
          mq2Value = String(sensorData[0].as<float>(), 4);
          mq3Value = String(sensorData[1].as<float>(), 4);
        }
        
        // Ambil timestamp
        lastUpdateTime = data["datetime"].as<String>();
        // Hanya ambil jam dan menit
        int timeIndex = lastUpdateTime.indexOf("T");
        if (timeIndex > 0) {
          String timePart = lastUpdateTime.substring(timeIndex + 1, timeIndex + 6);
          lastUpdateTime = timePart;
        }
        
        serverConnected = true;
        lv_label_set_text(labelServerStatus, "Connected ✓");
        
        // Update GUI
        updateDisplay();
        
      } else {
        lv_label_set_text(labelServerStatus, "No prediction data");
      }
    } else {
      Serial.println("JSON parse error!");
      lv_label_set_text(labelServerStatus, "JSON Error");
    }
  } else {
    Serial.printf("HTTP GET failed, error: %s\n", http.errorToString(httpCode).c_str());
    serverConnected = false;
    lv_label_set_text(labelServerStatus, "Server Error");
  }
  
  http.end();
}

// Fungsi untuk update tampilan LCD
void updateDisplay() {
  // Update status prediksi
  String statusText = "Status: " + lastPrediction;
  lv_label_set_text(labelStatus, statusText.c_str());
  
  // Update nilai sensor
  lv_label_set_text(labelMQ2, ("MQ2: " + mq2Value).c_str());
  lv_label_set_text(labelMQ3, ("MQ3: " + mq3Value).c_str());
  
  // Update confidence
  lv_label_set_text(labelConfidence, ("Confidence: " + lastConfidence).c_str());
  
  // Update waktu
  lv_label_set_text(labelTime, ("Last: " + lastUpdateTime).c_str());
  
  // Warna berdasarkan prediksi
  if (lastPrediction == "FRESH") {
    lv_obj_set_style_text_color(labelStatus, lv_color_hex(0x00FF00), LV_PART_MAIN);
  } else if (lastPrediction == "DEGRADED") {
    lv_obj_set_style_text_color(labelStatus, lv_color_hex(0xFFA500), LV_PART_MAIN);
  } else if (lastPrediction == "ERROR") {
    lv_label_set_text(labelNote, "Error: Check Sensors!");
    lv_obj_set_style_text_color(labelStatus, lv_color_hex(0xFF0000), LV_PART_MAIN);
  }
}

// Fungsi untuk membuat GUI utama
void lv_create_main_gui(void) {
  // Style untuk judul
  static lv_style_t title_style;
  lv_style_init(&title_style);
  lv_style_set_text_font(&title_style, &lv_font_montserrat_16);
  lv_style_set_text_align(&title_style, LV_TEXT_ALIGN_CENTER);
  
  // Judul
  lv_obj_t *title = lv_label_create(lv_scr_act());
  lv_obj_add_style(title, &title_style, 0);
  lv_label_set_text(title, "FOOD QUALITY DETECTOR");
  lv_obj_set_width(title, 220);
  lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 10);
  
  // Status koneksi server
  labelServerStatus = lv_label_create(lv_scr_act());
  lv_label_set_text(labelServerStatus, "Connecting...");
  lv_obj_set_width(labelServerStatus, 200);
  lv_obj_set_style_text_align(labelServerStatus, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_align(labelServerStatus, LV_ALIGN_TOP_MID, 0, 35);
  
  // Garis pemisah
  lv_obj_t *line = lv_line_create(lv_scr_act());
  static lv_point_t line_points[] = {{10, 60}, {230, 60}};
  lv_line_set_points(line, line_points, 2);
  
  // Label Status Deteksi
  labelStatus = lv_label_create(lv_scr_act());
  lv_label_set_long_mode(labelStatus, LV_LABEL_LONG_WRAP);
  lv_label_set_text(labelStatus, "Status: -");
  lv_obj_set_width(labelStatus, 200);
  lv_obj_set_style_text_font(labelStatus, &lv_font_montserrat_20, 0);
  lv_obj_set_style_text_align(labelStatus, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_align(labelStatus, LV_ALIGN_CENTER, 0, -50);
  
  // Label Confidence
  labelConfidence = lv_label_create(lv_scr_act());
  lv_label_set_text(labelConfidence, "Confidence: -");
  lv_obj_set_width(labelConfidence, 200);
  lv_obj_set_style_text_align(labelConfidence, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_align(labelConfidence, LV_ALIGN_CENTER, 0, -20);
  
  // Label Sensor MQ2
  labelMQ2 = lv_label_create(lv_scr_act());
  lv_label_set_text(labelMQ2, "MQ2: -");
  lv_obj_set_width(labelMQ2, 200);
  lv_obj_set_style_text_align(labelMQ2, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_align(labelMQ2, LV_ALIGN_CENTER, 0, 5);
  
  // Label Sensor MQ3
  labelMQ3 = lv_label_create(lv_scr_act());
  lv_label_set_text(labelMQ3, "MQ3: -");
  lv_obj_set_width(labelMQ3, 200);
  lv_obj_set_style_text_align(labelMQ3, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_align(labelMQ3, LV_ALIGN_CENTER, 0, 25);
  
  // Label Waktu Update
  labelTime = lv_label_create(lv_scr_act());
  lv_label_set_text(labelTime, "Last: -");
  lv_obj_set_width(labelTime, 200);
  lv_obj_set_style_text_align(labelTime, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_set_style_text_font(labelTime, &lv_font_montserrat_12, 0);
  lv_obj_align(labelTime, LV_ALIGN_CENTER, 0, 50);
  
  // Label Note
  labelNote = lv_label_create(lv_scr_act());
  lv_label_set_long_mode(labelNote, LV_LABEL_LONG_WRAP);
  lv_label_set_text(labelNote, "REST API Connected");
  lv_obj_set_width(labelNote, 200);
  lv_obj_set_style_text_align(labelNote, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_align(labelNote, LV_ALIGN_BOTTOM_MID, 0, -40);
  
  // Tombol Refresh
  lv_obj_t *btnRefresh = lv_button_create(lv_scr_act());
  lv_obj_add_event_cb(btnRefresh, btn_refresh_handler, LV_EVENT_CLICKED, NULL);
  lv_obj_align(btnRefresh, LV_ALIGN_BOTTOM_LEFT, 20, -10);
  lv_obj_set_size(btnRefresh, 80, 40);
  
  lv_obj_t *btnRefreshLabel = lv_label_create(btnRefresh);
  lv_label_set_text(btnRefreshLabel, "REFRESH");
  lv_obj_center(btnRefreshLabel);
  
  // Tombol WiFi
  lv_obj_t *btnWifi = lv_button_create(lv_scr_act());
  lv_obj_add_event_cb(btnWifi, btn_wifi_handler, LV_EVENT_CLICKED, NULL);
  lv_obj_align(btnWifi, LV_ALIGN_BOTTOM_RIGHT, -20, -10);
  lv_obj_set_size(btnWifi, 80, 40);
  
  lv_obj_t *btnWifiLabel = lv_label_create(btnWifi);
  lv_label_set_text(btnWifiLabel, "WiFi");
  lv_obj_center(btnWifiLabel);
}

// Setup
void setup() {
  Serial.begin(115200);
  
  // Inisialisasi WiFi
  Serial.println("Connecting to WiFi...");
  WiFi.begin(ssid, password);
  
  // Tunggu koneksi WiFi
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi connection failed!");
  }
  
  // Inisialisasi LVGL
  lv_init();
  
  // Inisialisasi touchscreen
  touchscreenSPI.begin(XPT2046_CLK, XPT2046_MISO, XPT2046_MOSI, XPT2046_CS);
  touchscreen.begin(touchscreenSPI);
  touchscreen.setRotation(2);
  
  // Setup display
  lv_display_t *disp = lv_tft_espi_create(SCREEN_WIDTH, SCREEN_HEIGHT, draw_buf, sizeof(draw_buf));
  lv_display_set_rotation(disp, LV_DISPLAY_ROTATION_270);
  
  // Setup input device (touchscreen)
  lv_indev_t *indev = lv_indev_create();
  lv_indev_set_type(indev, LV_INDEV_TYPE_POINTER);
  lv_indev_set_read_cb(indev, touchscreen_read);
  
  // Buat GUI
  lv_create_main_gui();
  
  // Ambil data pertama kali
  fetchLastPrediction();
  
  Serial.println("Setup completed!");
}

// Loop utama
void loop() {
  // Handle LVGL tasks
  lv_task_handler();
  lv_tick_inc(5);
  
  // Update data secara periodik
  unsigned long currentMillis = millis();
  if (currentMillis - lastUpdate >= updateInterval) {
    fetchLastPrediction();
    lastUpdate = currentMillis;
  }
  
  delay(10);
}

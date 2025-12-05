#define BLYNK_TEMPLATE_ID "TMPL6Ic1HFZR2"
#define BLYNK_TEMPLATE_NAME "finpro iot"
#define BLYNK_AUTH_TOKEN "xPCktTn6TcbyRq6AQ6jMq2i0aaOUd-Jn"


#include <lvgl.h>
#include <TFT_eSPI.h>

#include <XPT2046_Touchscreen.h>
#include <Wire.h>
#include <WiFi.h>
#include <BlynkSimpleEsp32.h>
#include <time.h>

const char ntpServer[] = "id.pool.ntp.org";
String currentTime;
String currentHourMinute;

char ssid[] = "loltotan";
char pass[] = "ntnt1234";

double suhu, kelembapan, oxygen;

// Touchscreen pins
#define XPT2046_IRQ 36
#define XPT2046_MOSI 32
#define XPT2046_MISO 39
#define XPT2046_CLK 25
#define XPT2046_CS 33

SPIClass touchscreenSPI = SPIClass(VSPI);
XPT2046_Touchscreen touchscreen(XPT2046_CS, XPT2046_IRQ);

#define SCREEN_WIDTH 240
#define SCREEN_HEIGHT 320

int x, y, z;

#define DRAW_BUF_SIZE (SCREEN_WIDTH * SCREEN_HEIGHT / 10 * (LV_COLOR_DEPTH / 8))
uint32_t draw_buf[DRAW_BUF_SIZE / 4];

// GUI OBJECTS
static lv_obj_t *labelStatus;
static lv_obj_t *labelNote;

// Touchscreen driver
void touchscreen_read(lv_indev_t * indev, lv_indev_data_t * data) {
  if(touchscreen.tirqTouched() && touchscreen.touched()) {
    TS_Point p = touchscreen.getPoint();
    x = map(p.x, 200, 3700, 1, SCREEN_WIDTH);
    y = map(p.y, 240, 3800, 1, SCREEN_HEIGHT);
    z = p.z;

    data->state = LV_INDEV_STATE_PRESSED;
    data->point.x = x;
    data->point.y = y;
  } else {
    data->state = LV_INDEV_STATE_RELEASED;
  }
}

static void btn_time_handler(lv_event_t *e) {
  Serial.println("Time button pressed!");
  // Tampilkan pesan test di layar
  lv_label_set_text(labelNote, "Button ditekan!");

  // Timer untuk mengembalikan tampilan note setelah 1 detik
  lv_timer_t * timer = lv_timer_create([](lv_timer_t * timer){
    lv_label_set_text(labelNote, "Note: -");
    lv_timer_del(timer);
  }, 1000, NULL);
}


//========================================================
//                GUI CREATOR
//========================================================
void lv_create_main_gui(void) {

  // Judul Baru
  lv_obj_t *title = lv_label_create(lv_screen_active());
  lv_label_set_long_mode(title, LV_LABEL_LONG_WRAP);
  lv_label_set_text(title, 
    "Desain Proyek Kelompok 15\nPendeteksi Kualitas Makanan Berbasis Sensor Gas");
  lv_obj_set_width(title, 220);
  lv_obj_set_style_text_align(title, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_align(title, LV_ALIGN_CENTER, 0, -70);

  // LABEL STATUS DETEKSI
  labelStatus = lv_label_create(lv_screen_active());
  lv_label_set_long_mode(labelStatus, LV_LABEL_LONG_WRAP);
  lv_label_set_text(labelStatus, "Status: -");
  lv_obj_set_width(labelStatus, 200);
  lv_obj_set_style_text_align(labelStatus, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_align(labelStatus, LV_ALIGN_CENTER, 0, -10);

  // NOTE (BASI / TIDAK)
  labelNote = lv_label_create(lv_screen_active());
  lv_label_set_long_mode(labelNote, LV_LABEL_LONG_WRAP);
  lv_label_set_text(labelNote, "Note: -");
  lv_obj_set_width(labelNote, 200);
  lv_obj_set_style_text_align(labelNote, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_align(labelNote, LV_ALIGN_CENTER, 0, 10);

  // Tombol TIME
  lv_obj_t *btnTime = lv_button_create(lv_screen_active());
  lv_obj_add_event_cb(btnTime, btn_time_handler, LV_EVENT_CLICKED, NULL);
  lv_obj_align(btnTime, LV_ALIGN_CENTER, 0, 80);
  lv_obj_remove_flag(btnTime, LV_OBJ_FLAG_PRESS_LOCK);

  lv_obj_t *btnLabel = lv_label_create(btnTime);
  lv_label_set_text(btnLabel, "MULAI DETEKSI");
  lv_obj_center(btnLabel);
}

//========================================================
//                TASK WAKTU
//========================================================
void updateTimeTask(void *pvParameters) {
  while (1) {
    struct tm timeinfo;
    if (getLocalTime(&timeinfo)) {

      char hourMinuteString[6];
      strftime(hourMinuteString, sizeof(hourMinuteString), "%H:%M", &timeinfo);
      currentHourMinute = String(hourMinuteString);
    }
    delay(5000);
  }
}

//========================================================
//                BLYNK HANDLER
//========================================================

void blynkTask(void *parameters) {
  while (1) {
    if (WiFi.status() == WL_CONNECTED) {
      Blynk.run();
    } else {
      WiFi.begin(ssid, pass);
    }

    Blynk.syncVirtual(V0);
    Blynk.syncVirtual(V1);
    Blynk.syncVirtual(V2);

    vTaskDelay(3000 / portTICK_PERIOD_MS);
  }
}

BLYNK_WRITE(V0) { suhu = param.asDouble(); }
BLYNK_WRITE(V1) { kelembapan = param.asDouble(); }
BLYNK_WRITE(V2) { oxygen = param.asDouble(); }

//========================================================
//                SENSOR EVALUATION
//========================================================
void updateStatus() {
  String status = "";
  String note = "";

  // Contoh logika sensor
  if (oxygen > 30 || kelembapan > 80 || suhu > 28) {
    status = "Terdeteksi Gas Tinggi!";
    note = "Makanan BASI!";
  } else {
    status = "Normal";
    note = "Makanan Aman";
  }

  lv_label_set_text(labelStatus, ("Status: " + status).c_str());
  lv_label_set_text(labelNote, ("Note: " + note).c_str());
}

//========================================================
//                      SETUP
//========================================================
void setup() {
  Serial.begin(115200);
  Blynk.config(BLYNK_AUTH_TOKEN);
  WiFi.begin(ssid, pass);
  configTime(7 * 3600, 0, ntpServer);

  lv_init();

  touchscreenSPI.begin(XPT2046_CLK, XPT2046_MISO, XPT2046_MOSI, XPT2046_CS);
  touchscreen.begin(touchscreenSPI);
  touchscreen.setRotation(2);

  lv_display_t *disp = lv_tft_espi_create(SCREEN_WIDTH, SCREEN_HEIGHT, draw_buf, sizeof(draw_buf));
  lv_display_set_rotation(disp, LV_DISPLAY_ROTATION_270);

  lv_indev_t *indev = lv_indev_create();
  lv_indev_set_type(indev, LV_INDEV_TYPE_POINTER);
  lv_indev_set_read_cb(indev, touchscreen_read);

  lv_create_main_gui();

  xTaskCreatePinnedToCore(updateTimeTask, "UpdateTime", 2048, NULL, 1, NULL, 1);
  xTaskCreatePinnedToCore(blynkTask, "RunBlynk", 4096, NULL, 1, NULL, 1);
}

//========================================================
//                       LOOP
//========================================================
void loop() {
  lv_task_handler();
  lv_tick_inc(5);

  updateStatus();   // Update status deteksi makanan

  delay(500);
}

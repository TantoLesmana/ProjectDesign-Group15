int mq2Pin = 34;
int sensorValue = 0;
const int MAX_ESP32_ADC = 4095;
const int MAX_RASPBERRY_MCP = 65472; // Dari kode Python

void setup() {
  Serial.begin(115200);
  delay(1000);
}

void loop() {
  sensorValue = analogRead(mq2Pin);
  
  // Konversi ke format Raspberry Pi untuk kompatibilitas model
  float raspberryCompatible = (float)sensorValue / MAX_ESP32_ADC * MAX_RASPBERRY_MCP;
  float normalizedForModel = raspberryCompatible / MAX_RASPBERRY_MCP;
  
  Serial.print("ESP32 Raw: ");
  Serial.print(sensorValue);
  Serial.print(" | Raspberry Compatible: ");
  Serial.print(raspberryCompatible);
  Serial.print(" | Normalized: ");
  Serial.println(normalizedForModel, 4);
  
  delay(1000);
}
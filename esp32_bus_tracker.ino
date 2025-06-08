
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// WiFi/MQTT Configuration
const char* ssid          = "CYBER3";
const char* password      = "Gojo@#9970";
const char* mqtt_server   = "2b2fa545-09b1-48fc-8672-4b38200019c8-00-39zwajtl8y01.pike.replit.dev";
const int   mqtt_port     = 3000;  // Use external port 3000, not 1883
const char* mqtt_username = "bus_device";
const char* mqtt_password = "secure_mqtt_password_123";
const char* bus_number    = "MH-12-CH-7798";
const char* mqtt_topic    = "buses/B001/telemetry";

// OLED and GPS config
#define OLED_SDA 21
#define OLED_SCL 22
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1

#define GPS_RX_PIN 16
#define GPS_TX_PIN 17

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
WiFiClient espClient;
PubSubClient client(espClient);

// GPS data struct
struct GPSData {
  float latitude = 0.0;
  float longitude = 0.0;
  float speed = 0.0;
  float heading = 0.0;
  bool fix = false;
} gpsData;

int satelliteCount = 0;
unsigned long lastMQTTSend = 0;
const unsigned long SEND_INTERVAL = 5000;

void setup() {
  Serial.begin(115200);

  // OLED
  Wire.begin(OLED_SDA, OLED_SCL);
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(WHITE);
  display.setCursor(0, 0);
  display.println("Starting...");
  display.display();

  // GPS
  Serial2.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);

  // WiFi
  WiFi.begin(ssid, password);
  display.setCursor(0, 10);
  display.println("Connecting WiFi...");
  display.display();
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("WiFi Connected");
  display.println(WiFi.localIP());
  display.display();

  delay(1000);

  // MQTT
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(onMqttMessage);
}

void loop() {
  if (!client.connected()) reconnectMQTT();
  client.loop();

  readGPS();

  if (millis() - lastMQTTSend >= SEND_INTERVAL) {
    sendTelemetry();
    lastMQTTSend = millis();
  }

  updateOLED();
  delay(500); // Reduce flickering
}

void readGPS() {
  while (Serial2.available()) {
    String gpsString = Serial2.readStringUntil('\n');

    if (gpsString.startsWith("$GPRMC")) {
      parseGPRMC(gpsString);
    } else if (gpsString.startsWith("$GPGGA")) {
      parseGPGGA(gpsString);
    }
  }
}

void parseGPRMC(String nmea) {
  int idx[12], cnt = 0;
  for (int i = 0; i < nmea.length() && cnt < 12; i++) if (nmea[i] == ',') idx[cnt++] = i;
  if (cnt < 9) return;

  String status = nmea.substring(idx[1] + 1, idx[2]);
  if (status != "A") {
    gpsData.fix = false;
    return;
  }
  gpsData.fix = true;

  String lat = nmea.substring(idx[2] + 1, idx[3]);
  String latD = nmea.substring(idx[3] + 1, idx[4]);
  if (lat.length()) {
    float val = lat.toFloat();
    int deg = int(val / 100);
    gpsData.latitude = deg + (val - deg * 100) / 60.0;
    if (latD == "S") gpsData.latitude *= -1;
  }

  String lon = nmea.substring(idx[4] + 1, idx[5]);
  String lonD = nmea.substring(idx[5] + 1, idx[6]);
  if (lon.length()) {
    float val = lon.toFloat();
    int deg = int(val / 100);
    gpsData.longitude = deg + (val - deg * 100) / 60.0;
    if (lonD == "W") gpsData.longitude *= -1;
  }

  String sp = nmea.substring(idx[6] + 1, idx[7]);
  if (sp.length()) gpsData.speed = sp.toFloat() * 1.852;
}

void parseGPGGA(String nmea) {
  int idx[15], cnt = 0;
  for (int i = 0; i < nmea.length() && cnt < 15; i++) if (nmea[i] == ',') idx[cnt++] = i;
  if (cnt < 8) return;

  String sats = nmea.substring(idx[6] + 1, idx[7]);
  if (sats.length()) satelliteCount = sats.toInt();
}

void sendTelemetry() {
  StaticJsonDocument<200> doc;
  doc["latitude"] = gpsData.latitude;
  doc["longitude"] = gpsData.longitude;
  doc["speed"] = gpsData.speed;
  doc["heading"] = gpsData.heading;
  doc["timestamp"] = millis();

  String payload;
  serializeJson(doc, payload);
  client.publish(mqtt_topic, payload.c_str());
}

void reconnectMQTT() {
  while (!client.connected()) {
    Serial.print("Connecting MQTT...");
    String clientId = "ESP32-" + String(bus_number);
    if (client.connect(clientId.c_str(), mqtt_username, mqtt_password)) {
      Serial.println("MQTT Connected");
    } else {
      Serial.print("MQTT Failed, rc=");
      Serial.println(client.state());
      delay(2000);
    }
  }
}

void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message [");
  Serial.print(topic);
  Serial.print("]: ");
  for (unsigned int i = 0; i < length; i++) Serial.print((char)payload[i]);
  Serial.println();
}

void updateOLED() {
  display.clearDisplay();
  display.setCursor(0, 0);
  display.setTextSize(1);

  display.print("WiFi: ");
  display.println(WiFi.SSID());

  display.print("Lat: ");
  display.println(gpsData.fix ? String(gpsData.latitude, 5) : "N/A");

  display.print("Lon: ");
  display.println(gpsData.fix ? String(gpsData.longitude, 5) : "N/A");

  display.print("Sats: ");
  display.println(satelliteCount);

  display.print("MQTT: ");
  display.println(client.connected() ? "Connected" : "Disconnected");

  display.display();
}

/*
 * Gatekeeper — ESP32-CAM gate node
 * --------------------------------
 * Flow:
 *   1. A motion sensor (PIR / ultrasonic) signals a vehicle at the gate.
 *   2. The ESP32-CAM captures a JPEG and POSTs it to the backend /api/gate/check/.
 *   3. The backend runs YOLO + OCR, matches the plate against the registry, and
 *      replies { "authorized": true|false, ... }.
 *   4. If authorized, drive the relay to open the gate; otherwise blink + hold.
 *   5. Between events, poll /api/gate/command/ so a dashboard operator can open the
 *      gate manually (and to act as a heartbeat so the device shows "online").
 *
 * Board: AI-Thinker ESP32-CAM. Select "AI Thinker ESP32-CAM" in the Arduino IDE.
 * Libraries: bundled with the ESP32 Arduino core (esp_camera, WiFi, HTTPClient).
 *
 * Copy config.h.example -> config.h and fill in your values before flashing.
 */

#include "config.h"

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include "esp_camera.h"

// The gate is on a different network from the server, so the device reaches the
// backend over the public HTTPS tunnel (e.g. https://api.yourdomain.com). We skip
// certificate validation (setInsecure) for prototype simplicity — for production,
// pin Cloudflare's root CA instead. If you instead run the ESP32 on the SAME LAN as
// the server, set SERVER_BASE_URL to http://<vm-lan-ip>:8000 and swap WiFiClientSecure
// for a plain WiFiClient.

// ---- AI-Thinker ESP32-CAM pin map ----
#define PWDN_GPIO_NUM 32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 0
#define SIOD_GPIO_NUM 26
#define SIOC_GPIO_NUM 27
#define Y9_GPIO_NUM 35
#define Y8_GPIO_NUM 34
#define Y7_GPIO_NUM 39
#define Y6_GPIO_NUM 36
#define Y5_GPIO_NUM 21
#define Y4_GPIO_NUM 19
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM 23
#define PCLK_GPIO_NUM 22

static unsigned long lastMotionAt = 0;
static unsigned long lastPollAt = 0;

void openGate() {
  Serial.println("[gate] OPEN");
  digitalWrite(GATE_RELAY_PIN, HIGH);
  digitalWrite(STATUS_LED_PIN, HIGH);
  delay(GATE_OPEN_MS);
  digitalWrite(GATE_RELAY_PIN, LOW);
  digitalWrite(STATUS_LED_PIN, LOW);
  Serial.println("[gate] CLOSED");
}

void denyBlink() {
  for (int i = 0; i < 4; i++) {
    digitalWrite(STATUS_LED_PIN, HIGH);
    delay(120);
    digitalWrite(STATUS_LED_PIN, LOW);
    delay(120);
  }
}

bool initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // Higher resolution if PSRAM is present (it is on the AI-Thinker board).
  if (psramFound()) {
    config.frame_size = FRAMESIZE_SVGA;  // 800x600 — good balance for plate OCR
    config.jpeg_quality = 12;
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 14;
    config.fb_count = 1;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[cam] init failed: 0x%x\n", err);
    return false;
  }
  return true;
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[wifi] connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print(".");
  }
  Serial.printf("\n[wifi] connected: %s\n", WiFi.localIP().toString().c_str());
}

// POST the current frame to /api/gate/check/ as multipart/form-data and act on the result.
void captureAndCheck() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("[cam] capture failed");
    return;
  }

  String url = String(SERVER_BASE_URL) + "/api/gate/check/";
  String boundary = "----gatekeeper" + String(millis());

  String head =
      "--" + boundary + "\r\n" +
      "Content-Disposition: form-data; name=\"direction\"\r\n\r\n" + String(GATE_DIRECTION) + "\r\n" +
      "--" + boundary + "\r\n" +
      "Content-Disposition: form-data; name=\"image\"; filename=\"capture.jpg\"\r\n" +
      "Content-Type: image/jpeg\r\n\r\n";
  String tail = "\r\n--" + boundary + "--\r\n";

  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.begin(client, url);
  http.setTimeout(20000);
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
  http.addHeader("X-Device-Key", DEVICE_API_KEY);

  size_t totalLen = head.length() + fb->len + tail.length();
  uint8_t *body = (uint8_t *)malloc(totalLen);
  if (!body) {
    Serial.println("[http] OOM building body");
    esp_camera_fb_return(fb);
    http.end();
    return;
  }
  memcpy(body, head.c_str(), head.length());
  memcpy(body + head.length(), fb->buf, fb->len);
  memcpy(body + head.length() + fb->len, tail.c_str(), tail.length());
  esp_camera_fb_return(fb);

  int code = http.POST(body, totalLen);
  free(body);

  if (code == 200) {
    String resp = http.getString();
    Serial.printf("[http] 200: %s\n", resp.c_str());
    if (resp.indexOf("\"authorized\":true") >= 0 || resp.indexOf("\"authorized\": true") >= 0) {
      openGate();
    } else {
      denyBlink();
    }
  } else {
    Serial.printf("[http] error %d\n", code);
    denyBlink();
  }
  http.end();
}

// Poll for a manual "open" command from the dashboard; also serves as a heartbeat.
void pollCommand() {
  String url = String(SERVER_BASE_URL) + "/api/gate/command/";
  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.begin(client, url);
  http.setTimeout(8000);
  http.addHeader("X-Device-Key", DEVICE_API_KEY);
  int code = http.GET();
  if (code == 200) {
    String resp = http.getString();
    if (resp.indexOf("\"open\"") >= 0) {
      Serial.println("[cmd] manual open");
      openGate();
    }
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  pinMode(PIR_PIN, INPUT);
  pinMode(GATE_RELAY_PIN, OUTPUT);
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(GATE_RELAY_PIN, LOW);
  digitalWrite(STATUS_LED_PIN, LOW);

  if (!initCamera()) {
    Serial.println("[cam] halting — fix wiring/board selection and reflash");
  }
  connectWiFi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  unsigned long now = millis();

  if (digitalRead(PIR_PIN) == HIGH && (now - lastMotionAt) > MOTION_COOLDOWN_MS) {
    lastMotionAt = now;
    Serial.println("[pir] motion — capturing");
    captureAndCheck();
  }

  if ((now - lastPollAt) > COMMAND_POLL_MS) {
    lastPollAt = now;
    pollCommand();
  }

  delay(50);
}

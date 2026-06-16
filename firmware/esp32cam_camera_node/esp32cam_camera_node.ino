/*
 * Gatekeeper — ESP32-CAM CAMERA node (split architecture)
 * --------------------------------------------------------
 * Role: this sketch turns the AI-Thinker ESP32-CAM into a "camera slave" that
 * does nothing on its own. It waits on a UART link for a CAPTURE command from
 * the ESP32 control node, takes a picture, uploads it over HTTPS to the
 * Django backend at /api/gate/check/, parses the {"authorized": ...} JSON
 * response, and reports the outcome back over the same UART so the control
 * node can drive the servo + LEDs + buzzer.
 *
 * It also polls /api/gate/command/ in the background and forwards a manual
 * "open" command from the dashboard to the control node as an "OPEN" line.
 *
 * Protocol on the inter-board UART (115200 baud, 8N1):
 *
 *     ESP32 (control)  -->  ESP32-CAM
 *         CAPTURE\n        : take a frame and ask the backend
 *
 *     ESP32-CAM  -->  ESP32 (control)
 *         READY\n          : sent once at boot, after WiFi is up
 *         AUTH:1\n         : backend authorised this plate
 *         AUTH:0\n         : backend denied this plate (or no plate)
 *         ERR\n            : capture or HTTP failed
 *         OPEN\n           : asynchronous manual-open from the dashboard
 *
 * Wiring (CAM <-> ESP32 dev kit):
 *
 *     ESP32-CAM GPIO14 (TX)  -->  ESP32 RX2 (GPIO16)
 *     ESP32-CAM GPIO15 (RX)  <--  ESP32 TX2 (GPIO17)
 *     ESP32-CAM GND          ---  ESP32 GND   (common ground!)
 *     ESP32-CAM 5V           ---  shared 5V supply
 *
 * Board: AI-Thinker ESP32-CAM. Select "AI Thinker ESP32-CAM" in Arduino IDE.
 * Copy config.h.example -> config.h before flashing.
 */

#include "config.h"

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include "esp_camera.h"

// ---- AI-Thinker ESP32-CAM camera pin map (unchanged) ----
#define PWDN_GPIO_NUM   32
#define RESET_GPIO_NUM  -1
#define XCLK_GPIO_NUM   0
#define SIOD_GPIO_NUM   26
#define SIOC_GPIO_NUM   27
#define Y9_GPIO_NUM     35
#define Y8_GPIO_NUM     34
#define Y7_GPIO_NUM     39
#define Y6_GPIO_NUM     36
#define Y5_GPIO_NUM     21
#define Y4_GPIO_NUM     19
#define Y3_GPIO_NUM     18
#define Y2_GPIO_NUM     5
#define VSYNC_GPIO_NUM  25
#define HREF_GPIO_NUM   23
#define PCLK_GPIO_NUM   22

// ---- Inter-board UART pins (on the ESP32-CAM side) ----
#define LINK_RX_PIN 15   // ESP32-CAM RX  <-- ESP32 TX2 (GPIO17)
#define LINK_TX_PIN 14   // ESP32-CAM TX  --> ESP32 RX2 (GPIO16)

// ---- Camera orientation ----
// The OV2640 sensor can flip the image in hardware. The AI-Thinker ESP32-CAM's
// default output comes out horizontally mirrored, so we enable HMIRROR alone to
// cancel that mirror. If you ever physically remount the camera, try these:
//   CAM_VFLIP=0 + CAM_HMIRROR=1  -> un-mirror only (the typical correct combo)
//   CAM_VFLIP=1 + CAM_HMIRROR=0  -> flip top-bottom only
//   CAM_VFLIP=1 + CAM_HMIRROR=1  -> rotate the whole image 180°
//   CAM_VFLIP=0 + CAM_HMIRROR=0  -> raw sensor output (mirrored)
#define CAM_VFLIP    0
#define CAM_HMIRROR  1

HardwareSerial Link(1);  // UART1, remapped onto LINK_RX_PIN / LINK_TX_PIN

static unsigned long lastPollAt = 0;

// ---------------------------------------------------------------------------
// Camera + WiFi setup
// ---------------------------------------------------------------------------

bool initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {
    config.frame_size  = FRAMESIZE_SVGA;   // 800x600 — good balance for plate OCR
    config.jpeg_quality = 12;
    config.fb_count     = 2;
  } else {
    config.frame_size  = FRAMESIZE_VGA;
    config.jpeg_quality = 14;
    config.fb_count     = 1;
  }

  // Always return the freshest frame and keep buffers in PSRAM.
  config.grab_mode    = CAMERA_GRAB_LATEST;
  config.fb_location  = CAMERA_FB_IN_PSRAM;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[cam] init failed: 0x%x\n", err);
    return false;
  }

  // Apply the configured flip/mirror so captured frames are right-way-up regardless
  // of how the board is physically mounted at the gate.
  sensor_t *s = esp_camera_sensor_get();
  if (s) {
    s->set_vflip(s,   CAM_VFLIP);
    s->set_hmirror(s, CAM_HMIRROR);
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

// ---------------------------------------------------------------------------
// Capture + check pipeline
// ---------------------------------------------------------------------------

// Returns: 1 = authorised, 0 = denied/no plate, -1 = transport/encoding error.
int captureAndCheck() {
  // Drain two stale frames (~80 ms of older buffer contents) so the picture we
  // upload is genuinely from "now" rather than a frame the sensor produced before
  // the CAPTURE command arrived. The short delay gives the OV2640 enough time to
  // start the next exposure between drains.
  for (int i = 0; i < 2; i++) {
    camera_fb_t *stale = esp_camera_fb_get();
    if (stale) esp_camera_fb_return(stale);
    delay(40);
  }

  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("[cam] capture failed");
    return -1;
  }

  String url      = String(SERVER_BASE_URL) + "/api/gate/check/";
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
    return -1;
  }
  memcpy(body,                                 head.c_str(), head.length());
  memcpy(body + head.length(),                 fb->buf,      fb->len);
  memcpy(body + head.length() + fb->len,       tail.c_str(), tail.length());
  esp_camera_fb_return(fb);

  int code = http.POST(body, totalLen);
  free(body);

  int result = -1;
  if (code == 200) {
    String resp = http.getString();
    Serial.printf("[http] 200: %s\n", resp.c_str());
    bool authorized = (resp.indexOf("\"authorized\":true") >= 0 ||
                       resp.indexOf("\"authorized\": true") >= 0);
    result = authorized ? 1 : 0;
  } else {
    Serial.printf("[http] error %d\n", code);
  }
  http.end();
  return result;
}

// Polls the backend for a manual-open command and, if present, pushes "OPEN"
// to the control node so it can actuate the boom + green LED + buzzer.
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
    Serial.println("[poll] 200 (heartbeat ok)");
    String resp = http.getString();
    if (resp.indexOf("\"open\"") >= 0) {
      Serial.println("[cmd] manual OPEN from dashboard -> forwarding");
      Link.println("OPEN");
    }
  } else if (code > 0) {
    // HTTP got a response but it wasn't 200. Most common: 401 = wrong device key,
    // 404 = wrong base URL / wrong path. Surface the body so the cause is obvious.
    String body = http.getString();
    Serial.printf("[poll] HTTP %d: %s\n", code, body.c_str());
  } else {
    // Negative codes are transport-level failures (connection refused, DNS, TLS…).
    Serial.printf("[poll] transport error %d\n", code);
  }
  http.end();
}

// ---------------------------------------------------------------------------
// Arduino entry points
// ---------------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  Link.begin(115200, SERIAL_8N1, LINK_RX_PIN, LINK_TX_PIN);

  if (!initCamera()) {
    Serial.println("[cam] halting — fix wiring/board selection and reflash");
  }
  connectWiFi();

  Link.println("READY");
  Serial.println("[cam] READY");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  // 1. Handle any CAPTURE command from the control node.
  if (Link.available()) {
    String cmd = Link.readStringUntil('\n');
    cmd.trim();
    if (cmd == "CAPTURE") {
      Serial.println("[link] CAPTURE received");
      int r = captureAndCheck();
      if      (r == 1)  Link.println("AUTH:1");
      else if (r == 0)  Link.println("AUTH:0");
      else              Link.println("ERR");
    } else if (cmd.length() > 0) {
      Serial.printf("[link] unknown command: '%s'\n", cmd.c_str());
    }
  }

  // 2. Background heartbeat + manual-open poll.
  unsigned long now = millis();
  if ((now - lastPollAt) > COMMAND_POLL_MS) {
    lastPollAt = now;
    pollCommand();
  }

  delay(20);
}

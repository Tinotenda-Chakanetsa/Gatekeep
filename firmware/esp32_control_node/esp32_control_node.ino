/*
 * Gatekeeper — ESP32 CONTROL node (split architecture)
 * ----------------------------------------------------
 * Role: this sketch runs on the ESP32 dev board sitting next to the gate
 * peripherals. It reads the PIR sensor, asks the ESP32-CAM to capture + check
 * a plate, and on the response drives the SG90 servo (the boom), the red /
 * green status LEDs and the buzzer. It does NOT talk to the backend; only the
 * ESP32-CAM has WiFi/HTTPS responsibility.
 *
 * Inter-board UART (Serial2, 115200 baud):
 *
 *     ESP32 RX2 (GPIO16)  <--  ESP32-CAM GPIO14 (TX)
 *     ESP32 TX2 (GPIO17)  -->  ESP32-CAM GPIO15 (RX)
 *     GND                ---  ESP32-CAM GND  (common ground!)
 *
 * Peripheral wiring (see Hardware Guide for full diagram):
 *
 *     PIR OUT      -->  D13 (GPIO13)
 *     Servo SG90   -->  D25 (GPIO25)   yellow/orange = signal
 *                       servo red  = 5V from external supply
 *                       servo brown = GND, common
 *     Green LED    -->  D26 (GPIO26)   anode through 220 Ω to GPIO; cathode to GND
 *     Red LED      -->  D27 (GPIO27)   anode through 220 Ω to GPIO; cathode to GND
 *     Buzzer (+)   -->  D33 (GPIO33)   buzzer (-) to GND
 *
 * Required library (Arduino IDE → Tools → Manage Libraries…):
 *     ESP32Servo by Kevin Harrington / John K. Bennett
 *
 * Board: ESP32 Dev Module / ESP32-WROOM-32. Select your specific dev board.
 * Copy config.h.example -> config.h before flashing.
 */

#include "config.h"
#include <ESP32Servo.h>

// ---- Peripheral pins ----
#define PIR_PIN        13   // HC-SR501 OUT
#define SERVO_PIN      25   // SG90 signal
#define LED_GREEN_PIN  26   // green LED + 220 Ω resistor
#define LED_RED_PIN    27   // red   LED + 220 Ω resistor
#define BUZZER_PIN     33   // active buzzer

// ---- Inter-board UART pins ----
#define LINK_RX_PIN    16   // ESP32 RX2 (default)
#define LINK_TX_PIN    17   // ESP32 TX2 (default)

// ---- Servo positions (degrees) ----
#define BOOM_CLOSED_DEG  0
#define BOOM_OPEN_DEG    90

Servo boom;
static unsigned long lastMotionAt = 0;

// ---------------------------------------------------------------------------
// Peripheral helpers
// ---------------------------------------------------------------------------

void setBoom(bool open) {
  boom.write(open ? BOOM_OPEN_DEG : BOOM_CLOSED_DEG);
}

void beep(int ms) {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(ms);
  digitalWrite(BUZZER_PIN, LOW);
}

void grantedFeedback() {
  Serial.println("[ctrl] GRANTED — opening boom");
  digitalWrite(LED_GREEN_PIN, HIGH);
  beep(120);                       // single short happy beep
  setBoom(true);
  delay(BOOM_OPEN_MS);
  setBoom(false);
  digitalWrite(LED_GREEN_PIN, LOW);
}

void deniedFeedback() {
  Serial.println("[ctrl] DENIED — boom stays closed");
  for (int i = 0; i < 4; i++) {
    digitalWrite(LED_RED_PIN, HIGH);
    digitalWrite(BUZZER_PIN,  HIGH);
    delay(180);
    digitalWrite(LED_RED_PIN, LOW);
    digitalWrite(BUZZER_PIN,  LOW);
    delay(120);
  }
}

// ---------------------------------------------------------------------------
// UART helper: read a single \n-terminated line from the camera node
// ---------------------------------------------------------------------------

String readLineFromCam(unsigned long timeoutMs) {
  unsigned long start = millis();
  String line;
  while (millis() - start < timeoutMs) {
    while (Serial2.available()) {
      char c = (char)Serial2.read();
      if (c == '\n' || c == '\r') {
        if (line.length() > 0) return line;
      } else {
        line += c;
      }
    }
    delay(5);
  }
  return String();  // empty on timeout
}

// Map a response line to the right feedback.
void actOnResponse(const String &line) {
  Serial.printf("[ctrl] cam: %s\n", line.c_str());
  if (line == "AUTH:1" || line == "OPEN") {
    grantedFeedback();
  } else if (line == "AUTH:0") {
    deniedFeedback();
  } else if (line == "ERR") {
    Serial.println("[ctrl] capture/transport error reported by cam");
    deniedFeedback();
  } else if (line == "READY") {
    Serial.println("[ctrl] cam reported READY");
  }
}

// ---------------------------------------------------------------------------
// Arduino entry points
// ---------------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, LINK_RX_PIN, LINK_TX_PIN);

  pinMode(PIR_PIN,       INPUT);
  pinMode(LED_GREEN_PIN, OUTPUT);
  pinMode(LED_RED_PIN,   OUTPUT);
  pinMode(BUZZER_PIN,    OUTPUT);
  digitalWrite(LED_GREEN_PIN, LOW);
  digitalWrite(LED_RED_PIN,   LOW);
  digitalWrite(BUZZER_PIN,    LOW);

  // SG90: 500–2400 µs pulse range gives the full ~0–180° travel on most clones.
  boom.attach(SERVO_PIN, 500, 2400);
  setBoom(false);

  Serial.println("[ctrl] ready, listening for PIR + CAM");
}

void loop() {
  unsigned long now = millis();

  // 1. PIR-driven flow: trigger -> ask CAM to capture -> act on response.
  if (digitalRead(PIR_PIN) == HIGH && (now - lastMotionAt) > MOTION_COOLDOWN_MS) {
    lastMotionAt = now;
    Serial.println("[ctrl] motion detected -> CAPTURE");
    Serial2.println("CAPTURE");

    String resp = readLineFromCam(RESPONSE_TIMEOUT_MS);
    if (resp.length() == 0) {
      Serial.println("[ctrl] no response from cam (timeout)");
      deniedFeedback();
    } else {
      actOnResponse(resp);
    }
  }

  // 2. Asynchronous push from cam (manual OPEN from dashboard, READY at boot…).
  if (Serial2.available()) {
    String line = readLineFromCam(200);
    if (line.length() > 0) {
      actOnResponse(line);
    }
  }

  delay(50);
}

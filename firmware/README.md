# Gatekeeper firmware — ESP32-CAM gate node

This sketch turns an **AI-Thinker ESP32-CAM** into the gate node: it watches a motion
sensor, captures a plate image, asks the backend whether the plate is registered, and
opens the gate (via a relay) if so.

## Bill of materials (~$15)

| Part | Notes |
|------|-------|
| AI-Thinker ESP32-CAM | The controller + camera (OV2640) |
| USB-TTL programmer (FTDI) or ESP32-CAM-MB | Needed to flash — the board has no USB |
| PIR motion sensor (HC-SR501) | Trigger. An HC-SR04 ultrasonic also works |
| Relay module (1-channel, 5V) | Drives the gate motor / barrier safely |
| 5V 2A power supply | The camera + WiFi need stable current |

> A servo (SG90) can replace the relay for a toy barrier, but **do not power a servo from
> the board's 3V3 pin** — use an external 5V supply and common ground, or you'll get
> brownouts mid-WiFi.

## Wiring (AI-Thinker)

| Signal | GPIO | Connect to |
|--------|------|-----------|
| PIR OUT | GPIO13 | PIR data out |
| Relay IN | GPIO12 | Relay control (active HIGH = open) |
| Status LED | GPIO4 | On-board flash LED (built in) |
| 5V / GND | 5V / GND | Shared 5V supply + common ground |

GPIO12 and GPIO13 are free only when the microSD slot is unused (the default here).
GPIO0 must be **floating at boot** (it's only grounded while flashing).

## Flashing

1. Install the **ESP32 board package** in the Arduino IDE (Boards Manager → "esp32").
2. Select board **AI Thinker ESP32-CAM**.
3. Wire the programmer: connect `IO0 → GND` to enter flash mode, power-cycle, upload,
   then remove the `IO0 → GND` jumper and reset.
4. Copy `esp32cam_gate/config.h.example` → `esp32cam_gate/config.h` and fill in WiFi,
   `SERVER_BASE_URL`, and the `DEVICE_API_KEY` from the dashboard's **Devices** page.
5. Upload and open Serial Monitor at 115200 baud.

## How it talks to the backend

- `POST {SERVER_BASE_URL}/api/gate/check/` — multipart form with `image` (JPEG) +
  `direction`, authenticated by the `X-Device-Key` header. Response includes
  `{"authorized": true|false}`.
- `GET {SERVER_BASE_URL}/api/gate/command/` — polled every few seconds; returns
  `{"gate_action": "open"}` when a dashboard operator presses **Open Gate**. Doubles as
  the heartbeat that marks the device "online".

## No hardware yet?

Use the software simulator at [`tools/gate_simulator.py`](../tools/gate_simulator.py) —
it sends a real image to the same `/api/gate/check/` endpoint, so you can demo the whole
pipeline (capture → OCR → match → decision → log on the dashboard) without any board.

## Upgrade path

If you outgrow the ESP32-CAM's limited GPIO (want an LCD, exit-loop sensor, buzzer, or a
second gate), split into a **regular ESP32 control node** (sensors + relay + peripherals)
plus the **ESP32-CAM as a pure camera node**. The backend and dashboard don't change —
only this firmware does.

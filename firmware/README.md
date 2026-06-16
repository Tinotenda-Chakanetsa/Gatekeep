# Gatekeeper firmware

Two firmware layouts are provided. The **split two-board architecture** is the recommended
one for any setup with peripherals beyond a single relay; the **single-board layout** is kept
as a simpler option for minimal prototypes.

| Layout | Folder(s) | What runs where |
|--------|-----------|-----------------|
| **Split (recommended)** | `esp32_control_node/`, `esp32cam_camera_node/` | ESP32 handles PIR + servo + LEDs + buzzer; ESP32-CAM handles capture + HTTPS only |
| Single board (legacy) | `esp32cam_gate/` | One AI-Thinker ESP32-CAM does everything (PIR + relay + capture) |

The backend and dashboard are identical for both — only the firmware changes.

---

## Split two-board architecture (recommended)

Splitting the work onto two boards has three benefits: (1) the ESP32 dev board has plenty
of GPIO for the boom servo, two LEDs and a buzzer; (2) the ESP32-CAM's GPIO contention
disappears because the cam only needs WiFi + camera; (3) the actuation latency is lower
because the cam doesn't have to wait on motion polling — the ESP32 tells it exactly when.

### Bill of materials (~$20)

| Part | Quantity | Notes |
|------|----------|-------|
| ESP32 dev board (ESP32-WROOM-32, e.g. DevKit V1) | 1 | The control node. USB-C/Micro-USB powered. |
| AI-Thinker ESP32-CAM | 1 | The camera node. |
| USB-TTL programmer (FTDI) or ESP32-CAM-MB | 1 | One-time, only needed to flash the ESP32-CAM. |
| PIR motion sensor (HC-SR501) | 1 | Trigger. |
| SG90 micro servo | 1 | Simulates the toll/boom barrier. |
| Red LED + 220 Ω resistor | 1 | DENIED indicator. |
| Green LED + 220 Ω resistor | 1 | GRANTED indicator. |
| Active buzzer (3.3–5 V) | 1 | Audible grant/deny feedback. |
| 5 V 2 A power supply | 1 | Servo + buzzer + both boards share this rail. |
| Jumper wires (M-F, F-F) | ~15 | Wiring. |
| Single-channel 5 V relay module | 0–1 | **Optional** — only if you swap the SG90 for a real gate motor later. |

### Wiring

**Inter-board UART link (3 wires + shared ground):**

```
ESP32-CAM GPIO14 (TX)  ─▶  ESP32 D16  (RX2 / GPIO16)
ESP32-CAM GPIO15 (RX)  ◀─  ESP32 D17  (TX2 / GPIO17)
ESP32-CAM GND           ─  ESP32 GND
ESP32-CAM 5V            ─  shared 5 V rail
```

**ESP32 control node peripherals:**

| Peripheral | ESP32 pin label | GPIO | Notes |
|------------|-----------------|------|-------|
| PIR OUT | D13 | 13 | HC-SR501 signal |
| Servo SG90 (yellow/orange) | D25 | 25 | Servo red → 5 V rail, brown → GND |
| Green LED (+) | D26 | 26 | Anode through **220 Ω** to GPIO, cathode to GND |
| Red LED (+)   | D27 | 27 | Anode through **220 Ω** to GPIO, cathode to GND |
| Buzzer (+) | D33 | 33 | Buzzer (–) to GND |
| 5 V supply | VIN / 5V | – | From USB or external 5 V 2 A PSU |
| GND | GND | – | **Common ground with ESP32-CAM, servo, buzzer, etc.** |

**Why no relay?** The SG90 is the boom for this prototype — it actuates directly from the
ESP32 PWM pin. Keep the relay aside for the day you swap to a real mains-powered gate motor,
when it would drive the motor's contactor.

**Power tip:** the SG90 can spike to ~500 mA on stall, which crashes a USB-only setup. Use a
dedicated 5 V 2 A supply for the rail, and add a **470 µF electrolytic capacitor across
the servo's V+/GND** close to the servo for stability.

### Inter-board protocol (text over UART, 115200 baud, 8N1)

```
ESP32  ──▶  ESP32-CAM       ESP32-CAM  ──▶  ESP32
  CAPTURE\n                   READY\n      (sent once at boot)
                              AUTH:1\n     (authorised → granted feedback)
                              AUTH:0\n     (denied / no plate → denied feedback)
                              ERR\n        (capture or HTTP error → denied feedback)
                              OPEN\n       (async: dashboard pressed Open Gate)
```

### Flashing

#### Camera node — `esp32cam_camera_node/esp32cam_camera_node.ino`
1. Arduino IDE → Board: **AI Thinker ESP32-CAM**.
2. Connect USB-TTL programmer (TX→U0R, RX→U0T, 5V, GND) and **IO0 → GND** for flash mode.
3. Copy `config.h.example` → `config.h`, fill in WiFi, `SERVER_BASE_URL`, and
   `DEVICE_API_KEY` from the dashboard's Devices page.
4. Upload, remove `IO0 → GND` jumper, press RESET.
5. Serial Monitor at 115200 baud should show `[wifi] connected: ...` then `[cam] READY`.

#### Control node — `esp32_control_node/esp32_control_node.ino`
1. Install the **ESP32Servo** library: Tools → Manage Libraries → search *ESP32Servo*
   (by Kevin Harrington / John K. Bennett) → Install.
2. Arduino IDE → Board: **ESP32 Dev Module** (or whichever matches your specific board).
3. Plug in via USB (no `IO0 → GND` jumper needed; the dev board has a USB-Serial bridge).
4. Copy `config.h.example` → `config.h` (only timing parameters live here).
5. Upload. Serial Monitor at 115200 baud should show `[ctrl] ready, listening for PIR + CAM`.

### Live behaviour
- Vehicle approaches → PIR fires → ESP32 sends `CAPTURE` → ESP32-CAM grabs a fresh frame
  and POSTs it → backend OCR + match → `{"authorized": true|false}` → CAM forwards as
  `AUTH:1` / `AUTH:0` → ESP32 raises the boom (servo 0° → 90°), lights green and beeps once
  on grant; flashes red + buzzes four times on deny.
- An operator pressing **Open Gate** on the dashboard → CAM picks up the queued command on
  its next `/api/gate/command/` poll → pushes `OPEN` to the ESP32 → control node opens the
  boom and confirms with the green LED.

---

## Single-board layout (legacy, simpler)

`esp32cam_gate/` is the original sketch: a single AI-Thinker ESP32-CAM does PIR reading,
capture, HTTPS and relay actuation. It's fine for a minimal demo with no servo/LEDs/buzzer,
but the GPIO contention and double-buffering quirks of running everything on the cam are
the reason the split layout above exists. Wiring and flashing are documented at the head of
its `esp32cam_gate.ino` file.

---

## No hardware yet?

The Python simulator at [`tools/gate_simulator.py`](../tools/gate_simulator.py) sends a real
image to the same `/api/gate/check/` endpoint — so you can demo the whole pipeline
(capture → OCR → match → decision → log on the dashboard) without any board at all.

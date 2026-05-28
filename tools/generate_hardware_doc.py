#!/usr/bin/env python3
"""Generate the Gatekeeper hardware components & wiring guide as a .docx file.

Run with a Python that has python-docx installed:
    python tools/generate_hardware_doc.py
Output: Gatekeeper_Hardware_Guide.docx in the project root.
"""

from __future__ import annotations

import os

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(PROJECT_ROOT, 'Gatekeeper_Hardware_Guide.docx')

ACCENT = RGBColor(0x2E, 0x6B, 0x4F)  # matches the dashboard's green


def add_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = 'Light Grid Accent 1'
    hdr = table.rows[0].cells
    for i, text in enumerate(headers):
        hdr[i].text = ''
        run = hdr[i].paragraphs[0].add_run(text)
        run.bold = True
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = str(value)
    return table


def add_mono(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.name = 'Consolas'
    run.font.size = Pt(9)
    return p


def build():
    doc = Document()

    # Base font
    normal = doc.styles['Normal']
    normal.font.name = 'Calibri'
    normal.font.size = Pt(11)

    # ---- Title ----
    title = doc.add_heading('Gatekeeper', level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph('Hardware Components & Wiring Guide')
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.runs[0].bold = True
    sub.runs[0].font.size = Pt(14)
    tagline = doc.add_paragraph('Automated license-plate gate access control — ESP32-CAM prototype')
    tagline.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tagline.runs[0].italic = True
    tagline.runs[0].font.color.rgb = ACCENT
    doc.add_paragraph()

    # ---- 1. Overview ----
    doc.add_heading('1. System overview', level=1)
    doc.add_paragraph(
        'A vehicle arrives at the gate and is detected by a motion sensor. The ESP32-CAM '
        'captures a photo of the number plate and sends it over WiFi to the backend server. '
        'The server runs plate detection (YOLO) and text recognition (PaddleOCR), then checks '
        'the reading against the registry of authorised vehicles. If the plate belongs to an '
        'active, registered vehicle the server replies "authorised", and the ESP32-CAM drives a '
        'relay to open the gate; otherwise the gate stays closed and the event is logged. An '
        'operator can also open the gate manually from the web dashboard.'
    )
    doc.add_paragraph('Signal flow:')
    add_mono(
        doc,
        'Vehicle\n'
        '   |  (motion)\n'
        '   v\n'
        '[ PIR / ultrasonic sensor ] --trigger--> [ ESP32-CAM ]\n'
        '                                              |  capture JPEG\n'
        '                                              v  WiFi (HTTP POST, X-Device-Key)\n'
        '                                       [ Backend server ]\n'
        '                                         YOLO + PaddleOCR\n'
        '                                         match registry\n'
        '                                              |  { "authorized": true|false }\n'
        '                                              v\n'
        '[ Relay ] <--GPIO-- [ ESP32-CAM ] --> opens gate motor / barrier if authorised',
    )

    # ---- 2. Bill of materials ----
    doc.add_heading('2. Bill of materials (what to buy)', level=1)
    doc.add_paragraph(
        'Minimum working build is about USD 15. Optional items add status feedback and night '
        'capture. Prices are rough street prices and vary by region/supplier.'
    )
    add_table(
        doc,
        ['Component', 'Purpose', 'Qty', 'Approx. cost', 'Notes'],
        [
            ['ESP32-CAM (AI-Thinker, OV2640)', 'Main controller: camera + WiFi + logic', '1', '$7–10',
             'The core board. Comes with a 2 MP OV2640 camera.'],
            ['USB-TTL / FTDI programmer (or ESP32-CAM-MB board)', 'Flash firmware — the board has no USB port',
             '1', '$2–4', 'One-time. The "ESP32-CAM-MB" dongle is the easiest option.'],
            ['PIR motion sensor (HC-SR501)', 'Detects a vehicle at the gate (the trigger)', '1', '$1–3',
             'An HC-SR04 ultrasonic distance sensor is a good alternative.'],
            ['Relay module (1-channel, 5V, opto-isolated)', 'Safely switches the gate motor / barrier', '1', '$1–3',
             'Drives the gate via its dry COM/NO contacts.'],
            ['Servo SG90 (optional)', 'A toy barrier arm instead of a relay', '1', '$2–3',
             'For demos. Must be powered from external 5V, not the board.'],
            ['5V 2A power supply', 'Stable power — camera + WiFi draw current spikes', '1', '$4–6',
             'Do not underpower; weak USB causes brownouts/reboots.'],
            ['Jumper wires (male-female, female-female)', 'Wiring between modules', '~10', '$2', 'A small assortment.'],
            ['Breadboard (optional)', 'Tidy prototyping', '1', '$2–4', 'Optional but convenient.'],
            ['Green + Red LEDs + 220 Ω resistors (optional)', 'Grant / deny status lights', '2', '$1', 'Nice feedback.'],
            ['Active buzzer (optional)', 'Audible grant/deny beep', '1', '$1', 'Optional.'],
            ['White / IR LED illuminator (optional)', 'Night-time plate capture', '1', '$2–5',
             'The OV2640 is weak in low light.'],
            ['Gate hardware (barrier / motor / existing controller)', 'The physical gate being controlled', '1',
             'varies', 'The relay switches this; mains motors need an electrician.'],
        ],
    )

    # ---- 3. Pin connections ----
    doc.add_heading('3. Pin connections (AI-Thinker ESP32-CAM)', level=1)
    doc.add_paragraph(
        'These GPIOs are free on the AI-Thinker board when the microSD slot is unused (the '
        'default for this project). Connect every module ground to a common ground.'
    )
    add_table(
        doc,
        ['Peripheral pin', 'ESP32-CAM pin', 'Direction', 'Notes'],
        [
            ['PIR OUT (signal)', 'GPIO13', 'Input', 'Goes HIGH when motion is detected.'],
            ['Relay IN (control)', 'GPIO12', 'Output', 'Active HIGH = open. See strapping-pin caution below.'],
            ['Status LED', 'GPIO4', 'Output', 'On-board flash LED; doubles as a status blinker.'],
            ['External green LED (optional)', 'GPIO2', 'Output', 'Through a 220 Ω resistor to GND.'],
            ['PIR VCC', '5V', 'Power', 'HC-SR501 runs on 5V.'],
            ['Relay VCC', '5V', 'Power', 'Most 1-channel modules are 5V.'],
            ['All module GND', 'GND', 'Power', 'Common ground is essential.'],
        ],
    )
    caution = doc.add_paragraph()
    caution.add_run('Strapping-pin caution: ').bold = True
    caution.add_run(
        'GPIO12 is a boot strapping pin (it selects the flash voltage). If it is held HIGH while '
        'the board powers on, the ESP32 may fail to boot. The firmware drives it LOW at startup, '
        'and most active-HIGH relay modules idle LOW — so this is usually fine. If you see boot '
        'failures, move the relay to GPIO14 (and update the pin in config.h).'
    )

    # ---- 4. Programming connections ----
    doc.add_heading('4. Flashing connections (one-time, to upload firmware)', level=1)
    doc.add_paragraph(
        'The ESP32-CAM has no USB port, so it is flashed through a USB-TTL/FTDI adapter. Skip '
        'this table entirely if you use an "ESP32-CAM-MB" programmer dongle (just plug it in).'
    )
    add_table(
        doc,
        ['USB-TTL / FTDI', 'ESP32-CAM', 'Notes'],
        [
            ['5V', '5V', 'Use 5V for reliable flashing.'],
            ['GND', 'GND', 'Common ground.'],
            ['TX', 'U0R (GPIO3 / RX)', 'Adapter transmit → board receive.'],
            ['RX', 'U0T (GPIO1 / TX)', 'Adapter receive → board transmit.'],
            ['— (jumper wire)', 'IO0  ↔  GND', 'Connect IO0 to GND to enter flash mode; remove afterward.'],
        ],
    )
    doc.add_paragraph('Upload procedure:')
    for step in [
        'In the Arduino IDE select board: "AI Thinker ESP32-CAM".',
        'Connect IO0 to GND, then press the on-board RESET (or power-cycle) to enter flash mode.',
        'Click Upload. After "Done uploading", remove the IO0–GND jumper and press RESET.',
        'Open Serial Monitor at 115200 baud to watch the device connect to WiFi.',
    ]:
        doc.add_paragraph(step, style='List Number')

    # ---- 5. Assembly steps ----
    doc.add_heading('5. Assembly steps', level=1)
    for step in [
        'Flash the firmware (Section 4). Before flashing, copy firmware/esp32cam_gate/config.h.example '
        'to config.h and fill in your WiFi name/password, the server URL, and the device API key.',
        'Power everything down before wiring.',
        'Wire the PIR sensor: OUT → GPIO13, VCC → 5V, GND → GND.',
        'Wire the relay: IN → GPIO12, VCC → 5V, GND → GND. Connect the gate motor circuit through the '
        'relay COM and NO terminals.',
        '(Optional) Add status LEDs / buzzer on the free GPIOs.',
        'Connect a stable 5V 2A supply and make sure every module shares a common ground.',
        'Power on and open the Serial Monitor (115200). Wave a hand past the PIR to trigger a capture, '
        'then confirm the event appears on the dashboard (Access Logs).',
    ]:
        doc.add_paragraph(step, style='List Number')

    # ---- 6. Power & safety ----
    doc.add_heading('6. Power & safety notes', level=1)
    for note in [
        'Use an external 5V 2A supply. The camera plus WiFi cause current spikes; weak USB power '
        'leads to brownouts and random reboots.',
        'Never power a servo from the board\'s 3V3 pin. Use a separate 5V source and tie grounds together.',
        'For a mains-powered gate motor, switch it through the relay\'s isolated (dry) COM/NO contacts. '
        'Keep mains wiring separated and have a qualified electrician handle high-voltage gate motors.',
        'GPIO12 is a boot strapping pin — keep it LOW at boot (the firmware does this). If the board '
        'will not boot, move the relay to GPIO14.',
        'Mount the camera roughly 1–2 m from where the plate sits, well-lit and square-on. The OV2640 '
        'is weak in low light — add a white/IR illuminator for night-time reliability.',
    ]:
        doc.add_paragraph(note, style='List Bullet')

    # ---- 7. Connecting to the software ----
    doc.add_heading('7. How the hardware connects to the software', level=1)
    doc.add_paragraph(
        'The ESP32-CAM only talks to the backend over WiFi using a device API key — it never '
        'handles user passwords. Create the device and copy its key from the dashboard.'
    )
    add_table(
        doc,
        ['Action', 'Endpoint', 'Auth', 'Purpose'],
        [
            ['Send a capture', 'POST /api/gate/check/', 'X-Device-Key header',
             'Upload the plate photo; receive { "authorized": true|false }.'],
            ['Poll for commands', 'GET /api/gate/command/', 'X-Device-Key header',
             'Receive a manual "open" command from an operator; also acts as the online heartbeat.'],
        ],
    )
    steps = doc.add_paragraph()
    steps.add_run('Getting the device API key: ').bold = True
    steps.add_run(
        'log in to the dashboard as an administrator → Devices page → "Add Device" → click "Show" '
        'to reveal the key → paste it into DEVICE_API_KEY in firmware config.h.'
    )
    doc.add_paragraph(
        'No hardware yet? Use tools/gate_simulator.py to send a real image to the same '
        '/api/gate/check/ endpoint and demo the whole pipeline without any board.'
    )

    # ---- 8. Upgrade path ----
    doc.add_heading('8. Optional upgrade path', level=1)
    doc.add_paragraph(
        'The single ESP32-CAM is the most budget-friendly choice and does the whole job for a '
        'prototype. If you later need more peripherals than its limited GPIO allows (an LCD, an '
        'exit-loop sensor, a buzzer, or a second gate), split the system into two boards:'
    )
    for item in [
        'A regular ESP32 dev board as the control node: handles the sensors, relay, LEDs, buzzer, '
        'and any display — it has plenty of free GPIO and a built-in USB port for easy flashing.',
        'The ESP32-CAM as a dedicated camera node: it only captures and uploads images on command.',
    ]:
        doc.add_paragraph(item, style='List Bullet')
    doc.add_paragraph(
        'Importantly, the backend and the web dashboard do not change for this upgrade — only the '
        'firmware does.'
    )

    doc.save(OUTPUT_PATH)
    print(f'Wrote {OUTPUT_PATH}')


if __name__ == '__main__':
    build()

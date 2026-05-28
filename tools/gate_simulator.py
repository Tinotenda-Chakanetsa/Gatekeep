#!/usr/bin/env python3
"""Gatekeeper gate simulator.

Mimics the ESP32-CAM: sends an image to the backend's /api/gate/check/ endpoint using a
device API key, prints the access decision, and (optionally) polls for manual-open
commands. Use this to demo the full pipeline without any hardware.

Examples
--------
  # One-shot: send an image and print the decision
  python tools/gate_simulator.py --image samples/car.jpg --key <DEVICE_API_KEY>

  # Watch mode: poll for dashboard "Open Gate" commands every 3s
  python tools/gate_simulator.py --key <DEVICE_API_KEY> --watch

Only the Python standard library is required.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import time
import urllib.request
import uuid


def _encode_multipart(fields: dict[str, str], file_field: str, file_path: str):
    boundary = f'----gatekeeper{uuid.uuid4().hex}'
    crlf = b'\r\n'
    body = bytearray()

    for name, value in fields.items():
        body += b'--' + boundary.encode() + crlf
        body += f'Content-Disposition: form-data; name="{name}"'.encode() + crlf + crlf
        body += str(value).encode() + crlf

    filename = os.path.basename(file_path)
    content_type = mimetypes.guess_type(filename)[0] or 'image/jpeg'
    with open(file_path, 'rb') as fh:
        file_bytes = fh.read()

    body += b'--' + boundary.encode() + crlf
    body += (
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"'.encode()
        + crlf
    )
    body += f'Content-Type: {content_type}'.encode() + crlf + crlf
    body += file_bytes + crlf
    body += b'--' + boundary.encode() + b'--' + crlf

    return bytes(body), f'multipart/form-data; boundary={boundary}'


def send_capture(base_url: str, key: str, image_path: str, direction: str) -> dict:
    body, content_type = _encode_multipart({'direction': direction}, 'image', image_path)
    req = urllib.request.Request(
        base_url.rstrip('/') + '/api/gate/check/',
        data=body,
        method='POST',
        headers={'Content-Type': content_type, 'X-Device-Key': key},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def poll_command(base_url: str, key: str) -> dict:
    req = urllib.request.Request(
        base_url.rstrip('/') + '/api/gate/command/',
        method='GET',
        headers={'X-Device-Key': key},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _print_decision(result: dict) -> None:
    authorized = result.get('authorized')
    icon = '✅ OPEN GATE' if authorized else '⛔ HOLD'
    print(f'\n{icon}  ({result.get("decision")})')
    print(f'  read text : {result.get("raw_text") or "—"}')
    print(f'  plate     : {result.get("plate") or "—"}')
    if result.get('owner'):
        print(f'  owner     : {result["owner"]} — {result.get("vehicle")}')
    print(f'  log id    : {result.get("log_id")}')


def main() -> int:
    parser = argparse.ArgumentParser(description='Simulate an ESP32-CAM gate node.')
    parser.add_argument('--url', default=os.environ.get('GATE_URL', 'http://127.0.0.1:8000'),
                        help='Backend base URL (default: http://127.0.0.1:8000)')
    parser.add_argument('--key', default=os.environ.get('DEVICE_API_KEY'),
                        help='Device API key (or set DEVICE_API_KEY env var)')
    parser.add_argument('--image', help='Path to a car image to send to the gate.')
    parser.add_argument('--direction', default='entry', choices=['entry', 'exit'])
    parser.add_argument('--watch', action='store_true',
                        help='Poll for manual-open commands from the dashboard.')
    parser.add_argument('--interval', type=float, default=3.0, help='Poll interval seconds.')
    args = parser.parse_args()

    if not args.key:
        parser.error('Provide --key (or DEVICE_API_KEY). Create a device on the dashboard Devices page.')

    if args.image:
        if not os.path.exists(args.image):
            parser.error(f'Image not found: {args.image}')
        print(f'Sending {args.image} → {args.url} (direction={args.direction})…')
        try:
            _print_decision(send_capture(args.url, args.key, args.image, args.direction))
        except urllib.error.HTTPError as exc:
            print(f'HTTP {exc.code}: {exc.read().decode(errors="replace")}')
            return 1

    if args.watch:
        print(f'\nWatching for manual-open commands every {args.interval}s (Ctrl+C to stop)…')
        try:
            while True:
                try:
                    cmd = poll_command(args.url, args.key)
                    if cmd.get('gate_action') == 'open':
                        print('✅ Manual OPEN command received from dashboard.')
                except urllib.error.HTTPError as exc:
                    print(f'poll error HTTP {exc.code}')
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print('\nStopped.')

    if not args.image and not args.watch:
        parser.error('Nothing to do: pass --image and/or --watch.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

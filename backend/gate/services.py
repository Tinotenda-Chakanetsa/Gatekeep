from __future__ import annotations

from typing import Any

from django.core.files.base import ContentFile
from django.utils import timezone

from .matching import find_matching_vehicle
from .models import AccessLog, GateDevice
from .plates import normalize_plate


def process_capture(
    image_path: str,
    *,
    device: GateDevice | None,
    direction: str,
    image_bytes: bytes | None = None,
    image_name: str = 'capture.jpg',
) -> AccessLog:
    """Run detection + OCR on a captured frame, decide access, and persist an AccessLog.

    `image_path` is a readable path for the OCR pipeline; `image_bytes` (optional) is
    stored on the log so the dashboard can show what the camera saw.
    """
    # Imported lazily: pulls in the heavy YOLO/PaddleOCR stack only when a real capture
    # is processed, so the API can boot and migrate without the ML dependencies present.
    from ocr_api.services import detect_plate_and_extract_text

    ocr = detect_plate_and_extract_text(image_path)

    raw_text = ocr.get('selected_text') or ''
    confidence = ocr.get('ocr', {}).get('average_score')
    plate_detected = bool(ocr.get('plate_detected'))

    matched_vehicle = find_matching_vehicle(raw_text) if plate_detected and raw_text else None

    if not plate_detected or not raw_text:
        decision = AccessLog.Decision.NO_PLATE
    elif matched_vehicle is not None:
        decision = AccessLog.Decision.GRANTED
    else:
        decision = AccessLog.Decision.DENIED

    log = AccessLog(
        device=device,
        direction=direction or AccessLog.Direction.ENTRY,
        source=AccessLog.Source.DEVICE,
        decision=decision,
        raw_text=raw_text[:128],
        normalized_plate=normalize_plate(raw_text),
        ocr_confidence=confidence,
        matched_vehicle=matched_vehicle,
        matched_person=matched_vehicle.owner if matched_vehicle else None,
    )

    if image_bytes:
        log.image.save(image_name, ContentFile(image_bytes), save=False)

    log.save()

    if device is not None:
        device.last_seen = timezone.now()
        device.save(update_fields=['last_seen'])

    return log


def decision_payload(log: AccessLog) -> dict[str, Any]:
    """Compact JSON the firmware reads to actuate the gate."""
    return {
        'authorized': log.decision == AccessLog.Decision.GRANTED,
        'decision': log.decision,
        'gate_action': 'open' if log.decision == AccessLog.Decision.GRANTED else 'hold',
        'plate': log.normalized_plate,
        'raw_text': log.raw_text,
        'vehicle': log.matched_vehicle.display_plate if log.matched_vehicle else None,
        'owner': log.matched_person.full_name if log.matched_person else None,
        'log_id': log.id,
    }

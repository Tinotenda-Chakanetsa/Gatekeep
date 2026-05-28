from __future__ import annotations

from django.conf import settings

from .models import Vehicle
from .plates import canonical_plate, levenshtein, normalize_plate


def find_matching_vehicle(raw_text: str) -> Vehicle | None:
    """Resolve a (possibly noisy) OCR plate string to an active registered vehicle.

    Tries exact normalized match first, then a confusion-folded match, then a bounded
    fuzzy match within PLATE_FUZZY_MAX_DISTANCE edits to tolerate OCR misreads.
    """
    normalized = normalize_plate(raw_text)
    if not normalized:
        return None

    active = Vehicle.objects.filter(is_active=True, owner__is_active=True)

    exact = active.filter(plate_number=normalized).first()
    if exact:
        return exact

    target_canonical = canonical_plate(raw_text)
    folded = active.filter(canonical=target_canonical).first()
    if folded:
        return folded

    max_distance = settings.PLATE_FUZZY_MAX_DISTANCE
    if max_distance <= 0:
        return None

    best: Vehicle | None = None
    best_distance = max_distance + 1
    for vehicle in active.only('id', 'canonical', 'plate_number', 'display_plate', 'owner'):
        distance = levenshtein(target_canonical, vehicle.canonical)
        if distance < best_distance:
            best_distance = distance
            best = vehicle
            if distance == 0:
                break

    return best if best_distance <= max_distance else None

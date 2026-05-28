from __future__ import annotations

import re

# Characters the OCR commonly confuses on plates. We fold them to a canonical form
# so "0/O" and "1/I" mismatches don't reject a legitimate vehicle.
_CONFUSION_MAP = str.maketrans({'O': '0', 'Q': '0', 'I': '1', 'L': '1', 'Z': '2', 'S': '5', 'B': '8'})
_NON_ALNUM = re.compile(r'[^A-Z0-9]')


def normalize_plate(raw: str) -> str:
    """Uppercase and strip everything but letters/digits. Used for storage + display key."""
    if not raw:
        return ''
    return _NON_ALNUM.sub('', raw.upper())


def canonical_plate(raw: str) -> str:
    """A fuzzier key that also folds visually-confusable characters, for matching only."""
    return normalize_plate(raw).translate(_CONFUSION_MAP)


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost))
        previous = current
    return previous[-1]

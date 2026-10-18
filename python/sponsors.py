"""Sponsor words read on a car (OCR text) as a team hint."""

SPONSOR_MIN_CONF = 0.90  # OCR detection confidence a word needs to count
FUZZY_MIN_LEN = 6  # keywords shorter than this must match exactly; longer ones may differ by one edit


def _within_one(a: str, b: str) -> bool:
    """Edit distance (insert, delete or substitute) of at most 1."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    if i == len(a):
        return True
    return a[i + 1:] == b[i + 1:] if len(a) == len(b) else a[i:] == b[i + 1:]


def sponsor_prefixes(ocr_trace: list, keywords: tuple) -> list:
    """ocr_trace: [[confidence, text], …]; keywords: ((word, tag prefix), …). The one prefix all
    matched sponsor words agree on, as a one-item list; [] when none match or two prefixes do."""
    found = set()
    for conf, text in ocr_trace:
        text = text.lower()
        if conf < SPONSOR_MIN_CONF:
            continue
        for word, prefix in keywords:
            if text == word or (len(word) >= FUZZY_MIN_LEN and _within_one(text, word)):
                found.add(prefix)
    return list(found) if len(found) == 1 else []

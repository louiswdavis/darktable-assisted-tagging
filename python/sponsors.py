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
    """ocr_trace: [[confidence, text, height share], …]; keywords: ((word, tag prefix), …). The one prefix
    all matched sponsor words agree on, as a one-item list; [] when none match or two prefixes do."""
    found = {prefix for _, prefix in _matches(ocr_trace, keywords)}
    return list(found) if len(found) == 1 else []


def _matches(ocr_trace: list, keywords: tuple) -> list:
    """The (keyword, tag prefix) pairs a confident OCR word in `ocr_trace` reads as, in read order."""
    out = []
    for conf, text, *_ in ocr_trace:
        text = text.lower()
        if conf < SPONSOR_MIN_CONF:
            continue
        for word, prefix in keywords:
            if text == word or (len(word) >= FUZZY_MIN_LEN and _within_one(text, word)):
                out.append((word, prefix))
    return out


def sponsor_words(ocr_trace: list, keywords: tuple, names: dict = None) -> list:
    """The listed keywords read in `ocr_trace`, each once in read order, as tag values: the keyword's
    `names` spelling ("dhl" -> "DHL"), else title-cased ("castrol" -> "Castrol"). Only listed words:
    free OCR text is never returned."""
    names = names or {}
    return list(dict.fromkeys(names.get(word) or word.title() for word, _ in _matches(ocr_trace, keywords)))

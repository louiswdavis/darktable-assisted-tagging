"""One fingerprint over everything that changes what identify.py caches per frame:
the constants of the per-frame modules and the decoder versions. It is part of
every cache.sqlite key, so editing a constant or upgrading a package re-reads on
the next run with no version to bump. test_identify.py fails when a constant of
a listed module is in neither table, so a new constant must be filed here."""

import hashlib
import json

import cv2
import numpy as np
import PIL

import car_colour
import colour
import embed
import ocr
import overlap
import people
import pod
import segment
import vehicles

# module -> constants whose value changes a cached box, read, embedding, histogram or mask
CACHE_INPUTS = {
    vehicles: ("MIN_BOX_FRAC", "MAX_BOXES", "CROP_DIM", "BOX_MARGIN_TRIM", "DETECTOR_INPUT", "DETECTOR_STRIDES",
               "DETECTOR_MIN_SCORE", "DETECTOR_NMS", "CANDIDATE_MIN_SCORE", "MAX_CANDIDATES", "VEHICLE_CLASSES"),
    ocr: ("OCR_MIN_SCORE", "NUMBER_MIN_HEIGHT", "DET_INPUT", "DET_MEAN", "REC_INPUT", "REC_CHARSET",
          "PADDLE_REC_HEIGHT", "PADDLE_REC_MIN_WIDTH", "_DIGIT_LOOKALIKES"),
    embed: ("EMBED_INPUT", "EMBED_DIM", "_MEAN", "_STD"),
    segment: ("SEGMENT_INPUT", "MAX_POINTS", "REGION_PAD", "MASK_MIN_SHARE", "GREY", "_INPUTS", "_OUTPUTS"),
    overlap: ("OVERLAP_MIN", "CONTAINED_MIN", "VISIBLE_MIN", "LEVEL_TOL"),
    pod: ("REGION_X", "REGION_Y", "REGION_MAX_DIM", "HUE", "MIN_SAT", "MIN_VAL", "YELLOW_MIN_FRAC", "BLACK_MAX_FRAC",
          "SIDE_ON_ASPECT"),
    colour: ("COLOUR_DIM", "CENTRE_FRACTION"),
    car_colour: ("BODY_X", "BODY_Y", "REGION_MAX_DIM"),
    people: ("FACE_EMBED_DIM", "FACE_CROP", "FACE_DETECT_LONG_EDGE", "FACE_DETECT_MIN_SCORE", "FACE_NMS"),
}
# module -> constants that only use cached data, are derived from an input, are already in
# the key another way (the palette digest, the model files) or are runtime state, not a value
CACHE_NEUTRAL = {
    vehicles: ("RAW_EXTENSIONS", "COCO_NAMES", "_RAW_FLIP_TURNS", "_DETECTORS"),
    ocr: ("REC_TARGET",),
    embed: ("DEGRADE_FACTOR",),
    segment: ("SEGMENTER_FILE", "SEGMENT_CACHE_TOKEN"),
    overlap: (),
    pod: (),
    colour: (),
    car_colour: ("PALETTE", "MULTI", "COLOUR_SOLE_MIN", "COLOUR_PART_MIN"),
    people: (),
}
_FINGERPRINT = ""


def _jsonable(v):
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, (set, frozenset)):
        return sorted(v)
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return v


def analysis_fingerprint() -> str:
    """12 hex chars over CACHE_INPUTS' values and the versions of OpenCV, Pillow, rawpy and numpy."""
    global _FINGERPRINT
    if _FINGERPRINT:
        return _FINGERPRINT
    try:
        import rawpy
        rawpy_version = getattr(rawpy, "__version__", "?")
    except ImportError:
        rawpy_version = "none"
    bits = {m.__name__: {n: _jsonable(getattr(m, n)) for n in names} for m, names in CACHE_INPUTS.items()}
    bits["versions"] = [cv2.__version__, PIL.__version__, rawpy_version, np.__version__]
    _FINGERPRINT = hashlib.sha1(json.dumps(bits, sort_keys=True, default=str).encode()).hexdigest()[:12]
    return _FINGERPRINT

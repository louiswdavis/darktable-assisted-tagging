"""Pick a frame's vehicles out of its shared detection entry (vehicle_detect.py) and
crop each one for OCR and embedding."""

import sys
import time
from pathlib import Path

try:
    import numpy as np
    import cv2
except ImportError as _e:
    print(
        f"Missing Python package '{_e.name or _e}' in {sys.executable}. "
        f"Install with: \"{sys.executable}\" -m pip install -r requirements.txt (from the repo's python folder)",
        file=sys.stderr,
    )
    sys.exit(3)

from common import RAW_EXTENSIONS  # noqa: E402  (stdlib-only module beside this file)
from vehicle_detect import CANDIDATE_MIN_SCORE, COCO_NAMES, boxes_in  # noqa: E402

MIN_BOX_FRAC = 0.005  # boxes smaller than this share of the frame are background traffic
MAX_BOXES = 4
CROP_DIM = 640
BOX_MARGIN_TRIM = 0.1  # trimmed off each edge of a detected box before cropping, so a loose
# box (common on cars shot at a distance) carries less background into the embedding
DETECTOR_MIN_SCORE = 0.20  # dark and distant liveries score 0.22-0.34, below the usual 0.35
MAX_CANDIDATES = 5  # weaker detections kept as rescue candidates (see rescue.py)


def log(msg: str):
    """One timestamped line on stderr, which the plugin appends to its run log."""
    print(time.strftime("%H:%M:%S ") + "py: " + msg, file=sys.stderr, flush=True)


def read_onnx(model_path: str):
    """cv2.dnn net from an .onnx file. Read through numpy: cv2's own path
    argument is narrow on Windows, so a non-ASCII path (a username) fails."""
    return cv2.dnn.readNetFromONNX(np.fromfile(model_path, np.uint8))


def load_hires(filepath: str):
    """A RAW decoded sharper than decode_rgb's embedded preview (half-size demosaic, upright), or None
    for any other file, which decode_rgb already decodes in full. The same framing as decode_rgb when
    the preview is uncropped; the caller checks the aspect ratio."""
    if Path(filepath).suffix.lower() not in RAW_EXTENSIONS:
        return None
    import rawpy
    with rawpy.imread(filepath) as raw:
        return raw.postprocess(half_size=True, use_camera_wb=True, no_auto_bright=True)


def strongest_detections(boxes: list, w: int, h: int) -> str:
    """For the log when no vehicle passes: the strongest vehicle the entry holds (only vehicle
    classes are stored, from CANDIDATE_MIN_SCORE up), with its size in the frame."""
    if not boxes:
        return f"nothing at {CANDIDATE_MIN_SCORE}"
    x0, y0, x1, y1, score, c = max(boxes, key=lambda b: b[4])
    return f"strongest vehicle {COCO_NAMES.get(c, f'class {c}')} {score:.2f} ({(x1 - x0) / w:.2f}x{(y1 - y0) / h:.2f} of frame)"


def select_boxes(boxes: list, w: int, h: int) -> list:
    """Boxes clipped to the frame, at least MIN_BOX_FRAC of it, largest first, at most MAX_BOXES."""
    out = []
    for x0, y0, x1, y1, score, coco in boxes:
        x0, x1 = min(max(x0, 0.0), w), min(max(x1, 0.0), w)
        y0, y1 = min(max(y0, 0.0), h), min(max(y1, 0.0), h)
        if (x1 - x0) * (y1 - y0) >= MIN_BOX_FRAC * w * h:
            out.append((float(x0), float(y0), float(x1), float(y1), float(score), int(coco)))
    out.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
    return out[:MAX_BOXES]


def detect(rgb: np.ndarray, entry: dict) -> tuple:
    """(vehicle boxes as (x0, y0, x1, y1, score, coco) in rgb pixels, weaker candidate boxes in
    the same form strongest first, log note: "" when at least one box passed). `entry` is the
    frame's shared detection (vehicle_detect.detect or detect_cached); its boxes are rescaled to
    rgb. Candidates scored CANDIDATE_MIN_SCORE up to DETECTOR_MIN_SCORE; they only matter to
    burst rescue."""
    h, w = rgb.shape[:2]
    stored = boxes_in(entry, w, h)
    boxes = select_boxes([b for b in stored if b[4] >= DETECTOR_MIN_SCORE], w, h)
    weak = [b for b in select_boxes(stored, w, h) if b[4] < DETECTOR_MIN_SCORE]
    weak = sorted(weak, key=lambda b: b[4], reverse=True)[:MAX_CANDIDATES]
    if boxes:
        return boxes, weak, ""
    return [], weak, f"no vehicle at {DETECTOR_MIN_SCORE}: {strongest_detections(stored, w, h)}"


def detect_vehicles(rgb: np.ndarray, entry: dict) -> tuple:
    """(vehicle boxes as (x0, y0, x1, y1, score, coco) in rgb pixels, log note:
    "" when at least one box passed)."""
    boxes, _, note = detect(rgb, entry)
    return boxes, note


def crop_box(rgb: np.ndarray, box) -> np.ndarray:
    """The box's region, trimmed by BOX_MARGIN_TRIM on each edge and its long side
    downscaled to at most CROP_DIM (never upscaled)."""
    h, w = rgb.shape[:2]
    bx0, by0, bx1, by1 = box[0], box[1], box[2], box[3]
    trim_x, trim_y = (bx1 - bx0) * BOX_MARGIN_TRIM, (by1 - by0) * BOX_MARGIN_TRIM
    x0, y0 = max(int(bx0 + trim_x), 0), max(int(by0 + trim_y), 0)
    x1, y1 = min(int(round(bx1 - trim_x)), w), min(int(round(by1 - trim_y)), h)
    crop = rgb[y0:max(y1, y0 + 1), x0:max(x1, x0 + 1)]
    ch, cw = crop.shape[:2]
    scale = CROP_DIM / max(ch, cw)
    if scale < 1:
        crop = cv2.resize(crop, (max(1, int(cw * scale)), max(1, int(ch * scale))), interpolation=cv2.INTER_AREA)
    return np.ascontiguousarray(crop)

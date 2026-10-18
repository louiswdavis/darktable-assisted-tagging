"""Decode a frame at native resolution, find its vehicles with YOLOX, and
crop each one for OCR and embedding."""

import io
import os
import sys
import time
from pathlib import Path

try:
    import numpy as np
    import cv2
    from PIL import Image, ImageOps
except ImportError as _e:
    print(
        f"Missing Python package '{_e.name or _e}' in {sys.executable}. "
        f"Install with: \"{sys.executable}\" -m pip install -r requirements.txt (from the repo's python folder)",
        file=sys.stderr,
    )
    sys.exit(3)

RAW_EXTENSIONS = {".cr2", ".cr3", ".nef", ".arw", ".rw2", ".dng", ".raf", ".orf"}

MIN_BOX_FRAC = 0.02  # boxes smaller than this share of the frame are background traffic
MAX_BOXES = 4
CROP_DIM = 640
BOX_MARGIN_TRIM = 0.1  # trimmed off each edge of a detected box before cropping, so a loose
# box (common on cars shot at a distance) carries less background into the embedding


def log(msg: str):
    """One timestamped line on stderr, which the plugin appends to its run log."""
    print(time.strftime("%H:%M:%S ") + "py: " + msg, file=sys.stderr, flush=True)


def file_key(filepath: str):
    """[path, mtime_ns, size], or None if the file can't be stat'ed (it then
    isn't cached, and the decode reports the real error)."""
    try:
        st = os.stat(filepath)
    except OSError:
        return None
    return [os.path.abspath(filepath), st.st_mtime_ns, st.st_size]


def _open_rgb(source) -> tuple:
    """(rgb array upright per EXIF orientation, whether the file carried a rotation)."""
    img = Image.open(source)
    rotated = img.getexif().get(0x0112, 1) not in (0, 1)
    return np.array(ImageOps.exif_transpose(img).convert("RGB")), rotated


# LibRaw's sizes.flip codes → the np.rot90 turns (counter-clockwise) that make the image upright
_RAW_FLIP_TURNS = {3: 2, 5: 1, 6: 3}


def load_full(filepath: str) -> np.ndarray:
    """Decoded image, upright, at native resolution (a RAW's embedded preview).
    Boxes and crops all come from this one decode, so they always agree."""
    ext = Path(filepath).suffix.lower()
    if ext in RAW_EXTENSIONS:
        import rawpy
        with rawpy.imread(filepath) as raw:
            try:
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    rgb, rotated = _open_rgb(io.BytesIO(thumb.data))
                elif thumb.format == rawpy.ThumbFormat.BITMAP:
                    rgb, rotated = thumb.data, False
                else:
                    raise ValueError("Unsupported thumbnail")
                # embedded previews are usually stored unrotated; the raw header says how to turn them
                if not rotated:
                    rgb = np.ascontiguousarray(np.rot90(rgb, _RAW_FLIP_TURNS.get(raw.sizes.flip, 0)))
            except Exception:
                rgb = raw.postprocess(half_size=True, use_camera_wb=True, no_auto_bright=True)
        return rgb
    rgb, _ = _open_rgb(filepath)
    return rgb


# YOLOX as exported by opencv_zoo (object_detection_yolox_2022nov.onnx): RGB 0–255
# letterboxed top-left onto a 114-grey 640² canvas; raw per-anchor grid outputs.
DETECTOR_INPUT = 640
DETECTOR_STRIDES = (8, 16, 32)
DETECTOR_MIN_SCORE = 0.25  # was 0.35; dark liveries score 0.25-0.34 (F1 report: 65 of 143 misses)
DETECTOR_NMS = 0.5
VEHICLE_CLASSES = [2, 3, 7]  # COCO car, motorcycle, truck (race cars are often called trucks)

_DETECTORS: dict = {}


def read_onnx(model_path: str):
    """cv2.dnn net from an .onnx file. Read through numpy: cv2's own path
    argument is narrow on Windows, so a non-ASCII path (a username) fails."""
    return cv2.dnn.readNetFromONNX(np.fromfile(model_path, np.uint8))


def detector_model(model_path: str):
    if model_path not in _DETECTORS:
        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"object detector model not found: {model_path}")
        _DETECTORS[model_path] = read_onnx(model_path)
    return _DETECTORS[model_path]


def _yolox_anchors(size: int = DETECTOR_INPUT) -> tuple:
    grids, strides = [], []
    for s in DETECTOR_STRIDES:
        n = size // s
        xv, yv = np.meshgrid(np.arange(n), np.arange(n))
        grids.append(np.stack((xv, yv), 2).reshape(-1, 2))
        strides.append(np.full((n * n, 1), s))
    return np.concatenate(grids), np.concatenate(strides)


def decode_vehicles(raw: np.ndarray, scale: float) -> list:
    """Raw YOLOX output (anchors × 85) → [(x0, y0, x1, y1, score, coco_class)]
    vehicle boxes in source pixels after NMS. `scale` is the letterbox resize factor."""
    grid, stride = _yolox_anchors()
    xy = (raw[:, :2] + grid) * stride
    wh = np.exp(raw[:, 2:4]) * stride
    cls = raw[:, 4:5] * raw[:, 5:][:, VEHICLE_CLASSES]
    score, best = cls.max(axis=1), cls.argmax(axis=1)
    keep = score >= DETECTOR_MIN_SCORE
    if not keep.any():
        return []
    xy, wh, score, best = xy[keep] / scale, wh[keep] / scale, score[keep], best[keep]
    tl = xy - wh / 2
    picked = cv2.dnn.NMSBoxes(np.hstack([tl, wh]).tolist(), score.tolist(), DETECTOR_MIN_SCORE, DETECTOR_NMS)
    return [(tl[i, 0], tl[i, 1], tl[i, 0] + wh[i, 0], tl[i, 1] + wh[i, 1], float(score[i]),
             VEHICLE_CLASSES[best[i]]) for i in np.asarray(picked).reshape(-1)]


COCO_NAMES = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane", 5: "bus",
              6: "train", 7: "truck", 8: "boat"}


def strongest_detections(raw: np.ndarray, scale: float, w: int, h: int) -> str:
    """For the log when no vehicle passes: the strongest detection of any
    class, and the strongest vehicle one, each with its size in the frame."""
    _, stride = _yolox_anchors()
    cls = raw[:, 4:5] * raw[:, 5:]

    def describe(i, c):
        bw, bh = np.exp(raw[i, 2:4]) * stride[i, 0] / scale
        return f"{COCO_NAMES.get(c, f'class {c}')} {cls[i, c]:.2f} ({bw / w:.2f}x{bh / h:.2f} of frame)"

    i, c = np.unravel_index(np.argmax(cls), cls.shape)
    vi, vc = np.unravel_index(np.argmax(cls[:, VEHICLE_CLASSES]), (len(cls), len(VEHICLE_CLASSES)))
    return f"strongest {describe(i, c)}, strongest vehicle {describe(vi, VEHICLE_CLASSES[vc])}"


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


def detect_vehicles(rgb: np.ndarray, model_path: str) -> tuple:
    """(vehicle boxes as (x0, y0, x1, y1, score, coco) in rgb pixels, log note:
    "" when at least one box passed)."""
    h, w = rgb.shape[:2]
    scale = min(DETECTOR_INPUT / h, DETECTOR_INPUT / w)
    canvas = np.full((DETECTOR_INPUT, DETECTOR_INPUT, 3), 114.0, np.float32)
    canvas[:int(h * scale), :int(w * scale)] = cv2.resize(rgb, (int(w * scale), int(h * scale)),
                                                          interpolation=cv2.INTER_AREA)
    net = detector_model(model_path)
    net.setInput(np.transpose(canvas, (2, 0, 1))[np.newaxis])
    raw = net.forward(net.getUnconnectedOutLayersNames())[0][0]
    boxes = select_boxes(decode_vehicles(raw, scale), w, h)
    if boxes:
        return boxes, ""
    return [], f"no vehicle at {DETECTOR_MIN_SCORE}: {strongest_detections(raw, scale, w, h)}"


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

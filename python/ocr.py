"""Race numbers from a vehicle crop: opencv_zoo's PP-OCRv3 text detector
finds text quads, its CRNN recogniser reads each one."""

import os

import numpy as np
import cv2

from vehicles import file_key, read_onnx

OCR_MIN_SCORE = 0.80

DET_INPUT = 736  # PP-OCRv3 DB takes sides that are multiples of 32
DET_MEAN = (122.67891434, 116.66876762, 104.00698793)
REC_INPUT = (100, 32)
REC_CHARSET = "0123456789abcdefghijklmnopqrstuvwxyz"
# CRNN wants the quad's corners bottom-left, top-left, top-right, bottom-right, which is the
# order the DB detector returns them in
REC_TARGET = np.array([[0, REC_INPUT[1] - 1], [0, 0], [REC_INPUT[0] - 1, 0],
                       [REC_INPUT[0] - 1, REC_INPUT[1] - 1]], dtype=np.float32)
# letters the recogniser confuses with digits on a race number
_DIGIT_LOOKALIKES = str.maketrans({"o": "0", "l": "1", "i": "1"})


def digits_only(text: str):
    """A 1–3 digit race number from recognised text, or None."""
    t = text.lower().translate(_DIGIT_LOOKALIKES)
    return t if 1 <= len(t) <= 3 and t.isdigit() else None


def ocr_key(det_path: str, rec_path: str):
    return [file_key(det_path), file_key(rec_path)]


def _letterbox(rgb: np.ndarray, size: int) -> np.ndarray:
    h, w = rgb.shape[:2]
    scale = size / max(h, w)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    canvas = np.full((size, size, 3), 255, np.uint8)
    canvas[:nh, :nw] = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    return canvas


def _probs(out: np.ndarray) -> np.ndarray:
    """CRNN output as per-step class probabilities (T × 37). Rows that are already probabilities pass
    through; logits and log-probabilities are softmaxed (softmax of log p is p)."""
    rows = out.reshape(out.shape[0], -1).astype(np.float64)
    if rows.min() >= 0 and np.allclose(rows.sum(axis=1), 1.0, atol=1e-3):
        return rows
    e = np.exp(rows - rows.max(axis=1, keepdims=True))
    return e / e.sum(axis=1, keepdims=True)


def _ctc_greedy(out: np.ndarray) -> tuple:
    """CRNN output (T × 1 × 37, class 0 blank) → (text, read confidence), repeats and blanks collapsed.
    A character's confidence is its best step's probability; the read's is its least sure character's,
    so one doubtful digit makes the whole number doubtful. No characters gives 0."""
    p = _probs(out)
    best = p.argmax(axis=1)
    chars, confs, prev = [], [], 0
    for t, c in enumerate(best):
        if c != 0 and c != prev:
            chars.append(REC_CHARSET[c - 1])
            confs.append(p[t, c])
        elif c != 0:
            confs[-1] = max(confs[-1], p[t, c])
        prev = c
    return "".join(chars), float(min(confs, default=0.0))


class NumberReader:
    def __init__(self, det_path: str, rec_path: str):
        self.last_trace: list = []
        for label, p in (("OCR text detection", det_path), ("OCR text recognition", rec_path)):
            if not os.path.isfile(p):
                raise FileNotFoundError(f"{label} model not found: {p}")
        self.det = cv2.dnn_TextDetectionModel_DB(read_onnx(det_path))
        self.det.setBinaryThreshold(0.3)
        self.det.setPolygonThreshold(0.5)
        self.det.setMaxCandidates(200)
        self.det.setUnclipRatio(2.0)
        self.det.setInputParams(1.0 / 255.0, (DET_INPUT, DET_INPUT), DET_MEAN)
        self.rec = read_onnx(rec_path)

    def read(self, crop_rgb: np.ndarray) -> list:
        """[(digits, confidence)], distinct numbers, most confident first, for text regions detected at
        OCR_MIN_SCORE or above. Confidence is the lower of the detection score and the recogniser's read
        confidence: a plate can look very like text and still be read unsurely. Also sets `last_trace`:
        the five most confident detected text regions as [confidence, raw text], accepted or not, so a
        zero-read crop shows what the reader saw."""
        bgr = cv2.cvtColor(_letterbox(crop_rgb, DET_INPUT), cv2.COLOR_RGB2BGR)
        quads, confidences = self.det.detect(bgr)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        best, trace = {}, []
        for quad, conf in zip(quads, confidences):
            m = cv2.getPerspectiveTransform(np.asarray(quad, np.float32).reshape(4, 2), REC_TARGET)
            word = cv2.warpPerspective(gray, m, REC_INPUT)
            self.rec.setInput(cv2.dnn.blobFromImage(word, 1 / 127.5, REC_INPUT, 127.5))
            text, read_conf = _ctc_greedy(self.rec.forward())
            both = min(float(conf), read_conf)
            trace.append([both, text])
            digits = digits_only(text)
            if conf >= OCR_MIN_SCORE and digits and both > best.get(digits, -1.0):
                best[digits] = both
        self.last_trace = sorted(trace, reverse=True)[:5]
        return sorted(best.items(), key=lambda kv: kv[1], reverse=True)

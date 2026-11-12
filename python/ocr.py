"""Race numbers from a vehicle crop: opencv_zoo's PP-OCRv3 text detector finds text quads, a
recogniser reads each one. The recogniser is opencv_zoo's CRNN, or a PaddleOCR one (e.g.
en_PP-OCRv5_mobile_rec) when its inference.yml sits beside the model as <model name>.yml."""

import math
import os

import numpy as np
import cv2

from vehicles import read_onnx
from vehicle_detect import file_key

OCR_MIN_SCORE = 0.80
# a number's text region must be at least this share of the vehicle crop's height. Number plate
# characters and lone sticker letters sit well under a door or bonnet number. A first guess: the
# report's "ocr saw" line prints each region's share (h0.12) to tune it from
NUMBER_MIN_HEIGHT = 0.07

DET_INPUT = 736  # PP-OCRv3 DB takes sides that are multiples of 32
DET_MEAN = (122.67891434, 116.66876762, 104.00698793)
REC_INPUT = (100, 32)
REC_CHARSET = "0123456789abcdefghijklmnopqrstuvwxyz"
# CRNN wants the quad's corners bottom-left, top-left, top-right, bottom-right, which is the
# order the DB detector returns them in
REC_TARGET = np.array([[0, REC_INPUT[1] - 1], [0, 0], [REC_INPUT[0] - 1, 0],
                       [REC_INPUT[0] - 1, REC_INPUT[1] - 1]], dtype=np.float32)
PADDLE_REC_HEIGHT = 48  # PaddleOCR rec inference.yml: RecResizeImg image_shape 3 x 48 x 320
PADDLE_REC_MIN_WIDTH = 320
# letters the recogniser confuses with digits on a race number
_DIGIT_LOOKALIKES = str.maketrans({"o": "0", "l": "1", "i": "1"})


def digits_only(text: str):
    """A 1–3 digit race number from recognised text, or None. ASCII digits only: a larger
    dictionary also holds superscript and circled digits, which str.isdigit accepts."""
    t = text.lower().translate(_DIGIT_LOOKALIKES)
    return t if 1 <= len(t) <= 3 and t.isascii() and t.isdigit() else None


def paddle_dict_path(rec_path: str) -> str:
    """The PaddleOCR inference.yml that marks a recogniser as PaddleOCR: <model without .onnx>.yml."""
    return os.path.splitext(rec_path)[0] + ".yml"


def ocr_key(det_path: str, rec_path: str):
    key = [file_key(det_path), file_key(rec_path)]
    dict_path = paddle_dict_path(rec_path)
    return key + [file_key(dict_path)] if os.path.isfile(dict_path) else key


def _letterbox(rgb: np.ndarray, size: int) -> np.ndarray:
    h, w = rgb.shape[:2]
    scale = size / max(h, w)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    canvas = np.full((size, size, 3), 255, np.uint8)
    canvas[:nh, :nw] = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    return canvas


def height_share(quad, crop_h: int, crop_w: int, size: int = DET_INPUT) -> float:
    """A letterboxed text quad's height (its longer left or right side) as a share of the crop's height."""
    q = np.asarray(quad, np.float32).reshape(4, 2)
    side = max(np.linalg.norm(q[0] - q[1]), np.linalg.norm(q[3] - q[2]))
    return float(side / (crop_h * size / max(crop_h, crop_w, 1)))


def _probs(out: np.ndarray) -> np.ndarray:
    """Recogniser output as per-step class probabilities (T × classes). Rows that are already probabilities pass
    through; logits and log-probabilities are softmaxed (softmax of log p is p)."""
    rows = out.reshape(out.shape[0], -1).astype(np.float64)
    if rows.min() >= 0 and np.allclose(rows.sum(axis=1), 1.0, atol=1e-3):
        return rows
    e = np.exp(rows - rows.max(axis=1, keepdims=True))
    return e / e.sum(axis=1, keepdims=True)


def _ctc_greedy(out: np.ndarray, charset=REC_CHARSET) -> tuple:
    """Recogniser output (T × [1 ×] classes, class 0 blank, class i charset[i - 1]) → (text, read
    confidence), repeats and blanks collapsed. A character's confidence is its best step's probability;
    the read's is its least sure character's, so one doubtful digit makes the whole number doubtful.
    No characters gives 0."""
    p = _probs(out)
    best = p.argmax(axis=1)
    chars, confs, prev = [], [], 0
    for t, c in enumerate(best):
        if c != 0 and c != prev:
            chars.append(charset[c - 1])
            confs.append(p[t, c])
        elif c != 0:
            confs[-1] = max(confs[-1], p[t, c])
        prev = c
    return "".join(chars), float(min(confs, default=0.0))


def paddle_charset(dict_path: str, classes: int) -> list:
    """The character list from a PaddleOCR inference.yml's PostProcess.character_dict, with the space
    PaddleOCR appends when the model has one more class than blank + dictionary."""
    import yaml  # only PaddleOCR recognisers need it
    with open(dict_path, encoding="utf-8") as f:
        doc = yaml.load(f, Loader=yaml.BaseLoader)  # BaseLoader keeps every entry a string ("0", "y")
    chars = list(((doc or {}).get("PostProcess") or {}).get("character_dict") or [])
    if classes == len(chars) + 2:
        return chars + [" "]
    if classes == len(chars) + 1:
        return chars
    raise ValueError(f"{dict_path}: {len(chars)} characters do not fit a recogniser with {classes} classes")


def paddle_rec_input(word_bgr: np.ndarray) -> np.ndarray:
    """A word crop as PaddleOCR rec input: height PADDLE_REC_HEIGHT at its own aspect, scaled to
    -1..1, right-padded with 0 to at least PADDLE_REC_MIN_WIDTH; shape 1 × 3 × H × W."""
    h, w = word_bgr.shape[:2]
    rw = max(1, math.ceil(PADDLE_REC_HEIGHT * w / max(h, 1)))
    img = cv2.resize(word_bgr, (rw, PADDLE_REC_HEIGHT)).astype(np.float32) / 255.0
    out = np.zeros((3, PADDLE_REC_HEIGHT, max(rw, PADDLE_REC_MIN_WIDTH)), np.float32)
    out[:, :, :rw] = ((img - 0.5) / 0.5).transpose(2, 0, 1)
    return out[np.newaxis]


def quad_word(bgr: np.ndarray, quad: np.ndarray) -> np.ndarray:
    """The quad (bottom-left, top-left, top-right, bottom-right) warped flat at its own size."""
    q = np.asarray(quad, np.float32).reshape(4, 2)
    w = int(round(max(np.linalg.norm(q[2] - q[1]), np.linalg.norm(q[3] - q[0])))) or 1
    h = int(round(max(np.linalg.norm(q[0] - q[1]), np.linalg.norm(q[3] - q[2])))) or 1
    target = np.array([[0, h - 1], [0, 0], [w - 1, 0], [w - 1, h - 1]], dtype=np.float32)
    return cv2.warpPerspective(bgr, cv2.getPerspectiveTransform(q, target), (w, h))


class CrnnRecogniser:
    """opencv_zoo's CRNN: grey 100 × 32, digits and lowercase letters."""
    name = "CRNN"

    def __init__(self, rec_path: str):
        self.net = read_onnx(rec_path)

    def read_word(self, bgr: np.ndarray, quad) -> tuple:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        m = cv2.getPerspectiveTransform(np.asarray(quad, np.float32).reshape(4, 2), REC_TARGET)
        word = cv2.warpPerspective(gray, m, REC_INPUT)
        self.net.setInput(cv2.dnn.blobFromImage(word, 1 / 127.5, REC_INPUT, 127.5))
        return _ctc_greedy(self.net.forward())


class PaddleRecogniser:
    """A PaddleOCR recogniser (e.g. en_PP-OCRv5_mobile_rec) on onnxruntime: colour, height 48."""
    name = "PaddleOCR"

    def __init__(self, rec_path: str, dict_path: str):
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1  # the worker pool supplies the parallelism
        with open(rec_path, "rb") as f:  # bytes, so a non-ASCII path can't trip a narrow-path API
            self.session = ort.InferenceSession(f.read(), opts, providers=["CPUExecutionProvider"])
        self.input = self.session.get_inputs()[0].name
        # one blank word gives the class count, so a dictionary that doesn't fit fails at load
        blank = np.zeros((1, 3, PADDLE_REC_HEIGHT, PADDLE_REC_MIN_WIDTH), np.float32)
        self.charset = paddle_charset(dict_path, self.session.run(None, {self.input: blank})[0].shape[-1])

    def read_word(self, bgr: np.ndarray, quad) -> tuple:
        out = self.session.run(None, {self.input: paddle_rec_input(quad_word(bgr, quad))})[0][0]
        return _ctc_greedy(out, self.charset)


def recogniser(rec_path: str):
    """PaddleRecogniser when <model>.yml sits beside the model, else CrnnRecogniser."""
    dict_path = paddle_dict_path(rec_path)
    return PaddleRecogniser(rec_path, dict_path) if os.path.isfile(dict_path) else CrnnRecogniser(rec_path)


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
        self.rec = recogniser(rec_path)

    def read(self, crop_rgb: np.ndarray) -> list:
        """[(digits, confidence)], distinct numbers, most confident first, for text regions detected at
        OCR_MIN_SCORE or above and at least NUMBER_MIN_HEIGHT of the crop's height. Confidence is the
        lower of the detection score and the recogniser's read confidence: a plate can look very like
        text and still be read unsurely. Also sets `last_trace`: the five most confident detected text
        regions as [confidence, raw text, height share], accepted or not, so a zero-read crop shows
        what the reader saw."""
        h, w = crop_rgb.shape[:2]
        bgr = cv2.cvtColor(_letterbox(crop_rgb, DET_INPUT), cv2.COLOR_RGB2BGR)
        quads, confidences = self.det.detect(bgr)
        best, trace = {}, []
        for quad, conf in zip(quads, confidences):
            text, read_conf = self.rec.read_word(bgr, quad)
            both = min(float(conf), read_conf)
            share = height_share(quad, h, w)
            trace.append([both, text, round(share, 3)])
            digits = digits_only(text)
            if conf >= OCR_MIN_SCORE and digits and share >= NUMBER_MIN_HEIGHT and both > best.get(digits, -1.0):
                best[digits] = both
        self.last_trace = sorted(trace, reverse=True)[:5]
        return sorted(best.items(), key=lambda kv: kv[1], reverse=True)

"""Race numbers from a vehicle crop: a text detector finds text quads, a recogniser reads each one.
The detector is opencv_zoo's PP-OCRv3, or a PaddleOCR one (e.g. PP-OCRv6_small_det); the recogniser
is opencv_zoo's CRNN, or a PaddleOCR one (e.g. en_PP-OCRv5_mobile_rec). A model is PaddleOCR when its
inference.yml sits beside it as <model name>.yml."""

import math
import os
import re
import string

import numpy as np
import cv2

from vehicles import read_onnx
from vehicle_detect import file_key

OCR_MIN_SCORE = 0.80
# a number's text region must be at least this share of the vehicle crop's height. Number plate
# characters and lone sticker letters sit well under a door or bonnet number. A first guess: the
# report's "ocr saw" line prints each region's share (h0.12) to tune it from
NUMBER_MIN_HEIGHT = 0.07

DET_INPUT = 736  # DB detectors take sides that are multiples of 32
# the long-side cap of the crop the reader gets: text is found on its DET_INPUT letterbox, then
# each quad is read from this crop, so a small number keeps the pixels the letterbox threw away
OCR_CROP_DIM = 1600
# a region read less surely than this is read again turned 180° (Rules.min_read's default; the
# reads are cached before matching, so a preset's min_read can't steer them)
TURN_RETRY_BELOW = 0.85
TALL_QUAD = 1.5  # ...and a quad at least this many times taller than wide, 90° both ways too
DET_MEAN = (122.67891434, 116.66876762, 104.00698793)
REC_INPUT = (100, 32)
REC_CHARSET = "0123456789abcdefghijklmnopqrstuvwxyz"
PADDLE_REC_HEIGHT = 48  # PaddleOCR rec inference.yml: RecResizeImg image_shape 3 x 48 x 320
PADDLE_REC_MIN_WIDTH = 320
# letters the recogniser confuses with digits on a race number
_DIGIT_LOOKALIKES = str.maketrans({"o": "0", "l": "1", "i": "1", "|": "1", "!": "1"})
# digit_matrix also folds these: list_read weighs them against the start list, while a read's
# text keeps the letter, so S4 is never tagged 54 unless 54 is on the list
_MATRIX_LOOKALIKES = str.maketrans({"o": "0", "l": "1", "i": "1", "|": "1", "!": "1",
                                    "s": "5", "b": "8", "z": "2", "g": "6"})
NUMBER_MAX_DIGITS = 3  # a longer run (a year, a phone number on a sticker) is not a race number
# a region's text splits into tokens at spaces and punctuation, except | and ! (look-alikes of 1)
_TOKEN_BREAK = re.compile("[\\s" + re.escape(string.punctuation.replace("|", "").replace("!", "")) + "]+")
DIGIT_COLUMNS = 11  # a digit matrix's columns: blank, then 0-9
CTC_TRIM_BLANK = 0.995  # leading and trailing steps this sure of blank carry no digit evidence
DB_MIN_SIDE = 3  # PaddleOCR DBPostProcess min_size: a text box's shorter side, in letterbox pixels


def digit_runs(text: str) -> list:
    """The race numbers in recognised text, in order, each once: a token that is all digits once
    look-alikes are folded counts whole (l4 → 14); in any other token only its ASCII digits count
    (14A → 14, #7 → 7, RALLYE → none). Runs over NUMBER_MAX_DIGITS (2026) are dropped. Superscript
    and circled digits are not ASCII, so they never count."""
    out = []
    for token in _TOKEN_BREAK.split(text.lower()):
        folded = token.translate(_DIGIT_LOOKALIKES)
        runs = [folded] if folded.isascii() and folded.isdigit() else re.findall("[0-9]+", token)
        out += [r for r in runs if len(r) <= NUMBER_MAX_DIGITS and r not in out]
    return out


def paddle_dict_path(model_path: str) -> str:
    """The PaddleOCR inference.yml that marks a detector or recogniser as PaddleOCR: <model without .onnx>.yml."""
    return os.path.splitext(model_path)[0] + ".yml"


def ocr_key(det_path: str, rec_path: str):
    """The models' cache key: both files, then the recogniser's and detector's .yml where present."""
    key = [file_key(det_path), file_key(rec_path)]
    return key + [file_key(p) for p in (paddle_dict_path(rec_path), paddle_dict_path(det_path)) if os.path.isfile(p)]


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


def digit_matrix(out: np.ndarray, charset=REC_CHARSET) -> list:
    """Recogniser output folded to DIGIT_COLUMNS per step, [blank, 0..9], as a list of rows rounded
    to 4 decimals. A digit's column sums its charset column and its look-alikes' (_MATRIX_LOOKALIKES),
    so every reader gives the same shape. Leading and trailing steps with blank above CTC_TRIM_BLANK
    are dropped; an all-blank output gives []."""
    p = _probs(out)
    cols = np.zeros((p.shape[0], DIGIT_COLUMNS))
    cols[:, 0] = p[:, 0]
    for i, ch in enumerate(charset, start=1):
        d = str(ch).lower().translate(_MATRIX_LOOKALIKES)
        if len(d) == 1 and d in "0123456789":
            cols[:, 1 + int(d)] += p[:, i]
    keep = np.nonzero(cols[:, 0] <= CTC_TRIM_BLANK)[0]
    if not len(keep):
        return []
    return np.round(cols[keep[0]:keep[-1] + 1], 4).tolist()


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
    img = _resized(word_bgr, (rw, PADDLE_REC_HEIGHT)).astype(np.float32) / 255.0
    out = np.zeros((3, PADDLE_REC_HEIGHT, max(rw, PADDLE_REC_MIN_WIDTH)), np.float32)
    out[:, :, :rw] = ((img - 0.5) / 0.5).transpose(2, 0, 1)
    return out[np.newaxis]


def _resized(img: np.ndarray, size: tuple) -> np.ndarray:
    """img at size (w, h): area-averaged when shrinking, so a word read from a large crop doesn't alias."""
    shrink = size[0] * size[1] < img.shape[0] * img.shape[1]
    return cv2.resize(img, size, interpolation=cv2.INTER_AREA if shrink else cv2.INTER_LINEAR)


def quad_word(bgr: np.ndarray, quad: np.ndarray) -> np.ndarray:
    """The quad (bottom-left, top-left, top-right, bottom-right) warped flat at its own size."""
    q = np.asarray(quad, np.float32).reshape(4, 2)
    w, h = _quad_size(q)
    target = np.array([[0, h - 1], [0, 0], [w - 1, 0], [w - 1, h - 1]], dtype=np.float32)
    return cv2.warpPerspective(bgr, cv2.getPerspectiveTransform(q, target), (w, h))


def _quad_size(q: np.ndarray) -> tuple:
    """(width, height) in whole pixels, at least 1, of a 4 × 2 quad: its longer top or bottom side, and
    its longer left or right side."""
    w = int(round(max(np.linalg.norm(q[2] - q[1]), np.linalg.norm(q[3] - q[0])))) or 1
    h = int(round(max(np.linalg.norm(q[0] - q[1]), np.linalg.norm(q[3] - q[2])))) or 1
    return w, h


def paddle_det_config(yml_path: str) -> dict:
    """A PaddleOCR detector's inference.yml as {thresh, box_thresh, unclip_ratio, max_candidates,
    mean, std}: DBPostProcess's settings and NormalizeImage's per-channel mean and std. A missing
    key raises, so a yml that isn't a DB detector's fails at load."""
    import yaml  # only PaddleOCR models need it
    with open(yml_path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    post = doc["PostProcess"]
    norm = next(op["NormalizeImage"] for op in doc["PreProcess"]["transform_ops"]
                if isinstance(op, dict) and "NormalizeImage" in op)
    return {"thresh": float(post["thresh"]), "box_thresh": float(post["box_thresh"]),
            "unclip_ratio": float(post["unclip_ratio"]), "max_candidates": int(post["max_candidates"]),
            "mean": np.array(norm["mean"], np.float32), "std": np.array(norm["std"], np.float32)}


def db_boxes(prob: np.ndarray, config: dict) -> tuple:
    """([quad], [score]) from a DB probability map (H × W), as PaddleOCR's DBPostProcess: each blob
    over thresh gives its rotated box, scored by the map's mean inside it, kept at box_thresh or
    above, then grown by area × unclip_ratio / perimeter on each side. The box is grown as a
    rectangle, not as the blob's polygon. Quads are clipped to the map, corners bottom-left,
    top-left, top-right, bottom-right (OpenCV's TextDetectionModel order)."""
    h, w = prob.shape
    contours, _ = cv2.findContours((prob > config["thresh"]).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    quads, scores = [], []
    for contour in contours[:config["max_candidates"]]:
        (cx, cy), (rw, rh), angle = cv2.minAreaRect(contour)
        if min(rw, rh) < DB_MIN_SIDE:
            continue
        mask = np.zeros((h, w), np.uint8)
        cv2.fillPoly(mask, [np.round(cv2.boxPoints(((cx, cy), (rw, rh), angle))).astype(np.int32)], 1)
        score = float(cv2.mean(prob, mask)[0])
        if score < config["box_thresh"]:
            continue
        grow = rw * rh * config["unclip_ratio"] / (2 * (rw + rh))
        if min(rw, rh) + 2 * grow < DB_MIN_SIDE + 2:
            continue
        points = np.clip(cv2.boxPoints(((cx, cy), (rw + 2 * grow, rh + 2 * grow), angle)), 0, [w - 1, h - 1])
        by_x = points[np.argsort(points[:, 0], kind="stable")]
        top_left, bottom_left = by_x[:2][np.argsort(by_x[:2, 1], kind="stable")]
        top_right, bottom_right = by_x[2:][np.argsort(by_x[2:, 1], kind="stable")]
        quads.append(np.array([bottom_left, top_left, top_right, bottom_right], np.float32))
        scores.append(score)
    return quads, scores


def _onnx_session(path: str):
    """(onnxruntime session on one thread, its input name)."""
    import onnxruntime as ort
    ort.set_default_logger_severity(3)  # errors only: the model-load warnings flood the run log
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1  # the worker pool supplies the parallelism
    with open(path, "rb") as f:  # bytes, so a non-ASCII path can't trip a narrow-path API
        session = ort.InferenceSession(f.read(), opts, providers=["CPUExecutionProvider"])
    return session, session.get_inputs()[0].name


class PaddleDetector:
    """A PaddleOCR DB text detector (e.g. PP-OCRv6_small_det) on onnxruntime, with its yml's settings."""
    name = "PaddleOCR"

    def __init__(self, det_path: str, yml_path: str):
        self.config = paddle_det_config(yml_path)
        self.session, self.input = _onnx_session(det_path)

    def detect(self, bgr: np.ndarray) -> tuple:
        x = ((bgr.astype(np.float32) / 255.0 - self.config["mean"]) / self.config["std"]).transpose(2, 0, 1)
        return db_boxes(self.session.run(None, {self.input: x[np.newaxis]})[0][0, 0], self.config)


def text_detector(det_path: str):
    """PaddleDetector when <model>.yml sits beside the model, else opencv_zoo's PP-OCRv3 DB through
    OpenCV. Either gives detect(bgr letterbox) → (quads, scores)."""
    yml_path = paddle_dict_path(det_path)
    if os.path.isfile(yml_path):
        return PaddleDetector(det_path, yml_path)
    det = cv2.dnn_TextDetectionModel_DB(read_onnx(det_path))
    det.setBinaryThreshold(0.3)
    det.setPolygonThreshold(0.5)
    det.setMaxCandidates(200)
    det.setUnclipRatio(2.0)
    det.setInputParams(1.0 / 255.0, (DET_INPUT, DET_INPUT), DET_MEAN)
    return det


class CrnnRecogniser:
    """opencv_zoo's CRNN: grey 100 × 32, digits and lowercase letters."""
    name = "CRNN"

    def __init__(self, rec_path: str):
        self.net = read_onnx(rec_path)

    def read_word(self, bgr: np.ndarray, quad) -> tuple:
        word = _resized(quad_word(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), quad), REC_INPUT)
        self.net.setInput(cv2.dnn.blobFromImage(word, 1 / 127.5, REC_INPUT, 127.5))
        out = self.net.forward()
        return (*_ctc_greedy(out), digit_matrix(out))


class PaddleRecogniser:
    """A PaddleOCR recogniser (e.g. en_PP-OCRv5_mobile_rec) on onnxruntime: colour, height 48."""
    name = "PaddleOCR"

    def __init__(self, rec_path: str, dict_path: str):
        self.session, self.input = _onnx_session(rec_path)
        # one blank word gives the class count, so a dictionary that doesn't fit fails at load
        blank = np.zeros((1, 3, PADDLE_REC_HEIGHT, PADDLE_REC_MIN_WIDTH), np.float32)
        self.charset = paddle_charset(dict_path, self.session.run(None, {self.input: blank})[0].shape[-1])

    def read_word(self, bgr: np.ndarray, quad) -> tuple:
        out = self.session.run(None, {self.input: paddle_rec_input(quad_word(bgr, quad))})[0][0]
        return (*_ctc_greedy(out, self.charset), digit_matrix(out, self.charset))


def recogniser(rec_path: str):
    """PaddleRecogniser when <model>.yml sits beside the model, else CrnnRecogniser."""
    dict_path = paddle_dict_path(rec_path)
    return PaddleRecogniser(rec_path, dict_path) if os.path.isfile(dict_path) else CrnnRecogniser(rec_path)


def drop_reason(region: dict, min_score: float = OCR_MIN_SCORE, min_height: float = NUMBER_MIN_HEIGHT) -> str:
    """Why a text region (NumberReader.last_regions) gives no number: "score" (detection under
    min_score), "not_digits" (no digit_runs) or "height" (under min_height of the crop), first
    failing first; "" when it passes."""
    if region["det"] < min_score:
        return "score"
    if not digit_runs(region["text"]):
        return "not_digits"
    if region["share"] < min_height:
        return "height"
    return ""


def pick_reads(regions: list, min_score: float = OCR_MIN_SCORE, min_height: float = NUMBER_MIN_HEIGHT) -> tuple:
    """([(digits, confidence)] most confident first, {digits: digit matrix}) from text regions
    (NumberReader.last_regions): each distinct number's best passing region, confidence the lower of
    detection and read. A region with several digit runs gives each one, all with its whole matrix.
    Shared by NumberReader.read and eval_numbers' replay, so both decide alike."""
    best, ctc = {}, {}
    for region in regions:
        if drop_reason(region, min_score, min_height):
            continue
        both = min(region["det"], region["rec"])
        for digits in digit_runs(region["text"]):
            if both > best.get(digits, -1.0):
                best[digits] = both
                ctc[digits] = region["matrix"]
    return sorted(best.items(), key=lambda kv: kv[1], reverse=True), ctc


class NumberReader:
    def __init__(self, det_path: str, rec_path: str, keep_regions: bool = False):
        self.last_trace: list = []
        self.last_ctc: dict = {}
        self.last_turns: dict = {}
        self.keep_regions = keep_regions  # --verify: last_regions holds every region, for eval_numbers
        self.last_regions: list = []
        for label, p in (("OCR text detection", det_path), ("OCR text recognition", rec_path)):
            if not os.path.isfile(p):
                raise FileNotFoundError(f"{label} model not found: {p}")
        self.det = text_detector(det_path)
        self.rec = recogniser(rec_path)

    def read(self, crop_rgb: np.ndarray) -> list:
        """[(digits, confidence)], distinct numbers, most confident first, for text regions detected at
        OCR_MIN_SCORE or above and at least NUMBER_MIN_HEIGHT of the crop's height. Confidence is the
        lower of the detection score and the recogniser's read confidence: a plate can look very like
        text and still be read unsurely. Text is found on the crop's DET_INPUT letterbox and each
        quad is read from the crop itself (read_turned), so a crop up to OCR_CROP_DIM keeps its detail.
        Also sets `last_trace`: the five most confident detected text
        regions as [confidence, raw text, height share], accepted or not, so a zero-read crop shows
        what the reader saw, `last_ctc`: each returned number's digit_matrix from its best region,
        and `last_turns`: {"90" | "180" | "270": regions whose turned read won}.
        With keep_regions, `last_regions` holds every detected region as {det, rec, text, share,
        matrix, dropped} (drop_reason at today's thresholds), else []."""
        h, w = crop_rgb.shape[:2]
        src = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2BGR)
        quads, confidences = self.det.detect(cv2.cvtColor(_letterbox(crop_rgb, DET_INPUT), cv2.COLOR_RGB2BGR))
        back = max(h, w) / DET_INPUT  # letterbox pixels → crop pixels; the letterbox keeps the crop top-left
        regions, trace, turns = [], [], {}
        for quad, conf in zip(quads, confidences):
            text, read_conf, matrix, turn = read_turned(self.rec.read_word, src, np.asarray(quad, np.float32).reshape(4, 2) * back)
            if turn:
                turns[str(turn)] = turns.get(str(turn), 0) + 1
            share = height_share(quad, h, w)
            trace.append([min(float(conf), read_conf), text, round(share, 3)])
            regions.append({"det": float(conf), "rec": float(read_conf), "text": text, "share": float(share), "matrix": matrix})
        reads, ctc = pick_reads(regions)
        self.last_trace = sorted(trace, reverse=True)[:5]
        self.last_ctc = ctc
        self.last_turns = turns
        self.last_regions = [dict(r, dropped=drop_reason(r)) for r in regions] if self.keep_regions else []
        return reads


def read_turned(read_word, bgr: np.ndarray, quad) -> tuple:
    """(text, read confidence, digit matrix, turn) for a quad (bottom-left, top-left, top-right,
    bottom-right): read as found and, when that read is under TURN_RETRY_BELOW, again turned 180°,
    and 90° and 270° when the quad is TALL_QUAD or taller. Turning rolls the corner order, so the
    word warps upright for a number upside down or on its side. The most confident read wins, the
    one as found on a tie; turn is 0, 90, 180 or 270 (corners rolled 1, 2 or 3 places)."""
    q = np.asarray(quad, np.float32).reshape(4, 2)
    best = (*read_word(bgr, q), 0)
    if best[1] >= TURN_RETRY_BELOW:
        return best
    w, h = _quad_size(q)
    for rolls in ((2, 1, 3) if h >= TALL_QUAD * w else (2,)):
        read = (*read_word(bgr, np.roll(q, -rolls, axis=0)), 90 * rolls)
        if read[1] > best[1]:
            best = read
    return best

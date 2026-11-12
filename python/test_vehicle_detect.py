# Run with: python python/run_tests.py vehicle_detect
# Exercises vehicle_detect.py with a fake detector family: numpy and sqlite only, no ONNX file,
# no cv2.dnn call, no onnxruntime import.

import os
import sqlite3
import sys
import tempfile
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vehicle_detect as V  # noqa: E402

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


class FakeDetector:
    id = "fake:x:1:abc"
    family = "fake"
    net = None
    classes = frozenset({2, 3, 7})


FAKE_OUT: list = []  # rows [x0, y0, x1, y1, score, cls] in source pixels the fake run returns
RUNS = []


def fake_run(detector, canvas, scale, w, h):
    RUNS.append((canvas.shape, scale, w, h))
    return np.array(FAKE_OUT, dtype=np.float64).reshape(-1, 6)


V.FAMILIES["fake"] = {"match": lambda name: False, "load": None, "run": fake_run,
                      "classes": frozenset({2, 3, 7}), "nms": True}
det = FakeDetector()

# detection_key ---------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    frame = os.path.join(d, "a.jpg")
    with open(frame, "wb") as f:
        f.write(b"x")
    k1 = V.detection_key(frame, det)
    check("detection_key is stable", V.detection_key(frame, det), k1)
    check("detection_key carries the detector id", "fake:x:1:abc" in k1, True)
    saved = V.DETECT_VERSION
    V.DETECT_VERSION = saved + 1
    check("detection_key changes with DETECT_VERSION", V.detection_key(frame, det) != k1, True)
    V.DETECT_VERSION = saved
    check("detection_key restored", V.detection_key(frame, det), k1)

# DetectionCache --------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "sub", "detections.sqlite")
    c = V.DetectionCache(p)
    check("cache creates the parent folder", os.path.isdir(os.path.join(d, "sub")), True)
    entry = {"frame": [10, 5], "detector": det.id, "boxes": [[1.0, 2.0, 3.0, 4.0, 0.9, 2]]}
    check("cache miss is None", c.get("k"), None)
    c.put(entry, "k")
    check("cache round-trips an entry", c.get("k"), entry)
    c.close()
    db = sqlite3.connect(p)
    db.execute("UPDATE detections SET used = ? WHERE key = 'k'", (int(time.time()) - 91 * 86400,))
    db.commit()
    db.close()
    c = V.DetectionCache(p)
    c.prune(days=90)
    check("prune drops a row unused for 90 days", c.get("k"), None)
    c.close()
    bad = os.path.join(d, "bad.sqlite")
    with open(bad, "wb") as f:
        f.write(b"not a database")
    try:
        V.DetectionCache(bad)
        check("non-sqlite file raises InputError", "no error", "InputError")
    except V.InputError as e:
        check("non-sqlite file raises InputError naming the path", bad in str(e), True)
    disabled = V.DetectionCache("")
    disabled.put(entry, "k")
    check("empty path disables the cache", disabled.get("k"), None)

# detect ----------------------------------------------------------------------
rgb = np.zeros((500, 1000, 3), np.uint8)
FAKE_OUT[:] = [[100, 100, 300, 300, 0.9, 2], [110, 110, 310, 310, 0.5, 2], [500, 100, 600, 200, 0.02, 2]]
RUNS.clear()
e = V.detect(rgb, det)
check("detect stores the frame size", e["frame"], [1000, 500])
check("detect stores the detector id", e["detector"], det.id)
check("detect keeps one NMS survivor above CANDIDATE_MIN_SCORE", e["boxes"], [[100.0, 100.0, 300.0, 300.0, 0.9, 2]])
check("detect letterboxes to DETECTOR_INPUT", RUNS[0][0], (V.DETECTOR_INPUT, V.DETECTOR_INPUT, 3))
check("detect passes the letterbox scale", RUNS[0][1], V.DETECTOR_INPUT / 1000)

FAKE_OUT[:] = [[0, 0, 100, 100, 0.9, 2], [5, 5, 105, 105, 0.5, 2],
               [300, 300, 400, 400, 0.4, 7], [305, 305, 405, 405, 0.3, 7], [600, 0, 650, 50, 0.2, 3]]
full = V.detect(rgb, det)["boxes"]
check("detect sorts score descending", [b[4] for b in full], sorted((b[4] for b in full), reverse=True))
at_35 = [b for b in full if b[4] >= 0.35]
subset = V.nms([b for b in FAKE_OUT if b[4] >= 0.35], V.DETECTOR_NMS)
check("NMS over the 0.03 set filtered at 0.35 equals NMS over the 0.35 set",
      [[float(v) for v in b[:5]] + [int(b[5])] for b in at_35],
      [[float(v) for v in b[:5]] + [int(b[5])] for b in subset])

# boxes_in --------------------------------------------------------------------
check("boxes_in rescales from the stored frame",
      V.boxes_in({"frame": [2000, 1000], "boxes": [[200, 100, 400, 300, 0.9, 2]]}, 1000, 500),
      [[100.0, 50.0, 200.0, 150.0, 0.9, 2]])

# detect_cached ---------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    frame = os.path.join(d, "corrupt.jpg")
    with open(frame, "wb") as f:
        f.write(b"x")
    cache = V.DetectionCache(os.path.join(d, "detections.sqlite"))
    saved_decode = V.decode_rgb

    def bad_decode(path, fast_jpeg=False):
        raise OSError("cannot identify image file")

    V.decode_rgb = bad_decode
    try:
        V.detect_cached(frame, det, cache)
        check("detect_cached raises on decode failure", "no error", "OSError")
    except OSError:
        check("detect_cached raises on decode failure", True, True)
    V.decode_rgb = saved_decode
    check("decode failure writes nothing", cache.get(V.detection_key(frame, det)), None)
    FAKE_OUT[:] = [[10, 10, 20, 20, 0.7, 2]]
    RUNS.clear()
    e1, hit1 = V.detect_cached(frame, det, cache, rgb=rgb)
    e2, hit2 = V.detect_cached(frame, det, cache, rgb=rgb)
    check("detect_cached misses then hits", (hit1, hit2), (False, True))
    check("detect_cached runs the detector once", len(RUNS), 1)
    check("detect_cached returns the stored entry on a hit", e2, e1)
    cache.close()

# load_detector ---------------------------------------------------------------
try:
    V.load_detector("missing.onnx")
    check("load_detector on a missing file raises InputError", "no error", "InputError")
except V.InputError as e:
    check("load_detector on a missing file names it", "missing.onnx" in str(e), True)
with tempfile.TemporaryDirectory() as d:
    unknown = os.path.join(d, "mystery.onnx")
    with open(unknown, "wb") as f:
        f.write(b"\x00")
    try:
        V.load_detector(unknown)
        check("load_detector with no family match raises InputError", "no error", "InputError")
    except V.InputError as e:
        check("load_detector with no family match names the file", "mystery.onnx" in str(e), True)
check("yolox family matches the opencv_zoo name", V.FAMILIES["yolox"]["match"]("object_detection_yolox_2022nov.onnx"), True)
check("detr family matches a D-FINE export", V.FAMILIES["detr"]["match"]("dfine_s_coco.onnx"), True)
check("detr family matches an RT-DETR export", V.FAMILIES["detr"]["match"]("rtdetrv2_s.onnx"), True)
check("yolox family does not match a D-FINE export", V.FAMILIES["yolox"]["match"]("dfine_s_coco.onnx"), False)


# detr post-processing on a stub session -------------------------------------
class _Named:
    def __init__(self, name):
        self.name = name


class StubSession:
    def get_inputs(self):
        return [_Named("images"), _Named("orig_target_sizes")]

    def get_outputs(self):
        return [_Named("labels"), _Named("boxes"), _Named("scores")]

    def run(self, names, feeds):
        self.feeds = feeds
        return [np.array([[2, 0]]), np.array([[[10, 10, 50, 50], [0, 0, 5, 5]]], np.float32), np.array([[0.8, 0.9]], np.float32)]


stub = StubSession()
detr = V.Detector(id="detr:dfine_s_coco.onnx:1:abc", family="detr", net=stub, classes=V.FAMILIES["detr"]["classes"])
e = V.detect(np.zeros((640, 640, 3), np.uint8), detr)
check("detr keeps the vehicle box and drops the person", e["boxes"], [[10.0, 10.0, 50.0, 50.0, 0.8, 2]])
check("detr feeds images and orig_target_sizes", sorted(stub.feeds), ["images", "orig_target_sizes"])
check("detr images input is 1x3x640x640", tuple(stub.feeds["images"].shape), (1, 3, 640, 640))


class RawStubSession:
    # transformers export (onnx-community/dfine_*-ONNX): no post-processor, 300 queries × 80 logits
    # and normalised cx,cy,w,h boxes.
    def get_inputs(self):
        return [_Named("pixel_values")]

    def get_outputs(self):
        return [_Named("logits"), _Named("pred_boxes")]

    def run(self, names, feeds):
        self.feeds = feeds
        logits = np.full((1, 2, 80), -20.0, np.float32)
        logits[0, 0, 2] = 0.0    # query 0: car at sigmoid(0) = 0.5
        logits[0, 0, 0] = 3.0    # ... and a stronger person score that must not win
        logits[0, 1, 7] = -5.0   # query 1: truck below CANDIDATE_MIN_SCORE
        boxes = np.array([[[0.25, 0.25, 0.5, 0.5], [0.5, 0.5, 0.1, 0.1]]], np.float32)
        return [logits, boxes]


raw = RawStubSession()
e = V.detect(np.zeros((320, 640, 3), np.uint8), V.Detector(id="detr:dfine_s_coco.onnx:1:abc", family="detr", net=raw,
                                                           classes=V.FAMILIES["detr"]["classes"]))
check("detr raw export: feeds pixel_values only", sorted(raw.feeds), ["pixel_values"])
check("detr raw export: sigmoid over vehicle classes, cxcywh × canvas / scale → source xyxy",
      e["boxes"], [[0.0, 0.0, 320.0, 320.0, 0.5, 2]])

# fingerprint -----------------------------------------------------------------
check("detection_fingerprint is 12 hex", len(V.detection_fingerprint()), 12)

print("all tests passed" if not failures else f"{failures} FAILED")
sys.exit(1 if failures else 0)

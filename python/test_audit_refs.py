# Run with: python python/test_audit_refs.py
# Exercises audit_refs.frame_audit with a fake detector model; no models needed.

import json
import os
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vehicle_detect
from audit_refs import FRAME_CACHE_NAME, AuditCancelled, _file_stamp, frame_audit
from vehicles import DETECTOR_MIN_SCORE

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


class FakeDetector:
    id = "fake"


detect_calls = []


def fake_detect(rgb, detector):
    """One car filling the whole frame, standing in for the ONNX model."""
    detect_calls.append(rgb.shape)
    h, w = rgb.shape[:2]
    return {"frame": [w, h], "detector": detector.id, "boxes": [[0.0, 0.0, float(w), float(h), 0.95, 2]]}


vehicle_detect.load_detector = lambda path: FakeDetector()  # the model files are the edge
vehicle_detect.detect = fake_detect


def collection(names):
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "refs", "7"))
    for n in names:
        Image.fromarray(np.full((40, 60, 3), 128, np.uint8)).save(os.path.join(d, "refs", "7", n))
    return d


def seed_cache(d, rels):
    refs = {r: {"stamp": _file_stamp(os.path.join(d, *r.split("/"))), "share": 0.5, "boxes": [[0, 0, 1, 1]]}
            for r in rels}
    with open(os.path.join(d, FRAME_CACHE_NAME), "w", encoding="utf-8") as f:
        json.dump({"detector": f"fake:{DETECTOR_MIN_SCORE}", "refs": refs}, f)


# A new ref listed before two already-checked ones: the checked ones are counted up front, so
# progress runs over the refs still to detect and the ETA isn't set by the instant cache hits.
d = collection(["1.jpg", "2.jpg", "3.jpg"])
path = ["refs/7/1.jpg", "refs/7/2.jpg", "refs/7/3.jpg"]
seed_cache(d, path[1:])
ticks = []
shares, boxes = frame_audit(d, path, "fake.onnx", on_progress=lambda *a: ticks.append(a) or True)
check("progress: cached refs counted before any detection", ticks, [(2, 3, 2)])
check("progress: only the new ref is detected", len(detect_calls), 1)
check("shares stay aligned with path", shares, [1.0, 0.5, 0.5])
check("boxes stay aligned with path", boxes[1:], [[[0, 0, 1, 1]], [[0, 0, 1, 1]]])

# Every ref cached: nothing to detect, one tick saying all are done.
detect_calls.clear()
ticks = []
frame_audit(d, path, "fake.onnx", on_progress=lambda *a: ticks.append(a) or True)
check("progress: all cached gives one done tick", ticks, [(3, 3, 3)])
check("progress: all cached detects nothing", len(detect_calls), 0)

# Cancelling still stops the run and keeps what was found.
d = collection(["1.jpg", "2.jpg"])
try:
    frame_audit(d, ["refs/7/1.jpg", "refs/7/2.jpg"], "fake.onnx", on_progress=lambda *a: False)
    check("cancel raises AuditCancelled", "no raise", "raised")
except AuditCancelled:
    check("cancel raises AuditCancelled", "raised", "raised")

if failures:
    print(f"{failures} test(s) failed")
    sys.exit(1)
print("all tests passed")

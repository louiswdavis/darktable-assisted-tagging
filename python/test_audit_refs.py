# Run with: python python/test_audit_refs.py
# Exercises audit_refs.frame_audit with a fake onnxruntime; no models needed.

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


detect_calls = []
session_threads = []


# onnxruntime is the edge: a fake D-FINE session that finds one car filling the image's part of
# the letterboxed canvas. load_detector, detect and the share maths all run for real.
class FakeSession:
    def __init__(self, model_bytes, sess_options, providers):
        session_threads.append(sess_options.intra_op_num_threads)

    def get_inputs(self):
        return [type("Input", (), {"name": "images"})]

    def get_outputs(self):
        return [type("Output", (), {"name": n}) for n in ("labels", "boxes", "scores")]

    def run(self, outputs, feeds):
        detect_calls.append(feeds["images"].shape)
        ys, xs = np.nonzero(np.abs(feeds["images"][0, 0] - 114 / 255) > 1e-3)
        box = [xs.min(), ys.min(), xs.max() + 1, ys.max() + 1]
        return [np.array([[2]]), np.array([[box]], np.float64), np.array([[0.95]])]


fake_ort = type(sys)("onnxruntime")
fake_ort.SessionOptions = lambda: type("Options", (), {})()
fake_ort.InferenceSession = FakeSession
sys.modules["onnxruntime"] = fake_ort
model = os.path.join(tempfile.mkdtemp(), "dfine_fake.onnx")
with open(model, "wb") as f:
    f.write(b"fake detector")
detector_id = vehicle_detect.load_detector(model).id
check("Identify's load: one thread, its worker pool supplies the parallelism", session_threads, [1])
session_threads.clear()


def collection(names):
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "refs", "7"))
    for n in names:  # 64×40 scales by exactly 10 onto the 640 canvas, so the car's share is exactly 1
        Image.fromarray(np.full((40, 64, 3), 128, np.uint8)).save(os.path.join(d, "refs", "7", n))
    return d


def seed_cache(d, rels):
    refs = {r: {"stamp": _file_stamp(os.path.join(d, *r.split("/"))), "share": 0.5, "boxes": [[0, 0, 1, 1]]}
            for r in rels}
    with open(os.path.join(d, FRAME_CACHE_NAME), "w", encoding="utf-8") as f:
        json.dump({"detector": f"{detector_id}:{DETECTOR_MIN_SCORE}", "refs": refs}, f)


# A new ref listed before two already-checked ones: the checked ones are counted up front, so
# progress runs over the refs still to detect and the ETA isn't set by the instant cache hits.
d = collection(["1.jpg", "2.jpg", "3.jpg"])
path = ["refs/7/1.jpg", "refs/7/2.jpg", "refs/7/3.jpg"]
seed_cache(d, path[1:])
ticks = []
shares, boxes = frame_audit(d, path, model, on_progress=lambda *a: ticks.append(a) or True)
check("audit's load: every core (onnxruntime 0), nothing else detects alongside it", session_threads, [0])
check("progress: cached refs counted before any detection", ticks, [(2, 3, 2)])
check("progress: only the new ref is detected", len(detect_calls), 1)
check("shares stay aligned with path", shares, [1.0, 0.5, 0.5])
check("boxes stay aligned with path", boxes[1:], [[[0, 0, 1, 1]], [[0, 0, 1, 1]]])

# Every ref cached: nothing to detect, one tick saying all are done.
detect_calls.clear()
ticks = []
frame_audit(d, path, model, on_progress=lambda *a: ticks.append(a) or True)
check("progress: all cached gives one done tick", ticks, [(3, 3, 3)])
check("progress: all cached detects nothing", len(detect_calls), 0)

# Cancelling still stops the run and keeps what was found.
d = collection(["1.jpg", "2.jpg"])
try:
    frame_audit(d, ["refs/7/1.jpg", "refs/7/2.jpg"], model, on_progress=lambda *a: False)
    check("cancel raises AuditCancelled", "no raise", "raised")
except AuditCancelled:
    check("cancel raises AuditCancelled", "raised", "raised")

if failures:
    print(f"{failures} test(s) failed")
    sys.exit(1)
print("all tests passed")

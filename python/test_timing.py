# Run with: python python/test_timing.py
# Exercises timing.py with a fake session at the edge; stdlib only.

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timing

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


class FakeSession:
    def run(self, names, feeds):
        time.sleep(0.01)
        return ["out"]

    def get_inputs(self):
        return ["input"]


class BrokenSession:
    def run(self, names, feeds):
        raise RuntimeError("boom")


session = timing.timed(FakeSession(), "/models/PP-OCRv5_server_rec.onnx")
check("run returns the session's output", session.run(None, {}), ["out"])
check("other attributes are forwarded", session.get_inputs(), ["input"])
session.run(None, {})
taken = timing.take()
check("calls counted under the file name", {k: v[0] for k, v in taken.items()}, {"PP-OCRv5_server_rec.onnx": 2})
check("seconds counted", 0.02 <= taken["PP-OCRv5_server_rec.onnx"][1] < 1.0, True)
check("take clears the totals", timing.take(), {})
check("report is empty with nothing run", timing.report(), "")

try:
    timing.timed(BrokenSession(), "b.onnx").run(None, {})
except RuntimeError:
    pass
check("a failing run is still counted and still raises", timing.take()["b.onnx"][0], 1)

timing.merge({"a.onnx": [3, 3.0], "b.onnx": [1, 5.0]})
timing.merge({"a.onnx": [1, 1.0]})
timing.merge(None)
check("merge adds worker totals", timing.take(), {"a.onnx": [4, 4.0], "b.onnx": [1, 5.0]})

timing.merge({"a.onnx": [4, 4.0], "b.onnx": [1, 5.0]})
check("report lists the slowest model first",
      timing.report("t"), "t: b.onnx 5s (1 calls, 5000 ms each); a.onnx 4s (4 calls, 1000 ms each)")

print("")
if failures == 0:
    print("all tests passed")
    sys.exit(0)
print(f"{failures} test(s) failed")
sys.exit(1)

# Run with: python python/run_tests.py compare_detectors
# Exercises the pure helpers of compare_detectors.py: no model files, no decode.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare_detectors as CD  # noqa: E402

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


def box(score):
    return [0, 0, 10, 10, score, 2]


ROWS = [
    {"frame": "a.jpg", "detector": "A", "ms": 10.0, "boxes": [box(0.9), box(0.3)], "truth": True},
    {"frame": "b.jpg", "detector": "A", "ms": 30.0, "boxes": [box(0.25)], "truth": True},
    {"frame": "c.jpg", "detector": "A", "ms": 20.0, "boxes": [], "truth": False},
    {"frame": "a.jpg", "detector": "B", "ms": 40.0, "boxes": [box(0.6)], "truth": True},
    {"frame": "b.jpg", "detector": "B", "ms": 40.0, "boxes": [box(0.6)], "truth": True},
    {"frame": "c.jpg", "detector": "B", "ms": 40.0, "boxes": [box(0.4)], "truth": False},
]

# summarise -------------------------------------------------------------------
rows = CD.summarise(ROWS, thresholds=(0.20, 0.35))
check("summarise: one row per detector per threshold", [(r["detector"], r["threshold"]) for r in rows],
      [("A", 0.20), ("A", 0.35), ("B", 0.20), ("B", 0.35)])
a20, a35, b20, b35 = rows
check("summarise: frames counted once per detector", a20["frames"], 3)
check("summarise: frames_with_car at 0.20", a20["frames_with_car"], 2)
check("summarise: frames_with_car at 0.35 drops the 0.25 box", a35["frames_with_car"], 1)
check("summarise: boxes at 0.20", a20["boxes"], 3)
check("summarise: boxes_per_frame rounded", a20["boxes_per_frame"], 1.0)
check("summarise: missed_cars = truth frames with no box at threshold", a35["missed_cars"], 1)
check("summarise: no missed cars when every truth frame has a box", b35["missed_cars"], 0)
check("summarise: truth False frames never count as missed", b20["missed_cars"], 0)
check("summarise: ms_mean over all frames", a20["ms_mean"], 20.0)
check("summarise: ms_p90 nearest-rank", a20["ms_p90"], 30.0)
check("summarise: ms is independent of threshold", a35["ms_mean"], 20.0)
check("summarise: default thresholds", [r["threshold"] for r in CD.summarise(ROWS[:1])], [0.20, 0.35, 0.50])
check("summarise: missed_cars None when no row has truth",
      CD.summarise([dict(ROWS[0], truth=None)])[0]["missed_cars"], None)

# disagreements ---------------------------------------------------------------
dis = CD.disagreements(ROWS, threshold=0.35)
check("disagreements: frames whose box counts differ, sorted by frame", [d["frame"] for d in dis], ["b.jpg", "c.jpg"])
check("disagreements: counts per detector id", dis[0]["counts"], {"A": 0, "B": 1})
check("disagreements: empty when every frame agrees", CD.disagreements([ROWS[0], ROWS[3]], threshold=0.35), [])

# truth -----------------------------------------------------------------------
truth = CD.read_truth(
    [{"id": "1", "box": "0"}, {"id": "1", "box": "1"}, {"id": "2", "box": "-1"}],
    [{"id": "1", "filepath": "C:/p/a.jpg"}, {"id": "2", "filepath": "C:/p/c.jpg"}, {"id": "3", "filepath": "C:/p/d.jpg"}])
check("read_truth: path → has vehicle, via manifest ids", truth, {"C:/p/a.jpg": True, "C:/p/c.jpg": False})

print("all tests passed" if not failures else f"{failures} FAILED")
sys.exit(1 if failures else 0)

# Run with: python python/test_pod.py
# Exercises pod.pod_colour; pod_reading needs numpy and OpenCV, so it is checked on real frames.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pod as P

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


check("yellow share over the line is yellow", P.pod_colour({"yellow": 0.05, "aspect": 1.0}), "yellow")
check("no yellow on a side-on car is black", P.pod_colour({"yellow": 0.0, "aspect": 3.0}), "black")
check("no yellow on a head-on car is unclear", P.pod_colour({"yellow": 0.0, "aspect": 1.0}), "")
check("a trace of yellow is unclear", P.pod_colour({"yellow": 0.0007, "aspect": 3.0}), "")
check("no reading is unclear", P.pod_colour({}), "")

if failures:
    print(f"{failures} test(s) failed")
    sys.exit(1)
print("\nall tests passed")

# Run with: python python/test_car_colour.py
# Exercises car_colour on synthetic crops (needs numpy and OpenCV) and its pure decision functions.

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import car_colour as C
from segment import GREY

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


def fill(rgb, h=200, w=300):
    crop = np.zeros((h, w, 3), dtype=np.uint8)
    crop[:] = rgb
    return crop


def colour_of(crop, masked=False):
    return C.decide_colour(C.colour_shares(crop, masked=masked))


RED, WHITE = (200, 0, 0), (255, 255, 255)

check("solid red is Red", colour_of(fill(RED)), "Red")

patched = fill(RED)
patched[:, :45] = WHITE  # 15% of the width
check("red with 15% white is Red", colour_of(patched), "Red")

split = fill(RED)
split[:, 165:] = WHITE  # 55% red, 45% white
check("55/45 red and white is Multi", colour_of(split), "Multi")

check("mud grey is no colour", colour_of(fill((128, 120, 110))), "")
check("silver is White", colour_of(fill((200, 200, 205))), "White")
check("dark navy is Blue or Black", colour_of(fill((20, 25, 70))) in ("Blue", "Black"), True)  # Task 8 pins it

halved = fill(RED)
halved[:, :150] = GREY
check("half grey, half red, masked is Red", colour_of(halved, masked=True), "Red")
check("half grey, half red, unmasked is no colour", colour_of(halved, masked=False), "")

check("sole colour with a minor second", C.decide_colour({"Red": 0.61, "White": 0.29}), "Red")
check("sole-share colour with a part second is Multi", C.decide_colour({"Red": 0.61, "White": 0.31}), "Multi")
check("two parts reaching the sole share", C.decide_colour({"Red": 0.35, "White": 0.30}), "Multi")
check("three parts", C.decide_colour({"Red": 0.31, "White": 0.31, "Blue": 0.31}), "")
check("no shares", C.decide_colour({}), "")

check("same colour agrees", C.colour_relation("Red", "Red"), 1)
check("different colours disagree", C.colour_relation("Red", "Blue"), -1)
check("empty entry is neutral", C.colour_relation("", "Red"), 0)
check("empty seen is neutral", C.colour_relation("Red", ""), 0)
check("Multi entry vs a colour disagrees", C.colour_relation("Multi", "Red"), -1)
check("Multi agrees with Multi", C.colour_relation("Multi", "Multi"), 1)

check("digest is stable", C.palette_digest(C.PALETTE) == C.palette_digest(C.PALETTE), True)
name, ranges = C.PALETTE[0]
tweaked = ((name, ((ranges[0][0] + 1,) + tuple(ranges[0][1:]),) + tuple(ranges[1:])),) + tuple(C.PALETTE[1:])
check("digest changes with a bound", C.palette_digest(C.PALETTE) != C.palette_digest(tweaked), True)
renamed = (("Crimson", ranges),) + tuple(C.PALETTE[1:])
check("digest changes with a name", C.palette_digest(C.PALETTE) != C.palette_digest(renamed), True)

if failures:
    print(f"{failures} test(s) failed")
    sys.exit(1)
print("\nall tests passed")

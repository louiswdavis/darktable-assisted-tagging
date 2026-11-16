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
check("55/45 red and white is Red", colour_of(split), "Red")  # white counts half

check("mud grey is Grey", colour_of(fill((128, 120, 110))), "Grey")
check("silver is Grey", colour_of(fill((150, 150, 155))), "Grey")
check("bright silver is White", colour_of(fill((200, 200, 205))), "White")
check("dark navy is Blue", colour_of(fill((20, 25, 70))), "Blue")
check("near black is Black", colour_of(fill((30, 20, 25))), "Black")
check("orange is Orange", colour_of(fill((255, 120, 0))), "Orange")
check("dark orange is Brown", colour_of(fill((120, 70, 20))), "Brown")
check("purple is Purple", colour_of(fill((130, 0, 200))), "Purple")
check("pink is Pink", colour_of(fill((255, 0, 150))), "Pink")

halved = fill(RED)
halved[:, :150] = GREY
check("half grey, half red, masked is Red", colour_of(halved, masked=True), "Red")
check("half grey, half red, unmasked is Red", colour_of(halved, masked=False), "Red")  # grey counts half

check("achromatic runner-up counts half", C.decide_colour({"Black": 0.6, "Red": 0.4}), "Multi")
check("a colour beats a smaller achromatic share", C.decide_colour({"Black": 0.3, "Red": 0.5}), "Red")
check("a mostly black car is Black", C.decide_colour({"Black": 0.9, "Red": 0.1}), "Black")
check("runner-up at the ratio is Multi", C.decide_colour({"Red": 0.5, "Blue": 0.3}), "Multi")
check("SigLIP scores: a white car is White, not weighted down", C.decide_colour({"White": 0.6, "Red": 0.39, "Multi": 0.01}), "White")
check("SigLIP scores: Multi wins only as the top prompt", C.decide_colour({"Red": 0.3, "Blue": 0.3, "Multi": 0.4}), "Multi")
check("runner-up under the ratio loses", C.decide_colour({"Red": 0.5, "Blue": 0.29}), "Red")
check("a tiny single share still decides", C.decide_colour({"Red": 0.001, "Blue": 0.0}), "Red")
check("all-zero shares", C.decide_colour({n: 0.0 for n, _ in C.PALETTE}), "")
check("no shares", C.decide_colour({}), "")


def test_palette_tiles_hsv():
    grid = np.stack(np.meshgrid(np.arange(180, dtype=np.uint8), np.arange(256, dtype=np.uint8),
                                np.arange(256, dtype=np.uint8), indexing="ij"), axis=-1)
    masks = C.assign(grid)
    check("one mask per palette row", len(masks), len(C.PALETTE))
    check("every HSV triple has exactly one colour", int(np.sum(masks, axis=0, dtype=np.uint8).min()), 1)
    check("no HSV triple has two colours", int(np.sum(masks, axis=0, dtype=np.uint8).max()), 1)
    for (name, _), hit in zip(C.PALETTE, masks):
        check(f"{name} takes some of the space", bool(hit.any()), True)


test_palette_tiles_hsv()
check("the palette has 11 names", [n for n, _ in C.PALETTE],
      ["Black", "White", "Grey", "Brown", "Red", "Orange", "Yellow", "Green", "Blue", "Purple", "Pink"])

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

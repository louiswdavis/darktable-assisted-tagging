# Run with: python python/test_overlap.py
# Exercises overlap.visible_boxes (pure geometry).

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import overlap as O

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


def states(boxes):
    return [s for _, s in O.visible_boxes(boxes)]


check("a lone box is visible", states([(0, 0, 100, 50)]), [""])
check("apart boxes are visible", states([(0, 0, 100, 50), (200, 0, 300, 50)]), ["", ""])

# level boxes: only the lower-scoring one is behind, so the pair never both lose the overlap
pair = O.visible_boxes([(0, 0, 100, 50, 0.4, 2), (80, 0, 200, 50, 0.7, 2)])
check("the weaker level box is trimmed", pair[0], ((0, 0, 80, 50, 0.4, 2), "trimmed"))
check("the stronger level box stays whole", pair[1], ((80, 0, 200, 50, 0.7, 2), ""))
check("with equal scores the earlier box stays whole",
      states([(0, 0, 100, 50), (80, 0, 200, 50)]), ["", "trimmed"])
check("two level boxes overlapping 63% hide only one",
      states([(318, 769, 518, 851, 0.21, 2), (280, 784, 445, 850, 0.38, 2)]), ["hidden", ""])

# a box 60% covered by a car in front of it is hidden
check("a mostly covered box is hidden", states([(0, 0, 100, 50), (40, 0, 200, 60)]), ["hidden", ""])

# a car whose bottom edge is well above the other is behind it and doesn't cut it
check("the box in front is not cut by one behind", states([(0, 20, 100, 80), (40, 0, 200, 50)])[0], "")

# a box inside another is a part of that car
check("a contained box is hidden", states([(0, 0, 200, 100), (50, 20, 120, 80)]), ["", "hidden"])

# a trimmed box keeps its extra fields
kept = O.visible_boxes([(0, 0, 100, 50, 0.7, 2), (80, 0, 200, 50, 0.6, 2)])[0][0]
check("trimmed box keeps score and class", kept[4:], (0.7, 2))

# a cut in the middle keeps the wider side
mid = O.visible_boxes([(0, 0, 100, 50), (55, 10, 75, 70)])[0]
check("a middle cut keeps the wider side", mid, ((0, 0, 55, 50), "trimmed"))

if failures:
    sys.exit(f"{failures} failed")
print("all tests passed")

# Run with: python python/test_match_people.py
# Exercises match_people.py's per-face and per-frame rules; no models or files needed.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import match_people as Mp
from match import BoxResult

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


def face(width, scores, min_sim=0.5, margin=0.05, min_px=48):
    r, status = Mp.match_face(0, width, scores, min_sim, margin, min_px)
    return r.method, r.entry_id, r.alt_entry_id, status


def run_tests():
    sims = [("A", 0.9), ("A", 0.8), ("A", 0.7), ("A", 0.1), ("B", 0.4), ("B", 0.2)]
    got = {e: round(s, 3) for e, s in Mp.entry_scores(sims)}
    check("entry_scores: top-3 mean ignores the fourth sim, two-reference entry uses both", got, {"A": 0.8, "B": 0.3})
    check("entry_scores: most similar first", [e for e, _ in Mp.entry_scores(sims)], ["A", "B"])
    check("entry_scores: no sims", Mp.entry_scores([]), [])

    check("width under min_face_px is too_small", face(47, [("A", 0.9)]), ("none", "", "", "too_small"))
    check("width equal to min_face_px is scored", face(48, [("A", 0.9)]), ("face", "A", "", "tagged"))
    check("no scores is unknown", face(100, []), ("none", "", "", "unknown"))
    check("best under min_sim is unknown", face(100, [("A", 0.49), ("B", 0.1)]), ("none", "", "", "unknown"))
    check("best equal to min_sim with room over the runner-up is tagged", face(100, [("A", 0.5), ("B", 0.1)]),
          ("face", "A", "", "tagged"))
    check("lead under margin is ambiguous", face(100, [("A", 0.80), ("B", 0.77)]), ("none", "", "B", "ambiguous"))
    check("lead equal to margin is tagged", face(100, [("A", 0.80), ("B", 0.75)]),
          ("face", "A", "", "tagged"))
    check("single entry needs only the floor", face(100, [("A", 0.6)]), ("face", "A", "", "tagged"))

    def pair(box, entry, conf, status="tagged"):
        method = "face" if status == "tagged" else "none"
        return BoxResult(box, method, entry if status == "tagged" else "", "", conf), status

    out = Mp.resolve_duplicates([pair(0, "A", 0.7), pair(1, "A", 0.9), pair(2, "B", 0.8)])
    check("duplicates: higher similarity keeps the entry",
          [(r.box, r.method, r.entry_id, s) for r, s in out],
          [(0, "none", "", "unknown"), (1, "face", "A", "tagged"), (2, "face", "B", "tagged")])
    others = [pair(0, "A", 0.7), pair(1, "", 0.3, "unknown"), pair(2, "", 0.0, "too_small")]
    check("duplicates: non-tagged faces are untouched", Mp.resolve_duplicates(others), others)
    tied = Mp.resolve_duplicates([pair(0, "A", 0.8), pair(1, "A", 0.8)])
    check("duplicates: a tie keeps the first face", [(r.box, r.method) for r, _ in tied], [(0, "face"), (1, "none")])

    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

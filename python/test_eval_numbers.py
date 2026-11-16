# Run with: python python/test_eval_numbers.py
# Exercises ocr.py's region filter (drop_reason, pick_reads) and eval_numbers' miss causes; no models or files needed.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_numbers as En
from match import Entry
from ocr import NUMBER_MIN_HEIGHT, OCR_MIN_SCORE, drop_reason, pick_reads

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


def region(text, det=0.95, rec=0.9, share=0.2):
    """A text region whose digit matrix is sure of its first three ASCII digits, one step each."""
    digits = "".join(ch for ch in text if ch.isascii() and ch.isdigit())[:3] or "0"
    matrix = [[0.99 if col == 1 + int(ch) else 0.001 for col in range(11)] for ch in digits]
    return {"det": det, "rec": rec, "text": text, "share": share, "matrix": matrix}


KNOBS = {"ocr_min_score": OCR_MIN_SCORE, "number_min_height": NUMBER_MIN_HEIGHT, "min_read": 0.85,
         "weak_read_min": 0.7, "number_list_margin": 2.3, "number_list_floor": 4.6}


def run_tests():
    check("drop: passes", drop_reason(region("14")), "")
    check("drop: detection under the floor", drop_reason(region("14", det=0.5)), "score")
    check("drop: letters", drop_reason(region("RED")), "not_digits")
    check("drop: too small", drop_reason(region("14", share=0.01)), "height")
    check("drop: score checked first", drop_reason(region("RED", det=0.5, share=0.01)), "score")
    check("drop: a lower floor lets it through", drop_reason(region("14", det=0.75), min_score=0.7), "")

    reads, ctc = pick_reads([region("14", det=0.9, rec=0.8), region("14", det=0.95, rec=0.95),
                             region("7", rec=0.6), region("RED"), region("22", det=0.5)])
    check("pick: best region per number, lower of det and rec, best first", reads, [("14", 0.95), ("7", 0.6)])
    check("pick: matrix of each read", sorted(ctc), ["14", "7"])
    check("pick: nothing passes", pick_reads([region("22", det=0.5)]), ([], {}))
    check("pick: a mixed-text region gives each digit run", pick_reads([region("14 RALLYE 2026"), region("#7")])[0],
          [("14", 0.9), ("7", 0.9)])
    check("drop: a year alone has no number", drop_reason(region("2026")), "not_digits")
    check("cause: a mixed region that read it is below min_read", En.cause("14", [], [region("14A")], KNOBS), "below min_read")

    check("cause: no region", En.cause("14", [], [], KNOBS), "no region")
    check("cause: recognised wrong", En.cause("14", [], [region("11")], KNOBS), "recognised wrong")
    check("cause: dropped with its reason", En.cause("14", [], [region("14", det=0.5)], KNOBS), "dropped: score")
    check("cause: passing region under min_read", En.cause("14", [], [region("14", rec=0.75)], KNOBS), "below min_read")
    check("cause: accepted read lost in matching", En.cause("14", [("14", 0.9)], [region("14")], KNOBS), "lost in matching")
    check("weak: right number between the two floors", En.weak_read("14", [region("14", rec=0.75)], KNOBS), True)
    check("weak: under WEAK_READ_MIN", En.weak_read("14", [region("14", rec=0.6)], KNOBS), False)

    entries = {"E14": Entry("E14", "14", "A", ("t|14",)), "E22": Entry("E22", "22", "B", ("t|22",))}
    box = {"box": 0, "hint": {}, "sims": [["E22", 0.5], ["E14", 0.4]],
           "ocr_regions": [region("14", det=0.75)]}
    check("replay: dropped region leaves the box unread", En.replay_box(box, entries, KNOBS)[0].method != "number", True)
    lower = dict(KNOBS, ocr_min_score=0.7, min_read=0.7)
    check("replay: OCR_MIN_SCORE=0.7 and min_read=0.7 read it", En.replay_box(box, entries, lower)[0].entry_id, "E14")
    # its confidence (0.75) is under min_read, but its matrix still takes it through the start list
    check("replay: OCR_MIN_SCORE=0.7 alone reads it as a weak read",
          En.replay_box(box, entries, dict(KNOBS, ocr_min_score=0.7))[0].entry_id, "E14")
    blank = dict(box, ocr_regions=[dict(region("14", det=0.75), matrix=[[0.0] * 11])])
    check("replay: a weak read whose matrix can't spell it stays unread",
          En.replay_box(blank, entries, dict(KNOBS, ocr_min_score=0.7))[0].method != "number", True)
    check("set: parses known names", En.parse_sets(["OCR_MIN_SCORE=0.7", "min_read=0.8"]),
          {"OCR_MIN_SCORE": 0.7, "min_read": 0.8})

    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

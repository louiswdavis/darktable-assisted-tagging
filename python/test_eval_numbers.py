# Run with: python python/test_eval_numbers.py
# Exercises ocr.py's region filter (drop_reason, pick_reads) and eval_numbers' miss causes; no models or files needed.

import contextlib
import io
import json
import os
import sys
import tempfile

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
    check("replay: dropped region leaves the box unread", En.replay_box(box, entries, KNOBS, {})[0].method != "number", True)
    lower = dict(KNOBS, ocr_min_score=0.7, min_read=0.7)
    check("replay: OCR_MIN_SCORE=0.7 and min_read=0.7 read it", En.replay_box(box, entries, lower, {})[0].entry_id, "E14")
    # its confidence (0.75) is under min_read, but its matrix still takes it through the start list
    check("replay: OCR_MIN_SCORE=0.7 alone reads it as a weak read",
          En.replay_box(box, entries, dict(KNOBS, ocr_min_score=0.7), {})[0].entry_id, "E14")
    blank = dict(box, ocr_regions=[dict(region("14", det=0.75), matrix=[[0.0] * 11])])
    check("replay: a weak read whose matrix can't spell it stays unread",
          En.replay_box(blank, entries, dict(KNOBS, ocr_min_score=0.7), {})[0].method != "number", True)
    both = dict(box, ocr_regions=[region("14"), region("41", rec=0.95)])
    three = dict(entries, E41=Entry("E41", "41", "C", ("t|41",)))
    check("replay: two numbers read in one box is no number read", En.replay_box(both, three, KNOBS, {})[0].method != "number", True)
    check("replay: the live run's noise number is left out", En.replay_box(both, three, KNOBS, {"41": 3})[0].entry_id, "E14")
    check("set: parses known names", En.parse_sets(["OCR_MIN_SCORE=0.7", "min_read=0.8"]),
          {"OCR_MIN_SCORE": 0.7, "min_read": 0.8})

    # 41 is read at 0.8 beside three start-list numbers: noise once min_read drops under 0.8
    def beside(number):
        return dict(box, ocr_regions=[region(number), region("41", rec=0.8)], read_entry="")

    four = dict(three, E33=Entry("E33", "33", "D", ("t|33",)))
    run = {"thresholds": KNOBS, "noise_numbers": {},
           "entries": {e.id: {"number": e.number, "team": e.team, "tags": list(e.tags)} for e in four.values()},
           "images": {"1": {"hand": "E14", "boxes": [beside("14")]}, "2": {"boxes": [beside("22")]},
                      "3": {"boxes": [beside("33"), dict(box, ocr_regions=[])]}}}
    check("noise: the live run's knobs give the live run's noise numbers", En.replay_noise(run, four, KNOBS), run["noise_numbers"])
    check("noise: a lower min_read finds the number the live run didn't count",
          En.replay_noise(run, four, dict(KNOBS, min_read=0.75)), {"41": 3})
    sure = {"noise_numbers": {"41": 3}, "images": {str(i): {"boxes": [{"ocr": [[n, 0.9], ["41", 0.9]]}]}
                                                   for i, n in enumerate(("14", "22", "33"))}}
    check("noise: a box that kept no regions counts with its stored reads", En.replay_noise(sure, four, KNOBS), sure["noise_numbers"])
    check("noise: a higher min_read drops the live run's noise number", En.replay_noise(sure, four, dict(KNOBS, min_read=0.95)), {})
    check("noise: a boxes.json from before noise numbers has none",
          En.replay_noise({"images": sure["images"]}, four, KNOBS), {})
    # ticket 71: a number_gate run stores each box's number share; under the gate the box has no reads
    shut = dict(box, ocr_regions=[region("14")], number_share=0.05, read_entry="")
    gate = dict(KNOBS, number_gate_min=0.1)
    check("gate: a box under the gate replays unread", En.replay_box(shut, entries, gate, {})[0].method != "number", True)
    check("gate: NUMBER_GATE_MIN=0 replays its regions", En.replay_box(shut, entries, dict(gate, number_gate_min=0.0), {})[0].entry_id, "E14")
    check("gate: a box with no number share is never gated", En.gated(dict(shut, number_share=None), gate), False)
    gate_run = {"thresholds": gate, "noise_numbers": {},
                "entries": {e.id: {"number": e.number, "team": e.team, "tags": list(e.tags)} for e in entries.values()},
                "images": {"1": {"hand": "E14", "boxes": [shut]}}}
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "gate.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(gate_run, f)
        printed, argv = io.StringIO(), sys.argv
        sys.argv = ["eval_numbers.py", path]
        try:
            with contextlib.redirect_stdout(printed):
                En.main()
        finally:
            sys.argv = argv
    check("main: a gated box is its own cause and agrees with the live run",
          [ln.strip() for ln in printed.getvalue().splitlines() if ln.strip().startswith(("gated", "replay"))],
          ["replay agrees with the live run on 1/1 boxes", "gated: 1"])
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "boxes.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(run, f)
        printed, argv = io.StringIO(), sys.argv
        sys.argv = ["eval_numbers.py", path, "--set", "min_read=0.75"]
        try:
            with contextlib.redirect_stdout(printed):
                En.main()
        finally:
            sys.argv = argv
    check("main: --set min_read replays with its own noise numbers",
          [ln for ln in printed.getvalue().splitlines() if ln.startswith("read right")],
          ["read right 1 (100.0%), wrong entry 0 (0.0%), unread 0 (0.0%)"])

    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

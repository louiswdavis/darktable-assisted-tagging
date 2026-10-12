# Run with: python python/test_match.py
# Exercises match.py's identification rules; no models or files needed.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import match as Mt
from match import BoxResult, Entry

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


ENTRIES = {
    "VER": Entry("VER", "1", "Red Bull", ("F1|Red Bull", "F1|Red Bull|Verstappen")),
    "TSU": Entry("TSU", "22", "Red Bull", ("F1|Red Bull", "F1|Red Bull|Tsunoda")),
    "HAM": Entry("HAM", "44", "Ferrari", ("F1|Ferrari|Hamilton",)),
    "SC": Entry("SC", "", "", ("F1|Safety Car",)),
}


def summary(r):
    return (r.method, r.entry_id, r.alt_entry_id)


def run_tests():
    # number rule
    check("a read number identifies its entry",
          summary(Mt.match_box(0, [("44", 0.9)], [], ENTRIES)), ("number", "HAM", ""))
    check("number confidence is the best matching candidate's",
          Mt.match_box(0, [("7", 0.99), ("44", 0.85)], [], ENTRIES).confidence, 0.85)
    shared = dict(ENTRIES, ALB=Entry("ALB", "44", "Williams", ("F1|Williams",)))
    check("a number two entries share identifies neither",
          summary(Mt.match_box(0, [("44", 0.9)], [], shared)), ("none", "", ""))
    check("two different numbers read identify neither",
          summary(Mt.match_box(0, [("44", 0.9), ("1", 0.9)], [], ENTRIES)), ("none", "", ""))
    check("an entry without a number never matches by number",
          summary(Mt.match_box(0, [("", 0.9)], [], ENTRIES)), ("none", "", ""))
    check("an unmatched number falls through to livery",
          summary(Mt.match_box(0, [("99", 0.9)], [("HAM", 0.8), ("VER", 0.6)], ENTRIES)), ("livery", "HAM", ""))

    # livery rules
    check("a clear livery match identifies",
          summary(Mt.match_box(0, [], [("HAM", 0.80), ("VER", 0.70)], ENTRIES)), ("livery", "HAM", ""))
    check("teammates too close to call give team only, with the runner-up",
          summary(Mt.match_box(0, [], [("VER", 0.80), ("TSU", 0.78)], ENTRIES)), ("team", "VER", "TSU"))
    check("different teams too close to call give none",
          summary(Mt.match_box(0, [], [("VER", 0.80), ("HAM", 0.78)], ENTRIES)), ("none", "", ""))
    check("below MATCH_MIN_SIM gives none even when clear",
          summary(Mt.match_box(0, [], [("HAM", 0.55), ("VER", 0.10)], ENTRIES)), ("none", "", ""))
    check("a single reference entry counts the runner-up as 0",
          summary(Mt.match_box(0, [], [("HAM", 0.62)], ENTRIES)), ("livery", "HAM", ""))
    check("an entry with no team never gives team only",
          summary(Mt.match_box(0, [], [("SC", 0.80), ("HAM", 0.79)], ENTRIES)), ("none", "", ""))
    check("references for entries no longer in entries.json are ignored",
          summary(Mt.match_box(0, [], [("GONE", 0.95), ("HAM", 0.80)], ENTRIES)), ("livery", "HAM", ""))
    check("no references and no number gives none",
          summary(Mt.match_box(0, [], [], ENTRIES)), ("none", "", ""))

    # burst consensus
    frames = {
        "1": [BoxResult(0, "number", "VER", "", 0.9)],
        "2": [BoxResult(0, "livery", "VER", "", 0.7)],
        "3": [BoxResult(0, "none")],
        "4": [BoxResult(0, "team", "VER", "TSU", 0.7)],
        "5": [BoxResult(-1, "none")],
    }
    burst_of = {k: "b" for k in frames}
    out = Mt.burst_consensus(frames, burst_of)
    check("an agreeing burst fills an unidentified frame", summary(out["3"][0]), ("burst", "VER", ""))
    check("an agreeing burst upgrades a team-only frame", summary(out["4"][0]), ("burst", "VER", ""))
    check("burst confidence is the agreeing share of the burst", out["3"][0].confidence, 2 / 5)
    check("a frame with no vehicle stays none", summary(out["5"][0]), ("none", "", ""))
    check("identified frames are left alone", summary(out["2"][0]), ("livery", "VER", ""))
    check("the input is not mutated", summary(frames["3"][0]), ("none", "", ""))

    one = Mt.burst_consensus({"1": frames["1"], "3": frames["3"]}, {"1": "b", "3": "b"})
    check("a single agreeing frame fills nothing", summary(one["3"][0]), ("none", "", ""))

    conflict = dict(frames, **{"6": [BoxResult(0, "number", "HAM", "", 0.9)]})
    out = Mt.burst_consensus(conflict, {k: "b" for k in conflict})
    check("a burst naming two entries fills nothing", summary(out["3"][0]), ("none", "", ""))

    split = Mt.burst_consensus(frames, {"1": "a", "2": "a", "3": "c", "4": "a", "5": "a"})
    check("consensus stays within its own burst", summary(split["3"][0]), ("none", "", ""))

    two_cars = {
        "1": [BoxResult(0, "number", "VER", "", 0.9), BoxResult(1, "none")],
        "2": [BoxResult(0, "number", "VER", "", 0.9)],
        "3": [BoxResult(0, "none"), BoxResult(1, "none")],
    }
    out = Mt.burst_consensus(two_cars, {k: "b" for k in two_cars})
    check("consensus fills only the largest box", [summary(r) for r in out["3"]],
          [("burst", "VER", ""), ("none", "", "")])
    check("a frame with one identified box isn't filled", summary(out["1"][1]), ("none", "", ""))

    print("")
    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

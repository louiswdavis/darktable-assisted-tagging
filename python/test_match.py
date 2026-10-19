# Run with: python python/test_match.py
# Exercises match.py's identification rules; no models or files needed.

import os
import sys
from dataclasses import replace

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
    "HAM": Entry("HAM", "44", "Ferrari", ("F1|Ferrari|Hamilton",), "yellow"),
    "LEC": Entry("LEC", "16", "Ferrari", ("F1|Ferrari|Leclerc",), "black"),
    "SC": Entry("SC", "", "", ("F1|Safety Car",)),
}


def summary(r):
    return (r.method, r.entry_id, r.alt_entry_id)


def run_tests():
    # number rule
    check("a number read that is part of the livery's longer number yields to the livery",
          summary(Mt.match_box(0, [("1", 0.9)], [("LEC", 0.95), ("VER", 0.50)], ENTRIES)), ("livery", "LEC", ""))
    check("a fragment read still wins when the livery is close and above the floor",
          summary(Mt.match_box(0, [("1", 0.9)], [("LEC", 0.70), ("VER", 0.62)], ENTRIES)), ("number", "VER", ""))
    check("a fragment read the livery does not back identifies nothing",
          summary(Mt.match_box(0, [("1", 0.9)], [("LEC", 0.52), ("VER", 0.45)], ENTRIES)), ("none", "", ""))
    check("a different number is not a fragment, so it wins over a clear livery",
          summary(Mt.match_box(0, [("44", 0.9)], [("LEC", 0.95), ("HAM", 0.50)], ENTRIES)), ("number", "HAM", ""))
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
          summary(Mt.match_box(0, [], [("HAM", 0.85), ("VER", 0.65)], ENTRIES)), ("livery", "HAM", ""))
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

    # identity-change split
    def ident(eid):
        return [BoxResult(0, "number", eid, "", 0.9)]

    def gap():
        return [BoxResult(0, "none")]

    cars = {"1": ident("VER"), "2": gap(), "3": ident("VER"), "4": ident("HAM"), "5": gap(), "6": ident("HAM"),
            "7": gap()}
    cars_burst = {k: "b" for k in cars}
    out = Mt.burst_consensus(cars, cars_burst)
    check("a split fills a gap inside a run", summary(out["2"][0]), ("burst", "VER", ""))
    check("a split fills a gap inside the other run", summary(out["5"][0]), ("burst", "HAM", ""))
    check("a split fills the burst's trailing edge from the last run", summary(out["7"][0]), ("burst", "HAM", ""))
    check("split confidence is the run's share of its span", round(out["2"][0].confidence, 3), round(2 / 3, 3))
    between = {"1": ident("VER"), "2": ident("VER"), "3": gap(), "4": ident("HAM"), "5": ident("HAM")}
    out = Mt.burst_consensus(between, {k: "b" for k in between})
    check("a gap between two runs belongs to neither", summary(out["3"][0]), ("none", "", ""))
    lone = {"1": ident("VER"), "2": ident("VER"), "3": gap(), "4": ident("HAM")}
    out = Mt.burst_consensus(lone, {k: "b" for k in lone})
    check("a single frame of another entry starts no run", summary(out["3"][0]), ("none", "", ""))
    shuffled = {"b": ident("HAM"), "a": ident("VER"), "c": gap(), "d": ident("VER"), "e": ident("HAM")}
    out = Mt.burst_consensus(shuffled, {k: "x" for k in shuffled}, None, {"a": 1, "d": 2, "c": 3, "b": 4, "e": 5})
    check("the order argument decides the shooting sequence", summary(out["c"][0]), ("none", "", ""))

    def livery(eid):
        return [BoxResult(0, "livery", eid, "", 0.7)]

    spike = {"1": ident("COL"), "2": livery("GAS"), "3": ident("COL"), "4": livery("GAS"), "5": ident("COL")}
    out = Mt.burst_consensus(spike, {k: "b" for k in spike})
    check("a livery call flanked by another car's numbers takes that car", summary(out["2"][0]), ("burst", "COL", ""))
    check("every flanked livery call is fixed", summary(out["4"][0]), ("burst", "COL", ""))
    edge = {"1": livery("GAS"), "2": ident("COL"), "3": ident("COL"), "4": ident("COL")}
    out = Mt.burst_consensus(edge, {k: "b" for k in edge})
    check("a livery call at the burst's edge is left alone", summary(out["1"][0]), ("livery", "GAS", ""))
    numbered = {"1": ident("COL"), "2": ident("GAS"), "3": ident("COL"), "4": ident("COL")}
    out = Mt.burst_consensus(numbered, {k: "b" for k in numbered})
    check("a number is never overridden", summary(out["2"][0]), ("number", "GAS", ""))

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

    # review fix 9: a team-only result for another team is evidence of a different car
    other_team = {
        "1": [BoxResult(0, "number", "VER", "", 0.9)],
        "2": [BoxResult(0, "number", "VER", "", 0.9)],
        "3": [BoxResult(0, "team", "HAM", "LEC", 0.7)],
        "4": [BoxResult(0, "team", "TSU", "VER", 0.7)],
    }
    out = Mt.burst_consensus(other_team, {k: "b" for k in other_team}, ENTRIES)
    check("burst doesn't override a team-only result for another team", summary(out["3"][0]), ("team", "HAM", "LEC"))
    check("burst does upgrade a team-only result for its own team", summary(out["4"][0]), ("burst", "VER", ""))

    # shot_type / decided_by / already_tagged / conflicts / promotable
    check("shot: no boxes", Mt.shot_type(0, 4), "")
    check("shot: one box is solo", Mt.shot_type(1, 4), "solo")
    check("shot: two boxes is a pack", Mt.shot_type(2, 4), "pack")
    check("shot: the cap reached is crowded", Mt.shot_type(4, 4), "crowded")

    sims_none = [("VER", 0.55), ("TSU", 0.40)]
    check("decided_by passes a method through", Mt.decided_by(BoxResult(0, "number", "VER"), [], ENTRIES), ("number", 0.0))
    check("decided_by: no vehicle", Mt.decided_by(BoxResult(-1, "none"), [], ENTRIES), ("no_vehicle", 0.0))
    check("decided_by: no references", Mt.decided_by(BoxResult(0, "none"), [], ENTRIES), ("no_references", 0.0))
    rule, gap = Mt.decided_by(BoxResult(0, "none"), sims_none, ENTRIES)
    check("decided_by: below the minimum similarity", (rule, round(gap, 3)), ("below_min_sim", 0.05))
    rule, gap = Mt.decided_by(BoxResult(0, "none"), [("VER", 0.91), ("HAM", 0.908)], ENTRIES)
    check("decided_by: margin too small", (rule, round(gap, 3)), ("margin_too_small", 0.148))

    check("already_tagged: a team tag alone is no one", Mt.already_tagged({"F1|Red Bull"}, ENTRIES), "")
    check("already_tagged: a driver's whole chain", Mt.already_tagged({"F1|Red Bull", "F1|Red Bull|Tsunoda"}, ENTRIES), "TSU")
    check("already_tagged: two drivers are no one", Mt.already_tagged(
        {"F1|Red Bull", "F1|Red Bull|Tsunoda", "F1|Ferrari|Hamilton"}, ENTRIES), "")

    check("conflict: a solo shot sharing no tag", Mt.conflicts("HAM", {"F1|Red Bull"}, ENTRIES, True), True)
    check("conflict: never in a pack", Mt.conflicts("HAM", {"F1|Red Bull"}, ENTRIES, False), False)
    check("conflict: nothing protected", Mt.conflicts("HAM", set(), ENTRIES, True), False)
    check("conflict: a shared tag agrees", Mt.conflicts("TSU", {"F1|Red Bull"}, ENTRIES, True), False)

    wide = {"method": "livery", "entry": "VER", "candidates": [["VER", 0.9], ["TSU", 0.7]]}
    check("promotable: number", Mt.promotable({"method": "number", "entry": "VER"}), True)
    check("promotable: wide livery margin", Mt.promotable(wide), True)
    check("promotable: narrow livery margin", Mt.promotable({**wide, "candidates": [["VER", 0.9], ["TSU", 0.85]]}), False)
    for m in ("burst", "team", "pooled", "conflict", "none"):
        check(f"promotable: never {m}", Mt.promotable({**wide, "method": m}), False)
    check("promotable: no entry", Mt.promotable({**wide, "entry": ""}), False)

    # ---- Stage B: hints
    check("entries_under: prefix boundary", list(Mt.entries_under(ENTRIES, ["F1|Red"])), [])
    check("entries_under: team prefix", list(Mt.entries_under(ENTRIES, ["F1|Red Bull"])), ["VER", "TSU"])
    sims = [("HAM", 0.90), ("VER", 0.70), ("TSU", 0.50)]
    r, h = Mt.hinted_match(0, [], sims, ENTRIES, [], "")
    check("hinted_match: no prefixes is plain match_box", (r.method, h), ("livery", {}))
    r, h = Mt.hinted_match(0, [], sims, ENTRIES, ["F1|Red Bull"], "tag")
    check("hinted_match: restricts to the team", (r.method, r.entry_id, h["restricted"], h["dropped"]), ("livery", "VER", 2, False))
    r, h = Mt.hinted_match(0, [], [("HAM", 0.9), ("VER", 0.5), ("TSU", 0.4)], ENTRIES, ["F1|Red Bull"], "sponsor")
    check("hinted_match: low restricted similarity drops the hint", (r.entry_id, h["dropped"], h["reason"]), ("HAM", True, "below_min_sim"))
    weak = [("HAM", 0.9), ("TSU", 0.5), ("VER", 0.45)]
    r, h = Mt.hinted_match(0, [], weak, ENTRIES, ["F1|Red Bull"], "tag")
    check("hinted_match: a weak livery under a tag gives the team", (r.method, r.entry_id, r.alt_entry_id, h["dropped"]), ("team", "TSU", "VER", False))
    check("hinted_match: the pod then picks the driver", Mt.match_camera(
        r, "yellow", dict(ENTRIES, VER=replace(ENTRIES["VER"], camera="yellow"), TSU=replace(ENTRIES["TSU"], camera="black"))).entry_id, "VER")
    r, h = Mt.hinted_match(0, [("1", 0.9)], weak, ENTRIES, ["F1|Red Bull"], "tag")
    check("hinted_match: a number inside the tagged set still wins", (r.method, r.entry_id), ("number", "VER"))
    r, h = Mt.hinted_match(0, [], weak, ENTRIES, ["F1|Red Bull"], "sponsor")
    check("hinted_match: a weak sponsor hint is still dropped", (r.method, h["dropped"]), ("livery", True))
    r, h = Mt.hinted_match(0, [("44", 0.9)], sims, ENTRIES, ["F1|Red Bull"], "tag")
    check("hinted_match: a number outside the set drops the hint", (r.entry_id, h["reason"]), ("HAM", "number_outside"))
    r, h = Mt.hinted_match(0, [("44", 0.9)], [("VER", 0.8), ("TSU", 0.5), ("HAM", 0.3)], ENTRIES, ["F1|Red Bull"], "tag")
    check("hinted_match: a number outside is ignored when the livery clearly points inside a tagged set",
          (r.method, r.entry_id, h["dropped"]), ("livery", "VER", False))
    r, h = Mt.hinted_match(0, [("44", 0.9)], [("VER", 0.8), ("TSU", 0.5), ("HAM", 0.3)], ENTRIES, ["F1|Red Bull"], "sponsor")
    check("hinted_match: a sponsor hint still yields to an outside number", (r.entry_id, h["reason"]), ("HAM", "number_outside"))
    check("disagrees: a solo shot of another entry", Mt.disagrees(BoxResult(0, "livery", "TSU"), "VER", True), True)
    check("disagrees: the tagged entry agrees", Mt.disagrees(BoxResult(0, "livery", "VER"), "VER", True), False)
    check("disagrees: a team result listing it agrees", Mt.disagrees(BoxResult(0, "team", "TSU", "VER", 0.7), "VER", True), False)
    check("disagrees: packs and unidentified boxes never disagree",
          (Mt.disagrees(BoxResult(0, "livery", "TSU"), "VER", False), Mt.disagrees(BoxResult(0, "none"), "VER", True)), (False, False))
    check("most_specific: an ancestor prefix is dropped", Mt.most_specific(["F1", "F1|Red Bull", "F1|Red Bull", "F2"]), ["F1|Red Bull", "F2"])
    r, h = Mt.hinted_match(0, [], sims, ENTRIES, ["F1", "F1|Red Bull"], "tag")
    check("hinted_match: a broad tag doesn't widen a team tag", (h["restricted"], h["prefixes"]), (2, ["F1|Red Bull"]))
    r, h = Mt.hinted_match(0, [], sims, ENTRIES, ["F1|Nobody"], "tag")
    check("hinted_match: a prefix matching no entry falls back", (r.entry_id, h["reason"]), ("HAM", "no_entries"))

    # ---- partial references
    none = BoxResult(0, "none")
    check("match_team: a clear team lead becomes team", Mt.match_team(none, [("F1|Red Bull", 0.8), ("F1|Ferrari", 0.6)], ENTRIES)
          .method, "team")
    check("match_team: a narrow lead stays none", Mt.match_team(none, [("F1|Red Bull", 0.8), ("F1|Ferrari", 0.78)], ENTRIES).method, "none")
    check("match_team: a one-entry team stays none", Mt.match_team(none, [("F1|Safety Car", 0.9)], ENTRIES).method, "none")
    check("match_team: identified results are untouched", Mt.match_team(BoxResult(0, "livery", "HAM"), [("F1|Red Bull", 0.9)], ENTRIES).method, "livery")
    check("team_key avoids the path separator", Mt.team_key("F1|Red Bull"), "@team@F1__Red Bull")

    print("")
    team_r = Mt.BoxResult(0, "team", "HAM", "LEC", 0.9)
    r = Mt.match_camera(team_r, "black", ENTRIES)
    check("match_camera: black pod picks the black driver", (r.method, r.entry_id, r.alt_entry_id), ("livery", "LEC", ""))
    check("match_camera: yellow pod picks the yellow driver", Mt.match_camera(team_r, "yellow", ENTRIES).entry_id, "HAM")
    check("match_camera: unknown colour is a no-op", Mt.match_camera(team_r, "", ENTRIES), team_r)
    check("match_camera: a livery result keeps its driver when the pod agrees", Mt.match_camera(
        Mt.BoxResult(0, "livery", "LEC", "", 0.7), "black", ENTRIES).entry_id, "LEC")
    check("match_camera: a livery result moves to the teammate whose pod matches", Mt.match_camera(
        Mt.BoxResult(0, "livery", "HAM", "", 0.7), "black", ENTRIES).entry_id, "LEC")
    check("match_camera: a livery result with an unknown pod is left alone", Mt.match_camera(
        Mt.BoxResult(0, "livery", "HAM", "", 0.7), "", ENTRIES).entry_id, "HAM")
    check("match_camera: number results never change", Mt.match_camera(
        Mt.BoxResult(0, "number", "HAM", "", 0.9), "black", ENTRIES).entry_id, "HAM")
    two_yellow = dict(ENTRIES, X=Entry("X", "", "Ferrari", ("F1|Ferrari",), "yellow"))
    check("match_camera: two owners of a colour is a no-op", Mt.match_camera(team_r, "yellow", two_yellow), team_r)
    check("match_camera: owner outside the candidates is a no-op", Mt.match_camera(replace(team_r, alt_entry_id="X"), "black", two_yellow).method, "team")

    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

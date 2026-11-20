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

    # misread number: a look-alike digit off a number in the livery's top 3
    close = [("HAM", 0.80), ("LEC", 0.79), ("VER", 0.70)]
    check("a 15 read backs the 16 in the livery's top 3 despite a tie",
          summary(Mt.match_box(0, [("15", 0.9)], close, ENTRIES)), ("livery", "LEC", ""))
    check("the misread keeps the unmatched number for the diagnostic tag",
          Mt.match_box(0, [("15", 0.9)], close, ENTRIES).unmatched_number, "15")
    check("a misread's confidence is the entry's similarity",
          Mt.match_box(0, [("15", 0.9)], close, ENTRIES).confidence, 0.79)
    check("a 12 is not a look-alike of 16, so the teammate tie stands",
          summary(Mt.match_box(0, [("12", 0.9)], close, ENTRIES)), ("team", "HAM", "LEC"))
    check("a misread of an entry outside the livery's top 3 does nothing",
          summary(Mt.match_box(0, [("15", 0.9)], [("HAM", 0.80), ("VER", 0.79), ("TSU", 0.78), ("LEC", 0.77)], ENTRIES)),
          ("none", "", ""))
    check("a misread of an entry under MATCH_MIN_SIM does nothing",
          summary(Mt.match_box(0, [("15", 0.9)], [("HAM", 0.58), ("LEC", 0.57)], ENTRIES)), ("none", "", ""))
    two = dict(ENTRIES, ALB=Entry("ALB", "15", "", ("F1|Williams",)))
    check("an exact read of another entry's number beats the look-alike",
          summary(Mt.match_box(0, [("15", 0.9)], close, two)), ("number", "ALB", ""))
    twin = dict(ENTRIES, STR=Entry("STR", "13", "Aston Martin", ("F1|Aston Martin",)))
    check("two entries a look-alike away from the read identify neither",
          summary(Mt.match_box(0, [("15", 0.9)], [("LEC", 0.80), ("STR", 0.79)], twin)), ("none", "", ""))

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
    frames.pop("5")
    burst_of = {k: "b" for k in frames}
    out = Mt.burst_consensus(frames, burst_of)
    check("an agreeing burst fills an unidentified frame", summary(out["3"][0]), ("burst", "VER", ""))
    check("an agreeing burst upgrades a team-only frame", summary(out["4"][0]), ("burst", "VER", ""))
    check("burst confidence is the agreeing share of the burst", out["3"][0].confidence, 2 / 4)
    novehicle = dict(frames, **{"5": [BoxResult(-1, "none")]})
    check("a frame with no vehicle under the confidence floor stays none",
          summary(Mt.burst_consensus(novehicle, {k: "b" for k in novehicle})["5"][0]), ("none", "", ""))
    small = {"1": frames["1"], "2": frames["2"], "5": [BoxResult(-1, "none")]}
    filled = Mt.burst_consensus(small, {k: "b" for k in small})["5"]
    check("a frame with no vehicle takes its burst's entry", [(r.box, *summary(r)) for r in filled], [(-1, "burst", "VER", "")])
    nb = {"1": [BoxResult(0, "neighbour", "VER", "", 0.8)], "2": frames["2"], "3": frames["3"]}
    check("a neighbour result anchors a burst", summary(Mt.burst_consensus(nb, {k: "b" for k in nb})["3"][0]), ("burst", "VER", ""))
    check("a neighbour result is not overwritten by the burst",
          summary(Mt.burst_consensus(nb, {k: "b" for k in nb})["1"][0]), ("neighbour", "VER", ""))
    err = {"1": frames["1"], "2": frames["2"], "5": [BoxResult(-1, "error")]}
    check("an error frame is never filled", Mt.burst_consensus(err, {k: "b" for k in err})["5"][0].method, "error")
    sparse = dict(frames, **{k: [BoxResult(0, "none")] for k in "567"})
    check("a burst fill under the confidence floor is not written",
          summary(Mt.burst_consensus(sparse, {k: "b" for k in sparse})["3"][0]), ("none", "", ""))
    check("identified frames are left alone", summary(out["2"][0]), ("livery", "VER", ""))
    check("the input is not mutated", summary(frames["3"][0]), ("none", "", ""))

    one = Mt.burst_consensus({"1": frames["1"], "3": frames["3"]}, {"1": "b", "3": "b"})
    check("a single agreeing frame fills nothing", summary(one["3"][0]), ("none", "", ""))

    sure = {"1": [BoxResult(0, "number", "VER", "", 0.97)], **{k: [BoxResult(0, "none")] for k in "2345"}}
    out = Mt.burst_consensus(sure, {k: "b" for k in sure})
    check("one sure number read fills its whole burst", [summary(out[k][0]) for k in "2345"],
          [("burst", "VER", "")] * 4)
    check("a solo fill's confidence is still the agreeing share", out["2"][0].confidence, 1 / 5)
    sure_livery = {"1": [BoxResult(0, "livery", "VER", "", 0.97)], "2": [BoxResult(0, "none")]}
    check("a sure livery call alone fills nothing",
          summary(Mt.burst_consensus(sure_livery, {k: "b" for k in sure_livery})["2"][0]), ("none", "", ""))
    sure_rival = dict(sure, **{"6": [BoxResult(0, "number", "HAM", "", 0.9)]})
    check("a sure read doesn't fill a burst that names another entry",
          summary(Mt.burst_consensus(sure_rival, {k: "b" for k in sure_rival})["2"][0]), ("none", "", ""))
    sure_team = dict(sure, **{"6": [BoxResult(0, "team", "HAM", "LEC", 0.7)]})
    check("a solo fill leaves another team's car alone",
          summary(Mt.burst_consensus(sure_team, {k: "b" for k in sure_team}, ENTRIES)["6"][0]), ("team", "HAM", "LEC"))

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
    # a pack's largest box need not be the burst's car: the box's own sims must back the entry
    pack = {"1": ident("VER"), "2": ident("VER"), "3": gap(), "4": gap()}
    pack_burst = {k: "b" for k in pack}
    sims = {"3": [("HAM", 0.80), ("NOR", 0.78), ("VER", 0.70)], "4": [("HAM", 0.80), ("VER", 0.76)]}
    out = Mt.burst_consensus(pack, pack_burst, None, None, sims)
    check("a burst entry far down the box's own sims is not filled", summary(out["3"][0]), ("none", "", ""))
    check("a burst entry within the slack of the box's top-1 is filled", summary(out["4"][0]), ("burst", "VER", ""))
    out = Mt.burst_consensus(pack, pack_burst, None, None, {"3": [("VER", 0.5)]})
    check("a burst entry the box ranks first is filled", summary(out["3"][0]), ("burst", "VER", ""))
    check("a frame with no sims is not filled when sims are given", summary(out["4"][0]), ("none", "", ""))

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

    # ticket 65: a pack burst names its car from box 0 or a hand tag, never from box 1
    def chased(eid):
        return [BoxResult(0, "none"), BoxResult(1, "number", eid, "", 0.9)]

    hand_pack = {"1": chased("HAM") + [BoxResult(-1, Mt.HAND, "VER", "", 1.0)], "2": chased("HAM"), "3": chased("HAM")}
    out = Mt.burst_consensus(hand_pack, {k: "b" for k in hand_pack})
    check("one hand-tagged pack frame fills its car's box 0 across the burst",
          [[summary(r) for r in out[k]] for k in "23"],
          [[("burst", "VER", ""), ("number", "HAM", "")]] * 2)
    behind = {"1": chased("HAM"), "2": chased("HAM"), "3": [BoxResult(0, "none")]}
    out = Mt.burst_consensus(behind, {k: "b" for k in behind})
    check("an entry seen only on box 1 never fills box 0", [summary(out[k][0]) for k in "123"],
          [("none", "", "")] * 3)
    split_hand = {"1": ident("GAS"), "2": ident("GAS"), "3": gap(),
                  "4": [BoxResult(0, "none"), BoxResult(1, "none"), BoxResult(-1, Mt.HAND, "COL", "", 1.0)],
                  "5": gap()}
    out = Mt.burst_consensus(split_hand, {k: "b" for k in split_hand})
    check("a split run of one hand-tagged frame fills to the burst's edge", summary(out["5"][0]), ("burst", "COL", ""))
    check("the gap between the two cars stays unfilled", summary(out["3"][0]), ("none", "", ""))

    # ticket 69: `why` collects, per frame a burst left blank, the burst's entry and the rule that stopped it
    def why_of(fr, *args):
        why = {}
        Mt.burst_consensus(fr, {k: "b" for k in fr}, *args, why=why)
        return why

    check("why: too small a share of the burst agrees", why_of(sparse).get("3"), ("VER", "low share"))
    check("why: only one frame reads the car", why_of({"1": frames["1"], "3": frames["3"]}).get("3"), ("VER", "one read"))
    check("why: a gap between two cars", why_of(between).get("3"), ("", "between cars"))
    check("why: the frame's own box doesn't look like the car", why_of(pack, None, None, sims).get("3"),
          ("VER", "looks unlike"))
    check("why: filled frames and anchors are not listed", sorted(why_of(cars)), [])

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

    # weak reads agreeing across a group
    blank = {k: [BoxResult(0, "none")] for k in "123"}
    grp = {k: "g" for k in blank}
    weak = {"1": {0: [("44", 0.8)]}, "2": {0: [("44", 0.75)]}, "3": {0: [("16", 0.8)]}}
    out = Mt.agreeing_reads(blank, grp, weak, ENTRIES)
    check("two frames' weak reads agree: number", (summary(out["1"][0]), out["1"][0].confidence), (("number", "HAM", ""), 0.8))
    check("the second agreeing frame too", summary(out["2"][0]), ("number", "HAM", ""))
    check("a lone weak read stays none", summary(out["3"][0]), ("none", "", ""))
    check("one frame alone doesn't agree",
          summary(Mt.agreeing_reads(blank, grp, {"1": {0: [("44", 0.8)]}}, ENTRIES)["1"][0]), ("none", "", ""))
    check("same read in different groups doesn't agree",
          summary(Mt.agreeing_reads(blank, {"1": "a", "2": "b", "3": "c"}, weak, ENTRIES)["1"][0]), ("none", "", ""))
    check("a read under WEAK_READ_MIN doesn't count",
          summary(Mt.agreeing_reads(blank, grp, {"1": {0: [("44", 0.6)]}, "2": {0: [("44", 0.8)]}}, ENTRIES)["2"][0]), ("none", "", ""))
    two = {"1": {0: [("44", 0.8)]}, "2": {0: [("44", 0.8), ("16", 0.8)]}, "3": {0: [("16", 0.8)]}}
    check("two entries agreed in one group: neither",
          summary(Mt.agreeing_reads(blank, grp, two, ENTRIES)["1"][0]), ("none", "", ""))
    rival = dict(blank, **{"3": [BoxResult(0, "livery", "LEC", "", 0.7)]})
    check("an identified rival in the group blocks it",
          summary(Mt.agreeing_reads(rival, grp, weak, ENTRIES)["1"][0]), ("none", "", ""))
    same = dict(blank, **{"3": [BoxResult(0, "livery", "HAM", "", 0.7)]})
    out = Mt.agreeing_reads(same, grp, weak, ENTRIES)
    check("an identified box of the same entry allows it; it is untouched",
          (summary(out["1"][0]), summary(out["3"][0])), (("number", "HAM", ""), ("livery", "HAM", "")))
    shared = dict(ENTRIES, **{"X": Entry("X", "44", "", ("F1|X",))})
    check("a number two entries share agrees on neither",
          summary(Mt.agreeing_reads(blank, grp, weak, shared)["1"][0]), ("none", "", ""))
    hidden = {"1": [BoxResult(0, "none"), BoxResult(1, "none")], "2": [BoxResult(0, "none")]}
    out = Mt.agreeing_reads(hidden, {"1": "g", "2": "g"}, {"1": {1: [("44", 0.8)]}, "2": {0: [("44", 0.8)]}}, ENTRIES)
    check("only the box that read it changes", (summary(out["1"][0]), summary(out["1"][1])), (("none", "", ""), ("number", "HAM", "")))

    # colour tie-break on weak reads: a read naming an entry of another colour isn't counted
    red = {k: [BoxResult(0, "none", colour="Red")] for k in "12"}
    red_grp = {k: "g" for k in red}
    red_weak = {"1": {0: [("44", 0.75)]}, "2": {0: [("44", 0.75)]}}
    def coloured(c):
        return dict(ENTRIES, HAM=replace(ENTRIES["HAM"], colour=c))
    check("weak reads of a Blue entry on red boxes stay none",
          summary(Mt.agreeing_reads(red, red_grp, red_weak, coloured("Blue"))["1"][0]), ("none", "", ""))
    check("weak reads of a Red entry on red boxes agree",
          summary(Mt.agreeing_reads(red, red_grp, red_weak, coloured("Red"))["1"][0]), ("number", "HAM", ""))
    check("weak reads with no entry colour agree as before",
          summary(Mt.agreeing_reads(red, red_grp, red_weak, coloured(""))["1"][0]), ("number", "HAM", ""))

    # colour_check: a number read whose entry's colour disagrees is flagged, the result kept
    num = {"1": [BoxResult(0, "number", "HAM", "", 0.99, colour="Red")]}
    out = Mt.colour_check(num, coloured("Blue"))["1"][0]
    check("a Blue entry read on a red box is flagged", (out.colour_flag, summary(out)), (True, ("number", "HAM", "")))
    check("no entry colour, no flag", Mt.colour_check(num, coloured(""))["1"][0].colour_flag, False)
    multi = {"1": [BoxResult(0, "number", "HAM", "", 0.99, colour="Multi")]}
    check("a Multi entry on a Multi box is not flagged", Mt.colour_check(multi, coloured("Multi"))["1"][0].colour_flag, False)
    liv = {"1": [BoxResult(0, "livery", "HAM", "", 0.8, colour="Red")]}
    check("only number results are flagged", Mt.colour_check(liv, coloured("Blue"))["1"][0].colour_flag, False)

    # colour_overturns: nearly all of an entry's number boxes in a clashing colour are reported
    def boxes(method, colours):
        return {str(i): [BoxResult(0, method, "HAM", "", 0.99, colour=c)] for i, c in enumerate(colours)}
    check("nearly all number boxes clashing with the entry's colour are reported",
          Mt.colour_overturns(boxes("number", ["Red"] * 9 + ["Blue"]), coloured("Blue")),
          [("HAM", "Blue", "Red", 9, 10, [str(i) for i in range(9)])])
    check("most but not nearly all is not reported",
          Mt.colour_overturns(boxes("number", ["Red"] * 3 + ["Blue"]), coloured("Blue")), [])
    check("livery boxes don't count towards an overturn",
          Mt.colour_overturns(boxes("livery", ["Red"] * 10), coloured("Blue")), [])

    # --verify: the tags name the car, so a solo box is checked against the tagged entry whatever its method
    tagged = {str(i): "HAM" for i in range(10)}
    check("verify: livery boxes of tagged solo shots count towards an overturn",
          Mt.colour_overturns(boxes("livery", ["Red"] * 10), coloured("Blue"), tagged),
          [("HAM", "Blue", "Red", 10, 10, [str(i) for i in range(10)])])
    check("verify: an untagged photo doesn't count",
          Mt.colour_overturns(boxes("livery", ["Red"] * 10), coloured("Blue"), {}), [])
    out = Mt.colour_check(liv, coloured("Blue"), {"1": "HAM"})["1"][0]
    check("verify: a tagged solo shot's clashing colour is flagged whatever its method", out.colour_flag, True)
    other = {"1": [BoxResult(0, "number", "VER", "", 0.99, colour="Red")]}
    check("verify: the tagged entry is checked, not the one read",
          Mt.colour_check(other, coloured("Blue"), {"1": "HAM"})["1"][0].colour_flag, True)
    pack = {"1": [BoxResult(0, "number", "HAM", "", 0.99, colour="Red"), BoxResult(1, "number", "HAM", "", 0.99, colour="Red")]}
    check("verify: packs stay unchecked",
          [r.colour_flag for r in Mt.colour_check(pack, coloured("Blue"), {"1": "HAM"})["1"]], [False, False])

    # burst_colours: one colour per car per burst, from the mean of its boxes' shares
    red = {"Red": 0.7, "Pink": 0.2, "Multi": 0.1}
    pink = {"Red": 0.35, "Pink": 0.5, "Multi": 0.15}
    car = {"1": [BoxResult(0, "number", "HAM", colour="Red")], "2": [BoxResult(0, "livery", "HAM", colour="Pink")],
           "3": [BoxResult(0, "burst", "HAM", colour="Red")]}
    shares = {("1", 0): red, ("2", 0): pink, ("3", 0): red}
    out, changes = Mt.burst_colours(car, {"1": "b", "2": "b", "3": "b"}, shares)
    check("the odd frame takes the car's colour", [out[f][0].colour for f in "123"], ["Red", "Red", "Red"])
    check("the change is listed", changes, [("2", 0, "Pink", "Red", 3)])
    out, changes = Mt.burst_colours(car, {"1": "a", "2": "b", "3": "c"}, shares)
    check("separate bursts keep their own colours", ([out[f][0].colour for f in "123"], changes), (["Red", "Pink", "Red"], []))
    two_cars = {"1": [BoxResult(0, "number", "HAM", colour="Red"), BoxResult(1, "number", "VER", colour="Pink")],
                "2": [BoxResult(0, "number", "HAM", colour="Pink")]}
    out, _ = Mt.burst_colours(two_cars, {"1": "b", "2": "b"}, {("1", 0): red, ("1", 1): pink, ("2", 0): {**red, "Red": 0.6}})
    check("each car votes alone", [r.colour for r in out["1"]] + [out["2"][0].colour], ["Red", "Pink", "Red"])
    unknown = {"1": [BoxResult(0, "number", "HAM", colour="Red")], "2": [BoxResult(0, "none", colour="Pink")],
               "3": [BoxResult(0, "team", "HAM", colour="Pink")]}
    out, changes = Mt.burst_colours(unknown, {"1": "b", "2": "b", "3": "b"}, {("1", 0): red, ("2", 0): pink, ("3", 0): pink})
    check("unidentified and team-only boxes neither vote nor change", changes, [])
    unsure = {"Red": 0.4, "Pink": 0.35, "Multi": 0.25}
    out, changes = Mt.burst_colours(car, {"1": "b", "2": "b", "3": "b"}, {("1", 0): unsure, ("2", 0): pink, ("3", 0): unsure})
    check("a mean that decides no colour keeps each box's own", changes, [])
    hsv = {"Red": 0.6, "Pink": 0.1}
    out, changes = Mt.burst_colours(car, {"1": "b", "2": "b", "3": "b"}, {("1", 0): red, ("2", 0): hsv, ("3", 0): red})
    check("shares from two colour readers are not mixed", changes, [])

    # main_car_only: one car per photo, the largest box; a smaller box counts only with another car's number
    background = {"1": [BoxResult(0, "number", "HAM", colour="Brown"), BoxResult(1, "none", colour="Blue", unmatched_number="7")]}
    out, ignored = Mt.main_car_only(background)
    check("a background box loses its colour and seen number", out["1"][1], BoxResult(1, "none"))
    check("the main car is kept", out["1"][0], background["1"][0])
    check("the ignored box is listed", ignored, [("1", 1, "none", "")])
    twin = {"1": [BoxResult(0, "livery", "HAM", colour="Grey"), BoxResult(1, "livery", "HAM", colour="Purple")]}
    check("a second livery box is ignored", summary(Mt.main_car_only(twin)[0]["1"][1]), ("none", "", ""))
    pack = {"1": [BoxResult(0, "number", "HAM", colour="Red"), BoxResult(1, "number", "VER", colour="Pink")]}
    check("a smaller box reading another car's number is kept", Mt.main_car_only(pack)[0], pack)
    same = {"1": [BoxResult(0, "number", "HAM"), BoxResult(1, "number", "HAM", colour="Red")]}
    check("a smaller box reading the main car's number is ignored", Mt.main_car_only(same)[0]["1"][1], BoxResult(1, "none"))
    unread = {"1": [BoxResult(0, "none", colour="Green"), BoxResult(1, "none", colour="Blue")], "2": [BoxResult(-1, "hand", "HAM", "", 1.0)]}
    out, _ = Mt.main_car_only(unread)
    check("an unidentified photo keeps only its main box's colour", [r.colour for r in out["1"]], ["Green", ""])
    check("box -1 rows are kept", out["2"], unread["2"])

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
    check("decided_by: margin too small", (rule, round(gap, 3)), ("margin_too_small", 0.098))

    check("already_tagged: a team tag alone is no one", Mt.already_tagged({"F1|Red Bull"}, ENTRIES), "")
    check("already_tagged: a driver's whole chain", Mt.already_tagged({"F1|Red Bull", "F1|Red Bull|Tsunoda"}, ENTRIES), "TSU")
    check("already_tagged: two drivers are no one", Mt.already_tagged(
        {"F1|Red Bull", "F1|Red Bull|Tsunoda", "F1|Ferrari|Hamilton"}, ENTRIES), "")

    car = ("Rally|Number|30", "Rally|Number|730")
    mates = dict(ENTRIES, **{"30": Entry("30", "30", "", car, car="30"), "730": Entry("730", "730", "", car, car="30"),
                             "12": Entry("12", "12", "", ("Rally|Number|12",))})
    check("by_car keeps the best of a car, order kept", Mt.by_car([("30", .80), ("730", .79), ("12", .50)], mates),
          [("30", .80), ("12", .50)])
    check("a livery near-tie between car-mates names the car",
          summary(Mt.match_livery(0, [("730", .80), ("30", .79), ("12", .50)], mates)), ("livery", "730", ""))
    shared = ("F1|Shared|16",)
    pair = {"D1": Entry("D1", "16", "", shared, car="D1"), "D2": Entry("D2", "16", "", shared, car="D1"),
            "HAM": ENTRIES["HAM"]}
    check("a misread counts a double-driven car once, so it still names the car",
          summary(Mt.match_box(0, [("15", 0.9)], [("D1", .80), ("D2", .79), ("HAM", .70)], pair)), ("livery", "D1", ""))
    check("car-mates take one top-3 slot, so a misread 4th by raw rank is reached",
          summary(Mt.match_box(0, [("15", 0.9)], [("30", .80), ("730", .79), ("12", .78), ("LEC", .77)],
                               mates)), ("livery", "LEC", ""))
    check("decided_by: car-mates don't eat the margin",
          [round(x, 3) if isinstance(x, float) else x
           for x in Mt.decided_by(Mt.BoxResult(0, "none"), [("30", .65), ("730", .64), ("12", .58)], mates)],
          ["margin_too_small", 0.03])
    check("already_tagged: a car's full tags name its first entry", Mt.already_tagged(set(car), mates), "30")
    check("already_tagged: a car plus another driver is no one",
          Mt.already_tagged(set(car) | {"F1|Ferrari|Hamilton"}, mates), "")

    check("conflict: a solo shot sharing no tag", Mt.conflicts("HAM", {"F1|Red Bull"}, ENTRIES, True), True)
    check("conflict: never in a pack", Mt.conflicts("HAM", {"F1|Red Bull"}, ENTRIES, False), False)
    check("conflict: nothing protected", Mt.conflicts("HAM", set(), ENTRIES, True), False)
    check("conflict: a shared tag agrees", Mt.conflicts("TSU", {"F1|Red Bull"}, ENTRIES, True), False)

    wide = {"method": "livery", "entry": "VER", "candidates": [["VER", 0.9], ["TSU", 0.7]]}
    check("promotable: number", Mt.promotable({"method": "number", "entry": "VER"}), True)
    # a wide livery lead isn't enough: on Rallye, 36 of the 44 boxes promoted to car 39 were other cars
    check("promotable: never livery, however wide its lead", Mt.promotable(wide), False)
    for m in ("burst", "team", "pooled", "conflict", "none"):
        check(f"promotable: never {m}", Mt.promotable({**wide, "method": m}), False)
    check("promotable: no entry", Mt.promotable({"method": "number", "entry": ""}), False)

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
    check("disagrees: a solo shot of another entry", Mt.disagrees(BoxResult(0, "livery", "TSU"), "VER", True, ENTRIES), True)
    check("disagrees: the tagged entry agrees", Mt.disagrees(BoxResult(0, "livery", "VER"), "VER", True, ENTRIES), False)
    check("disagrees: a team result listing it agrees", Mt.disagrees(BoxResult(0, "team", "TSU", "VER", 0.7), "VER", True, ENTRIES), False)
    check("disagrees: a match moved off the tagged entry disagrees",
          Mt.disagrees(BoxResult(0, "livery", "TSU", "VER", 0.7, anchor_flag=True), "VER", True, ENTRIES), True)
    check("disagrees: packs and unidentified boxes never disagree",
          (Mt.disagrees(BoxResult(0, "livery", "TSU"), "VER", False, ENTRIES), Mt.disagrees(BoxResult(0, "none"), "VER", True, ENTRIES)), (False, False))
    check("disagrees: a car-mate's read agrees (a double-driven car's entries are one car)",
          (Mt.disagrees(BoxResult(0, "livery", "730"), "30", True, mates), Mt.disagrees(BoxResult(0, "number", "30"), "730", True, mates)),
          (False, False))
    check("disagrees: another car still disagrees with a car-mate", Mt.disagrees(BoxResult(0, "livery", "12"), "30", True, mates), True)
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

    # Start-list scoring: reads scored against every entry number by their digit matrices.
    def matrix(*steps):
        """Digit matrix rows from {column: probability} per step; "-" is blank, else a digit."""
        rows = []
        for step in steps:
            row = [0.0] * 11
            for k, v in step.items():
                row[0 if k == "-" else 1 + int(k)] = v
            rows.append(row)
        return rows

    def numbered(*numbers):
        return {f"E{n}": Entry(f"E{n}", n, "", (f"Rally|Number|{n}",)) for n in numbers}

    check("ctc: a sure one-step digit spells it", round(Mt.ctc_log_likelihood(matrix({"1": 1.0}), "1"), 3), 0.0)
    check("ctc: a repeated digit needs a blank between, so two steps can't spell 11",
          Mt.ctc_log_likelihood(matrix({"1": 1.0}, {"1": 1.0}), "11"), float("-inf"))

    # greedy 1 - 4 - 4 = "144", but the second 4 is weaker than reading one long 4
    m144 = matrix({"1": .98, "-": .02}, {"-": .95, "1": .05}, {"4": .98, "-": .02}, {"-": .6, "4": .4}, {"4": .55, "-": .45})
    r = Mt.match_box(0, [("144", 0.9)], [], numbered("14", "44", "22"), {"144": m144})
    check("list: a 144 read gives 14 when 144 isn't on the list", (r.method, r.entry_id), ("number", "E14"))
    check("list: the result shows greedy, best and runner-up", r.list_read.startswith("144>14 "), True)
    check("list: a number not on the list never wins", "144" not in r.list_read.split(">", 1)[1], True)

    # greedy "1", with a faint 4 after it
    m1 = matrix({"1": .98, "-": .02}, {"-": .9, "1": .1}, {"-": .55, "4": .45}, {"-": .55, "4": .45})
    r = Mt.match_box(0, [("1", 0.9)], [], numbered("14", "44", "22"), {"1": m1})
    check("list: a 1 read gives 14 when 1 isn't on the list", (r.method, r.entry_id), ("number", "E14"))
    r = Mt.match_box(0, [("1", 0.9)], [], numbered("1", "14"), {"1": m1})
    check("list: 1 and 14 both on the list and the 4 faint is a close call", (r.method, r.list_read.endswith("close call")), ("none", True))

    # first digit unclear between 1 and 4
    m_x4 = matrix({"1": .5, "4": .48, "-": .02}, {"-": .95, "4": .05}, {"4": .98, "-": .02})
    r = Mt.match_box(0, [("14", 0.9)], [], numbered("14", "44"), {"14": m_x4})
    check("list: 14 and 44 with an unclear first digit is a close call", (r.method, r.entry_id, r.unmatched_number), ("none", "", "14"))
    check("list: a close call says so", r.list_read.endswith("close call"), True)
    r = Mt.match_box(0, [("14", 0.9)], [("E44", 0.8), ("E14", 0.5)], numbered("14", "44"), {"14": m_x4})
    check("list: a close call goes on to livery", (r.method, r.entry_id), ("livery", "E44"))

    r = Mt.match_box(0, [("7", 0.9)], [], numbered("14", "44"), {"7": matrix({"7": .99})})
    check("list: a read far from every number is no list read", (r.method, r.unmatched_number, r.list_read), ("none", "7", "7> no list read"))

    # without the matrix, today's path
    sims = [("HAM", 0.8), ("VER", 0.5)]
    for name, ctc in (("none", None), ("missing for a read", {"9": m1})):
        check(f"list: matrix {name} gives today's result", Mt.match_box(0, [("1", 0.9)], sims, ENTRIES, ctc),
              Mt.match_box(0, [("1", 0.9)], sims, ENTRIES))
    check("list: no matrix keeps the look-alike fallback", Mt.match_box(0, [("11", 0.9)], [("E14", 0.8)], numbered("14", "77"), None).entry_id, "E14")
    check("list: hinted_match passes the matrix on",
          Mt.hinted_match(0, [("144", 0.9)], [], numbered("14", "44", "22"), [], "", {"144": m144})[0].entry_id, "E14")

    # Weak reads through the start list, and burst totals
    check("usable: a weak read with a matrix joins the sure ones",
          Mt.usable_reads([("14", 0.9), ("1", 0.75), ("7", 0.6)], {"1": m1}, 0.85), [("14", 0.9), ("1", 0.75)])
    check("usable: no matrix keeps only the sure ones", Mt.usable_reads([("14", 0.9), ("1", 0.75)], None, 0.85), [("14", 0.9)])
    # box a reads 14 (1 at -1.73); box b reads 1 with a faint 4 after it (14 at +0.84): each alone a close call
    m_a = matrix({"1": .9, "4": .1}, {"4": .85, "-": .15})
    m_b = matrix({"1": .98, "-": .02}, {"-": .55, "4": .45}, {"-": .55, "4": .45})
    nums = numbered("1", "14", "44")
    check("burst: box a alone is no read", Mt.match_box(0, [("14", 0.78)], [], nums, {"14": m_a}).method, "none")
    check("burst: box b alone is no read", Mt.match_box(0, [("1", 0.8)], [], nums, {"1": m_b}).method, "none")
    pair = {"a": [BoxResult(0, "none")], "b": [BoxResult(0, "none")]}
    pair_weak = {"a": {0: [("14", 0.78)]}, "b": {0: [("1", 0.8)]}}
    pair_ctc = {"a": {0: {"14": m_a}}, "b": {0: {"1": m_b}}}
    out = Mt.agreeing_reads(pair, {"a": "g", "b": "g"}, pair_weak, nums, pair_ctc)
    check("burst: the two boxes' totals give 14", [(summary(out[f][0]), out[f][0].confidence) for f in "ab"],
          [(("number", "E14", ""), 0.78), (("number", "E14", ""), 0.8)])
    check("burst: list_read gives the totals", out["a"][0].list_read, "14/1>14 0.84, 1 -1.73 (burst of 2)")
    check("burst: different groups don't sum",
          summary(Mt.agreeing_reads(pair, {"a": "g", "b": "h"}, pair_weak, nums, pair_ctc)["a"][0]), ("none", "", ""))
    sure = dict(pair, c=[BoxResult(0, "number", "E1", "", 0.95)])
    out = Mt.agreeing_reads(sure, {"a": "g", "b": "g", "c": "g"}, pair_weak, nums, pair_ctc)
    check("burst: a sure read of another number keeps its frame and the group",
          [summary(out[f][0]) for f in "abc"], [("none", "", ""), ("none", "", ""), ("number", "E1", "")])
    out = Mt.agreeing_reads(dict(pair, c=[BoxResult(0, "number", "E14", "", 0.95)]), {"a": "g", "b": "g", "c": "g"},
                            pair_weak, nums, pair_ctc)
    check("burst: a sure read of the winner leaves the fusion on", summary(out["a"][0]), ("number", "E14", ""))
    check("burst: one frame with matrices falls back to string agreement",
          Mt.burst_list_read(["a", "b"], pair, pair_weak, {"a": pair_ctc["a"]}, nums), None)
    red_nums = {k: replace(e, colour="Red") if k == "E14" else e for k, e in nums.items()}
    blue = {f: [BoxResult(0, "none", colour="Blue")] for f in "ab"}
    check("burst: a colour clash drops the number",
          summary(Mt.agreeing_reads(blue, {"a": "g", "b": "g"}, pair_weak, red_nums, pair_ctc)["a"][0]), ("none", "", ""))
    check("hinted: a weak read outside the tag set doesn't drop the hint",
          Mt.hinted_match(0, [("44", 0.75)], [("E14", 0.9)], nums, ["Rally|Number|14"], "sponsor", None, 0.85)[1]["dropped"], False)

    # Noise numbers: a class "3" on every car, read beside three different start-list numbers
    grid = numbered("3", "14", "22", "7")
    with_3 = [[("14", 0.9), ("3", 0.9)], [("22", 0.9), ("3", 0.95)], [("7", 0.9), ("3", 0.9)], [("3", 0.9)]]
    noise = Mt.noise_numbers(with_3, grid, 0.85)
    check("noise: a number beside three start-list numbers is noise, with its partner count", noise, {"3": 3})
    check("noise: the box that also reads 14 is number 14",
          summary(Mt.match_box(0, Mt.without_noise(with_3[0], noise), [], grid)), ("number", "E14", ""))
    check("noise: the box that reads only 3 is still number 3",
          summary(Mt.match_box(0, Mt.without_noise(with_3[3], noise), [], grid)), ("number", "E3", ""))
    check("noise: two cars sharing a box twice make neither number noise",
          Mt.noise_numbers([[("14", 0.9), ("22", 0.9)], [("14", 0.95), ("22", 0.9)]], grid, 0.85), {})
    check("noise: a read under min_read is no partner and gains none",
          Mt.noise_numbers(with_3[:2] + [[("7", 0.8), ("3", 0.9)], [("3", 0.8), ("7", 0.9)]], grid, 0.85), {})
    check("noise: a number off the start list is no partner, but can be noise itself",
          Mt.noise_numbers([[("14", 0.9), ("500", 0.9), ("99", 0.9)], [("22", 0.9), ("500", 0.9)], [("7", 0.9), ("500", 0.9)]],
                           grid, 0.85), {"500": 3})
    passed = with_3[:3] + [[("3", 0.9)]] * 3
    check("noise: a real car beside three others in three boxes, alone in three more, is no noise",
          Mt.noise_numbers(passed, grid, 0.85), {})
    check("noise: a class number alone in a few boxes, beside a start-list number in most, stays noise",
          Mt.noise_numbers(passed[:5], grid, 0.85), {"3": 3})
    check("noise: boxes that read it under min_read don't count towards the share",
          Mt.noise_numbers(with_3[:3] + [[("3", 0.9)]] * 2 + [[("3", 0.8)]] * 4, grid, 0.85), {"3": 3})
    check("noise: a box reading only noise numbers keeps them all",
          Mt.without_noise([("3", 0.9), ("500", 0.9)], {"3": 3, "500": 4}), [("3", 0.9), ("500", 0.9)])

    shown = {"E14": Entry("E14", "14", "", (), shows=("44",)), "E44": Entry("E44", "44", "", ()),
             "E108": Entry("E108", "108", "", (), shows=("808",))}
    check("shows: a shown number held by no other entry identifies by number",
          summary(Mt.match_box(0, [("808", 0.9)], [("E14", 0.7)], shown)), ("number", "E108", ""))
    check("shows: a shown number another entry carries goes to livery (old 44 on car 14)",
          summary(Mt.match_box(0, [("44", 0.9)], [("E14", 0.99), ("E44", 0.40)], shown)), ("livery", "E14", ""))
    check("shows: the entered car still wins its own number on livery",
          summary(Mt.match_box(0, [("44", 0.9)], [("E44", 0.99), ("E14", 0.40)], shown)), ("livery", "E44", ""))
    check("shows: livery after a shared number picks only between the cars carrying it",
          summary(Mt.match_box(0, [("44", 0.9)], [("E108", 0.99), ("E14", 0.80), ("E44", 0.40)], shown)), ("livery", "E14", ""))
    read_44 = {"44": [[0.9 if j == c else 0.01 for j in range(11)] for c in (5, 0, 5)]}
    check("shows: a start-list read of a shared number also limits livery to its cars",
          summary(Mt.match_box(0, [("44", 0.9)], [("E108", 0.99), ("E14", 0.80), ("E44", 0.40)], shown, read_44)),
          ("livery", "E14", ""))
    check("shows: the number index lists both cars for a shared number", Mt.number_index(shown)["44"], ["E14", "E44"])
    check("shows: list_scores scores shown numbers",
          sorted(Mt.list_scores([("808", 0.9)], {"808": [[0.9 if j == c else 0.01 for j in range(11)] for c in (9, 0, 1, 0, 9)]}, shown)[0]),
          ["108", "14", "44", "808"])
    check("shows: a read of a colour-removed car's number still drops the colour pool",
          Mt.colour_pool({"E14": replace(shown["E14"], colour="Blue"), "E44": replace(shown["E44"], colour="Red")},
                         "Blue", [("44", 0.95)], [("E14", 0.9)], 0.85)[1]["reason"], "number_outside")

    # closer_car_match: a match unlike its anchors moves to the closer car, or is dropped
    cars = {"14": Entry("14", "14", "", ()), "808": Entry("808", "808", "", (), car="108"),
            "108": Entry("108", "108", "", (), car="108"), "60": Entry("60", "60", "", ())}
    doubt = BoxResult(0, "livery", "14", confidence=0.7, colour="Blue")

    def closer(other_car, own, other, margin, taken=(), sure=()):
        got = Mt.closer_car_match(doubt, own, other_car, other, cars, margin, 0.6, taken, sure)
        return got.method, got.entry_id, got.alt_entry_id, got.confidence, got.anchor_flag, got.colour

    check("closer car: a lead of the margin or more moves the match and keeps the flag",
          closer("60", 0.70, 0.86, 0.1), ("livery", "60", "14", 0.86, True, "Blue"))
    check("closer car: a lead of exactly the margin moves", closer("60", 0.761, 0.861, 0.1)[:2], ("livery", "60"))
    sure_frames = {"a": [BoxResult(0, "number", "808", confidence=0.95)], "b": [BoxResult(0, "number", "60", confidence=0.85)],
                   "c": [BoxResult(0, Mt.HAND, "14", confidence=1.0)], "d": [BoxResult(0, "livery", "60", confidence=0.99)],
                   "e": [BoxResult(0, "number", "60", confidence=0.9)]}
    check("sure cars: a 0.9+ number read (by car) or a hand tag counts, per burst; weak reads and livery don't",
          Mt.sure_cars(sure_frames, {"a": "1", "b": "1", "c": "2", "d": "2"}, cars, 0.9),
          {"1": {"108"}, "2": {"14"}, "e": {"60"}})
    check("closer car: a burst or neighbour match never moves",
          [Mt.closer_car_match(replace(doubt, method=m), 0.5, "60", 0.9, cars, 0.1, 0.6).method for m in ("burst", "neighbour")],
          ["none", "none"])
    check("closer car: a lead under the margin drops", closer("60", 0.80, 0.86, 0.1), ("none", "", "14", 0.0, True, "Blue"))
    check("closer car: margin 0 never moves", closer("60", 0.10, 0.99, 0)[:2], ("none", ""))
    check("closer car: no closer car drops", closer("", 0.50, None, 0.1)[:2], ("none", ""))
    check("closer car: a double-driven car can't say which driver, so drops", closer("108", 0.50, 0.90, 0.1)[:2], ("none", ""))
    check("closer car: a closer car under the anchor floor drops", closer("60", 0.30, 0.55, 0.1)[:2], ("none", ""))
    check("closer car: the photo's other box is that car already, so drops", closer("60", 0.50, 0.90, 0.1, {"60"})[:2], ("none", ""))
    check("closer car: the burst's sure cars name another car, so drops", closer("60", 0.50, 0.90, 0.1, sure={"108"})[:2], ("none", ""))
    check("closer car: the burst's sure cars include the closer car, so moves",
          closer("60", 0.50, 0.90, 0.1, sure={"108", "60"})[:2], ("livery", "60"))

    # new numbers: a number no entry has, read on 3+ frames of one burst (ticket 88)
    burst = {"f1": "b1", "f2": "b1", "f3": "b1", "f4": "b1", "g1": "b2", "g2": "b2", "g3": "b2"}
    three = {"f1": {0: [("115", 0.9)]}, "f2": {0: [("115", 0.8), ("16", 0.95)]}, "f3": {1: [("115", 0.7)]}}
    check("new numbers: 3 frames of a burst read 115, no entry has it",
          Mt.new_numbers(three, burst, ENTRIES, {}), {"115": {"f1": [0], "f2": [0], "f3": [1]}})
    check("new numbers: the frames count however the box was matched (16 beside it on f2)",
          list(Mt.new_numbers(three, burst, ENTRIES, {})), ["115"])
    check("new numbers: 2 frames are not enough",
          Mt.new_numbers({k: three[k] for k in ("f1", "f2")}, burst, ENTRIES, {}), {})
    check("new numbers: 3 frames across 2 bursts are not enough",
          Mt.new_numbers({"f1": three["f1"], "f2": three["f2"], "g1": {0: [("115", 0.9)]}}, burst, ENTRIES, {}), {})
    check("new numbers: a frame alone is its own burst",
          Mt.new_numbers({"x1": {0: [("115", 0.9)]}, "x2": {0: [("115", 0.9)]}, "x3": {0: [("115", 0.9)]}}, {}, ENTRIES, {}), {})
    check("new numbers: reads below WEAK_READ_MIN don't count",
          Mt.new_numbers({**three, "f3": {1: [("115", 0.69)]}}, burst, ENTRIES, {}), {})
    check("new numbers: a number an entry has is never new",
          Mt.new_numbers({f: {0: [("44", 0.9)]} for f in ("f1", "f2", "f3")}, burst, ENTRIES, {}), {})
    check("new numbers: only 1 to 3 digits, as Find New Entries lists",
          Mt.new_numbers({f: {0: [("1150", 0.9), ("A11", 0.9)]} for f in ("f1", "f2", "f3")}, burst, ENTRIES, {}), {})
    check("new numbers: a noise number is never new",
          Mt.new_numbers(three, burst, ENTRIES, {"115": 3}), {})
    check("new numbers: two boxes of one frame count that frame once",
          Mt.new_numbers({"f1": {0: [("115", 0.9)], 1: [("115", 0.9)]}, "f2": three["f2"]}, burst, ENTRIES, {}), {})
    check("new numbers: both of a frame's boxes are named when the burst qualifies",
          Mt.new_numbers({**three, "f1": {0: [("115", 0.9)], 1: [("115", 0.8)]}}, burst, ENTRIES, {})["115"]["f1"], [0, 1])
    check("new numbers: two bursts each qualifying both count",
          {d: sorted(f) for d, f in Mt.new_numbers({**three, **{g: {0: [("115", 0.9)]} for g in ("g1", "g2", "g3")}},
                                                   burst, ENTRIES, {}).items()},
          {"115": ["f1", "f2", "f3", "g1", "g2", "g3"]})

    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

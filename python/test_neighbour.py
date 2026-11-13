# Run with: python python/test_neighbour.py
# Exercises neighbour.py's number-order aid and look-alike check; no models or files needed.

import os
import sys
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import neighbour as N
from match import BoxResult, Entry

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


def entries(*numbers):
    return {n: Entry(n, n, "", ()) for n in numbers}


def seen(number, conf=0.99):
    return BoxResult(0, "number", number, confidence=conf)


def unmatched(digits):
    return BoxResult(0, "none", unmatched_number=digits)


def shoot(*boxes, start=100, step=10):
    """One frame per box, each its own group, `step` seconds apart."""
    frames = {f"f{i}": [b] for i, b in enumerate(boxes)}
    times = {f"f{i}": start + i * step for i in range(len(boxes))}
    return frames, {}, times


def run_tests():
    E = entries("33", "34", "35", "37", "38")

    check("positions skip gaps and are ordered", N.entry_positions(E), {33: 0, 34: 1, 35: 2, 37: 3, 38: 4})
    check("positions collapse leading zeros", N.entry_positions(entries("007", "7", "8")), {7: 0, 8: 1})
    check("positions skip non-digit numbers", N.entry_positions(entries("12", "A1", "")), {12: 0})
    check("distance wraps around the end", N.position_distance(0, 4, 5), 1)
    check("distance inside the list", N.position_distance(1, 3, 5), 2)
    check("look-alike digit is a candidate", N.candidates_for("36", E), ["35"])
    check("an inserted digit is a candidate", N.candidates_for("335", E), ["33", "35"])
    check("a dropped digit is a candidate", N.candidates_for("3", E), ["33", "34", "35", "37", "38"])
    check("an exact match is not a candidate", N.candidates_for("37", E), [])

    frames, burst, times = shoot(seen("34"), unmatched("36"), seen("37"))
    check("weight 0 returns the input unchanged", N.neighbour_aid(frames, burst, times, E, 5, 0.0) is frames, True)
    check("empty entries returns the input unchanged", N.neighbour_aid(frames, burst, times, {}, 5, 1.0) is frames, True)

    out = N.neighbour_aid(frames, burst, times, E, 5, 1.0)
    got = out["f1"][0]
    check("a doubtful read resolves toward its neighbours", (got.method, got.entry_id), ("neighbour", "35"))
    check("resolved confidence is the support", round(got.confidence, 3), round(1 - 1 / 6, 3))
    check("the unmatched digits are kept", got.unmatched_number, "36")
    check("other frames are untouched", out["f0"], frames["f0"])

    # 35 sits one place from both neighbours: support 1 - 1/6, needs weight 1/6 or more
    out = N.neighbour_aid(frames, burst, times, E, 5, 0.1)
    check("low weight keeps support below the accept bar", out["f1"][0].method, "none")
    out = N.neighbour_aid(frames, burst, times, E, 5, 1 / 6)
    check("weight exactly at the bar resolves", out["f1"][0].method, "neighbour")
    out = N.neighbour_aid(frames, burst, times, E, 5, 0.3)
    check("a weight under 0.5 still resolves", out["f1"][0].method, "neighbour")
    same, burst, times = shoot(seen("35"), unmatched("36"), seen("38"))
    check("a tiny weight takes the same car nearby",
          N.neighbour_aid(same, burst, times, E, 5, 0.01)["f1"][0].entry_id, "35")

    far, burst, times = shoot(seen("10"), unmatched("36"), seen("10"))
    far_E = entries("10", "20", "30", "35", "40", "50", "60", "70", "80", "90")
    out = N.neighbour_aid(far, burst, times, far_E, 1, 1.0)
    check("neighbours beyond the tolerance give no support", out["f1"][0].method, "none")

    none_E = entries("20", "21", "22")
    frames, burst, times = shoot(seen("20"), unmatched("99"), seen("21"))
    check("no candidate stays none", N.neighbour_aid(frames, burst, times, none_E, 5, 1.0)["f1"][0].method, "none")

    # A clear read is never changed or flagged, even when it fits nothing nearby.
    frames, burst, times = shoot(seen("33"), seen("38", 0.99), seen("33"))
    out = N.neighbour_aid(frames, burst, times, E, 0, 1.0)
    check("a clear read is never flagged", out["f1"][0].order_flag, False)

    # A doubtful read that matches no neighbour is flagged and kept.
    spread = entries(*[str(n) for n in range(10, 40)])
    frames, burst, times = shoot(seen("10"), seen("30", 0.85), seen("11"))
    out = N.neighbour_aid(frames, burst, times, spread, 2, 1.0)
    check("a misfit doubtful read is flagged", out["f1"][0].order_flag, True)
    check("a flagged read keeps its entry", (out["f1"][0].method, out["f1"][0].entry_id), ("number", "30"))
    out = N.neighbour_aid(frames, burst, times, spread, 2, 0.4)
    check("no flag below the flag weight", out["f1"][0].order_flag, False)

    # The end of a loop is next to the start: 39 then 10 is not a misfit.
    frames, burst, times = shoot(seen("39"), seen("10", 0.85), seen("11"))
    out = N.neighbour_aid(frames, burst, times, spread, 2, 1.0)
    check("wrap-around neighbours support a read", out["f1"][0].order_flag, False)

    # The same number in adjacent groups is support.
    frames, burst, times = shoot(seen("20"), seen("20", 0.85))
    out = N.neighbour_aid(frames, burst, times, spread, 2, 1.0)
    check("the same number next door counts as support", out["f1"][0].order_flag, False)

    # Neighbours across a stage break or without a time are ignored.
    frames, burst, times = shoot(seen("11"), seen("30", 0.85), seen("12"), step=N.NEIGHBOUR_MAX_GAP_S + 1)
    out = N.neighbour_aid(frames, burst, times, spread, 2, 1.0)
    check("neighbours across a stage break are ignored", out["f1"][0].order_flag, False)
    frames, burst, times = shoot(seen("11"), seen("30", 0.85), seen("12"))
    del times["f0"], times["f2"]
    out = N.neighbour_aid(frames, burst, times, spread, 2, 1.0)
    check("untimed neighbours are ignored", out["f1"][0].order_flag, False)
    times["f1"] = 0
    check("an untimed photo is left alone", N.neighbour_aid(frames, burst, times, spread, 2, 1.0)["f1"][0].order_flag, False)

    # Frames of one burst group share what they saw: the group is one position in the sequence.
    frames = {"a": [seen("30")], "b": [seen("30", 0.85)], "c": [seen("12")]}
    out = N.neighbour_aid(frames, {"a": "g", "b": "g", "c": "h"}, {"a": 100, "b": 105, "c": 110}, spread, 2, 1.0)
    check("a group's own frames don't support each other", out["b"][0].order_flag, True)

    # Degenerate sizes don't raise.
    check("no frames", N.neighbour_aid({}, {}, {}, E, 5, 1.0), {})
    frames, burst, times = shoot(unmatched("36"))
    check("one group, no neighbours", N.neighbour_aid(frames, burst, times, E, 5, 1.0)["f0"][0].method, "none")
    one = entries("5")
    frames, burst, times = shoot(seen("5", 0.85), seen("5", 0.85))
    check("one entry in the list", N.neighbour_aid(frames, burst, times, one, 5, 1.0)["f0"][0].order_flag, False)

    # Look-alike: an unread box takes the nearby car its crop resembles.
    blank = BoxResult(0, "none")
    frames, burst, times = shoot(seen("34"), blank, seen("38"))

    def sims(table):
        return lambda fid, box, ofid, obox: table.get(ofid)

    out = N.neighbour_aid(frames, burst, times, E, 5, 0.5, sims({"f0": 0.92, "f2": 0.60}))
    got = out["f1"][0]
    check("an unread box takes the car it looks like", (got.method, got.entry_id, got.via), ("neighbour", "34", "lookalike"))
    check("look-alike confidence is the sim", got.confidence, 0.92)
    out = N.neighbour_aid(frames, burst, times, E, 5, 0.5, sims({"f0": 0.80, "f2": 0.60}))
    check("a look-alike under the floor is left", out["f1"][0].method, "none")
    out = N.neighbour_aid(frames, burst, times, E, 5, 0.5, sims({"f0": 0.92, "f2": 0.90}))
    check("two cars that look alike are left", out["f1"][0].method, "none")
    out = N.neighbour_aid(frames, burst, times, E, 5, 0.5, sims({}))
    check("no embeddings leave the box", out["f1"][0].method, "none")
    check("no similar callback leaves the box", N.neighbour_aid(frames, burst, times, E, 5, 0.5)["f1"][0].method, "none")
    frames, burst, times = shoot(seen("34"), unmatched("36"), seen("37"))
    out = N.neighbour_aid(frames, burst, times, E, 5, 1.0, sims({"f0": 0.99, "f2": 0.10}))
    check("a number-order resolve comes before the look-alike", (out["f1"][0].entry_id, out["f1"][0].via), ("35", "order"))
    frames, burst, times = shoot(seen("34"), BoxResult(-1, "none"), seen("38"))
    out = N.neighbour_aid(frames, burst, times, E, 5, 0.5, sims({"f0": 0.99}))
    check("a frame with no vehicle is not looked at", out["f1"][0].method, "none")

    # Colour tie-break on number order: 33 and 37 tie at full support for a read "3".
    def painted(colours):
        return {n: Entry(n, n, "", (), "", c) for n, c in colours.items()}
    C = painted({"33": "Red", "35": "", "37": "Blue"})
    frames, burst, times = shoot(seen("33"), BoxResult(0, "none", unmatched_number="3", colour="Red"), seen("37"))
    out = N.neighbour_aid(frames, burst, times, C, 5, 1.0)
    check("an order tie on a red box goes to the Red entry", (out["f1"][0].method, out["f1"][0].entry_id), ("neighbour", "33"))
    check("an order tie with no entry colours stays a tie",
          N.neighbour_aid(frames, burst, times, painted({"33": "", "35": "", "37": ""}), 5, 1.0)["f1"][0].method, "none")
    frames, burst, times = shoot(seen("33"), unmatched("3"), seen("37"))
    check("an order tie on a box with no colour stays a tie", N.neighbour_aid(frames, burst, times, C, 5, 1.0)["f1"][0].method, "none")

    # Colour tie-break on look-alike: a nearby box of another colour can't lend its entry.
    def lookalike_frames(near, here):
        return shoot(replace(seen("34"), colour=near), BoxResult(0, "none", colour=here), replace(seen("38"), colour=near))
    frames, burst, times = lookalike_frames("White", "Red")
    out = N.neighbour_aid(frames, burst, times, E, 5, 0.5, sims({"f0": 0.92, "f2": 0.60}))
    check("a white look-alike can't lend to a red box", out["f1"][0].method, "none")
    frames, burst, times = lookalike_frames("Red", "Red")
    out = N.neighbour_aid(frames, burst, times, E, 5, 0.5, sims({"f0": 0.92, "f2": 0.60}))
    check("a red look-alike lends to a red box", (out["f1"][0].method, out["f1"][0].entry_id), ("neighbour", "34"))
    frames, burst, times = lookalike_frames("", "")
    out = N.neighbour_aid(frames, burst, times, E, 5, 0.5, sims({"f0": 0.92, "f2": 0.60}))
    check("a look-alike with no colours lends as before", (out["f1"][0].method, out["f1"][0].entry_id), ("neighbour", "34"))

    # Library neighbours: unselected tagged photos lend support, rows as read from the CSV (strings).
    frames, burst, times = {"7": [unmatched("36")]}, {}, {"7": 200}
    alone = N.neighbour_aid(frames, burst, times, E, 5, 1.0)
    check("a lone doubtful read stays unread", alone["7"][0].method, "none")
    rows = [["5", "190", "34"], ["9", "210", "37"]]
    lf, lb, lt = N.with_library_neighbours(frames, burst, times, rows, E)
    out = N.neighbour_aid(lf, lb, lt, E, 5, 1.0)
    check("library neighbours resolve a doubtful read", (out["7"][0].method, out["7"][0].entry_id), ("neighbour", "35"))
    check("the input dicts are not changed", (sorted(frames), burst, times), (["7"], {}, {"7": 200}))
    check("library frames carry the prefix", sorted(lf), ["7", "lib:5", "lib:9"])

    rows = [["5", "190", "99"], ["6", "", "34"], ["8", "0", "34"], ["7", "195", "34"], ["9", "210", "37"]]
    lf, lb, lt = N.with_library_neighbours(frames, burst, times, rows, E)
    check("unknown, untimed and selected rows are dropped", sorted(lf), ["7", "lib:9"])

    rows = [["1", "180", "34"], ["2", "181", "34"], ["3", "182", "37"], ["4", "183", "34"]]
    _, lb, _ = N.with_library_neighbours(frames, burst, times, rows, E)
    check("consecutive rows of one entry form one group",
          [lb["lib:1"], lb["lib:2"], lb["lib:3"], lb["lib:4"]], ["lib:1", "lib:1", "lib:3", "lib:4"])

    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

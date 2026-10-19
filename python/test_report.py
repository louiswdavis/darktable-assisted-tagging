# Run with: python python/test_report.py
# Exercises report.py's categories, levers, summary and rendering; no models or files needed.

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report as R

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


ENTRIES = {"a": {"team": "", "number": "1", "tags": ["T|X", "T|X|A"], "refs": 3},
           "b": {"team": "", "number": "2", "tags": ["T|X", "T|X|B"], "refs": 0},
           "c": {"team": "Y", "number": "3", "tags": ["T|Y", "T|Y|C"], "refs": 2}}


def box(method="none", decided_by="margin_too_small", cands=(("a", 0.7), ("b", 0.69)), gap=0.04, unmatched="",
        conflict=False, ocr=(), n=0):
    return {"box": n, "bbox": [0, 0, 1, 1], "entry": "a" if method not in ("none",) else "", "alt_entry": "",
            "method": method, "confidence": 0.7, "candidates": [list(c) for c in cands], "ocr": [list(o) for o in ocr],
            "decided_by": decided_by, "gap": gap, "unmatched_number": unmatched, "conflict": conflict}


def image(boxes, status="ok", shot="solo"):
    return {"shot": shot, "status": status, "file": "f", "frame": [1, 1], "boxes": boxes}


def data(images, skipped=()):
    return {"collection": "demo", "thresholds": {"min_sim": 0.6, "min_margin": 0.05, "reference_margin": 0.1},
            "entries": ENTRIES, "images": images, "skipped": list(skipped)}


def run_tests():
    check("categorize: number, livery, burst and pooled are identified",
          [R.categorize(box(m, m)) for m in ("number", "livery", "burst", "pooled")], ["identified"] * 4)
    check("categorize: team", R.categorize(box("team", "team")), "team-obvious")
    check("categorize: conflict wins over the method", R.categorize(box("conflict", "conflict", conflict=True)), "conflict")
    check("categorize: no references", R.categorize(box(decided_by="no_references", cands=())), "no-references")
    check("categorize: no references wins over unmatched digits",
          R.categorize(box(decided_by="no_references", cands=(), unmatched="77")), "no-references")
    check("categorize: unmatched number", R.categorize(box(unmatched="77")), "number-unmatched")
    check("categorize: below min sim", R.categorize(box(decided_by="below_min_sim", cands=(("a", 0.4),))), "weak-match")
    check("categorize: small margin", R.categorize(box()), "weak-match")

    def podbox(entry, yellow, method="number"):
        return dict(box(method), entry=entry, pod={"yellow": yellow, "aspect": 3.0})

    pod_entries = {"a": dict(ENTRIES["a"], camera="yellow"), "b": dict(ENTRIES["b"], camera="black")}
    pod_data = dict(data({"1": image([podbox("a", 0.01)]), "2": image([podbox("a", 0.0007)]),
                          "3": image([podbox("b", 0.0)]), "4": image([podbox("b", 0.01)]),
                          "5": image([podbox("a", 0.01, "livery")])}), entries=pod_entries)
    stats = R.pod_stats(pod_data, R.rows(pod_data))
    check("pod_stats: right, unclear and wrong against the entry's camera", stats["verdicts"],
          {"right": 2, "unclear": 1, "wrong": 1})
    check("pod_stats: only number-identified frames count", sum(d["boxes"] for d in stats["drivers"]), 4)
    check("pod_stats: percentiles", (stats["yellow_p10"], stats["black_p90"]), (0.001, 0.01))
    check("pod_stats: no camera colours, no stats", R.pod_stats(data({"1": image([podbox("a", 0.01)])}), []), {})

    check("lever: shared tag, no team set", R.lever("weak-match", box(), ENTRIES), "set team on a and b")
    other = box(cands=(("a", 0.7), ("c", 0.69)))
    check("lever: no shared tag, runner-up has refs", R.lever("weak-match", other, ENTRIES), "")
    check("lever: top entry without references",
          R.lever("weak-match", box(cands=(("b", 0.7), ("c", 0.69))), ENTRIES), "b needs references")
    check("lever: below min sim", R.lever("weak-match", box(decided_by="below_min_sim", cands=(("a", 0.4),)), ENTRIES),
          "weak match, add references from this angle")
    check("lever: unmatched number", R.lever("number-unmatched", box(unmatched="77;5"), ENTRIES), "no entry has number 77 or 5")
    check("lever: no references", R.lever("no-references", box(cands=()), ENTRIES), "no references yet, add some")
    check("lever: weak-match with no candidates", R.lever("weak-match", box(cands=()), ENTRIES), "")
    check("lever: identified has none", R.lever("identified", box("number", "number"), ENTRIES), "")

    check("margin and top1 with one candidate", (R.top1_of(box(cands=(("a", 0.7),))), R.margin_of(box(cands=(("a", 0.7),)))),
          (0.7, 0.0))
    check("margin and top1 with none", (R.top1_of(box(cands=())), R.margin_of(box(cands=()))), (0.0, 0.0))

    d = data({"1": image([box("number", "number", n=0), box(n=1)], shot="pack"),
              "2": image([], status="no_vehicle", shot=""), "3": image([], status="error", shot="")}, skipped=["9"])
    all_rows = R.rows(d)
    check("rows: boxes, no-vehicle and already-tagged images; errors left out",
          sorted((r["image"], r["category"]) for r in all_rows),
          [("1", "identified"), ("1", "weak-match"), ("2", "no-vehicle"), ("9", "already-tagged")])
    s = R.summarize(d, all_rows)
    check("summarize: total, errors, rate", (s["total"], s["errors"], s["identified_rate"]), (4, 1, 0.25))
    check("summarize: medians only for populated categories", s["medians"], {"weak-match": {"top1": 0.7, "margin": 0.01}})

    empty = data({})
    es = R.summarize(empty, R.rows(empty))
    check("summarize: an empty run has zero shares and no medians", (es["total"], es["identified_rate"], es["medians"]),
          (0, 0.0, {}))
    check("render: an empty run renders", "0 vehicles/images" in R.render_md(empty, [], es, 20), True)

    weak = [{**R.rows(data({"1": image([box(cands=((f"a", 0.7 + i / 100), ("b", 0.5)))])}))[0], "image": f"i{i}"} for i in range(3)]
    ws = R.summarize(d, weak)
    md = R.render_md(d, weak, ws, 1)
    check("render: top=1 lists the worst box and counts the rest", ("`i0`" in md, "`i1`" in md, "… 2 more in report.json" in md),
          (True, False, True))
    check("render: top=0 has summary only", "## weak-match" in R.render_md(d, weak, ws, 0), False)

    weird = data({"x|y_z": image([box(cands=(("a|b_c", 0.7), ("b", 0.69)))])})
    wmd = R.render_md(weird, R.rows(weird), R.summarize(weird, R.rows(weird)), 5)
    check("render: ids with markdown characters sit in code spans", ("`x|y_z`" in wmd, "`a|b_c`" in wmd), (True, True))

    hinted = data({"x": image([dict(box(), hint={"prefixes": ["F1|Red Bull"], "source": "tag", "restricted": 2,
                                                 "dropped": True, "reason": "below_min_sim"})])})
    hmd = R.render_md(hinted, R.rows(hinted), R.summarize(hinted, R.rows(hinted)), 5)
    check("render: a dropped hint is listed and counted", ("hint `Red Bull` (tag) dropped (below_min_sim)" in hmd,
                                                           "hints: 1 applied, 1 dropped" in hmd), (True, True))
    check("render: no hint, no hint line", "hints:" in R.render_md(d, R.rows(d), R.summarize(d, R.rows(d)), 5), False)

    with tempfile.TemporaryDirectory() as tmp:
        prefix = os.path.join(tmp, "sub", "c.report")
        md_path, json_path = R.write_report(d, prefix, 20)
        out = json.load(open(json_path, encoding="utf-8"))
        check("write_report: both files, every row carries its category",
              (os.path.isfile(md_path), [r["category"] for r in out["rows"]]),
              (True, ["already-tagged", "identified", "weak-match", "no-vehicle"]))

    print("")
    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

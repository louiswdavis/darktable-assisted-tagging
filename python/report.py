"""Debug report built from a run's boxes.json: every detected vehicle gets one category, the run
summary counts them, and the worst boxes per category are listed with their numbers and a lever.

Standalone: report.py BOXES_JSON OUT_PREFIX [--report-top N]  (writes OUT_PREFIX.md and .json)
"""

import argparse
import json
import os
import statistics
import sys

from pod import pod_colour
from sponsors import SPONSOR_MIN_CONF

CATEGORIES = ("identified", "team-obvious", "weak-match", "no-references", "number-unmatched",
              "conflict", "already-tagged", "no-vehicle")
IDENTIFIED_METHODS = ("number", "livery", "burst", "pooled")
# categories whose boxes are listed one by one; the rest are only counted
DETAIL_CATEGORIES = ("team-obvious", "weak-match", "no-references", "number-unmatched", "conflict", "no-vehicle")
MEDIAN_CATEGORIES = ("team-obvious", "weak-match")
# detector score bands [from, to); the first band also holds everything below the cutoff
DETECTOR_BANDS = ((0.0, 0.30), (0.30, 0.40), (0.40, 0.50), (0.50, 0.70), (0.70, 1.01))
UNHINTED_CATEGORIES = ("team-obvious", "weak-match", "no-references")
SUGGEST_MIN_LEN = 4  # shorter OCR words are mostly noise
SUGGEST_MIN_BOXES = 2  # identified boxes a word must appear on


def top1_of(box: dict) -> float:
    c = box.get("candidates") or []
    return c[0][1] if c else 0.0


def margin_of(box: dict) -> float:
    c = box.get("candidates") or []
    return c[0][1] - c[1][1] if len(c) > 1 else 0.0


def categorize(box: dict) -> str:
    """The one category of a boxes.json box record. Precedence: conflict, identified, team,
    then the failures of a `none` result (no references before unmatched number before weak)."""
    if box.get("conflict"):
        return "conflict"
    if box["method"] in IDENTIFIED_METHODS:
        return "identified"
    if box["method"] == "team":
        return "team-obvious"
    if box["decided_by"] == "no_references":
        return "no-references"
    if box.get("unmatched_number"):
        return "number-unmatched"
    return "weak-match"


def lever(category: str, box: dict, entries: dict) -> str:
    """One suggested next step from a fixed rule list; "" when no rule applies."""
    cands = box.get("candidates") or []
    if category == "no-references":
        return "no references yet, add some"
    if category == "number-unmatched":
        return "no entry has number " + box["unmatched_number"].replace(";", " or ")
    if category != "weak-match" or not cands:
        return ""
    top = entries.get(cands[0][0], {})
    if box["decided_by"] == "margin_too_small" and len(cands) > 1:
        a, b = entries.get(cands[0][0], {}), entries.get(cands[1][0], {})
        if not a.get("team") and not b.get("team") and set(a.get("tags", [])) & set(b.get("tags", [])):
            return f"set team on {cands[0][0]} and {cands[1][0]}"
    if top.get("refs") == 0:
        return f"{cands[0][0]} needs references"
    if box["decided_by"] == "below_min_sim":
        return "weak match, add references from this angle"
    return ""


def rows(data: dict) -> list:
    """One flat row per box, plus one per already-tagged and no-vehicle image. Images that
    failed analysis are left out (see summarize's `errors`)."""
    entries, out = data["entries"], []
    for image_id in data["skipped"]:
        out.append({"image": image_id, "box": -1, "category": "already-tagged"})
    for image_id, img in data["images"].items():
        if img["status"] == "no_vehicle":
            out.append({"image": image_id, "box": -1, "category": "no-vehicle", "top1": 0.0,
                        "burst": img.get("burst", ""), "note": img.get("note", "")})
        for box in img["boxes"]:
            cat = categorize(box)
            out.append({"image": image_id, "box": box["box"], "category": cat, "shot": img["shot"],
                        "entry": box["entry"], "alt_entry": box["alt_entry"], "method": box["method"],
                        "score": box.get("score"), "decided_by": box["decided_by"], "gap": box["gap"],
                        "top1": round(top1_of(box), 4),
                        "margin": round(margin_of(box), 4), "candidates": box["candidates"],
                        "ocr": box["ocr"], "ocr_trace": box.get("ocr_trace", []), "pod": box.get("pod", {}), "hint": box.get("hint", {}),
                        "lever": lever(cat, box, entries)})
    return out


def summarize(data: dict, all_rows: list) -> dict:
    total = len(all_rows)
    counts = {c: sum(1 for r in all_rows if r["category"] == c) for c in CATEGORIES}
    medians = {}
    for c in MEDIAN_CATEGORIES:
        sel = [r for r in all_rows if r["category"] == c]
        if sel:
            medians[c] = {"top1": round(statistics.median(r["top1"] for r in sel), 4),
                          "margin": round(statistics.median(r["margin"] for r in sel), 4)}
    return {"total": total,
            "errors": sum(1 for i in data["images"].values() if i["status"] == "error"),
            "counts": counts,
            "shares": {c: (counts[c] / total if total else 0.0) for c in CATEGORIES},
            "identified_rate": counts["identified"] / total if total else 0.0,
            "medians": medians}


def burst_timing(data: dict) -> dict:
    """Per-burst capture timing from boxes.json: frames, span, the within-burst gaps and the gap to
    the next burst. Bursts with no capture times are counted, not described."""
    groups = {}
    for image_id, img in data["images"].items():
        groups.setdefault(str(img.get("burst", "")), []).append((img.get("time"), image_id, img))
    timed, untimed = [], 0
    for burst, members in groups.items():
        times = sorted(t for t, _, _ in members if t is not None)
        if not times:
            untimed += 1
            continue
        gaps = [b - a for a, b in zip(times, times[1:])]
        statuses = [i["status"] for _, _, i in members]
        timed.append({"burst": burst, "frames": len(members), "start": times[0], "end": times[-1],
                      "span": times[-1] - times[0], "max_gap": max(gaps, default=0),
                      "no_vehicle": statuses.count("no_vehicle"), "ok": statuses.count("ok")})
    timed.sort(key=lambda b: b["start"])
    for cur, nxt in zip(timed, timed[1:]):
        cur["gap_to_next"] = nxt["start"] - cur["end"]
    if timed:
        timed[-1]["gap_to_next"] = None
    within = [b["max_gap"] for b in timed]
    return {"bursts": timed, "untimed": untimed,
            "frame_counts": sorted(b["frames"] for b in timed),
            "max_gap_counts": {str(g): within.count(g) for g in sorted(set(within))}}


def detector_bands(all_rows: list) -> list:
    """Boxes grouped by detector score band, with how many were identified: shows what the
    DETECTOR_MIN_SCORE cutoff is letting in. Boxes without a score (older boxes.json) are left out."""
    bands = []
    for lo, hi in DETECTOR_BANDS:
        sel = [r for r in all_rows if r.get("score") is not None and lo <= r["score"] < hi]
        if sel:
            bands.append({"from": lo, "to": hi, "boxes": len(sel),
                          "identified": sum(1 for r in sel if r["category"] == "identified")})
    return bands


def quantile(values: list, q: float) -> float:
    """The q-th quantile (0-1) of a non-empty list, nearest rank."""
    s = sorted(values)
    return s[min(int(q * len(s)), len(s) - 1)]


def pod_stats(data: dict, all_rows: list) -> dict:
    """How the camera-pod reading does on frames whose driver is known from the race number (the
    only labelled data a run has), for the entries that have a `camera` colour:
    {drivers: [{entry, camera, boxes, min, median, max}], verdicts: {right, unclear, wrong},
    yellow_p10, black_p90}. `yellow_p10` is the 10th percentile yellow share over yellow-pod frames and
    `black_p90` the 90th over black-pod side-on frames: YELLOW_MIN_FRAC should sit below the first and
    above the second. Empty when no labelled frame has a pod reading."""
    cameras = {eid: e.get("camera", "") for eid, e in data["entries"].items()}
    labelled = [r for r in all_rows if r.get("method") == "number" and r.get("pod") and cameras.get(r["entry"])]
    if not labelled:
        return {}
    by_entry: dict = {}
    verdicts = {"right": 0, "unclear": 0, "wrong": 0}
    for r in labelled:
        by_entry.setdefault(r["entry"], []).append(r["pod"]["yellow"])
        read = pod_colour(r["pod"])
        verdicts["unclear" if not read else "right" if read == cameras[r["entry"]] else "wrong"] += 1
    drivers = [{"entry": eid, "camera": cameras[eid], "boxes": len(v), "min": min(v),
                "median": statistics.median(v), "max": max(v)} for eid, v in sorted(by_entry.items())]
    yellow = [y for eid, v in by_entry.items() if cameras[eid] == "yellow" for y in v]
    black = [r["pod"]["yellow"] for r in labelled if cameras[r["entry"]] == "black" and r["pod"]["aspect"] >= 2.0]
    return {"drivers": drivers, "verdicts": verdicts,
            "yellow_p10": quantile(yellow, 0.1) if yellow else None,
            "black_p90": quantile(black, 0.9) if black else None}


def sponsor_suggestions(data: dict, all_rows: list) -> list:
    """Words OCR read confidently on identified boxes that point at one tag prefix, not yet in
    `sponsor_keywords`: [{word, prefix, identified, other, unhinted}], best first. `prefix` is the
    entry's shallowest tag; `other` counts identified boxes of a different prefix carrying the word;
    `unhinted` counts team-obvious/weak-match/no-references boxes that carry it (what it would hint)."""
    known = data.get("sponsor_keywords", {})
    entries = data["entries"]
    seen = {}
    for r in all_rows:
        if r["category"] == "no-vehicle" or "ocr_trace" not in r:
            continue
        words = {t.lower() for c, t in r["ocr_trace"] if c >= SPONSOR_MIN_CONF and len(t) >= SUGGEST_MIN_LEN and t.isalpha()}
        prefix = None
        if r["category"] == "identified":
            tags = entries[r["entry"]]["tags"]
            prefix = min(tags, key=lambda t: t.count("|")) if tags else None
        for w in words:
            seen.setdefault(w, []).append((r["category"], prefix))
    out = []
    for w, hits in seen.items():
        if w in known:
            continue
        counts = {}
        for cat, p in hits:
            if p:
                counts[p] = counts.get(p, 0) + 1
        if not counts:
            continue
        prefix, n = max(counts.items(), key=lambda kv: kv[1])
        other = sum(counts.values()) - n
        if n >= SUGGEST_MIN_BOXES and other == 0:
            out.append({"word": w, "prefix": prefix, "identified": n, "other": other,
                        "unhinted": sum(1 for cat, p in hits if cat in UNHINTED_CATEGORIES)})
    out.sort(key=lambda s: (-s["unhinted"], -s["identified"], s["word"]))
    return out


def pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def describe(r: dict) -> str:
    if r["category"] == "no-vehicle":
        return f"`{r['image']}` burst {r['burst']}: {r['note'] or 'no detector note'}"
    cands = ", ".join(f"`{e}` {s:.3f}" for e, s in r["candidates"][:3]) or "no candidates"
    parts = [f"`{r['image']}` box {r['box']}: {cands}", f"{r['decided_by']}" + (f", short by {r['gap']:.3f}" if r["gap"] else "")]
    if r.get("score") is not None:
        parts.append(f"detector {r['score']:.2f}")
    if r["ocr"]:
        parts.append("read " + ", ".join(f"`{d}`" for d, _ in r["ocr"]))
    elif r.get("ocr_trace"):
        parts.append("ocr saw " + ", ".join(f"`{t}` {c:.2f}" for c, t in r["ocr_trace"][:3]))
    elif "ocr_trace" in r:
        parts.append("ocr saw no text")
    if r.get("pod"):
        parts.append(f"pod {pod_colour(r['pod']) or 'unclear'} (yellow {r['pod']['yellow']:.3f}, aspect {r['pod']['aspect']:.1f})")
    if r.get("rescued"):
        parts.append(f"rescued from {r['rescued']['from']} (crop similarity {r['rescued']['sim']:.2f})")
    h = r.get("hint")
    if h:
        parts.append("hint " + ", ".join(f"`{p.rsplit('|', 1)[-1]}`" for p in h["prefixes"]) + f" ({h['source']})"
                     + (f" dropped ({h['reason']})" if h["dropped"] else ""))
    if r["lever"]:
        parts.append(f"lever: {r['lever']}")
    return "; ".join(parts)


def extras(data: dict, all_rows: list) -> dict:
    """The sections beyond the per-box rows, computed once for both the .md and the .json."""
    return {"bursts": burst_timing(data), "detector_bands": detector_bands(all_rows),
            "sponsor_suggestions": sponsor_suggestions(data, all_rows), "pod": pod_stats(data, all_rows)}


def render_md(data: dict, all_rows: list, summary: dict, top: int, extra: dict = None) -> str:
    extra = extra or extras(data, all_rows)
    t = data["thresholds"]
    out = [f"# Assisted Tagging report: `{data['collection']}`", "",
           f"thresholds: min_sim {t['min_sim']}, min_margin {t['min_margin']}, reference_margin {t['reference_margin']}",
           "", "## Summary", "", f"{summary['total']} vehicles/images, identified rate {pct(summary['identified_rate'])}", ""]
    for c in CATEGORIES:
        out.append(f"- {c}: {summary['counts'][c]} ({pct(summary['shares'][c])})")
    for c, m in summary["medians"].items():
        out.append(f"- median {c}: top-1 {m['top1']:.3f}, margin {m['margin']:.3f}")
    hinted = [r["hint"] for r in all_rows if r.get("hint")]
    if hinted:
        out.append(f"- hints: {len(hinted)} applied, {sum(1 for h in hinted if h['dropped'])} dropped")
    if summary["errors"]:
        out.append(f"- images that failed analysis (not counted above): {summary['errors']}")
    bands = extra["detector_bands"]
    if bands and top > 0:
        out += ["", "## detector score", ""]
        out += [f"- {b['from']:.2f}-{min(b['to'], 1.0):.2f}: {b['boxes']} boxes, {b['identified']} identified" for b in bands]
    suggestions = extra["sponsor_suggestions"]
    if suggestions and top > 0:
        out += ["", "## sponsor keyword suggestions", "",
                "words OCR read on identified boxes of one tag prefix only; add under `rules.sponsor_keywords` after checking:"]
        out += [f"- `{s['word']}` → `{s['prefix']}`: {s['identified']} identified, would hint {s['unhinted']} unidentified"
                for s in suggestions[:top]]
    pod = extra.get("pod")
    if pod and top > 0:
        v = pod["verdicts"]
        out += ["", "## camera pod (frames identified by number)", "",
                f"read right {v['right']}, unclear {v['unclear']}, wrong {v['wrong']}",
                "yellow share of the pod region per driver (min / median / max):"]
        out += [f"- {d['entry']} ({d['camera']}, {d['boxes']} boxes): {d['min']:.4f} / {d['median']:.4f} / {d['max']:.4f}"
                for d in pod["drivers"][:top]]
        if pod["yellow_p10"] is not None and pod["black_p90"] is not None:
            out.append(f"yellow-pod 10th percentile {pod['yellow_p10']:.4f}, black-pod side-on 90th percentile "
                       f"{pod['black_p90']:.4f}: pod.YELLOW_MIN_FRAC should sit between them")
    timing = extra["bursts"]
    if timing["bursts"] and top > 0:
        out += ["", f"## bursts ({len(timing['bursts'])} timed, {timing['untimed']} without capture times)", "",
                "within-burst largest gap (s) → bursts: " + ", ".join(f"{g}s ×{n}" for g, n in timing["max_gap_counts"].items()),
                "frames per burst: " + ", ".join(str(n) for n in timing["frame_counts"]), "",
                "closest to the next burst (possible split):"]
        near = sorted((b for b in timing["bursts"] if b["gap_to_next"] is not None), key=lambda b: b["gap_to_next"])
        out += [f"- burst {b['burst']}: {b['frames']} frames, next burst starts {b['gap_to_next']}s later" for b in near[:top]]
        out += ["", "largest within-burst gap (possible merge):"]
        wide = sorted(timing["bursts"], key=lambda b: -b["max_gap"])
        out += [f"- burst {b['burst']}: {b['frames']} frames over {b['span']}s, largest gap {b['max_gap']}s, "
                f"{b['ok']} with vehicles, {b['no_vehicle']} without" for b in wide[:top]]
    if top > 0:
        for c in DETAIL_CATEGORIES:
            sel = sorted((r for r in all_rows if r["category"] == c), key=lambda r: r["top1"])
            if not sel:
                continue
            out += ["", f"## {c} ({len(sel)})", ""]
            out += [f"- {describe(r)}" for r in sel[:top]]
            if len(sel) > top:
                out.append(f"- … {len(sel) - top} more in report.json")
    return "\n".join(out) + "\n"


def write_report(data: dict, out_prefix: str, top: int) -> tuple:
    """Writes OUT_PREFIX.md (capped at `top` boxes per category) and OUT_PREFIX.json (every row);
    returns both paths."""
    all_rows = rows(data)
    summary = summarize(data, all_rows)
    extra = extras(data, all_rows)
    paths = (out_prefix + ".md", out_prefix + ".json")
    os.makedirs(os.path.dirname(os.path.abspath(out_prefix)), exist_ok=True)
    for path, text in ((paths[0], render_md(data, all_rows, summary, top, extra)),
                       (paths[1], json.dumps({"collection": data["collection"], "thresholds": data["thresholds"],
                                              "summary": summary, **extra, "rows": all_rows}))):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rebuild the debug report from a saved boxes.json")
    parser.add_argument("boxes", help="boxes.json from a run")
    parser.add_argument("out_prefix", help="Writes <this>.md and <this>.json")
    parser.add_argument("--report-top", type=int, default=20, help="Per-category cap on box detail in the .md")
    args = parser.parse_args(argv)
    with open(args.boxes, encoding="utf-8") as f:
        data = json.load(f)
    md_path, json_path = write_report(data, args.out_prefix, args.report_top)
    print(md_path)
    print(json_path)


if __name__ == "__main__":
    sys.exit(main())

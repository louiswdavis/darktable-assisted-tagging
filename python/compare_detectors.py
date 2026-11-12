#!/usr/bin/env python3
"""Run two or more vehicle detectors over the same photos and compare what they find.

    compare_detectors.py --detector A.onnx --detector B.onnx [--truth results.csv --manifest manifest.csv]
                         [--out table.csv] [--disagree disagree.csv] PATH...

Each photo is decoded once; only the detector call is timed. Prints one markdown table row per
detector per score threshold. `--truth` is a tagging run's results.csv (box −1 = no vehicle) and
`--manifest` the id,filepath manifest of that run: together they say which frames hold a car, so
the table can count the cars a detector missed. Paths may be files, folders or `@list.txt`.
"""

import argparse
import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare_ocr import MODELS, photos  # noqa: E402
from vehicle_detect import InputError, decode_rgb, detect, load_detector  # noqa: E402

THRESHOLDS = (0.20, 0.35, 0.50)
COLUMNS = ("detector", "threshold", "frames", "frames_with_car", "missed_cars", "boxes", "boxes_per_frame",
           "ms_mean", "ms_p90")


def _p90(values: list) -> float:
    ordered = sorted(values)
    return ordered[max(0, int(round(0.9 * len(ordered) + 0.5)) - 1)]


def summarise(rows: list, thresholds=THRESHOLDS) -> list:
    """One dict per detector per threshold (COLUMNS). missed_cars is None when no row carries truth."""
    out = []
    by_det: dict = {}
    for r in rows:
        by_det.setdefault(r["detector"], []).append(r)
    for det, det_rows in by_det.items():
        ms = [r["ms"] for r in det_rows]
        has_truth = any(r.get("truth") is not None for r in det_rows)
        for thr in thresholds:
            counts = [sum(1 for b in r["boxes"] if b[4] >= thr) for r in det_rows]
            with_car = sum(1 for c in counts if c)
            missed = sum(1 for r, c in zip(det_rows, counts) if r.get("truth") is True and not c) if has_truth else None
            out.append({"detector": det, "threshold": thr, "frames": len(det_rows), "frames_with_car": with_car,
                        "missed_cars": missed, "boxes": sum(counts),
                        "boxes_per_frame": round(sum(counts) / len(det_rows), 2) if det_rows else 0.0,
                        "ms_mean": round(sum(ms) / len(ms), 1) if ms else 0.0, "ms_p90": round(_p90(ms), 1) if ms else 0.0})
    return out


def disagreements(rows: list, threshold: float = 0.35) -> list:
    """Frames where the detectors' box counts at `threshold` differ: [{"frame", "counts": {detector: n}}]."""
    per_frame: dict = {}
    for r in rows:
        per_frame.setdefault(r["frame"], {})[r["detector"]] = sum(1 for b in r["boxes"] if b[4] >= threshold)
    return [{"frame": f, "counts": c} for f, c in sorted(per_frame.items()) if len(set(c.values())) > 1]


def read_truth(results: list, manifest: list) -> dict:
    """filepath → True when results.csv has a box ≥ 0 for that image id, False when its only box is −1."""
    paths = {m["id"]: m["filepath"] for m in manifest}
    truth: dict = {}
    for r in results:
        path = paths.get(r["id"])
        if path is not None:
            truth[path] = truth.get(path, False) or int(r["box"]) >= 0
    return truth


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _read_csv(path: str) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: str, rows: list, columns) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(columns))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 fromfile_prefix_chars="@")
    ap.add_argument("--detector", action="append", required=True, help="detector .onnx; give two or more")
    ap.add_argument("--truth", help="results.csv from a tagging run (needs --manifest)")
    ap.add_argument("--manifest", help="id,filepath manifest of that tagging run")
    ap.add_argument("--out", help="write the summary table as CSV")
    ap.add_argument("--disagree", help="write the frames where box counts differ at 0.35 as CSV")
    ap.add_argument("paths", nargs="+", help="photos, folders, or @list.txt")
    args = ap.parse_args()
    if len(args.detector) < 2:
        ap.error("give at least two --detector files")
    if bool(args.truth) != bool(args.manifest):
        ap.error("--truth and --manifest go together")
    try:
        detectors = [load_detector(p if os.path.exists(p) else os.path.join(MODELS, os.path.basename(p)))
                     for p in args.detector]
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    truth = read_truth(_read_csv(args.truth), _read_csv(args.manifest)) if args.truth else {}
    truth = {_norm(k): v for k, v in truth.items()}
    for d in detectors:
        print(f"detector: {d.id}")

    rows = []
    frames = photos(args.paths)
    for i, path in enumerate(frames, 1):
        try:
            rgb = decode_rgb(path)
        except InputError as e:
            print(f"skip {path}: {e}", file=sys.stderr)
            continue
        for d in detectors:
            t0 = time.perf_counter()
            entry = detect(rgb, d)
            ms = (time.perf_counter() - t0) * 1000.0
            rows.append({"frame": path, "detector": d.id, "ms": ms, "boxes": entry["boxes"], "truth": truth.get(_norm(path))})
        print(f"\r{i}/{len(frames)}", end="", file=sys.stderr, flush=True)
    print("", file=sys.stderr)

    table = summarise(rows)
    print("| " + " | ".join(COLUMNS) + " |")
    print("|" + "---|" * len(COLUMNS))
    for r in table:
        print("| " + " | ".join("" if r[c] is None else str(r[c]) for c in COLUMNS) + " |")
    dis = disagreements(rows)
    print(f"\n{len(dis)} frames where the detectors disagree on box count at 0.35")
    if args.out:
        _write_csv(args.out, table, COLUMNS)
    if args.disagree:
        ids = [d.id for d in detectors]
        _write_csv(args.disagree, [{"frame": d["frame"], **{i: d["counts"].get(i, 0) for i in ids}} for d in dis],
                   ["frame", *ids])
    return 0


if __name__ == "__main__":
    sys.exit(main())

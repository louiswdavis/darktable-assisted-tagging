"""Throwaway check: in a run's boxes.json, which frames have more than one vehicle box, and are the
extra boxes the same car again (high IoU, or one box inside the other) or a second vehicle?

     python python/experiments/box_pairs.py <config>/last-run/<collection>.boxes.json

Prints one line per box pair, then counts by kind."""

import json
import sys


def area(b):
    return max(b[2] - b[0], 0.0) * max(b[3] - b[1], 0.0)


def pair_kind(a, b):
    """(kind, IoU, share of the smaller box inside the larger)."""
    iw = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    ih = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = iw * ih
    iou = inter / max(area(a) + area(b) - inter, 1.0)
    inside = inter / max(min(area(a), area(b)), 1.0)
    kind = ("duplicate" if iou >= 0.5 else "part inside" if inside >= 0.8
            else "touching" if inter > 0 else "separate")
    return kind, iou, inside


def main():
    with open(sys.argv[1], encoding="utf-8") as f:
        run = json.load(f)
    counts, multi = {}, 0
    for iid, rec in run["images"].items():
        boxes = rec.get("boxes", [])
        if len(boxes) < 2:
            continue
        multi += 1
        w, h = rec["frame"]
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                kind, iou, inside = pair_kind(a["bbox"], b["bbox"])
                counts[kind] = counts.get(kind, 0) + 1
                small = min(area(a["bbox"]), area(b["bbox"])) / (w * h)
                print(f"{iid} {rec['file'].split(chr(92))[-1].split('/')[-1]}: b{a['box']} {a['score']:.2f} "
                      f"[{a.get('overlap') or '-'}{' masked' if a.get('masked') else ''}] + b{b['box']} {b['score']:.2f} "
                      f"[{b.get('overlap') or '-'}{' masked' if b.get('masked') else ''}]  {kind}  "
                      f"IoU {iou:.2f} inside {inside:.2f} smaller box {small:.1%} of frame")
    total = len(run["images"])
    print(f"\n{multi} of {total} frames have 2+ boxes. Pairs: "
          + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))


if __name__ == "__main__":
    main()

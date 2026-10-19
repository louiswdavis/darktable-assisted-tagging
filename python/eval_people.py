"""Leave-one-out check of face matching for a `people` collection, to choose rules.min_sim, rules.margin
and rules.min_face_px. Each reference crop is the query once, matched against the other references.
Run from this folder:

  python eval_people.py COLLECTION_DIR --face-detector YUNET.onnx --face-recognizer SFACE.onnx

COLLECTION_DIR holds entries.json and refs/<entry id>/*.jpg (112px aligned crops). The crops lose the
photo's original face width, so each query is also re-embedded as if the face were 112, 96, 80, 64, 48
and 32 px wide (shrunk, then enlarged back to 112). Entries with fewer than 2 references are skipped.
Writes people-report.txt beside entries.json. References are cleaner than real stage photos, so read
the trend across widths and thresholds, not the absolute numbers."""

import argparse
import os
import sys

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from match_people import entry_scores, match_face
from people import FACE_CROP, FaceModel

WIDTHS = (112, 96, 80, 64, 48, 32)
MIN_SIMS = [round(0.30 + 0.05 * i, 2) for i in range(11)]  # 0.30 .. 0.80
MARGINS = (0.0, 0.02, 0.05, 0.10)


def load_crops(cdir: str) -> list:
    """[(entry id, relative path, RGB crop)] for every reference with a sibling reference."""
    refs = os.path.join(cdir, "refs")
    found = []
    for entry in sorted(os.listdir(refs)):
        d = os.path.join(refs, entry)
        names = sorted(n for n in os.listdir(d) if n.lower().endswith(".jpg")) if os.path.isdir(d) else []
        if len(names) < 2:
            continue
        for n in names:
            with Image.open(os.path.join(d, n)) as im:
                found.append((entry, f"{entry}/{n}", np.array(im.convert("RGB"))))
    return found


def at_width(crop: np.ndarray, width: int) -> np.ndarray:
    """The crop as a face `width` px wide would look after enlarging to the recogniser's input size."""
    if width >= FACE_CROP:
        return crop
    small = cv2.resize(crop, (width, width), interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (FACE_CROP, FACE_CROP), interpolation=cv2.INTER_LINEAR)


def outcomes(ref_emb, entry, query_emb, width, min_sim, margin) -> tuple:
    """(right, wrong, untagged) counts over all queries at one width and threshold pair."""
    right = wrong = untagged = 0
    for i, q in enumerate(query_emb):
        sims = [(e, float(s)) for j, (e, s) in enumerate(zip(entry, ref_emb @ q)) if j != i]
        r, _ = match_face(i, width, entry_scores(sims), min_sim, margin, 0)
        if r.method != "face":
            untagged += 1
        elif r.entry_id == entry[i]:
            right += 1
        else:
            wrong += 1
    return right, wrong, untagged


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("collection_dir")
    ap.add_argument("--face-detector", required=True)
    ap.add_argument("--face-recognizer", required=True)
    a = ap.parse_args()
    model = FaceModel(a.face_detector, a.face_recognizer)
    crops = load_crops(a.collection_dir)
    if not crops:
        sys.exit("no entry has 2 or more reference crops under refs/")
    entry = [c[0] for c in crops]
    ref_emb = np.stack([model.embed(c[2]) for c in crops])
    lines = [f"{len(crops)} references, {len(set(entry))} entries", ""]
    for width in WIDTHS:
        query_emb = np.stack([model.embed(at_width(c[2], width)) for c in crops])
        lines += [f"== simulated face width {width}px (right/wrong/untagged % of {len(crops)} queries) =="]
        lines.append("min_sim  " + "  ".join(f"margin {m:<4}" + " " * 9 for m in MARGINS))
        for ms in MIN_SIMS:
            cells = []
            for mg in MARGINS:
                r, w, u = outcomes(ref_emb, entry, query_emb, width, ms, mg)
                n = len(crops)
                cells.append(f"{100 * r / n:5.1f}/{100 * w / n:4.1f}/{100 * u / n:5.1f}")
            lines.append(f"{ms:<8} " + "  ".join(f"{c:<20}" for c in cells))
        lines.append("")
    lines.append("Pick the lowest min_sim and margin whose wrong% is ~0 at the widths you care about; "
                 "min_face_px is the narrowest width where that still holds.")
    out = os.path.join(a.collection_dir, "people-report.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"written: {out}")


if __name__ == "__main__":
    main()

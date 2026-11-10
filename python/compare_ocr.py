"""Side-by-side number reads from two or more recognisers on the same vehicle crops.

Run from the plugin folder, e.g.:
  python python/compare_ocr.py --rec models/text_recognition_CRNN_EN_2021sep.onnx
      --rec models/en_PP-OCRv5_mobile_rec.onnx --out compare.csv <photos or a folder>

Each photo goes through the same vehicle detector and text detector as a run; only the recogniser
differs. Prints one line per vehicle, then per recogniser how many vehicles got a number. Nothing is
written to darktable or the cache."""

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ocr import NumberReader
from vehicles import crop_box, detect_vehicles, load_full

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, "..", "models")
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".cr2", ".cr3", ".nef", ".arw", ".rw2", ".dng", ".raf", ".orf"}


JPEG_EXT = {".jpg", ".jpeg"}


def photos(paths: list) -> list:
    """Files as given, plus each folder's images; a RAW with a same-name JPEG beside it is skipped,
    as a run reads the pair once, from the JPEG."""
    out = []
    for p in paths:
        if not os.path.isdir(p):
            out.append(p)
            continue
        files = [f for f in os.listdir(p) if os.path.splitext(f)[1].lower() in IMAGE_EXT]
        jpeg_stems = {os.path.splitext(f)[0].lower() for f in files if os.path.splitext(f)[1].lower() in JPEG_EXT}
        out += sorted(os.path.join(p, f) for f in files
                      if os.path.splitext(f)[1].lower() in JPEG_EXT or os.path.splitext(f)[0].lower() not in jpeg_stems)
    return out


def shown(reads: list) -> str:
    return " ".join(f"{d}@{c:.2f}" for d, c in reads) or "-"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--detector", default=os.path.join(MODELS, "object_detection_yolox_2022nov.onnx"))
    ap.add_argument("--ocr-det", default=os.path.join(MODELS, "text_detection_en_ppocrv3_2023may.onnx"))
    ap.add_argument("--rec", action="append", required=True, help="a recogniser model; give it two or more times")
    ap.add_argument("--out", help="also write every read to this CSV")
    ap.add_argument("paths", nargs="+", help="photos, or folders of photos")
    args = ap.parse_args()
    if len(args.rec) < 2:
        ap.error("give --rec at least twice")

    readers = [(os.path.basename(r), NumberReader(args.ocr_det, r)) for r in args.rec]
    names = [n for n, _r in readers]
    print("recognisers: " + ", ".join(f"{n} ({r.rec.name})" for n, r in readers))
    rows, got = [], {n: 0 for n in names}
    vehicles = 0
    for path in photos(args.paths):
        try:
            rgb = load_full(path)
        except Exception as e:  # one unreadable photo shouldn't end the comparison
            print(f"{os.path.basename(path)}: can't decode: {type(e).__name__}: {e}")
            continue
        boxes, _note = detect_vehicles(rgb, args.detector)
        for i, box in enumerate(boxes):
            crop = crop_box(rgb, box)
            vehicles += 1
            reads = [r.read(crop) for _n, r in readers]
            for n, rd in zip(names, reads):
                got[n] += bool(rd)
            marker = "" if len({tuple(d for d, _c in rd[:1]) for rd in reads}) == 1 else "  <- differ"
            print(f"{os.path.basename(path)} box {i}: " + " | ".join(shown(rd) for rd in reads) + marker)
            rows.append([os.path.basename(path), i] + [shown(rd) for rd in reads])
    print(f"\n{vehicles} vehicles")
    for n in names:
        print(f"  {n}: a number on {got[n]}")
    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["photo", "box"] + names)
            w.writerows(rows)


if __name__ == "__main__":
    main()

"""Throwaway test: can SigLIP 2 name a car's colour and which way it faces, better than today's rules?

Today's rules: car_colour.py (HSV shares of the body band) for colour, and pod.py's aspect ratio
(box width / height >= SIDE_ON_ASPECT → side-on; anything narrower can't be told apart) for view.

Needs `pip install tokenizers` and SigLIP 2 base from onnx-community/siglip2-base-patch16-224-ONNX in
one folder: onnx/vision_model.onnx, onnx/text_model.onnx and tokenizer.json, saved as
vision_model.onnx, text_model.onnx, tokenizer.json.

1. Sample crops from a run's boxes.json and classify them (writes the crops and a CSV):
     python python/experiments/siglip2_colour_view.py sample --boxes <config>/last-run/<collection>.boxes.json
         --model-dir models/siglip2 --out siglip2.csv --crops siglip2-crops --limit 50
   --boxes takes several runs' files (pooled). --seed N picks at random instead of evenly spread;
   --skip <earlier>.csv leaves out boxes an earlier sample already tested.
2. Open each crop, fill colour_ok / view_ok in the CSV with r (rules right), s (SigLIP right),
   b (both right) or n (neither).
3. Count:
     python python/experiments/siglip2_colour_view.py score siglip2.csv

Car or not: `cars --boxes ... --model-dir ...` crops every box and names it (rally car, person, shed,
railing, spectators, trees, road); fill is_car with y or n, then `score` the CSV.

Only boxes read on a plain crop are sampled (no overlap, no mask), so the crop here is the one the
run measured and the test compares classifiers, not crops."""

import argparse
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

COLOUR_PROMPTS = {name: f"a photo of a {name.lower()} rally car." for name in (
    "Black", "White", "Grey", "Brown", "Red", "Orange", "Yellow", "Green", "Blue", "Purple", "Pink")}
COLOUR_PROMPTS["Multi"] = "a photo of a multicoloured rally car."
VIEW_PROMPTS = {
    "side": "a photo of a rally car seen from the side.",
    "front": "a photo of a rally car seen from the front.",
    "rear": "a photo of a rally car seen from the rear.",
    "front-corner": "a photo of a rally car seen from the front three-quarter angle.",
    "rear-corner": "a photo of a rally car seen from the rear three-quarter angle.",
}
CAR_PROMPTS = {
    "car": "a photo of a rally car.",
    "person": "a photo of a person.",
    "building": "a photo of a shed or a small building.",
    "railing": "a photo of a metal railing or crash barrier along a road.",
    "crowd": "a photo of spectators.",
    "trees": "a photo of trees and bushes.",
    "road": "a photo of an empty road.",
}
TEXT_LEN = 64  # SigLIP 2 was trained on text padded to 64 tokens
IMAGE_SIZE = 224
FIELDS = ["image", "box", "entry", "crop", "rules_colour", "siglip_colour", "siglip_colour_gap",
          "rules_view", "siglip_view", "siglip_view_gap", "aspect", "colour_ok", "view_ok"]


class SigLIP:
    def __init__(self, model_dir: str):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        opts = ort.SessionOptions()
        self.vision = ort.InferenceSession(os.path.join(model_dir, "vision_model.onnx"), opts)
        self.text = ort.InferenceSession(os.path.join(model_dir, "text_model.onnx"), opts)
        self.tok = Tokenizer.from_file(os.path.join(model_dir, "tokenizer.json"))
        self.pad = self.tok.token_to_id("<pad>")
        self.eos = self.tok.token_to_id("<eos>")

    @staticmethod
    def _pooled(session, feeds):
        import numpy as np
        names = [o.name for o in session.get_outputs()]
        out = session.run(None, feeds)
        vec = out[names.index("pooler_output")] if "pooler_output" in names else out[0]
        if vec.ndim == 3:
            vec = vec[:, 0]
        return vec / np.linalg.norm(vec, axis=1, keepdims=True)

    def embed_text(self, prompts: list):
        import numpy as np
        rows = []
        for p in prompts:
            ids = self.tok.encode(p.lower()).ids[:TEXT_LEN]
            if ids[-1] != self.eos:
                ids = ids[:TEXT_LEN - 1] + [self.eos]
            rows.append(ids + [self.pad] * (TEXT_LEN - len(ids)))
        ids = np.array(rows, dtype=np.int64)
        feeds = {}
        for i in self.text.get_inputs():
            feeds[i.name] = ids if i.name == "input_ids" else np.ones_like(ids)
        return self._pooled(self.text, feeds)

    def embed_image(self, crop_rgb):
        import numpy as np
        from PIL import Image
        img = Image.fromarray(crop_rgb).resize((IMAGE_SIZE, IMAGE_SIZE), Image.BILINEAR)
        x = (np.asarray(img, dtype=np.float32) / 255.0 - 0.5) / 0.5
        x = x.transpose(2, 0, 1)[None]
        return self._pooled(self.vision, {self.vision.get_inputs()[0].name: x})


def pick(image_vec, text_vecs, labels: list):
    """(best label, cosine lead over the runner-up)."""
    sims = (text_vecs @ image_vec[0]).tolist()
    ranked = sorted(zip(sims, labels), reverse=True)
    return ranked[0][1], round(ranked[0][0] - ranked[1][0], 4)


def sample_boxes(boxes_jsons: list, limit: int, seed, skip_csvs: list) -> list:
    """Up to `limit` (image id, record, box) from the runs' plain-crop boxes, minus boxes already in
    `skip_csvs`. Spread evenly, or a random pick when `seed` is set."""
    import json
    import random
    skip = set()
    for path in skip_csvs:
        with open(path, encoding="utf-8") as f:
            skip.update((row["image"], str(row["box"])) for row in csv.DictReader(f))
    plain = []
    left_out = {"image skipped (already tagged)": 0, "image not ok": 0, "overlap": 0, "masked": 0,
                "rescued": 0, "already tested": 0}
    for boxes_json in boxes_jsons:
        with open(boxes_json, encoding="utf-8") as f:
            run = json.load(f)
        left_out["image skipped (already tagged)"] += len(run.get("skipped", []))
        for iid, rec in run["images"].items():
            if rec.get("status") != "ok":
                left_out["image not ok"] += 1
                continue
            for b in rec.get("boxes", []):
                reason = ("overlap" if b.get("overlap") else "masked" if b.get("masked")
                          else "rescued" if b.get("rescued")
                          else "already tested" if (iid, str(b["box"])) in skip else None)
                if reason:
                    left_out[reason] += 1
                else:
                    plain.append((iid, rec, b))
    print(f"{len(plain)} plain-crop boxes to pick from; left out: "
          + ", ".join(f"{k} {v}" for k, v in left_out.items()))
    if len(plain) <= limit:
        return plain
    if seed is not None:
        return sorted(random.Random(seed).sample(plain, limit), key=lambda p: p[1]["file"])
    step = len(plain) / limit
    return [plain[int(i * step)] for i in range(limit)]


def sample(args):
    from PIL import Image
    from car_colour import colour_shares, decide_colour
    from pod import SIDE_ON_ASPECT
    from vehicle_detect import decode_rgb
    from vehicles import crop_box

    model = SigLIP(args.model_dir)
    colour_labels, view_labels = list(COLOUR_PROMPTS), list(VIEW_PROMPTS)
    colour_vecs = model.embed_text([COLOUR_PROMPTS[k] for k in colour_labels])
    view_vecs = model.embed_text([VIEW_PROMPTS[k] for k in view_labels])
    os.makedirs(args.crops, exist_ok=True)
    rows, frames = [], {}
    for iid, rec, b in sample_boxes(args.boxes, args.limit, args.seed, args.skip):
        if rec["file"] not in frames:
            frames.clear()
            frames[rec["file"]] = decode_rgb(rec["file"])
        rgb = frames[rec["file"]]
        if [rgb.shape[1], rgb.shape[0]] != rec["frame"]:
            print(f"{iid}: frame size changed since the run, skipped")
            continue
        crop = crop_box(rgb, b["bbox"])
        name = f"{iid}_b{b['box']}.jpg"
        Image.fromarray(crop).save(os.path.join(args.crops, name), quality=90)
        vec = model.embed_image(crop)
        s_colour, c_gap = pick(vec, colour_vecs, colour_labels)
        s_view, v_gap = pick(vec, view_vecs, view_labels)
        x0, y0, x1, y1 = b["bbox"][:4]
        aspect = round((x1 - x0) / max(y1 - y0, 1.0), 2)
        row = {"image": iid, "box": b["box"], "entry": b.get("entry", ""), "crop": name,
               "rules_colour": decide_colour(colour_shares(crop)) or "-", "siglip_colour": s_colour,
               "siglip_colour_gap": c_gap, "rules_view": "side" if aspect >= SIDE_ON_ASPECT else "front/rear?",
               "siglip_view": s_view, "siglip_view_gap": v_gap, "aspect": aspect, "colour_ok": "", "view_ok": ""}
        rows.append(row)
        print(f"{name}: colour rules {row['rules_colour']:<7} siglip {s_colour:<7} ({c_gap})  "
              f"view rules {row['rules_view']:<11} siglip {s_view} ({v_gap})")
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} crops → {args.out}, images in {args.crops}. Fill colour_ok / view_ok with r, s, b or n.")


CAR_FIELDS = ["image", "box", "crop", "det_score", "overlap", "siglip_is", "siglip_gap", "is_car"]


def cars(args):
    """Every box in the runs (any overlap state), cropped and named by SigLIP 2 as a car or one of
    the things the detector mistakes for one. The user fills is_car with y or n."""
    import json
    from PIL import Image
    from vehicle_detect import decode_rgb
    from vehicles import crop_box

    model = SigLIP(args.model_dir)
    labels = list(CAR_PROMPTS)
    vecs = model.embed_text([CAR_PROMPTS[k] for k in labels])
    os.makedirs(args.crops, exist_ok=True)
    rows = []
    for boxes_json in args.boxes:
        with open(boxes_json, encoding="utf-8") as f:
            run = json.load(f)
        for iid, rec in run["images"].items():
            if rec.get("status") != "ok" or not rec.get("boxes"):
                continue
            rgb = decode_rgb(rec["file"])
            if [rgb.shape[1], rgb.shape[0]] != rec["frame"]:
                print(f"{iid}: frame size changed since the run, skipped")
                continue
            for b in rec["boxes"]:
                crop = crop_box(rgb, b["bbox"])
                name = f"{iid}_b{b['box']}.jpg"
                Image.fromarray(crop).save(os.path.join(args.crops, name), quality=90)
                what, gap = pick(model.embed_image(crop), vecs, labels)
                rows.append({"image": iid, "box": b["box"], "crop": name, "det_score": b.get("score", ""),
                             "overlap": b.get("overlap") or "-", "siglip_is": what, "siglip_gap": gap, "is_car": ""})
                print(f"{name}: detector {b.get('score', 0):.2f}  siglip {what} ({gap})")
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAR_FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} crops → {args.out}, images in {args.crops}. Fill is_car with y or n.")


def score_cars(path: str):
    """SigLIP's car / not-car call against the user's is_car marks, next to the best single detector
    score cut-off for comparison."""
    marked = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mark = row["is_car"].strip().lower()
            if mark in ("y", "n"):
                marked.append((mark == "y", row["siglip_is"] == "car", float(row["det_score"] or 0)))
    cars_n = sum(1 for c, _, _ in marked if c)
    print(f"{len(marked)} marked: {cars_n} cars, {len(marked) - cars_n} not cars")
    kept = sum(1 for c, s, _ in marked if c and s)
    dropped = sum(1 for c, s, _ in marked if not c and not s)
    print(f"SigLIP 2: keeps {kept}/{cars_n} cars, drops {dropped}/{len(marked) - cars_n} non-cars")
    best = max(((sum(1 for c, _, d in marked if c and d >= t) + sum(1 for c, _, d in marked if not c and d < t), t)
                for t in sorted({d for _, _, d in marked})), default=(0, 0.0))
    t = best[1]
    print(f"detector score cut-off {t:.2f} (best single cut): keeps "
          f"{sum(1 for c, _, d in marked if c and d >= t)}/{cars_n} cars, drops "
          f"{sum(1 for c, _, d in marked if not c and d < t)}/{len(marked) - cars_n} non-cars")


def score(args):
    with open(args.csv, encoding="utf-8") as f:
        if "is_car" in (csv.DictReader(f).fieldnames or []):
            return score_cars(args.csv)
    counts = {k: {"rules": 0, "siglip": 0, "marked": 0} for k in ("colour", "view")}
    with open(args.csv, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for k in counts:
                mark = row[f"{k}_ok"].strip().lower()
                if mark not in ("r", "s", "b", "n"):
                    continue
                counts[k]["marked"] += 1
                counts[k]["rules"] += mark in ("r", "b")
                counts[k]["siglip"] += mark in ("s", "b")
    for k, c in counts.items():
        print(f"{k}: rules right {c['rules']}/{c['marked']}, SigLIP 2 right {c['siglip']}/{c['marked']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--boxes", required=True, nargs="+",
                   help="one or more runs' boxes.json (last-run/<collection>.boxes.json); boxes are pooled")
    s.add_argument("--seed", type=int, help="pick boxes at random with this seed (default: spread evenly)")
    s.add_argument("--skip", nargs="*", default=[], help="CSVs from earlier samples; their boxes aren't picked again")
    s.add_argument("--model-dir", required=True, help="folder with vision_model.onnx, text_model.onnx, tokenizer.json")
    s.add_argument("--out", default="siglip2.csv")
    s.add_argument("--crops", default="siglip2-crops")
    s.add_argument("--limit", type=int, default=50)
    k = sub.add_parser("cars")
    k.add_argument("--boxes", required=True, nargs="+", help="one or more runs' boxes.json")
    k.add_argument("--model-dir", required=True)
    k.add_argument("--out", default="siglip2-cars.csv")
    k.add_argument("--crops", default="siglip2-cars-crops")
    c = sub.add_parser("score")
    c.add_argument("csv")
    args = parser.parse_args()
    {"sample": sample, "cars": cars, "score": score}[args.cmd](args)


if __name__ == "__main__":
    main()

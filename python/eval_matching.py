"""Leave-one-out check of how well reference matching tells entries apart, and whether centring,
top-k scoring, a colour feature or a stretched crop would do better. Each reference is the query
once, matched against all the others. Run from this folder:

  python eval_matching.py COLLECTION_DIR                      # embedding-only variants
  python eval_matching.py COLLECTION_DIR --embedder PATH.onnx  # also colour and stretch variants

COLLECTION_DIR holds entries.json, index.npz and refs/. Near-duplicates of the query (cosine over
--dup-sim, e.g. frames of one burst) are ignored as neighbours, so the numbers aren't flattered by
them. References are cleaner than real in-race crops, so read the ranking of variants, not the
absolute accuracy."""

import argparse
import json
import os
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from match import MATCH_MIN_MARGIN, MATCH_MIN_SIM, TEAM_KEY


def unit(x):
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-9)


def load(cdir):
    with np.load(os.path.join(cdir, "index.npz"), allow_pickle=False) as z:
        emb, entry, path = z["emb"].astype(np.float32), [str(s) for s in z["entry"]], [str(s) for s in z["path"]]
    with open(os.path.join(cdir, "entries.json"), encoding="utf-8") as f:
        data = json.load(f)
    items = data["entries"] if isinstance(data, dict) else data
    rules = data.get("rules", {}) if isinstance(data, dict) else {}
    team = {e["id"]: e.get("team") or e["id"] for e in items}
    counts = Counter(entry)
    keep = [i for i, e in enumerate(entry) if e in team and not e.startswith(TEAM_KEY) and counts[e] >= 2]
    return emb[keep], [entry[i] for i in keep], [path[i] for i in keep], team, bool(rules.get("blur_references"))


def score_matrix(emb, entry, k, dup_mask):
    """scores[i, j]: query i vs entry j, the mean of its k most similar references (self and near-duplicates out)."""
    sims = emb @ emb.T
    sims[dup_mask] = np.nan
    names = sorted(set(entry))
    cols = []
    for name in names:
        sub = np.where(np.isnan(sims[:, [e == name for e in entry]]), -np.inf, sims[:, [e == name for e in entry]])
        sub = np.sort(sub, axis=1)[:, ::-1][:, :k]
        cols.append(np.where(np.isinf(sub), np.nan, sub).mean(axis=1))
    return names, np.stack(cols, axis=1)


def report(label, names, scores, entry, team):
    """Prints accuracy, the current decision rule's outcome and precision at fixed coverage."""
    truth = np.array([names.index(e) for e in entry])
    ok = ~np.isnan(scores[np.arange(len(entry)), truth])  # the true entry has a non-duplicate neighbour
    filled = np.where(np.isnan(scores), -np.inf, scores)
    order = np.argsort(-filled, axis=1)
    top1, top2 = order[:, 0], order[:, 1]
    s1, s2 = filled[np.arange(len(entry)), top1], filled[np.arange(len(entry)), top2]
    s2 = np.where(np.isinf(s2), 0.0, s2)
    margin = s1 - s2
    right = (top1 == truth) & ok
    team_right = np.array([team[names[t]] == team[entry[i]] for i, t in enumerate(top1)]) & ok
    n = ok.sum()
    decided = (s1 >= MATCH_MIN_SIM) & (margin >= MATCH_MIN_MARGIN) & ok
    print(f"\n{label}\n  entry accuracy {right.sum() / n:.1%}   team accuracy {team_right.sum() / n:.1%}   median margin {np.median(margin[ok]):.3f}")
    print(f"  current rule (sim>={MATCH_MIN_SIM}, margin>={MATCH_MIN_MARGIN}): identified right {(decided & right).sum() / n:.1%}, "
          f"wrong {(decided & ~right).sum() / n:.1%}, abstained {(~decided).sum() / n:.1%}")
    sweep = [f"{m:.2f}: {((s1 >= MATCH_MIN_SIM) & (margin >= m) & ok & right).sum() / n:.0%}/{((s1 >= MATCH_MIN_SIM) & (margin >= m) & ok & ~right).sum() / n:.1%}"
             for m in (0.05, 0.08, 0.10, 0.12, 0.15, 0.20)]
    print("  margin gate: identified right/wrong  " + "   ".join(sweep))
    by_margin = np.argsort(-margin[ok])
    hits = right[ok][by_margin]
    row = [f"{int(cov * 100)}%: {hits[:max(1, int(len(hits) * cov))].mean():.0%}" for cov in (0.25, 0.5, 0.75, 1.0)]
    print("  precision at coverage (most confident first)  " + "   ".join(row))
    wrong = Counter((entry[i], names[top1[i]]) for i in np.where(ok & ~right)[0])
    print("  commonest confusions: " + ", ".join(f"{a}->{b} x{c}" for (a, b), c in wrong.most_common(5)))


def dup_mask_of(emb, dup_sim):
    return (emb @ emb.T >= dup_sim) | np.eye(len(emb), dtype=bool)


def crops(cdir, paths, blur):
    from PIL import Image
    from embed import degrade
    out = []
    for p in paths:
        with Image.open(os.path.join(cdir, *p.split("/"))) as im:
            c = np.array(im.convert("RGB"))
        out.append(degrade(c) if blur else c)
    return out


def hsv_hist(crop):
    import cv2
    hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
    h = cv2.calcHist([hsv], [0, 1], None, [18, 3], [0, 180, 0, 256]).ravel()
    return np.sqrt(h / max(h.sum(), 1.0))


def stretch_embed(embedder_path, imgs):
    import cv2
    import embed
    embed.preprocess = lambda c: np.transpose((cv2.resize(c, (embed.EMBED_INPUT,) * 2, interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
                                               - embed._MEAN) / embed._STD, (2, 0, 1))[np.newaxis]
    model = embed.Embedder(embedder_path)
    return np.stack([model.embed(c) for c in imgs])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("collection_dir")
    ap.add_argument("--embedder", default="", help="DINOv2 .onnx; adds the colour and stretch variants")
    ap.add_argument("--dup-sim", type=float, default=0.97)
    ap.add_argument("--topk", type=int, default=3)
    a = ap.parse_args()
    for need in ("entries.json", "index.npz"):
        if not os.path.isfile(os.path.join(a.collection_dir, need)):
            sys.exit(f"{a.collection_dir} has no {need}: pass the collection folder itself (the one holding entries.json)")
    emb, entry, path, team, blur = load(a.collection_dir)
    print(f"{len(entry)} references, {len(set(entry))} entries with 2+; blur_references={blur}")
    dup = dup_mask_of(emb, a.dup_sim)
    centred = unit(emb - emb.mean(axis=0))
    variants = [("baseline (max similarity)", emb, 1), (f"top-{a.topk} mean", emb, a.topk),
                ("centred embeddings", centred, 1), (f"centred + top-{a.topk} mean", centred, a.topk)]
    if a.embedder:
        if not os.path.isfile(a.embedder):
            sys.exit(f"embedder model not found: {a.embedder}")
        missing = [p for p in path if not os.path.isfile(os.path.join(a.collection_dir, *p.split("/")))]
        if missing:
            sys.exit(f"{len(missing)} of {len(path)} reference crops are missing under {a.collection_dir} (first: {missing[0]}); "
                     f"the colour and stretch variants need the refs/ images. Run without --embedder for the embedding-only variants")
        imgs = crops(a.collection_dir, path, blur)
        hist = unit(np.stack([hsv_hist(c) for c in imgs]))
        for w in (0.5, 1.0, 2.0):
            variants.append((f"centred + colour histogram x{w}, top-{a.topk}", unit(np.hstack([centred, w * hist])), a.topk))
        stretched = stretch_embed(a.embedder, imgs)
        variants.append((f"stretched crop, centred, top-{a.topk}", unit(stretched - stretched.mean(axis=0)), a.topk))
    for label, x, k in variants:
        names, scores = score_matrix(x, entry, k, dup)
        report(label, names, scores, entry, team)


if __name__ == "__main__":
    main()

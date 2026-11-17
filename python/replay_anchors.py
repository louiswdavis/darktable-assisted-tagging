"""Suggests reference_store.ANCHOR_MIN_SIM from a collection's refs. Each anchor is the query once,
left out of its car's anchors, in the space the live check uses (ReferenceIndex.project). Reports only.
Run from this folder:

  python replay_anchors.py COLLECTION_DIR [--colour-weight 0] [--dup-sim 0.97]

Prints, over anchors:
  own   - best similarity to the car's other anchors (a right match should clear the threshold)
  other - best similarity to another car's anchors (a wrong match the threshold should stop)
then the same for non-anchor refs (weak number reads), and a suggested ANCHOR_MIN_SIM: the 5th
percentile of `own`, with the share of `other` it would still let through."""

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audit_refs import ref_anchors, ref_cars  # noqa: E402
from match import TEAM_KEY  # noqa: E402
from reference_store import ANCHOR_MIN_SIM, CENTRE_MIN_REFS, INDEX_NAME  # noqa: E402

PERCENTILES = (5, 10, 25, 50, 75, 90)


def project(emb, hist, colour_weight):
    """ReferenceIndex.project for a whole index: centred when it has CENTRE_MIN_REFS refs or more
    (a smaller index keeps its stored centre, which this replay doesn't have, so stays uncentred)."""
    x = emb.astype(np.float32)
    if len(x) >= CENTRE_MIN_REFS:
        x = x - x.mean(axis=0)
        x = x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-9)
    if colour_weight > 0 and hist is not None:
        x = np.hstack([x, colour_weight * hist.astype(np.float32)])
        x = x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-9)
    return x


def replay(x, car, anchor, dup_sim):
    """(own, other) best similarities per ref: own over its car's other anchors (near-duplicates
    at dup_sim or more left out, so a burst frame doesn't vouch for its twin), other over other
    cars' anchors. -inf where there is nothing to compare with."""
    sims = x @ x.T
    key = np.array(car)
    same = key[:, None] == key[None, :]
    mine = same & anchor[None, :] & ~np.eye(len(key), dtype=bool) & (sims < dup_sim)
    own = np.where(mine, sims, -np.inf).max(axis=1)
    other = np.where(~same & anchor[None, :], sims, -np.inf).max(axis=1)
    return own, other


def spread(label, vals):
    vals = vals[np.isfinite(vals)]
    if not len(vals):
        return f"  {label:6} none"
    cells = "  ".join(f"p{p} {np.percentile(vals, p):.3f}" for p in PERCENTILES)
    return f"  {label:6} n {len(vals):4}  {cells}"


def report(own, other, anchor):
    """Lines for the console."""
    out = []
    for name, rows in (("anchors", anchor), ("non-anchor refs", ~anchor)):
        both = rows & np.isfinite(own) & np.isfinite(other)
        out += [f"{name}:", spread("own", own[rows]), spread("other", other[rows])]
        if both.any():
            closer = int((other[both] > own[both]).sum())
            out.append(f"  closer to another car's anchors: {closer} of {int(both.sum())}")
    test = anchor & np.isfinite(own)
    if not test.any():
        return out + ["no car has 2+ anchors; nothing to suggest"]
    suggest = float(np.percentile(own[test], 5))
    wrong = other[anchor & np.isfinite(other)]
    passed = float((wrong >= suggest).mean()) if len(wrong) else 0.0
    now = float((own[test] < ANCHOR_MIN_SIM).mean())
    out += [f"ANCHOR_MIN_SIM now {ANCHOR_MIN_SIM}: drops {now:.0%} of right anchor matches",
            f"suggested ANCHOR_MIN_SIM {suggest:.2f}: drops 5% of right matches, lets {passed:.0%} of "
            "best wrong-car matches through on similarity alone (the closer-car test catches more)"]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("collection_dir")
    ap.add_argument("--colour-weight", type=float, default=0.0, help="the collection's colour_weight rule")
    ap.add_argument("--dup-sim", type=float, default=0.97)
    args = ap.parse_args()
    with np.load(os.path.join(args.collection_dir, INDEX_NAME), allow_pickle=False) as z:
        emb, entry, path = z["emb"], [str(e) for e in z["entry"]], [str(p) for p in z["path"]]
        hist = z["hist"] if "hist" in z.files else None
    keep = [i for i, e in enumerate(entry) if not e.startswith(TEAM_KEY)]
    emb, entry, path = emb[keep], [entry[i] for i in keep], [path[i] for i in keep]
    hist = hist[keep] if hist is not None else None
    anchor = ref_anchors(args.collection_dir, path)
    car = ref_cars(args.collection_dir, entry)
    own, other = replay(project(emb, hist, args.colour_weight), car, anchor, args.dup_sim)
    print(f"{len(entry)} refs, {int(anchor.sum())} anchors, {len(set(car))} cars")
    print("\n".join(report(own, other, anchor)))


if __name__ == "__main__":
    main()

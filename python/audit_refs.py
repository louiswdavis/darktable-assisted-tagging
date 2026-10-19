"""Lists references that look wrongly filed, so you can review them by hand. Each reference is the
query once, matched against the others (centred embeddings, as the live matcher does). Reports only;
it never moves or deletes anything. Run from this folder:

  python audit_refs.py COLLECTION_DIR [--dup-sim 0.97] [--top 40]

Writes ref-audit.txt in COLLECTION_DIR. Sections:
  mislabel suspects  - closer to another entry's refs than to its own (margin = other - own)
  cross-entry copies - near-identical to a ref filed under a different entry
  outliers           - far from the rest of its own entry (robust z-score, entries with 5+ refs)
  redundant          - near-duplicates inside one entry (add no variety)"""

import argparse
import os
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_matching import load, unit


def audit(emb, entry, path, team, dup_sim):
    """Returns (mislabel, copies, outliers, redundant) lists, each worst first."""
    x = unit(emb - emb.mean(axis=0))
    sims = x @ x.T
    n = len(entry)
    ent = np.array(entry)
    same = ent[:, None] == ent[None, :]
    own = np.where(same & (sims < dup_sim) & ~np.eye(n, dtype=bool), sims, -np.inf)
    other = np.where(~same, sims, -np.inf)
    own_best, own_arg = own.max(axis=1), own.argmax(axis=1)
    other_best, other_arg = other.max(axis=1), other.argmax(axis=1)

    mislabel, copies = [], []
    for i in range(n):
        j = other_arg[i]
        if other_best[i] >= dup_sim:
            copies.append((other_best[i], i, j))
        if other_best[i] > own_best[i]:
            mislabel.append((other_best[i] - own_best[i], i, j))

    outliers = []
    for name in sorted(set(entry)):
        idx = np.where(ent == name)[0]
        if len(idx) < 5:
            continue
        # own_best is -inf when every same-entry neighbour is a near-duplicate; treat as well-supported
        vals = np.where(np.isinf(own_best[idx]), np.nan, own_best[idx])
        med = np.nanmedian(vals)
        mad = max(np.nanmedian(np.abs(vals - med)), 0.01)
        for k, i in enumerate(idx):
            z = (vals[k] - med) / (1.4826 * mad)
            if z < -2.5:
                outliers.append((z, i, own_arg[i]))

    dup_counts = Counter()
    for i in range(n):
        if ((same[i] & (sims[i] >= dup_sim)).sum() - 1) > 0:
            dup_counts[entry[i]] += 1
    redundant = sorted(dup_counts.items(), key=lambda kv: -kv[1])

    return (sorted(mislabel, reverse=True), sorted(copies, reverse=True), sorted(outliers),
            redundant, own_best, other_best)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("collection_dir")
    ap.add_argument("--dup-sim", type=float, default=0.97)
    ap.add_argument("--top", type=int, default=40, help="rows per section")
    a = ap.parse_args()
    for need in ("entries.json", "index.npz"):
        if not os.path.isfile(os.path.join(a.collection_dir, need)):
            sys.exit(f"{a.collection_dir} has no {need}: pass the collection folder itself (the one holding entries.json)")
    emb, entry, path, team, _ = load(a.collection_dir)
    mislabel, copies, outliers, redundant, own_best, other_best = audit(emb, entry, path, team, a.dup_sim)

    out = [f"{len(entry)} references, {len(set(entry))} entries with 2+ refs (entries with fewer are skipped)",
           f"{len(mislabel)} mislabel suspects, {len(copies)} cross-entry copies, {len(outliers)} outliers", ""]

    def row(i, j, extra):
        cross = " (same team)" if team.get(entry[j]) == team.get(entry[i]) else ""
        return f"  {path[i]}  [{entry[i]}]  ~  {path[j]}  [{entry[j]}]{cross}  {extra}"

    out.append("## mislabel suspects (closer to another entry than to its own; check the first file)")
    for m, i, j in mislabel[:a.top]:
        out.append(row(i, j, f"margin {m:.3f}  own {own_best[i]:.3f}  other {other_best[i]:.3f}"))
    out.append("\n## cross-entry copies (near-identical crop filed under two entries; one is wrong)")
    for s, i, j in copies[:a.top]:
        out.append(row(i, j, f"sim {s:.3f}"))
    out.append("\n## outliers (far from the rest of their own entry; wrong car, background or partial crop)")
    for z, i, j in outliers[:a.top]:
        out.append(f"  {path[i]}  [{entry[i]}]  z {z:.1f}  best own match {own_best[i]:.3f}")
    out.append("\n## redundant (refs with a near-duplicate in the same entry)")
    for name, c in redundant[:a.top]:
        out.append(f"  {name}: {c}")

    text = "\n".join(out) + "\n"
    with open(os.path.join(a.collection_dir, "ref-audit.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    print("\n".join(out[:2]) + f"\nwrote {os.path.join(a.collection_dir, 'ref-audit.txt')}")


if __name__ == "__main__":
    main()

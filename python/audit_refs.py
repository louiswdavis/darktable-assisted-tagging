"""Lists references that look wrongly filed, so you can review them by hand. Each reference is the
query once, matched against the others (centred embeddings, as the live matcher does). Reports only;
it never moves or deletes anything. Run from this folder:

  python audit_refs.py COLLECTION_DIR [--dup-sim 0.97] [--top 40]

Writes ref-audit.txt in COLLECTION_DIR. Sections:
  strongest candidates - refs flagged by 2+ of the checks below; start here
  mislabel suspects  - closer to another entry's refs than to its own (margin = other - own, 0.2+)
  cross-entry copies - near-identical to a ref filed under a different entry
  outliers           - far from the rest of its own entry (robust z-score, entries with 5+ refs)
  odd crops          - crop size or shape far from the entry's usual (distant car, whole frame, nose-only cut)
  colour outliers    - livery colours (hue/saturation, brightness ignored) unlike the entry's typical ones
  redundant          - near-duplicates inside one entry (add no variety)"""

import argparse
import os
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_matching import load, unit

MISLABEL_MIN_MARGIN = 0.2  # other-entry similarity must beat the own-entry one by this much
CROP_MIN_Z = 4.0  # robust z of crop size or aspect ratio against the entry's median
CROP_AREA_MAD_FLOOR = 0.15  # log scale, so 0.15 is about 16% in side length
CROP_ASPECT_MAD_FLOOR = 0.08
COLOUR_MAD_FLOOR = 0.03  # entries whose refs agree closely would otherwise flag normal lighting variation


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
        if other_best[i] - own_best[i] >= MISLABEL_MIN_MARGIN:
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


def colour_audit(collection_dir, entry, path):
    """Refs whose hue/saturation signature (colour.colour_hist, brightness-blind) is far from their
    entry's typical one. Returns [(z, i, own_sim, other_entry, other_sim)], worst first; an entry needs
    4+ refs. other_entry is the entry whose typical colours the ref matches best, if that beats its own."""
    from PIL import Image
    from colour import colour_hist
    hists = []
    for rel in path:
        with Image.open(os.path.join(collection_dir, *rel.split("/"))) as im:
            hists.append(colour_hist(np.array(im.convert("RGB"))))
    hists = np.stack(hists)
    ent = np.array(entry)
    names = sorted(set(entry))
    cent = {n: unit(np.median(hists[ent == n], axis=0)) for n in names}
    found = []
    for n in names:
        idx = np.where(ent == n)[0]
        if len(idx) < 4:
            continue
        sims = hists[idx] @ cent[n]
        med = np.median(sims)
        mad = max(np.median(np.abs(sims - med)), COLOUR_MAD_FLOOR)
        for k, i in enumerate(idx):
            z = (sims[k] - med) / (1.4826 * mad)
            if z < -3.0:
                others = {m: float(hists[i] @ cent[m]) for m in names if m != n}
                best = max(others, key=others.get)
                found.append((float(z), i, float(sims[k]), best if others[best] > sims[k] else "", others[best]))
    return sorted(found)


def crop_audit(collection_dir, entry, path):
    """Refs whose crop size or shape is far from their entry's usual: a distant car (small crop), a
    whole frame saved instead of a car, or a nose-only cut. Image headers only, no model. An entry
    needs 4+ refs. Returns [(score, i, (w, h), (median w, median h))], worst first."""
    from PIL import Image
    sizes = []
    for rel in path:
        with Image.open(os.path.join(collection_dir, *rel.split("/"))) as im:
            sizes.append(im.size)
    wh = np.array(sizes, dtype=float)
    log_area, log_aspect = np.log(wh[:, 0] * wh[:, 1]) / 2, np.log(wh[:, 0] / wh[:, 1])
    ent = np.array(entry)
    found = []
    for n in sorted(set(entry)):
        idx = np.where(ent == n)[0]
        if len(idx) < 4:
            continue
        worst = np.zeros(len(idx))
        for vals, floor in ((log_area[idx], CROP_AREA_MAD_FLOOR), (log_aspect[idx], CROP_ASPECT_MAD_FLOOR)):
            med = np.median(vals)
            mad = max(np.median(np.abs(vals - med)), floor)
            worst = np.maximum(worst, np.abs(vals - med) / (1.4826 * mad))
        med_wh = tuple(int(v) for v in np.median(wh[idx], axis=0))
        found += [(float(worst[k]), i, tuple(int(v) for v in wh[i]), med_wh) for k, i in enumerate(idx) if worst[k] > CROP_MIN_Z]
    return sorted(found, reverse=True)


def write_audit(collection_dir, dup_sim=0.97, top=40):
    """Audits collection_dir's index.npz and writes ref-audit.txt beside it. Returns
    (path written, {"references", "mislabel", "copies", "outliers"})."""
    emb, entry, path, team, _ = load(collection_dir)
    if len(set(entry)) < 2:
        sys.exit(f"{collection_dir} needs 2+ entries with 2+ references each to audit")
    mislabel, copies, outliers, redundant, own_best, other_best = audit(emb, entry, path, team, dup_sim)

    try:
        colours = colour_audit(collection_dir, entry, path)
    except ImportError:  # no cv2: the colour section is skipped
        colours = []
    crops = crop_audit(collection_dir, entry, path)
    out = [f"{len(entry)} references, {len(set(entry))} entries with 2+ refs (entries with fewer are skipped)",
           f"{len(mislabel)} mislabel suspects, {len(copies)} cross-entry copies, {len(outliers)} outliers, "
           f"{len(colours)} colour outliers, {len(crops)} odd crops", ""]

    def row(i, j, extra):
        cross = " (same team)" if team.get(entry[j]) == team.get(entry[i]) else ""
        return f"  {path[i]}  [{entry[i]}]  ~  {path[j]}  [{entry[j]}]{cross}  {extra}"

    flags = {}
    for label, items in (("mislabel", [(m, i) for m, i, _ in mislabel]), ("copy", [(s, i) for s, i, _ in copies]),
                         ("outlier", [(-z, i) for z, i, _ in outliers]), ("colour", [(-z, i) for z, i, *_ in colours]),
                         ("crop", [(z, i) for z, i, *_ in crops])):
        for _, i in items:
            flags.setdefault(i, []).append(label)
    strongest = sorted((i for i, f in flags.items() if len(f) >= 2), key=lambda i: (-len(flags[i]), path[i]))
    out.append("## strongest candidates (flagged by 2+ checks; look at these first)")
    for i in strongest[:top]:
        out.append(f"  {path[i]}  [{entry[i]}]  {', '.join(flags[i])}")
    out.append(f"  ({len(strongest)} in total)\n")
    out.append("## mislabel suspects (closer to another entry than to its own; check the first file)")
    for m, i, j in mislabel[:top]:
        out.append(row(i, j, f"margin {m:.3f}  own {own_best[i]:.3f}  other {other_best[i]:.3f}"))
    out.append("\n## cross-entry copies (near-identical crop filed under two entries; one is wrong)")
    for s, i, j in copies[:top]:
        out.append(row(i, j, f"sim {s:.3f}"))
    out.append("\n## outliers (far from the rest of their own entry; wrong car, background or partial crop)")
    for z, i, j in outliers[:top]:
        out.append(f"  {path[i]}  [{entry[i]}]  z {z:.1f}  best own match {own_best[i]:.3f}")
    out.append("\n## colour outliers (livery colours differ from the entry's typical ones; ignores brightness. 'looks like' names the entry whose colours it matches better)")
    for z, i, own, other, other_sim in colours[:top]:
        out.append(f"  {path[i]}  [{entry[i]}]  z {z:.1f}  own {own:.3f}" + (f"  looks like [{other}] {other_sim:.3f}" if other else ""))
    out.append("\n## odd crops (size or shape far from the entry's usual: distant car, whole frame, nose-only cut; these can be good refs too)")
    for z, i, (w, h), (mw, mh) in crops[:top]:
        out.append(f"  {path[i]}  [{entry[i]}]  {w}x{h}  entry median {mw}x{mh}  z {z:.1f}")
    out.append("\n## redundant (refs with a near-duplicate in the same entry)")
    for name, c in redundant[:top]:
        out.append(f"  {name}: {c}")

    report = os.path.join(collection_dir, "ref-audit.txt")
    with open(report, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    return report, {"references": len(entry), "mislabel": len(mislabel), "copies": len(copies), "outliers": len(outliers),
                    "colour": len(colours), "crops": len(crops), "strongest": len(strongest)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("collection_dir")
    ap.add_argument("--dup-sim", type=float, default=0.97)
    ap.add_argument("--top", type=int, default=40, help="rows per section")
    a = ap.parse_args()
    for need in ("entries.json", "index.npz"):
        if not os.path.isfile(os.path.join(a.collection_dir, need)):
            sys.exit(f"{a.collection_dir} has no {need}: pass the collection folder itself (the one holding entries.json)")
    report, counts = write_audit(a.collection_dir, a.dup_sim, a.top)
    print(f"{counts}\nwrote {report}")


if __name__ == "__main__":
    main()

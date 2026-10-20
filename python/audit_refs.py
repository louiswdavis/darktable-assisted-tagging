"""Lists references that look wrongly filed, so you can review them by hand. Each reference is the
query once, matched against the others (centred embeddings, as the live matcher does). Reports only;
it never moves or deletes anything. Run from this folder:

  python audit_refs.py COLLECTION_DIR [--dup-sim 0.97] [--top 40] [--detector PATH.onnx] [--suggest-crops]

Writes ref-audit.txt in COLLECTION_DIR. Sections:
  strongest candidates - refs flagged by 2+ of the checks below; start here
  attractors         - correctly filed refs that are the closest match for other entries' refs (they pull wrong cars in)
  mislabel suspects  - closer to another entry's refs than to its own (margin = other - own, 0.2+)
  cross-entry copies - near-identical to a ref filed under a different entry
  outliers           - far from the rest of its own entry (robust z-score, entries with 5+ refs)
  odd crops          - crop size or shape far from the entry's usual (distant car, whole frame, nose-only cut)
  colour outliers    - livery colours (hue/saturation, brightness ignored) unlike the entry's typical ones from the same event (ids close together = one weekend)
  whole frames       - refs where the detector finds no car, or one under 15% of the image (needs --detector)
  redundant          - near-duplicates inside one entry (add no variety)
  duplicate groups   - the near-duplicate files together with their similarity; often harmless burst frames"""

import argparse
import json
import os
import re
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_matching import load, unit

MISLABEL_MIN_MARGIN = 0.2  # other-entry similarity must beat the own-entry one by this much
CROP_MIN_Z = 4.0  # robust z of crop size or aspect ratio against the entry's median
CROP_AREA_MAD_FLOOR = 0.15  # log scale, so 0.15 is about 16% in side length
CROP_ASPECT_MAD_FLOOR = 0.08
WHOLE_FRAME_MAX_FRAC = 0.15  # detected car's share of the ref image below this = whole frame or scenery
FRAME_CACHE_NAME = "frame-share-cache.json"
QUARANTINE_DIR = "refs-quarantine"  # --quarantine moves the strongest candidates here, one folder per entry
QUARANTINE_LIST_NAME = "moved.txt"  # inside QUARANTINE_DIR; one line per moved file
CROP_SUGGEST_DIR = "ref-audit-crops"  # --suggest-crops writes re-cropped copies of wide refs here, one folder per entry
FRAME_FULL_LIST_NAME = "ref-audit-frames.txt"  # every flagged whole frame; the report shows only the first `top`
FRAME_SHARE_BUCKETS = [0.05, 0.10, 0.15, 0.25, 0.50]  # histogram band edges for the car-share spread
ATTRACTOR_MIN_PULLS = 3  # wrong-entry queries a ref must win before it is listed as an attractor
EVENT_GAP = 1000  # ref ids further apart than this belong to different events (race weekends)
COLOUR_MIN_EVENT_REFS = 4  # an entry's refs from one event needed to score its colours against that event alone
STRONG_MIN_FLAGS = 2  # checks that must flag a ref for it to be a strongest candidate, to be quarantined, or to be refused at add time
COLOUR_MAD_FLOOR = 0.03 # entries whose refs agree closely would otherwise flag normal lighting variation


def audit(emb, entry, dup_sim):
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


def attractor_audit(emb, entry, team, dup_sim):
    """Refs that win matches they shouldn't, whatever their own label. Each ref is the query once and
    its single closest other ref (same-entry near-duplicates skipped, as in audit) wins it; a win for
    a ref of another entry is a wrong pull, which is how an odd-angle or odd-size ref misidentifies
    other cars. Teammates' cars look alike, so pulls from the same team are counted apart: only
    other-team pulls count toward the threshold. Returns [(other-team pulls, right pulls, i,
    {victim entry: pulls}, same-team pulls)] for refs with ATTRACTOR_MIN_PULLS+ other-team pulls and
    more of those than right ones, worst margin first."""
    x = unit(emb - emb.mean(axis=0))
    sims = x @ x.T
    n = len(entry)
    ent = np.array(entry)
    same = ent[:, None] == ent[None, :]
    eligible = ~np.eye(n, dtype=bool) & ~(same & (sims >= dup_sim))
    winner = np.where(eligible, sims, -np.inf).argmax(axis=1)
    wrong, right, mates, victims = Counter(), Counter(), Counter(), {}
    for q, j in enumerate(winner):
        if ent[q] == ent[j]:
            right[j] += 1
        elif team.get(ent[q]) is not None and team.get(ent[q]) == team.get(ent[j]):
            mates[j] += 1
        else:
            wrong[j] += 1
            victims.setdefault(j, Counter())[ent[q]] += 1
    found = [(wrong[j], right[j], j, dict(victims[j]), mates[j]) for j in wrong
             if wrong[j] >= ATTRACTOR_MIN_PULLS and wrong[j] > right[j]]
    return sorted(found, key=lambda t: (t[1] - t[0], -t[0]))


def duplicate_groups(collection_dir, emb, entry, path, dup_sim):
    """Near-duplicate refs inside one entry (centred-embedding similarity >= dup_sim, chained). Returns
    [(keep, [drop, ...], lowest similarity of a drop to keep)] as indexes into path, biggest group first.
    The ref named keep is the one with the most pixels (ties: first filename)."""
    from PIL import Image
    x = unit(emb - emb.mean(axis=0))
    sims = x @ x.T
    ent = np.array(entry)
    link = (sims >= dup_sim) & (ent[:, None] == ent[None, :])
    seen, groups = set(), []
    for start in range(len(entry)):
        if start in seen or link[start].sum() < 2:
            continue
        group, todo = set(), [start]
        while todo:
            i = todo.pop()
            if i not in group:
                group.add(i)
                todo += [int(j) for j in np.where(link[i])[0]]
        seen |= group
        area = {}
        for i in group:
            with Image.open(os.path.join(collection_dir, *path[i].split("/"))) as im:
                area[i] = im.size[0] * im.size[1]
        order = sorted(group, key=lambda i: (-area[i], path[i]))
        groups.append((order[0], order[1:], float(min(sims[order[0], j] for j in order[1:]))))
    return sorted(groups, key=lambda g: -len(g[1]))


def ref_events(path):
    """Groups refs into events (race weekends). The file stem is the photo's darktable id, which follows
    import order, and a weekend's photos are imported together, so ids split into events wherever two
    consecutive ids across all refs are more than EVENT_GAP apart. Returns ([event number per ref],
    [(lowest id, highest id, refs)] per event)."""
    ids = [int(re.match(r"\d+", os.path.basename(p)).group()) for p in path]  # stems like 139712_b0 carry a box suffix
    event_of, event, prev = {}, 0, None
    for v in sorted(set(ids)):
        if prev is not None and v - prev > EVENT_GAP:
            event += 1
        event_of[v], prev = event, v
    events = [event_of[v] for v in ids]
    ranges = [(min(v for v, e in zip(ids, events) if e == k), max(v for v, e in zip(ids, events) if e == k),
               events.count(k)) for k in range(event + 1)]
    return events, ranges


def colour_audit(collection_dir, entry, path, events):
    """Refs whose hue/saturation signature (colour.colour_hist, brightness-blind) is far from their
    entry's typical one. Liveries change between weekends, so a ref is scored against the same entry's
    refs from its own event (ref_events) when that has COLOUR_MIN_EVENT_REFS+ refs, else against the
    whole entry. Returns [(z, i, own_sim, other_entry, other_sim)], worst first; an entry needs 4+ refs.
    other_entry is the entry whose typical colours the ref matches best, if that beats its own."""
    from PIL import Image
    from colour import colour_hist
    hists = []
    for rel in path:
        with Image.open(os.path.join(collection_dir, *rel.split("/"))) as im:
            hists.append(colour_hist(np.array(im.convert("RGB"))))
    hists = np.stack(hists)
    ent = np.array(entry)
    names = sorted(set(entry))
    ev = np.array(events)
    cent = {n: unit(np.median(hists[ent == n], axis=0)) for n in names}
    found = []
    for n in names:
        idx = np.where(ent == n)[0]
        if len(idx) < 4:
            continue
        for e in sorted(set(ev[idx])):
            sub = idx[ev[idx] == e]
            group = sub if len(sub) >= COLOUR_MIN_EVENT_REFS else idx
            centre = unit(np.median(hists[group], axis=0))
            med = np.median(hists[group] @ centre)
            mad = max(np.median(np.abs(hists[group] @ centre - med)), COLOUR_MAD_FLOOR)
            for i in sub:
                own = float(hists[i] @ centre)
                z = (own - med) / (1.4826 * mad)
                if z < -3.0:
                    others = {m: float(hists[i] @ cent[m]) for m in names if m != n}
                    best = max(others, key=others.get)
                    found.append((float(z), i, own, best if others[best] > own else "", others[best]))
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


class AuditCancelled(Exception):
    """on_progress returned False: the caller wants the audit stopped."""


def _file_stamp(p):
    st = os.stat(p)
    return f"{st.st_size}:{st.st_mtime_ns}"


def frame_audit(collection_dir, path, detector, on_progress=None, need_boxes=False):
    """Each ref's car share: the largest detected vehicle's fraction of the ref image (0 when the
    detector finds none). A good ref is already cropped to its car, so the car fills most of the image.
    Shares and the detected boxes are cached in FRAME_CACHE_NAME beside the index, keyed by each ref
    file's size and mtime and by the detector file and threshold, so a re-run only detects new or changed
    refs. need_boxes also re-detects refs cached without boxes (caches from before boxes were stored).
    on_progress(done, total) is called per ref; a False return raises AuditCancelled (results found so
    far stay cached). Returns (shares, boxes), each aligned with `path`; a ref's boxes are
    [x0, y0, x1, y1] lists in its own pixels."""
    from PIL import Image
    from vehicles import DETECTOR_MIN_SCORE, detect_vehicles
    cache_path = os.path.join(collection_dir, FRAME_CACHE_NAME)
    detector_id = f"{os.path.basename(detector)}:{_file_stamp(detector)}:{DETECTOR_MIN_SCORE}"
    cached = {}
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            saved = json.load(f)
        if saved.get("detector") == detector_id:
            cached = saved.get("refs", {})
    shares, all_boxes = [], []
    try:
        for i, rel in enumerate(path):
            if on_progress and not on_progress(i, len(path)):
                raise AuditCancelled()
            file = os.path.join(collection_dir, *rel.split("/"))
            stamp = _file_stamp(file)
            hit = cached.get(rel)
            if hit and hit["stamp"] == stamp and (not need_boxes or "boxes" in hit):
                shares.append(hit["share"])
                all_boxes.append(hit.get("boxes", []))
                continue
            with Image.open(file) as im:
                rgb = np.array(im.convert("RGB"))
            boxes, _ = detect_vehicles(rgb, detector)
            h, w = rgb.shape[:2]
            share = max(((b[2] - b[0]) * (b[3] - b[1]) / (w * h) for b in boxes), default=0.0)
            plain = [[float(v) for v in b[:4]] for b in boxes]
            cached[rel] = {"stamp": stamp, "share": share, "boxes": plain}
            shares.append(share)
            all_boxes.append(plain)
    finally:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"detector": detector_id, "refs": cached}, f)
    return shares, all_boxes


def suggest_crops(collection_dir, path, entry, frames, boxes):
    """Writes a re-cropped copy of each wide ref where the detector found exactly one car (vehicles.
    crop_box, as saved refs are cut) into CROP_SUGGEST_DIR/<entry>/, replacing any earlier suggestions.
    Refs with no car or several cars are skipped: with several, which one is the entry is unknown.
    frames is [(share, i)] as in write_audit. Returns ([i of each written ref], count skipped for no
    car, count skipped for several cars). Never touches the refs themselves."""
    import shutil
    from PIL import Image
    from vehicles import crop_box
    out_dir = os.path.join(collection_dir, CROP_SUGGEST_DIR)
    shutil.rmtree(out_dir, ignore_errors=True)
    written, no_car, several = [], 0, 0
    for share, i in frames:
        if share == 0.0 or not boxes[i]:
            no_car += 1
            continue
        if len(boxes[i]) > 1:
            several += 1
            continue
        with Image.open(os.path.join(collection_dir, *path[i].split("/"))) as im:
            rgb = np.array(im.convert("RGB"))
        dest = os.path.join(out_dir, entry[i], os.path.basename(path[i]))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        Image.fromarray(crop_box(rgb, boxes[i])).save(dest, quality=95)
        written.append(i)
    return written, no_car, several


def share_histogram(shares):
    """Counts of shares per FRAME_SHARE_BUCKETS band, as report lines."""
    lines = [f"  no car found: {sum(1 for s in shares if s == 0.0)}"]
    for lo, hi in zip([0.0] + FRAME_SHARE_BUCKETS, FRAME_SHARE_BUCKETS + [1.01]):
        lines.append(f"  {lo:.0%} to {min(hi, 1.0):.0%}: {sum(1 for s in shares if s > 0.0 and lo <= s < hi)}")
    return lines


def quarantine_refs(collection_dir, path, entry, chosen, flags):
    """Moves the refs at the `chosen` indexes into QUARANTINE_DIR/<entry>/ and appends one line per
    file to QUARANTINE_LIST_NAME there (new path, old path, flags). Existing quarantine files stay.
    The index.npz still holds them until the next audit's index refresh drops them. Returns the
    indexes moved."""
    import shutil
    moved = []
    root = os.path.join(collection_dir, QUARANTINE_DIR)
    for i in chosen:
        src = os.path.join(collection_dir, *path[i].split("/"))
        dest = os.path.join(root, entry[i], os.path.basename(path[i]))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(src, dest)
        moved.append(i)
    with open(os.path.join(root, QUARANTINE_LIST_NAME), "a", encoding="utf-8") as f:
        f.writelines(f"{QUARANTINE_DIR}/{entry[i]}/{os.path.basename(path[i])}\t{path[i]}\t{','.join(flags[i])}\n" for i in moved)
    return moved


def ref_flags(mislabel, copies, outliers, colours, crops, frames):
    """{ref index: [check names that flag it]} from the per-check lists; frames is a list of ref indexes."""
    flags = {}
    for label, idx in (("mislabel", [i for _, i, _ in mislabel]), ("copy", [i for _, i, _ in copies]),
                       ("outlier", [i for _, i, _ in outliers]), ("colour", [i for _, i, *_ in colours]),
                       ("crop", [i for _, i, *_ in crops]), ("frame", frames)):
        for i in idx:
            flags.setdefault(i, []).append(label)
    return flags


def screen_refs(collection_dir, rels, dup_sim=0.97):
    """The audit's per-ref checks (not attractors or whole frames, which need every ref queried or a
    detector) run for just `rels`, refs already in the saved index. Returns {rel: [check names]} for
    those with a flag; empty when the index holds under 2 entries. Entries with too few refs for a check
    (5 for outliers, 4 for colour and crop) pass it, as in the audit."""
    emb, entry, path, _team, _ = load(collection_dir)
    if len(set(entry)) < 2:
        return {}
    mislabel, copies, outliers, *_ = audit(emb, entry, dup_sim)
    try:
        colours = colour_audit(collection_dir, entry, path, ref_events(path)[0])
    except ImportError:  # no cv2: the colour check is skipped
        colours = []
    flags = ref_flags(mislabel, copies, outliers, colours, crop_audit(collection_dir, entry, path), [])
    wanted = set(rels)
    return {path[i]: f for i, f in flags.items() if path[i] in wanted}


def write_audit(collection_dir, dup_sim=0.97, top=40, detector="", on_progress=None, crops_wanted=False,
                quarantine=False):
    """Audits collection_dir's index.npz and writes ref-audit.txt beside it. detector (YOLOX .onnx)
    enables the whole-frame check; without it that section is skipped. crops_wanted (needs the
    detector) also writes suggested re-crops of wide refs to CROP_SUGGEST_DIR; the first such run
    re-detects refs cached without boxes, so it is slow. on_progress is passed to
    frame_audit (the slow step); AuditCancelled propagates and no report is written. Returns
    (path written, {"references", "mislabel", "copies", "outliers", ...})."""
    emb, entry, path, team, _ = load(collection_dir)
    if len(set(entry)) < 2:
        sys.exit(f"{collection_dir} needs 2+ entries with 2+ references each to audit")
    mislabel, copies, outliers, redundant, own_best, other_best = audit(emb, entry, dup_sim)

    events, event_ranges = ref_events(path)
    try:
        colours = colour_audit(collection_dir, entry, path, events)
    except ImportError:  # no cv2: the colour section is skipped
        colours = []
    crops = crop_audit(collection_dir, entry, path)
    attractors = attractor_audit(emb, entry, team, dup_sim)
    shares, boxes = frame_audit(collection_dir, path, detector, on_progress, crops_wanted) if detector else ([], [])
    # a small car was found (likely real scenery) before no car found (often a detector miss); the nearest-to-cutoff first
    frames = sorted(((s, i) for i, s in enumerate(shares) if s < WHOLE_FRAME_MAX_FRAC),
                    key=lambda t: (t[0] == 0.0, -t[0], path[t[1]]))
    out = [f"{len(entry)} references, {len(set(entry))} entries with 2+ refs (entries with fewer are skipped)",
           f"{len(mislabel)} mislabel suspects, {len(copies)} cross-entry copies, {len(outliers)} outliers, "
           f"{len(colours)} colour outliers, {len(crops)} odd crops, {len(attractors)} attractors, "
           + (f"{len(frames)} whole frames" if detector else "whole-frame check skipped (no detector)"),
           f"events (ids more than {EVENT_GAP} apart split; colour outliers are judged within an event): "
           + ", ".join(f"{lo}-{hi} ({c})" for lo, hi, c in event_ranges), ""]

    def row(i, j, extra):
        cross = " (same team)" if team.get(entry[j]) == team.get(entry[i]) else ""
        return f"  {path[i]}  [{entry[i]}]  ~  {path[j]}  [{entry[j]}]{cross}  {extra}"

    flags = ref_flags(mislabel, copies, outliers, colours, crops, [i for s, i in frames if s > 0.0])
    strongest = sorted((i for i, f in flags.items() if len(f) >= STRONG_MIN_FLAGS), key=lambda i: (-len(flags[i]), path[i]))
    out.append("## strongest candidates (flagged by 2+ checks; look at these first)")
    for i in strongest[:top]:
        out.append(f"  {path[i]}  [{entry[i]}]  {', '.join(flags[i])}")
    out.append(f"  ({len(strongest)} in total)\n")
    out.append(f"## attractors (correctly filed, but the closest match for {ATTRACTOR_MIN_PULLS}+ refs of other teams' entries and more of those than of its own: an odd angle or size that pulls other cars toward this entry. Teammates' cars look alike, so their pulls are shown but not counted. Removing one costs its own entry some coverage, so check 'pulls' against 'own')")
    for wrong, right, i, victims, mates in attractors[:top]:
        names = ", ".join(f"{v} x{c}" for v, c in sorted(victims.items(), key=lambda kv: -kv[1])[:4])
        out.append(f"  {path[i]}  [{entry[i]}]  other-team pulls {wrong}  own {right}  teammate pulls {mates}  pulled: {names}")
    out.append(f"  ({len(attractors)} in total)\n")
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
    out.append(f"\n## whole frames (detected car covers under {WHOLE_FRAME_MAX_FRAC:.0%} of the ref: scenery drives its matches, but it also fires when the detector misses a dark or blurred car, so look before deleting. A small car found comes first, nearest the cutoff; 'no car found' refs follow and are the likelier detector misses. Every one is in {FRAME_FULL_LIST_NAME})")
    if detector:
        out.append("  car share across all refs:")
        out += ["  " + line for line in share_histogram(shares)]
    for share, i in frames[:top]:
        out.append(f"  {path[i]}  [{entry[i]}]  car share {share:.1%}")
    out.append(f"  ({len(frames)} in total)")
    if detector:
        with open(os.path.join(collection_dir, FRAME_FULL_LIST_NAME), "w", encoding="utf-8") as f:
            f.writelines(f"{path[i]}\t{entry[i]}\t{share:.4f}\n" for share, i in frames)
    suggested = []
    if detector and crops_wanted:
        suggested, no_car, several = suggest_crops(collection_dir, path, entry, frames, boxes)
        out.append(f"\n## suggested crops (a wide ref with exactly one car found, re-cut to it: copies in {CROP_SUGGEST_DIR}/<entry>/. Look at each; if it is the right car, copy it over the ref in refs/<entry>/. Nothing in refs/ was changed. Skipped: {no_car} with no car found, {several} with several cars)")
        for i in suggested[:top]:
            out.append(f"  {path[i]}  [{entry[i]}]")
        out.append(f"  ({len(suggested)} in total)")
    out.append("\n## redundant (refs with a near-duplicate in the same entry)")
    for name, c in redundant[:top]:
        out.append(f"  {name}: {c}")
    out.append("\n## duplicate groups (near-identical crops of one entry; many are burst frames of the same car and fine to keep, so judge by eye. sim = lowest match to the first file)")
    for keep, drops, low in duplicate_groups(collection_dir, emb, entry, path, dup_sim)[:top]:
        out.append(f"  {path[keep]}  [{entry[keep]}]  ~  {', '.join(path[i] for i in drops)}  sim {low:.3f}")

    moved = quarantine_refs(collection_dir, path, entry, strongest, flags) if quarantine else []
    if quarantine:
        out.append(f"\n## quarantined (the strongest candidates, moved out of refs/ into {QUARANTINE_DIR}/<entry>/; {QUARANTINE_LIST_NAME} lists each. To undo, copy a file back into refs/<entry>/ and re-run the audit)")
        out += [f"  {path[i]}  [{entry[i]}]  {', '.join(flags[i])}" for i in moved[:top]]
        out.append(f"  ({len(moved)} in total)")

    report = os.path.join(collection_dir, "ref-audit.txt")
    with open(report, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    return report, {"references": len(entry), "mislabel": len(mislabel), "copies": len(copies), "outliers": len(outliers),
                    "colour": len(colours), "crops": len(crops), "attractors": len(attractors), "frames": len(frames), "strongest": len(strongest),
                    "suggested": len(suggested), "quarantined": len(moved)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("collection_dir")
    ap.add_argument("--dup-sim", type=float, default=0.97)
    ap.add_argument("--top", type=int, default=40, help="rows per section")
    ap.add_argument("--detector", default="", help="YOLOX .onnx; enables the whole-frame check")
    ap.add_argument("--suggest-crops", action="store_true",
                    help=f"also write re-cropped copies of wide refs to {CROP_SUGGEST_DIR}/ (needs --detector)")
    ap.add_argument("--quarantine", action="store_true",
                    help=f"move the strongest candidates (2+ checks) out of refs/ into {QUARANTINE_DIR}/")
    a = ap.parse_args()
    if a.suggest_crops and not a.detector:
        sys.exit("--suggest-crops needs --detector")
    for need in ("entries.json", "index.npz"):
        if not os.path.isfile(os.path.join(a.collection_dir, need)):
            sys.exit(f"{a.collection_dir} has no {need}: pass the collection folder itself (the one holding entries.json)")
    report, counts = write_audit(a.collection_dir, a.dup_sim, a.top, a.detector, crops_wanted=a.suggest_crops, quarantine=a.quarantine)
    print(f"{counts}\nwrote {report}")


if __name__ == "__main__":
    main()

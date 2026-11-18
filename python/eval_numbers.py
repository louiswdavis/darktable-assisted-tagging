"""Scores the number reader against hand-tagged truth from a --verify run's boxes.json, and replays
the number path with other thresholds. Run from this folder:

  python eval_numbers.py BOXES.json                            # today's thresholds
  python eval_numbers.py BOXES.json --set OCR_MIN_SCORE=0.7    # what a lower detection floor would read

Truth is each image's hand entry, else the entry whose tags it already carries. Only single-box
frames are scored (which box is the car is unknown otherwise); the rest are counted. A box that is
not read right gets one cause: no region, region dropped (and why), below min_read, recognised
wrong, or the right read lost in matching. The replay with no --set must agree with the live run:
it reports how many boxes do, and lists the ones that don't."""

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import match
from match import Entry, hinted_match, usable_reads, without_noise
from ocr import digit_runs, drop_reason, pick_reads

# --set name → boxes.json thresholds key
KNOBS = {"OCR_MIN_SCORE": "ocr_min_score", "NUMBER_MIN_HEIGHT": "number_min_height", "min_read": "min_read",
         "WEAK_READ_MIN": "weak_read_min", "NUMBER_LIST_MARGIN": "number_list_margin",
         "NUMBER_LIST_FLOOR": "number_list_floor"}


def load_entries(data: dict) -> dict:
    """boxes.json's entries as match.Entry, with the fields the number path reads."""
    return {eid: Entry(eid, e["number"], e["team"], tuple(e["tags"]), e.get("camera", ""),
                       colour=e.get("colour", ""), car=e.get("car", ""))
            for eid, e in data["entries"].items()}


def replay_noise(data: dict, entries: dict, knobs: dict) -> dict:
    """The run's noise numbers under `knobs`, from every box's reads the way identify's match_all
    feeds match.noise_numbers: each box's OCR regions picked again with the replay's floors (its
    stored reads when it kept no regions), counted at the replay's min_read. A boxes.json from
    before noise numbers was matched without them, so its replay has none."""
    if "noise_numbers" not in data:
        return {}
    reads = [pick_reads(box["ocr_regions"], knobs["ocr_min_score"], knobs["number_min_height"])[0]
             if "ocr_regions" in box else [tuple(c) for c in box["ocr"]]
             for img in data["images"].values() for box in img["boxes"]]
    return match.noise_numbers(reads, entries, knobs["min_read"])


def replay_box(box: dict, entries: dict, knobs: dict, noise: dict) -> tuple:
    """(BoxResult, accepted reads) for one box, decided from its stored OCR regions the way
    match_frame decides it, up to hinted_match. `noise` is replay_noise's noise numbers."""
    reads, ctc = pick_reads(box["ocr_regions"], knobs["ocr_min_score"], knobs["number_min_height"])
    reads = without_noise(usable_reads(reads, ctc, knobs["min_read"]), noise)
    hint = box.get("hint") or {}
    r, _ = hinted_match(box["box"], reads, [tuple(s) for s in box["sims"]], entries,
                        hint.get("prefixes", []), hint.get("source", ""), ctc, knobs["min_read"])
    return r, reads


def cause(number: str, reads: list, regions: list, knobs: dict) -> str:
    """Why a box whose car carries `number` was not read as it: the right number was accepted but
    lost in matching, a region read it but was dropped (with drop_reason's reason) or fell under
    min_read, regions were recognised as something else, or there was no region at all."""
    if number in {d for d, _ in reads}:
        return "lost in matching"
    right = [g for g in regions if number in digit_runs(g["text"])]
    if right:
        reasons = [drop_reason(g, knobs["ocr_min_score"], knobs["number_min_height"]) for g in right]
        return "below min_read" if "" in reasons else f"dropped: {reasons[0]}"
    return "recognised wrong" if regions else "no region"


def weak_read(number: str, regions: list, knobs: dict) -> bool:
    """A passing region read `number` at WEAK_READ_MIN or more but under min_read."""
    return any(number in digit_runs(g["text"])
               and not drop_reason(g, knobs["ocr_min_score"], knobs["number_min_height"])
               and knobs["weak_read_min"] <= min(g["det"], g["rec"]) < knobs["min_read"]
               for g in regions)


def parse_sets(pairs: list) -> dict:
    out = {}
    for pair in pairs:
        name, _, value = pair.partition("=")
        if name not in KNOBS or not value:
            sys.exit(f"--set {pair}: use NAME=value with NAME one of {', '.join(KNOBS)}")
        out[name] = float(value)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("boxes")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=value",
                    help="override a threshold for the replay: " + ", ".join(KNOBS))
    ap.add_argument("--show", type=int, default=10, help="mismatches and confusions to list")
    args = ap.parse_args()

    with open(args.boxes, encoding="utf-8") as f:
        data = json.load(f)
    images = data["images"]
    if not any("ocr_regions" in b for img in images.values() for b in img["boxes"]):
        sys.exit(f"{args.boxes} has no OCR regions: run identify with --verify and --boxes-out first")
    sets = parse_sets(args.set)
    knobs = {key: sets.get(name, data["thresholds"][key]) for name, key in KNOBS.items()}
    for name in ("NUMBER_LIST_MARGIN", "NUMBER_LIST_FLOOR"):
        setattr(match, name, knobs[KNOBS[name]])
    entries = load_entries(data)
    noise = replay_noise(data, entries, knobs)

    frames, causes, confusion, mismatches = Counter(), Counter(), Counter(), []
    agree = replayed = weak = 0
    for image_id, img in images.items():
        truth = img.get("hand") or img.get("tagged")
        if not truth:
            frames["no truth"] += 1
            continue
        if len(img["boxes"]) != 1:
            frames["no vehicle" if not img["boxes"] else "skipped: more than one box"] += 1
            continue
        number = entries[truth].number
        if not number:
            frames["truth entry has no number"] += 1
            continue
        box = img["boxes"][0]
        if "ocr_regions" not in box:
            frames["no OCR regions"] += 1
            continue
        r, reads = replay_box(box, entries, knobs, noise)
        read = r.entry_id if r.method == "number" else ""
        replayed += 1
        if read == box["read_entry"]:
            agree += 1
        else:
            mismatches.append(f"{image_id}: live {box['read_entry'] or '-'}, replay {read or '-'}")
        frames["scored"] += 1
        got = entries[read].number if read else ""
        if got == number:
            frames["correct"] += 1
            continue
        frames["wrong entry" if read else "unread"] += 1
        causes[cause(number, reads, box["ocr_regions"], knobs)] += 1
        confusion[(number, got or (reads[0][0] if reads else "none"))] += 1
        if not read and weak_read(number, box["ocr_regions"], knobs):
            weak += 1

    scored = frames["scored"]
    share = (lambda n: f"{n} ({100.0 * n / scored:.1f}%)") if scored else str
    print("thresholds: " + ", ".join(f"{name}={knobs[key]}{' (set)' if name in sets else ''}" for name, key in KNOBS.items()))
    print(f"replay {'with --set ' if sets else ''}agrees with the live run on {agree}/{replayed} boxes"
          + ("" if sets or agree == replayed else "  <- should be all: the replay is out of step with match_frame"))
    for line in mismatches[:args.show]:
        print(f"  {line}")
    print(f"frames: {scored} scored; " + "; ".join(f"{n} {k}" for k, n in sorted(frames.items())
                                                    if k not in ("scored", "correct", "wrong entry", "unread")))
    print(f"read right {share(frames['correct'])}, wrong entry {share(frames['wrong entry'])}, unread {share(frames['unread'])}")
    print("misses by cause:")
    for name, n in causes.most_common():
        print(f"  {name}: {n}")
    print(f"unread boxes with a weak read of the right number (WEAK_READ_MIN..min_read): {weak}")
    print("confusions (truth -> read):")
    for (want, got), n in confusion.most_common(args.show):
        print(f"  {want} -> {got}: {n}")


if __name__ == "__main__":
    main()

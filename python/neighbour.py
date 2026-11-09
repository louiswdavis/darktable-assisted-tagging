"""Neighbour aid: groups shot just before and after a photo help a doubtful number read.

Cars pass in number order, or close to it, and loop. Distance is counted in positions of the
collection's sorted distinct numbers around a circle, so gaps in the list cost nothing and the end of
a loop (highest number, then lowest) is one step. Pure functions on plain data; no I/O."""

from dataclasses import replace

from match import IDENTIFIED, BoxResult, Entry, _one_confusion_apart

NEIGHBOUR_WINDOW = 3  # groups either side of a group that can lend support
NEIGHBOUR_MAX_GAP_S = 120  # a neighbour shot further away than this (a stage break) is ignored
DOUBT_CONF = 0.90  # a number read below this is doubtful; reads under ocr.OCR_MIN_SCORE (0.80) never get here
ACCEPT_SCORE = 0.5  # support x order_weight a candidate needs to be taken
FLAG_MIN_WEIGHT = 0.5  # order_weight at which a doubtful read with no support is flagged


def entry_positions(entries: dict) -> dict:
    """Distinct integer values of the entries' all-digit numbers, sorted, mapped to their position.
    `007` and `7` are one value; entries without a number are skipped."""
    values = sorted({int(e.number) for e in entries.values() if e.number.isdigit()})
    return {v: i for i, v in enumerate(values)}


def position_distance(a: int, b: int, count: int) -> int:
    """Circular distance between two positions in a list of `count`."""
    d = abs(a - b)
    return min(d, count - d)


def _one_digit_edit(a: str, b: str) -> bool:
    """True when one string is the other with exactly one digit inserted."""
    if len(a) < len(b):
        a, b = b, a
    return len(a) == len(b) + 1 and any(a[:i] + a[i + 1:] == b for i in range(len(a)))


def candidates_for(digits: str, entries: dict) -> list:
    """Ids of entries whose number is one look-alike digit apart from `digits` or one digit added or
    dropped. An exact match is not a candidate: match_box has already taken those."""
    return sorted(e.id for e in entries.values()
                  if e.number and e.number != digits
                  and (_one_confusion_apart(digits, e.number) or _one_digit_edit(digits, e.number)))


def _group_times(frames: dict, burst_of: dict, times: dict) -> dict:
    """Group id to its earliest positive capture time; groups with no timed photo are left out."""
    out: dict = {}
    for fid in frames:
        t = times.get(fid)
        if t and t > 0:
            g = burst_of.get(fid, fid)
            out[g] = min(out.get(g, t), t)
    return out


def neighbour_aid(frames: dict, burst_of: dict, times: dict, entries: dict,
                  tolerance: int, weight: float) -> dict:
    """frames: image id to [BoxResult]; times: image id to capture seconds (0 or missing = untimed).
    A `none` box with digits read takes the one candidate whose support from nearby groups, times
    `weight`, reaches ACCEPT_SCORE (method `neighbour`). A doubtful `number` read that no nearby group
    supports is flagged (`order_flag`), result unchanged. Clear reads are never touched.
    Returns `frames` itself when weight is 0 or there is nothing to measure against."""
    positions = entry_positions(entries)
    if weight <= 0 or not positions:
        return frames
    count = len(positions)

    def pos(eid: str):
        e = entries.get(eid)
        return positions.get(int(e.number)) if e and e.number.isdigit() else None

    members: dict = {}
    for fid in frames:
        members.setdefault(burst_of.get(fid, fid), []).append(fid)
    seen = {g: [r.entry_id for fid in ids for r in frames[fid]
                if r.method in IDENTIFIED and pos(r.entry_id) is not None]
            for g, ids in members.items()}
    gtimes = _group_times(frames, burst_of, times)
    ordered = sorted(gtimes, key=gtimes.get)

    def window(g) -> list:
        i = ordered.index(g)
        near = ordered[max(0, i - NEIGHBOUR_WINDOW):i] + ordered[i + 1:i + 1 + NEIGHBOUR_WINDOW]
        return [eid for n in near if abs(gtimes[n] - gtimes[g]) <= NEIGHBOUR_MAX_GAP_S for eid in seen[n]]

    def support(eid: str, around: list) -> float:
        p = pos(eid)
        if p is None:
            return 0.0
        best = 0.0
        for other in around:
            d = position_distance(p, pos(other), count)
            if d <= tolerance:
                best = max(best, 1 - d / (tolerance + 1))
        return best

    out = dict(frames)
    for g in ordered:
        around = window(g)
        if not around:
            continue
        for fid in members[g]:
            boxes = []
            for r in frames[fid]:
                if r.method == "none" and r.unmatched_number:
                    cands = {c for d in r.unmatched_number.split(";") for c in candidates_for(d, entries)}
                    scored = sorted(((support(c, around) * weight, c) for c in cands), reverse=True)
                    if scored and scored[0][0] >= ACCEPT_SCORE and (len(scored) == 1 or scored[0][0] > scored[1][0]):
                        r = replace(r, method="neighbour", entry_id=scored[0][1], confidence=scored[0][0])
                elif (r.method == "number" and r.confidence < DOUBT_CONF and weight >= FLAG_MIN_WEIGHT
                      and support(r.entry_id, around) == 0):
                    r = replace(r, order_flag=True)
                boxes.append(r)
            out[fid] = boxes
    return out

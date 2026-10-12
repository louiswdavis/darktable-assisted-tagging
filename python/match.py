"""Identification rules: number first, then livery similarity, then burst
consensus. Pure functions over OCR candidates and similarities."""

from dataclasses import dataclass, replace

MATCH_MIN_SIM = 0.60
MATCH_MIN_MARGIN = 0.05
BURST_MIN_AGREE = 2

IDENTIFIED = ("number", "livery")


@dataclass(frozen=True)
class Entry:
    id: str
    number: str
    team: str
    tags: tuple


@dataclass(frozen=True)
class BoxResult:
    box: int  # -1: the frame had no vehicle
    method: str  # number | livery | team | burst | none
    entry_id: str = ""
    alt_entry_id: str = ""
    confidence: float = 0.0


def match_box(box: int, ocr: list, sims: list, entries: dict) -> BoxResult:
    """ocr: [(digits, confidence)]; sims: [(entry_id, similarity)] most similar first."""
    by_number: dict = {}
    for e in entries.values():
        if e.number:
            by_number.setdefault(e.number, []).append(e.id)
    hits, best_conf = set(), 0.0
    for digits, conf in ocr:
        for eid in by_number.get(digits, []):
            hits.add(eid)
            best_conf = max(best_conf, conf)
    if len(hits) == 1:
        return BoxResult(box, "number", hits.pop(), "", best_conf)

    sims = [(eid, s) for eid, s in sims if eid in entries]
    if not sims:
        return BoxResult(box, "none")
    (e1, s1), (e2, s2) = sims[0], sims[1] if len(sims) > 1 else ("", 0.0)
    if s1 >= MATCH_MIN_SIM and s1 - s2 >= MATCH_MIN_MARGIN:
        return BoxResult(box, "livery", e1, "", s1)
    if s1 >= MATCH_MIN_SIM and e2 and entries[e1].team and entries[e1].team == entries[e2].team:
        return BoxResult(box, "team", e1, e2, s1)
    return BoxResult(box, "none", "", "", max(s1, 0.0))


def burst_consensus(frames: dict, burst_of: dict) -> dict:
    """frames: image id → [BoxResult]. A frame none of whose boxes was identified
    takes its burst's entry on its largest box when at least BURST_MIN_AGREE
    frames agree on that entry and no frame names another."""
    members: dict = {}
    for fid in frames:
        members.setdefault(burst_of.get(fid, fid), []).append(fid)
    out = dict(frames)
    for ids in members.values():
        agree: dict = {}
        for fid in ids:
            for eid in {r.entry_id for r in frames[fid] if r.method in IDENTIFIED}:
                agree[eid] = agree.get(eid, 0) + 1
        if len(agree) != 1:
            continue
        (eid, n), = agree.items()
        if n < BURST_MIN_AGREE:
            continue
        for fid in ids:
            rows = frames[fid]
            if any(r.method in IDENTIFIED for r in rows) or not any(r.box == 0 for r in rows):
                continue
            out[fid] = [replace(r, method="burst", entry_id=eid, alt_entry_id="", confidence=n / len(ids))
                        if r.box == 0 else r for r in rows]
    return out

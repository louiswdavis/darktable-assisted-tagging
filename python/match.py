"""Identification rules: number first, then livery similarity, then burst
consensus. Pure functions over OCR candidates and similarities."""

from dataclasses import dataclass, replace

MATCH_MIN_SIM = 0.60
MATCH_MIN_MARGIN = 0.05
BURST_MIN_AGREE = 2
REFERENCE_MIN_MARGIN = 0.10  # a livery match must lead by this much to be saved as a reference

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
    method: str  # number | livery | team | burst | none | error (couldn't analyse; tags left alone)
    entry_id: str = ""
    alt_entry_id: str = ""
    confidence: float = 0.0
    # Set independently of `method` whenever OCR read digits that didn't resolve to exactly
    # one entry (no entry has that number, or more than one does): every distinct digit
    # string read, ";"-joined, for one diagnostic tag per string, even when livery/team/
    # burst still identified the vehicle.
    unmatched_number: str = ""


def match_livery(box: int, sims: list, entries: dict, unmatched: str = "") -> BoxResult:
    """sims: [(entry_id, similarity)] most similar first. Livery match, else a
    same-team tie-break, else none. Shared with pooled burst matching, so a caller
    can run this once on sims averaged across a burst instead of one frame's own."""
    sims = [(eid, s) for eid, s in sims if eid in entries]
    if not sims:
        return BoxResult(box, "none", "", "", 0.0, unmatched)
    (e1, s1), (e2, s2) = sims[0], sims[1] if len(sims) > 1 else ("", 0.0)
    if s1 >= MATCH_MIN_SIM and s1 - s2 >= MATCH_MIN_MARGIN:
        return BoxResult(box, "livery", e1, "", s1, unmatched)
    if s1 >= MATCH_MIN_SIM and e2 and entries[e1].team and entries[e1].team == entries[e2].team:
        return BoxResult(box, "team", e1, e2, s1, unmatched)
    return BoxResult(box, "none", "", "", max(s1, 0.0), unmatched)


def pool_sims(sims_list: list) -> list:
    """Average each entry's similarity across a burst's frames (sims_list: one
    [(entry_id, similarity)] per frame), most similar first."""
    totals, counts = {}, {}
    for sims in sims_list:
        for eid, s in sims:
            totals[eid] = totals.get(eid, 0.0) + s
            counts[eid] = counts.get(eid, 0) + 1
    pooled = [(eid, totals[eid] / counts[eid]) for eid in totals]
    pooled.sort(key=lambda t: t[1], reverse=True)
    return pooled


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
    unmatched = ";".join(dict.fromkeys(digits for digits, _ in ocr))
    return match_livery(box, sims, entries, unmatched)


def shot_type(n_boxes: int, max_boxes: int) -> str:
    """solo / pack / crowded from the box count; "" when the frame has no vehicle.
    crowded = the detector's cap was reached, so more cars may be in frame than were boxed."""
    if n_boxes <= 0:
        return ""
    if n_boxes == 1:
        return "solo"
    return "crowded" if n_boxes >= max_boxes else "pack"


def decided_by(r: BoxResult, sims: list, entries: dict) -> tuple:
    """(rule, gap): the rule that produced r. For method `none`, the rule that failed and
    how far short it fell (similarity below MATCH_MIN_SIM, or margin below MATCH_MIN_MARGIN)."""
    if r.method != "none":
        return r.method, 0.0
    if r.box == -1:
        return "no_vehicle", 0.0
    sims = [(eid, s) for eid, s in sims if eid in entries]
    if not sims:
        return "no_references", 0.0
    s1 = sims[0][1]
    s2 = sims[1][1] if len(sims) > 1 else 0.0
    if s1 < MATCH_MIN_SIM:
        return "below_min_sim", MATCH_MIN_SIM - s1
    return "margin_too_small", MATCH_MIN_MARGIN - (s1 - s2)


def already_tagged(protected: set, entries: dict) -> str:
    """The id of the one entry whose tags are all in `protected`; "" when none or several
    are (a shared team tag alone matches no one). Same rule as the plugin's entry_for_tags."""
    found = ""
    for e in entries.values():
        if e.tags and all(t in protected for t in e.tags):
            if found:
                return ""
            found = e.id
    return found


def conflicts(entry_id: str, protected: set, entries: dict, solo: bool) -> bool:
    """A solo shot whose result shares no tag with the tags the user applied by hand. Packs
    never conflict: the user may have tagged just one of the cars."""
    if not solo or not protected or entry_id not in entries:
        return False
    return not any(t in protected for t in entries[entry_id].tags)


def promotable(record: dict) -> bool:
    """A boxes.json box record confident enough to become a reference: number-read, or a
    livery match whose lead over the runner-up is at least REFERENCE_MIN_MARGIN. Burst,
    team, pooled and conflict boxes never are."""
    if not record.get("entry"):
        return False
    if record["method"] == "number":
        return True
    if record["method"] != "livery":
        return False
    cands = record.get("candidates") or []
    if not cands:
        return False
    s2 = cands[1][1] if len(cands) > 1 else 0.0
    return cands[0][1] - s2 >= REFERENCE_MIN_MARGIN


def burst_consensus(frames: dict, burst_of: dict, entries=None) -> dict:
    """frames: image id → [BoxResult]. A frame none of whose boxes was identified
    takes its burst's entry on its largest box when at least BURST_MIN_AGREE
    frames agree on that entry and no frame names another. With `entries`, a
    frame whose team-only result names another team is left alone: that's
    evidence of a different car."""
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
            if entries and eid in entries and any(
                    r.method == "team" and r.entry_id in entries and entries[r.entry_id].team != entries[eid].team
                    for r in rows):
                continue
            out[fid] = [replace(r, method="burst", entry_id=eid, alt_entry_id="", confidence=n / len(ids))
                        if r.box == 0 else r for r in rows]
    return out

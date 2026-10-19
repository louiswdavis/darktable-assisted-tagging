"""Identification rules: number first, then livery similarity, then burst
consensus. Pure functions over OCR candidates and similarities."""

from dataclasses import dataclass, replace

MATCH_MIN_SIM = 0.60
MATCH_MIN_MARGIN = 0.10  # on centred similarities (reference_store.best_per_entry); eval_matching.py sweeps it
BURST_MIN_AGREE = 2
REFERENCE_MIN_MARGIN = 0.10  # a livery match must lead by this much to be saved as a reference

IDENTIFIED = ("number", "livery")


@dataclass(frozen=True)
class Entry:
    id: str
    number: str
    team: str
    tags: tuple
    camera: str = ""  # onboard camera pod colour ("yellow" / "black"), a teammate tie-break; "" when unknown


@dataclass(frozen=True)
class BoxResult:
    box: int  # -1: the frame had no vehicle
    # number | livery | team | burst | pooled | none | conflict (disagrees with a hand-applied tag) |
    # skipped (already fully tagged) | error (couldn't analyse; tags left alone)
    method: str
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


def _fragment_of_livery(hit: str, ocr: list, sims: list, entries: dict) -> bool:
    """True when the number read for `hit` is probably part of a longer number (a `1` from a `12`
    or `31`) and the livery does not back `hit`: either it clearly points to another entry whose
    number contains the digits (MATCH_MIN_SIM, leading `hit` by MATCH_MIN_MARGIN), or `hit`'s own
    livery similarity is below MATCH_MIN_SIM. A real other-team car with the right number still wins."""
    if not sims or sims[0][0] == hit:
        return False
    read = {d for d, _ in ocr if hit in {e.id for e in entries.values() if e.number == d}}
    if not any(d != e.number and d in e.number for d in read for e in entries.values() if e.number):
        return False
    sim = dict(sims)
    if sim.get(hit, 0.0) < MATCH_MIN_SIM:
        return True
    top = entries.get(sims[0][0])
    if top is None or not top.number or sims[0][1] < MATCH_MIN_SIM:
        return False
    if sims[0][1] - sim[hit] < MATCH_MIN_MARGIN:
        return False
    return any(d != top.number and d in top.number for d in read)


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
    if len(hits) == 1 and not _fragment_of_livery(next(iter(hits)), ocr, sims, entries):
        return BoxResult(box, "number", hits.pop(), "", best_conf)
    unmatched = ";".join(dict.fromkeys(digits for digits, _ in ocr))
    return match_livery(box, sims, entries, unmatched)


def entries_under(entries: dict, prefixes: list) -> dict:
    """The entries with a tag equal to a prefix or below it (`prefix|…`), in file order."""
    return {eid: e for eid, e in entries.items()
            if any(t == p or t.startswith(p + "|") for t in e.tags for p in prefixes)}


def most_specific(prefixes: list) -> list:
    """`prefixes` without any that is an ancestor of another (`F1` beside `F1|Alpine` keeps only
    `F1|Alpine`), so a broad tag the user applied can't widen a narrower one back to everything."""
    return [p for p in dict.fromkeys(prefixes) if not any(q.startswith(p + "|") for q in prefixes)]


def hinted_match(box: int, ocr: list, sims: list, entries: dict, prefixes: list, source: str) -> tuple:
    """(BoxResult, hint) matching only the entries under `prefixes`. The restriction is a soft
    prior: it is dropped (the full set is matched) when it holds no entries, every restricted
    similarity is under MATCH_MIN_SIM, or OCR read a number that belongs to an entry outside it.
    The exception is a weak livery under a user-applied tag (`source` "tag") whose entries all share
    one team: that gives a `team` result instead, since the user already said which team.
    `hint` is {} without prefixes, else {prefixes, source, restricted, dropped, reason}."""
    if not prefixes:
        return match_box(box, ocr, sims, entries), {}
    prefixes = most_specific(prefixes)
    inside = entries_under(entries, prefixes)
    hint = {"prefixes": list(prefixes), "source": source, "restricted": len(inside), "dropped": False, "reason": ""}
    reason = ""
    if not inside:
        reason = "no_entries"
    else:
        digits = {d for d, _ in ocr}
        outside = [eid for eid, e in entries.items() if e.number and e.number in digits and eid not in inside]
        if outside and source == "tag":
            # The user tagged this photo to the set; a number outside it only wins when the livery
            # doesn't clearly point back inside (a misread digit or sponsor text, not another car).
            sim = dict(sims)
            lead = max((sim.get(eid, 0.0) for eid in inside), default=0.0) - max(sim.get(eid, 0.0) for eid in outside)
            if lead >= MATCH_MIN_MARGIN:
                ocr = [(d, c) for d, c in ocr if d not in {entries[eid].number for eid in outside}]
                outside = []
        if outside:
            reason = "number_outside"
        elif not any(s >= MATCH_MIN_SIM for eid, s in sims if eid in inside):
            reason = "below_min_sim"
    if reason == "below_min_sim" and source == "tag":
        # The user tagged this photo to the set, so a weak livery is no reason to look outside it.
        # A number inside still identifies; otherwise one team's worth of entries gives a team
        # result, which the camera pod can narrow to a driver.
        restricted = [(eid, s) for eid, s in sims if eid in inside]
        r = match_box(box, ocr, restricted, inside)
        teams = {e.team for e in inside.values()}
        if r.method == "number":
            return r, hint
        if len(teams) == 1 and "" not in teams and len(restricted) >= 2:
            (e1, s1), (e2, _) = restricted[0], restricted[1]
            return replace(r, method="team", entry_id=e1, alt_entry_id=e2, confidence=s1), hint
    if reason:
        hint.update(dropped=True, reason=reason)
        return match_box(box, ocr, sims, entries), hint
    return match_box(box, ocr, [(eid, s) for eid, s in sims if eid in inside], inside), hint


TEAM_KEY = "@team@"  # reference folder / index key prefix of a team-level reference


def team_key(prefix: str) -> str:
    """The refs/ folder name of a team prefix (`|` can't sit in a path on every platform)."""
    return TEAM_KEY + prefix.replace("|", "__")


def match_team(result: BoxResult, team_sims: list, entries: dict) -> BoxResult:
    """A `none` result upgraded to `team` when one team's references clearly lead: team_sims is
    [(team prefix, similarity)] most similar first. The first two entries under the team become
    entry/alt so the plugin writes only their shared tags. Any other result is returned as is."""
    if result.method != "none" or not team_sims:
        return result
    (prefix, s1), s2 = team_sims[0], team_sims[1][1] if len(team_sims) > 1 else 0.0
    members = list(entries_under(entries, [prefix]))
    if s1 < MATCH_MIN_SIM or s1 - s2 < MATCH_MIN_MARGIN or len(members) < 2:
        return result
    return replace(result, method="team", entry_id=members[0], alt_entry_id=members[1], confidence=s1)


def match_camera(result: BoxResult, colour: str, entries: dict) -> BoxResult:
    """The camera pod colour read off the car as a teammate tie-break. A `team` result is narrowed
    to the one driver of that team with this pod colour when he is one of the two candidates. A
    `livery` result whose driver has the other colour moves to his teammate with this one: teammates
    share a livery, so the pod outweighs a close livery call. Anything else, or any case without
    exactly one owner of the colour in the team, returns the result as is."""
    if result.method not in ("team", "livery") or not colour or result.entry_id not in entries:
        return result
    team = entries[result.entry_id].team
    owners = [e.id for e in entries.values() if team and e.team == team and e.camera == colour]
    if len(owners) != 1:
        return result
    if result.method == "team":
        if owners[0] not in (result.entry_id, result.alt_entry_id):
            return result
        return replace(result, method="livery", entry_id=owners[0], alt_entry_id="")
    if not entries[result.entry_id].camera or entries[result.entry_id].camera == colour:
        return result
    return replace(result, entry_id=owners[0])


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


def disagrees(result: BoxResult, tagged: str, solo: bool) -> bool:
    """--verify: a solo shot whose result names a different entry than the one its tags already
    spell out (`tagged`). A team result agrees when it still lists that entry."""
    if not solo or not result.entry_id:
        return False
    return tagged not in (result.entry_id, result.alt_entry_id)


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


def _burst_fill(frames: dict, fid: str, eid: str, confidence: float, entries) -> list:
    """The frame's rows with box 0 set to the burst's entry, or the rows unchanged when the frame is
    already identified, has no box 0, or shows a team-only result for another team (a different car)."""
    rows = frames[fid]
    if any(r.method in IDENTIFIED for r in rows) or not any(r.box == 0 for r in rows):
        return rows
    if entries and eid in entries and any(
            r.method == "team" and r.entry_id in entries and entries[r.entry_id].team != entries[eid].team
            for r in rows):
        return rows
    return [replace(r, method="burst", entry_id=eid, alt_entry_id="", confidence=confidence) if r.box == 0 else r
            for r in rows]


def _split_burst(ids: list, frames: dict) -> list:
    """Fill spans for a burst that names several entries: [(entry id, [frame ids to fill from])]. `ids` is
    in shooting order. An anchor is a frame whose box 0 was identified; a run of anchors with one entry
    (at least BURST_MIN_AGREE) fills the frames between its first and last anchor, plus the unidentified
    frames reaching the burst's edge on its side. Frames between two runs of different entries could
    belong to either car and stay unfilled."""
    anchors = []
    for pos, fid in enumerate(ids):
        ident = [r.entry_id for r in frames[fid] if r.box == 0 and r.method in IDENTIFIED]
        if ident:
            anchors.append((pos, ident[0]))
    runs: list = []
    for pos, eid in anchors:
        if runs and runs[-1][0] == eid:
            runs[-1][1].append(pos)
        else:
            runs.append((eid, [pos]))
    spans = []
    for n, (eid, positions) in enumerate(runs):
        if len(positions) < BURST_MIN_AGREE:
            continue
        lo = 0 if n == 0 else positions[0]
        hi = len(ids) - 1 if n == len(runs) - 1 else positions[-1]
        spans.append((eid, ids[lo:hi + 1], len(positions)))
    return spans


def _smooth_spikes(ids: list, frames: dict) -> dict:
    """`frames` with each isolated `livery` anchor set to the entry its neighbouring anchors agree on:
    a livery call is weaker than a number, and one flanked on both sides by the same other car is
    a misread of that car, not a car passing for one frame."""
    anchors = [(fid, [r for r in frames[fid] if r.box == 0 and r.method in IDENTIFIED]) for fid in ids]
    anchors = [(fid, rs[0]) for fid, rs in anchors if rs]
    out = dict(frames)
    for n in range(1, len(anchors) - 1):
        fid, r = anchors[n]
        before, after = anchors[n - 1][1].entry_id, anchors[n + 1][1].entry_id
        if r.method == "livery" and before == after != r.entry_id:
            out[fid] = [replace(x, method="burst", entry_id=before, alt_entry_id="") if x.box == 0 else x
                        for x in frames[fid]]
    return out


def burst_consensus(frames: dict, burst_of: dict, entries=None, order: dict = None) -> dict:
    """frames: image id → [BoxResult]. A frame none of whose boxes was identified
    takes its burst's entry on its largest box when at least BURST_MIN_AGREE
    frames agree on that entry and no frame names another. With `entries`, a
    frame whose team-only result names another team is left alone: that's
    evidence of a different car. A burst that names several entries is split at the identity
    changes (see _split_burst) using `order` (image id → sort key, shooting order; default the
    order of `frames`), so each stretch fills only from its own car."""
    members: dict = {}
    for fid in frames:
        members.setdefault(burst_of.get(fid, fid), []).append(fid)
    out = dict(frames)
    for ids in members.values():
        agree: dict = {}
        for fid in ids:
            for eid in {r.entry_id for r in frames[fid] if r.method in IDENTIFIED}:
                agree[eid] = agree.get(eid, 0) + 1
        if len(agree) > 1:
            ordered = sorted(ids, key=order.__getitem__) if order else ids
            smoothed = _smooth_spikes(ordered, frames)
            out.update({fid: smoothed[fid] for fid in ids})
            for eid, span, n in _split_burst(ordered, smoothed):
                for fid in span:
                    out[fid] = _burst_fill(smoothed, fid, eid, n / len(span), entries)
            continue
        if len(agree) != 1:
            continue
        (eid, n), = agree.items()
        if n < BURST_MIN_AGREE:
            continue
        for fid in ids:
            out[fid] = _burst_fill(frames, fid, eid, n / len(ids), entries)
    return out

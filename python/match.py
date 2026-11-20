"""Identification rules: number first, then livery similarity, then burst
consensus. Pure functions over OCR candidates and similarities."""

import math
from dataclasses import dataclass, replace

from car_colour import colour_relation, decide_colour, overturned_colour

MATCH_MIN_SIM = 0.60
MATCH_MIN_MARGIN = 0.10  # on centred similarities (reference_store.best_per_entry); eval_matching.py sweeps it
BURST_MIN_AGREE = 2
BURST_MIN_CONFIDENCE = 0.5  # a burst fill below this share of its span is not written
# a number read at least this sure identifies a burst naming no other entry on its own: it fills the
# burst with one anchor and whatever share of the burst agrees
SOLO_ANCHOR_CONF = 0.95
BURST_MAX_RANK = 2  # the burst's entry must be in the box's own top N by similarity...
BURST_SIM_SLACK = 0.05  # ...or within this of its top-1

# a number read under rules.min_read but at least this sure goes through the start-list scoring
# (usable_reads), and its scores are summed across WEAK_AGREE_MIN or more frames of a group
# (burst_list_read); without digit matrices, that many frames must read the same number
WEAK_READ_MIN = 0.7  # the rally's old-reader misreads of a lone letter as 5 sat at about 0.6
WEAK_AGREE_MIN = 2
NEW_NUMBER_MIN_FRAMES = 3  # frames of one burst reading a number no entry has before it's flagged (new_numbers)

CONFUSABLE_DIGITS = {frozenset(p) for p in ("56", "17", "06", "08", "38", "35", "14")}  # pairs OCR swaps on race numbers
MISREAD_TOP_N = 3  # a misread number only backs an entry in the livery's own top N

# Start-list scoring (list_read), in natural-log likelihood relative to the greedy read's own: the best
# number must lead the runner-up by NUMBER_LIST_MARGIN (10x) and score at least -NUMBER_LIST_FLOOR
# (within 100x of the greedy read). First guesses; the log prints both scores per box to tune them.
NUMBER_LIST_MARGIN = 2.3
NUMBER_LIST_FLOOR = 4.6
CTC_MIN_PROB = 1e-4  # a digit matrix holds 4 decimals; a 0 there is read as this

# a number read at min_read or more beside this many different start-list numbers across the run
# is on many cars (a class number, a year, a sponsor's digits), so it names none (noise_numbers)
NOISE_MIN_PARTNERS = 3
# ...and only when more than this share of the boxes that read it also read a start-list number:
# a class number sits beside the car's own, a real car's number is mostly alone in its box
NOISE_MIN_BESIDE_SHARE = 0.5

IDENTIFIED = ("number", "livery")
HAND = "hand"  # the entry the user's own number or driver tag names (the manifest's 7th field)
BURST_ANCHORS = IDENTIFIED + ("neighbour", HAND)  # results that can anchor a burst fill


@dataclass(frozen=True)
class Entry:
    id: str
    number: str
    team: str
    tags: tuple
    camera: str = ""  # onboard camera pod colour ("yellow" / "black"), a teammate tie-break; "" when unknown
    colour: str = ""  # body colour (a palette name or "Multi"), a doubtful-decision tie-break; "" when unknown
    name: str = ""  # the driver, the value of the driver tag family; "" when unknown
    car: str = ""  # a double-driven car's id (the lower entry's id), set on both entries; "" when unshared
    co_driver: str = ""  # a rally co-driver, the value of the co-driver tag family; "" when none
    shows: tuple = ()  # other numbers the car carries (an old event's number left on the door); () when none


def numbers_of(e: Entry) -> tuple:
    """The numbers a read can name `e` by: its entry number, then any it also shows."""
    return tuple(n for n in (e.number, *e.shows) if n)


def number_index(entries: dict) -> dict:
    """{number: [entry ids]} over every number each entry carries (numbers_of). A number shown by
    one car and entered by another names both, so livery decides between them."""
    by_number: dict = {}
    for e in entries.values():
        for n in numbers_of(e):
            by_number.setdefault(n, []).append(e.id)
    return by_number


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
    # Set by neighbour.neighbour_aid on a doubtful number read that doesn't fit the groups shot
    # either side of it; the result and its tags stay, the photographer checks it.
    order_flag: bool = False
    # How neighbour.neighbour_aid settled a `neighbour` result: "order" (a misread fits the number
    # order), "lookalike" (the crop looks like a nearby identified car) or "candidate" (its best livery
    # guess was identified nearby). Log only; not in results.csv.
    via: str = ""
    # The box's decided body colour (car_colour), carried through every later rewrite; "" when none.
    colour: str = ""
    # A confident number read whose entry's colour disagrees with `colour`; the result stays, the photographer checks it.
    colour_flag: bool = False
    # A livery, burst or neighbour match that doesn't look like its car's anchors (reference_store.Anchors):
    # alt_entry_id names the rejected car and the photographer gets a Check tag. method is "none", or
    # kept with the entry of the car it is closer to (closer_car_match).
    anchor_flag: bool = False
    # ListRead.text() when the box's reads were scored against the start list; "" on the fallback path.
    list_read: str = ""
    # The rules.sponsor_keywords words read on the box as tag values, ";"-joined, when the sponsor
    # family is on; "" otherwise. Carried through every later rewrite like `colour`.
    sponsor: str = ""
    # new_numbers' digits this box read, ";"-joined: a possible new entry. Set after every matching
    # pass and independent of `method`; "" otherwise.
    new_number: str = ""


@dataclass(frozen=True)
class ListRead:
    greedy: str  # the box's greedy reads, "/"-joined
    best: str = ""  # the best-scoring start-list number; "" when none scored
    score: float = -math.inf
    runner: str = ""
    runner_score: float = -math.inf
    winner: str = ""  # `best` when it clears NUMBER_LIST_FLOOR and NUMBER_LIST_MARGIN, else ""
    confidence: float = 0.0  # the read confidence of the region that gave `best`
    burst: int = 0  # frames whose scores were summed (burst_list_read); 0 for one box

    def text(self) -> str:
        """`1>14 -0.40, 44 -6.10`, then ` close call` or ` no list read` when nothing won, then
        ` (burst of 3)` for a burst total."""
        if not self.best:
            return f"{self.greedy}> no list read"
        out = f"{self.greedy}>{self.best} {self.score:.2f}"
        if self.runner:
            out += f", {self.runner} {self.runner_score:.2f}"
        if not self.winner:
            out += " no list read" if self.score < -NUMBER_LIST_FLOOR * max(self.burst, 1) else " close call"
        return out + (f" (burst of {self.burst})" if self.burst else "")


def by_car(sims: list, entries: dict) -> list:
    """sims with only the best of each double-driven car kept, order preserved; ids not in
    entries pass through. Both entries of a car carry the same tags, so either one names it."""
    seen, out = set(), []
    for eid, s in sims:
        car = entries[eid].car if eid in entries else ""
        if car and car in seen:
            continue
        seen.add(car)
        out.append((eid, s))
    return out


def match_livery(box: int, sims: list, entries: dict, unmatched: str = "") -> BoxResult:
    """sims: [(entry_id, similarity)] most similar first. Livery match, else a
    same-team tie-break, else none. Shared with pooled burst matching, so a caller
    can run this once on sims averaged across a burst instead of one frame's own.
    A double-driven car's two entries count as one candidate (by_car)."""
    sims = by_car([(eid, s) for eid, s in sims if eid in entries], entries)
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
    read = {d for d, _ in ocr if hit in {e.id for e in entries.values() if d in numbers_of(e)}}
    if not any(d != n and d in n for d in read for e in entries.values() for n in numbers_of(e)):
        return False
    sim = dict(sims)
    if sim.get(hit, 0.0) < MATCH_MIN_SIM:
        return True
    top = entries.get(sims[0][0])
    if top is None or not numbers_of(top) or sims[0][1] < MATCH_MIN_SIM:
        return False
    if sims[0][1] - sim[hit] < MATCH_MIN_MARGIN:
        return False
    return any(d != n and d in n for d in read for n in numbers_of(top))


def _one_confusion_apart(read: str, number: str) -> bool:
    """True when `read` is `number` with exactly one digit swapped for a look-alike."""
    if len(read) != len(number):
        return False
    diff = [(a, b) for a, b in zip(read, number) if a != b]
    return len(diff) == 1 and frozenset(diff[0]) in CONFUSABLE_DIGITS


def _misread_number(ocr: list, sims: list, entries: dict):
    """(entry_id, similarity) when exactly one of the livery's top MISREAD_TOP_N entries, at or above
    MATCH_MIN_SIM, has a number one look-alike digit away from a number OCR read (a 5 read for a 6);
    else None. Only called when the read matches no entry's number exactly. A double-driven car's
    two entries take one slot (by_car)."""
    near = [(eid, s) for eid, s in by_car(sims, entries)[:MISREAD_TOP_N]
            if s >= MATCH_MIN_SIM and eid in entries and entries[eid].number
            and any(_one_confusion_apart(d, entries[eid].number) for d, _ in ocr)]
    return near[0] if len(near) == 1 else None


def _logadd(a: float, b: float) -> float:
    if a == -math.inf:
        return b
    if b == -math.inf:
        return a
    hi, lo = max(a, b), min(a, b)
    return hi + math.log1p(math.exp(lo - hi))


def ctc_log_likelihood(matrix: list, number: str) -> float:
    """Natural-log probability that a digit matrix (ocr.digit_matrix: rows [blank, 0..9]) spells
    `number`: the CTC forward sum over every step path that collapses to it. Every step counts, so a
    short number scores low on a longer number's steps. -inf when there are too few steps."""
    if not matrix:
        return -math.inf
    lp = [[math.log(max(v, CTC_MIN_PROB)) for v in row] for row in matrix]
    labels = [0]
    for ch in number:
        labels += [1 + int(ch), 0]
    alpha = [-math.inf] * len(labels)
    alpha[0], alpha[1] = lp[0][0], lp[0][labels[1]]
    for row in lp[1:]:
        nxt = []
        for s, lab in enumerate(labels):
            a = alpha[s]
            if s >= 1:
                a = _logadd(a, alpha[s - 1])
            if s >= 2 and lab != 0 and lab != labels[s - 2]:
                a = _logadd(a, alpha[s - 2])
            nxt.append(a + row[lab] if a > -math.inf else -math.inf)
        alpha = nxt
    return _logadd(alpha[-1], alpha[-2])


def usable_reads(ocr: list, ctc, min_read: float) -> list:
    """The reads matching may use: those at min_read or more, plus those at WEAK_READ_MIN or more
    that have a digit matrix, since list_read holds a weak read to the same bar as a sure one."""
    return [(d, c) for d, c in ocr if c >= min_read or (c >= WEAK_READ_MIN and ctc is not None and d in ctc)]


def noise_numbers(boxes: list, entries: dict, min_read: float) -> dict:
    """{digits: partner count} of the run's noise numbers, from every vehicle box's reads (`boxes`:
    one [(digits, confidence)] per box). A read's partners are the other start-list numbers read in
    the same box, both at min_read or more. A number is noise with NOISE_MIN_PARTNERS different
    partners across the run and a partner in more than NOISE_MIN_BESIDE_SHARE of the boxes that read
    it: a real car passed by three others is still alone in most of its boxes. Two cars sharing a
    box give each number one partner, however often they do."""
    listed = set(number_index(entries))
    partners, read_in, beside = {}, {}, {}
    for ocr in boxes:
        sure = {d for d, c in ocr if c >= min_read}
        for d in sure:
            mates = {n for n in sure if n != d and n in listed}
            partners.setdefault(d, set()).update(mates)
            read_in[d] = read_in.get(d, 0) + 1
            beside[d] = beside.get(d, 0) + bool(mates)
    return {d: len(p) for d, p in sorted(partners.items())
            if len(p) >= NOISE_MIN_PARTNERS and beside[d] > NOISE_MIN_BESIDE_SHARE * read_in[d]}


def without_noise(ocr: list, noise: dict) -> list:
    """ocr without the run's noise numbers. Unchanged when nothing else was read: a noise number
    alone in a box can still be the car's own."""
    kept = [(d, c) for d, c in ocr if d not in noise]
    return kept or ocr


def new_numbers(reads: dict, burst_of: dict, entries: dict, noise: dict) -> dict:
    """{digits: {image id: [boxes]}} of 1-3 digit numbers (what Find New Entries lists) no entry has that NEW_NUMBER_MIN_FRAMES or more frames
    of one burst read at WEAK_READ_MIN or more: a car missing from entries.json. `reads` is
    {image id: {box: [(digits, confidence)]}}, the raw reads before list scoring, so a read the list
    gave a look-alike entry still counts. A frame missing from `burst_of` is its own burst; noise
    numbers never count."""
    listed = number_index(entries)
    seen: dict = {}
    for fid, boxes in reads.items():
        for box, ocr in boxes.items():
            for d in {d for d, c in ocr if c >= WEAK_READ_MIN and d.isdigit() and len(d) <= 3
                           and d not in noise and d not in listed}:
                seen.setdefault((burst_of.get(fid, fid), d), {}).setdefault(fid, []).append(box)
    out: dict = {}
    for (_, d), by_frame in seen.items():
        if len(by_frame) >= NEW_NUMBER_MIN_FRAMES:
            out.setdefault(d, {}).update(by_frame)
    return {d: {fid: sorted(boxes) for fid, boxes in sorted(f.items())} for d, f in sorted(out.items())}


def list_scores(ocr: list, ctc, entries: dict):
    """({number: score}, {number: confidence}): each start-list number's ctc_log_likelihood under
    each read's matrix (`ctc`: {digits: digit matrix}) minus the read's own, best over the reads,
    with that read's confidence. None when there are no reads or a read has no matrix (an analysis
    cached before matrices were kept)."""
    if not ocr or ctc is None or any(d not in ctc for d, _ in ocr):
        return None
    numbers = sorted({n for e in entries.values() for n in numbers_of(e) if n.isascii() and n.isdigit()})
    scores, conf_of = {}, {}
    for d, conf in ocr:
        base = ctc_log_likelihood(ctc[d], d)
        if base == -math.inf:
            continue
        for n in numbers:
            s = ctc_log_likelihood(ctc[d], n) - base
            if s > scores.get(n, -math.inf):
                scores[n], conf_of[n] = s, conf
    return {n: s for n, s in scores.items() if s > -math.inf}, conf_of


def list_read(ocr: list, ctc, entries: dict):
    """ocr scored against the start list (list_scores): the best number wins when it clears
    NUMBER_LIST_FLOOR and leads the runner-up by NUMBER_LIST_MARGIN. None as list_scores."""
    scored = list_scores(ocr, ctc, entries)
    if scored is None:
        return None
    scores, conf_of = scored
    greedy = "/".join(d for d, _ in ocr)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if not ranked:
        return ListRead(greedy)
    (best, score), (runner, runner_score) = ranked[0], ranked[1] if len(ranked) > 1 else ("", -math.inf)
    wins = score >= -NUMBER_LIST_FLOOR and score - runner_score >= NUMBER_LIST_MARGIN
    return ListRead(greedy, best, score, runner, runner_score, best if wins else "", conf_of[best])


def match_box(box: int, ocr: list, sims: list, entries: dict, ctc=None, pool: set = None) -> BoxResult:
    """ocr: [(digits, confidence)]; sims: [(entry_id, similarity)] most similar first; ctc: {digits:
    digit matrix} or None. With every read's matrix the reads are scored against the start list
    (list_read): only a clear winner counts as the number read, and look-alike guessing is skipped.
    Without, an exact number hit, then one look-alike digit away (_misread_number). A number
    several entries carry (shows) sends livery to pick between those entries only.
    `pool` (Identify Missing Entries) limits the answer to those entry ids; None is every entry.
    Numbers and look-alikes are still read against all of `entries`, so a car outside the pool that
    is read (or misread) clearly gives `none`, not the nearest pool entry."""
    allowed = entries if pool is None else {eid: e for eid, e in entries.items() if eid in pool}
    by_number = number_index(entries)
    listed = list_read(ocr, ctc, entries)
    if listed is not None:
        unmatched = ";".join(dict.fromkeys(digits for digits, _ in ocr))
        hits = by_number.get(listed.winner, []) if listed.winner else []
        if len(hits) == 1 and not _fragment_of_livery(hits[0], [(listed.winner, listed.confidence)], sims, entries):
            if hits[0] not in allowed:
                return BoxResult(box, "none", "", "", listed.confidence, unmatched, list_read=listed.text())
            return BoxResult(box, "number", hits[0], "", listed.confidence, list_read=listed.text())
        narrowed = {eid: allowed[eid] for eid in hits if eid in allowed} if len(hits) > 1 else allowed
        return replace(match_livery(box, sims, narrowed, unmatched), list_read=listed.text())
    hits, best_conf = set(), 0.0
    for digits, conf in ocr:
        for eid in by_number.get(digits, []):
            hits.add(eid)
            best_conf = max(best_conf, conf)
    unmatched = ";".join(dict.fromkeys(digits for digits, _ in ocr))
    if len(hits) == 1 and not _fragment_of_livery(next(iter(hits)), ocr, sims, entries):
        if next(iter(hits)) not in allowed:
            return BoxResult(box, "none", "", "", best_conf, unmatched)
        return BoxResult(box, "number", hits.pop(), "", best_conf)
    if not hits:
        fuzzy = _misread_number(ocr, sims, entries)
        if fuzzy and fuzzy[0] not in allowed:
            return BoxResult(box, "none", "", "", fuzzy[1], unmatched)
        if fuzzy:
            return BoxResult(box, "livery", fuzzy[0], "", fuzzy[1], unmatched)
    return match_livery(box, sims, {eid: allowed[eid] for eid in hits if eid in allowed} if len(hits) > 1 else allowed, unmatched)


def burst_list_read(ids: list, frames: dict, weak: dict, ctc: dict, entries: dict):
    """(ListRead, {frame: (box, confidence)}) from summing list_scores across the group `ids`'
    unidentified boxes: each frame gives each number its best box's score, a number counts only when
    every scoring frame scored it, and the best total wins when it leads the runner-up's by
    NUMBER_LIST_MARGIN and averages at least -NUMBER_LIST_FLOOR per frame. A number whose entry's
    colour disagrees with a box's can't win, but still ranks. The map gives each frame's box for the
    winner. None when fewer than WEAK_AGREE_MIN frames have a box with every read's matrix."""
    by_number = number_index(entries)
    per_frame, reads_seen, clashes = {}, [], set()
    for fid in ids:
        for r in frames[fid]:
            if r.method != "none" or r.box < 0:
                continue
            reads = weak.get(fid, {}).get(r.box, [])
            scored = list_scores(reads, ctc.get(fid, {}).get(r.box), entries)
            if not scored:
                continue
            scores, conf_of = scored
            best = per_frame.setdefault(fid, {})
            reads_seen += [d for d, _ in reads]
            for n, s in scores.items():
                eids = by_number.get(n, [])
                if len(eids) == 1 and colour_relation(entries[eids[0]].colour, r.colour) == -1:
                    clashes.add(n)
                if s > best.get(n, (-math.inf,))[0]:
                    best[n] = (s, r.box, conf_of[n])
    per_frame = {fid: best for fid, best in per_frame.items() if best}
    if len(per_frame) < WEAK_AGREE_MIN:
        return None
    totals = {n: sum(best[n][0] for best in per_frame.values())
              for n in set.intersection(*(set(best) for best in per_frame.values()))}
    greedy = "/".join(dict.fromkeys(reads_seen))
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    if not ranked:
        return ListRead(greedy, burst=len(per_frame)), {}
    (top, total), (runner, runner_total) = ranked[0], ranked[1] if len(ranked) > 1 else ("", -math.inf)
    wins = (total >= -NUMBER_LIST_FLOOR * len(per_frame) and total - runner_total >= NUMBER_LIST_MARGIN
            and top not in clashes)
    boxes = {fid: best[top][1:] for fid, best in per_frame.items()}
    conf = max(c for _, c in boxes.values())
    return ListRead(greedy, top, total, runner, runner_total, top if wins else "", conf, len(per_frame)), boxes


def agreeing_reads(frames: dict, burst_of: dict, weak: dict, entries: dict, ctc: dict = None, pool: set = None) -> dict:
    """`frames` with weak number reads promoted where a group agrees on them. `weak` is
    {frame_id: {box: [(digits, confidence)]}}, the reads at WEAK_READ_MIN or more; `ctc` is
    {frame_id: {box: {digits: digit matrix}}}. A group whose unidentified boxes carry matrices in
    WEAK_AGREE_MIN or more frames is decided by burst_list_read: its winner becomes `number` on each
    frame's box, `list_read` giving the burst total. Otherwise, an entry whose number (held by no
    other entry) is read on unidentified boxes of WEAK_AGREE_MIN or more frames becomes `number`
    on those boxes, when it is the only entry so agreed. Either way, nothing changes when a number,
    livery or neighbour result in the group names another entry. A read naming an entry whose
    colour disagrees with the box's isn't counted. With `pool`, an agreed entry outside it names nothing."""
    by_number = number_index(entries)
    groups: dict = {}
    for fid in frames:
        groups.setdefault(burst_of.get(fid, fid), []).append(fid)
    out = dict(frames)
    for ids in groups.values():
        fused = burst_list_read(ids, frames, weak, ctc or {}, entries)
        if fused is not None:
            listed, boxes = fused
            eids = by_number.get(listed.winner, []) if listed.winner else []
            if len(eids) != 1 or any(r.method in BURST_ANCHORS and r.entry_id != eids[0] for fid in ids for r in frames[fid]):
                continue
            if pool is not None and eids[0] not in pool:
                continue
            for fid, (box, conf) in boxes.items():
                out[fid] = [replace(r, method="number", entry_id=eids[0], alt_entry_id="", confidence=conf,
                                    unmatched_number="", list_read=listed.text())
                            if r.box == box else r for r in frames[fid]]
            continue
        hits: dict = {}  # entry -> {frame: (box, confidence)}, the surest box per frame
        for fid in ids:
            for r in frames[fid]:
                if r.method != "none" or r.box < 0:
                    continue
                for digits, conf in weak.get(fid, {}).get(r.box, []):
                    eids = by_number.get(digits, [])
                    if len(eids) != 1 or conf < WEAK_READ_MIN or colour_relation(entries[eids[0]].colour, r.colour) == -1:
                        continue
                    seen = hits.setdefault(eids[0], {})
                    if fid not in seen or conf > seen[fid][1]:
                        seen[fid] = (r.box, conf)
        agreed = [eid for eid, by_frame in hits.items() if len(by_frame) >= WEAK_AGREE_MIN]
        if len(agreed) != 1:
            continue
        eid = agreed[0]
        if pool is not None and eid not in pool:
            continue
        if any(r.method in BURST_ANCHORS and r.entry_id != eid for fid in ids for r in frames[fid]):
            continue
        for fid, (box, conf) in hits[eid].items():
            out[fid] = [replace(r, method="number", entry_id=eid, alt_entry_id="", confidence=conf, unmatched_number="")
                        if r.box == box else r for r in frames[fid]]
    return out


def colour_check(frames: dict, entries: dict, tagged_of: dict = None) -> dict:
    """`frames` with `colour_flag` set on `number` results whose entry's colour disagrees with the
    box's colour. The result itself stays; the photographer checks it. With `tagged_of` (--verify:
    image id → the entry its tags name), a solo shot's box is checked against that entry instead,
    whatever its method."""
    def check(fid: str, r: BoxResult, solo: bool) -> BoxResult:
        eid = r.entry_id if tagged_of is None else tagged_of.get(fid, "")
        counted = r.method == "number" if tagged_of is None else solo and r.box >= 0
        e = entries.get(eid)
        if counted and e is not None and colour_relation(e.colour, r.colour) == -1:
            return replace(r, colour_flag=True)
        return r
    return {fid: [check(fid, r, sum(1 for b in rs if b.box >= 0) == 1) for r in rs] for fid, rs in frames.items()}


def colour_overturns(frames: dict, entries: dict, tagged_of: dict = None) -> list:
    """[(entry id, stored colour, colour seen, boxes seen in it, boxes read, image ids seen in it)]
    for each entry whose `number` boxes overturn its colour in entries.json
    (car_colour.overturned_colour), sorted by entry id. With `tagged_of` (--verify: image id → the
    entry its tags name), each tagged solo shot's box counts for that entry instead. Nothing is
    changed: the run reports them for the photographer to check."""
    counts, ids_of = {}, {}
    for fid, rs in frames.items():
        solo = sum(1 for b in rs if b.box >= 0) == 1
        for r in rs:
            eid = r.entry_id if tagged_of is None else tagged_of.get(fid, "")
            counted = r.method == "number" if tagged_of is None else solo and r.box >= 0
            if counted and r.colour and eid in entries:
                seen = counts.setdefault(eid, {})
                seen[r.colour] = seen.get(r.colour, 0) + 1
                ids_of.setdefault((eid, r.colour), []).append(fid)
    out = []
    for eid, seen in sorted(counts.items()):
        colour = overturned_colour(entries[eid].colour, seen)
        if colour:
            out.append((eid, entries[eid].colour, colour, seen[colour], sum(seen.values()), ids_of[eid, colour]))
    return out


def burst_colours(frames: dict, burst_of: dict, shares_of: dict) -> tuple:
    """(frames, changes): every box of one burst identified as the same entry takes one colour,
    decided from the mean of those boxes' colour shares (`shares_of`: (image id, box) → shares).
    One frame's glare or shadow then no longer gives the car a second colour tag. A group of one
    box, a group whose boxes hold differently keyed shares (two colour readers), or one whose mean
    decides no colour keeps each box's own. `changes` lists (image id, box, old, new, boxes)."""
    groups: dict = {}
    for fid, rs in frames.items():
        for r in rs:
            if r.box >= 0 and r.entry_id and r.method in BURST_ANCHORS + ("burst",) and shares_of.get((fid, r.box)):
                groups.setdefault((burst_of.get(fid, fid), r.entry_id), []).append((fid, r.box))
    colour_of: dict = {}
    for keys in groups.values():
        all_shares = [shares_of[k] for k in keys]
        if len(keys) < 2 or any(s.keys() != all_shares[0].keys() for s in all_shares):
            continue
        mean = {n: sum(s[n] for s in all_shares) / len(all_shares) for n in all_shares[0]}
        colour = decide_colour(mean)
        if colour:
            colour_of.update({k: (colour, len(keys)) for k in keys})
    out, changes = {}, []
    for fid, rs in frames.items():
        row = []
        for r in rs:
            colour, n = colour_of.get((fid, r.box), (r.colour, 0))
            if colour != r.colour:
                changes.append((fid, r.box, r.colour, colour, n))
                r = replace(r, colour=colour)
            row.append(r)
        out[fid] = row
    return out, changes


def main_car_only(frames: dict) -> tuple:
    """(frames, ignored): each photo is of one car, its largest box (box 0: vehicles.select_boxes
    sorts largest first). A smaller box keeps its result only when it read the number of another
    car, a real two-car shot; any other smaller box becomes `none` with no colour, sponsor or seen
    number, so background traffic adds no tags. Box -1 rows (no vehicle, hand) are kept.
    `ignored` lists (image id, box, method, entry) for each smaller box that had a result or colour."""
    out, ignored = {}, []
    for fid, rs in frames.items():
        named = {r.entry_id for r in rs if r.box == 0 and r.entry_id}
        row = []
        for r in rs:
            if r.box > 0:
                if r.method == "number" and r.entry_id not in named:
                    named.add(r.entry_id)
                else:
                    if r.entry_id or r.colour or r.sponsor or r.unmatched_number:
                        ignored.append((fid, r.box, r.method, r.entry_id))
                    r = BoxResult(r.box, "none")
            row.append(r)
        out[fid] = row
    return out, ignored


def sure_cars(frames: dict, burst_of: dict, entries: dict, min_read: float) -> dict:
    """{burst: the cars a number read of `min_read` or more, or the user's own tag, names in it}.
    A burst fill for one of these cars is backed by that read, so it skips the anchors check: on
    Rallye 68 of 69 such fills the check dropped were right (a rear view or a blurred pan doesn't
    look like the anchors)."""
    out: dict = {}
    for fid, rs in frames.items():
        for r in rs:
            if r.entry_id in entries and (r.method == HAND or r.method == "number" and r.confidence >= min_read):
                out.setdefault(burst_of.get(fid, fid), set()).add(entries[r.entry_id].car or r.entry_id)
    return out


def closer_car_match(r: BoxResult, own: float, other_car: str, other, entries: dict, margin: float,
                     min_sim: float, taken=(), sure=()) -> BoxResult:
    """`r`, a match unlike its car's anchors (reference_store.Anchors.unlike gives own, other_car and
    other), moved to the car whose anchors it is closer to, or dropped to `none`. It moves only when
    it is a livery match (on Rallye 0 of 69 burst fills checked against their burst's number reads
    were the closer car), `margin` is above 0 (0: never move), `other` leads `own` by `margin` or more and reaches `min_sim`,
    one entry drives that car (a double-driven car can't say which driver), no other box of the
    photo (`taken`: their entry ids) is that entry, and the burst's sure cars (`sure`: sure_cars'
    set for this burst), when it has any, include that car: on Rallye two red 112s moved to the
    blue 35 of the same model inside a burst whose number reads said 112. Either way anchor_flag is
    set and alt_entry_id names the rejected car."""
    drivers = [e.id for e in entries.values() if (e.car or e.id) == other_car] if other_car else []
    moves = r.method == "livery" and margin > 0 and len(drivers) == 1 and drivers[0] not in taken \
        and (not sure or other_car in sure) and other >= min_sim and other - own >= margin - 1e-9
    if not moves:
        return replace(r, method="none", entry_id="", alt_entry_id=r.entry_id, confidence=0.0, anchor_flag=True)
    return replace(r, entry_id=drivers[0], alt_entry_id=r.entry_id, confidence=other, anchor_flag=True)


def colour_pool(entries: dict, colour: str, reads: list, sims: list, min_read: float) -> tuple:
    """(pool, note): the entries whose colour can be the box's `colour` (colour_relation not -1),
    a soft prior like hinted_match's. `note` is {} when nothing was removed, else {colour, kept,
    removed, dropped, reason}. Dropped (the full `entries` returned) when a read at `min_read` or
    more names a removed entry (number wins), no entry is left, or no kept similarity reaches
    MATCH_MIN_SIM (colour alone can't identify a car)."""
    pool = {eid: e for eid, e in entries.items() if colour_relation(e.colour, colour) != -1}
    if not colour or len(pool) == len(entries):
        return entries, {}
    note = {"colour": colour, "kept": len(pool), "removed": len(entries) - len(pool), "dropped": False, "reason": ""}
    digits = {d for d, c in reads if c >= min_read}
    if any(set(numbers_of(e)) & digits for eid, e in entries.items() if eid not in pool):
        note["reason"] = "number_outside"
    elif not pool:
        note["reason"] = "no_entries"
    elif not any(s >= MATCH_MIN_SIM for eid, s in sims if eid in pool):
        note["reason"] = "below_min_sim"
    if note["reason"]:
        note["dropped"] = True
        return entries, note
    return pool, note


def entries_under(entries: dict, prefixes: list) -> dict:
    """The entries with a tag equal to a prefix or below it (`prefix|…`), in file order."""
    return {eid: e for eid, e in entries.items()
            if any(t == p or t.startswith(p + "|") for t in e.tags for p in prefixes)}


def most_specific(prefixes: list) -> list:
    """`prefixes` without any that is an ancestor of another (`F1` beside `F1|Alpine` keeps only
    `F1|Alpine`), so a broad tag the user applied can't widen a narrower one back to everything."""
    return [p for p in dict.fromkeys(prefixes) if not any(q.startswith(p + "|") for q in prefixes)]


def hinted_match(box: int, ocr: list, sims: list, entries: dict, prefixes: list, source: str, ctc=None,
                 min_read: float = 0.0, pool: set = None) -> tuple:
    """(BoxResult, hint) matching only the entries under `prefixes`. The restriction is a soft
    prior: it is dropped (the full set is matched) when it holds no entries, every restricted
    similarity is under MATCH_MIN_SIM, or OCR read a number at `min_read` or more that belongs to an
    entry outside it (a weak read can't drop it).
    The exception is a weak livery under a user-applied tag (`source` "tag") whose entries all share
    one team: that gives a `team` result instead, since the user already said which team.
    `hint` is {} without prefixes, else {prefixes, source, restricted, dropped, reason}. `ctc` and
    `pool` go to match_box; a team result names only pool entries."""
    if not prefixes:
        return match_box(box, ocr, sims, entries, ctc, pool), {}
    prefixes = most_specific(prefixes)
    inside = entries_under(entries, prefixes)
    hint = {"prefixes": list(prefixes), "source": source, "restricted": len(inside), "dropped": False, "reason": ""}
    reason = ""
    if not inside:
        reason = "no_entries"
    else:
        digits = {d for d, c in ocr if c >= min_read}
        outside = [eid for eid, e in entries.items() if set(numbers_of(e)) & digits and eid not in inside]
        if outside and source == "tag":
            # The user tagged this photo to the set; a number outside it only wins when the livery
            # doesn't clearly point back inside (a misread digit or sponsor text, not another car).
            sim = dict(sims)
            lead = max((sim.get(eid, 0.0) for eid in inside), default=0.0) - max(sim.get(eid, 0.0) for eid in outside)
            if lead >= MATCH_MIN_MARGIN:
                ocr = [(d, c) for d, c in ocr if d not in {n for eid in outside for n in numbers_of(entries[eid])}]
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
        r = match_box(box, ocr, restricted, inside, ctc, pool)
        restricted = [(eid, s) for eid, s in restricted if pool is None or eid in pool]
        teams = {e.team for e in inside.values()}
        if r.method == "number":
            return r, hint
        if len(teams) == 1 and "" not in teams and len(restricted) >= 2:
            (e1, s1), (e2, _) = restricted[0], restricted[1]
            return replace(r, method="team", entry_id=e1, alt_entry_id=e2, confidence=s1), hint
    if reason:
        hint.update(dropped=True, reason=reason)
        return match_box(box, ocr, sims, entries, ctc, pool), hint
    return match_box(box, ocr, [(eid, s) for eid, s in sims if eid in inside], inside, ctc, pool), hint


TEAM_KEY = "@team@"  # reference folder / index key prefix of a team-level reference


def team_key(prefix: str) -> str:
    """The refs/ folder name of a team tag (`|` can't sit in a path on every platform)."""
    return TEAM_KEY + prefix.replace("|", "__")


def match_team(result: BoxResult, team_sims: list, entries: dict, pool: set = None) -> BoxResult:
    """A `none` result upgraded to `team` when one team's references clearly lead: team_sims is
    [(team tag, similarity)] most similar first. The first two entries under the team become
    entry/alt so the plugin writes only their shared tags. Any other result is returned as is.
    `pool` (Identify Missing Entries) counts only those entry ids as team members."""
    if result.method != "none" or not team_sims:
        return result
    (prefix, s1), s2 = team_sims[0], team_sims[1][1] if len(team_sims) > 1 else 0.0
    members = [eid for eid in entries_under(entries, [prefix]) if pool is None or eid in pool]
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
    sims = by_car([(eid, s) for eid, s in sims if eid in entries], entries)
    if not sims:
        return "no_references", 0.0
    s1 = sims[0][1]
    s2 = sims[1][1] if len(sims) > 1 else 0.0
    if s1 < MATCH_MIN_SIM:
        return "below_min_sim", MATCH_MIN_SIM - s1
    return "margin_too_small", MATCH_MIN_MARGIN - (s1 - s2)


def already_tagged(protected: set, entries: dict) -> str:
    """The id of the one entry whose tags are all in `protected`; "" when none or several
    are (a shared team tag alone matches no one). Entries with the same tag set (a double-driven
    car's two entries) count as one: the first is returned. Same rule as the plugin's entry_for_tags."""
    found = None
    for e in entries.values():
        if e.tags and all(t in protected for t in e.tags):
            if found is None:
                found = e
            elif set(e.tags) != set(found.tags):
                return ""
    return found.id if found else ""


def conflicts(entry_id: str, protected: set, entries: dict, solo: bool) -> bool:
    """A solo shot whose result shares no tag with the tags the user applied by hand. Packs
    never conflict: the user may have tagged just one of the cars."""
    if not solo or not protected or entry_id not in entries:
        return False
    return not any(t in protected for t in entries[entry_id].tags)


def disagrees(result: BoxResult, tagged: str, solo: bool, entries: dict) -> bool:
    """--verify: a solo shot whose result names a different car than the one its tags already
    spell out (`tagged`). A double-driven car's two entries are one car, so a read of either
    agrees. A team result agrees when it still lists that entry; a match moved to the closer
    car (alt_entry_id = the car it left) does not."""
    if not solo or not result.entry_id:
        return False

    def car(eid):
        return entries[eid].car or eid if eid in entries else eid
    return car(tagged) not in (car(result.entry_id), car(result.alt_entry_id) if result.method == "team" else "")


def promotable(record: dict) -> bool:
    """A boxes.json box record confident enough to become a reference: number-read only. A livery
    match never is, however wide its lead: a wrong one saved as a reference then matches itself
    on the next run, so the error grows."""
    return bool(record.get("entry")) and record["method"] == "number"


def _supported(sims: list, eid: str) -> bool:
    """Whether a box's own similarities back the burst's entry: top BURST_MAX_RANK, or within
    BURST_SIM_SLACK of the top-1. In a pack the largest box is often not the car that anchored the burst."""
    if not sims:
        return False
    top = sims[0][1]
    return any(e == eid and (rank < BURST_MAX_RANK or top - s <= BURST_SIM_SLACK) for rank, (e, s) in enumerate(sims))


def _burst_fill(frames: dict, fid: str, eid: str, confidence: float, entries, box0_sims: dict = None,
                solo: bool = False, why: dict = None, pool: set = None) -> list:
    """The frame's rows with box 0 set to the burst's entry, or the rows unchanged when the frame is
    already identified on box 0 or as a whole (a car on box 1 alone is another car in a pack), already
    identifies the entry on another box (a team-only result naming it is upgraded), has no box 0, shows a team-only result for another team (a different car), the
    confidence is under BURST_MIN_CONFIDENCE (waived when `solo`: a SOLO_ANCHOR_CONF read anchors the
    burst), or (with `box0_sims`) box 0's own similarities don't back the entry. A frame where no
    vehicle was found (a lone box -1 `none` row) takes the entry on that row: nothing in it contradicts the burst.
    With `why`, a frame left unchanged that is not an anchor itself gets why[fid] = (eid, reason).
    With `pool`, an entry outside it fills nothing ("carried"): the anchors stay as evidence."""
    rows = frames[fid]

    def blank(reason):
        if why is not None:
            why[fid] = (eid, reason)
        return rows

    if _anchor_rows(rows) or any(r.entry_id == eid and r.method in BURST_ANCHORS for r in rows):
        return rows
    if pool is not None and eid not in pool:
        return blank("carried")
    if confidence < BURST_MIN_CONFIDENCE and not solo:
        return blank("low share")
    if all(r.box < 0 and r.method == "none" for r in rows):
        return [replace(r, method="burst", entry_id=eid, alt_entry_id="", confidence=confidence) for r in rows]
    if not any(r.box == 0 for r in rows):
        return blank("no box 0")
    if box0_sims is not None and not (fid in box0_sims and (not box0_sims[fid] or _supported(box0_sims[fid], eid))):
        return blank("looks unlike")  # empty sims (a collection without references) leave nothing to contradict the burst
    if entries and eid in entries and any(
            r.method == "team" and r.entry_id in entries and entries[r.entry_id].team != entries[eid].team
            for r in rows):
        return blank("other team")
    return [replace(r, method="burst", entry_id=eid, alt_entry_id="", confidence=confidence) if r.box == 0 else r
            for r in rows]


def _split_burst(ids: list, frames: dict) -> list:
    """Fill spans for a burst that names several entries: [(entry id, [frame ids to fill from], anchor
    count, solo)]. `ids` is in shooting order. An anchor is a frame with an _anchor_rows result; a run of
    anchors with one entry (at least BURST_MIN_AGREE, or one _solo anchor) fills the frames between its
    first and last anchor, plus the unidentified frames reaching the burst's edge on its side. Frames
    between two runs of different entries could belong to either car and stay unfilled."""
    anchors = []
    for pos, fid in enumerate(ids):
        rows = _anchor_rows(frames[fid])
        if rows:
            anchors.append((pos, rows[0]))
    runs: list = []
    for pos, row in anchors:
        if runs and runs[-1][0] == row.entry_id:
            runs[-1][1].append(pos)
            runs[-1][2].append(row)
        else:
            runs.append((row.entry_id, [pos], [row]))
    spans = []
    for n, (eid, positions, rows) in enumerate(runs):
        solo = any(_solo(r) for r in rows)
        if len(positions) < BURST_MIN_AGREE and not solo:
            continue
        lo = 0 if n == 0 else positions[0]
        hi = len(ids) - 1 if n == len(runs) - 1 else positions[-1]
        spans.append((eid, ids[lo:hi + 1], len(positions), solo))
    return spans


def _smooth_spikes(ids: list, frames: dict) -> dict:
    """`frames` with each isolated `livery` anchor set to the entry its neighbouring anchors agree on:
    a livery call is weaker than a number, and one flanked on both sides by the same other car is
    a misread of that car, not a car passing for one frame."""
    anchors = [(fid, _anchor_rows(frames[fid])) for fid in ids]
    anchors = [(fid, rs[0]) for fid, rs in anchors if rs]
    out = dict(frames)
    for n in range(1, len(anchors) - 1):
        fid, r = anchors[n]
        before, after = anchors[n - 1][1].entry_id, anchors[n + 1][1].entry_id
        if r.method == "livery" and before == after != r.entry_id:
            out[fid] = [replace(x, method="burst", entry_id=before, alt_entry_id="") if x.box == 0 else x
                        for x in frames[fid]]
    return out


def burst_consensus(frames: dict, burst_of: dict, entries=None, order: dict = None, box0_sims: dict = None,
                    why: dict = None, pool: set = None) -> dict:
    """frames: image id → [BoxResult]. A frame whose box 0 wasn't identified (and no hand tag)
    takes its burst's entry on its largest box when at least BURST_MIN_AGREE
    frames agree on that entry (a number, livery, neighbour or hand result), or one number read reaches
    SOLO_ANCHOR_CONF or one frame is hand-tagged, and no frame names another. With `entries`, a
    frame whose team-only result names another team is left alone: that's
    evidence of a different car. A burst that names several entries is split at the identity
    changes (see _split_burst) using `order` (image id → sort key, shooting order; default the
    order of `frames`), so each stretch fills only from its own car. With `box0_sims` (image id → box 0's
    [(entry id, sim)]) a frame is filled only when its own box backs the entry; see _supported.
    With `why` (filled in place), each frame of an anchored burst left blank maps to (burst entry, reason):
    "one read", "between cars" (entry ""), or a _burst_fill reason. `pool` goes to _burst_fill."""
    members: dict = {}
    for fid in frames:
        members.setdefault(burst_of.get(fid, fid), []).append(fid)
    out = dict(frames)
    for ids in members.values():
        agree: dict = {}
        for fid in ids:
            for eid in {r.entry_id for r in _anchor_rows(frames[fid])}:
                agree[eid] = agree.get(eid, 0) + 1
        if len(agree) > 1:
            ordered = sorted(ids, key=order.__getitem__) if order else ids
            smoothed = _smooth_spikes(ordered, frames)
            out.update({fid: smoothed[fid] for fid in ids})
            spanned = set()
            for eid, span, n, solo in _split_burst(ordered, smoothed):
                spanned.update(span)
                for fid in span:
                    out[fid] = _burst_fill(smoothed, fid, eid, n / len(span), entries, box0_sims, solo, why, pool)
            if why is not None:
                for fid in ids:
                    if fid not in spanned and not _anchor_rows(smoothed[fid]):
                        why[fid] = ("", "between cars")
            continue
        if len(agree) != 1:
            continue
        (eid, n), = agree.items()
        solo = any(r.entry_id == eid and _solo(r) for fid in ids for r in _anchor_rows(frames[fid]))
        if n < BURST_MIN_AGREE and not solo:
            if why is not None:
                why.update({fid: (eid, "one read") for fid in ids if not _anchor_rows(frames[fid])})
            continue
        for fid in ids:
            out[fid] = _burst_fill(frames, fid, eid, n / len(ids), entries, box0_sims, solo, why, pool)
    return out


def _anchor_rows(rows: list) -> list:
    """The results in `rows` that can anchor a burst fill: identified on box 0, the frame's main car,
    or on the frame as a whole (box -1, a hand tag). A car seen only on box 1 is another car in a pack
    and never names the burst."""
    return [r for r in rows if r.box <= 0 and r.method in BURST_ANCHORS]


def _solo(row) -> bool:
    """Whether one anchor is enough to fill its burst: a hand tag or a number read at SOLO_ANCHOR_CONF."""
    return row.method == HAND or row.method == "number" and row.confidence >= SOLO_ANCHOR_CONF

"""Per-face identification for `people` collections. Pure Python: sims in, decisions out."""

from dataclasses import replace

from match import BoxResult

TOP_K = 3


def entry_scores(sims: list, k: int = TOP_K) -> list:
    """sims: [(entry_id, similarity)] over every reference. [(entry_id, mean of its top-k sims)],
    most similar first; an entry with fewer than k references averages all of them."""
    by_entry: dict = {}
    for eid, s in sims:
        by_entry.setdefault(eid, []).append(s)
    scores = [(eid, sum(top) / len(top)) for eid, v in by_entry.items() for top in [sorted(v, reverse=True)[:k]]]
    return sorted(scores, key=lambda x: -x[1])


def match_face(box: int, width_px: float, scores: list, min_sim: float, margin: float, min_face_px: int) -> tuple:
    """(BoxResult, status) for one face; scores from `entry_scores`. status is tagged (method "face"),
    unknown (nothing close enough), ambiguous (runner-up too close; alt_entry_id names it) or
    too_small (narrower than min_face_px); every status but tagged is method "none"."""
    if width_px < min_face_px:
        return BoxResult(box, "none"), "too_small"
    if not scores:
        return BoxResult(box, "none"), "unknown"
    (e1, s1), (e2, s2) = scores[0], scores[1] if len(scores) > 1 else ("", None)
    if s1 < min_sim:
        return BoxResult(box, "none", confidence=s1), "unknown"
    if s2 is not None and round(s1 - s2, 6) < margin:
        return BoxResult(box, "none", "", e2, s1), "ambiguous"
    return BoxResult(box, "face", e1, "", s1), "tagged"


def resolve_duplicates(pairs: list) -> list:
    """pairs: [(BoxResult, status)] for one frame. A person appears once, so when several tagged faces
    claim an entry the most similar keeps it (the first on a tie) and the rest become unknown."""
    best: dict = {}
    for i, (r, status) in enumerate(pairs):
        if status == "tagged" and (r.entry_id not in best or r.confidence > pairs[best[r.entry_id]][0].confidence):
            best[r.entry_id] = i
    return [(replace(r, method="none", entry_id="", alt_entry_id=""), "unknown")
            if status == "tagged" and best[r.entry_id] != i else (r, status)
            for i, (r, status) in enumerate(pairs)]

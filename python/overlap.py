"""Boxes that overlap in a pack: which part of each car is actually visible. Pure geometry, no packages."""

OVERLAP_MIN = 0.15  # share of a box covered by another before its crop is trimmed to the visible part
CONTAINED_MIN = 0.80  # share of a box inside another: it is a part of that car, not a car of its own
VISIBLE_MIN = 0.50  # share of its width that must stay visible, else the box is hidden
LEVEL_TOL = 0.10  # a box whose bottom edge is this close (as a share of height) to another's isn't known to be behind it

VISIBLE, TRIMMED, HIDDEN = "", "trimmed", "hidden"


def _inter(a, b) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def _area(b) -> float:
    return (b[2] - b[0]) * (b[3] - b[1])


def visible_boxes(boxes: list) -> list:
    """(box to read, state) per box; boxes are (x0, y0, x1, y1, ...). A box mostly inside another is
    HIDDEN (a part of that car). A box covered by one in front of it (lower in the frame, or level with it)
    is cut down to its widest visible span and TRIMMED, or HIDDEN when under VISIBLE_MIN of its width is
    left. A hidden box keeps its own coordinates."""
    out = []
    for i, b in enumerate(boxes):
        x0, y0, x1, y1 = b[:4]
        height = y1 - y0
        cuts, contained = [], False
        for j, o in enumerate(boxes):
            if j == i:
                continue
            inter = _inter(b, o)
            mine, theirs = inter / _area(b), inter / _area(o)
            if mine >= CONTAINED_MIN and mine >= theirs:
                contained = True
            elif mine >= OVERLAP_MIN and theirs < CONTAINED_MIN and o[3] >= y1 - LEVEL_TOL * height:
                cuts.append((max(x0, o[0]), min(x1, o[2])))
        if contained:
            out.append((b, HIDDEN))
            continue
        if not cuts:
            out.append((b, VISIBLE))
            continue
        spans = [(x0, x1)]
        for c0, c1 in cuts:
            spans = [s for lo, hi in spans for s in ((lo, min(hi, c0)), (max(lo, c1), hi)) if s[1] > s[0]]
        best = max(spans, key=lambda s: s[1] - s[0], default=None)
        if best is None or best[1] - best[0] < VISIBLE_MIN * (x1 - x0):
            out.append((b, HIDDEN))
        else:
            out.append(((best[0], y0, best[1], y1, *b[4:]), TRIMMED))
    return out

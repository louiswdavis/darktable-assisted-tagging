"""Burst rescue: a frame where the detector found no vehicle borrows its burst-mates' position.
Frames of one burst show the same car a moment apart, so a weak detector candidate near where a
mate's box sits (similar size, a short shift) is the same car the detector under-scored. Pure
geometry over boxes; the image work lives in identify.py."""

RESCUE_MAX_SHIFT = 1.0  # centre shift, in widths of the mate's box
RESCUE_AREA_RATIO = (0.5, 2.0)  # candidate area / mate area
RESCUE_MIN_SIM = 0.90  # raw embedding cosine between the rescued crop and the mate's crop


def track_candidate(mate_box, candidates: list):
    """Index of the highest-scoring candidate that could be the mate's car a moment later, else None.
    Boxes are (x0, y0, x1, y1, score, ...)."""
    mw, mh = mate_box[2] - mate_box[0], mate_box[3] - mate_box[1]
    if mw <= 0 or mh <= 0:
        return None
    mx, my = (mate_box[0] + mate_box[2]) / 2, (mate_box[1] + mate_box[3]) / 2
    best = None
    for i, c in enumerate(candidates):
        cw, ch = c[2] - c[0], c[3] - c[1]
        if cw <= 0 or ch <= 0:
            continue
        shift = ((((c[0] + c[2]) / 2 - mx) ** 2 + ((c[1] + c[3]) / 2 - my) ** 2) ** 0.5) / mw
        ratio = (cw * ch) / (mw * mh)
        if shift <= RESCUE_MAX_SHIFT and RESCUE_AREA_RATIO[0] <= ratio <= RESCUE_AREA_RATIO[1]:
            if best is None or c[4] > candidates[best][4]:
                best = i
    return best


def plan_burst(burst: list) -> dict:
    """burst: [(key, analysis or None)] in shooting order. {key: (candidate box, mate key)} for each
    frame with no box and a candidate that tracks a mate's largest box. The nearest mate in shooting
    order that yields a candidate is used."""
    plan = {}
    for pos, (key, a) in enumerate(burst):
        if a is None or a["boxes"]:
            continue
        candidates = a.get("candidates", [])
        if not candidates:
            continue
        mates = sorted((m for m in range(len(burst)) if m != pos and burst[m][1] and burst[m][1]["boxes"]),
                       key=lambda m: abs(m - pos))
        for m in mates:
            hit = track_candidate(burst[m][1]["boxes"][0], candidates)
            if hit is not None:
                plan[key] = (candidates[hit], burst[m][0])
                break
    return plan

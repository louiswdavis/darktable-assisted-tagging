"""A car's paintwork colour from its crop: HSV shares over the body region, then a pure decision.
Only the raw shares are cached; `decide_colour` applies the weights at match time, so tuning them
needs no re-read. Bounds are OpenCV HSV (hue 0-179, saturation and value 0-255). The ranges tile the
HSV space, so every counted pixel belongs to exactly one colour."""

import hashlib

_SAT = (41, 255)  # above the achromatic band
_VAL = (51, 255)  # above Black


def _hue(lo: int, hi: int) -> tuple:
    return (lo, hi) + _SAT + _VAL


# (name, ((hue_lo, hue_hi, sat_lo, sat_hi, val_lo, val_hi), ...)); a pixel goes to the first colour
# that matches, so the achromatic rows and Brown come before the hue rows they overlap.
PALETTE = (
    ("Black", ((0, 179, 0, 255, 0, 50),)),
    ("White", ((0, 179, 0, 40, 180, 255),)),
    ("Grey", ((0, 179, 0, 40, 51, 179),)),  # silver reads as Grey
    ("Brown", ((5, 25, 41, 255, 51, 140),)),
    ("Red", (_hue(0, 8), _hue(170, 179))),  # hue wraps at 0
    ("Orange", (_hue(9, 19),)),
    ("Yellow", (_hue(20, 35),)),  # cf. pod.HUE
    ("Green", (_hue(36, 85),)),
    ("Blue", (_hue(86, 130),)),
    ("Purple", (_hue(131, 150),)),
    ("Pink", (_hue(151, 169),)),
)
MULTI = "Multi"
COLOUR_NAMES = tuple(n for n, _ in PALETTE) + (MULTI,)
ACHROMATIC = ("White", "Grey", "Black")
ACHROMATIC_WEIGHT = 0.5  # tarmac, glass and shadow in the body band are achromatic, so these count less
MULTI_RATIO = 0.6  # the runner-up's weighted share, as a part of the winner's, from which a car is Multi
SIGLIP_MIN_SCORE = 0.4  # a SigLIP 2 top score under this is unsure: no colour
SIGLIP_MIN_GAP = 0.1  # nor when the runner-up is within this of the top score

# Share of the crop. Drops the outer margin (sky, track) and the lower tyre/shadow band; the top band
# (window and roofline, mostly dark) is dropped too so it doesn't read as Black.
BODY_X = (0.10, 0.90)
BODY_Y = (0.30, 0.72)
REGION_MAX_DIM = 320  # the region is downscaled to this long side before measuring


def assign(hsv, palette=PALETTE):
    """One boolean mask per palette row, in row order: the pixels of `hsv` that row takes. A pixel
    goes to the first row that matches."""
    import numpy as np
    taken = np.zeros(hsv.shape[:-1], dtype=bool)
    masks = []
    for _, ranges in palette:
        hit = np.zeros(hsv.shape[:-1], dtype=bool)
        for hlo, hhi, slo, shi, vlo, vhi in ranges:
            hit |= ((hsv[..., 0] >= hlo) & (hsv[..., 0] <= hhi) & (hsv[..., 1] >= slo)
                    & (hsv[..., 1] <= shi) & (hsv[..., 2] >= vlo) & (hsv[..., 2] <= vhi))
        hit &= ~taken
        taken |= hit
        masks.append(hit)
    return masks


def colour_shares(crop_rgb, palette=PALETTE, masked: bool = False) -> dict:
    """{name: share of body-region pixels in that colour}, rounded to 3 places, 0.0 included. A pixel
    no row of a custom palette matches counts in the denominator only. When `masked`, pixels equal to
    segment.GREY on all channels are left out of both. cv2 and numpy load here so report.py can use
    `decide_colour` without them."""
    import cv2
    import numpy as np
    from segment import GREY
    h, w = crop_rgb.shape[:2]
    x0, x1 = int(w * BODY_X[0]), max(int(w * BODY_X[1]), int(w * BODY_X[0]) + 1)
    y0, y1 = int(h * BODY_Y[0]), max(int(h * BODY_Y[1]), int(h * BODY_Y[0]) + 1)
    region = np.ascontiguousarray(crop_rgb[y0:y1, x0:x1])
    scale = REGION_MAX_DIM / max(region.shape[:2])
    if scale < 1:  # nearest keeps GREY pixels exact at the mask edge
        region = cv2.resize(region, (max(1, int(region.shape[1] * scale)), max(1, int(region.shape[0] * scale))),
                            interpolation=cv2.INTER_NEAREST)
    counted = np.ones(region.shape[:2], dtype=bool)
    if masked:
        counted = ~(region == GREY).all(axis=2)
    total = int(counted.sum())
    shares = {name: 0.0 for name, _ in palette}
    if total == 0:
        return shares
    masks = assign(cv2.cvtColor(region, cv2.COLOR_RGB2HSV), palette)
    for (name, _), hit in zip(palette, masks):
        shares[name] = round(int((hit & counted).sum()) / total, 3)
    return shares


def decide_colour(shares: dict) -> str:
    """The colour with the highest weighted share, MULTI when the runner-up is at least MULTI_RATIO
    of it, or "" when every share is 0. Names in ACHROMATIC count at ACHROMATIC_WEIGHT. SigLIP 2
    scores (siglip.colour_scores, the only shares with a MULTI key) skip both: the top score wins
    when it is at least SIGLIP_MIN_SCORE and SIGLIP_MIN_GAP clear of the runner-up, else ""."""
    if MULTI in shares:
        top, second = (sorted(shares.values(), reverse=True) + [0.0])[:2]
        if top < SIGLIP_MIN_SCORE or round(top - second, 3) < SIGLIP_MIN_GAP:
            return ""
        return max(shares, key=shares.get)
    ranked = sorted(((s * (ACHROMATIC_WEIGHT if n in ACHROMATIC else 1.0), n) for n, s in shares.items() if s > 0),
                    key=lambda p: -p[0])
    if not ranked:
        return ""
    if len(ranked) > 1 and ranked[1][0] >= MULTI_RATIO * ranked[0][0]:
        return MULTI
    return ranked[0][1]


NEAR_COLOURS = (("White", "Grey"), ("Grey", "Black"))  # shade and silver blur these; neither agrees nor differs


def colour_relation(entry_colour: str, seen: str) -> int:
    """1 when the entry's colour and the seen colour agree, -1 when they differ, 0 when either is empty
    or the two are too close to call: MULTI against a single colour (a multicoloured car often reads as
    its main colour, and the other way round) or a NEAR_COLOURS pair."""
    if not entry_colour or not seen:
        return 0
    if entry_colour == seen:
        return 1
    if MULTI in (entry_colour, seen) or (entry_colour, seen) in NEAR_COLOURS or (seen, entry_colour) in NEAR_COLOURS:
        return 0
    return -1


def palette_digest(palette) -> str:
    """Short sha1 over the palette names and bounds and the body-region constants, for the cache key.
    Names count: cached shares are keyed by name, so a rename must re-read."""
    bounds = [(name, [list(r) for r in ranges]) for name, ranges in palette]
    return hashlib.sha1(repr((bounds, BODY_X, BODY_Y, REGION_MAX_DIM)).encode()).hexdigest()[:8]

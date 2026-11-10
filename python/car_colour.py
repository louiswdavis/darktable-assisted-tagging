"""A car's paintwork colour from its crop: HSV shares over the body region, then a pure decision.
Only the raw shares are cached; `decide_colour` applies the thresholds at match time, so tuning them
needs no re-read. Bounds are OpenCV HSV (hue 0-179, saturation and value 0-255); neighbouring hue
ranges leave gaps, so a pixel in a gap or mid-grey belongs to no colour."""

import hashlib

# (name, ((hue_lo, hue_hi, sat_lo, sat_hi, val_lo, val_hi), ...)); a pixel goes to the first colour that matches.
PALETTE = (
    ("Red", ((0, 8, 90, 255, 50, 255), (165, 179, 90, 255, 50, 255))),  # hue wraps at 0
    ("Blue", ((95, 130, 90, 255, 50, 255),)),
    ("Green", ((40, 85, 90, 255, 50, 255),)),
    ("Yellow", ((20, 35, 90, 255, 50, 255),)),  # cf. pod.HUE
    ("White", ((0, 179, 0, 40, 170, 255),)),
    ("Black", ((0, 179, 0, 255, 0, 60),)),
)
MULTI = "Multi"
COLOUR_SOLE_MIN = 0.60  # one colour at least this share → that colour
COLOUR_PART_MIN = 0.30  # two colours each at least this and together COLOUR_SOLE_MIN → Multi

# Share of the crop. Drops the outer margin (sky, track) and the lower tyre/shadow band; the top band
# (window and roofline, mostly dark) is dropped too so it doesn't read as Black.
BODY_X = (0.10, 0.90)
BODY_Y = (0.30, 0.72)
REGION_MAX_DIM = 320  # the region is downscaled to this long side before measuring


def colour_shares(crop_rgb, palette=PALETTE, masked: bool = False) -> dict:
    """{name: share of body-region pixels in that colour}, rounded to 3 places, 0.0 included. Gap and
    mid-grey pixels count in the denominator only. When `masked`, pixels equal to segment.GREY on all
    channels are left out of both. cv2 and numpy load here so report.py can use `decide_colour` without them."""
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
    hsv = cv2.cvtColor(region, cv2.COLOR_RGB2HSV)
    taken = np.zeros(region.shape[:2], dtype=bool)
    for name, ranges in palette:
        hit = np.zeros(region.shape[:2], dtype=bool)
        for hlo, hhi, slo, shi, vlo, vhi in ranges:
            hit |= ((hsv[..., 0] >= hlo) & (hsv[..., 0] <= hhi) & (hsv[..., 1] >= slo)
                    & (hsv[..., 1] <= shi) & (hsv[..., 2] >= vlo) & (hsv[..., 2] <= vhi))
        hit &= counted & ~taken
        taken |= hit
        shares[name] = round(int(hit.sum()) / total, 3)
    return shares


def decide_colour(shares: dict) -> str:
    """A palette name, MULTI or "" (can't tell), from the raw shares."""
    parts = [(n, s) for n, s in shares.items() if s >= COLOUR_PART_MIN]
    if len(parts) == 1 and parts[0][1] >= COLOUR_SOLE_MIN:
        return parts[0][0]
    if len(parts) == 2 and sum(s for _, s in parts) >= COLOUR_SOLE_MIN:
        return MULTI
    return ""


def colour_relation(entry_colour: str, seen: str) -> int:
    """1 when the entry's colour and the seen colour agree, -1 when they differ, 0 when either is empty.
    MULTI agrees only with MULTI."""
    if not entry_colour or not seen:
        return 0
    return 1 if entry_colour == seen else -1


def palette_digest(palette) -> str:
    """Short sha1 over the palette names and bounds and the body-region constants, for the cache key.
    Names count: cached shares are keyed by name, so a rename must re-read."""
    bounds = [(name, [list(r) for r in ranges]) for name, ranges in palette]
    return hashlib.sha1(repr((bounds, BODY_X, BODY_Y, REGION_MAX_DIM)).encode()).hexdigest()[:8]

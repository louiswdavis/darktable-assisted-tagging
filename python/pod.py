"""The onboard camera pod on top of a car (yellow or black, fixed per driver for the season) as a
teammate tie-break. Measured on the full frame, not the trimmed crop: the pod sits at the very top of
the detector box, where crop_box trims. Only the raw numbers are cached; `pod_colour` applies the
thresholds at match time, so tuning them needs no re-analysis."""

REGION_X = (0.30, 0.70)  # share of the box width, centred
REGION_Y = (0.0, 0.35)  # share of the box height, from the top
REGION_MAX_DIM = 320  # the region is downscaled to this long side before measuring
HUE = (20, 35)  # OpenCV hue is 0-179; this is yellow
MIN_SAT = 120
MIN_VAL = 120
YELLOW_MIN_FRAC = 0.03  # at least this share of the region yellow → a yellow pod
BLACK_MAX_FRAC = 0.002  # at most this much yellow on a side-on car → a black pod
SIDE_ON_ASPECT = 2.0  # box width / height; a head-on or rear view hides the pod


def pod_reading(rgb, box) -> dict:
    """{yellow: share of the top-centre region that is saturated yellow, aspect: box width / height}.
    cv2 and numpy load here so report.py can use `pod_colour` without them."""
    import cv2
    import numpy as np
    x0, y0, x1, y1 = (float(v) for v in box[:4])
    bw, bh = max(x1 - x0, 1.0), max(y1 - y0, 1.0)
    h, w = rgb.shape[:2]
    rx0, rx1 = int(max(x0 + bw * REGION_X[0], 0)), int(min(x0 + bw * REGION_X[1], w))
    ry0, ry1 = int(max(y0 + bh * REGION_Y[0], 0)), int(min(y0 + bh * REGION_Y[1], h))
    region = rgb[ry0:max(ry1, ry0 + 1), rx0:max(rx1, rx0 + 1)]
    scale = REGION_MAX_DIM / max(region.shape[:2])
    if scale < 1:
        region = cv2.resize(region, (max(1, int(region.shape[1] * scale)), max(1, int(region.shape[0] * scale))),
                            interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(np.ascontiguousarray(region), cv2.COLOR_RGB2HSV)
    mask = (hsv[..., 0] >= HUE[0]) & (hsv[..., 0] <= HUE[1]) & (hsv[..., 1] >= MIN_SAT) & (hsv[..., 2] >= MIN_VAL)
    return {"yellow": round(float(mask.mean()), 4), "aspect": round(bw / bh, 2)}


def pod_colour(reading: dict) -> str:
    """"yellow", "black" or "" (can't tell). Black is only claimed on a side-on car with no yellow
    at all: a pod hidden by the angle would read the same."""
    if not reading:
        return ""
    if reading["yellow"] >= YELLOW_MIN_FRAC:
        return "yellow"
    if reading["yellow"] <= BLACK_MAX_FRAC and reading["aspect"] >= SIDE_ON_ASPECT:
        return "black"
    return ""

"""A crop's colour signature: a hue/saturation histogram of its central part, used alongside the
embedding so a car's livery colours count as well as its shape and detail."""

import numpy as np

COLOUR_DIM = 18 * 3
CENTRE_FRACTION = 0.5  # keep the middle half of height and width, dropping track and sky around the car


def colour_hist(crop_rgb: np.ndarray, masked: bool = False) -> np.ndarray:
    """Unit-length float32 vector of COLOUR_DIM values (sqrt of the normalised HSV histogram). When
    `masked`, pixels equal to segment.GREY on all channels (the mask fill) are left out."""
    import cv2
    from segment import GREY
    h, w = crop_rgb.shape[:2]
    dy, dx = int(h * (1 - CENTRE_FRACTION) / 2), int(w * (1 - CENTRE_FRACTION) / 2)
    centre = np.ascontiguousarray(crop_rgb[dy:h - dy, dx:w - dx])
    hsv = cv2.cvtColor(centre, cv2.COLOR_RGB2HSV)
    keep = (~(centre == GREY).all(axis=2)).astype(np.uint8) * 255 if masked else None
    hist = cv2.calcHist([hsv], [0, 1], keep, [18, 3], [0, 180, 0, 256]).ravel()
    v = np.sqrt(hist / max(float(hist.sum()), 1.0)).astype(np.float32)
    return v / max(float(np.linalg.norm(v)), 1e-9)

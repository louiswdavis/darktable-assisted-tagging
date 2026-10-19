"""A crop's colour signature: a hue/saturation histogram of its central part, used alongside the
embedding so a car's livery colours count as well as its shape and detail."""

import numpy as np

COLOUR_DIM = 18 * 3
CENTRE_FRACTION = 0.5  # keep the middle half of height and width, dropping track and sky around the car


def colour_hist(crop_rgb: np.ndarray) -> np.ndarray:
    """Unit-length float32 vector of COLOUR_DIM values (sqrt of the normalised HSV histogram)."""
    import cv2
    h, w = crop_rgb.shape[:2]
    dy, dx = int(h * (1 - CENTRE_FRACTION) / 2), int(w * (1 - CENTRE_FRACTION) / 2)
    hsv = cv2.cvtColor(crop_rgb[dy:h - dy, dx:w - dx], cv2.COLOR_RGB2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [18, 3], [0, 180, 0, 256]).ravel()
    v = np.sqrt(hist / max(float(hist.sum()), 1.0)).astype(np.float32)
    return v / max(float(np.linalg.norm(v)), 1e-9)

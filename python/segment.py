"""Car-shaped masks for boxes that overlap another: EfficientSAM (opencv_zoo, run through cv2.dnn)
prompted with points inside the box. The box's crop is then read with everything outside the car
(background, the neighbouring car) painted grey. Optional: no model file, no masking."""
import os

import cv2
import numpy as np

from overlap import CONTAINED_MIN, HIDDEN, OVERLAP_MIN, _area, _inter
from vehicles import read_onnx

SEGMENTER_FILE = "image_segmentation_efficientsam_ti_2025april.onnx"  # looked up next to the detector
SEGMENT_CACHE_TOKEN = "mask-1"
SEGMENT_INPUT = 1024
MAX_POINTS = 6
REGION_PAD = 0.25  # context added around the box, as a share of its size, so the car's edge is inside the region
MASK_MIN_SHARE = 0.15  # a mask covering less of the box than this found something other than the car
GREY = 128
_INPUTS = ("batched_images", "batched_point_coords", "batched_point_labels")
_OUTPUTS = ["output_masks", "iou_predictions"]


def needs_mask(boxes: list, states: list) -> list:
    """Per box: whether it overlaps another box enough to carry that car's pixels. Hidden boxes are
    never read, so they never need one."""
    out = []
    for i, b in enumerate(boxes):
        hit = False
        for j, o in enumerate(boxes):
            if j == i:
                continue
            inter = _inter(b, o)
            if inter and max(inter / _area(b), inter / _area(o)) >= OVERLAP_MIN:
                hit = True
        out.append(hit and states[i] != HIDDEN)
    return out


class Segmenter:
    def __init__(self, model_path: str):
        self.net = read_onnx(model_path)

    def cut(self, img: np.ndarray, seen, others: list):
        """(region, box in region) with everything outside the car at `seen` painted grey, or None
        when no mask is believable (the caller reads the plain crop). `others` are the other boxes
        that overlap this one; their centres are points the car's mask must not contain."""
        h, w = img.shape[:2]
        x0, y0, x1, y1 = seen[:4]
        bw, bh = x1 - x0, y1 - y0
        rx0, ry0 = max(int(x0 - REGION_PAD * bw), 0), max(int(y0 - REGION_PAD * bh), 0)
        rx1, ry1 = min(int(round(x1 + REGION_PAD * bw)), w), min(int(round(y1 + REGION_PAD * bh)), h)
        region = img[ry0:ry1, rx0:rx1]
        local = (x0 - rx0, y0 - ry0, x1 - rx0, y1 - ry0)
        avoid = [((o[0] + o[2]) / 2 - rx0, (o[1] + o[3]) / 2 - ry0) for o in others
                 if _inter(seen, o) / _area(o) < CONTAINED_MIN]
        mask = self._mask(region, local, avoid)
        if mask is None:
            return None
        out = region.copy()
        out[~mask] = GREY
        return out, local

    def _mask(self, region: np.ndarray, box, avoid: list):
        rh, rw = region.shape[:2]
        x0, y0, x1, y1 = box
        bw, bh = x1 - x0, y1 - y0
        # car body: the middle of the box and a point either side, a little below centre
        points = [((x0 + f * bw) * SEGMENT_INPUT / rw, (y0 + 0.55 * bh) * SEGMENT_INPUT / rh) for f in (0.5, 0.3, 0.7)]
        pad = MAX_POINTS - len(points)
        coords = np.array([[points + [(0.0, 0.0)] * pad]], dtype=np.float32)
        labels = np.array([[[[1.0]] * len(points) + [[-1.0]] * pad]], dtype=np.float32)
        image = cv2.resize(region, (SEGMENT_INPUT, SEGMENT_INPUT)).astype(np.float32) / 255.0
        for name, blob in zip(_INPUTS, (cv2.dnn.blobFromImage(image), coords, labels)):
            self.net.setInput(blob, name)
        masks, ious = self.net.forward(_OUTPUTS)
        masks, ious = masks[0, 0], ious[0, 0]
        lx0, ly0, lx1, ly1 = (max(int(v), 0) for v in (x0, y0, x1, y1))
        for k in np.argsort(ious)[::-1]:
            m = cv2.resize((masks[k] >= 0).astype(np.uint8), (rw, rh), interpolation=cv2.INTER_NEAREST).astype(bool)
            if any(0 <= int(py) < rh and 0 <= int(px) < rw and m[int(py), int(px)] for px, py in avoid):
                continue
            if m[ly0:ly1, lx0:lx1].mean() >= MASK_MIN_SHARE:
                return m
        return None


def segmenter_path(detector_path: str, given: str = "") -> str:
    """The segmentation model to use: `given`, else the one next to the detector when it is there,
    else "" (masking off)."""
    path = given or (os.path.join(os.path.dirname(detector_path), SEGMENTER_FILE) if detector_path else "")
    return path if os.path.isfile(path) else ""

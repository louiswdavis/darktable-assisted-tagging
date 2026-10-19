"""Why a frame's cars are or aren't boxed. Usage: probe_detect.py DETECTOR_ONNX IMAGE [IMAGE ...]

For each image, lists every vehicle the detector scores at 0.05 or more (NMS 0.5, the live setting, then NMS 0.8)
with its size and which live filter keeps or drops it: DETECTOR_MIN_SCORE, MIN_BOX_FRAC, MAX_BOXES."""

import sys

import cv2
import numpy as np

from vehicles import DETECTOR_INPUT, DETECTOR_MIN_SCORE, MAX_BOXES, MIN_BOX_FRAC, decode_vehicles, detector_model, load_full

PROBE_MIN_SCORE = 0.05


def probe(path: str, model: str):
    rgb = load_full(path)
    h, w = rgb.shape[:2]
    scale = min(DETECTOR_INPUT / h, DETECTOR_INPUT / w)
    canvas = np.full((DETECTOR_INPUT, DETECTOR_INPUT, 3), 114.0, np.float32)
    canvas[:int(h * scale), :int(w * scale)] = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    net = detector_model(model)
    net.setInput(np.transpose(canvas, (2, 0, 1))[np.newaxis])
    raw = net.forward(net.getUnconnectedOutLayersNames())[0][0]
    print(f"{path}: {w}x{h}, detector scale {scale:.2f}")
    for nms in (0.5, 0.8):
        boxes = sorted(decode_vehicles(raw, scale, PROBE_MIN_SCORE, nms), key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
        print(f"  NMS {nms}: {len(boxes)} boxes")
        for rank, (x0, y0, x1, y1, score, _) in enumerate(boxes):
            frac = (x1 - x0) * (y1 - y0) / (w * h)
            drops = [name for name, bad in (("score", score < DETECTOR_MIN_SCORE), ("size", frac < MIN_BOX_FRAC),
                                            ("cap", rank >= MAX_BOXES)) if bad]
            print(f"    x {x0:.0f}-{x1:.0f} y {y0:.0f}-{y1:.0f}  {x1 - x0:.0f}x{y1 - y0:.0f}  score {score:.2f}  "
                  f"{frac * 100:.1f}% of frame  {'DROPPED: ' + ','.join(drops) if drops else 'kept'}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    for image in sys.argv[2:]:
        probe(image, sys.argv[1])

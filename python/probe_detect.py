"""Why a frame's cars are or aren't boxed. Usage: probe_detect.py DETECTOR_ONNX IMAGE [IMAGE ...]

For each image, lists every vehicle the detector scores at 0.05 or more (NMS at the live setting)
with its size and which live filter keeps or drops it: DETECTOR_MIN_SCORE, MIN_BOX_FRAC, MAX_BOXES."""

import sys

from vehicles import DETECTOR_MIN_SCORE, MAX_BOXES, MIN_BOX_FRAC
from vehicle_detect import DETECTOR_NMS, boxes_in, decode_rgb, detect, load_detector

PROBE_MIN_SCORE = 0.05


def probe(path: str, detector):
    rgb = decode_rgb(path)
    h, w = rgb.shape[:2]
    entry = detect(rgb, detector)
    boxes = [b for b in boxes_in(entry, w, h) if b[4] >= PROBE_MIN_SCORE]
    boxes.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
    print(f"{path}: {w}x{h}, {detector.id}")
    print(f"  NMS {DETECTOR_NMS}: {len(boxes)} boxes")
    for rank, (x0, y0, x1, y1, score, _) in enumerate(boxes):
        frac = (x1 - x0) * (y1 - y0) / (w * h)
        drops = [name for name, bad in (("score", score < DETECTOR_MIN_SCORE), ("size", frac < MIN_BOX_FRAC),
                                        ("cap", rank >= MAX_BOXES)) if bad]
        print(f"    x {x0:.0f}-{x1:.0f} y {y0:.0f}-{y1:.0f}  {x1 - x0:.0f}x{y1 - y0:.0f}  score {score:.2f}  "
              f"{frac * 100:.1f}% of frame  {'DROPPED: ' + ','.join(drops) if drops else 'kept'}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    loaded = load_detector(sys.argv[1])
    for image in sys.argv[2:]:
        probe(image, loaded)

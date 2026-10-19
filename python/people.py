"""Face detection (YuNet) and embedding (SFace) through OpenCV, for `people` collections.

Smoke check: python people.py DETECTOR.onnx RECOGNIZER.onnx IMAGE"""

import sys
from collections import namedtuple

import cv2
import numpy as np

from vehicles import file_key, load_full

FACE_EMBED_DIM = 128
FACE_CROP = 112  # SFace's aligned input size
FACE_DETECT_LONG_EDGE = 1600  # frames are detected at this size or smaller; small faces need the pixels
FACE_DETECT_MIN_SCORE = 0.6
FACE_NMS = 0.3

# Full-frame pixels; landmarks are five (x, y): eyes, nose, mouth corners.
Face = namedtuple("Face", "x y w h landmarks score")


def face_model_key(det_path: str, rec_path: str) -> list:
    return [file_key(det_path), file_key(rec_path)]


def _row(face: Face) -> np.ndarray:
    """The 15-value row OpenCV's alignCrop takes: box, five landmarks, score."""
    flat = [v for pt in face.landmarks for v in pt]
    return np.array([[face.x, face.y, face.w, face.h, *flat, face.score]], np.float32)


class FaceModel:
    def __init__(self, det_path: str, rec_path: str):
        self.detector = cv2.FaceDetectorYN.create(det_path, "", (320, 320), FACE_DETECT_MIN_SCORE, FACE_NMS, 5000)
        self.recognizer = cv2.FaceRecognizerSF.create(rec_path, "")

    def detect(self, rgb: np.ndarray) -> list:
        """Faces in `rgb`, largest first."""
        h, w = rgb.shape[:2]
        scale = min(1.0, FACE_DETECT_LONG_EDGE / max(h, w))
        small = cv2.resize(rgb, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA) if scale < 1 else rgb
        self.detector.setInputSize((small.shape[1], small.shape[0]))
        _, rows = self.detector.detect(cv2.cvtColor(small, cv2.COLOR_RGB2BGR))
        faces = []
        for r in ([] if rows is None else rows):
            v = [float(x) / scale for x in r[:14]]
            faces.append(Face(v[0], v[1], v[2], v[3], [(v[4 + 2 * i], v[5 + 2 * i]) for i in range(5)], float(r[14])))
        return sorted(faces, key=lambda f: -f.w * f.h)

    def align_crop(self, rgb: np.ndarray, face: Face) -> np.ndarray:
        """The face warped upright from its landmarks, FACE_CROP square, RGB."""
        aligned = self.recognizer.alignCrop(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), _row(face))
        return cv2.cvtColor(aligned, cv2.COLOR_BGR2RGB)

    def embed(self, crop_rgb: np.ndarray) -> np.ndarray:
        """Unit-length feature of an already aligned crop, shape (FACE_EMBED_DIM,)."""
        if crop_rgb.shape[:2] != (FACE_CROP, FACE_CROP):
            crop_rgb = cv2.resize(crop_rgb, (FACE_CROP, FACE_CROP), interpolation=cv2.INTER_AREA)
        vec = self.recognizer.feature(cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2BGR)).reshape(-1).astype(np.float32)
        return vec / max(float(np.linalg.norm(vec)), 1e-9)

    def embed_face(self, rgb: np.ndarray, face: Face) -> np.ndarray:
        return self.embed(self.align_crop(rgb, face))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    model = FaceModel(sys.argv[1], sys.argv[2])
    image = load_full(sys.argv[3])
    found = model.detect(image)
    for n, f in enumerate(found):
        print(f"face {n}: box ({f.x:.0f}, {f.y:.0f}) {f.w:.0f}x{f.h:.0f}, score {f.score:.2f}")
    if len(found) >= 2:
        a, b = (model.embed_face(image, f) for f in found[:2])
        print(f"cosine of the first two faces: {float(a @ b):.3f}")
    print(f"{len(found)} face(s)")

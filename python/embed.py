"""DINOv2 ViT-S/14 image embeddings for livery matching."""

import base64
import os

import numpy as np
import cv2

from vehicles import file_key

EMBED_INPUT = 224
EMBED_DIM = 384
DEGRADE_FACTOR = 4  # how far a reference crop is downscaled-then-upscaled by degrade()
_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)


def embedder_key(model_path: str):
    return file_key(model_path)


def degrade(crop_rgb: np.ndarray) -> np.ndarray:
    """Downscaled by DEGRADE_FACTOR and back, so a close-up reference loses detail
    roughly the way a small, far-away box does once stretched up to EMBED_INPUT."""
    h, w = crop_rgb.shape[:2]
    small = cv2.resize(crop_rgb, (max(1, w // DEGRADE_FACTOR), max(1, h // DEGRADE_FACTOR)),
                        interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)


def encode(vec: np.ndarray) -> str:
    return base64.b64encode(np.asarray(vec, np.float32).tobytes()).decode("ascii")


def decode(s: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(s), np.float32)


def preprocess(crop_rgb: np.ndarray) -> np.ndarray:
    """Letterboxed (not centre-cropped, so a wide car keeps its nose and tail)
    onto mid-grey, resized, ImageNet-normalised, NCHW."""
    h, w = crop_rgb.shape[:2]
    side = max(h, w)
    square = np.full((side, side, 3), 128, np.uint8)
    y, x = (side - h) // 2, (side - w) // 2
    square[y:y + h, x:x + w] = crop_rgb
    img = cv2.resize(square, (EMBED_INPUT, EMBED_INPUT), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    return np.transpose((img - _MEAN) / _STD, (2, 0, 1))[np.newaxis]


class Embedder:
    def __init__(self, model_path: str):
        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"embedder model not found: {model_path}")
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1  # the worker pool supplies the parallelism
        with open(model_path, "rb") as f:  # bytes, so a non-ASCII path can't trip a narrow-path API
            self.session = ort.InferenceSession(f.read(), opts, providers=["CPUExecutionProvider"])

    def embed(self, crop_rgb: np.ndarray) -> np.ndarray:
        """Unit-length CLS feature, shape (EMBED_DIM,)."""
        hidden = self.session.run(["last_hidden_state"], {"pixel_values": preprocess(crop_rgb)})[0]
        vec = hidden[0, 0].astype(np.float32)
        return vec / max(float(np.linalg.norm(vec)), 1e-12)

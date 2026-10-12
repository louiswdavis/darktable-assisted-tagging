"""DINOv2 ViT-S/14 image embeddings for livery matching."""

import base64
import os

import numpy as np
import cv2

from vehicles import file_key

EMBED_INPUT = 224
EMBED_DIM = 384
_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)


def embedder_key(model_path: str):
    return file_key(model_path)


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
        self.session = ort.InferenceSession(model_path, opts, providers=["CPUExecutionProvider"])

    def embed(self, crop_rgb: np.ndarray) -> np.ndarray:
        """Unit-length CLS feature, shape (EMBED_DIM,)."""
        hidden = self.session.run(["last_hidden_state"], {"pixel_values": preprocess(crop_rgb)})[0]
        vec = hidden[0, 0].astype(np.float32)
        return vec / max(float(np.linalg.norm(vec)), 1e-12)

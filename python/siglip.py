"""SigLIP 2 zero-shot answers for a box crop: is it a car (the box check), and what colour is it.

Three files from onnx-community/siglip2-base-patch16-224-ONNX, renamed to sit in models/ together:
onnx/vision_model.onnx → siglip2_base_vision.onnx, onnx/text_model.onnx → siglip2_base_text.onnx,
tokenizer.json → siglip2_base_tokenizer.json. Only the vision file is passed (`--siglip`); the other
two are found beside it by name. One image vector per crop answers both questions."""

import os

from vehicle_detect import file_key

TEXT_LEN = 64  # SigLIP 2 was trained on text padded to 64 tokens
IMAGE_SIZE = 224
SCALE = 100.0  # cosine → logit before the softmax, so colour scores read like shares (sum 1)
SIGLIP_CACHE_TOKEN = "siglip-1"

CAR = "car"
CAR_PROMPTS = {
    CAR: "a photo of a rally car.",
    "race car": "a photo of a racing car on a circuit.",
    "motorbike": "a photo of a motorbike or quad bike.",
    "truck": "a photo of a truck.",
    "person": "a photo of a person.",
    "building": "a photo of a shed or a small building.",
    "railing": "a photo of a metal railing or crash barrier along a road.",
    "crowd": "a photo of spectators.",
    "trees": "a photo of trees and bushes.",
    "road": "a photo of an empty road.",
}
VEHICLES = (CAR, "race car", "motorbike", "truck")  # the detector boxes all of these; the box check keeps them
MULTI_PROMPT = "a photo of a multicoloured rally car."


def siglip_files(vision_path: str) -> tuple:
    """(vision, text, tokenizer) paths: the text model and tokenizer share the vision file's name
    with `vision.onnx` swapped for `text.onnx` and `tokenizer.json`."""
    stem = vision_path[:-len("vision.onnx")] if vision_path.endswith("vision.onnx") else vision_path
    return vision_path, stem + "text.onnx", stem + "tokenizer.json"


def siglip_key(vision_path: str) -> list:
    """Cache key parts: the code token, a digest of this module's constants and all three files."""
    import hashlib
    consts = hashlib.sha1(repr((TEXT_LEN, IMAGE_SIZE, SCALE, CAR_PROMPTS, MULTI_PROMPT, VEHICLES)).encode()).hexdigest()[:8]
    return [SIGLIP_CACHE_TOKEN, consts, *(file_key(p) for p in siglip_files(vision_path))]


def colour_prompts(palette) -> dict:
    """{colour name: prompt} for the palette's names (bounds are not used) plus Multi."""
    from car_colour import MULTI
    prompts = {name: f"a photo of a {name.lower()} rally car." for name, _ in palette}
    prompts[MULTI] = MULTI_PROMPT
    return prompts


class SigLIP:
    def __init__(self, vision_path: str):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        vision, text, tokenizer = siglip_files(vision_path)
        for path in (text, tokenizer):
            if not os.path.isfile(path):
                raise FileNotFoundError(f"{os.path.basename(path)} must sit beside {os.path.basename(vision)}")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1  # the worker pool supplies the parallelism
        self.vision = ort.InferenceSession(vision, opts, providers=["CPUExecutionProvider"])
        self.text = ort.InferenceSession(text, opts, providers=["CPUExecutionProvider"])
        self.tok = Tokenizer.from_file(tokenizer)
        self.pad = self.tok.token_to_id("<pad>")
        self.eos = self.tok.token_to_id("<eos>")
        self.texts: dict = {}  # prompts tuple → (labels, vectors), worked out once per process

    def embed_image(self, crop_rgb):
        """The crop's unit image vector (1, dim)."""
        import numpy as np
        from PIL import Image
        img = Image.fromarray(crop_rgb).resize((IMAGE_SIZE, IMAGE_SIZE), Image.BILINEAR)
        x = (np.asarray(img, dtype=np.float32) / 255.0 - 0.5) / 0.5
        return self._pooled(self.vision, {self.vision.get_inputs()[0].name: x.transpose(2, 0, 1)[None]})

    @staticmethod
    def _pooled(session, feeds):
        import numpy as np
        names = [o.name for o in session.get_outputs()]
        out = session.run(None, feeds)
        vec = out[names.index("pooler_output")] if "pooler_output" in names else out[0]
        if vec.ndim == 3:
            vec = vec[:, 0]
        return vec / np.linalg.norm(vec, axis=1, keepdims=True)

    def is_what(self, image_vec) -> str:
        """The box check: CAR when the CAR_PROMPTS label nearest the crop is one of VEHICLES, else
        that label (what the box shows instead)."""
        labels, vecs = self._text(CAR_PROMPTS)
        label = labels[int((vecs @ image_vec[0]).argmax())]
        return CAR if label in VEHICLES else label

    def _text(self, prompts: dict) -> tuple:
        key = tuple(prompts.items())
        if key not in self.texts:
            self.texts[key] = (list(prompts), self._embed_text(list(prompts.values())))
        return self.texts[key]

    def _embed_text(self, prompts: list):
        import numpy as np
        rows = []
        for p in prompts:
            ids = self.tok.encode(p.lower()).ids[:TEXT_LEN]
            if ids[-1] != self.eos:
                ids = ids[:TEXT_LEN - 1] + [self.eos]
            rows.append(ids + [self.pad] * (TEXT_LEN - len(ids)))
        ids = np.array(rows, dtype=np.int64)
        feeds = {i.name: ids if i.name == "input_ids" else np.ones_like(ids) for i in self.text.get_inputs()}
        return self._pooled(self.text, feeds)

    def colour_scores(self, image_vec, palette) -> dict:
        """{colour: softmax score} over colour_prompts(palette), rounded to 3 places. Multi is always a
        key, which is how car_colour.decide_colour tells these from HSV shares."""
        import numpy as np
        labels, vecs = self._text(colour_prompts(palette))
        logits = SCALE * (vecs @ image_vec[0])
        p = np.exp(logits - logits.max())
        p /= p.sum()
        return {name: round(float(s), 3) for name, s in zip(labels, p)}

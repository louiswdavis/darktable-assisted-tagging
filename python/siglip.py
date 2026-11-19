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
# The box check drops a box only when VEHICLES' summed softmax share of CAR_PROMPTS is below
# BOX_MIN_VEHICLE_SHARE and the detector scored it below BOX_KEEP_SCORE (2026-11-17: a plain argmax
# dropped 5 identified Rallye cars, one detected at 0.84 with its number read at 0.99)
BOX_MIN_VEHICLE_SHARE = 0.25
BOX_KEEP_SCORE = 0.8
MULTI_PROMPT = "a photo of a multicoloured rally car."
# The number gate (collection setting number_gate): a plain box crop whose "number …" prompts take
# less than NUMBER_GATE_MIN of the softmax over NUMBER_PROMPTS is not read by OCR.
# NUMBER_GATE_MIN is provisional until eval_numbers.py has scored it on a truth set.
NUMBER = "number"
NUMBER_PROMPTS = {
    "number side": "a photo of a race car with a large racing number on its door.",
    "number front": "a photo of a rally car with a number plate and racing numbers.",
    "number bike": "a photo of a racing motorbike with a number board.",
    "none far": "a photo of a distant car, too small to read any number.",
    "none hidden": "a photo of a car with no number visible.",
    "none blur": "a blurred photo of a car with no readable text.",
}
NUMBER_GATE_MIN = 0.1
NUMBER_GATE_CACHE_TOKEN = "number-gate-1"


def siglip_files(vision_path: str) -> tuple:
    """(vision, text, tokenizer) paths: the text model and tokenizer share the vision file's name
    with `vision.onnx` swapped for `text.onnx` and `tokenizer.json`."""
    stem = vision_path[:-len("vision.onnx")] if vision_path.endswith("vision.onnx") else vision_path
    return vision_path, stem + "text.onnx", stem + "tokenizer.json"


def siglip_key(vision_path: str) -> list:
    """Cache key parts: the code token, a digest of this module's constants and all three files."""
    import hashlib
    consts = hashlib.sha1(repr((TEXT_LEN, IMAGE_SIZE, SCALE, CAR_PROMPTS, MULTI_PROMPT, VEHICLES,
                                BOX_MIN_VEHICLE_SHARE, BOX_KEEP_SCORE)).encode()).hexdigest()[:8]
    return [SIGLIP_CACHE_TOKEN, consts, *(file_key(p) for p in siglip_files(vision_path))]


def number_gate_key() -> list:
    """Cache key parts of an analysis made with the number gate on: they stay out of siglip_key, so
    a run with the gate off keeps its cached analyses."""
    import hashlib
    return [NUMBER_GATE_CACHE_TOKEN, hashlib.sha1(repr((NUMBER, NUMBER_PROMPTS, NUMBER_GATE_MIN)).encode()).hexdigest()[:8]]


def colour_prompts(palette) -> dict:
    """{colour name: prompt} for the palette's names (bounds are not used) plus Multi."""
    from car_colour import MULTI
    prompts = {name: f"a photo of a {name.lower()} rally car." for name, _ in palette}
    prompts[MULTI] = MULTI_PROMPT
    return prompts


class SigLIP:
    def __init__(self, vision_path: str, texts=None):
        """With `texts` (another SigLIP's prepare_texts), only the image model loads: the prompt
        vectors come from there, and a prompt set outside them raises."""
        import onnxruntime as ort
        ort.set_default_logger_severity(3)  # errors only: the model-load warnings flood the run log
        vision, text, tokenizer = siglip_files(vision_path)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1  # the worker pool supplies the parallelism
        self.vision = ort.InferenceSession(vision, opts, providers=["CPUExecutionProvider"])
        self.texts: dict = dict(texts or {})  # prompts tuple → (labels, vectors)
        self.text = self.tok = None
        if texts is not None:
            return
        from tokenizers import Tokenizer
        for path in (text, tokenizer):
            if not os.path.isfile(path):
                raise FileNotFoundError(f"{os.path.basename(path)} must sit beside {os.path.basename(vision)}")
        self.text = ort.InferenceSession(text, opts, providers=["CPUExecutionProvider"])
        self.tok = Tokenizer.from_file(tokenizer)
        self.pad = self.tok.token_to_id("<pad>")
        self.eos = self.tok.token_to_id("<eos>")

    def prepare_texts(self, palette=None, number_gate: bool = False) -> dict:
        """The prompt vectors a run needs (the box check's, the colour prompts of `palette` and, with
        `number_gate`, the number gate's), worked out here once; then the text model and tokenizer
        are freed. Pass the result to the workers' SigLIP."""
        self._text(CAR_PROMPTS)
        if palette:
            self._text(colour_prompts(palette))
        if number_gate:
            self._text(NUMBER_PROMPTS)
        self.text = self.tok = None
        return self.texts

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

    def is_what(self, image_vec) -> tuple:
        """The box check's view of a crop: (answer, vehicle share). The share is VEHICLES' summed
        softmax over CAR_PROMPTS, 3 places; the answer is CAR when the nearest label is one of
        VEHICLES or the share reaches BOX_MIN_VEHICLE_SHARE, else the nearest label (what the box
        shows instead)."""
        import numpy as np
        labels, vecs = self._text(CAR_PROMPTS)
        logits = SCALE * (vecs @ image_vec[0])
        p = np.exp(logits - logits.max())
        p /= p.sum()
        share = round(float(sum(p[i] for i, label in enumerate(labels) if label in VEHICLES)), 3)
        label = labels[int(logits.argmax())]
        return (CAR if label in VEHICLES or share >= BOX_MIN_VEHICLE_SHARE else label), share

    def number_visible(self, image_vec) -> float:
        """The number gate's view of a crop: the "number …" prompts' summed softmax share of
        NUMBER_PROMPTS, 3 places."""
        import numpy as np
        labels, vecs = self._text(NUMBER_PROMPTS)
        logits = SCALE * (vecs @ image_vec[0])
        p = np.exp(logits - logits.max())
        p /= p.sum()
        return round(float(sum(p[i] for i, label in enumerate(labels) if label.split()[0] == NUMBER)), 3)

    def _text(self, prompts: dict) -> tuple:
        key = tuple(prompts.items())
        if key not in self.texts:
            if self.text is None:
                raise RuntimeError(f"SigLIP 2 has no text model loaded and no vectors for the prompts {list(prompts)}")
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

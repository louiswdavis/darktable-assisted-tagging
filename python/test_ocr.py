# Run with: python python/test_ocr.py
# Exercises ocr's decoding, number filter and PaddleOCR input/dictionary helpers on made-up data;
# NumberReader needs the models. Needs PyYAML (requirements.txt).

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocr as O

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


def steps(*rows):
    """Recogniser output (T × 1 × 37) from (class, probability) per step; the rest is spread evenly."""
    out = np.zeros((len(rows), 1, 37))
    for t, (c, p) in enumerate(rows):
        out[t, 0, :] = (1 - p) / 36
        out[t, 0, c] = p
    return out


def digit(d):
    return O.REC_CHARSET.index(str(d)) + 1


text, conf = O._ctc_greedy(steps((digit(4), 0.99), (0, 0.9), (digit(2), 0.97)))
check("two sure digits read", text, "42")
check("the read's confidence is its least sure digit", round(conf, 2), 0.97)

text, conf = O._ctc_greedy(steps((digit(7), 0.6), (digit(7), 0.95), (0, 0.9), (digit(7), 0.9)))
check("a repeat collapses, a blank splits", text, "77")
check("a repeated step keeps its best probability", round(conf, 2), 0.9)

text, conf = O._ctc_greedy(steps((digit(1), 0.99), (digit(3), 0.5)))
check("one doubtful digit makes the read doubtful", round(conf, 2), 0.5)

check("nothing read gives confidence 0", O._ctc_greedy(steps((0, 0.99), (0, 0.99))), ("", 0.0))

probs = steps((digit(5), 0.9))
check("probabilities pass through", bool(np.allclose(O._probs(probs), probs.reshape(1, 37))), True)
check("log-probabilities come back as probabilities", bool(np.allclose(O._probs(np.log(probs)), probs.reshape(1, 37))), True)
logits = np.log(probs) + 3.0
check("logits are softmaxed", bool(np.allclose(O._probs(logits), probs.reshape(1, 37))), True)

# PaddleOCR recognisers: own charset, output T × classes with no middle axis.
paddle = np.zeros((2, 5))
paddle[0, 3], paddle[1, 2] = 1.0, 1.0
check("a PaddleOCR charset decodes", O._ctc_greedy(paddle, ["A", "7", "1", " "])[0], "17")

check("superscript digits are not a number", O.digits_only("1²"), None)
check("circled digits are not a number", O.digits_only("①"), None)
check("look-alike letters still read as digits", O.digits_only("1O"), "10")

check("the PaddleOCR yml sits beside the model", O.paddle_dict_path(os.path.join("m", "en_rec.onnx")), os.path.join("m", "en_rec.yml"))

import tempfile
with tempfile.TemporaryDirectory() as tmp:
    yml = os.path.join(tmp, "rec.yml")
    with open(yml, "w", encoding="utf-8") as f:
        f.write("PostProcess:\n  name: CTCLabelDecode\n  character_dict:\n  - '0'\n  - '1'\n  - y\n  - ''''\n")
    check("the dictionary keeps every entry a string", O.paddle_charset(yml, 5), ["0", "1", "y", "'"])
    check("one class more adds the space", O.paddle_charset(yml, 6), ["0", "1", "y", "'", " "])
    try:
        O.paddle_charset(yml, 9)
        check("a dictionary that doesn't fit the model raises", False, True)
    except ValueError:
        check("a dictionary that doesn't fit the model raises", True, True)

word = np.full((20, 40, 3), 255, np.uint8)
blob = O.paddle_rec_input(word)
check("PaddleOCR input is 1 x 3 x 48 x 320 for a short word", blob.shape, (1, 3, 48, 320))
check("the word is scaled to 1, the padding is 0", (float(blob[0, 0, 0, 0]), float(blob[0, 0, 0, 319])), (1.0, 0.0))
check("a long word widens the input", O.paddle_rec_input(np.zeros((10, 100, 3), np.uint8)).shape, (1, 3, 48, 480))

quad = np.array([[0, 20], [0, 0], [40, 0], [40, 20]], np.float32)
check("a quad warps flat at its own size", O.quad_word(np.zeros((30, 50, 3), np.uint8), quad).shape, (20, 40, 3))

if failures:
    print(f"{failures} failed")
    sys.exit(1)
print("all passed")

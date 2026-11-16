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

check("superscript digits are not part of a number", O.digit_runs("1²"), ["1"])
check("circled digits are not a number", O.digit_runs("①"), [])
check("look-alike letters still read as digits", O.digit_runs("1O"), ["10"])
check("a trailing space keeps the number", O.digit_runs("14 "), ["14"])
check("a hash before the number", O.digit_runs("#7"), ["7"])
check("a letter after the number", O.digit_runs("14A"), ["14"])
check("a word beside the number, its l not folded", O.digit_runs("14 RALLYE"), ["14"])
check("a year is not a number", O.digit_runs("2026"), [])
check("one read per digit run", O.digit_runs("l4-22"), ["14", "22"])
check("| reads as 1", O.digit_runs("|4"), ["14"])
check("S4 keeps its S in the read", O.digit_runs("S4"), ["4"])

# height_share: quads are bottom-left, top-left, top-right, bottom-right in letterbox pixels.
def quad(top, bottom, left=10, right=60):
    return np.array([[left, bottom], [left, top], [right, top], [right, bottom]], np.float32)


# a 600 × 300 crop letterboxes to 736 × 368: a 92 px tall region is a quarter of the crop's height
check("a door number is a fair share of the crop", round(O.height_share(quad(100, 192), 300, 600), 3), 0.25)
check("a plate character is a small share", O.height_share(quad(100, 118), 300, 600) < O.NUMBER_MIN_HEIGHT, True)
# a 300 × 600 (tall) crop fills the letterbox's height: 73.6 px is a tenth
check("a tall crop measures against the full height", round(O.height_share(quad(0, 73.6), 600, 300), 3), 0.1)
check("a slanted quad uses its longer side", round(O.height_share(
    np.array([[0, 92], [0, 0], [50, 0], [50, 46]], np.float32), 300, 600), 3), 0.25)

check("the PaddleOCR yml sits beside the model",O.paddle_dict_path(os.path.join("m", "en_rec.onnx")), os.path.join("m", "en_rec.yml"))

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

# Digit matrices: [blank, 0..9] per step, lead and trail blanks trimmed.
m = O.digit_matrix(steps((0, 0.999), (digit(4), 0.99), (0, 0.9), (digit(2), 0.97), (0, 0.999)))
check("a digit matrix trims sure blanks at either end", len(m), 3)
check("a digit matrix row is blank then 0-9", len(m[0]), 11)
check("a digit's column holds its probability", round(m[0][5], 2), 0.99)
check("a look-alike letter adds to its digit", O.digit_matrix(steps((O.REC_CHARSET.index("o") + 1, 0.9)))[0][1] >= 0.9, True)
check("an all-blank output gives no matrix", O.digit_matrix(steps((0, 0.999))), [])
check("a PaddleOCR charset folds to digits", O.digit_matrix(paddle, ["A", "7", "1", " "])[0][2], 1.0)
s4, five4 = np.zeros((2, 5)), np.zeros((2, 5))
s4[0, 1], s4[1, 4] = 1.0, 1.0        # S then 4
five4[0, 2], five4[1, 4] = 1.0, 1.0  # 5 then 4
check("an S's matrix scores 5 as a 5's does", O.digit_matrix(s4, ["S", "5", "|", "4"]), O.digit_matrix(five4, ["S", "5", "|", "4"]))
check("| and ! fold to 1 in the matrix", O.digit_matrix(np.eye(3)[1:], ["|", "!"])[0][2] + O.digit_matrix(np.eye(3)[1:], ["|", "!"])[1][2], 2.0)

# read_turned: a fake recogniser reads "42" only from an upright word, which it knows by a dark mark
# in the word's top-left corner; any other warp reads unsurely.
calls = []


def upright_only(bgr, q):
    calls.append(1)
    word = O.quad_word(bgr, q)
    h, w = word.shape[:2]
    if w > h and word[:h // 2, :w // 4].mean() < 80:
        return "42", 0.95, []
    return "??", 0.3, []


def box_quad(x0, y0, x1, y1):
    return np.array([[x0, y1], [x0, y0], [x1, y0], [x1, y1]], np.float32)


frame = np.full((120, 200, 3), 255, np.uint8)
frame[40:60, 40:70] = 0  # the word spans x 40-160, y 40-80; its top-left quarter is dark
for name, img, q, want in (
        ("upright", frame, box_quad(40, 40, 160, 80), ("42", 0)),
        ("turned 180°", np.rot90(frame, 2), box_quad(40, 40, 160, 80), ("42", 180)),
        ("turned 90° clockwise, a tall quad", np.rot90(frame, -1), box_quad(40, 40, 80, 160), ("42", 90)),
        ("turned 90° anticlockwise, a tall quad", np.rot90(frame, 1), box_quad(40, 40, 80, 160), ("42", 270))):
    got = O.read_turned(upright_only, np.ascontiguousarray(img), q)
    check(f"read_turned: a number {name} reads as upright", (got[0], got[3]), want)

calls.clear()
O.read_turned(upright_only, frame, box_quad(40, 40, 160, 80))
check("read_turned: a sure read is not retried", len(calls), 1)
calls.clear()
O.read_turned(upright_only, np.full((120, 200, 3), 255, np.uint8), box_quad(40, 40, 160, 80))
check("read_turned: a weak wide quad is retried at 180° only", len(calls), 2)
calls.clear()
got = O.read_turned(upright_only, np.full((200, 120, 3), 255, np.uint8), box_quad(40, 40, 80, 160))
check("read_turned: a weak tall quad is retried at 180°, 90° and 270°", len(calls), 4)
check("read_turned: no better read keeps the read as found", got[3], 0)

if failures:
    print(f"{failures} failed")
    sys.exit(1)
print("all passed")

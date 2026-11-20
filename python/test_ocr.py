# Run with: python python/test_ocr.py
# Exercises ocr's decoding, number filter and PaddleOCR input/dictionary helpers on made-up data;
# NumberReader needs the models. Needs PyYAML (requirements.txt).

import json
import os
import sys
import tempfile

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

# paddock ids: a listed id read whole is a paddock read, and its digits are no number
PAD = frozenset({"D14", "C6"})
check("a listed paddock id gives no number", O.digit_runs("D14", PAD), [])
check("a paddock id beside the number leaves the number", O.digit_runs("D14 100", PAD), ["100"])
check("an unlisted letter+digits token still gives its digits", O.digit_runs("A11", PAD), ["11"])
check("paddock ids are matched ignoring case", O.digit_runs("d14", PAD), [])
check("paddock_runs reads a listed id whole", O.paddock_runs("D14", PAD), ["D14"])
check("paddock_runs ignores case and keeps order, each once", O.paddock_runs("c6 d14 D14", PAD), ["C6", "D14"])
check("paddock_runs: a longer token is not the id", O.paddock_runs("D140 AD14", PAD), [])
check("paddock_runs: nothing listed reads nothing", O.paddock_runs("D14", frozenset()), [])
region = {"det": 0.9, "rec": 0.97, "text": "D14", "share": 0.2, "matrix": None}
check("pick_paddocks: a clean region reads its id", O.pick_paddocks([region], PAD), [("D14", 0.9)])
check("pick_paddocks: a weak detection reads nothing", O.pick_paddocks([dict(region, det=0.2)], PAD), [])
check("pick_paddocks: a tiny region reads nothing", O.pick_paddocks([dict(region, share=0.01)], PAD), [])
check("pick_paddocks: the second reader must read it too", O.pick_paddocks([dict(region, second="D1")], PAD), [])
check("pick_paddocks: the second reader agreeing keeps it", O.pick_paddocks([dict(region, second="d14")], PAD), [("D14", 0.9)])
check("pick_paddocks: the best region wins", O.pick_paddocks([region, dict(region, det=0.99, rec=0.99)], PAD), [("D14", 0.99)])
check("pick_reads: a paddock region gives no number", O.pick_reads([region], paddocks=PAD)[0], [])
check("pick_reads: with no paddocks listed D14 still gives 14", [d for d, _ in O.pick_reads([region])[0]], ["14"])
check("drop_reason: a paddock-only region is not_digits for numbers", O.drop_reason(region, paddocks=PAD), "not_digits")

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

    det_yml = os.path.join(tmp, "det.yml")
    with open(det_yml, "w", encoding="utf-8") as f:
        f.write("PostProcess:\n  box_thresh: 0.45\n  max_candidates: 3000\n  name: DBPostProcess\n  thresh: 0.2\n"
                "  unclip_ratio: 1.4\nPreProcess:\n  transform_ops:\n  - DecodeImage:\n      img_mode: BGR\n"
                "  - DetResizeForTest: null\n  - NormalizeImage:\n      mean: [0.485, 0.456, 0.406]\n"
                "      order: hwc\n      scale: 1./255.\n      std: [0.229, 0.224, 0.225]\n")
    det_config = O.paddle_det_config(det_yml)
    check("a detector yml gives its DB settings", (det_config["thresh"], det_config["box_thresh"],
          det_config["unclip_ratio"], det_config["max_candidates"]), (0.2, 0.45, 1.4, 3000))
    check("a detector yml gives its mean and std",
          tuple([round(float(x), 3) for x in det_config[k]] for k in ("mean", "std")),
          ([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]))
    try:
        O.paddle_det_config(yml)
        check("a recogniser's yml is not a detector's", False, True)
    except KeyError:
        check("a recogniser's yml is not a detector's", True, True)
    for name in ("det.onnx", "rec.onnx"):
        open(os.path.join(tmp, name), "wb").close()
    check("a PaddleOCR detector's yml joins the cache key", len(O.ocr_key(os.path.join(tmp, "det.onnx"), os.path.join(tmp, "rec.onnx"))), 4)
    os.remove(det_yml)
    check("without it the key is the two models and the recogniser's yml", len(O.ocr_key(os.path.join(tmp, "det.onnx"), os.path.join(tmp, "rec.onnx"))), 3)

    # db_boxes: a sure word 100 x 20, a faint blob and a speck
    prob = np.zeros((100, 200), np.float32)
    prob[40:60, 50:150] = 0.9
    prob[80:90, 10:30] = 0.3
    prob[5:7, 5:7] = 0.9
    db_quads, db_scores = O.db_boxes(prob, det_config)
    check("db_boxes keeps the sure word only", (len(db_quads), round(db_scores[0], 2)), (1, 0.9))
    q = db_quads[0]
    check("db_boxes corners run bottom-left, top-left, top-right, bottom-right",
          (q[0][0] < q[2][0], q[0][1] > q[1][1], q[3][0] > q[1][0], q[3][1] > q[2][1]), (True, True, True, True))
    check("db_boxes grows the box by area x unclip / perimeter (~11 px a side)",
          (round(float(q[1][0])), round(float(q[1][1])), round(float(q[3][0])), round(float(q[3][1]))), (39, 29, 160, 70))

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

# second reader: a region counts only when PARSeq read one of its numbers too
region = {"det": 0.95, "rec": 0.95, "text": "42", "share": 0.5, "matrix": [], "second": "17"}
check("drop_reason: readers that disagree drop the region", O.drop_reason(region), "disagree")
check("drop_reason: a second read with the number in it passes", O.drop_reason(dict(region, second="42.")), "")
check("drop_reason: no second read passes as before", O.drop_reason({k: v for k, v in region.items() if k != "second"}), "")
check("pick_reads: only the runs both readers read count",
      [d for d, _ in O.pick_reads([dict(region, text="42 7", second="42")])[0]], ["42"])

config = {"vocab": "0123456789", "mean": [0.5, 0.5, 0.5], "std": [0.25, 0.25, 0.25], "input_shape": [3, 32, 128]}
x = O.parseq_input(np.full((10, 20, 3), 255, np.uint8), config)
check("parseq_input: 1 × 3 × H × W from input_shape", x.shape, (1, 3, 32, 128))
check("parseq_input: the word keeps its aspect, white is (1 - mean) / std", float(x[0, 0, 31, 63]), 2.0)
check("parseq_input: the rest is zero padding, (0 - mean) / std", float(x[0, 0, 0, 64]), -2.0)


# onnxruntime is the edge: a fake whose session answers by the model file's bytes. The detector
# finds one wide word, the recogniser reads "42", PARSeq reads `parseq_text`.
class FakeSession:
    def __init__(self, model_bytes, opts, providers):
        self.model = model_bytes.decode()

    def get_inputs(self):
        return [type("Input", (), {"name": "x"})]

    def run(self, outputs, feed):
        x = feed["x"]
        if self.model == "det":
            prob = np.zeros((1, 1, *x.shape[2:]), np.float32)
            prob[0, 0, 40:100, 40:400] = 1.0
            return [prob]
        if self.model == "rec":
            out = np.zeros((1, 3, 12), np.float32)
            for t, c in enumerate((5, 0, 3)):  # 4, blank, 2 with the charset 0-9 after the blank
                out[0, t, c] = 1.0
            return [out]
        out = np.zeros((1, 5, 11), np.float32)
        for t, ch in enumerate(parseq_text + "$"):
            out[0, t, 10 if ch == "$" else config["vocab"].index(ch)] = 20.0
        return [out]


fake_ort = type(sys)("onnxruntime")
fake_ort.set_default_logger_severity = lambda level: None
fake_ort.SessionOptions = lambda: type("Options", (), {})()
fake_ort.InferenceSession = FakeSession
real_ort = sys.modules.get("onnxruntime")
sys.modules["onnxruntime"] = fake_ort
models = tempfile.mkdtemp()
for name in ("det", "rec", "parseq"):
    with open(os.path.join(models, name + ".onnx"), "w") as f:
        f.write(name)
with open(os.path.join(models, "det.yml"), "w") as f:
    f.write("PreProcess:\n  transform_ops:\n  - NormalizeImage:\n      mean: [0.5, 0.5, 0.5]\n      std: [0.5, 0.5, 0.5]\n"
            "PostProcess:\n  thresh: 0.3\n  box_thresh: 0.6\n  unclip_ratio: 1.5\n  max_candidates: 10\n")
with open(os.path.join(models, "rec.yml"), "w") as f:
    f.write("PostProcess:\n  character_dict: ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']\n")
with open(os.path.join(models, "parseq.json"), "w") as f:
    json.dump(config, f)

parseq_text = "17"
text, conf = O.ParseqRecogniser(os.path.join(models, "parseq.onnx")).read_word(np.zeros((40, 100, 3), np.uint8),
                                                                              box_quad(0, 0, 100, 40))
check("ParseqRecogniser: reads up to the end class", (text, round(conf, 3)), ("17", 1.0))
reader = O.NumberReader(os.path.join(models, "det.onnx"), os.path.join(models, "rec.onnx"),
                        second_path=os.path.join(models, "parseq.onnx"))
crop = np.zeros((368, 736, 3), np.uint8)
check("NumberReader: a second reader that disagrees gives no number", reader.read(crop), [])
check("NumberReader: last_second counts the disagreement", reader.last_second, {"checked": 1, "disagreed": 1})
parseq_text = "42"
check("NumberReader: both readers agreeing gives the number", [d for d, _ in reader.read(crop)], ["42"])
check("NumberReader: last_second counts the check", reader.last_second, {"checked": 1, "disagreed": 0})
check("NumberReader: no second reader reads as before",
      [d for d, _ in O.NumberReader(os.path.join(models, "det.onnx"), os.path.join(models, "rec.onnx")).read(crop)], ["42"])
# The fake recogniser's charset has no letters, so a listed id the fake can read ("42") stands in
# for D14: the plumbing is real, a letter read needs the real model (a Windows run).
check("NumberReader: no paddocks listed, nothing in last_paddocks", reader.last_paddocks, [])
reader.paddocks = frozenset({"42"})
check("NumberReader: a listed id is no number", reader.read(crop), [])
check("NumberReader: a listed id read by both readers is a paddock read", [c for c, _ in reader.last_paddocks], ["42"])
parseq_text = "17"
reader.read(crop)
check("NumberReader: a listed id the second reader disagrees on is no paddock read", reader.last_paddocks, [])
reader.paddocks = frozenset()
if real_ort:
    sys.modules["onnxruntime"] = real_ort
else:
    del sys.modules["onnxruntime"]

if failures:
    print(f"{failures} failed")
    sys.exit(1)
print("all passed")

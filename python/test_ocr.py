# Run with: python python/test_ocr.py
# Exercises ocr._probs and ocr._ctc_greedy on made-up recogniser output; NumberReader needs the models.

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

if failures:
    print(f"{failures} failed")
    sys.exit(1)
print("all passed")

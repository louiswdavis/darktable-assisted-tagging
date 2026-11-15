# Run with: python python/test_embed.py
# Exercises embed.Embedder.dim with a fake ONNX session; no models needed.

import os
import sys
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from embed import Embedder

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


class FakeSession:
    """Reports `shape` for last_hidden_state; a run returns a hidden state `size` wide."""

    def __init__(self, shape, size=0):
        self.shape = shape
        self.size = size
        self.runs = 0

    def get_outputs(self):
        return [SimpleNamespace(name="pooler_output", shape=[1, 1]),
                SimpleNamespace(name="last_hidden_state", shape=self.shape)]

    def run(self, names, feeds):
        self.runs += 1
        return [np.ones((1, 257, self.size), np.float32)]


def embedder(session) -> Embedder:
    e = Embedder.__new__(Embedder)
    e.session = session
    return e


def test_dim_follows_model():
    check("a base model's size is 768", embedder(FakeSession([1, 257, 768])).dim, 768)
    check("a large model's size is 1024", embedder(FakeSession([1, 257, 1024])).dim, 1024)
    s = FakeSession(["batch", "tokens", "hidden"], size=384)
    check("a symbolic size is measured with one run", (embedder(s).dim, s.runs), (384, 1))


def run_tests():
    test_dim_follows_model()
    print("")
    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

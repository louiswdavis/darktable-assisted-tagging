# Run with: python python/test_reference_store.py
# Exercises reference_store.py with a fake embedder; no models needed.

import os
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reference_store import ReferenceIndex

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


class FakeEmbedder:
    """One-hot vector picked by the crop's mean brightness, counting its calls."""

    def __init__(self):
        self.calls = 0

    def embed(self, crop):
        self.calls += 1
        v = np.zeros(384, np.float32)
        v[int(round(float(crop.mean()))) % 384] = 1.0
        return v


def crop(level: int) -> np.ndarray:
    return np.full((40, 80, 3), level, np.uint8)


def run_tests():
    # Review Focus 1: non-ASCII collection path and entry id
    d = tempfile.mkdtemp(prefix="références_ü_")
    emb = FakeEmbedder()
    idx = ReferenceIndex.load(d, emb, ["model", 1])
    check("an empty collection has no references", idx.count_by_entry(), {})
    check("matching an empty index gives nothing", idx.best_per_entry(np.ones(384, np.float32)), [])

    rel = idx.add("Pérez", "12", crop(10))
    check("a sample is saved as refs/<entry>/<image id>.jpg", rel, "refs/Pérez/12.jpg")
    check("the sample file exists under a non-ASCII path", os.path.isfile(os.path.join(d, "refs", "Pérez", "12.jpg")),
          True)
    # Review Focus 3: re-adding the same image replaces its sample
    idx.add("Pérez", "12", crop(10))
    idx.add("VER", "13", crop(200))
    idx.save()
    check("re-adding an image keeps one row for it", idx.count_by_entry(), {"Pérez": 1, "VER": 1})
    check("re-adding an image keeps one file", os.listdir(os.path.join(d, "refs", "Pérez")), ["12.jpg"])

    emb2 = FakeEmbedder()
    again = ReferenceIndex.load(d, emb2, ["model", 1])
    check("a reload reads the index without re-embedding", (again.count_by_entry(), emb2.calls),
          ({"Pérez": 1, "VER": 1}, 0))
    best = again.best_per_entry(again.emb[again.path.index("refs/VER/13.jpg")])
    check("matching ranks the identical sample first", [e for e, _ in best], ["VER", "Pérez"])
    check("an identical sample scores 1", round(best[0][1], 5), 1.0)

    os.remove(os.path.join(d, "refs", "VER", "13.jpg"))
    pruned = ReferenceIndex.load(d, FakeEmbedder(), ["model", 1])
    check("a deleted crop drops out of the index", pruned.count_by_entry(), {"Pérez": 1})

    ham_dir = os.path.join(d, "refs", "HAM")
    os.makedirs(ham_dir)
    Image.fromarray(crop(77)).save(os.path.join(ham_dir, "99.jpg"))
    emb3 = FakeEmbedder()
    found = ReferenceIndex.load(d, emb3, ["model", 1])
    check("a crop dropped in by hand is picked up and embedded", (found.count_by_entry(), emb3.calls),
          ({"Pérez": 1, "HAM": 1}, 1))

    emb4 = FakeEmbedder()
    rebuilt = ReferenceIndex.load(d, emb4, ["model", 2])
    check("a new embedder key re-embeds every crop", (rebuilt.count_by_entry(), emb4.calls), ({"Pérez": 1, "HAM": 1}, 2))

    with open(os.path.join(d, "index.npz"), "wb") as f:
        f.write(b"not a zip")
    emb5 = FakeEmbedder()
    recovered = ReferenceIndex.load(d, emb5, ["model", 2])
    check("an unreadable index is rebuilt from the crops", (recovered.count_by_entry(), emb5.calls),
          ({"Pérez": 1, "HAM": 1}, 2))

    # review fix 10: re-adding an image under another entry moves it
    m = tempfile.mkdtemp()
    idx = ReferenceIndex.load(m, FakeEmbedder(), ["model", 1])
    idx.add("WRONG", "5", crop(30))
    idx.add("RIGHT", "5", crop(30))
    check("re-adding an image under another entry moves its sample", idx.count_by_entry(), {"RIGHT": 1})
    check("the old entry's file is removed", os.path.exists(os.path.join(m, "refs", "WRONG", "5.jpg")), False)

    # review fix 11: a corrupt crop is skipped, not fatal
    c = tempfile.mkdtemp()
    os.makedirs(os.path.join(c, "refs", "VER"))
    Image.fromarray(crop(50)).save(os.path.join(c, "refs", "VER", "1.jpg"))
    open(os.path.join(c, "refs", "VER", "2.jpg"), "wb").close()
    try:
        skipped = ReferenceIndex.load(c, FakeEmbedder(), ["model", 1]).count_by_entry()
    except Exception as e:
        skipped = f"raised {type(e).__name__}"
    check("a zero-byte crop is skipped", skipped, {"VER": 1})

    print("")
    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

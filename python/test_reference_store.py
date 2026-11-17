# Run with: python python/test_reference_store.py
# Exercises reference_store.py with a fake embedder; no models needed.

import os
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reference_store import Anchors, ReferenceIndex

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

    def __init__(self, dim: int = 384):
        self.calls = 0
        self.dim = dim

    def embed(self, crop):
        self.calls += 1
        v = np.zeros(self.dim, np.float32)
        v[int(round(float(crop.mean()))) % self.dim] = 1.0
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

    # a crop replaced by hand (same name, other content) is embedded again on the next load
    Image.fromarray(crop(120)).save(os.path.join(d, "refs", "VER", "13.jpg"), quality=92)
    os.utime(os.path.join(d, "refs", "VER", "13.jpg"), ns=(1, 1))  # a clock-identical overwrite still differs in size or mtime
    emb_r = FakeEmbedder()
    replaced = ReferenceIndex.load(d, emb_r, ["model", 1])
    check("a replaced crop is re-embedded", (replaced.count_by_entry(), emb_r.calls), ({"Pérez": 1, "VER": 1}, 1))
    check("the re-embedding reads the new content", int(np.argmax(replaced.emb[replaced.path.index("refs/VER/13.jpg")])), 120)
    emb_s = FakeEmbedder()
    ReferenceIndex.load(d, emb_s, ["model", 1])
    check("the replaced crop's new stat is saved", emb_s.calls, 0)

    os.remove(os.path.join(d, "refs", "VER", "13.jpg"))
    pruned = ReferenceIndex.load(d, FakeEmbedder(), ["model", 1])
    check("a deleted crop drops out of the index", pruned.count_by_entry(), {"Pérez": 1})

    # colour: two samples with the same embedding, told apart only by colour
    d2 = tempfile.mkdtemp(prefix="colour_")
    plain = ReferenceIndex.load(d2, FakeEmbedder(), ["model", 1])
    red, blue = np.zeros((40, 80, 3), np.uint8), np.zeros((40, 80, 3), np.uint8)
    red[..., 0], blue[..., 2] = 200, 200
    plain.add("RED", "1", red)
    plain.add("BLUE", "2", blue)
    plain.save()
    emb3 = FakeEmbedder()
    coloured = ReferenceIndex.load(d2, emb3, ["model", 1], colour=True)
    check("turning colour on reads histograms from the crops without re-embedding", emb3.calls, 0)
    from colour import colour_hist
    best = coloured.best_per_entry(coloured.emb[0], colour_hist(blue), 1.0)
    check("a blue query ranks the blue sample first when colour counts", best[0][0], "BLUE")
    best = coloured.best_per_entry(coloured.emb[0], colour_hist(red), 1.0)
    check("a red query ranks the red sample first when colour counts", best[0][0], "RED")
    check("colour weight 0 ignores the histogram", len({round(s, 5) for _, s in
          coloured.best_per_entry(coloured.emb[0], colour_hist(red), 0.0)}), 1)
    again = ReferenceIndex.load(d2, FakeEmbedder(), ["model", 1], colour=True)
    check("saved histograms reload", again.hist.shape, (2, 54))

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

    # audit M2: re-embedding ticks progress, and a stop keeps what was embedded
    ticks = []
    ReferenceIndex.load(d, FakeEmbedder(), ["model", 3], on_progress=lambda n, t: ticks.append((n, t)))
    check("re-embedding reports each reference", ticks, [(1, 2), (2, 2)])
    emb6 = FakeEmbedder()
    stopped = ReferenceIndex.load(d, emb6, ["model", 4], on_progress=lambda n, t: False)
    check("a stop after the first reference keeps it", (len(stopped.path), emb6.calls), (1, 1))
    emb7 = FakeEmbedder()
    resumed = ReferenceIndex.load(d, emb7, ["model", 4])
    check("the next load embeds only the rest", (resumed.count_by_entry(), emb7.calls), ({"Pérez": 1, "HAM": 1}, 1))

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

    # a face index: 128-d vectors, raw similarities for every reference
    class SmallEmbedder:
        def embed(self, crop):
            v = np.zeros(128, np.float32)
            v[int(round(float(crop.mean()))) % 128] = 1.0
            return v

    f = tempfile.mkdtemp()
    idx = ReferenceIndex.load(f, SmallEmbedder(), ["faces"], dim=128)
    idx.add("A", "1", crop(10))
    idx.add("A", "2", crop(11))
    idx.add("B", "3", crop(10))
    idx.save()
    check("a 128-d index reloads at 128", ReferenceIndex.load(f, SmallEmbedder(), ["faces"], dim=128).emb.shape, (3, 128))
    probe = SmallEmbedder().embed(crop(10))
    check("all_sims gives one raw cosine per reference", sorted((e, round(s, 3)) for e, s in idx.all_sims(probe)),
          [("A", 0.0), ("A", 1.0), ("B", 1.0)])
    check("all_sims on an empty index", ReferenceIndex.load(tempfile.mkdtemp(), SmallEmbedder(), ["faces"], dim=128).all_sims(probe), [])

    # the index re-embeds when the embedder size changes (small 384 -> base 768)
    g = tempfile.mkdtemp()
    small = ReferenceIndex.load(g, FakeEmbedder(384), ["K1", False])
    small.add("A", "1", crop(10))
    small.add("B", "2", crop(200))
    small.save()
    base = FakeEmbedder(768)
    bigger = ReferenceIndex.load(g, base, ["K2", False], dim=base.dim)
    check("a new embedder size re-embeds every reference", (base.calls, bigger.emb.shape), (2, (2, 768)))
    check("an empty index takes the embedder's size", ReferenceIndex.load(tempfile.mkdtemp(), base, ["K2", False]).emb.shape,
          (0, 768))

    # ticket 58: a small collection centres on its references plus this run's boxes
    def car(i):
        v = np.zeros(384, np.float32)
        v[0], v[i] = 3.0, 1.0  # a large shared component, as the real embedder gives
        return v / np.linalg.norm(v)

    s = ReferenceIndex.load(tempfile.mkdtemp(), FakeEmbedder(), ["model", 1])
    for i in range(5):
        s.add(f"E{i}", str(i), crop(10 + i))
    s.emb = np.stack([car(i + 1) for i in range(5)])
    raw = dict(s.best_per_entry(car(1)))
    check("a small collection with no run centre scores two cars raw", round(raw["E1"], 2), 0.9)
    check("too few run boxes keeps raw similarity", s.use_run_centre([car(6)] * 3),
          "livery: raw similarity (5 references and 3 boxes, under 20)")
    check("raw similarity leaves no centre", s.centre, None)
    run = [car(i) for i in range(6, 21)]
    check("enough run boxes centre the collection", s.use_run_centre(run),
          "livery: centred on 5 references and 15 boxes from this run")
    centred = dict(s.best_per_entry(car(1)))
    check("centring drops another car's score well below raw", centred["E1"] < 0.2, True)
    check("centring keeps the identical car at 1", round(centred["E0"], 5), 1.0)

    # ---- ticket 80: sources and anchors
    a = tempfile.mkdtemp()
    ai = ReferenceIndex.load(a, FakeEmbedder(), ["anchors"])
    ai.add("10", "1", crop(10))
    ai.add("10", "2", crop(10), "picked")
    ai.add("20", "3_b0", crop(20), "number", 0.95123)
    ai.add("20", "4_b0", crop(30), "number", 0.6)
    ai.save()
    check("each button records its source", [ai.sources[r]["source"] for r in ai.path], ["hand", "picked", "number", "number"])
    check("a number ref keeps its read", (ai.sources["refs/20/3_b0.jpg"]["confidence"],
                                          ai.sources["refs/20/4_b0.jpg"]["confidence"]), (0.9512, 0.6))
    check("hand, picked and strong reads anchor; a weak read doesn't", [ai.is_anchor(r) for r in ai.path],
          [True, True, True, False])
    check("sources.json survives a reload", ReferenceIndex.load(a, FakeEmbedder(), ["anchors"]).sources, ai.sources)

    b = tempfile.mkdtemp()
    os.makedirs(os.path.join(b, "refs", "7"))
    Image.fromarray(crop(10)).save(os.path.join(b, "refs", "7", "5_b0.jpg"))
    Image.fromarray(crop(10)).save(os.path.join(b, "refs", "7", "6.jpg"))
    bi = ReferenceIndex.load(b, FakeEmbedder(), ["backfill"])
    check("refs saved before sources.json are backfilled by file name",
          {r: (bi.sources[r]["source"], bi.sources[r]["confidence"]) for r in bi.path},
          {"refs/7/5_b0.jpg": ("number", None), "refs/7/6.jpg": ("hand", None)})
    check("a backfilled number ref of unknown read anchors", bi.is_anchor("refs/7/5_b0.jpg"), True)
    check("the backfill is written to sources.json", os.path.isfile(os.path.join(b, "refs", "sources.json")), True)

    probe = FakeEmbedder()
    anchors = Anchors(ai, {})
    check("a weak number read is not an anchor", anchors.rels, ["refs/10/1.jpg", "refs/10/2.jpg", "refs/20/3_b0.jpg"])
    check("a box like its car's anchors", anchors.unlike("10", probe.embed(crop(10)))[0], "like")
    check("a box unlike its car's anchors", anchors.unlike("10", probe.embed(crop(40)))[:2], ("unlike", 0.0))
    check("a box closer to another car's anchor names that car", anchors.unlike("10", probe.embed(crop(20))),
          ("unlike", 0.0, "20"))
    check("a car with no anchor accepts its first match", anchors.unlike("30", probe.embed(crop(40))),
          ("unanchored", None, ""))
    check("unanchored lists cars with no anchor", anchors.unanchored(["10", "20", "30"]), ["30"])
    anchors.add("30", probe.embed(crop(40)), rel="run box")
    check("a run's box becomes an anchor", anchors.unlike("30", probe.embed(crop(40)))[0], "like")
    pooled = Anchors(ai, {"11": "10"})
    check("a double-driven car's second entry uses the first entry's anchors",
          pooled.unlike("11", probe.embed(crop(10)))[0], "like")
    check("skip leaves a job's new refs out of the anchors", Anchors(ai, {}, skip=["refs/20/3_b0.jpg"]).has("20"), False)
    check("an anchor is not its own evidence", anchors.compare("20", probe.embed(crop(20)), skip_rel="refs/20/3_b0.jpg"), None)

    print("")
    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

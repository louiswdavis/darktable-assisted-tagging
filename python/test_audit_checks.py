"""audit_refs.py's per-ref checks on real arrays and real files: events, attractors, near-duplicate groups,
flags, the share histogram and quarantine. No models: the embeddings are small hand-made vectors."""
import os
import sys
import tempfile

import numpy as np
from PIL import Image

import audit_refs as AR

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


def write_image(folder: str, rel: str, size: tuple):
    full = os.path.join(folder, *rel.split("/"))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    Image.new("RGB", size, (90, 90, 90)).save(full)


def run_tests():
    # ---- ref_events: ids split into race weekends wherever two consecutive ids are > EVENT_GAP apart
    paths = ["refs/A/100.jpg", "refs/A/150.jpg", "refs/B/5000.jpg", "refs/B/5100_b2.jpg", "refs/C/20000.jpg"]
    events, ranges = AR.ref_events(paths)
    check("events: a gap over EVENT_GAP starts a new event", events, [0, 0, 1, 1, 2])
    check("events: ranges are lowest id, highest id and ref count", ranges, [(100, 150, 2), (5000, 5100, 2), (20000, 20000, 1)])
    check("events: a box suffix (5100_b2) still reads as id 5100", ranges[1][1], 5100)
    check("events: ids within the gap stay one event", AR.ref_events(["a/1.jpg", "a/900.jpg"])[0], [0, 0])

    # ---- share_histogram
    lines = AR.share_histogram([0.0, 0.0, 0.02, 0.07, 0.12, 0.3, 0.9])
    check("histogram: first line counts frames with no car", lines[0], "  no car found: 2")
    check("histogram: one line per band after it", len(lines), 1 + len(AR.FRAME_SHARE_BUCKETS) + 1)
    check("histogram: shares land in the band whose lower edge they reach",
          [l.split(": ")[1] for l in lines[1:]], ["1", "1", "1", "0", "1", "1"])
    check("histogram: the top band ends at 100%", lines[-1].startswith("  50% to 100%"), True)

    # ---- ref_flags
    flags = AR.ref_flags([(0.3, 1, 2)], [(0.99, 1, 0)], [(0.1, 4, 0)], [(0.5, 4, "x")], [(5.0, 7, "wide")], [7, 9])
    check("flags: a ref flagged by several checks lists each, in check order", flags[1], ["mislabel", "copy"])
    check("flags: the colour, outlier and crop checks share ref 4 and 7", (flags[4], flags[7]), (["outlier", "colour"], ["crop", "frame"]))
    check("flags: frames contribute their indexes directly", flags[9], ["frame"])
    check("flags: no flags at all is empty", AR.ref_flags([], [], [], [], [], []), {})

    # ---- attractor_audit: three B refs whose closest ref is the single A0, so A0 wins three wrong queries
    base = np.array([1.0, 0, 0, 0], np.float32)
    emb = np.array([base,                                        # 0 A0, the attractor
                    base * 0.9 + 0.3 * np.eye(4)[1],             # 1-3 B refs, each closest to A0
                    base * 0.9 + 0.3 * np.eye(4)[2],
                    base * 0.9 + 0.3 * np.eye(4)[3],
                    -base], np.float32)                          # 4 A1, far from everything
    entry = ["A", "B", "B", "B", "A"]
    found = AR.attractor_audit(emb, entry, {}, 0.97)
    check("attractor: the ref that wins other entries' matches is listed", [f[2] for f in found], [0])
    check("attractor: its wrong pulls are counted and named by victim entry", (found[0][0], found[0][3]), (3, {"B": 3}))
    check("attractor: it won no right matches", found[0][1], 0)
    teammates = AR.attractor_audit(emb, entry, {"A": "T", "B": "T"}, 0.97)
    check("attractor: pulls between teammates are counted apart and don't list the ref", teammates, [])
    check("attractor: fewer than ATTRACTOR_MIN_PULLS wrong pulls lists nothing",
          AR.attractor_audit(emb[:3], entry[:3], {}, 0.97), [])

    # ---- duplicate_groups: near-identical refs of one entry; the biggest picture is kept
    with tempfile.TemporaryDirectory() as tmp:
        rels = ["refs/A/1.jpg", "refs/A/2.jpg", "refs/A/3.jpg", "refs/B/4.jpg", "refs/A/5.jpg"]
        sizes = [(40, 40), (80, 80), (60, 60), (50, 50), (30, 30)]
        for rel, size in zip(rels, sizes):
            write_image(tmp, rel, size)
        dup = np.array([[1, 0, 0], [1, 0.001, 0], [1, 0, 0.001], [0, 1, 0], [0, 0, 1]], np.float32)
        groups = AR.duplicate_groups(tmp, dup, ["A", "A", "A", "B", "A"], rels, 0.97)
        check("duplicates: one group of the three near-identical A refs", len(groups), 1)
        keep, drop, low = groups[0]
        check("duplicates: the ref with the most pixels is kept", rels[keep], "refs/A/2.jpg")
        check("duplicates: the others are dropped, bigger first", [rels[i] for i in drop], ["refs/A/3.jpg", "refs/A/1.jpg"])
        check("duplicates: the lowest similarity to the kept ref is reported", 0.97 <= low <= 1.0, True)
        check("duplicates: distinct refs make no group", AR.duplicate_groups(tmp, np.eye(5, dtype=np.float32), ["A"] * 5, rels, 0.97), [])

        # ---- quarantine_refs: moved, listed, and an existing list is appended to
        write_image(tmp, "refs/C/9.jpg", (20, 20))
        first = AR.quarantine_refs(tmp, ["refs/A/1.jpg", "refs/B/4.jpg"], ["A", "B"], [0], {0: ["mislabel", "crop"]})
        check("quarantine: returns the indexes it moved", first, [0])
        check("quarantine: the file moved into refs-quarantine/<entry>/",
              (os.path.exists(os.path.join(tmp, "refs", "A", "1.jpg")),
               os.path.exists(os.path.join(tmp, AR.QUARANTINE_DIR, "A", "1.jpg"))), (False, True))
        AR.quarantine_refs(tmp, ["refs/C/9.jpg"], ["C"], [0], {0: ["frame"]})
        with open(os.path.join(tmp, AR.QUARANTINE_DIR, AR.QUARANTINE_LIST_NAME), encoding="utf-8") as f:
            listed = f.read().splitlines()
        check("quarantine: moved.txt holds a line per file, old runs kept", len(listed), 2)
        check("quarantine: a line is new path, old path, flags (tab separated)",
              listed[0].split("\t"), ["refs-quarantine/A/1.jpg", "refs/A/1.jpg", "mislabel,crop"])

    print("")
    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

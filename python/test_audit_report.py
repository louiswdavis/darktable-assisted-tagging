"""audit_refs.py's report writer, screening and crop suggestions on a real collection folder: entries.json,
index.npz and ref images on disk. No detector or models: embeddings are small hand-made vectors, and the
boxes handed to suggest_crops are what a detector would return."""
import json
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


def make_collection(tmp: str) -> list:
    """Entries A and B with 4 refs each. B's ref 4 sits on A's side, so it is a mislabel suspect."""
    rels = [f"refs/A/{i}.jpg" for i in (1, 2, 3, 4)] + [f"refs/B/{i}.jpg" for i in (5, 6, 7, 8)]
    entry = ["A"] * 4 + ["B"] * 4
    emb = np.array([[1, 0.1 * k, 0] for k in range(4)] + [[1, 0.5, 0], [0, 1, 0.1], [0, 1, 0.2], [0, 1, 0.3]], np.float32)
    emb /= np.linalg.norm(emb, axis=1, keepdims=True)
    for rel in rels:
        full = os.path.join(tmp, *rel.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        Image.new("RGB", (60, 40), (120, 80, 40)).save(full)
    np.savez(os.path.join(tmp, "index.npz"), emb=emb, entry=np.array(entry), path=np.array(rels))
    with open(os.path.join(tmp, "entries.json"), "w", encoding="utf-8") as f:
        json.dump({"entries": [{"id": "A"}, {"id": "B"}]}, f)
    return rels


def read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def run_tests():
    with tempfile.TemporaryDirectory() as tmp:
        rels = make_collection(tmp)

        # ---- write_audit without a detector
        report, counts = AR.write_audit(tmp)
        text = read(report)
        check("audit: the report is ref-audit.txt in the collection folder", report, os.path.join(tmp, "ref-audit.txt"))
        check("audit: header counts the references and entries", text.splitlines()[0].startswith("8 references, 2 entries"), True)
        check("audit: counts say how many references it read", counts["references"], 8)
        check("audit: no detector says so and skips the frame list",
              ("whole-frame check skipped (no detector)" in text, os.path.exists(os.path.join(tmp, AR.FRAME_FULL_LIST_NAME))), (True, False))
        check("audit: every section heading is written",
              all(h in text for h in ("## strongest candidates", "## mislabel suspects", "## cross-entry copies", "## outliers",
                                       "## odd crops", "## redundant", "## duplicate groups")), True)
        check("audit: the mislabelled ref is named in the mislabel section", "refs/B/5.jpg" in text.split("## mislabel suspects")[1], True)
        check("audit: nothing is quarantined unless asked", (counts["quarantined"], os.path.exists(os.path.join(tmp, AR.QUARANTINE_DIR))), (0, False))
        check("audit: top limits the rows of a section",
              len(AR.write_audit(tmp, top=0)[0]) > 0 and "refs/B/5.jpg" not in read(report).split("## mislabel suspects")[1].split("## cross-entry")[0], True)

        # ---- write_audit with quarantine: only refs flagged by 2+ checks move
        _, counts = AR.write_audit(tmp, quarantine=True)
        check("audit: quarantined count matches the strongest candidates", counts["quarantined"], counts["strongest"])
        check("audit: quarantine adds its section", "## quarantined" in read(report), True)

        # ---- screen_refs: flags only the asked-for refs
        screened = AR.screen_refs(tmp, ["refs/B/5.jpg"])
        check("screen: only the asked refs can appear", set(screened) <= {"refs/B/5.jpg"}, True)
        check("screen: refs not asked for are never listed", AR.screen_refs(tmp, []), {})

        # ---- suggest_crops: one car is re-cut, none or several are skipped
        frames = [(0.1, 0), (0.0, 1), (0.1, 2)]
        boxes = [[[10, 5, 40, 30]], [], [[0, 0, 20, 20], [30, 0, 55, 20]]] + [[]] * 5
        os.makedirs(os.path.join(tmp, AR.CROP_SUGGEST_DIR, "A"), exist_ok=True)
        stale = os.path.join(tmp, AR.CROP_SUGGEST_DIR, "A", "old.jpg")
        Image.new("RGB", (4, 4)).save(stale)
        written, no_car, several = AR.suggest_crops(tmp, rels, ["A"] * 4 + ["B"] * 4, frames, boxes)
        check("crops: only the single-car ref is written", written, [0])
        check("crops: no-car and several-car skips are counted apart", (no_car, several), (1, 1))
        check("crops: the copy lands in <dir>/<entry>/<file>", os.path.exists(os.path.join(tmp, AR.CROP_SUGGEST_DIR, "A", "1.jpg")), True)
        check("crops: earlier suggestions are replaced", os.path.exists(stale), False)
        check("crops: the original ref is untouched", Image.open(os.path.join(tmp, "refs", "A", "1.jpg")).size, (60, 40))

    # ---- a collection with one entry can't be audited
    with tempfile.TemporaryDirectory() as tmp:
        make_collection(tmp)
        with open(os.path.join(tmp, "entries.json"), "w", encoding="utf-8") as f:
            json.dump({"entries": [{"id": "A"}, {"id": "B"}]}, f)
        np.savez(os.path.join(tmp, "index.npz"), emb=np.eye(4, dtype=np.float32), entry=np.array(["A"] * 4), path=np.array(rels))
        check("screen: under 2 entries screens nothing", AR.screen_refs(tmp, ["refs/A/1.jpg"]), {})
        try:
            AR.write_audit(tmp)
            raised = ""
        except SystemExit as e:
            raised = str(e)
        check("audit: under 2 entries exits naming the need", "needs 2+ entries" in raised, True)

    print("")
    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

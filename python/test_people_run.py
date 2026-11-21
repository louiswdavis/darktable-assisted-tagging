"""people_run.py: frame analysis, face matching and the report record for `people` collections. The face
model (YuNet/SFace) and the reference store are the edge and are faked; every function under test is real."""
import json
import os
import sys
import tempfile

import numpy as np

import identify as I
import people_run as PR
from embed import decode
from people import Face

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


def unit(*v) -> np.ndarray:
    vec = np.array(v, np.float32)
    return vec / np.linalg.norm(vec)


class FakeFaceModel:
    """detect() returns the given faces; embed_face() returns one vector per face, by order."""

    def __init__(self, faces, vectors):
        self.faces, self.vectors, self.aligned = faces, vectors, []

    def detect(self, rgb):
        return sorted(self.faces, key=lambda f: -f.w * f.h)

    def embed_face(self, rgb, face):
        return self.vectors[self.faces.index(face)]

    def align_crop(self, rgb, face):
        self.aligned.append(face)
        return rgb[:4, :4]


class FakeIndex:
    """all_sims like ReferenceIndex: [(entry_id, cosine)] over every reference."""

    def __init__(self, refs):
        self.refs = refs

    def all_sims(self, vec):
        return [(eid, float(np.dot(ref, vec))) for eid, ref in self.refs]


def face(x, w, score=0.9) -> Face:
    return Face(x, 10.0, w, w, [(x + 1, 11.0)] * 5, score)


def people_entries(settings=None):
    LH = {"id": "LH", "tags": ["People|Lewis"]}
    PX = {"id": "PX", "tags": ["People|Pat"]}
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "entries.json"), "w", encoding="utf-8") as f:
            json.dump({"kind": "people", "entries": [LH, PX]}, f)
        with open(os.path.join(tmp, "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"min_sim": 0.5, "margin": 0.1, "min_face_px": 40}, f)
        return I.load_collection(tmp)[:2]


def run_tests():
    entries, rules = people_entries()
    rgb = np.zeros((100, 200, 3), np.uint8)

    # ---- analyse_frame_people
    a = PR.analyse_frame_people(rgb, FakeFaceModel([face(20, 30), face(100, 60)], [unit(1, 0), unit(0, 1)]))
    check("analyse: frame is [width, height]", a["frame"], [200, 100])
    check("analyse: no note when faces are found", a["note"], "")
    check("analyse: boxes are largest first with their score", [b[2] for b in a["boxes"]], [60, 30])
    check("analyse: one embedding per face, in box order",
          [decode(e).round(3).tolist() for e in a["emb"]], [[0.0, 1.0], [1.0, 0.0]])
    none = PR.analyse_frame_people(rgb, FakeFaceModel([], []))
    check("analyse: a frame with no face says so", (none["note"], none["boxes"], none["emb"]), ("no face found", [], []))

    # ---- match_frame_people
    index = FakeIndex([("LH", unit(1, 0)), ("PX", unit(0, 1))])
    detail = []
    results = PR.match_frame_people("img1", a, index, entries, rules, detail)
    check("match: a big enough face is named by its closest entry", [r.entry_id for r in results], ["PX", ""])
    check("match: a named face's method is face, an unnamed one's is none", [r.method for r in results], ["face", "none"])
    check("match: detail has one row per face with status and width",
          [(d["face"], d["status"], d["width_px"]) for d in detail], [(0, "tagged", 60.0), (1, "too_small", 30.0)])
    check("match: a too-small face is left unnamed", results[1].entry_id, "")
    check("match: candidates are rounded [entry, similarity] best first", detail[0]["candidates"][0], ["PX", 1.0])

    twin = PR.analyse_frame_people(rgb, FakeFaceModel([face(20, 50), face(100, 60)], [unit(1, 0.05), unit(1, 0)]))
    twin_detail = []
    twin_results = PR.match_frame_people("img2", twin, index, entries, rules, twin_detail)
    check("match: one person is named once; the weaker duplicate becomes unknown",
          sorted(r.entry_id for r in twin_results), ["", "LH"])
    check("match: the duplicate's detail status is unknown", sorted(d["status"] for d in twin_detail), ["tagged", "unknown"])

    stranger = PR.analyse_frame_people(rgb, FakeFaceModel([face(20, 60)], [unit(1, 1)]))
    ambiguous = PR.match_frame_people("img3", stranger, index, entries, rules, [])
    check("match: two equally close entries are ambiguous, not named", (ambiguous[0].entry_id, ambiguous[0].alt_entry_id != ""), ("", True))
    check("match: no references means unknown", PR.match_frame_people("img4", a, FakeIndex([]), entries, rules, [])[0].entry_id, "")

    # ---- build_boxes_people
    frames = {"img1": results, "img5": [I.BoxResult(-1, "skipped")], "img6": [I.BoxResult(-1, "none")], "img7": [I.BoxResult(-1, "error")]}
    shots = {k: "single" for k in frames}
    details = {
        "img1": {"file": "a.jpg", "frame": [200, 100], "faces": detail, "note": "", "burst": "b1", "time": 5},
        "img5": {"file": "e.jpg", "frame": [], "faces": [], "note": "", "burst": "", "time": None},
        "img6": {"file": "c.jpg", "frame": [200, 100], "faces": [], "note": "no face found", "burst": "", "time": None},
        "img7": {"file": "d.jpg", "frame": [], "faces": [], "note": "", "burst": "", "time": None},
    }
    out = PR.build_boxes_people("coll", frames, shots, details, entries, {"LH": 3}, rules)
    check("report: kind and collection", (out["kind"], out["collection"]), ("people", "coll"))
    check("report: thresholds come from the rules", out["thresholds"], {"min_sim": 0.5, "margin": 0.1, "min_face_px": 40})
    check("report: entries carry tags and reference counts", out["entries"]["LH"], {"tags": ["People|Lewis"], "refs": 3})
    check("report: an entry with no references counts 0", out["entries"]["PX"]["refs"], 0)
    check("report: skipped images are listed and left out of images", (out["skipped"], "img5" in out["images"]), (["img5"], False))
    check("report: statuses are ok, no_face and error",
          (out["images"]["img1"]["status"], out["images"]["img6"]["status"], out["images"]["img7"]["status"]), ("ok", "no_face", "error"))
    check("report: a face row carries its entry, method and conflict flag",
          [(f["entry"], f["method"], f["conflict"]) for f in out["images"]["img1"]["faces"]], [("PX", "face", False), ("", "none", False)])
    conflicted = {"img1": [I.BoxResult(0, "conflict", "LH", "", 0.9)]}
    flag = PR.build_boxes_people("coll", conflicted, {"img1": "single"}, {"img1": dict(details["img1"], faces=detail[:1])}, entries, {}, rules)
    check("report: a conflict result sets the conflict flag", flag["images"]["img1"]["faces"][0]["conflict"], True)

    # ---- reference_face
    model = FakeFaceModel([face(20, 60)], [unit(1, 0)])
    crop, status = PR.reference_face(rgb, model)
    check("reference_face: one face gives its aligned crop", (status, crop is not None, len(model.aligned)), ("ok", True, 1))
    check("reference_face: no face", PR.reference_face(rgb, FakeFaceModel([], [])), (None, "no_face"))
    check("reference_face: two faces can't say which is meant",
          PR.reference_face(rgb, FakeFaceModel([face(20, 30), face(100, 60)], [unit(1, 0), unit(0, 1)])), (None, "multiple_faces"))

    print("")
    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

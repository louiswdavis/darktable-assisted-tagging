# Run with: python python/test_identify.py
# Exercises identify.py's entries/rules loading, cache key, output and run flow,
# plus vehicles.py's decode and crop, on synthetic files; no models needed.

import json
import os
import sys
import tempfile
from argparse import Namespace

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import identify as I
import vehicles as V
from embed import encode
from match import BoxResult

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


VER = {"id": "VER", "number": "1", "team": "Red Bull", "tags": ["F1|Red Bull", "F1|Red Bull|Verstappen"]}
TSU = {"id": "TSU", "number": 22, "team": "Red Bull", "tags": ["F1|Red Bull", "F1|Red Bull|Tsunoda"]}


def collection(data, root=None) -> str:
    d = tempfile.mkdtemp(dir=root)
    with open(os.path.join(d, "entries.json"), "w", encoding="utf-8") as f:
        f.write(data if isinstance(data, str) else json.dumps(data))
    return d


def load_error(data) -> str:
    d = collection(data)
    try:
        I.load_collection(d)
    except I.InputError as e:
        msg = str(e)
        return msg[len(os.path.join(d, "entries.json")) + 2:] if msg.startswith(os.path.join(d, "entries.json")) \
            else "(message doesn't start with the file path) " + msg
    return "(no error)"


def run_tests():
    # ---- loading entries.json
    entries, rules = I.load_collection(collection([VER, TSU]))
    check("a bare list loads entries in file order", list(entries), ["VER", "TSU"])
    check("an int number is read as text", entries["TSU"].number, "22")
    check("a bare list gets the default rules", rules, I.Rules())
    entries, rules = I.load_collection(collection({"rules": {"team_only": "none", "unidentified": ["F1|Check"],
                                                             "diagnostics": {"burst": "", "team": "X|Team"}},
                                                   "entries": [VER]}))
    check("rules: team_only", rules.team_only, "none")
    check("rules: unidentified tags", rules.unidentified, ("F1|Check",))
    check("rules: renamed, dropped and default diagnostics", dict(rules.diagnostics),
          dict(I.DIAG_DEFAULTS, burst="", team="X|Team"))
    check("default diagnostics sit under Assisted Tagging|Motorsport",
          all(v.startswith("Assisted Tagging|Identification|") for v in I.DIAG_DEFAULTS.values()), True)

    check("duplicate id is rejected", load_error([VER, VER]), 'entry "VER" appears twice')
    check("a comma in a tag is rejected", load_error([dict(VER, tags=["a,b"])]),
          'entry "VER": tags: tag "a,b" can\'t contain , ; or "')
    check("a non-digit number is rejected", load_error([dict(VER, number="1a")]), 'entry "VER": number must be 1–3 digits')
    check("empty tags are rejected", load_error([dict(VER, tags=[])]),
          'entry "VER": tags must be a non-empty list of tag names')
    check("a path character in an id is rejected", load_error([dict(VER, id="a/b")]).startswith('entry "a/b": id can\'t'),
          True)
    check("bad JSON is rejected", load_error("[{").startswith("not valid JSON"), True)
    d = tempfile.mkdtemp()
    try:
        I.load_collection(d)
        missing = "(no error)"
    except I.InputError as e:
        missing = str(e)
    check("a missing entries.json names the file", missing, os.path.join(d, "entries.json") + ": file not found")
    check("a misspelt rule is named", load_error({"rules": {"team_onyl": "none"}, "entries": []}),
          'unknown rule "team_onyl" (rules are team_only, unidentified, diagnostics, burst_livery_pooling, blur_references, sponsor_keywords, partial_references)')
    check("a misspelt entry field is named", load_error([dict(VER, tagz=[])]),
          'entry "VER": unknown field "tagz" (fields are id, number, team, tags, camera)')
    check("a misspelt top-level key is named", load_error({"entrys": []}),
          'unknown key "entrys" (the file holds "rules" and "entries")')
    check("a bad team_only value is rejected", load_error({"rules": {"team_only": "both"}, "entries": []}),
          'rules.team_only must be "shared tags" or "none"')
    check("an unknown diagnostic is named", load_error({"rules": {"diagnostics": {"guess": "x"}}, "entries": []}),
          'unknown diagnostic "guess" (they are number, livery, burst, team, none, number_seen, pooled, shot_solo, shot_pack, shot_crowded)')

    # ---- csv outputs and the tag plan
    entries, rules = I.load_collection(collection({"rules": {"unidentified": ["F1|Check"]},
                                                   "entries": [VER, TSU, {"id": "SC", "tags": ["F1|Safety Car"]}]}))
    out = tempfile.mkdtemp()
    I.write_entries_csv(entries, os.path.join(out, "e.csv"))
    I.write_rules_csv(rules, os.path.join(out, "r.csv"))
    check("entries.csv rows", open(os.path.join(out, "e.csv"), encoding="utf-8").read().splitlines()[1],
          "TSU,Red Bull,22,F1|Red Bull;F1|Red Bull|Tsunoda")
    check("rules.csv rows", open(os.path.join(out, "r.csv"), encoding="utf-8").read().splitlines()[:3],
          ["team_only,shared tags", "unidentified,F1|Check", "diag_number,Assisted Tagging|Identification|By number"])
    plan = I.tag_plan("F1", entries, rules, {"VER": 3})
    check("the plan lists the teammates' shared tags", "  Red Bull (VER, TSU):\n      F1|Red Bull\n" in plan, True)
    check("the plan lists the unidentified tags", "rules.unidentified.\n      F1|Check" in plan, True)
    check("the plan names entries it can only find by number",
          "No references yet, so identified by number only: TSU" in plan, True)
    check("the plan names entries it can never find yet",
          "No number and no references, so never identified until references are added: SC" in plan, True)
    none_plan = I.tag_plan("F1", entries, I.Rules(team_only="none"), {})
    check("the plan says team only adds nothing with team_only none", "adds no collection tags" in none_plan, True)

    # ---- cache key
    img = tempfile.mkdtemp()
    frame = os.path.join(img, "f.jpg")
    Image.new("RGB", (64, 48), (90, 90, 90)).save(frame)
    models = {k: frame for k in ("detector", "ocr_det", "ocr_rec", "embedder")}
    key = I.frame_key(frame, models)
    saved = I.OCR_MIN_SCORE
    I.OCR_MIN_SCORE = 0.5
    check("changing OCR_MIN_SCORE changes the cache key", I.frame_key(frame, models) != key, True)
    I.OCR_MIN_SCORE = saved
    check("the cache key is stable", I.frame_key(frame, models), key)

    # ---- results rows
    check("a no-vehicle row", I.format_row("7", BoxResult(-1, "none")), "7,-1,none,,,0.000,,")
    check("a team row carries the runner-up", I.format_row("7", BoxResult(0, "team", "VER", "TSU", 0.71234)),
          "7,0,team,VER,TSU,0.712,,")
    check("a row ends with the shot type", I.format_row("7", BoxResult(0, "number", "VER", "", 0.9), "pack"),
          "7,0,number,VER,,0.900,,pack")
    check("a row has eight fields", len(I.format_row("7", BoxResult(0, "none"), "solo").split(",")), 8)

    # ---- Review Focus 2: EXIF-rotated frames
    rotated = os.path.join(img, "portrait.jpg")
    exif = Image.Exif()
    exif[0x0112] = 6  # stored landscape, displayed rotated 90° clockwise
    Image.new("RGB", (300, 200), (10, 120, 200)).save(rotated, exif=exif)
    rgb = V.load_full(rotated)
    check("an Orientation-6 JPEG decodes upright (portrait)", rgb.shape[:2], (300, 200))
    crop = V.crop_box(rgb, (0, 0, 200, 150, 0.9, 2))
    check("a crop of an upright box keeps the upright aspect", crop.shape[:2], (120, 160))
    check("crops are never upscaled", V.crop_box(rgb, (10, 10, 60, 40, 0.9, 2)).shape[:2], (24, 40))
    check("box selection clips, filters and sorts",
          [b[:4] for b in V.select_boxes([(-5, 0, 50, 40, 0.9, 2), (0, 0, 2, 2, 0.9, 2), (0, 0, 200, 300, 0.5, 7)],
                                         200, 300)],
          [(0.0, 0.0, 200.0, 300.0), (0.0, 0.0, 50.0, 40.0)])

    # ---- review fix 5: models load from non-ASCII paths, and bad models fail at startup
    models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models")
    yolox = os.path.join(models_dir, "object_detection_yolox_2022nov.onnx")
    if os.path.isfile(yolox):
        uni = tempfile.mkdtemp(prefix="modèles_José_")
        moved = os.path.join(uni, "yolox.onnx")
        with open(yolox, "rb") as src, open(moved, "wb") as dst:
            dst.write(src.read())
        check("an ONNX model loads from a non-ASCII path", V.read_onnx(moved) is not None, True)
    else:
        print("skip non-ASCII model load (models/ not downloaded)")
    fake = os.path.join(img, "not-a-model.onnx")
    with open(fake, "w") as f:
        f.write("<html>404</html>")
    try:
        I.check_models({"detector": fake, "ocr_det": fake, "ocr_rec": fake, "embedder": fake})
        bad = "(no error)"
    except I.InputError as e:
        bad = str(e)
    check("a file that isn't a model fails at startup with exit-2 input error",
          bad.startswith("object detector model can't be loaded"), True)
    check("the worker pool is capped", I.worker_count(64) <= I.MAX_WORKERS and I.worker_count(2) == 1, True)

    # ---- the identify run, with the analysis stubbed (no models)
    root = tempfile.mkdtemp(prefix="collections_")
    coll = collection([VER, TSU], root=root)
    manifest = os.path.join(img, "manifest.csv")
    with open(manifest, "w", encoding="utf-8") as f:
        f.write('"1","/x/1.jpg","5"\n"2","/x/2.jpg","5"\n"3","/x/3.jpg","5"\n"4","/x/4.jpg","9"\n"5","/x/5.jpg","9"\n')
    vec = encode(np.eye(384, dtype=np.float32)[0])
    car = [[0, 0, 100, 50, 0.9, 2]]
    fr = [100, 50]
    stub = {
        "/x/1.jpg": {"boxes": car, "ocr": [[["1", 0.95]]], "ocr_trace": [[]], "pod": [{}], "emb": [vec], "note": "", "frame": fr},
        "/x/2.jpg": {"boxes": car, "ocr": [[["1", 0.90]]], "ocr_trace": [[]], "pod": [{}], "emb": [vec], "note": "", "frame": fr},
        "/x/3.jpg": {"boxes": car, "ocr": [[]], "ocr_trace": [[]], "pod": [{}], "emb": [vec], "note": "", "frame": fr},
        "/x/4.jpg": {"boxes": [], "ocr": [], "emb": [], "note": "no vehicle"},
        "/x/5.jpg": None,
        "/x/6.jpg": {"boxes": car, "ocr": [[["1", 0.95]]], "ocr_trace": [[]], "pod": [{}], "emb": [vec], "note": "", "frame": fr},
        "/x/7.jpg": {"boxes": car, "ocr": [[["1", 0.95]]], "ocr_trace": [[]], "pod": [{}], "emb": [vec], "note": "", "frame": fr},
        "/x/8.jpg": {"boxes": car, "ocr": [[]], "ocr_trace": [[]], "pod": [{}], "emb": [vec], "note": "", "frame": fr},
        "/x/9.jpg": {"boxes": car * 2, "ocr": [[["1", 0.95]], []], "ocr_trace": [[], []], "pod": [{}, {}], "emb": [vec, vec], "note": "", "frame": fr},
    }

    class FakeEmbedder:
        def __init__(self, path):
            pass

        def embed(self, crop):
            return np.eye(384, dtype=np.float32)[0]

    real = (I.check_models, I.Embedder, I.run_frames)
    I.check_models, I.Embedder = (lambda m: FakeEmbedder("fake")), FakeEmbedder
    I.run_frames = lambda paths, models, cache, progress: stub
    results = os.path.join(img, "results.csv")
    args = Namespace(manifest=manifest, results=results, progress=os.path.join(img, "progress.txt"), cache="",
                     collections_root=root, collection=os.path.basename(coll), entries_out=os.path.join(img, "e.csv"),
                     rules_out=os.path.join(img, "r.csv"), boxes_out="", boxes_in="", report_out="", report_top=20, archive_dir="")
    I.identify(args, {"embedder": "fake"})
    rows = open(results, encoding="utf-8").read().splitlines()
    check("number reads, burst consensus and no-vehicle rows come out in manifest order (3-column manifest)", rows,
          ["1,0,number,VER,,0.950,,solo", "2,0,number,VER,,0.900,,solo", "3,0,burst,VER,,0.667,,solo",
           "4,-1,none,,,0.000,,", "5,-1,error,,,0.000,,"])
    check("the run writes the collection's tag plan", os.path.isfile(os.path.join(coll, "tag-plan.txt")), True)
    check("the run writes rules.csv for the plugin", os.path.isfile(args.rules_out), True)

    _, shot_rules = I.load_collection(collection({"rules": {"diagnostics": {"shot_pack": "Mine|Pack", "shot_solo": ""}},
                                                  "entries": [VER]}))
    check("shot diagnostics can be renamed or dropped like the others",
          (dict(shot_rules.diagnostics)["shot_pack"], dict(shot_rules.diagnostics)["shot_solo"],
           dict(shot_rules.diagnostics)["shot_crowded"]),
          ("Mine|Pack", "", I.DIAG_DEFAULTS["shot_crowded"]))

    # ---- hand-applied tags: skipped, conflict (also after burst fill), packs; and boxes.json
    with open(manifest, "w", encoding="utf-8") as f:
        f.write('"1","/x/1.jpg","5","F1|Red Bull;F1|Red Bull|Tsunoda"\n'
                '"2","/x/2.jpg","5","F1|Red Bull|Tsunoda"\n'
                '"6","/x/6.jpg","8",""\n"7","/x/7.jpg","8",""\n'
                '"8","/x/8.jpg","8","F1|Red Bull|Tsunoda"\n'
                '"9","/x/9.jpg","9","F1|Red Bull|Tsunoda"\n')
    args.boxes_out = os.path.join(img, "last-run", "c.boxes.json")
    I.identify(args, {"embedder": "fake"})
    rows = open(results, encoding="utf-8").read().splitlines()
    check("a fully tagged image is skipped; solo disagreement is a conflict, also when burst-filled; packs aren't", rows,
          ["1,-1,skipped,,,0.000,,", "2,0,conflict,VER,,0.900,,solo", "6,0,number,VER,,0.950,,solo",
           "7,0,number,VER,,0.950,,solo", "8,0,conflict,VER,,0.667,,solo", "9,0,number,VER,,0.950,,pack",
           "9,1,none,,,0.000,,pack"])
    run = json.load(open(args.boxes_out, encoding="utf-8"))
    check("boxes.json names the collection and the skipped images", (run["collection"], run["skipped"]),
          (os.path.basename(coll), ["1"]))
    check("boxes.json records the shot and frame", (run["images"]["9"]["shot"], run["images"]["9"]["frame"]),
          ("pack", [100, 50]))
    b = run["images"]["2"]["boxes"][0]
    check("a conflict box keeps its entry and is flagged", (b["method"], b["entry"], b["conflict"]),
          ("conflict", "VER", True))
    check("a box with no references says why", run["images"]["9"]["boxes"][1]["decided_by"], "no_references")
    check("a number box records its OCR", run["images"]["6"]["boxes"][0]["ocr"], [["1", 0.95]])
    check("boxes.json records each image's status and the box's unmatched digits",
          (run["images"]["9"]["status"], run["images"]["9"]["boxes"][1]["unmatched_number"]), ("ok", ""))
    check("boxes.json carries the thresholds and per-entry facts the report needs",
          (sorted(run["thresholds"]), sorted(run["entries"]["VER"])), (["min_margin", "min_sim", "reference_margin"],
                                                                      ["camera", "number", "refs", "tags", "team"]))
    args.report_out = os.path.join(img, "last-run", "c.report")
    I.identify(args, {"embedder": "fake"})
    check("--report-out writes report.md and report.json", (os.path.isfile(args.report_out + ".md"),
          json.load(open(args.report_out + ".json", encoding="utf-8"))["summary"]["counts"]["already-tagged"]), (True, 1))
    args.report_out = ""

    # ---- --promote-boxes: saves confident boxes from the box crop, replaces on re-run, flags a changed file
    real_jpg = os.path.join(img, "promo.jpg")
    Image.new("RGB", (100, 50), (200, 30, 30)).save(real_jpg)
    promo_boxes = os.path.join(img, "promo.boxes.json")

    def write_promo(frame):
        record = {"shot": "pack", "file": real_jpg, "frame": frame, "boxes": [
            {"box": 0, "bbox": [0, 0, 50, 50], "entry": "VER", "alt_entry": "", "method": "number",
             "confidence": 0.95, "candidates": [], "ocr": [], "decided_by": "number", "gap": 0.0, "conflict": False},
            {"box": 1, "bbox": [50, 0, 100, 50], "entry": "TSU", "alt_entry": "", "method": "livery",
             "confidence": 0.8, "candidates": [["TSU", 0.80], ["VER", 0.78]], "ocr": [], "decided_by": "livery",
             "gap": 0.0, "conflict": False}]}
        with open(promo_boxes, "w", encoding="utf-8") as f:
            json.dump({"collection": os.path.basename(coll), "images": {"1": record}, "skipped": []}, f)

    with open(manifest, "w", encoding="utf-8") as f:
        f.write(f'"1","{real_jpg}",""\n')
    pargs = Namespace(manifest=manifest, results=results, progress=os.path.join(img, "p2.txt"), cache="",
                      collections_root=root, collection=os.path.basename(coll), entries_out=args.entries_out,
                      rules_out=args.rules_out, boxes_out="", boxes_in=promo_boxes)
    write_promo([100, 50])
    I.promote_boxes(pargs, {"embedder": "fake"})
    check("promote adds a confident box", open(results, encoding="utf-8").read().strip(), "1,added")
    refs = sorted(os.listdir(os.path.join(coll, "refs")))
    check("only the wide-margin box became a reference", refs, ["VER"])
    I.promote_boxes(pargs, {"embedder": "fake"})
    check("promoting again replaces rather than duplicates", len(os.listdir(os.path.join(coll, "refs", "VER"))), 1)
    write_promo([10, 10])
    I.promote_boxes(pargs, {"embedder": "fake"})
    check("a file that no longer matches the run is stale", open(results, encoding="utf-8").read().strip(), "1,stale")

    # ---- Review Focus 4: cancel leaves no results
    os.remove(results)
    open(args.progress + ".cancel", "w").close()
    try:
        I.identify(args, {"embedder": "fake"})
        code = 0
    except SystemExit as e:
        code = e.code
    check("a cancelled run exits 130", code, 130)
    check("a cancelled run writes no results", os.path.exists(results) or os.path.exists(results + ".tmp"), False)
    I.check_models, I.Embedder, I.run_frames = real

    # ---- Stage B: hints
    mf = os.path.join(tempfile.mkdtemp(), "m.csv")
    with open(mf, "w", encoding="utf-8") as f:
        f.write('1,a.jpg,0\n2,b.jpg,0,F1|X\n3,c.jpg,0,,F1|Red Bull\n')
    check("3-, 4- and 5-column manifests all parse", [r[3:] for r in I.read_manifest(mf, 3, 2)],
          [["", ""], ["F1|X", ""], ["", "F1|Red Bull"]])
    ents = {"VER": I.Entry("VER", "1", "Red Bull", ("F1|Red Bull", "F1|Red Bull|Verstappen"))}
    check("strict prefixes of entry tags", I.strict_prefixes(ents), ["F1", "F1|Red Bull"])
    check("tag and sponsor hints that agree merge", I.box_hint(["F1|Red Bull"], ["F1|Red Bull"]), (["F1|Red Bull"], "both"))
    check("a tag hint beats a differing sponsor hint", I.box_hint(["F1|Ferrari"], ["F1|Red Bull"]), (["F1|Ferrari"], "tag"))
    check("sponsor hint alone", I.box_hint([], ["F1|Red Bull"]), (["F1|Red Bull"], "sponsor"))
    check("no hint", I.box_hint([], []), ([], ""))
    check("sponsor_keywords naming a prefix with no entries is rejected",
          load_error({"rules": {"sponsor_keywords": {"petronas": "F1|Mercedes"}}, "entries": [VER]}).startswith(
              "rules.sponsor_keywords.petronas: no entry has a tag under"), True)
    check("sponsor_keywords must be lowercase", load_error(
          {"rules": {"sponsor_keywords": {"Petronas": "F1"}}, "entries": [VER]}),
          "rules.sponsor_keywords must map lowercase keywords to tag prefixes")
    check("partial_references must be a boolean", load_error({"rules": {"partial_references": "yes"}, "entries": [VER]}),
          "rules.partial_references must be true or false")

    print("")
    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


# Worker processes re-import this file on spawn; only the parent runs the tests.
if __name__ == "__main__":
    run_tests()

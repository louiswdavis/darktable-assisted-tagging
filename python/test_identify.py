# Run with: python python/test_identify.py
# Exercises identify.py's entries/rules loading, cache key, output and run flow,
# plus vehicle_detect.py's decode and vehicles.py's crop, on synthetic files; no models needed.

import ast
import json
import os
import sys
import tempfile
from argparse import Namespace

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import car_colour as C
import fingerprint as FP
import identify as I
import ocr as O
import vehicle_detect as VD
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
    entries, rules, _fe = I.load_collection(collection([VER, TSU]))
    check("a bare list loads entries in file order", list(entries), ["VER", "TSU"])
    check("an int number is read as text", entries["TSU"].number, "22")
    check("a bare list gets the default rules", rules, I.Rules())
    entries, rules, _fe = I.load_collection(collection({"rules": {"team_only": "none", "unidentified": ["F1|Check"],
                                                             "diagnostics": {"burst": "", "team": "X|Team"}},
                                                   "entries": [VER]}))
    check("rules: team_only", rules.team_only, "none")
    check("rules: unidentified tags", rules.unidentified, ("F1|Check",))
    check("rules: renamed, dropped and default diagnostics", dict(rules.diagnostics),
          dict(I.DIAG_DEFAULTS, burst="", team="X|Team"))
    check("default diagnostics sit under Assisted Tagging|Motorsport",
          all(v.startswith("Assisted Tagging|Identification|") for k, v in I.DIAG_DEFAULTS.items() if k != "colour"), True)

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
          'unknown rule "team_onyl" (rules are team_only, unidentified, sponsor_keywords, tag_prefix, colour_palette; '
          'behaviour settings such as order_weight go in settings.json)')
    lines = []
    real_log, I.log = I.log, lines.append
    try:
        moved_entries, moved_rules, _fe = I.load_collection(collection(
            {"rules": {"order_weight": 0.5, "min_read": 0.9}, "entries": [VER]}))
    finally:
        I.log = real_log
    check("moved rules in entries.json still load", (moved_rules.order_weight, moved_rules.min_read), (0.5, 0.9))
    check("moved rules log the deprecation", "rules.order_weight in entries.json is deprecated; move it to settings.json" in lines, True)
    check("a misspelt entry field is named", load_error([dict(VER, tagz=[])]),
          'entry "VER": unknown field "tagz" (fields are id, number, team, name, tags, camera, colour)')
    check("a misspelt top-level key is named", load_error({"entrys": []}),
          'unknown key "entrys" (the file holds "kind", "rules" and "entries")')
    LH = {"id": "Lando Norris", "tags": ["People|Professions|F1 Drivers|Lando Norris"]}
    PX = {"id": "Max Verstappen", "tags": ["People|Professions|F1 Drivers|Max Verstappen"]}
    check("kind defaults to motorsport", I.load_collection(collection([VER, TSU]))[1].kind, "motorsport")
    p_entries, p_rules, _fe = I.load_collection(collection({"kind": "people", "entries": [LH, PX]}))
    check("a people collection loads", (p_rules.kind, list(p_entries), p_entries["Lando Norris"].tags),
          ("people", ["Lando Norris", "Max Verstappen"], ("People|Professions|F1 Drivers|Lando Norris",)))
    check("people face rules have defaults", (p_rules.min_sim, p_rules.margin, p_rules.min_face_px), (0.50, 0.05, 48))
    _, tuned, _fe = I.load_collection(collection({"kind": "people", "rules": {"min_sim": 0.6, "margin": 0, "min_face_px": 64},
                                             "entries": [LH]}))
    check("people face rules are read", (tuned.min_sim, tuned.margin, tuned.min_face_px), (0.6, 0.0, 64))
    check("a people entry with a number is rejected", load_error({"kind": "people", "entries": [dict(LH, number="3")]}),
          'entry "Lando Norris": unknown field "number" (fields are id, tags)')
    check("an unknown kind lists the valid ones", load_error({"kind": "faces", "entries": []}),
          "unknown kind 'faces' (kinds are motorsport, people)")
    check("a bad team_only value is rejected", load_error({"rules": {"team_only": "both"}, "entries": []}),
          'rules.team_only must be "shared tags" or "none"')

    # ---- rules.tag_prefix builds tags from team and name
    entries, rules, _fe = I.load_collection(collection({"rules": {"tag_prefix": "Motorsport|F1"}, "entries": [
        {"id": "VER", "team": "Red Bull", "name": "Max Verstappen", "tags": ["Extra|Champion", "Motorsport|F1|Red Bull"]},
        {"id": "RB", "team": "Red Bull"}, {"id": "SC", "name": "Safety Car"}]}))
    check("prefix: team, then team|name, then extras without repeats", entries["VER"].tags,
          ("Motorsport|F1|Red Bull", "Motorsport|F1|Red Bull|Max Verstappen", "Extra|Champion"))
    check("prefix: a team-only entry gets just the team tag", entries["RB"].tags, ("Motorsport|F1|Red Bull",))
    check("prefix: a name with no team hangs off the prefix", entries["SC"].tags, ("Motorsport|F1|Safety Car",))
    check("name without a prefix is rejected", load_error({"entries": [dict(VER, name="Max")]}),
          'entry "VER": name needs rules.tag_prefix; without one, list the full tags')
    check("prefix: an entry with nothing to build from is rejected",
          load_error({"rules": {"tag_prefix": "F1"}, "entries": [{"id": "X"}]}),
          'entry "X": needs a team or name to build its tags from rules.tag_prefix, or its own tags')
    n_entries, _, _fe = I.load_collection(collection({"rules": {"tag_prefix": "Rally|2026"}, "entries": [
        {"id": "12", "number": "12"}, {"id": "7", "number": 7, "team": "Red"}]}))
    check("numbers-only entry tags come from prefix and number", n_entries["12"].tags, ("Rally|2026|12",))
    check("an entry with a team keeps the team tag, not the number", n_entries["7"].tags, ("Rally|2026|Red",))
    check("numbers-only entry without a prefix is rejected",
          load_error({"entries": [{"id": "12", "number": "12"}]}),
          'entry "12": tags must be a non-empty list of tag names')
    check("order_weight defaults to 0", I.load_collection(collection([VER]))[1].order_weight, 0.0)
    check("min_read defaults to 0.85", I.load_collection(collection([VER]))[1].min_read, 0.85)
    sd = collection([VER])
    with open(os.path.join(sd, "settings.json"), "w", encoding="utf-8") as f:
        f.write('{"order_weight": 0.2}')
    other = os.path.join(tempfile.mkdtemp(), "other.json")
    with open(other, "w", encoding="utf-8") as f:
        f.write('{"order_weight": 0.7}')
    check("settings.json sets order_weight", I.load_collection(sd)[1].order_weight, 0.2)
    check("a settings_path file overrides the collection's", I.load_collection(sd, other)[1].order_weight, 0.7)
    sd = collection([VER])
    with open(os.path.join(sd, "settings.json"), "w", encoding="utf-8") as f:
        f.write('{"tag_colour": false}')
    d_rules = I.load_collection(sd)[1]
    check("diag_from_settings_json: colour switch off blanks the name", dict(d_rules.diagnostics)["colour"], "")
    d_csv = os.path.join(tempfile.mkdtemp(), "d.csv")
    I.write_rules_csv(d_rules, (), d_csv)
    check("diag_from_settings_json: rules.csv has diag_colour,", "diag_colour," in open(d_csv, encoding="utf-8").read().splitlines(), True)
    # ---- colour tags
    check("colour_tags defaults off", I.load_collection(collection([VER]))[1].colour_tags, False)
    check("colour_tags is read", I.load_collection(collection({"rules": {"colour_tags": True}, "entries": [VER]}))[1].colour_tags, True)
    blue = dict(C.PALETTE)["Blue"]
    check("default palette is the built-in one", I.load_collection(collection([VER]))[1].colour_palette, C.PALETTE)
    _, navy, _fe = I.load_collection(collection({"rules": {"colour_palette": {"Navy": "Blue"}}, "entries": [VER]}))
    check("a built-in name renames and drops the rest", navy.colour_palette, (("Navy", blue),))
    _, custom, _fe = I.load_collection(collection({"rules": {"colour_palette": {"Teal": [
        {"hue": [80, 95], "sat": [60, 255], "val": [40, 255]}, {"hue": [96, 100]}]}}, "entries": [VER]}))
    check("bounds objects map to 6-tuples, missing sat/val is full range", custom.colour_palette,
          (("Teal", ((80, 95, 60, 255, 40, 255), (96, 100, 0, 255, 0, 255))),))
    for bad_palette in ({"Multi": "Red"}, {"Red": "Pink"}, {"Red": [{"hue": [9, 3]}]}, {"Red": [{"hue": [0, 300]}]},
                        {"A|B": "Red"}, {}, {"Red": []}):
        check(f"colour_palette {bad_palette!r} is rejected",
              "colour_palette" in load_error({"rules": {"colour_palette": bad_palette}, "entries": [VER]}), True)
    entries, _, _fe = I.load_collection(collection([dict(VER, colour="Red"), dict(TSU, colour="Multi")]))
    check("entry colour is read", (entries["VER"].colour, entries["TSU"].colour), ("Red", "Multi"))
    check("entry colour defaults empty", I.load_collection(collection([VER]))[0]["VER"].colour, "")
    msg = load_error([dict(VER, colour="Pink")])
    check("unknown entry colour names the entry and colour", 'entry "VER"' in msg and "Pink" in msg, True)
    msg = load_error({"rules": {"colour_palette": {"Red": "Red"}}, "entries": [dict(VER, colour="Blue")]})
    check("entry colour outside the palette names the entry and colour", 'entry "VER"' in msg and "Blue" in msg, True)
    _, diag, _fe = I.load_collection(collection({"rules": {"diagnostics": {"colour": "Rally|Colour"}}, "entries": [VER]}))
    check("colour diagnostic is renamable", dict(diag.diagnostics)["colour"], "Rally|Colour")
    check("a trailing | on the prefix is rejected", "tag_prefix" in load_error({"rules": {"tag_prefix": "F1|"}, "entries": []}), True)

    # ---- csv outputs and the tag plan
    entries, rules, _fe = I.load_collection(collection({"rules": {"unidentified": ["F1|Check"]},
                                                   "entries": [VER, TSU, {"id": "SC", "tags": ["F1|Safety Car"]}]}))
    out = tempfile.mkdtemp()
    I.write_entries_csv(entries, os.path.join(out, "e.csv"))
    I.write_rules_csv(rules, _fe, os.path.join(out, "r.csv"))
    check("entries.csv rows", open(os.path.join(out, "e.csv"), encoding="utf-8").read().splitlines()[1],
          "TSU,Red Bull,22,F1|Red Bull;F1|Red Bull|Tsunoda")
    check("rules.csv rows", open(os.path.join(out, "r.csv"), encoding="utf-8").read().splitlines()[:3],
          ["team_only,shared tags", "unidentified,F1|Check", "diag_number,Assisted Tagging|Identification|By number"])
    rows = open(os.path.join(out, "r.csv"), encoding="utf-8").read().splitlines()
    check("rules.csv ends with from_entries_json, empty here", rows[-1], "from_entries_json,")
    entries, rules, fe = I.load_collection(collection({"rules": {"order_weight": 0.5}, "entries": [VER]}))
    I.write_rules_csv(rules, fe, os.path.join(out, "r2.csv"))
    text = open(os.path.join(out, "r2.csv"), encoding="utf-8").read()
    check("rules_csv_has_moved_keys", all(x in text.splitlines() for x in (
        "order_weight,0.5", "neighbour_tolerance,5", "colour_tags,false", "from_entries_json,order_weight")), True)
    entries, rules, _fe = I.load_collection(collection({"rules": {"unidentified": ["F1|Check"]},
                                                   "entries": [VER, TSU, {"id": "SC", "tags": ["F1|Safety Car"]}]}))
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
    models["kind"] = "motorsport"
    key = I.frame_key(frame, models)
    fp = FP.analysis_fingerprint()
    check("the fingerprint is 12 hex chars", len(fp) == 12 and all(c in "0123456789abcdef" for c in fp), True)
    saved = O.OCR_MIN_SCORE
    O.OCR_MIN_SCORE = 0.5
    FP._FINGERPRINT = ""
    check("changing OCR_MIN_SCORE changes the fingerprint", FP.analysis_fingerprint() != fp, True)
    check("changing OCR_MIN_SCORE changes the cache key", I.frame_key(frame, models) != key, True)
    O.OCR_MIN_SCORE = saved
    FP._FINGERPRINT = ""
    check("restoring the constant restores the fingerprint", FP.analysis_fingerprint(), fp)
    check("the cache key is stable", I.frame_key(frame, models), key)
    models["car_colour"] = None
    check("no colour tags leaves the cache key as it was", I.frame_key(frame, models),
          [VD.file_key(frame), VD.file_key(models["detector"]), I.ocr_key(models["ocr_det"], models["ocr_rec"]),
           I.embedder_key(models["embedder"]), fp, "ocr-trace-2", "read-conf-1", "pod-2", "cand-1", "overlap-2"])
    models["car_colour"] = C.PALETTE
    colour_key = I.frame_key(frame, models)
    check("colour tags add the palette to the cache key", colour_key[-2:], ["car-colour-1", C.palette_digest(C.PALETTE)])
    models["car_colour"] = (("Crimson", C.PALETTE[0][1]),) + tuple(C.PALETTE[1:])
    check("renaming a palette colour changes the cache key", I.frame_key(frame, models) != colour_key, True)
    models["car_colour"] = None
    models["segmenter"] = frame
    check("the segmenter model file joins the cache key", I.frame_key(frame, models)[-2:], ["mask-1", VD.file_key(frame)])
    del models["segmenter"]
    people = {"kind": "people", "face_det": frame, "face_rec": frame}
    check("the people key carries the fingerprint", FP.analysis_fingerprint() in I.frame_key(frame, people), True)
    check("the cache key carries no stray version", "1" not in I.IdentifyCache._key(["x"]), True)

    # ---- every per-frame constant is filed as a cache input or neutral
    for mod in FP.CACHE_INPUTS:
        tree = ast.parse(open(mod.__file__, encoding="utf-8").read())
        names = [t.id for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign))
                 for t in (node.targets if isinstance(node, ast.Assign) else [node.target])
                 if isinstance(t, ast.Name) and t.id.lstrip("_").isupper() and t.id != "__all__"]
        filed = FP.CACHE_INPUTS[mod] + FP.CACHE_NEUTRAL[mod]
        check(f"{mod.__name__}: every constant is filed once", sorted(n for n in names if filed.count(n) != 1), [])
        check(f"{mod.__name__}: nothing filed that does not exist", sorted(set(filed) - set(names)), [])

    # ---- shared detections: a frame analysed twice runs the detector once, the second read is the cached entry
    det_runs = []

    def fake_run(detector, canvas, scale, w, h):
        det_runs.append(w)
        return np.array([[0, 0, 32, 24, 0.1, 2]], dtype=np.float64).reshape(-1, 6)

    VD.FAMILIES["fake"] = {"match": lambda name: False, "load": None, "run": fake_run,
                           "classes": frozenset({2, 3, 7}), "nms": True}
    fake_det = VD.Detector(id="fake:x:1:abc", family="fake", net=None, classes=frozenset({2, 3, 7}))
    saved_w = dict(I._W)
    I._W.clear()
    I._W.update(models={"kind": "motorsport"}, detector=fake_det,
                detections=VD.DetectionCache(os.path.join(img, "detections.sqlite")))
    try:
        first = I.analyse_frame(frame)
        second = I.analyse_frame(frame)
    finally:
        I._W["detections"].close()
        I._W.clear()
        I._W.update(saved_w)
    check("analyse_frame runs the detector once for a frame analysed twice", len(det_runs), 1)
    check("the first analysis detected, the second read the cache",
          (first.pop("detection_cached", None), second.pop("detection_cached", None)), (False, True))
    check("the cached detection gives the same candidates", second["candidates"], first["candidates"])
    check("a box under DETECTOR_MIN_SCORE is a candidate, not a box",
          (first["boxes"], first["candidates"]), ([], [[0.0, 0.0, 32.0, 24.0, 0.1, 2]]))

    # ---- results rows
    check("a no-vehicle row", I.format_row("7", BoxResult(-1, "none")), "7,-1,none,,,0.000,,,,,")
    check("a team row carries the runner-up", I.format_row("7", BoxResult(0, "team", "VER", "TSU", 0.71234)),
          "7,0,team,VER,TSU,0.712,,,,,")
    check("a row has the shot type before the order flag", I.format_row("7", BoxResult(0, "number", "VER", "", 0.9), "pack"),
          "7,0,number,VER,,0.900,,pack,,,")
    check("a flagged row has 1 in the order flag", I.format_row("7", BoxResult(0, "number", "VER", "", 0.85, order_flag=True), "solo"),
          "7,0,number,VER,,0.850,,solo,1,,")
    check("a row ends with the colour and its flag",
          I.format_row("7", BoxResult(0, "number", "VER", "", 0.85, colour="Red", colour_flag=True), "solo").endswith(",Red,1"), True)
    check("a row with no colour ends with two empty fields", I.format_row("7", BoxResult(0, "none"), "solo").endswith(",,"), True)
    check("a row has eleven fields", len(I.format_row("7", BoxResult(0, "none"), "solo").split(",")), 11)

    # ---- Review Focus 2: EXIF-rotated frames
    rotated = os.path.join(img, "portrait.jpg")
    exif = Image.Exif()
    exif[0x0112] = 6  # stored landscape, displayed rotated 90° clockwise
    Image.new("RGB", (300, 200), (10, 120, 200)).save(rotated, exif=exif)
    rgb = VD.decode_rgb(rotated)
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
        I.check_models({"detector": fake, "ocr_det": fake, "ocr_rec": fake, "embedder": fake, "kind": "motorsport"})
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

    real = (I.check_models, I.Embedder, I.run_frames, I.refine_frames)
    I.check_models, I.Embedder = (lambda m: FakeEmbedder("fake")), FakeEmbedder
    I.run_frames = lambda paths, models, cache, progress: stub
    I.refine_frames = lambda wanted, analyses, models, cache, progress="": analyses  # the re-read needs real files
    results = os.path.join(img, "results.csv")
    args = Namespace(manifest=manifest, results=results, progress=os.path.join(img, "progress.txt"), cache="",
                     collections_root=root, collection=os.path.basename(coll), settings="", entries_out=os.path.join(img, "e.csv"),
                     rules_out=os.path.join(img, "r.csv"), boxes_out="", boxes_in="", report_out="", report_top=20, archive_dir="")
    I.identify(args, {"embedder": "fake"})
    rows = open(results, encoding="utf-8").read().splitlines()
    check("number reads, burst consensus and no-vehicle rows come out in manifest order (3-column manifest)", rows,
          ["1,0,number,VER,,0.950,,solo,,,", "2,0,number,VER,,0.900,,solo,,,", "3,0,burst,VER,,0.667,,solo,,,",
           "4,-1,none,,,0.000,,,,,", "5,-1,error,,,0.000,,,,,"])
    check("the run writes the collection's tag plan", os.path.isfile(os.path.join(coll, "tag-plan.txt")), True)
    check("the run writes rules.csv for the plugin", os.path.isfile(args.rules_out), True)

    _, shot_rules, _fe = I.load_collection(collection({"rules": {"diagnostics": {
        "shot_solo": "Mine|Solo", "shot_pack": "Mine|Pack", "shot_crowded": "Mine|Crowded"}}, "entries": [VER]}))
    check("old shot_* diagnostics sharing one base rename the shot tag",
          tuple(dict(shot_rules.diagnostics)[k] for k in ("shot_solo", "shot_pack", "shot_crowded")),
          ("Mine|Solo", "Mine|Pack", "Mine|Crowded"))
    _, shot_rules, _fe = I.load_collection(collection({"rules": {"diagnostics": {
        "shot_solo": "", "shot_pack": "", "shot_crowded": ""}}, "entries": [VER]}))
    check("old shot_* diagnostics all blank switch the shot tag off",
          tuple(dict(shot_rules.diagnostics)[k] for k in ("shot_solo", "shot_pack", "shot_crowded")), ("", "", ""))
    lines = []
    real_log, I.log = I.log, lines.append
    try:
        _, shot_rules, _fe = I.load_collection(collection({"rules": {"diagnostics": {
            "shot_pack": "Mine|Pack", "shot_solo": ""}}, "entries": [VER]}))
    finally:
        I.log = real_log
    check("old shot_* diagnostics with mixed bases log and keep the default shot tag",
          (dict(shot_rules.diagnostics)["shot_pack"], any("do not share one base" in ln for ln in lines)),
          (I.DIAG_DEFAULTS["shot_pack"], True))

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
          ["1,-1,skipped,,,0.000,,,,,", "2,0,conflict,VER,,0.900,,solo,,,", "6,0,number,VER,,0.950,,solo,,,",
           "7,0,number,VER,,0.950,,solo,,,", "8,0,conflict,VER,,0.667,,solo,,,", "9,0,number,VER,,0.950,,pack,,,",
           "9,1,none,,,0.000,,pack,,,"])
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
                      collections_root=root, collection=os.path.basename(coll), settings="", entries_out=args.entries_out,
                      rules_out=args.rules_out, boxes_out="", boxes_in=promo_boxes)
    write_promo([100, 50])
    I.promote_boxes(pargs, {"embedder": "fake"})
    check("promote adds a confident box", open(results, encoding="utf-8").read().strip(), "1,added,,VER")
    refs = sorted(os.listdir(os.path.join(coll, "refs")))
    check("only the wide-margin box became a reference", refs, ["VER"])
    I.promote_boxes(pargs, {"embedder": "fake"})
    check("promoting again replaces rather than duplicates", len(os.listdir(os.path.join(coll, "refs", "VER"))), 1)
    write_promo([10, 10])
    I.promote_boxes(pargs, {"embedder": "fake"})
    check("a file that no longer matches the run is stale", open(results, encoding="utf-8").read().strip(), "1,stale,,")

    # ---- add-time screening: refs flagged by 2+ audit checks are refused (skip) or kept with a log line (warn)
    import audit_refs
    write_promo([100, 50])
    real_screen = audit_refs.screen_refs
    audit_refs.screen_refs = lambda collection, rels: {r: ["outlier", "colour"] for r in rels}
    try:
        I.promote_boxes(pargs, {"embedder": "fake"})
        check("a promoted box the audit checks flag is not saved", open(results, encoding="utf-8").read().strip(), "1,flagged,,VER")
        check("a flagged box's crop is replaced by the sample it overwrote",
              os.listdir(os.path.join(coll, "refs", "VER")), ["1_b0.jpg"])
        audit_refs.screen_refs = lambda collection, rels: {r: ["outlier"] for r in rels}
        I.promote_boxes(pargs, {"embedder": "fake"})
        check("one flag alone does not refuse a box", open(results, encoding="utf-8").read().strip(), "1,added,,VER")
        kept = os.listdir(os.path.join(coll, "refs", "VER"))
        with open(os.path.join(coll, "refs", "VER", kept[0]), "rb") as f:
            before = f.read()
        write_promo([100, 50])
        audit_refs.screen_refs = lambda collection, rels: {r: ["outlier", "colour"] for r in rels}
        I.promote_boxes(pargs, {"embedder": "fake"})
        with open(os.path.join(coll, "refs", "VER", kept[0]), "rb") as f:
            check("a refused re-promote puts the earlier sample back", f.read() == before, True)
    finally:
        audit_refs.screen_refs = real_screen

    # ---- reference actions fill an entry's colour (rules.colour_tags)
    import entries_file
    real_detect, real_entry = I.detect_vehicles, I.frame_entry
    I.detect_vehicles = lambda rgb, entry: ([(0, 0, 50, 50)], "")
    I.frame_entry = lambda filepath, rgb, models: ({"frame": [rgb.shape[1], rgb.shape[0]], "boxes": []}, False)
    # refs cut from one crop pile up here; screening them is the block above's subject
    audit_refs.screen_refs = lambda collection, rels: {}
    vmodels = {"embedder": "fake", "detector": ""}
    ccoll = collection(entries_file.dump({"rules": {"colour_tags": True, "partial_references": True}, "entries": [VER, TSU]}), root=root)
    centries = os.path.join(ccoll, "entries.json")

    def ref_job(job, coll_dir, row, boxes_in="", colours_only=False):
        with open(manifest, "w", encoding="utf-8") as f:
            f.write(row + "\n")
        job(Namespace(manifest=manifest, results=results, progress=os.path.join(img, "p3.txt"), cache="",
                      collections_root=root, collection=os.path.basename(coll_dir), settings="", entries_out=args.entries_out,
                      rules_out=args.rules_out, boxes_out="", boxes_in=boxes_in, colours_only=colours_only), dict(vmodels))
        return open(results, encoding="utf-8").read().strip()

    try:
        before = open(os.path.join(coll, "entries.json"), encoding="utf-8").read()
        check("colour off: a hand colour gives no colour note", ref_job(I.add_references, coll, f'"1","{real_jpg}","VER","Red"'), "1,added,,VER")
        check("colour off: entries.json isn't written", open(os.path.join(coll, "entries.json"), encoding="utf-8").read(), before)

        before = open(centries, encoding="utf-8").read()
        check("a team reference gets no colour", ref_job(I.add_references, ccoll, f'"1","{real_jpg}","F1|Red Bull","Red"'), "1,added,,F1|Red Bull")
        check("a team reference leaves entries.json alone", open(centries, encoding="utf-8").read(), before)

        old_boxes = os.path.join(img, "old.boxes.json")
        with open(old_boxes, "w", encoding="utf-8") as f:
            json.dump({"collection": os.path.basename(ccoll), "skipped": [], "images": {"1": {
                "shot": "solo", "file": real_jpg, "frame": [100, 50], "boxes": [
                    {"box": 0, "bbox": [0, 0, 50, 50], "entry": "VER", "alt_entry": "", "method": "number",
                     "confidence": 0.95, "candidates": [], "ocr": [], "decided_by": "number", "gap": 0.0, "conflict": False}]}}}, f)
        check("an old boxes.json box without colour_shares is still added, with no colour",
              ref_job(I.promote_boxes, ccoll, f'"1","{real_jpg}",""', old_boxes), "1,added,,VER")
        check("an old boxes.json box leaves entries.json alone", open(centries, encoding="utf-8").read(), before)

        check("a hand colour on an entry without one is set", ref_job(I.add_references, ccoll, f'"1","{real_jpg}","VER","Red"'), "1,added,set,VER")
        check("entries.json gains the colour", json.load(open(centries, encoding="utf-8"))["entries"][0].get("colour"), "Red")
        check("a different reading of a coloured entry differs", ref_job(I.add_references, ccoll, f'"1","{real_jpg}","VER","Blue"'), "1,added,differs,VER")
        check("a differing reading leaves the colour", json.load(open(centries, encoding="utf-8"))["entries"][0].get("colour"), "Red")

        # --colours-only: the colour alone goes to entries.json, no reference is saved
        ocoll = collection(entries_file.dump({"rules": {"colour_tags": True}, "entries": [VER, TSU]}), root=root)
        oentries = os.path.join(ocoll, "entries.json")
        check("colours-only: a hand colour sets the entry and saves no reference",
              (ref_job(I.add_references, ocoll, f'"1","{real_jpg}","VER","Red"', colours_only=True),
               os.path.exists(os.path.join(ocoll, "refs", "VER"))), ("1,read,set,VER", False))
        check("colours-only: entries.json gains the colour", json.load(open(oentries, encoding="utf-8"))["entries"][0].get("colour"), "Red")
        os.remove(oentries + ".bak")
        before = open(oentries, "rb").read()
        check("colours-only: an entry with that colour is already",
              (ref_job(I.add_references, ocoll, f'"1","{real_jpg}","VER","Red"', colours_only=True),
               open(oentries, "rb").read() == before, os.path.exists(oentries + ".bak")), ("1,read,already,VER", True, False))
        I.detect_vehicles = lambda rgb, entry: ([], "no vehicle")
        check("colours-only: no vehicle is unread and saves nothing",
              (ref_job(I.add_references, ocoll, f'"1","{real_jpg}","TSU",""', colours_only=True),
               os.path.exists(os.path.join(ocoll, "refs", "TSU"))), ("1,unread,,TSU", False))
        I.detect_vehicles = lambda rgb, entry: ([(0, 0, 50, 50)], "")
        try:
            ref_job(I.add_references, coll, f'"1","{real_jpg}","VER","Red"', colours_only=True)
            off = "(no error)"
        except I.InputError as e:
            off = str(e)
        check("colours-only needs colour_tags", off, "Fill entry colours needs read car colour (colour_tags) on")
        pcoll = collection({"kind": "people", "rules": {"colour_tags": True}, "entries": [LH]}, root=root)
        try:
            ref_job(I.add_references, pcoll, f'"1","{real_jpg}","Lando Norris",""', colours_only=True)
            people = "(no error)"
        except I.InputError as e:
            people = str(e)
        check("colours-only refuses a people collection", people, "Fill entry colours is for vehicle collections")
        check("colours-only saves no face reference", os.path.isdir(os.path.join(pcoll, "refs", "Lando Norris")), False)
    finally:
        I.detect_vehicles, I.frame_entry = real_detect, real_entry
        audit_refs.screen_refs = real_screen

    # ---- Review Focus 4: cancel leaves no results
    os.remove(results)
    open(args.progress + ".cancel", "w").close()
    try:
        I.identify(args, {"embedder": "fake"})
        code = 0
    except SystemExit as e:
        code = e.code
    check("a cancelled run exits 130", code, 130)
    check("a cancelled run writes no results (nor leaves a temp file)",
          [n for n in os.listdir(os.path.dirname(results)) if n.startswith(os.path.basename(results))], [])
    I.check_models, I.Embedder, I.run_frames, I.refine_frames = real

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
    lines = []
    real_log, I.log = I.log, lines.append
    try:
        _, pr_rules, _fe = I.load_collection(collection({"rules": {"partial_references": "yes"}, "entries": [VER]}))
    finally:
        I.log = real_log
    check("a non-boolean partial_references in entries.json logs and keeps the default",
          (pr_rules.partial_references, "entries.json: rules.partial_references invalid, using False" in lines),
          (False, True))

    print("")
    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


# Worker processes re-import this file on spawn; only the parent runs the tests.
if __name__ == "__main__":
    try:
        run_tests()
    except Exception:
        # A crash stops the remaining checks, so say so in stdout with the traceback, not only on stderr.
        import traceback
        print("\nFAIL crashed before finishing; later checks did not run")
        print(traceback.format_exc())
        sys.exit(1)

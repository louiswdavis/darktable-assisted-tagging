# Run with: python python/test_identify.py
# Exercises identify.py's entries/rules loading, cache key, output and run flow,
# plus vehicle_detect.py's decode and vehicles.py's crop, on synthetic files; no models needed.

import ast
import json
import os
import re
import sys
import tempfile
from argparse import Namespace

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import car_colour as C
import fingerprint as FP
import identify as I
import siglip as S
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


# Only the team family is on, rooted at F1: VER and TSU build exactly the tags they list.
FIXTURE_SETTINGS = {"family_colour": False, "family_number": False, "family_driver": False, "family_co_driver": False, "family_extra": False,
                    "family_vehicle": False, "family_team_root": "F1"}
ALL_FAMILIES = {"colour": "Assisted Tagging|Motorsport|Colour", "number": "Assisted Tagging|Motorsport|Number", "team": "Assisted Tagging|Motorsport|Team",
                "driver": "Assisted Tagging|Motorsport|Driver", "co_driver": "Assisted Tagging|Motorsport|Co-driver", "extra": "Assisted Tagging|Motorsport|Class", "vehicle": "Assisted Tagging|Motorsport|Vehicle"}


def collection(data, root=None, settings=FIXTURE_SETTINGS) -> str:
    """A collection folder holding `data` as entries.json; settings=None writes no settings.json (the defaults)."""
    d = tempfile.mkdtemp(dir=root)
    with open(os.path.join(d, "entries.json"), "w", encoding="utf-8") as f:
        f.write(data if isinstance(data, str) else json.dumps(data))
    if settings is not None:
        with open(os.path.join(d, "settings.json"), "w", encoding="utf-8") as f:
            json.dump(settings, f)
    return d


def load_message(data, settings=FIXTURE_SETTINGS) -> tuple:
    d = collection(data, settings=settings)
    try:
        I.load_collection(d)
    except I.InputError as e:
        return d, str(e)
    return d, "(no error)"


def load_error(data, settings=FIXTURE_SETTINGS) -> str:
    d, msg = load_message(data, settings)
    if msg == "(no error)":
        return msg
    return msg[len(os.path.join(d, "entries.json")) + 2:] if msg.startswith(os.path.join(d, "entries.json")) \
        else "(message doesn't start with the file path) " + msg


def settings_error(data, settings) -> str:
    """The whole message of an error that names settings.json or entries.json itself, not the file path."""
    return load_message(data, settings)[1]


def run_tests():
    # ---- loading entries.json
    entries, rules, _fe = I.load_collection(collection([VER, TSU]))
    check("a bare list loads entries in file order", list(entries), ["VER", "TSU"])
    check("an int number is read as text", entries["TSU"].number, "22")
    check("a bare list gets the default rules", rules, I.Rules(families={"team": "F1"}))
    entries, rules, _fe = I.load_collection(collection({"rules": {"team_only": "none", "unidentified": ["F1|Check"],
                                                             "diagnostics": {"burst": "", "team": "X|Team"}},
                                                   "entries": [VER]}))
    check("rules: team_only", rules.team_only, "none")
    check("rules: unidentified tags", rules.unidentified, ("F1|Check",))
    check("rules: renamed, dropped and default diagnostics", dict(rules.diagnostics),
          dict(I.DIAG_DEFAULTS, burst="", team="X|Team"))
    check("default diagnostics sit under Assisted Tagging|Motorsport",
          all(v.startswith("Assisted Tagging|Identification|") for k, v in I.DIAG_DEFAULTS.items()), True)

    check("duplicate id is rejected", load_error([VER, VER]), 'entry "VER" appears twice')
    check("a comma in a tag is rejected", load_error([dict(VER, tags=["a,b"])]),
          'entry "VER": tags: tag "a,b" can\'t contain , ; or "')
    check("a non-digit number is rejected", load_error([dict(VER, number="1a")]), 'entry "VER": number must be 1–3 digits')
    check("a shows list loads as a tuple", I.load_collection(collection([dict(VER, shows=["44", "44"])]))[0]["VER"].shows,
          ("44",))
    check("a paddock field is accepted", I.load_collection(collection([dict(VER, paddock="H3")]))[0]["VER"].id, "VER")
    check("a non-list shows is rejected", load_error([dict(VER, shows="44")]),
          'entry "VER": shows must be a list of 1–3 digit numbers, e.g. ["44"]')
    check("a non-digit shown number is rejected", load_error([dict(VER, shows=["4a"])]),
          'entry "VER": shows must be a list of 1–3 digit numbers, e.g. ["44"]')
    check("shows can't repeat the entry's own number", load_error([dict(VER, shows=["1"])]),
          'entry "VER": shows repeats its own number 1')
    check("empty tags load when families build tags", load_error([dict(VER, tags=[])]), "(no error)")
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
          'unknown rule "team_onyl" (rules are team_only, unidentified, sponsor_keywords, sponsor_names, colour_palette; '
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
          'entry "VER": unknown field "tagz" (fields are id, number, team, name, co_driver, extra, make, model, tags, camera, colour, car, shows, paddock)')
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

    # ---- tag families build an entry's tags from its number, team and name
    LEC = {"id": "12", "number": "12", "team": "Ferrari", "name": "Leclerc"}
    entries, rules, _fe = I.load_collection(collection([LEC, dict(VER, name="Max")], settings=None))
    check("families: every family is on by default", rules.families, ALL_FAMILIES)
    check("families: number, team, then driver", entries["12"].tags,
          ("Assisted Tagging|Motorsport|Number|12", "Assisted Tagging|Motorsport|Team|Ferrari", "Assisted Tagging|Motorsport|Driver|Leclerc"))
    check("families: the entry's own tags follow as extras", entries["VER"].tags,
          ("Assisted Tagging|Motorsport|Number|1", "Assisted Tagging|Motorsport|Team|Red Bull", "Assisted Tagging|Motorsport|Driver|Max", "F1|Red Bull", "F1|Red Bull|Verstappen"))
    entries, _, _fe = I.load_collection(collection(
        [dict(LEC, tags=["Extra|Champion", "Assisted Tagging|Motorsport|Team|Ferrari"])], settings=None))
    check("families: an extra that repeats a built tag is listed once", entries["12"].tags,
          ("Assisted Tagging|Motorsport|Number|12", "Assisted Tagging|Motorsport|Team|Ferrari", "Assisted Tagging|Motorsport|Driver|Leclerc", "Extra|Champion"))
    AMES, COLE = {"id": "30", "number": "30", "name": "Ames"}, {"id": "730", "number": "730", "name": "Cole", "car": "30"}
    entries, _, _fe = I.load_collection(collection([AMES, COLE], settings=None))
    union = ("Assisted Tagging|Motorsport|Number|30", "Assisted Tagging|Motorsport|Driver|Ames", "Assisted Tagging|Motorsport|Number|730", "Assisted Tagging|Motorsport|Driver|Cole")
    check("car: both entries of a shared car get the union of tags, the named entry's first",
          (entries["30"].tags, entries["730"].tags), (union, union))
    check("car: both entries carry the named id", (entries["30"].car, entries["730"].car), ("30", "30"))
    check("car: naming a missing id fails", load_error([AMES, dict(COLE, car="31")], settings=None),
          'entry "730": car "31" is not an entry id')
    check("car: naming itself fails", load_error([AMES, dict(COLE, car="730")], settings=None), 'entry "730": car names itself')
    check("car: naming an entry that names a car fails",
          load_error([dict(AMES, car="5"), {"id": "5", "number": "5"}, COLE], settings=None),
          'entry "730": car "30" names another car itself; name the lower entry of the pair')
    check("car: three entries in one car fail", load_error([AMES, COLE, {"id": "830", "number": "830", "car": "30"}], settings=None),
          'entries "730" and "830" both share car "30"; a car has two entries at most')
    entries, rules, _fe = I.load_collection(collection([LEC], settings={"family_team": False}))
    check("families: team off drops the team tag", entries["12"].tags, ("Assisted Tagging|Motorsport|Number|12", "Assisted Tagging|Motorsport|Driver|Leclerc"))
    check("families: team off leaves it out of rules.families", "team" in rules.families, False)
    entries, rules, _fe = I.load_collection(collection([LEC], settings={
        "family_number_root": "Rally|2026|Number", "family_team_root": "Rally|2026|Team", "family_driver": False,
        "family_colour_root": "Rally|Colour"}))
    check("families: roots come from settings.json", entries["12"].tags, ("Rally|2026|Number|12", "Rally|2026|Team|Ferrari"))
    check("families: the colour root is read", rules.families["colour"], "Rally|Colour")
    check("families: an empty root is the default",
          I.load_collection(collection([LEC], settings={"family_team_root": ""}))[1].families["team"], "Assisted Tagging|Motorsport|Team")
    check("families: a root of spaces names the setting", settings_error([LEC], {"family_team_root": "  "}),
          "settings.json: family_team_root is empty")
    check("families: an entry that builds no tag is rejected",
          load_error([{"id": "12", "number": "12"}], {"family_number": False}),
          'entry "12": builds no tag; turn on a family it has a value for, or give it tags')
    check("families: an entry with nothing at all is rejected", load_error([{"id": "X"}], None),
          'entry "X": builds no tag; turn on a family it has a value for, or give it tags')
    check("families: a numbers-only entry needs no tags", I.load_collection(
        collection([{"id": "12", "number": "12"}], settings=None))[0]["12"].tags, ("Assisted Tagging|Motorsport|Number|12",))
    check("families: a root with a comma names the setting", settings_error([LEC], {"family_team_root": "A,B"}),
          'settings.json: family_team_root can\'t contain , ; or "')
    check("families: a root ending in | names the setting", settings_error([LEC], {"family_number_root": "F1|"}),
          "settings.json: family_number_root can't start or end with | or a space")
    check("families: one root under another names both settings",
          settings_error([LEC], {"family_number_root": "Cars", "family_team_root": "Cars|Team"}),
          'settings.json: family_number_root ("Cars") and family_team_root ("Cars|Team") overlap; '
          'each family needs its own root')
    check("families: a switched-off family's root isn't checked", I.load_collection(collection(
        [LEC], settings={"family_number_root": "Cars", "family_team_root": "Cars|Team", "family_team": False}))[0]["12"].tags,
        ("Cars|12", "Assisted Tagging|Motorsport|Driver|Leclerc"))
    RALLY = {"id": "7", "number": "7", "name": "Smith", "co_driver": "Jones"}
    check("co-driver: own tag after the driver's", I.load_collection(collection([RALLY], settings=None))[0]["7"].tags,
          ("Assisted Tagging|Motorsport|Number|7", "Assisted Tagging|Motorsport|Driver|Smith",
           "Assisted Tagging|Motorsport|Co-driver|Jones"))
    check("co-driver: family off, no tag", I.load_collection(collection(
        [RALLY], settings={"family_co_driver": False}))[0]["7"].tags,
          ("Assisted Tagging|Motorsport|Number|7", "Assisted Tagging|Motorsport|Driver|Smith"))
    check("co-driver: ; rejected", load_error([dict(RALLY, co_driver="Jo;nes")], None),
          'entry "7": co_driver must be text without , ; or "')
    ESC = {"id": "7", "number": "7", "extra": "A1", "make": "Ford", "model": "Escort"}
    check("vehicle: make+model, extra: class", I.load_collection(collection([ESC], settings=None))[0]["7"].tags,
          ("Assisted Tagging|Motorsport|Number|7", "Assisted Tagging|Motorsport|Class|A1", "Assisted Tagging|Motorsport|Vehicle|Ford|Escort"))
    check("vehicle: make only", I.load_collection(collection(
        [{"id": "7", "number": "7", "make": "Ford"}], settings=None))[0]["7"].tags,
          ("Assisted Tagging|Motorsport|Number|7", "Assisted Tagging|Motorsport|Vehicle|Ford"))
    check("vehicle: model without make", load_error([{"id": "7", "number": "7", "model": "Escort"}], None),
          'entry "7": model Escort has no make')
    check("vehicle: make with | rejected", load_error([dict(ESC, make="Ford|Escort", model="")], None),
          'entry "7": make must be text without , ; " or |')
    check("extra: not text rejected", load_error([dict(ESC, extra=1)], None),
          'entry "7": extra must be text without , ; " or |')
    check("families: vehicle off, no vehicle tag", I.load_collection(collection(
        [ESC], settings={"family_vehicle": False}))[0]["7"].tags, ("Assisted Tagging|Motorsport|Number|7", "Assisted Tagging|Motorsport|Class|A1"))
    check("vehicle: custom root", I.load_collection(collection(
        [ESC], settings={"family_vehicle_root": "Cars"}))[0]["7"].tags,
          ("Assisted Tagging|Motorsport|Number|7", "Assisted Tagging|Motorsport|Class|A1", "Cars|Ford|Escort"))
    old = {"id": "7", "number": "7", "tags": ["Motorsport|Vehicle|Ford|Escort"]}
    old_dir = collection([old], settings=None)
    check("load: old vehicle tag upgraded", I.load_collection(old_dir)[0]["7"].tags,
          ("Assisted Tagging|Motorsport|Number|7", "Assisted Tagging|Motorsport|Vehicle|Ford|Escort"))
    with open(os.path.join(old_dir, "entries.json"), encoding="utf-8") as f:
        check("load: the upgraded file holds make and model", json.load(f),
              [{"id": "7", "number": "7", "make": "Ford", "model": "Escort"}])
    check("load: an upgraded vehicle follows the configured root", I.load_collection(collection(
        [old], settings={"family_vehicle_root": "Cars"}))[0]["7"].tags, ("Assisted Tagging|Motorsport|Number|7", "Cars|Ford|Escort"))
    check("load: an upgrade conflict names the entry", load_error([dict(old, make="Opel")], None),
          'entry "7": make "Opel" disagrees with tag "Motorsport|Vehicle|Ford|Escort"')
    latin = collection('', settings=None)
    with open(os.path.join(latin, "entries.json"), "wb") as f:
        f.write('[{"id": "7", "number": "7", "name": "José"}]'.encode("latin-1"))
    try:
        I.load_collection(latin)
        latin_msg = "(no error)"
    except I.InputError as e:
        latin_msg = str(e)
    check("load: a non-UTF-8 file still says not valid JSON", "not valid JSON" in latin_msg, True)
    only_new = {"family_colour": False, "family_number": False, "family_team": False, "family_driver": False}
    check("families: extra only, entry without extra builds no tag",
          load_error([{"id": "12", "number": "12"}], only_new),
          'entry "12": builds no tag; turn on a family it has a value for, or give it tags')
    check("rules.tag_prefix is removed and names the family roots",
          load_error({"rules": {"tag_prefix": "Motorsport|F1"}, "entries": [LEC]}),
          'rules.tag_prefix was removed; set family_number_root, family_team_root and family_driver_root '
          'in settings.json (README, "Tag families")')
    check("people: no families, the entry's tags only",
          I.load_collection(collection({"kind": "people", "entries": [LH]}, settings=None))[1].families, {})
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
    # ---- the colour family
    d_rules = I.load_collection(collection([VER], settings={"family_colour": False}))[1]
    check("family_colour off: no colour family", "colour" in d_rules.families, False)
    d_csv = os.path.join(tempfile.mkdtemp(), "d.csv")
    I.write_rules_csv(d_rules, (), d_csv)
    d_lines = open(d_csv, encoding="utf-8").read().splitlines()
    check("family_colour off: rules.csv has no family_colour line", [x for x in d_lines if x.startswith("family_colour,")], [])
    check("family_colour off: the other families are still written", "family_team,Assisted Tagging|Motorsport|Team" in d_lines, True)
    check("no diag_colour line is written", [x for x in d_lines if x.startswith("diag_colour,")], [])
    on_rules = I.load_collection(collection([VER], settings=None))[1]
    I.write_rules_csv(on_rules, (), d_csv)
    check("the colour family is on by default: rules.csv has its root",
          "family_colour,Assisted Tagging|Motorsport|Colour" in open(d_csv, encoding="utf-8").read().splitlines(), True)
    for old, new in (("colour_tags", "family_colour"), ("tag_colour", "family_colour"), ("tag_colour_name", "family_colour_root")):
        check(f"settings.json: removed {old} stops the load", settings_error([VER], {old: True}),
              f'settings.json: {old} was removed; use {new} (README, "Tag families")')
    check("entries.json: removed rules.colour_tags stops the load",
          settings_error({"rules": {"colour_tags": True}, "entries": [VER]}, None),
          'entries.json: rules.colour_tags was removed; use family_colour in settings.json (README, "Tag families")')
    blue = dict(C.PALETTE)["Blue"]
    check("default palette is the built-in one", I.load_collection(collection([VER]))[1].colour_palette, C.PALETTE)
    _, navy, _fe = I.load_collection(collection({"rules": {"colour_palette": {"Navy": "Blue"}}, "entries": [VER]}))
    check("a built-in name renames and drops the rest", navy.colour_palette, (("Navy", blue),))
    _, custom, _fe = I.load_collection(collection({"rules": {"colour_palette": {"Teal": [
        {"hue": [80, 95], "sat": [60, 255], "val": [40, 255]}, {"hue": [96, 100]}]}}, "entries": [VER]}))
    check("bounds objects map to 6-tuples, missing sat/val is full range", custom.colour_palette,
          (("Teal", ((80, 95, 60, 255, 40, 255), (96, 100, 0, 255, 0, 255))),))
    for bad_palette in ({"Multi": "Red"}, {"Red": "Teal"}, {"Red": [{"hue": [9, 3]}]}, {"Red": [{"hue": [0, 300]}]},
                        {"A|B": "Red"}, {}, {"Red": []}):
        check(f"colour_palette {bad_palette!r} is rejected",
              "colour_palette" in load_error({"rules": {"colour_palette": bad_palette}, "entries": [VER]}), True)
    entries, _, _fe = I.load_collection(collection([dict(VER, colour="Red"), dict(TSU, colour="Multi")]))
    check("entry colour is read", (entries["VER"].colour, entries["TSU"].colour), ("Red", "Multi"))
    check("entry colour defaults empty", I.load_collection(collection([VER]))[0]["VER"].colour, "")
    msg = load_error([dict(VER, colour="Teal")])
    check("unknown entry colour names the entry and colour", 'entry "VER"' in msg and "Teal" in msg, True)
    msg = load_error({"rules": {"colour_palette": {"Red": "Red"}}, "entries": [dict(VER, colour="Blue")]})
    check("entry colour outside the palette names the entry and colour", 'entry "VER"' in msg and "Blue" in msg, True)
    check("entries.json: removed rules.diagnostics.colour stops the load",
          settings_error({"rules": {"diagnostics": {"colour": "Rally|Colour"}}, "entries": [VER]}, None),
          'entries.json: rules.diagnostics.colour was removed; use family_colour_root in settings.json (README, "Tag families")')

    # ---- csv outputs and the tag plan
    entries, rules, _fe = I.load_collection(collection({"rules": {"unidentified": ["F1|Check"]},
                                                   "entries": [VER, TSU, {"id": "SC", "tags": ["F1|Safety Car"]}]}))
    out = tempfile.mkdtemp()
    I.write_entries_csv(entries, os.path.join(out, "e.csv"))
    I.write_rules_csv(rules, _fe, os.path.join(out, "r.csv"))
    check("entries.csv rows", open(os.path.join(out, "e.csv"), encoding="utf-8").read().splitlines()[1],
          "TSU,Red Bull,22,F1|Red Bull;F1|Red Bull|Tsunoda,,,,")
    name_entries = I.load_collection(collection([dict(VER, name="Max Verstappen", co_driver="Gianpiero Lambiase")]))[0]
    I.write_entries_csv(name_entries, os.path.join(out, "n.csv"))
    check("entries.csv ends with the name and co-driver", open(os.path.join(out, "n.csv"), encoding="utf-8").read().splitlines()[0],
          "VER,Red Bull,1,F1|Red Bull;F1|Red Bull|Verstappen,Max Verstappen,Gianpiero Lambiase,,")
    car_entries = I.load_collection(collection([AMES, COLE], settings=None))[0]
    I.write_entries_csv(car_entries, os.path.join(out, "c.csv"))
    check("entries.csv ends with the shared car's id on both entries",
          [line.rsplit(",", 1)[1] for line in open(os.path.join(out, "c.csv"), encoding="utf-8").read().splitlines()], ["30", "30"])
    check("rules.csv rows", open(os.path.join(out, "r.csv"), encoding="utf-8").read().splitlines()[:3],
          ["team_only,shared tags", "unidentified,F1|Check", "diag_number,Assisted Tagging|Identification|By number"])
    rows = open(os.path.join(out, "r.csv"), encoding="utf-8").read().splitlines()
    check("rules.csv ends with from_entries_json, empty here", rows[-1], "from_entries_json,")
    check("rules.csv lists each family that is on", [x for x in rows if x.startswith("family_")], ["family_team,F1"])
    entries, rules, fe = I.load_collection(collection({"rules": {"order_weight": 0.5}, "entries": [VER]}))
    I.write_rules_csv(rules, fe, os.path.join(out, "r2.csv"))
    text = open(os.path.join(out, "r2.csv"), encoding="utf-8").read()
    check("rules_csv_has_moved_keys", all(x in text.splitlines() for x in (
        "order_weight,0.5", "neighbour_tolerance,5", "from_entries_json,order_weight")), True)
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
    saved = V.HIRES_MIN_GAIN
    V.HIRES_MIN_GAIN = saved + 0.1
    FP._FINGERPRINT = ""
    check("changing HIRES_MIN_GAIN changes the cache key", I.frame_key(frame, models) != key, True)
    V.HIRES_MIN_GAIN = saved
    FP._FINGERPRINT = ""
    models["car_colour"] = None
    check("no colour tags leaves the cache key as it was", I.frame_key(frame, models),
          [VD.file_key(frame), VD.file_key(models["detector"]), I.ocr_key(models["ocr_det"], models["ocr_rec"]),
           I.embedder_key(models["embedder"]), fp, "ocr-trace-2", "read-conf-1", "ctc-1", "pod-2", "cand-1", "overlap-2"])
    models["car_colour"] = C.PALETTE
    colour_key = I.frame_key(frame, models)
    check("colour tags add the palette to the cache key", colour_key[-2:], ["car-colour-2", C.palette_digest(C.PALETTE)])
    models["car_colour"] = (("Crimson", C.PALETTE[0][1]),) + tuple(C.PALETTE[1:])
    check("renaming a palette colour changes the cache key", I.frame_key(frame, models) != colour_key, True)
    models["car_colour"] = None
    models["segmenter"] = frame
    check("the segmenter model file joins the cache key", I.frame_key(frame, models)[-2:], ["mask-1", VD.file_key(frame)])
    del models["segmenter"]
    plain_key = I.frame_key(frame, models)
    models["siglip"] = frame
    check("SigLIP 2 joins the cache key with its three files", I.frame_key(frame, models)[len(plain_key):],
          S.siglip_key(frame))
    check("the SigLIP key names the token and every file", (S.siglip_key(frame)[0], len(S.siglip_key(frame))),
          (S.SIGLIP_CACHE_TOKEN, 5))
    siglip_frame_key = I.frame_key(frame, models)
    models["number_gate"] = True
    check("the number gate joins the cache key with its own token and constants", I.frame_key(frame, models)[len(siglip_frame_key):],
          S.number_gate_key())
    models["number_gate"] = False
    check("number_gate off leaves the cache key as it was", I.frame_key(frame, models), siglip_frame_key)
    del models["siglip"]
    models["number_gate"] = True
    check("the number gate without SigLIP 2 leaves the cache key as it was", I.frame_key(frame, models), plain_key)
    del models["number_gate"]
    check("no SigLIP leaves the cache key as it was", I.frame_key(frame, models), plain_key)
    with open(os.path.splitext(frame)[0] + ".json", "w", encoding="utf-8") as f:
        f.write("{}")
    models["ocr_second"] = frame
    check("the second reader joins the cache key with its token, model and .json",
          I.frame_key(frame, models)[len(plain_key):], ["second-reader-1", *O.parseq_key(frame)])
    models["ocr_second"] = ""
    check("no second reader leaves the cache key as it was", I.frame_key(frame, models), plain_key)
    del models["ocr_second"]
    # ticket 76: the model files are read once per process, the frame's own file every time
    model_file = os.path.join(img, "model.onnx")
    Image.new("RGB", (8, 8), (1, 2, 3)).save(model_file, "PNG")
    once = {**{k: model_file for k in ("detector", "ocr_det", "ocr_rec", "embedder")}, "kind": "motorsport"}
    once_key = I.frame_key(frame, once)
    os.utime(model_file, (1, 1))
    check("a model file touched mid-run keeps its key", I.frame_key(frame, once), once_key)
    I._MODEL_KEYS.clear()
    check("the next run reads the model files again", I.frame_key(frame, once) != once_key, True)
    once_key = I.frame_key(frame, once)
    os.utime(frame, (1, 1))
    check("a frame file touched mid-run changes its key", I.frame_key(frame, once) != once_key, True)
    check("SigLIP files sit beside the vision file", S.siglip_files("m/siglip2_base_vision.onnx"),
          ("m/siglip2_base_vision.onnx", "m/siglip2_base_text.onnx", "m/siglip2_base_tokenizer.json"))
    check("custom palette names are the colour prompts", S.colour_prompts((("Teal", ()),)),
          {"Teal": "a photo of a teal rally car.", C.MULTI: S.MULTI_PROMPT})

    # ---- a masked crop's GREY fill never reads as the car's colour (HSV, histogram, SigLIP 2)
    from colour import colour_hist
    from segment import GREY
    half = np.full((40, 40, 3), GREY, dtype=np.uint8)
    half[:, :20] = (200, 20, 20)
    red = np.full((40, 40, 3), (200, 20, 20), dtype=np.uint8)
    old_siglip = I._W.get("siglip")
    I._W["siglip"] = None
    shares = I.colour_read(half, C.PALETTE, masked=True)
    check("a half-GREY masked crop of a red car reads Red", max(shares, key=shares.get), "Red")
    check("the masked histogram matches the plain red crop's",
          bool(np.allclose(colour_hist(half, masked=True), colour_hist(red))), True)

    class FillSigLIP:
        """Records the crop it embeds."""
        def embed_image(self, crop):
            self.seen = crop
            return None

        def colour_scores(self, vec, palette):
            return {}

    I._W["siglip"] = fake = FillSigLIP()
    I.colour_read(half, C.PALETTE, masked=True)
    check("SigLIP 2 sees the GREY fill painted the kept colour", bool((fake.seen == red).all()), True)
    check("the caller's crop is left as it was", int((half == GREY).all(axis=2).sum()), 40 * 20)
    I._W["siglip"] = old_siglip

    # ---- the hires re-read takes the preview size from the analysis and reads only the wanted boxes
    class CountingReader:
        """Counts crops read; every read is empty."""
        last_trace, last_ctc, calls = [], [], 0
        keep_regions, last_regions, last_turns = False, [], {}
        second, last_second = None, {}

        def read(self, crop):
            self.calls += 1
            return []

    class OneEmbedder:
        def embed(self, crop):
            return np.ones(4, dtype=np.float32)

    saved_w, real_hires = dict(I._W), I.load_hires
    I._W.clear()
    I._W.update(reader=CountingReader(), embedder=OneEmbedder(), models={"kind": "motorsport"})
    # load_hires is the RAW decoder (rawpy needs a real camera file); hires_frame around it runs for real
    I.load_hires = lambda path: np.zeros((200, 300, 3), dtype=np.uint8)
    two = [[0, 0, 40, 40, 0.9, 2], [60, 0, 100, 40, 0.9, 2]]
    read = I.hires_frame(("/x/1.cr3", two, [100, 66], [1]))
    check("the hires re-read reads only the wanted box", (I._W["reader"].calls, read["ocr"][0], read["ocr"][1]),
          (1, None, []))
    check("the hires re-read keeps the per-box list shape", (len(read["emb"]), read["pod"]), (2, [None, None]))
    check("a decode not wide enough over the analysis frame isn't re-read",
          I.hires_frame(("/x/1.cr3", two, [250, 166], [1])), {})
    check("the wanted boxes join the hires key", I.hires_key(two, [1]) != I.hires_key(two, [0, 1]), True)
    I.load_hires = real_hires
    I._W.clear()
    I._W.update(saved_w)

    # ---- rescue reads are cached: an unchanged re-run decodes nothing, a new mate re-runs
    class CountingPool:
        """Stands in for WorkerPool: submit runs the job inline and counts it."""
        jobs = 0

        def get(self):
            return self

        def submit(self, fn, job):
            import concurrent.futures
            self.jobs += 1
            fut = concurrent.futures.Future()
            try:
                fut.set_result(fn(job))
            except Exception as e:
                fut.set_exception(e)
            return fut

    # real plan_burst, rescue_frame and cache keys over real files; only the models are stand-ins
    burst_dir = tempfile.mkdtemp()
    shots = [os.path.join(burst_dir, f"{n}.jpg") for n in (1, 2, 3)]
    for p in shots:
        Image.new("RGB", (64, 48), (90, 90, 90)).save(p)
    car_box = [2, 2, 50, 40, 0.9, 2]
    one = encode(np.ones(4, dtype=np.float32))
    rescue_rows = [[str(n), p, "b", "", "", str(n), ""] for n, p in enumerate(shots, 1)]
    saved_w = dict(I._W)
    I._W.clear()
    I._W.update(models={"kind": "motorsport"}, reader=CountingReader(), embedder=OneEmbedder(), siglip=None)
    rescue_db = os.path.join(tempfile.mkdtemp(), "cache.sqlite")
    counts = []
    try:
        for mate_has_car in ([True, True], [True, True], [False, True]):  # the last run loses shot 1's car → mate is 3
            rescue_an = {shots[1]: {"boxes": [], "candidates": [[3, 3, 49, 39, 0.1, 2]], "emb": []}}
            for p, has_car in zip((shots[0], shots[2]), mate_has_car):
                rescue_an[p] = {"boxes": [car_box] if has_car else [], "emb": [one] if has_car else []}
            pool, cache = CountingPool(), I.IdentifyCache(rescue_db)
            got = I.rescue_frames(rescue_rows, rescue_an, models, cache, pool)
            cache.close()
            counts.append((pool.jobs, got[shots[1]]["rescued"]["from"], len(got[shots[1]]["boxes"])))
        # ticket 76: a frame that can't be decoded is left as it was; the other bursts' rescues still land
        mate, broken = os.path.join(burst_dir, "c1.jpg"), os.path.join(burst_dir, "c2.jpg")
        Image.new("RGB", (64, 48), (90, 90, 90)).save(mate)
        with open(broken, "wb") as f:
            f.write(b"not a jpeg")
        rescue_an[mate] = {"boxes": [car_box], "emb": [one]}
        rescue_an[broken] = {"boxes": [], "candidates": [[3, 3, 49, 39, 0.1, 2]], "emb": []}
        pool, cache = CountingPool(), I.IdentifyCache(rescue_db)
        got = I.rescue_frames(rescue_rows + [["8", mate, "c", "", "", "1", ""], ["9", broken, "c", "", "", "2", ""]],
                              rescue_an, models, cache, pool)
        broken_job = (broken, (3, 3, 49, 39, 0.1, 2), mate, one)
        failed_rescue = (pool.jobs, got[broken]["boxes"], got[shots[1]]["rescued"]["from"],
                         cache.get(*I.rescue_key(broken_job, models)))
        cache.close()
    finally:
        I._W.clear()
        I._W.update(saved_w)
    check("rescue: first run decodes, an unchanged re-run reads the cache, a new mate re-runs", counts,
          [(1, "1.jpg", 1), (0, "1.jpg", 1), (1, "3.jpg", 1)])
    check("rescue: a frame that fails to decode stays no vehicle and uncached, the rest are rescued", failed_rescue,
          (1, [], "3.jpg", None))

    # ---- ticket 76: the cache is in WAL mode, has an index on `used`, and only a pruning connection drops old entries
    import sqlite3
    aged_db = os.path.join(tempfile.mkdtemp(), "cache.sqlite")
    aged = I.IdentifyCache(aged_db)
    aged.put({"n": 1}, "old")
    aged.put({"n": 2}, "new")
    aged.db.execute("UPDATE frames SET used = 0 WHERE key = ?", (aged._key(["old"]),))
    check("the cache journal is WAL", aged.db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
    check("the cache has an index on used",
          [r[1] for r in aged.db.execute("PRAGMA index_list(frames)") if r[1] == "frames_used"], ["frames_used"])
    aged.close()
    later = I.IdentifyCache(aged_db)
    check("a later stage's connection keeps an old entry", later.get("old"), {"n": 1})
    later.used = []  # the read above would refresh the entry's age on close
    later.close()
    first = I.IdentifyCache(aged_db, prune=True)
    check("the run's first connection prunes it and keeps the fresh one", (first.get("old"), first.get("new")), (None, {"n": 2}))
    first.close()

    # the shared detection cache: the same journal and index, and only the parent's pruning connection drops old rows
    aged_det = os.path.join(tempfile.mkdtemp(), "detections.sqlite")
    worker_det = VD.DetectionCache(aged_det)
    worker_det.put({"boxes": [1]}, "old")
    worker_det.put({"boxes": [2]}, "new")
    worker_det.db.execute("UPDATE detections SET used = 0 WHERE key = 'old'")
    worker_det.db.commit()
    check("the detection cache journal is WAL and has an index on used",
          (worker_det.db.execute("PRAGMA journal_mode").fetchone()[0],
           [r[1] for r in worker_det.db.execute("PRAGMA index_list(detections)") if r[1] == "detections_used"]),
          ("wal", ["detections_used"]))
    worker_det.close()
    later_det = VD.DetectionCache(aged_det)
    check("a worker's detection cache connection keeps an old row", later_det.get("old"), {"boxes": [1]})
    later_det.used = []  # the read above would refresh the row's age on close
    later_det.close()
    parent_det = VD.DetectionCache(aged_det, prune=True)
    check("the parent's connection prunes it and keeps the fresh one",
          (parent_det.get("old"), parent_det.get("new")), (None, {"boxes": [2]}))
    parent_det.close()

    # ---- cancel stops a worker mid-frame instead of waiting for it
    import concurrent.futures
    import time
    slow = I.WorkerPool({})
    slow.executor = concurrent.futures.ProcessPoolExecutor(max_workers=1)
    slow.executor.submit(time.sleep, 0).result()  # the worker is up
    slow.executor.submit(time.sleep, 30)
    time.sleep(0.5)
    started = time.time()
    with slow:
        slow.cancel()
    check("cancel ends a run with a 30 s frame in flight in under 2 s", time.time() - started < 2, True)

    # ---- the box check: non-car boxes are dropped and counted; no SigLIP keeps every box
    class FakeSigLIP:
        """Answers one label per crop, in call order; a crop's vector is its call number."""
        def __init__(self, answers):
            self.answers, self.calls = answers, 0

        def embed_image(self, crop):
            self.calls += 1
            return self.calls - 1

        def is_what(self, vec):
            return self.answers[vec]

    boxes = [(0, 0, 10, 10, 0.5), (0, 0, 20, 10, 0.5), (0, 0, 30, 10, 0.5), (0, 0, 20, 5, 0.5), (0, 0, 9, 9, 0.84)]
    canvas = np.zeros((40, 40, 3), dtype=np.uint8)
    old_siglip = I._W.get("siglip")
    I._W["siglip"] = None
    check("no SigLIP keeps every box", I.check_boxes(canvas, boxes), (boxes, None, {}, []))
    I._W["siglip"] = FakeSigLIP([("person", 0.1), ("car", 0.9), ("railing", 0.2), ("person", 0.05), ("person", 0.1)])
    kept, vecs, dropped, contested = I.check_boxes(canvas, boxes)
    I._W["siglip"] = old_siglip
    check("the box check keeps the car, and a low-share box the detector scored high",
          (kept, vecs), ([(0, 0, 20, 10, 0.5), (0, 0, 9, 9, 0.84)], [1, 4]))
    check("the box check counts dropped boxes per answer", dropped, {"person": 2, "railing": 1})
    check("contested boxes carry answer, share, score and why kept", contested[-1],
          {"answer": "person", "share": 0.1, "score": 0.84, "kept": "score"})
    check("a clear car is not contested", len(contested), 4)

    # ---- Add references' box: the entry's number read, else the largest car, else the largest box
    class ListReader:
        """Answers one list of reads per crop, in call order."""
        def __init__(self, answers):
            self.answers, self.calls = answers, 0

        def read(self, crop):
            self.calls += 1
            return self.answers[self.calls - 1]

    pack = [(0, 0, 30, 10, 0.5), (0, 0, 20, 10, 0.5), (0, 0, 10, 10, 0.5)]
    old_reader = I._W.get("reader")
    I._W["siglip"] = None
    I._W["reader"] = ListReader([[("12", 0.9)], [("7", 0.9)], []])
    check("reference_box: the box reading the entry's number wins over a larger car",
          I.reference_box(canvas, pack, "7"), (pack[1], "number read"))
    I._W["reader"] = ListReader([[], [], []])
    I._W["siglip"] = FakeSigLIP([("person", 0.1), ("car", 0.9), ("car", 0.9)])
    check("reference_box: no number read, a larger marshal is passed over for the largest car",
          I.reference_box(canvas, pack, "7"), (pack[1], "largest car"))
    I._W["siglip"] = FakeSigLIP([("person", 0.1)])
    I._W["reader"] = ListReader([])
    check("reference_box: one box is never read and stays the pick when the check fails it",
          I.reference_box(canvas, pack[:1], "7"), (pack[0], "largest box"))
    I._W["siglip"] = None
    I._W["reader"] = ListReader([[], [], []])
    check("reference_box: without SigLIP 2 and no number read, the largest box",
          I.reference_box(canvas, pack, "7"), (pack[0], "largest box"))
    I._W["reader"] = ListReader([])
    check("reference_box: a team reference (no number) reads nothing",
          (I.reference_box(canvas, pack, ""), I._W["reader"].calls), ((pack[0], "largest box"), 0))
    I._W["siglip"], I._W["reader"] = old_siglip, old_reader
    import siglip as SG
    real = SG.SigLIP.__new__(SG.SigLIP)
    labels = list(SG.CAR_PROMPTS)
    real.texts = {tuple(SG.CAR_PROMPTS.items()): (labels, np.eye(len(labels), dtype=np.float32))}

    def what_of(sims: dict):
        vec = np.array([[sims.get(label, 0.0) for label in labels]], dtype=np.float32)
        return real.is_what(vec)
    check("is_what: a split vehicle vote beats a lone person", what_of({"car": 0.10, "truck": 0.10, "person": 0.105})[0], SG.CAR)
    check("is_what: a clear person is dropped with its share", what_of({"person": 0.2, "car": 0.1}), ("person", 0.0))
    check("is_what: a vehicle nearest is a car even at a low share", what_of({"truck": 0.1})[0], SG.CAR)
    numbers = list(SG.NUMBER_PROMPTS)
    real.texts[tuple(SG.NUMBER_PROMPTS.items())] = (numbers, np.eye(len(numbers), dtype=np.float32))

    def number_share_of(sims: dict):
        return real.number_visible(np.array([[sims.get(label, 0.0) for label in numbers]], dtype=np.float32))
    check("number_visible: the number prompts' summed share", number_share_of({"number side": 0.1, "number bike": 0.1}) > 0.99, True)
    check("number_visible: a crop nearest a none prompt has a low share", number_share_of({"none far": 0.1}) < 0.01, True)
    check("number_visible: no prompt nearer than another is an even split", number_share_of({}), 0.5)

    # ---- ticket 71, the number gate: a plain crop under NUMBER_GATE_MIN is not read by OCR
    class GateSigLIP:
        """A crop's vector is its box index; its number share is listed per box."""
        def __init__(self, shares):
            self.shares = shares

        def number_visible(self, vec):
            return self.shares[vec]

    apart = [(0, 0, 18, 18, 0.9, 2), (20, 20, 38, 38, 0.9, 2)]
    under, over = SG.NUMBER_GATE_MIN / 2, SG.NUMBER_GATE_MIN + 0.3
    gate_w = dict(I._W)
    I._W.clear()
    I._W.update(reader=CountingReader(), embedder=OneEmbedder(), siglip=GateSigLIP([under, over]),
                models={"kind": "motorsport", "number_gate": True})
    gate_read = I._read_boxes(canvas, apart, vecs=[0, 1])
    check("number gate: the box under the gate is not read, the box over it is",
          (I._W["reader"].calls, gate_read["ocr"], gate_read["ocr_trace"], gate_read["ocr_ctc"][0], gate_read["number_share"]),
          (1, [[], []], [I.GATED_TRACE, []], {}, [under, over]))
    I._W["reader"] = CountingReader()
    no_vecs = I._read_boxes(canvas, apart)
    check("number gate: a box with no box-check vector is read as ever",
          (I._W["reader"].calls, no_vecs["ocr_trace"], no_vecs["number_share"]), (2, [[], []], [None, None]))
    I._W["reader"] = CountingReader()
    I._W["reader"].keep_regions = True
    verify_read = I._read_boxes(canvas, apart, vecs=[0, 1])
    check("number gate: --verify still reads a gated box, for its regions only",
          (I._W["reader"].calls, verify_read["ocr_trace"][0], len(verify_read["ocr_regions"])), (2, I.GATED_TRACE, 2))
    I._W["reader"] = CountingReader()
    I._W["models"] = {"kind": "motorsport", "number_gate": False}
    gate_off = I._read_boxes(canvas, apart, vecs=[0, 1])
    I._W["siglip"] = None
    check("number gate: off, the analysis is the one made without it",
          (I._W["reader"].calls, json.dumps(gate_off, sort_keys=True)),
          (2, json.dumps(I._read_boxes(canvas, apart), sort_keys=True)))
    I._W["models"] = {"kind": "motorsport", "number_gate": True}
    check("number gate: on without SigLIP 2, the analysis is the one made without it",
          json.dumps(I._read_boxes(canvas, apart), sort_keys=True), json.dumps(gate_off, sort_keys=True))
    I._W.clear()
    I._W.update(gate_w)
    lines = []
    real_log, I.log = I.log, lines.append
    try:
        I.log_box_check({"a": {"dropped": {"person": 2}, "contested": [{"kept": "score"}, {"kept": False}]},
                         "b": {"dropped": {"person": 1, "railing": 1}, "contested": [{"kept": "share"}]}, "c": None},
                        {"kind": "vehicles", "siglip": frame})
        I.log_box_check({"a": {"dropped": {"person": 2}}}, {"kind": "vehicles", "siglip": ""})
    finally:
        I.log = real_log
    check("the drop log counts per answer and kept reason, and is silent without SigLIP", lines,
          ["box check: dropped 4 boxes: person 3, railing 1; kept 1 on vehicle share, 1 on detector score"])
    people = {"kind": "people", "face_det": frame, "face_rec": frame}
    check("the people key carries the fingerprint", FP.analysis_fingerprint() in I.frame_key(frame, people), True)
    check("the cache key carries no stray version", "1" not in I.IdentifyCache._key(["x"]), True)

    # ---- every per-frame constant is filed as a cache input or neutral
    # (siglip is neutral only: its constants are in siglip_key, so the fingerprint stays as it was)
    for mod in {**FP.CACHE_INPUTS, **FP.CACHE_NEUTRAL}:
        tree = ast.parse(open(mod.__file__, encoding="utf-8").read())
        names = [t.id for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign))
                 for t in (node.targets if isinstance(node, ast.Assign) else [node.target])
                 if isinstance(t, ast.Name) and t.id.lstrip("_").isupper() and t.id != "__all__"]
        filed = FP.CACHE_INPUTS.get(mod, ()) + FP.CACHE_NEUTRAL[mod]
        check(f"{mod.__name__}: every constant is filed once", sorted(n for n in names if filed.count(n) != 1), [])
        check(f"{mod.__name__}: nothing filed that does not exist", sorted(set(filed) - set(names)), [])

    # ---- shared detections: a frame analysed twice runs the detector once, the second read is the cached entry
    det_runs = []

    def fake_run(detector, canvas, scale, w, h):
        det_runs.append(w)
        return np.array([[0, 0, 32, 24, 0.1, 2]], dtype=np.float64).reshape(-1, 6)

    VD.FAMILIES["fake"] = {"match": lambda name: False, "load": None, "run": fake_run,
                           "classes": frozenset({2, 3, 7})}
    fake_det = VD.Detector(id="fake:x:1:abc", family="fake", net=None, classes=frozenset({2, 3, 7}))
    saved_w = dict(I._W)
    I._W.clear()
    I._W.update(models={"kind": "motorsport"}, detector=fake_det, reader=CountingReader(),
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

    # ---- worker smoke: the real per-frame workers run end to end with SigLIP 2 on and stand-in
    # models, so a changed helper signature fails here and not on a 2-hour Windows run
    VD.FAMILIES["fakecar"] = {"match": lambda name: False, "load": None, "classes": frozenset({2, 3, 7}),
                              "run": lambda detector, canvas, scale, w, h: np.array([[2, 2, 50, 40, 0.9, 2]], dtype=np.float64)}
    saved_w = dict(I._W)
    I._W.clear()
    I._W.update(models={"kind": "motorsport"}, reader=CountingReader(), embedder=OneEmbedder(),
                siglip=FakeSigLIP([("car", 0.9)] * 4),
                detector=VD.Detector(id="fakecar:x:1:abc", family="fakecar", net=None, classes=frozenset({2, 3, 7})),
                detections=VD.DetectionCache(os.path.join(tempfile.mkdtemp(), "detections.sqlite")))
    try:
        analysed = I.analyse_frame(frame)
        rescued = I.rescue_frame((frame, [2, 2, 50, 40, 0.9, 2], "/x/mate.jpg", encode(np.ones(4, dtype=np.float32))))
    finally:
        I._W["detections"].close()
        I._W.clear()
        I._W.update(saved_w)
    check("smoke: analyse_frame keeps the box the check calls a car", (len(analysed["boxes"]), analysed["dropped"]), (1, {}))
    check("smoke: rescue_frame reads the candidate as the frame's one box", (len(rescued["boxes"]), rescued["rescued"]["from"]),
          (1, "mate.jpg"))
    check("a box under DETECTOR_MIN_SCORE is a candidate, not a box",
          (first["boxes"], first["candidates"]), ([], [[0.0, 0.0, 32.0, 24.0, 0.1, 2]]))

    # ---- results rows
    check("a no-vehicle row", I.format_row("7", BoxResult(-1, "none")), "7,-1,none,,,0.000,,,,,,,")
    check("a team row carries the runner-up", I.format_row("7", BoxResult(0, "team", "VER", "TSU", 0.71234)),
          "7,0,team,VER,TSU,0.712,,,,,,,")
    check("a row has the shot type before the order flag", I.format_row("7", BoxResult(0, "number", "VER", "", 0.9), "pack"),
          "7,0,number,VER,,0.900,,pack,,,,,")
    check("a flagged row has 1 in the order flag", I.format_row("7", BoxResult(0, "number", "VER", "", 0.85, order_flag=True), "solo"),
          "7,0,number,VER,,0.850,,solo,1,,,,")
    check("a row ends with the colour and its flag",
          I.format_row("7", BoxResult(0, "number", "VER", "", 0.85, colour="Red", colour_flag=True), "solo").endswith(",Red,1,,,"), True)
    check("a row with no colour, sponsor, anchor flag or new number ends with five empty fields", I.format_row("7", BoxResult(0, "none"), "solo").endswith(",,,,,"), True)
    check("a row ends with its sponsor words",
          I.format_row("7", BoxResult(0, "number", "VER", "", 0.85, sponsor="Castrol;Shell"), "solo").endswith(",,,Castrol;Shell,,"), True)
    check("a row ends with the anchor flag",
          I.format_row("7", BoxResult(0, "none", "", "VER", anchor_flag=True), "solo").endswith(",1,"), True)
    check("a row ends with its new numbers",
          I.format_row("7", BoxResult(0, "number", "VER", "", 0.85, new_number="115;207"), "solo").endswith(",,115;207"), True)
    check("a row has fourteen fields", len(I.format_row("7", BoxResult(0, "none"), "solo").split(",")), 14)

    # ---- pooled burst livery (experimental)
    drivers = {"VER": I.Entry("VER", "1", "Red Bull", ("F1|Red Bull|VER",)),
               "TSU": I.Entry("TSU", "22", "Red Bull", ("F1|Red Bull|TSU",)),
               "HAM": I.Entry("HAM", "44", "Ferrari", ("F1|Ferrari|HAM",))}
    ver_sims = [("VER", 0.9), ("TSU", 0.5), ("HAM", 0.2)]
    seen_box = {"boxes": [{"overlap": "", "hint": {}}]}
    unread = [BoxResult(0, "none")]
    burst = {"a": "g", "b": "g", "c": "g"}
    methods = lambda out: {fid: (rs[0].method, rs[0].entry_id, rs[0].alt_entry_id) for fid, rs in out.items()}
    check("pooled: unidentified frames of a burst take the pooled livery match",
          methods(I.pool_burst_livery({"a": unread, "b": unread}, burst, {"a": ver_sims, "b": ver_sims}, drivers,
                                      {"a": seen_box, "b": seen_box})),
          {"a": ("pooled", "VER", ""), "b": ("pooled", "VER", "")})
    check("pooled: a frame already identified by livery keeps its method",
          methods(I.pool_burst_livery({"a": [BoxResult(0, "livery", "VER", "", 0.8)], "b": unread}, burst,
                                      {"a": ver_sims, "b": ver_sims}, drivers, {"a": seen_box, "b": seen_box})),
          {"a": ("livery", "VER", ""), "b": ("pooled", "VER", "")})
    check("pooled: a burst with a frame identified as another car is left alone",
          methods(I.pool_burst_livery({"a": [BoxResult(0, "livery", "HAM", "", 0.8)], "b": unread, "c": unread}, burst,
                                      {"a": ver_sims, "b": ver_sims, "c": ver_sims}, drivers,
                                      {"a": seen_box, "b": seen_box, "c": seen_box})),
          {"a": ("livery", "HAM", ""), "b": ("none", "", ""), "c": ("none", "", "")})
    check("pooled: an overlapped box 0 is neither pooled nor filled",
          methods(I.pool_burst_livery({"a": unread, "b": unread, "c": unread}, burst,
                                      {"a": ver_sims, "b": ver_sims, "c": [("HAM", 5.0)]}, drivers,
                                      {"a": seen_box, "b": seen_box, "c": {"boxes": [{"overlap": I.HIDDEN, "hint": {}}]}})),
          {"a": ("pooled", "VER", ""), "b": ("pooled", "VER", ""), "c": ("none", "", "")})
    tie = [("VER", 0.9), ("TSU", 0.9 - I.MATCH_MIN_MARGIN / 2), ("HAM", 0.2)]
    check("pooled: a pooled team tie names no driver",
          methods(I.pool_burst_livery({"a": unread, "b": unread}, burst, {"a": tie, "b": tie}, drivers,
                                      {"a": seen_box, "b": seen_box})),
          {"a": ("none", "", ""), "b": ("none", "", "")})
    ferrari_hint = {"boxes": [{"overlap": "", "hint": {"prefixes": ["F1|Ferrari"], "source": "tag", "restricted": 1,
                                                       "dropped": False, "reason": ""}}]}
    check("pooled: a frame whose tag hint leaves the entry out keeps its result",
          methods(I.pool_burst_livery({"a": unread, "b": unread, "c": unread}, burst,
                                      {"a": ver_sims, "b": ver_sims, "c": ver_sims}, drivers,
                                      {"a": ferrari_hint, "b": seen_box, "c": seen_box})),
          {"a": ("none", "", ""), "b": ("pooled", "VER", ""), "c": ("pooled", "VER", "")})
    check("pooled: a team result takes the pooled driver only for its own team",
          methods(I.pool_burst_livery({"a": [BoxResult(0, "team", "TSU", "VER", 0.7)], "b": [BoxResult(0, "team", "HAM", "", 0.7)],
                                       "c": unread}, burst, {"a": ver_sims, "b": ver_sims, "c": ver_sims}, drivers,
                                      {"a": seen_box, "b": seen_box, "c": seen_box})),
          {"a": ("pooled", "VER", ""), "b": ("team", "HAM", ""), "c": ("pooled", "VER", "")})
    blue = dict(drivers, VER=I.Entry("VER", "1", "Red Bull", ("F1|Red Bull|VER",), colour="Blue"))
    red_box, blue_box = [BoxResult(0, "none", colour="Red")], [BoxResult(0, "none", colour="Blue")]
    check("pooled: a frame whose colour differs from the pooled entry's is left out of the fill",
          methods(I.pool_burst_livery({"a": blue_box, "b": unread, "c": red_box}, burst,
                                      {"a": ver_sims, "b": ver_sims, "c": ver_sims}, blue,
                                      {"a": seen_box, "b": seen_box, "c": seen_box})),
          {"a": ("pooled", "VER", ""), "b": ("pooled", "VER", ""), "c": ("none", "", "")})
    # c's sims carry the pool to VER; without c the two blue frames name no one
    weak_sims = [("VER", I.MATCH_MIN_SIM - 0.1), ("TSU", 0.2), ("HAM", 0.1)]
    check("pooled: a frame whose colour differs is left out of the pool",
          methods(I.pool_burst_livery({"a": blue_box, "b": unread, "c": red_box}, burst,
                                      {"a": weak_sims, "b": weak_sims, "c": [("VER", 5.0)]}, blue,
                                      {"a": seen_box, "b": seen_box, "c": seen_box})),
          {"a": ("none", "", ""), "b": ("none", "", ""), "c": ("none", "", "")})
    check("pooled: one frame left after the colour check is no pool",
          methods(I.pool_burst_livery({"a": blue_box, "b": red_box}, burst, {"a": ver_sims, "b": ver_sims}, blue,
                                      {"a": seen_box, "b": seen_box})),
          {"a": ("none", "", ""), "b": ("none", "", "")})

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
    # ticket 76: the parent works out SigLIP 2's prompt vectors once; a worker loads the image model only
    siglip_vision = os.path.join(models_dir, "siglip2_base_vision.onnx")
    if os.path.isfile(siglip_vision):
        parent = S.SigLIP(siglip_vision)
        crop = np.full((64, 96, 3), (200, 30, 30), dtype=np.uint8)
        vec = parent.embed_image(crop)
        want = (parent.is_what(vec), parent.colour_scores(vec, C.PALETTE))
        texts = parent.prepare_texts(C.PALETTE)
        check("the parent frees SigLIP 2's text model once its vectors are made", (parent.text, parent.tok, len(texts)),
              (None, None, 2))
        siglip_w = dict(I._W)
        I._W.clear()
        I._W.update(siglip_texts=texts)
        worker = I._siglip({"siglip": siglip_vision})
        I._W.clear()
        I._W.update(siglip=S.SigLIP(siglip_vision))
        with I.WorkerPool({"kind": "motorsport", "car_colour": C.PALETTE}) as started:
            pool_texts = started.get()._initargs[1]  # no job is submitted, so no worker starts
            pool_parent = (I._W["siglip"].text, sorted(len(labels) for labels, _ in pool_texts.values()))
        I._W.clear()
        I._W.update(siglip_w)
        check("starting the pool hands the workers both prompt sets and frees the parent's text model", pool_parent,
              (None, sorted([len(S.CAR_PROMPTS), len(C.PALETTE) + 1])))
        check("a worker's SigLIP 2 has no text model", (worker.text, worker.tok), (None, None))
        check("a worker answers from the parent's vectors as the parent did",
              (worker.is_what(worker.embed_image(crop)), worker.colour_scores(worker.embed_image(crop), C.PALETTE)), want)
        try:
            worker.colour_scores(vec, (("Teal", C.PALETTE[0][1]),))
            unprepared = "(no error)"
        except RuntimeError as e:
            unprepared = str(e)
        check("a palette the parent didn't prepare raises", unprepared.startswith("SigLIP 2 has no text model loaded"), True)
    else:
        print("skip SigLIP 2 prompt vectors (models/ not downloaded)")
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

    # ---- the identify run: the real analysis, rescue and re-read over real image files; only the
    # models are stand-ins, and the worker pool runs in this process so they reach the workers
    root = tempfile.mkdtemp(prefix="collections_")
    coll = collection([VER, TSU], root=root)
    manifest = os.path.join(img, "manifest.csv")
    X = tempfile.mkdtemp(prefix="frames_")
    with open(manifest, "w", encoding="utf-8") as f:
        f.write(f'"1","{X}/1.jpg","5"\n"2","{X}/2.jpg","5"\n"3","{X}/3.jpg","5"\n"4","{X}/4.jpg","9"\n"5","{X}/5.jpg","9"\n')
    # a frame's grey shade is its scene: 10 car reading 1 at 0.95, 20 at 0.90, 30 a car with no read,
    # 40 no vehicle; frame 9 is two cars (left 10, right 30). Frame 5 is missing: a decode error.
    for n, shade in {1: 10, 2: 20, 3: 30, 4: 40, 6: 10, 7: 10, 8: 30}.items():
        Image.new("RGB", (100, 50), (shade,) * 3).save(f"{X}/{n}.jpg", format="PNG")
    pack_img = Image.new("RGB", (100, 50), (30,) * 3)
    pack_img.paste((10, 10, 10), (0, 0, 50, 50))
    pack_img.save(f"{X}/9.jpg", format="PNG")
    scene_reads = {10: [("1", 0.95)], 20: [("1", 0.90)], 30: [], 40: []}

    def scene_shade(pixel):
        return min(scene_reads, key=lambda s: abs(s - float(pixel)))

    def scene_run(detector, canvas, scale, w, h):
        left, right = scene_shade(canvas[1, 1, 0]), scene_shade(canvas[1, int(w * scale) - 2, 0])
        if left == 40:
            return np.zeros((0, 6), dtype=np.float64)
        if left != right:
            return np.array([[0, 0, w / 2, h, 0.9, 2], [w / 2, 0, w, h, 0.85, 2]], dtype=np.float64)
        return np.array([[0, 0, w, h, 0.9, 2]], dtype=np.float64)

    VD.FAMILIES["scene"] = {"match": lambda name: False, "load": None, "run": scene_run, "classes": frozenset({2, 3, 7})}

    class SceneReader(CountingReader):
        def read(self, crop):
            return list(scene_reads[scene_shade(crop[crop.shape[0] // 2, crop.shape[1] // 2, 0])])

    class FakeEmbedder:
        dim = 384

        def __init__(self, path):
            pass

        def embed(self, crop):
            return np.eye(384, dtype=np.float32)[0]

    class InlinePool(I.WorkerPool):
        """The real WorkerPool's stages, run on one thread here: its workers get the stand-in models
        as _init_worker would give them the loaded ones."""
        def get(self):
            if self.executor is None:
                import concurrent.futures
                I._W.update(models=self.models, reader=SceneReader(), embedder=FakeEmbedder(""), segmenter=None, siglip=None,
                            detector=VD.Detector(id="scene:x:1:abc", family="scene", net=None, classes=frozenset({2, 3, 7})),
                            detections=VD.DetectionCache(""))
                self.size, self.executor = 1, concurrent.futures.ThreadPoolExecutor(max_workers=1)
            return self.executor

    fake_models = {k: frame for k in ("detector", "ocr_det", "ocr_rec", "embedder")}
    identify_w = dict(I._W)
    real = (I.check_models, I.Embedder, I.WorkerPool)
    # check_models loads every model file; these are stand-ins
    I.check_models, I.Embedder, I.WorkerPool = (lambda m, siglip=True: FakeEmbedder("fake")), FakeEmbedder, InlinePool
    results = os.path.join(img, "results.csv")
    args = Namespace(manifest=manifest, results=results, progress=os.path.join(img, "progress.txt"), cache="",
                     collections_root=root, collection=os.path.basename(coll), settings="", entries_out=os.path.join(img, "e.csv"),
                     rules_out=os.path.join(img, "r.csv"), boxes_out="", overturns_out="", boxes_in="", report_out="", report_top=20, archive_dir="")
    I.identify(args, dict(fake_models))
    rows = open(results, encoding="utf-8").read().splitlines()
    check("number reads, burst consensus and no-vehicle rows come out in manifest order (3-column manifest)", rows,
          ["1,0,number,VER,,0.950,,solo,,,,,", "2,0,number,VER,,0.900,,solo,,,,,", "3,0,burst,VER,,0.667,,solo,,,,,",
           "4,-1,none,,,0.000,,,,,,,", "5,-1,error,,,0.000,,,,,,,"])
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
        f.write(f'"1","{X}/1.jpg","5","F1|Red Bull;F1|Red Bull|Tsunoda"\n'
                f'"2","{X}/2.jpg","5","F1|Red Bull|Tsunoda"\n'
                f'"6","{X}/6.jpg","8",""\n"7","{X}/7.jpg","8",""\n'
                f'"8","{X}/8.jpg","8","F1|Red Bull|Tsunoda"\n'
                f'"9","{X}/9.jpg","9","F1|Red Bull|Tsunoda"\n')
    args.boxes_out = os.path.join(img, "last-run", "c.boxes.json")
    I.identify(args, dict(fake_models))
    rows = open(results, encoding="utf-8").read().splitlines()
    check("a fully tagged image is skipped; solo disagreement is a conflict, also when burst-filled; packs aren't", rows,
          ["1,-1,skipped,,,0.000,,,,,,,", "2,0,conflict,VER,,0.900,,solo,,,,,", "6,0,number,VER,,0.950,,solo,,,,,",
           "7,0,number,VER,,0.950,,solo,,,,,", "8,0,conflict,VER,,0.667,,solo,,,,,", "9,0,number,VER,,0.950,,pack,,,,,",
           "9,1,none,,,0.000,,pack,,,,,"])
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
          (sorted(run["thresholds"]), sorted(run["entries"]["VER"])),
          (["min_margin", "min_read", "min_sim", "noise_min_beside_share", "noise_min_partners", "number_gate_min", "number_list_floor", "number_list_margin",
            "number_min_height", "ocr_min_score", "weak_read_min"],
           ["camera", "car", "colour", "number", "refs", "tags", "team"]))
    readme = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "README.md"), encoding="utf-8").read()
    listed = re.search(r'"thresholds" \(\{([^}]*)\}', readme)
    check("the README's boxes.json shape lists the thresholds the run writes",
          sorted(listed.group(1).split(", ")) if listed else None, sorted(run["thresholds"]))
    args.report_out = os.path.join(img, "last-run", "c.report")
    I.identify(args, dict(fake_models))
    check("--report-out writes report.md and report.json", (os.path.isfile(args.report_out + ".md"),
          json.load(open(args.report_out + ".json", encoding="utf-8"))["summary"]["counts"]["already-tagged"]), (True, 1))
    args.report_out = ""

    # ---- the 7th manifest field: the entry the user's own number or driver tag names
    with open(manifest, "w", encoding="utf-8") as f:
        f.write(f'"2","{X}/2.jpg","5","F1|Red Bull","","","TSU"\n'
                f'"3","{X}/3.jpg","7","","","",""\n'
                f'"8","{X}/8.jpg","7","Assisted Tagging|Motorsport|Number|22","","","TSU"\n'
                f'"4","{X}/4.jpg","9","Assisted Tagging|Motorsport|Number|22","","","TSU"\n'
                f'"9","{X}/9.jpg","6","Assisted Tagging|Motorsport|Number|22","","","TSU"\n')
    args.boxes_out = ""
    I.identify(args, dict(fake_models))
    rows = open(results, encoding="utf-8").read().splitlines()
    check("a hand-tagged solo shot read as another car is a conflict, though the two share a team tag", rows[0],
          "2,0,conflict,VER,,0.900,,solo,,,,,")
    check("a hand-tagged frame anchors its burst alone", rows[1], "3,0,burst,TSU,,0.500,,solo,,,,,")
    check("an unread box takes the hand-tagged entry", rows[2], "8,0,hand,TSU,,1.000,,solo,,,,,")
    check("a frame with no vehicle takes the hand-tagged entry", rows[3], "4,-1,hand,TSU,,1.000,,,,,,,")
    check("a pack keeps its boxes and gains the hand-tagged entry", rows[4:],
          ["9,0,number,VER,,0.950,,pack,,,,,", "9,1,none,,,0.000,,pack,,,,,", "9,-1,hand,TSU,,1.000,,pack,,,,,"])
    with open(manifest, "w", encoding="utf-8") as f:
        f.write(f'"4","{X}/4.jpg","9","Assisted Tagging|Motorsport|Number|5","","","GONE"\n')
    lines = []
    real_log, I.log = I.log, lines.append
    try:
        I.identify(args, dict(fake_models))
    finally:
        I.log = real_log
    check("a hand entry that isn't in entries.json is logged and its image identified without it",
          (open(results, encoding="utf-8").read().splitlines(), any("hand-tagged as entry GONE" in ln for ln in lines)),
          (["4,-1,none,,,0.000,,,,,,,"], True))

    # ---- the 8th manifest field: "1" when the user locked the photo's tags (ticket 89)
    with open(manifest, "w", encoding="utf-8") as f:
        f.write(f'"8","{X}/8.jpg","7","Assisted Tagging|Motorsport|Number|22","","","TSU","1"\n'
                f'"3","{X}/3.jpg","7","","","",""\n'
                f'"2","{X}/2.jpg","5","F1|Red Bull","","","TSU","1"\n'
                f'"4","{X}/4.jpg","9","","","","","1"\n')
    I.identify(args, dict(fake_models))
    rows = open(results, encoding="utf-8").read().splitlines()
    check("a locked photo is left alone but its entry still fills its burst", rows[:2],
          ["8,-1,skipped,,,0.000,,,,,,,", "3,0,burst,TSU,,0.500,,solo,,,,,"])
    check("a locked photo read as another car is left alone, not a conflict; one with no entry too", rows[2:],
          ["2,-1,skipped,,,0.000,,,,,,,", "4,-1,skipped,,,0.000,,,,,,,"])

    # ---- noise numbers: a class "3" on every car, read beside three start-list numbers; one car is number 3
    ALB = {"id": "ALB", "number": "7", "team": "Williams", "tags": ["F1|Williams", "F1|Williams|Albon"]}
    PER = {"id": "PER", "number": "3", "team": "Cadillac", "tags": ["F1|Cadillac", "F1|Cadillac|Perez"]}
    # two cars entered under 99, which no frame reads
    OCO = {"id": "OCO", "number": "99", "team": "Haas", "tags": ["F1|Haas", "F1|Haas|Ocon"]}
    BEA = {"id": "BEA", "number": "99", "team": "Haas", "tags": ["F1|Haas", "F1|Haas|Bearman"]}
    noise_coll = collection([VER, TSU, ALB, PER, OCO, BEA], root=root)
    scene_reads.update({50: [("1", 0.95), ("3", 0.95)], 60: [("22", 0.95), ("3", 0.95)], 70: [("7", 0.95), ("3", 0.95)],
                        80: [("3", 0.95)]})
    for n, shade in {11: 50, 12: 60, 13: 70, 14: 80}.items():
        Image.new("RGB", (100, 50), (shade,) * 3).save(f"{X}/{n}.jpg", format="PNG")
    with open(manifest, "w", encoding="utf-8") as f:
        f.write("".join(f'"{n}","{X}/{n}.jpg","{n}"\n' for n in (11, 12, 13, 14)))
    args.collection, args.boxes_out = os.path.basename(noise_coll), os.path.join(img, "last-run", "noise.boxes.json")
    lines = []
    real_log, I.log = I.log, lines.append
    try:
        I.identify(args, dict(fake_models))
    finally:
        I.log = real_log
    check("a noise number is left out of a box that reads another number, and kept where it is the only read",
          open(results, encoding="utf-8").read().splitlines(),
          ["11,0,number,VER,,0.950,,solo,,,,,", "12,0,number,TSU,,0.950,,solo,,,,,", "13,0,number,ALB,,0.950,,solo,,,,,",
           "14,0,number,PER,,0.950,,solo,,,,,"])
    check("the run logs its noise numbers once, and each box that left one out",
          ([ln for ln in lines if ln.startswith("noise numbers:")], sum("[noise number 3 not used]" in ln for ln in lines)),
          (["noise numbers: 3 (beside 3 numbers); left out of a box's reads when it has another"], 3))
    shared = [i for i, ln in enumerate(lines) if ln.startswith("entry list: number 99 is on more than one car (OCO, BEA)")]
    check("the run logs a number entered on two cars once, before any frame is matched",
          (len(shared), shared[:1] < [i for i, ln in enumerate(lines) if ln.startswith("11:")][:1]), (1, True))
    noise_run = json.load(open(args.boxes_out, encoding="utf-8"))
    check("boxes.json lists the noise numbers and keeps each box's full OCR",
          (noise_run["noise_numbers"], noise_run["images"]["11"]["boxes"][0]["ocr"]), ({"3": 3}, [["1", 0.95], ["3", 0.95]]))
    check("boxes.json keeps the entry-list findings the run logged",
          noise_run["entry_list"], [ln for ln in lines if ln.startswith("entry list:")])
    check("the entry-list findings are not empty", len(noise_run["entry_list"]) > 0, True)
    args.collection, args.boxes_out = os.path.basename(coll), ""

    # ---- the entry-list check at the start of a run
    listed = {"A": I.Entry("A", "14", "", ()), "B": I.Entry("B", "14", "", ()), "C": I.Entry("C", "7", "", (), shows=("22",)),
              "D": I.Entry("D", "22", "", ()), "E": I.Entry("E", "", "", ()), "F": I.Entry("F", "", "", ())}
    check("entry list: a number on two cars (entered or shown), an entry nothing can find, and entries without references",
          I.entry_list_check(listed, {"A": 3, "F": 1}),
          ["entry list: number 14 is on more than one car (A, B): a read of it names none of them, only livery can",
           "entry list: number 22 is on more than one car (C, D): a read of it names none of them, only livery can",
           "entry list: 1 entry has no number and no references, so nothing can identify it: E",
           "entry list: 3 of 6 entries have no references, so only a number read finds them: B, C, D"])
    check("entry list: with no references at all, entries that have a number aren't listed",
          I.entry_list_check({k: listed[k] for k in "CE"}, {}),
          ["entry list: 1 entry has no number and no references, so nothing can identify it: E"])
    pair = {"A": I.Entry("A", "14", "", (), car="A"), "B": I.Entry("B", "14", "", (), car="A")}
    check("entry list: a double-driven car's two entries share its number and its references", I.entry_list_check(pair, {"B": 2}), [])
    many = {f"E{n}": I.Entry(f"E{n}", str(n), "", ()) for n in range(1, 19)}
    check("entry list: one entry without references reads in the singular",
          I.entry_list_check({k: listed[k] for k in "AB"}, {"A": 3}),
          ["entry list: number 14 is on more than one car (A, B): a read of it names none of them, only livery can",
           "entry list: 1 of 2 entries has no references, so only a number read finds it: B"])
    check("entry list: a long list of ids is cut short", I.entry_list_check(many, {"E18": 1})[0].endswith("E14, E15 and 2 more"), True)

    # ---- --promote-boxes: saves confident boxes from the box crop, replaces on re-run, flags a changed file
    real_jpg = os.path.join(img, "promo.jpg")
    Image.new("RGB", (100, 50), (200, 30, 30)).save(real_jpg)
    promo_boxes = os.path.join(img, "promo.boxes.json")

    def write_promo(frame, read=0.95):
        record = {"shot": "pack", "file": real_jpg, "frame": frame, "boxes": [
            {"box": 0, "bbox": [0, 0, 50, 50], "entry": "VER", "alt_entry": "", "method": "number",
             "confidence": read, "candidates": [], "ocr": [], "decided_by": "number", "gap": 0.0, "conflict": False},
            {"box": 1, "bbox": [50, 0, 100, 50], "entry": "TSU", "alt_entry": "", "method": "livery",
             "confidence": 0.8, "candidates": [["TSU", 0.80], ["VER", 0.78]], "ocr": [], "decided_by": "livery",
             "gap": 0.0, "conflict": False}]}
        with open(promo_boxes, "w", encoding="utf-8") as f:
            json.dump({"collection": os.path.basename(coll), "images": {"1": record}, "skipped": []}, f)

    with open(manifest, "w", encoding="utf-8") as f:
        f.write(f'"1","{real_jpg}",""\n')
    pargs = Namespace(manifest=manifest, results=results, progress=os.path.join(img, "p2.txt"), cache="",
                      collections_root=root, collection=os.path.basename(coll), settings="", entries_out=args.entries_out,
                      rules_out=args.rules_out, boxes_out="", overturns_out="", boxes_in=promo_boxes)
    write_promo([100, 50])
    I.promote_boxes(pargs, {"embedder": "fake"})
    check("promote adds a confident box", open(results, encoding="utf-8").read().strip(), "1,added,,VER")
    refs = sorted(d for d in os.listdir(os.path.join(coll, "refs")) if d != "sources.json")
    check("only the wide-margin box became a reference", refs, ["VER"])
    I.promote_boxes(pargs, {"embedder": "fake"})
    check("promoting again replaces rather than duplicates", len(os.listdir(os.path.join(coll, "refs", "VER"))), 1)
    write_promo([10, 10])
    I.promote_boxes(pargs, {"embedder": "fake"})
    check("a file that no longer matches the run is stale", open(results, encoding="utf-8").read().strip(), "1,stale,,")

    # ---- add-time screening: refs flagged by 2+ audit checks are refused (skip) or kept with a log line (warn)
    # the real screen_refs runs: wide 160x80 seed refs make the near-square red crop fail the crop
    # check, and blue seeds also fail the colour check; the stand-in embedder trips no embedding check.
    # A read under ANCHOR_MIN_READ (0.85) makes the promoted ref a non-anchor, which the screen may refuse.
    seeds = [os.path.join(coll, "refs", "VER", f"{n}.jpg") for n in range(2, 6)] + [os.path.join(coll, "refs", "TSU", f"{n}.jpg") for n in (6, 7)]

    def seed_refs(rgb):
        for p in seeds:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            Image.new("RGB", (160, 80), rgb).save(p)

    write_promo([100, 50])
    seed_refs((30, 30, 200))
    try:
        I.promote_boxes(pargs, {"embedder": "fake"})
        check("a strong read is an anchor: flagged, but never removed", open(results, encoding="utf-8").read().strip(), "1,added,,VER")
        with open(os.path.join(coll, "refs", "sources.json"), encoding="utf-8") as f:
            check("a promoted box records its source and read", {k: f_rec for k, f_rec in json.load(f)["refs/VER/1_b0.jpg"].items() if k != "date"},
                  {"source": "number", "confidence": 0.95})
        write_promo([100, 50], 0.85)
        I.promote_boxes(pargs, {"embedder": "fake"})
        check("a promoted box the audit checks flag is not saved", open(results, encoding="utf-8").read().strip(), "1,flagged,,VER")
        check("a flagged box's crop is replaced by the sample it overwrote",
              sorted(os.listdir(os.path.join(coll, "refs", "VER"))), ["1_b0.jpg", "2.jpg", "3.jpg", "4.jpg", "5.jpg"])
        seed_refs((200, 30, 30))
        write_promo([100, 50], 0.85)
        I.promote_boxes(pargs, {"embedder": "fake"})
        check("one flag alone does not refuse a box", open(results, encoding="utf-8").read().strip(), "1,added,,VER")
        with open(os.path.join(coll, "refs", "VER", "1_b0.jpg"), "rb") as f:
            before = f.read()
        write_promo([100, 50], 0.85)
        seed_refs((30, 30, 200))
        I.promote_boxes(pargs, {"embedder": "fake"})
        with open(os.path.join(coll, "refs", "VER", "1_b0.jpg"), "rb") as f:
            check("a refused re-promote puts the earlier sample back", f.read() == before, True)
    finally:
        for p in seeds:
            os.remove(p)

    # ---- reference actions fill an entry's colour (the colour family)
    import entries_file
    # the real frame_entry and detect_vehicles run; the detector is a stand-in that finds one car, or none
    VD.FAMILIES["fakenone"] = {"match": lambda name: False, "load": None, "classes": frozenset({2, 3, 7}),
                              "run": lambda detector, canvas, scale, w, h: np.zeros((0, 6), dtype=np.float64)}
    one_car = VD.Detector(id="fakecar:x:1:abc", family="fakecar", net=None, classes=frozenset({2, 3, 7}))
    no_car = VD.Detector(id="fakenone:x:1:abc", family="fakenone", net=None, classes=frozenset({2, 3, 7}))
    ref_w = dict(I._W)
    I._W.update(detector=one_car, detections=VD.DetectionCache(os.path.join(tempfile.mkdtemp(), "detections.sqlite")))
    vmodels = {"embedder": "fake", "detector": ""}
    colour_on = dict(FIXTURE_SETTINGS, family_colour=True)
    ccoll = collection(entries_file.dump({"rules": {"partial_references": True}, "entries": [VER, TSU]}), root=root, settings=colour_on)
    centries = os.path.join(ccoll, "entries.json")

    def ref_job(job, coll_dir, row, boxes_in="", colours_only=False):
        with open(manifest, "w", encoding="utf-8") as f:
            f.write(row + "\n")
        job(Namespace(manifest=manifest, results=results, progress=os.path.join(img, "p3.txt"), cache="",
                      collections_root=root, collection=os.path.basename(coll_dir), settings="", entries_out=args.entries_out,
                      rules_out=args.rules_out, boxes_out="", overturns_out="", boxes_in=boxes_in, colours_only=colours_only), dict(vmodels))
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
        check("a different hand colour replaces the entry's colour", ref_job(I.add_references, ccoll, f'"1","{real_jpg}","VER","Blue"'), "1,added,set,VER")
        check("entries.json holds the hand colour", json.load(open(centries, encoding="utf-8"))["entries"][0].get("colour"), "Blue")
        ccars = I.load_collection(ccoll, "")[0]
        crules = I.load_collection(ccoll, "")[1]
        check("a different reading of a coloured entry differs",
              I.fill_colours(centries, ccars, crules, [("1", "added", [])], [[("VER", "Red", False)]]), ["differs"])
        check("a differing reading leaves the colour", json.load(open(centries, encoding="utf-8"))["entries"][0].get("colour"), "Blue")
        check("a hand colour beats a reading earlier in the job",
              I.fill_colours(centries, ccars, crules, [("1", "added", []), ("2", "added", [])],
                             [[("VER", "Green", False)], [("VER", "Red", True)]]), ["differs", "set"])
        check("entries.json holds the later hand colour", json.load(open(centries, encoding="utf-8"))["entries"][0].get("colour"), "Red")

        # readings vote: one odd burst can't set an empty entry's colour
        vcoll = collection(entries_file.dump({"entries": [VER, TSU]}), root=root, settings=colour_on)
        ventries = os.path.join(vcoll, "entries.json")
        vcars, vrules = I.load_collection(vcoll, "")[:2]
        vdone = [(str(n), "added", []) for n in range(1, 5)]
        check("readings that tie set no colour",
              I.fill_colours(ventries, vcars, vrules, vdone[:2], [[("VER", "Red", False)], [("VER", "Blue", False)]]),
              ["differs", "differs"])
        check("tied readings leave the entry without a colour", json.load(open(ventries, encoding="utf-8"))["entries"][0].get("colour"), None)
        check("the colour most photos read wins over an odd first photo, near readings support it",
              I.fill_colours(ventries, vcars, vrules, vdone,
                             [[("VER", "Red", False)], [("VER", "Blue", False)], [("VER", "Blue", False)], [("VER", "Purple", False)]]),
              ["differs", "set", "set", ""])
        check("entries.json gains the voted colour", json.load(open(ventries, encoding="utf-8"))["entries"][0].get("colour"), "Blue")
        vcars = I.load_collection(vcoll, "")[0]
        check("a near reading of a coloured entry isn't a difference",
              I.fill_colours(ventries, vcars, vrules, vdone[:2], [[("VER", "Purple", False)], [("VER", "Blue", False)]]), ["", "already"])
        check("readings clashing with the stored colour in most but not nearly all photos leave it",
              I.fill_colours(ventries, vcars, vrules, vdone, [[("VER", "Red", False)]] * 3 + [[("VER", "Blue", False)]]),
              ["differs", "differs", "differs", "already"])
        check("a clash short of nearly all keeps the stored colour", json.load(open(ventries, encoding="utf-8"))["entries"][0].get("colour"), "Blue")
        rdone = [(str(n), "added", []) for n in range(1, 6)]
        check("nearly all photos reading a clashing colour replace the stored colour",
              I.fill_colours(ventries, vcars, vrules, rdone, [[("VER", "Red", False)]] * 5), ["set"] * 5)
        check("entries.json holds the overturning colour", json.load(open(ventries, encoding="utf-8"))["entries"][0].get("colour"), "Red")

        # --colours-only: the colour alone goes to entries.json, no reference is saved
        ocoll = collection(entries_file.dump({"entries": [VER, TSU]}), root=root, settings=colour_on)
        oentries = os.path.join(ocoll, "entries.json")
        check("colours-only: a hand colour sets the entry and saves no reference",
              (ref_job(I.add_references, ocoll, f'"1","{real_jpg}","VER","Red"', colours_only=True),
               os.path.exists(os.path.join(ocoll, "refs", "VER"))), ("1,read,set,VER,Red", False))
        check("colours-only: entries.json gains the colour", json.load(open(oentries, encoding="utf-8"))["entries"][0].get("colour"), "Red")
        os.remove(oentries + ".bak")
        before = open(oentries, "rb").read()
        check("colours-only: an entry with that colour is already",
              (ref_job(I.add_references, ocoll, f'"1","{real_jpg}","VER","Red"', colours_only=True),
               open(oentries, "rb").read() == before, os.path.exists(oentries + ".bak")), ("1,read,already,VER,Red", True, False))
        check("colours-only: a photo with no entry reads its colour and leaves entries.json alone",
              (ref_job(I.add_references, ocoll, f'"1","{real_jpg}","","Blue"', colours_only=True),
               open(oentries, "rb").read() == before), ("1,read,,,Blue", True))
        I._W["detector"] = no_car
        check("colours-only: no vehicle is unread and saves nothing",
              (ref_job(I.add_references, ocoll, f'"1","{real_jpg}","TSU",""', colours_only=True),
               os.path.exists(os.path.join(ocoll, "refs", "TSU"))), ("1,unread,,TSU", False))
        check("colours-only: a photo with no entry and no vehicle is unread",
              ref_job(I.add_references, ocoll, f'"1","{real_jpg}","",""', colours_only=True), "1,unread,,")
        I._W["detector"] = one_car
        try:
            ref_job(I.add_references, coll, f'"1","{real_jpg}","VER","Red"', colours_only=True)
            off = "(no error)"
        except I.InputError as e:
            off = str(e)
        check("colours-only needs the colour family", off, "Identify Colour needs the colour family (family_colour) on")
        pcoll = collection({"kind": "people", "entries": [LH]}, root=root)
        try:
            ref_job(I.add_references, pcoll, f'"1","{real_jpg}","Lando Norris",""', colours_only=True)
            people = "(no error)"
        except I.InputError as e:
            people = str(e)
        check("colours-only refuses a people collection", people, "Identify Colour is for vehicle collections")
        check("colours-only saves no face reference", os.path.isdir(os.path.join(pcoll, "refs", "Lando Norris")), False)
    finally:
        I._W["detections"].close()
        I._W.clear()
        I._W.update(ref_w)

    # ---- Review Focus 4: cancel leaves no results
    os.remove(results)
    open(args.progress + ".cancel", "w").close()
    try:
        I.identify(args, dict(fake_models))
        code = 0
    except SystemExit as e:
        code = e.code
    check("a cancelled run exits 130", code, 130)
    check("a cancelled run writes no results (nor leaves a temp file)",
          [n for n in os.listdir(os.path.dirname(results)) if n.startswith(os.path.basename(results))], [])
    I.check_models, I.Embedder, I.WorkerPool = real
    I._W.clear()
    I._W.update(identify_w)

    # ---- Stage B: hints
    mf = os.path.join(tempfile.mkdtemp(), "m.csv")
    with open(mf, "w", encoding="utf-8") as f:
        f.write('1,a.jpg,0\n2,b.jpg,0,F1|X\n3,c.jpg,0,,F1|Red Bull\n')
    check("3-, 4- and 5-column manifests all parse", [r[3:] for r in I.read_manifest(mf, 3, 2)],
          [["", ""], ["F1|X", ""], ["", "F1|Red Bull"]])
    ents = {"VER": I.Entry("VER", "1", "Red Bull", ("F1|Red Bull", "F1|Red Bull|Verstappen"))}
    check("team tags come from the team family root", I.team_tags(ents, {"team": "F1"}), ["F1|Red Bull"])
    check("no team tags with the team family off", I.team_tags(ents, {}), [])
    check("tag and sponsor hints that agree merge", I.box_hint(["F1|Red Bull"], ["F1|Red Bull"]), (["F1|Red Bull"], "both"))
    check("a tag hint beats a differing sponsor hint", I.box_hint(["F1|Ferrari"], ["F1|Red Bull"]), (["F1|Ferrari"], "tag"))
    check("sponsor hint alone", I.box_hint([], ["F1|Red Bull"]), (["F1|Red Bull"], "sponsor"))
    check("no hint", I.box_hint([], []), ([], ""))
    check("sponsor_keywords naming a prefix with no entries is rejected",
          load_error({"rules": {"sponsor_keywords": {"petronas": "F1|Mercedes"}}, "entries": [VER]}).startswith(
              "rules.sponsor_keywords.petronas: no entry has a tag under"), True)
    check("sponsor_keywords can't hold | (a keyword becomes a sponsor tag value)", load_error(
          {"rules": {"sponsor_keywords": {"red|bull": "F1"}}, "entries": [VER]}),
          "rules.sponsor_keywords must map lowercase keywords to tag prefixes")
    check("sponsor_keywords must be lowercase", load_error(
          {"rules": {"sponsor_keywords": {"Petronas": "F1"}}, "entries": [VER]}),
          "rules.sponsor_keywords must map lowercase keywords to tag prefixes")
    check("sponsor_names must name a sponsor_keywords word", load_error(
          {"rules": {"sponsor_names": {"dhl": "DHL"}}, "entries": [VER]}),
          'rules.sponsor_names must map sponsor_keywords words to tag values without , ; " or |')
    check("sponsor_names can't hold | (it becomes a tag value)", load_error(
          {"rules": {"sponsor_keywords": {"petronas": "F1"}, "sponsor_names": {"petronas": "PET|RONAS"}}, "entries": [VER]}),
          'rules.sponsor_names must map sponsor_keywords words to tag values without , ; " or |')
    lines = []
    real_log, I.log = I.log, lines.append
    try:
        _, pr_rules, _fe = I.load_collection(collection({"rules": {"partial_references": "yes"}, "entries": [VER]}))
    finally:
        I.log = real_log
    check("a non-boolean partial_references in entries.json logs and keeps the default",
          (pr_rules.partial_references, "entries.json: rules.partial_references invalid, using False" in lines),
          (False, True))
    _, solo_rules, _fe = I.load_collection(collection({"entries": [VER]}))
    _, packs_rules, _fe = I.load_collection(collection({"entries": [VER]},
                                                       settings=dict(FIXTURE_SETTINGS, cars_per_photo="packs")))
    check("cars_per_photo: solo by default, packs from settings.json",
          (solo_rules.cars_per_photo, packs_rules.cars_per_photo), ("solo", "packs"))

    # ticket 67: a box's colour softly narrows the entries; the number wins
    cp = {"R": I.Entry("R", "1", "A", ("F1|A",), colour="Red"), "B": I.Entry("B", "2", "B", ("F1|B",), colour="Blue"),
          "N": I.Entry("N", "3", "C", ("F1|C",))}
    pool, note = I.colour_pool(cp, "Red", [], [("R", 0.99), ("B", 0.99)], 0.5)
    check("colour_pool keeps the matching and unknown colours", (sorted(pool), note["kept"], note["dropped"]),
          (["N", "R"], 2, False))
    check("colour_pool: no colour keeps every entry", I.colour_pool(cp, "", [], [], 0.5), (cp, {}))
    check("colour_pool: a confident read of a removed entry drops the filter",
          I.colour_pool(cp, "Red", [("2", 0.9)], [("R", 0.99)], 0.5)[1]["reason"], "number_outside")
    check("colour_pool: no kept similarity at the minimum drops the filter",
          I.colour_pool(cp, "Red", [], [("R", 0.0), ("B", 0.99)], 0.5)[1]["reason"], "below_min_sim")

    # ticket 60: the progress line names its stage and how many were cached
    prog = os.path.join(tempfile.mkdtemp(), "progress.txt")
    I.write_progress(prog, 12, 40, "analysing", 10)
    with open(prog, encoding="utf-8") as pf:
        check("a staged progress line is stage,cur,tot,cached", pf.read(), "analysing,12,40,10")
    I.write_progress(prog, 3, 9)
    with open(prog, encoding="utf-8") as pf:
        check("a progress line with no stage stays cur,tot", pf.read(), "3,9")

    # ticket 75: each stage logs a start line and a done line with its seconds and peak memory
    import contextlib
    import io
    I.end_stage()
    stderr_text = io.StringIO()
    with contextlib.redirect_stderr(stderr_text):
        I.write_progress("", 1, 2, "refining")
        I.write_progress("", 2, 2, "refining")
        I.write_progress("", 0, 5, "matching")
        I.end_stage()
        I.end_stage()
    stage_lines = [re.sub(r"^\d\d:\d\d:\d\d py: ", "", line) for line in stderr_text.getvalue().splitlines()]
    check("stage lines: one start and one done line per stage, in order",
          [re.sub(r"\d+", "N", line) for line in stage_lines],
          ["refining: started", "refining: done, Ns, peak memory N MB (workers not included)",
           "matching: started", "matching: done, Ns, peak memory N MB (workers not included)"])
    check("peak memory is this process's real peak, in MB", 20 < V.peak_memory_mb() < 100000, True)

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

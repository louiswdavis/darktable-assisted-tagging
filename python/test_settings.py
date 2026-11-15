# Run with: python python/test_settings.py
# Exercises settings.py's schema, precedence (settings.json, then entries.json rules, then
# defaults) and diagnostics_of; the Lua schema parity check reads lua/assisted_tagging.lua.

import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings as S

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


def folder(data=None, raw=None) -> str:
    d = tempfile.mkdtemp()
    if raw is not None:
        with open(os.path.join(d, "settings.json"), "wb") as f:
            f.write(raw)
    elif data is not None:
        with open(os.path.join(d, "settings.json"), "w", encoding="utf-8") as f:
            json.dump(data, f)
    return d


def load(data=None, rules=None, raw=None, path=""):
    lines = []
    values, from_entries = S.load_settings(folder(data, raw), rules, lines.append, path)
    return values, from_entries, lines


def defaults_match_spec():
    d = S.defaults()
    check("default min_read", d["min_read"], 0.85)
    check("default neighbour_tolerance", d["neighbour_tolerance"], 5)
    check("default tag_shot_name", d["tag_shot_name"], "Assisted Tagging|Identification|Shot")
    check("default tag_burst", d["tag_burst"] is True, True)
    check("schema length", len(S.SETTINGS_SCHEMA), 6 + 11 + 21 + 12)
    check("family defaults", {k: v for k, v in d.items() if k.startswith("family_")}, {
        "family_colour": True, "family_colour_root": "Assisted Tagging|Colour",
        "family_number": True, "family_number_root": "Motorsport|Number",
        "family_team": True, "family_team_root": "Motorsport|Team",
        "family_driver": True, "family_driver_root": "Motorsport|Driver",
        "family_extra": True, "family_extra_root": "Motorsport|Class",
        "family_vehicle": True, "family_vehicle_root": "Motorsport|Vehicle"})


def removed_keys_stop_the_load():
    for old, new in (("colour_tags", "family_colour"), ("tag_colour", "family_colour"),
                     ("tag_colour_name", "family_colour_root")):
        try:
            load({old: True})
            msg = "(no error)"
        except S.SettingsError as e:
            msg = str(e)
        check(f"removed {old} in settings.json", msg, f'settings.json: {old} was removed; use {new} (README, "Tag families")')
    for rules, key, new in (({"colour_tags": True}, "rules.colour_tags", "family_colour"),
                            ({"diagnostics": {"colour": "Cars|Paint"}}, "rules.diagnostics.colour", "family_colour_root")):
        try:
            load(None, rules)
            msg = "(no error)"
        except S.SettingsError as e:
            msg = str(e)
        check(f"removed {key} in entries.json", msg,
              f'entries.json: {key} was removed; use {new} in settings.json (README, "Tag families")')


def set_removed_model_key_stops():
    for key in ("ocr_rec_file", "embedder_file"):
        try:
            load({key: "x.onnx"})
            msg = "(no error)"
        except S.SettingsError as e:
            msg = str(e)
        check(f"removed {key} set in settings.json", msg,
              f'settings.json: {key} was removed; the plugin picks the model now (README, "Models")')


def blank_removed_model_key_is_ignored():
    v, fe, lines = load({"embedder_file": "", "ocr_rec_file": "  "})
    check("blank removed model keys load", ("embedder_file" in v, "ocr_rec_file" in v), (False, False))
    check("blank removed model keys log nothing", lines, [])


def family_roots_are_only_stripped():
    v, fe, lines = load({"family_team_root": "  A|B  ", "family_number_root": "", "family_driver": False})
    check("family root stripped", v["family_team_root"], "A|B")
    check("empty family root is the default", v["family_number_root"], "Motorsport|Number")
    check("family switch read", v["family_driver"], False)
    check("family settings log nothing", lines, [])


def file_wins_over_rules():
    v, fe, lines = load({"order_weight": 0.3}, {"order_weight": 0.5})
    check("file wins: value", v["order_weight"], 0.3)
    check("file wins: from entries", fe, ())
    check("file wins: log", lines, [])


def rules_fallback_logs():
    v, fe, lines = load(None, {"order_weight": 0.5, "min_read": 0.9})
    check("rules fallback: values", (v["order_weight"], v["min_read"]), (0.5, 0.9))
    check("rules fallback: from entries", fe, ("order_weight", "min_read"))
    check("rules fallback: log", lines, [
        "rules.order_weight in entries.json is deprecated; move it to settings.json",
        "rules.min_read in entries.json is deprecated; move it to settings.json"])


def invalid_file_value_logs_and_falls_through():
    v, fe, lines = load({"min_read": 2}, {"min_read": 0.9})
    check("invalid file value: falls to rules", v["min_read"], 0.9)
    check("invalid file value: one log line", len(lines), 1)
    check("invalid file value: names key and file",
          "min_read" in lines[0] and "settings.json" in lines[0], True)


def blank_is_absent():
    v, fe, lines = load({"order_weight": ""})
    check("blank: value", v["order_weight"], 0)
    check("blank: log", lines, [])


def bool_is_not_a_number():
    v, fe, lines = load({"colour_weight": True})
    check("bool as number: value", v["colour_weight"], 0)
    check("bool as number: log", len(lines), 1)
    v, fe, lines = load({"neighbour_tolerance": 3.5})
    check("fraction as integer: value", v["neighbour_tolerance"], 5)
    check("fraction as integer: log", len(lines), 1)


def bom_accepted():
    v, fe, lines = load(raw=b"\xef\xbb\xbf" + json.dumps({"min_read": 0.6}).encode())
    check("bom: value", v["min_read"], 0.6)
    check("bom: log", lines, [])


def non_object_file_counts_as_empty():
    v, fe, lines = load(raw=b"[1, 2]")
    check("non-object file: defaults", v, S.defaults())
    check("non-object file: one log line", len(lines), 1)


def diag_names_from_rules():
    v, fe, lines = load(None, {"diagnostics": {"burst": "Cars|Burst"}})
    check("diag name: value", v["tag_burst_name"], "Cars|Burst")
    check("diag name: from entries", "tag_burst_name" in fe, True)
    check("diag name: diagnostics_of", ("burst", "Cars|Burst") in S.diagnostics_of(v), True)


def empty_diag_turns_switch_off():
    v, fe, lines = load(None, {"diagnostics": {"burst": ""}})
    check("empty diag: switch", v["tag_burst"], False)
    check("empty diag: name stays default", v["tag_burst_name"], S.DIAG_DEFAULTS["burst"])
    check("empty diag: from entries", "tag_burst" in fe, True)
    check("empty diag: diagnostics_of", ("burst", "") in S.diagnostics_of(v), True)


def unknown_diagnostic_logs():
    v, fe, lines = load(None, {"diagnostics": {"colur": "X|Y"}})
    check("unknown diagnostic: log line", lines, ["entries.json: rules.diagnostics.colur unknown, ignored"])
    check("unknown diagnostic: defaults", (v, fe), (S.defaults(), ()))


def non_object_diagnostics_logs():
    v, fe, lines = load(None, {"diagnostics": ["burst"]})
    check("non-object diagnostics: log line", lines, ["entries.json: rules.diagnostics must be an object, ignored"])
    check("non-object diagnostics: defaults", (v, fe), (S.defaults(), ()))


def shot_base_from_three_paths():
    v, fe, lines = load(None, {"diagnostics": {
        "shot_solo": "A|B|Solo", "shot_pack": "A|B|Pack", "shot_crowded": "A|B|Crowded"}})
    check("shot base: value", v["tag_shot_name"], "A|B")
    check("shot base: from entries", "tag_shot_name" in fe, True)
    v, fe, lines = load(None, {"diagnostics": {
        "shot_solo": "A|B|Solo", "shot_pack": "X|Pack", "shot_crowded": "A|B|Crowded"}})
    check("shot mismatch: default base", v["tag_shot_name"], "Assisted Tagging|Identification|Shot")
    check("shot mismatch: one log line", len(lines), 1)
    check("shot mismatch: log names all three",
          all(s in lines[0] for s in ("A|B|Solo", "X|Pack", "A|B|Crowded")), True)


def diagnostics_of_shot_leaves():
    v = S.defaults()
    v["tag_shot_name"] = "A|B"
    d = dict(S.diagnostics_of(v))
    check("shot leaves", (d["shot_solo"], d["shot_pack"], d["shot_crowded"]),
          ("A|B|Solo", "A|B|Pack", "A|B|Crowded"))
    v["tag_shot"] = False
    d = dict(S.diagnostics_of(v))
    check("shot off", (d["shot_solo"], d["shot_pack"], d["shot_crowded"]), ("", "", ""))
    check("diagnostics_of keys", list(d), list(S.DIAG_DEFAULTS))


def explicit_path_overrides_collection_file():
    d = folder({"min_read": 0.6})
    other = os.path.join(tempfile.mkdtemp(), "other.json")
    with open(other, "w", encoding="utf-8") as f:
        json.dump({"min_read": 0.7}, f)
    v, fe = S.load_settings(d, None, lambda s: None, other)
    check("explicit path", v["min_read"], 0.7)


def invalid_rules_value_logs():
    v, fe, lines = load(None, {"min_read": 2})
    check("invalid rules value: default", v["min_read"], 0.85)
    check("invalid rules value: from entries", fe, ())
    check("invalid rules value: one log line", len(lines), 1)
    check("invalid rules value: names key and entries.json",
          "min_read" in lines[0] and "entries.json" in lines[0], True)
    v, fe, lines = load(None, {"diagnostics": {"burst": "  "}})
    check("blank rules name: default", v["tag_burst_name"], S.DIAG_DEFAULTS["burst"])
    check("blank rules name: one log line", len(lines), 1)


def normalisation_and_edge_values():
    v, fe, lines = load({"min_face_px": 64.0})
    check("whole float for integer", (v["min_face_px"], type(v["min_face_px"]), lines), (64, int, []))
    v, fe, lines = load({"colour_weight": float("inf"), "margin": float("nan")})
    check("non-finite rejected", (v["colour_weight"], v["margin"], len(lines)), (0, 0.05, 2))
    v, fe, lines = load({"tag_burst_name": "  Cars|Burst  "})
    check("file name stripped", v["tag_burst_name"], "Cars|Burst")
    v, fe, lines = load({"tag_burst_name": "  "})
    check("file blank name invalid", (v["tag_burst_name"], len(lines)), (S.DIAG_DEFAULTS["burst"], 1))
    v, fe, lines = load(None, {"min_face_px": 0, "colour_weight": 0})
    check("zero from rules is not False", (v["min_face_px"], v["colour_weight"], fe), (48, 0, ("colour_weight",)))


def shot_edge_cases():
    v, fe, lines = load(None, {"diagnostics": {
        "shot_solo": "|Solo", "shot_pack": "|Pack", "shot_crowded": "|Crowded"}})
    check("empty shot base rejected", (v["tag_shot_name"], len(lines)), (S.defaults()["tag_shot_name"], 1))
    v, fe, lines = load({"tag_shot_name": "F|G"}, {"diagnostics": {
        "shot_solo": "A|B|Solo", "shot_pack": "X|Pack", "shot_crowded": "A|B|Crowded"}})
    check("file shot name silences mismatch log", (v["tag_shot_name"], lines), ("F|G", []))


def _lua_value(text):
    text = text.strip()
    if text in ("true", "false"):
        return text == "true"
    if text.startswith('"'):
        return text[1:-1]
    return float(text) if "." in text else int(text)


def lua_schema_parity():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "lua", "assisted_tagging.lua"), encoding="utf-8") as f:
        src = f.read()
    found = re.search(r"M\.PRESET_SCHEMA = \{(.*?)\n\}", src, re.S)
    check("lua PRESET_SCHEMA block found", found is not None, True)
    if found is None:
        return
    block = found.group(1)
    rows = re.findall(r'\{ key = "(\w+)", kind = "(\w+)"(?:, choices = \{([^}]*)\})?, default = ([^}]+) \}', block)
    check("lua schema keys", [r[0] for r in rows], [s.key for s in S.SETTINGS_SCHEMA])
    check("lua schema kinds", [r[1] for r in rows], [s.kind for s in S.SETTINGS_SCHEMA])
    check("lua schema choices", [tuple(re.findall(r'"(\w+)"', r[2])) for r in rows],
          [s.choices for s in S.SETTINGS_SCHEMA])
    check("lua schema defaults", [_lua_value(r[3]) for r in rows], [s.default for s in S.SETTINGS_SCHEMA])

    found = re.search(r"local SETTING_RANGES = \{(.*?)\n\}", src, re.S)
    check("lua SETTING_RANGES block found", found is not None, True)
    if found is None:
        return
    lua_ranges = {}
    for key, body in re.findall(r"(\w+) = \{([^}]*)\}", found.group(1)):
        fields = dict(re.findall(r"(\w+) = ([\w.]+)", body))
        lua_ranges[key] = (_lua_value(fields["lo"]) if "lo" in fields else None,
                           _lua_value(fields["hi"]) if "hi" in fields else None,
                           fields.get("lo_open") == "true", fields.get("hi_open") == "true",
                           fields.get("integer") == "true")
    py_ranges = {s.key: (s.lo, s.hi, s.lo_open, s.hi_open, s.integer) for s in S.SETTINGS_SCHEMA
                 if s.kind == "number"}
    check("lua SETTING_RANGES match lo/hi/lo_open/hi_open/integer",
          {k: lua_ranges.get(k, (None, None, False, False, False)) for k in py_ranges}, py_ranges)
    check("lua SETTING_RANGES name only number settings", sorted(set(lua_ranges) - set(py_ranges)), [])


for t in (defaults_match_spec, removed_keys_stop_the_load, set_removed_model_key_stops, blank_removed_model_key_is_ignored,
          family_roots_are_only_stripped, file_wins_over_rules, rules_fallback_logs,
          invalid_file_value_logs_and_falls_through, blank_is_absent, bool_is_not_a_number,
          bom_accepted, non_object_file_counts_as_empty, diag_names_from_rules,
          empty_diag_turns_switch_off, unknown_diagnostic_logs, non_object_diagnostics_logs, shot_base_from_three_paths, diagnostics_of_shot_leaves,
          explicit_path_overrides_collection_file, invalid_rules_value_logs,
          normalisation_and_edge_values, shot_edge_cases, lua_schema_parity):
    t()

print(f"\n{failures} failure(s)")
sys.exit(1 if failures else 0)

"""A collection's settings: one schema, resolved from settings.json, then the old `rules`
block of entries.json (deprecated, logged), then the defaults. Stdlib only."""

import json
import math
import os
import re
from dataclasses import dataclass

_BAD_TAG = re.compile(r'[,;"]')


@dataclass(frozen=True)
class Setting:
    key: str
    kind: str  # bool | number | string | choice
    default: object
    choices: tuple = ()
    lo: object = None
    hi: object = None
    lo_open: bool = False
    hi_open: bool = False
    integer: bool = False


DIAG_DEFAULTS = {
    "number": "Assisted Tagging|Identification|By number",
    "livery": "Assisted Tagging|Identification|By livery",
    "burst": "Assisted Tagging|Identification|By burst",
    # Neighbour aid (order_weight): a doubtful number read settled by the groups shot around it.
    "neighbour": "Assisted Tagging|Identification|By neighbour",
    # A doubtful number read that doesn't fit the groups shot around it; the entry tag stays.
    "check_order": "Assisted Tagging|Identification|Check order",
    "team": "Assisted Tagging|Identification|Team only",
    "none": "Assisted Tagging|Identification|Unidentified",
    # Suffixed with the literal digits read, e.g. "...|Number seen|115": independent of
    # the outcome above, applied whenever OCR read a number that matched zero or 2+ entries.
    "number_seen": "Assisted Tagging|Identification|Number seen",
    # Suffixed with the car's body colour, e.g. "...|Colour|Red" (colour_tags).
    "colour": "Assisted Tagging|Colour",
    # A confident number read whose entry's colour disagrees with the colour seen; the entry tag stays.
    "check_colour": "Assisted Tagging|Identification|Check colour",
    # Written instead of "livery"/"team" when burst_livery_pooling resolved a frame
    # that didn't clear the threshold on its own.
    "pooled": "Assisted Tagging|Identification|By pooled burst",
    # One per image, from how many vehicles were boxed (see match.shot_type).
    "shot_solo": "Assisted Tagging|Identification|Shot|Solo",
    "shot_pack": "Assisted Tagging|Identification|Shot|Pack",
    "shot_crowded": "Assisted Tagging|Identification|Shot|Crowded",
}

SHOT_LEAVES = (("shot_solo", "Solo"), ("shot_pack", "Pack"), ("shot_crowded", "Crowded"))

TOGGLE_KEYS = ("number", "livery", "burst", "pooled", "neighbour", "check_order", "team", "none",
               "number_seen", "colour", "check_colour", "shot")

MOVED_RULES = ("order_weight", "neighbour_tolerance", "min_read", "colour_weight", "colour_tags",
               "partial_references", "min_sim", "margin", "min_face_px", "burst_livery_pooling",
               "blur_references")

_SHOT_BASE = "Assisted Tagging|Identification|Shot"


def _schema() -> tuple:
    out = [
        Setting("use_hints", "bool", True),
        Setting("group_support", "choice", "native", choices=("native", "tags", "none")),
        Setting("group_node", "string", ""),
        Setting("run_tag", "bool", False),
        Setting("suggest_crops", "bool", False),
        Setting("quarantine", "bool", False),
        Setting("embedder_file", "string", ""),
        Setting("ocr_rec_file", "string", ""),
        Setting("order_weight", "number", 0, lo=0, hi=1),
        Setting("neighbour_tolerance", "number", 5, lo=0, integer=True),
        Setting("min_read", "number", 0.85, lo=0, hi=1),
        Setting("colour_weight", "number", 0, lo=0),
        Setting("colour_tags", "bool", False),
        Setting("partial_references", "bool", False),
        Setting("min_sim", "number", 0.5, lo=0, hi=1, lo_open=True),
        Setting("margin", "number", 0.05, lo=0, hi=1, hi_open=True),
        Setting("min_face_px", "number", 48, lo=1, integer=True),
        Setting("burst_livery_pooling", "bool", False),
        Setting("blur_references", "bool", False),
    ]
    for k in TOGGLE_KEYS:
        out.append(Setting(f"tag_{k}", "bool", True))
        name = _SHOT_BASE if k == "shot" else DIAG_DEFAULTS[k]
        out.append(Setting(f"tag_{k}_name", "string", name))
    return tuple(out)


SETTINGS_SCHEMA = _schema()
_BY_KEY = {s.key: s for s in SETTINGS_SCHEMA}


def defaults() -> dict:
    return {s.key: s.default for s in SETTINGS_SCHEMA}


def _blank(v) -> bool:
    return v is None or (isinstance(v, str) and v == "")


def _coerce(s: Setting, v):
    """(ok, normalised value): strings are stripped, whole floats become ints."""
    if s.kind == "bool":
        return isinstance(v, bool), v
    if s.kind == "choice":
        return v in s.choices, v
    if s.kind == "string":
        if not isinstance(v, str):
            return False, v
        v = v.strip()
        if s.key.endswith("_name") and (not v or _BAD_TAG.search(v)):
            return False, v
        return True, v
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return False, v
    if s.integer:
        if isinstance(v, float) and not v.is_integer():
            return False, v
        v = int(v)
    if s.lo is not None and (v <= s.lo if s.lo_open else v < s.lo):
        return False, v
    if s.hi is not None and (v >= s.hi if s.hi_open else v > s.hi):
        return False, v
    return True, v


def _read_file(path: str, log) -> dict:
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        log(f"settings.json: unreadable ({e}), using defaults")
        return {}
    if not isinstance(data, dict):
        log("settings.json: not a JSON object, using defaults")
        return {}
    return data


def _rules_values(rules_raw) -> dict:
    """Old entries.json rules as settings keys: key -> (raw value, label for log lines)."""
    out = {}
    if not isinstance(rules_raw, dict):
        return out
    for k in MOVED_RULES:
        if k in rules_raw:
            out[k] = (rules_raw[k], f"rules.{k}")
    diag = rules_raw.get("diagnostics")
    if isinstance(diag, dict):
        for k in TOGGLE_KEYS:
            if k == "shot" or k not in diag:
                continue
            label = f"rules.diagnostics.{k}"
            if isinstance(diag[k], str) and diag[k] == "":
                out[f"tag_{k}"] = (False, label)
            else:
                out[f"tag_{k}_name"] = (diag[k], label)
    return out


def _shot_from_rules(diag, log_mismatch, log):
    """The three old shot_* paths as (key, value) when they share one non-empty base; else None."""
    if not isinstance(diag, dict) or not any(k in diag for k, _ in SHOT_LEAVES):
        return None
    given = [diag.get(k, DIAG_DEFAULTS[k]) for k, _ in SHOT_LEAVES]
    if all(g == "" for g in given):
        return ("tag_shot", False)
    bases = {g[:-len("|" + leaf)] if isinstance(g, str) and g.endswith("|" + leaf) else None
             for g, (_, leaf) in zip(given, SHOT_LEAVES)}
    if len(bases) == 1 and None not in bases and "" not in bases:
        return ("tag_shot_name", bases.pop())
    if log_mismatch:
        log("rules.diagnostics shot_solo/shot_pack/shot_crowded in entries.json do not share one base "
            f"({given[0]!r}, {given[1]!r}, {given[2]!r}); using the default shot tag")
    return None


def load_settings(collection_dir: str, rules_raw, log, path: str = "") -> tuple[dict, tuple[str, ...]]:
    """Every schema key resolved: settings.json, else the old entries.json rules, else the default.

    Returns (values, keys that came from rules_raw)."""
    file_vals = _read_file(path or os.path.join(collection_dir, "settings.json"), log)
    old = _rules_values(rules_raw)
    diag = rules_raw.get("diagnostics") if isinstance(rules_raw, dict) else None
    if isinstance(rules_raw, dict) and "diagnostics" in rules_raw:
        if not isinstance(diag, dict):
            log("entries.json: rules.diagnostics must be an object, ignored")
        else:
            for k in diag:
                if k not in DIAG_DEFAULTS:
                    log(f"entries.json: rules.diagnostics.{k} unknown, ignored")
    shot = _shot_from_rules(diag, _blank(file_vals.get("tag_shot_name")), log)
    if shot is not None:
        old[shot[0]] = (shot[1], "rules.diagnostics.shot_*")
    values = defaults()
    from_entries = []
    for s in SETTINGS_SCHEMA:
        fv = file_vals.get(s.key)
        file_bad = False
        if not _blank(fv):
            ok, val = _coerce(s, fv)
            if ok:
                values[s.key] = val
                continue
            file_bad = True
        if s.key in old and not _blank(old[s.key][0]):
            raw, label = old[s.key]
            ok, val = _coerce(s, raw)
            if ok:
                values[s.key] = val
                from_entries.append(s.key)
                if not file_bad:
                    log(f"{label} in entries.json is deprecated; move it to settings.json")
            else:
                log(f"entries.json: {label} invalid, using {s.default!r}")
        if file_bad:
            log(f"settings.json: {s.key} invalid, using {values[s.key]!r}")
    return values, tuple(from_entries)


def diagnostics_of(values: dict) -> tuple[tuple[str, str], ...]:
    """The Rules.diagnostics shape: (diagnostic key, tag path or "" when off)."""
    out = []
    for k in DIAG_DEFAULTS:
        if k.startswith("shot_"):
            continue
        out.append((k, values[f"tag_{k}_name"] if values[f"tag_{k}"] else ""))
    shot_on = values["tag_shot"]
    base = values["tag_shot_name"]
    out.extend((k, f"{base}|{leaf}" if shot_on else "") for k, leaf in SHOT_LEAVES)
    return tuple(out)

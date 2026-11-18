"""Assisted Tagging: identify the vehicles in each frame of a manifest and
write one result row per vehicle for assisted_tagging.lua.

Modes:
  identify.py MANIFEST RESULTS ...            id,filepath,burst_id[,protected tags,hint prefixes,capture epoch] →
                                              id,box,method,entry,alt_entry,confidence,unmatched_number,shot,order_flag,colour,colour_flag,sponsor,anchor_flag
                                              (+ --boxes-out: the per-vehicle boxes.json)
  identify.py MANIFEST RESULTS --add-reference id,filepath,entry_id → id,status
  identify.py MANIFEST RESULTS --promote-boxes --boxes-in F   id,filepath,"" → id,status
                                              (confident vehicles from a run's boxes.json become references)
  identify.py MANIFEST RESULTS --audit-refs [--suggest-crops] [--quarantine]   (manifest unused) → name,count per audit total, then report,<ref-audit.txt path>
  identify.py - - --list                      collection names (+ entries.csv, rules.csv)

Every mode that reads a collection also writes its tag-plan.txt: the exact tags
each outcome writes, from entries.json.

Exit codes: 0 ok, 2 bad input (message on stderr), 3 missing package, 130 cancelled."""

import argparse
import concurrent.futures
import csv
import hashlib
import json
import multiprocessing.util
import os
import re
import shutil
import sqlite3
import sys
import time
from collections import Counter
from dataclasses import dataclass, field, replace

from vehicles import HIRES_ASPECT_TOL, HIRES_MIN_GAIN, MAX_BOXES, crop_box, detect, detect_vehicles, load_hires, log
from vehicle_detect import DetectionCache, boxes_in, decode_rgb, decode_rgb_sized, detect_cached, file_key, load_detector
from common import atomic_write
from ocr import NUMBER_MIN_HEIGHT, OCR_CROP_DIM, OCR_MIN_SCORE, NumberReader, ocr_key
import car_colour
import entries_file
from colour import colour_hist
from embed import Embedder, decode, embedder_key, encode
from fingerprint import analysis_fingerprint
from match import (HAND, MATCH_MIN_MARGIN, MATCH_MIN_SIM, NUMBER_LIST_FLOOR, NUMBER_LIST_MARGIN, WEAK_READ_MIN, BoxResult, Entry, agreeing_reads, already_tagged, usable_reads,
                   burst_colours, burst_consensus, closer_car_match, colour_check, colour_pool, conflicts, decided_by, disagrees, entries_under, hinted_match, main_car_only, match_camera, sure_cars,
                   match_livery, match_team, pool_sims, promotable, shot_type, team_key, TEAM_KEY)
from neighbour import neighbour_aid, with_library_neighbours
from overlap import HIDDEN, _inter, visible_boxes
from segment import SEGMENT_CACHE_TOKEN, Segmenter, needs_mask, segmenter_path
from siglip import BOX_KEEP_SCORE, CAR, SigLIP, siglip_key
from pod import pod_colour, pod_reading
from rescue import RESCUE_MIN_SIM, plan_burst
from sponsors import sponsor_prefixes, sponsor_words
from report import write_report
from kinds import DEFAULT_KIND, check_entry_fields, check_kind
from settings import DIAG_DEFAULTS, MOVED_RULES, SettingsError, diagnostics_of, load_settings
from families import FAMILIES, family_tag, resolve, team_tags
from reference_store import ANCHOR_MIN_READ, ANCHOR_MIN_SIM, Anchors, ReferenceIndex
from people import FACE_EMBED_DIM, FaceModel, face_model_key
from people_run import analyse_frame_people, build_boxes_people, match_frame_people, reference_face

MAX_WORKERS = 4  # each worker holds every model plus a full-resolution decode
CACHE_MAX_AGE_DAYS = 90
CACHE_COMMIT_EVERY = 50
ANCHOR_CHECKED = ("livery", "pooled", "burst", "neighbour")  # methods whose match must look like the car's anchors; number, hand and team never are

# , ; " break the CSV handoff to Lua; the rest can't appear in a Windows folder name
_BAD_ID = re.compile(r'[,;"/\\:*?<>|]')
_BAD_TAG = re.compile(r'[,;"]')


class InputError(Exception):
    """Bad input the user fixes (entries.json, a model path): exit 2, message on stderr."""


# ---------------------------------------------------------------- entries and rules

TEAM_ONLY_CHOICES = ("shared tags", "none")


@dataclass(frozen=True)
class Rules:
    """What each outcome tags: the resolved settings (settings.json, --settings, or the old entries.json rules)
    plus entries.json's entries-only rules. An empty diagnostic name writes no tag."""
    team_only: str = "shared tags"
    unidentified: tuple = ()
    diagnostics: tuple = tuple(DIAG_DEFAULTS.items())
    # Experimental: pool box-0 livery similarity across a burst's frames and re-run the
    # livery/team decision once on the average, for frames number didn't resolve.
    burst_livery_pooling: bool = False
    # "solo": each photo is of one car, its largest box (match.main_car_only); "packs": every box
    # is tagged, for racing where several cars share a shot.
    cars_per_photo: str = "solo"
    # A match unlike its car's anchors moves to the car whose anchors it is closer to by this much
    # similarity or more (match.closer_car_match) instead of being dropped; 0: always dropped.
    closer_car_margin: float = 0.0
    # Experimental: embed references after downscaling-then-upscaling them (embed.degrade),
    # so their embeddings sit closer to a far-away query crop's degraded detail level.
    blur_references: bool = False
    # ((lowercase keyword, tag prefix), …): a sponsor word read on a car hints its team's prefix
    # (see sponsors.sponsor_prefixes). Empty: off.
    sponsor_keywords: tuple = ()
    # ((keyword, tag value), …): how the Sponsor family spells a keyword ("dhl" → "DHL"); a keyword
    # not listed is title-cased.
    sponsor_names: tuple = ()
    # Solo shots carrying only a team tag are accepted as team-level references.
    partial_references: bool = False
    # Which pipeline the collection runs (kinds.KINDS). The three below only steer `people`: a face
    # is tagged when its entry scores at least min_sim, leads the runner-up by margin, and is at
    # least min_face_px wide.
    kind: str = DEFAULT_KIND
    min_sim: float = 0.50
    margin: float = 0.05
    min_face_px: int = 48
    # Motorsport: how much a car's colour histogram counts next to its embedding when scoring references
    # (reference_store.best_per_entry). 0 turns colour off.
    colour_weight: float = 0.0
    # Motorsport: {family key: root tag} for each tag family switched on (families.resolve). An entry's
    # number, team and name each become a tag under their root (see _entry_tags); "colour" in it turns
    # on reading each car's body colour (car_colour). People collections have none.
    families: dict = field(default_factory=dict)
    # Motorsport: how much the groups shot just before and after a photo help a doubtful number read
    # (neighbour.neighbour_aid): 0 ignores them (random order), 1 expects the numbers strictly in order.
    order_weight: float = 0.0
    # Motorsport: how many entries apart (in the sorted number list, wrapping round) a nearby group can be
    # and still support a doubtful read; used when the order weight is above 0.
    neighbour_tolerance: int = 5
    # Motorsport: the least confidence (lower of text detection and the reader's own) a number read needs
    # to count. Weaker reads stay in the box's OCR trace but name nothing.
    min_read: float = 0.85
    # ((tag name, ((hue_lo, hue_hi, sat_lo, sat_hi, val_lo, val_hi), ...)), ...): the colours read, in output order.
    colour_palette: tuple = car_colour.PALETTE


def _entry_tags(eid: str, item: dict, roots: dict, bad) -> tuple:
    """An entry's tags: one per family in `roots` the entry has a value for (its source fields joined
    with |), then its own `tags` as extras, without repeats. The caller has checked the values."""
    extra = item.get("tags", [])
    _check_tags(extra, f'entry "{eid}": tags', bad, allow_empty=True)
    built = []
    for fam in FAMILIES:
        value = "|".join(v for v in (str(item.get(s, "")) for s in fam.sources) if v)
        if value and fam.key in roots:
            built.append(family_tag(roots[fam.key], value))
    if not built and not extra:
        raise bad(f'entry "{eid}": builds no tag; turn on a family it has a value for, or give it tags')
    return tuple(dict.fromkeys(built + extra))


def _check_tags(tags, where: str, bad, allow_empty: bool = False):
    if not isinstance(tags, list) or (not tags and not allow_empty) \
            or not all(isinstance(t, str) and t.strip() for t in tags):
        raise bad(f"{where} must be a {'' if allow_empty else 'non-empty '}list of tag names")
    for t in tags:
        if _BAD_TAG.search(t):
            raise bad(f'{where}: tag "{t}" can\'t contain , ; or "')


def _load_palette(raw, bad) -> tuple:
    """rules.colour_palette → the PALETTE shape: {tag name: built-in name | [{"hue": [lo, hi], "sat": [lo, hi], "val": [lo, hi]}, ...]}.
    A missing sat or val is the full range (0, 255); hue is required."""
    if not isinstance(raw, dict) or not raw:
        raise bad("rules.colour_palette must be an object mapping tag names to a built-in colour name or a list of bounds")
    builtin = dict(car_colour.PALETTE)
    out = []
    for name, spec in raw.items():
        if not name.strip() or _BAD_TAG.search(name) or "|" in name or name == car_colour.MULTI:
            raise bad(f'rules.colour_palette: "{name}" must be a tag name without | , ; " and not "{car_colour.MULTI}"')
        if isinstance(spec, str):
            if spec not in builtin:
                raise bad(f'rules.colour_palette.{name}: "{spec}" is not a built-in colour ({", ".join(builtin)})')
            out.append((name, builtin[spec]))
            continue
        if not isinstance(spec, list) or not spec:
            raise bad(f"rules.colour_palette.{name} must be a built-in colour name or a non-empty list of bounds")
        ranges = []
        for item in spec:
            if not isinstance(item, dict) or "hue" not in item or set(item) - {"hue", "sat", "val"}:
                raise bad(f'rules.colour_palette.{name}: each bounds object needs "hue" and may have "sat" and "val"')
            bounds = []
            for key, top in (("hue", 179), ("sat", 255), ("val", 255)):
                lo_hi = item.get(key, [0, 255])
                if not (isinstance(lo_hi, list) and len(lo_hi) == 2
                        and all(isinstance(v, int) and not isinstance(v, bool) for v in lo_hi)
                        and 0 <= lo_hi[0] <= lo_hi[1] <= top):
                    raise bad(f"rules.colour_palette.{name}.{key} must be [lo, hi] whole numbers, 0 to {top}, lo at most hi")
                bounds.extend(lo_hi)
            ranges.append(tuple(bounds))
        out.append((name, tuple(ranges)))
    return tuple(out)


def _load_rules(raw, bad) -> dict:
    """The entries.json-only rules as Rules fields; moved options come from settings.load_settings."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise bad('"rules" must be an object')
    if "tag_prefix" in raw:
        raise bad('rules.tag_prefix was removed; set family_number_root, family_team_root and family_driver_root '
                  'in settings.json (README, "Tag families")')
    unknown = sorted(set(raw) - {"team_only", "unidentified", "sponsor_keywords", "sponsor_names", "colour_palette",
                                  "diagnostics", "colour_tags", *MOVED_RULES})
    if unknown:
        raise bad(f'unknown rule "{unknown[0]}" (rules are team_only, unidentified, sponsor_keywords, sponsor_names, '
                   f'colour_palette; behaviour settings such as order_weight go in settings.json)')
    defaults = Rules()
    colour_palette = _load_palette(raw["colour_palette"], bad) if "colour_palette" in raw else defaults.colour_palette
    sponsors = raw.get("sponsor_keywords", {})
    if not isinstance(sponsors, dict) or not all(
            isinstance(k, str) and k.strip() and k == k.lower() and not _BAD_TAG.search(k) and "|" not in k
            and isinstance(v, str) and v.strip()
            and not _BAD_TAG.search(v) for k, v in sponsors.items()):
        raise bad("rules.sponsor_keywords must map lowercase keywords to tag prefixes")
    names = raw.get("sponsor_names", {})
    if not isinstance(names, dict) or not all(
            k in sponsors and isinstance(v, str) and v.strip() and not _BAD_TAG.search(v) and "|" not in v
            for k, v in names.items()):
        raise bad("rules.sponsor_names must map sponsor_keywords words to tag values without , ; \" or |")
    team_only = raw.get("team_only", "shared tags")
    if team_only not in TEAM_ONLY_CHOICES:
        raise bad('rules.team_only must be "shared tags" or "none"')
    unidentified = raw.get("unidentified", [])
    _check_tags(unidentified, "rules.unidentified", bad, allow_empty=True)
    return dict(team_only=team_only, unidentified=tuple(unidentified), sponsor_keywords=tuple(sponsors.items()),
                sponsor_names=tuple((k, v.strip()) for k, v in names.items()), colour_palette=colour_palette)


def _pair_cars(entries: dict, bad):
    """Checks each `car` (an entry names the lower-numbered entry of the car it shares) and gives
    both entries the union of their tags (the named entry's first) and `car` set to the named id."""
    named: dict = {}
    for e in entries.values():
        if not e.car:
            continue
        if e.car == e.id:
            raise bad(f'entry "{e.id}": car names itself')
        if e.car not in entries:
            raise bad(f'entry "{e.id}": car "{e.car}" is not an entry id')
        if entries[e.car].car:
            raise bad(f'entry "{e.id}": car "{e.car}" names another car itself; name the lower entry of the pair')
        if e.car in named:
            raise bad(f'entries "{named[e.car]}" and "{e.id}" both share car "{e.car}"; a car has two entries at most')
        named[e.car] = e.id
    for first_id, second_id in named.items():
        first, second = entries[first_id], entries[second_id]
        tags = first.tags + tuple(t for t in second.tags if t not in first.tags)
        entries[first_id] = replace(first, tags=tags, car=first_id)
        entries[second_id] = replace(second, tags=tags, car=first_id)


def load_collection(collection_dir: str, settings_path: str = "") -> tuple:
    """entries.json + settings.json → ({id: Entry} in file order, Rules, the settings keys that came from
    entries.json rules). The file is either a list of entries or {"rules": {...}, "entries": [...]}.
    Raises InputError naming the file."""
    path = os.path.join(collection_dir, "entries.json")

    def bad(why):
        return InputError(f"{path}: {why}")

    try:
        upgraded = entries_file.upgrade(path)
    except (OSError, UnicodeDecodeError):  # before ValueError: UnicodeDecodeError is one
        upgraded = 0  # the read below reports it
    except ValueError as e:
        raise bad(str(e))
    if upgraded:
        log(f"entries.json: {upgraded} entries upgraded (class, make/model → fields)")
    try:
        with open(path, encoding="utf-8-sig") as f:  # Notepad saves a BOM
            data = json.load(f)
    except FileNotFoundError:
        raise bad("file not found")
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise bad(f"not valid JSON ({e})")
    rules_raw = None
    if isinstance(data, dict):
        unknown = sorted(set(data) - {"kind", "rules", "entries"})
        if unknown:
            raise bad(f'unknown key "{unknown[0]}" (the file holds "kind", "rules" and "entries")')
        kind_raw, rules_raw, data = data.get("kind", DEFAULT_KIND), data.get("rules"), data.get("entries")
    else:
        kind_raw = DEFAULT_KIND
    try:
        kind = check_kind(kind_raw)
    except ValueError as e:
        raise bad(str(e))
    if not isinstance(data, list):
        raise bad('"entries" must be a list of entries')
    own_rules = _load_rules(rules_raw, bad)
    try:
        values, from_entries = load_settings(collection_dir, rules_raw, log, settings_path)
    except SettingsError as e:
        raise InputError(str(e))
    try:
        roots = {} if kind == "people" else resolve(values)
    except ValueError as e:
        raise InputError(f"settings.json: {e}")
    rules = Rules(**own_rules, **{k: values[k] for k in MOVED_RULES},
                  cars_per_photo=values["cars_per_photo"], closer_car_margin=values["closer_car_margin"], diagnostics=diagnostics_of(values), kind=kind,
                  families=roots)
    entries = {}
    for n, item in enumerate(data, 1):
        if not isinstance(item, dict):
            raise bad(f"entry {n} is not an object")
        eid = item.get("id")
        if not isinstance(eid, str) or not eid.strip():
            raise bad(f"entry {n} has no id")
        if _BAD_ID.search(eid):
            raise bad(f'entry "{eid}": id can\'t contain any of , ; " / \\ : * ? < > |')
        if eid in entries:
            raise bad(f'entry "{eid}" appears twice')
        unknown = check_entry_fields(kind, item)
        if unknown:
            fields = "id, tags" if kind == "people" else "id, number, team, name, co_driver, extra, make, model, tags, camera, colour, car, shows, paddock"
            raise bad(f'entry "{eid}": unknown field "{unknown}" (fields are {fields})')
        if kind == "people":
            _check_tags(item.get("tags"), f'entry "{eid}": tags', bad)
            entries[eid] = Entry(eid, "", "", tuple(item["tags"]))
            continue
        number = item.get("number", "")
        number = str(number) if isinstance(number, int) and not isinstance(number, bool) else number
        if not isinstance(number, str) or (number and not re.fullmatch(r"\d{1,3}", number)):
            raise bad(f'entry "{eid}": number must be 1–3 digits')
        team = item.get("team", "")
        if not isinstance(team, str) or _BAD_TAG.search(team):
            raise bad(f'entry "{eid}": team must be text without , ; or "')
        name = item.get("name", "")
        if not isinstance(name, str) or _BAD_TAG.search(name):
            raise bad(f'entry "{eid}": name must be text without , ; or "')
        co_driver = item.get("co_driver", "")
        if not isinstance(co_driver, str) or _BAD_TAG.search(co_driver):
            raise bad(f'entry "{eid}": co_driver must be text without , ; or "')
        for key in ("extra", "make", "model"):
            value = item.get(key, "")
            if not isinstance(value, str) or _BAD_TAG.search(value) or "|" in value:
                raise bad(f'entry "{eid}": {key} must be text without , ; " or |')
        if item.get("model") and not item.get("make"):
            raise bad(f'entry "{eid}": model {item["model"]} has no make')
        camera = item.get("camera", "")
        if camera not in ("", "yellow", "black"):
            raise bad(f'entry "{eid}": camera must be "yellow" or "black"')
        colour = item.get("colour", "")
        colours = [n for n, _ in rules.colour_palette] + [car_colour.MULTI]
        if colour != "" and colour not in colours:
            raise bad(f'entry "{eid}": colour "{colour}" is not one of {", ".join(colours)}')
        car = item.get("car", "")
        if not isinstance(car, str):
            raise bad(f'entry "{eid}": car must be the id of the entry sharing the car')
        shows = item.get("shows", [])
        if not isinstance(shows, list) or not all(isinstance(s, str) and re.fullmatch(r"\d{1,3}", s) for s in shows):
            raise bad(f'entry "{eid}": shows must be a list of 1–3 digit numbers, e.g. ["44"]')
        if number in shows:
            raise bad(f'entry "{eid}": shows repeats its own number {number}')
        entries[eid] = Entry(eid, number, team, _entry_tags(eid, item, rules.families, bad), camera, colour, name, car,
                             co_driver, tuple(dict.fromkeys(shows)))
    if kind == "people":
        if rules_raw is None:
            log("warning: entries.json has no rules block, so the face thresholds use defaults")
        return entries, rules, from_entries
    _pair_cars(entries, bad)
    teams: dict = {}
    for e in entries.values():
        if e.team:
            teams.setdefault(e.team, []).append(e)
    no_pod = [e.id for es in teams.values() if len(es) > 1 for e in es if not e.camera]
    if no_pod:
        log(f"warning: teammates without a camera colour, so the pod can't separate them: {', '.join(no_pod)}")
    if rules_raw is None:
        log("warning: entries.json has no rules block, so sponsor keywords and the other rules use defaults")
    for word, prefix in rules.sponsor_keywords:
        if not entries_under(entries, [prefix]):
            raise bad(f'rules.sponsor_keywords.{word}: no entry has a tag under "{prefix}"')
    return entries, rules, from_entries


def write_entries_csv(entries: dict, path: str):
    with open(path, "w", newline="", encoding="utf-8") as f:
        for e in entries.values():
            f.write(f"{e.id},{e.team},{e.number},{';'.join(e.tags)},{e.name},{e.co_driver},{e.colour}\n")


def write_rules_csv(rules: Rules, from_entries: tuple, path: str):
    """key,value lines for assisted_tagging.lua: team_only, unidentified (tags joined by ;), diag_<outcome>,
    family_<key> (the root of each family that is on),
    each moved setting, and from_entries_json (the settings keys still read from entries.json, joined by ;)."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write(f"team_only,{rules.team_only}\n")
        f.write(f"unidentified,{';'.join(rules.unidentified)}\n")
        for key, name in rules.diagnostics:
            f.write(f"diag_{key},{name}\n")
        for key, root in rules.families.items():
            f.write(f"family_{key},{root}\n")
        for key in MOVED_RULES:
            v = getattr(rules, key)
            f.write(f"{key},{str(v).lower() if isinstance(v, bool) else v}\n")
        f.write(f"from_entries_json,{';'.join(from_entries)}\n")


def count_references(collection_dir: str) -> dict:
    refs = os.path.join(collection_dir, "refs")
    if not os.path.isdir(refs):
        return {}
    return {e: sum(n.lower().endswith(".jpg") for n in os.listdir(os.path.join(refs, e)))
            for e in os.listdir(refs) if os.path.isdir(os.path.join(refs, e))}


def tag_plan(name: str, entries: dict, rules: Rules, refs: dict) -> str:
    """The exact tags every outcome writes in this collection, for the user to read."""
    lines = [f"Tag plan for {name}", "", "Identified (by number, livery or burst): the vehicle's entry tags."]
    for e in entries.values():
        how = f"#{e.number}" if e.number else "no number, livery only"
        n = refs.get(e.id, 0)
        lines.append(f"  {e.id} ({how}{', ' + e.team if e.team else ''}; {n} reference{'s' if n != 1 else ''})")
        lines.extend(f"      {t}" for t in e.tags)
    lines += ["", f'Team only (teammates too close to call): rules.team_only = "{rules.team_only}".']
    teams: dict = {}
    for e in entries.values():
        if e.team:
            teams.setdefault(e.team, []).append(e)
    pairs = [(t, es) for t, es in teams.items() if len(es) > 1]
    if rules.team_only == "none":
        lines.append("  adds no collection tags, only the Team only diagnostic below.")
    elif not pairs:
        lines.append("  no two entries share a team, so this never happens.")
    for team, es in pairs:
        shared = [t for t in es[0].tags if all(t in o.tags for o in es[1:])]
        lines.append(f"  {team} ({', '.join(e.id for e in es)}):")
        lines.extend(f"      {t}" for t in shared) if shared else lines.append("      (no shared tags: adds nothing)")
    lines += ["", "unidentified tags (yours), written when no vehicle was found or no match was confident: rules.unidentified."]
    lines.extend(f"      {t}" for t in rules.unidentified) if rules.unidentified else lines.append("      (nothing)")
    lines += ["", "Diagnostics (only with the diagnostic tags preference on): rules.diagnostics."]
    lines.extend(f"  {k:<12} {v or '(off)'}" for k, v in rules.diagnostics)
    number_only = [e.id for e in entries.values() if not refs.get(e.id) and e.number]
    never = [e.id for e in entries.values() if not refs.get(e.id) and not e.number]
    if number_only:
        lines += ["", "No references yet, so identified by number only: " + ", ".join(number_only)]
    if never:
        lines += ["", "No number and no references, so never identified until references are added: "
                  + ", ".join(never)]
    unknown = sorted(set(refs) - set(entries))
    if unknown:
        lines += ["", "Reference folders with no entry (ignored): " + ", ".join(unknown)]
    return "\n".join(lines) + "\n"


def write_tag_plan(collection_dir: str, name: str, entries: dict, rules: Rules) -> str:
    path = os.path.join(collection_dir, "tag-plan.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(tag_plan(name, entries, rules, count_references(collection_dir)))
    return path


def list_collections(root: str) -> list:
    if not root or not os.path.isdir(root):
        return []
    names = [n for n in os.listdir(root) if os.path.isfile(os.path.join(root, n, "entries.json"))]
    return sorted(names, key=str.lower)


# ---------------------------------------------------------------- cache

class IdentifyCache:
    """Per-frame detections, OCR candidates and embeddings in SQLite, keyed by
    the file's identity, every model and the settings that change them.
    Matching isn't cached, so new references or entries apply without a
    re-decode. An empty path disables it."""

    def __init__(self, path: str):
        self.db, self.used, self.pending = None, [], 0
        if not path:
            return
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        try:
            self.db = sqlite3.connect(path, timeout=30)
            self.db.execute("CREATE TABLE IF NOT EXISTS frames "
                            "(key TEXT PRIMARY KEY, value TEXT NOT NULL, used REAL NOT NULL)")
            self.db.execute("DELETE FROM frames WHERE used < ?", (time.time() - CACHE_MAX_AGE_DAYS * 86400,))
            self.db.commit()
        except sqlite3.DatabaseError as e:
            raise InputError(f"cache {path} is unreadable ({e}); delete it to start a fresh one") from e

    @staticmethod
    def _key(parts) -> str:
        return json.dumps(list(parts), separators=(",", ":"))

    def get(self, *parts):
        if not self.db or any(p is None for p in parts):
            return None
        k = self._key(parts)
        row = self.db.execute("SELECT value FROM frames WHERE key = ?", (k,)).fetchone()
        if row is None:
            return None
        self.used.append(k)
        return json.loads(row[0])

    def put(self, value, *parts):
        if not self.db or any(p is None for p in parts):
            return
        self.db.execute("INSERT OR REPLACE INTO frames (key, value, used) VALUES (?, ?, ?)",
                        (self._key(parts), json.dumps(value), time.time()))
        self.pending += 1
        if self.pending >= CACHE_COMMIT_EVERY:
            self.db.commit()
            self.pending = 0

    def close(self):
        if not self.db:
            return
        now = time.time()
        self.db.executemany("UPDATE frames SET used = ? WHERE key = ?", [(now, k) for k in self.used])
        self.db.commit()
        self.db.close()
        self.db = None


def frame_key(filepath: str, models: dict) -> list:
    """Cache key parts for a frame's analysis: the file, every model file, the
    constants fingerprint and a token per cached stage (bumped on a code-only
    change to that stage). Entries and references stay out of it."""
    if models["kind"] == "people":
        return [file_key(filepath), "people", *face_model_key(models["face_det"], models["face_rec"]),
                analysis_fingerprint(), "face-1"]
    return [file_key(filepath), file_key(models["detector"]), ocr_key(models["ocr_det"], models["ocr_rec"]),
            embedder_key(models["embedder"]), analysis_fingerprint(),
            "ocr-trace-2", "read-conf-1", "ctc-1", "pod-2", "cand-1", "overlap-2", *(["colour-2"] if models.get("colour") else []),
            *(["car-colour-2", car_colour.palette_digest(models["car_colour"])] if models.get("car_colour") else []),
            *([SEGMENT_CACHE_TOKEN, file_key(models["segmenter"])] if models.get("segmenter") else []),
            *(siglip_key(models["siglip"]) if models.get("siglip") else []),
            *(["ocr-regions-1"] if models.get("ocr_regions") else [])]


# ---------------------------------------------------------------- progress

def write_progress(progress_path: str, cur: int, tot: int, stage: str = "", cached: int = 0):
    """Writes `stage,cur,tot,cached` (or `cur,tot` with no stage) for the Lua poll: `cached` of
    `cur` were done without work, so the ETA counts only the rest."""
    if not progress_path:
        return
    line = f"{stage},{cur},{tot},{cached}" if stage else f"{cur},{tot}"
    for _ in range(8):
        try:
            with open(progress_path, "w", encoding="utf-8") as pf:
                pf.write(line)
            return
        except OSError:
            time.sleep(0.02)


def cancel_requested(progress_path: str) -> bool:
    return bool(progress_path) and os.path.exists(progress_path + ".cancel")


# ---------------------------------------------------------------- per-frame analysis (workers)

_W: dict = {}


def _detection_tools(models: dict) -> tuple:
    """(loaded detector, shared detection cache) for this process, loaded on first use. The cache is
    closed by multiprocessing's finalizers, which run in the pool's workers as well as the parent
    (atexit handlers do not: workers leave through os._exit)."""
    if "detector" not in _W:
        _W["detector"] = load_detector(models["detector"])
        _W["detections"] = DetectionCache(models.get("detections", ""))
        multiprocessing.util.Finalize(None, _W["detections"].close, exitpriority=0)
    return _W["detector"], _W["detections"]


def frame_entry(filepath: str, rgb, models: dict) -> tuple:
    """(the frame's shared detection entry, whether it came from the cache)."""
    detector, cache = _detection_tools(models)
    return detect_cached(filepath, detector, cache, rgb=rgb)


def _init_worker(models: dict):
    try:
        import cv2
        cv2.setNumThreads(1)
    except Exception:
        pass
    _W["models"] = models
    if models["kind"] == "people":
        _W["faces"] = FaceModel(models["face_det"], models["face_rec"])
        return
    _W["reader"] = NumberReader(models["ocr_det"], models["ocr_rec"], keep_regions=bool(models.get("ocr_regions")))
    _W["embedder"] = Embedder(models["embedder"])
    _W["segmenter"] = Segmenter(models["segmenter"]) if models.get("segmenter") else None
    _siglip(models)  # the detector loads in frame_entry, on the first frame that detects


def _siglip(models: dict):
    """This process's SigLIP 2, loaded on first use, or None without one."""
    if "siglip" not in _W:
        _W["siglip"] = SigLIP(models["siglip"]) if models.get("siglip") else None
    return _W["siglip"]


def analyse_frame(filepath: str) -> dict:
    """Boxes, OCR candidates and embeddings for one frame: the cached value, plus `detection_cached`
    (whether the shared detection entry was already there), which run_frames pops off. Detection
    reads a fast small decode; the full-size decode runs only when a vehicle box passes. Boxes,
    candidates and `frame` are in full-size pixels either way."""
    if _W["models"]["kind"] == "people":
        return analyse_frame_people(decode_rgb(filepath), _W["faces"])
    small, (w, h) = decode_rgb_sized(filepath, fast_jpeg=True)
    entry, hit = frame_entry(filepath, small, _W["models"])
    boxes, weak, note = detect(small, entry)
    if boxes:
        rgb = decode_rgb(filepath)
        h, w = rgb.shape[:2]
        boxes, weak, note = detect(rgb, entry)
        boxes, vecs, dropped, contested = check_boxes(rgb, boxes)
        if dropped and not boxes:
            note = (f"no car: the box check dropped {sum(dropped.values())} boxes ("
                    + ", ".join(f"{c['answer']} {c['share']:.2f} at {c['score']:.2f}" for c in contested if not c["kept"]) + ")")
        out = _read_boxes(rgb, boxes, vecs=vecs)
        out["dropped"] = dropped
        out["contested"] = contested
    else:
        sh, sw = small.shape[:2]
        weak = boxes_in({"frame": [sw, sh], "boxes": weak}, w, h)
        out = _read_boxes(small, [])
    out.update(note=note, frame=[w, h], candidates=[list(b) for b in weak], detection_cached=hit)
    return out


def check_boxes(rgb, boxes: list) -> tuple:
    """The box check: (kept boxes, their SigLIP 2 image vectors or None, {answer: count} of the
    dropped ones, contested boxes). A box is dropped when SigLIP 2 calls it anything but a car
    (siglip.is_what) and the detector scored it below BOX_KEEP_SCORE; without SigLIP all are kept.
    Contested: {answer, share, score, kept} per box with a vehicle share under 0.5, kept being
    "share", "score" or False, for tuning the two thresholds from a run."""
    siglip = _W.get("siglip")
    if not siglip or not boxes:
        return boxes, None, {}, []
    kept, vecs, dropped, contested = [], [], {}, []
    for b in boxes:
        vec = siglip.embed_image(crop_box(rgb, b))
        what, share = siglip.is_what(vec)
        score = round(float(b[4]), 3)
        keep = "share" if what == CAR else "score" if score >= BOX_KEEP_SCORE else False
        if share < 0.5:
            contested.append({"answer": what, "share": share, "score": score, "kept": keep})
        if keep:
            kept.append(b)
            vecs.append(vec)
        else:
            dropped[what] = dropped.get(what, 0) + 1
    return kept, vecs, dropped, contested


def _read_boxes(rgb, boxes: list, hi=None, vecs=None, frame=None, wanted=None) -> dict:
    """OCR candidates, pod reading and embedding of each box, in the analysis shape. With `hi`, a
    sharper decode of the same frame, `rgb` is None and `frame` the preview's (w, h): the crops (OCR,
    embedding, colour) come from `hi`, boxes stay in preview pixels and pod is None. `wanted`, box
    indices, limits the reading to those boxes; the others hold None in every per-box list. `vecs`,
    the box check's SigLIP 2 vectors of the plain box crops, are reused for colour where the crop read
    is that same plain crop."""
    ocr, trace, ctc, emb, pod, hist, overlap, masked, shares, regions = [], [], [], [], [], [], [], [], [], []
    turns = {}
    palette = _W["models"].get("car_colour")
    keep_regions = _W["reader"].keep_regions
    scale = hi.shape[1] / frame[0] if hi is not None else 1.0
    seen_boxes = visible_boxes(boxes)
    wants_mask = needs_mask(boxes, [state for _, state in seen_boxes]) if _W.get("segmenter") else [False] * len(boxes)
    for i, (b, (seen, state)) in enumerate(zip(boxes, seen_boxes)):
        overlap.append(state)
        if wanted is not None and i not in wanted:
            for skipped in (pod, masked, ocr, trace, ctc, emb, *([hist] if _W["models"].get("colour") else []),
                            *([shares] if palette else []), *([regions] if keep_regions else [])):
                skipped.append(None)
            continue
        pod.append(pod_reading(rgb, seen) if hi is None else None)
        src, area = (rgb if hi is None else hi), tuple(v * scale for v in seen[:4])
        cut = None
        if wants_mask[i]:
            near = [tuple(v * scale for v in o[:4]) for j, o in enumerate(boxes) if j != i and _inter(b, o) > 0]
            cut = _W["segmenter"].cut(src, area, near)
        masked.append(cut is not None)
        crop = crop_box(*cut) if cut else crop_box(src, area)
        ocr.append([[d, c] for d, c in _W["reader"].read(crop_box(*(cut or (src, area)), OCR_CROP_DIM))])
        for turn, n in _W["reader"].last_turns.items():
            turns[turn] = turns.get(turn, 0) + n
        trace.append(_W["reader"].last_trace)
        ctc.append(_W["reader"].last_ctc)
        if keep_regions:
            regions.append(_W["reader"].last_regions)
        emb.append(encode(_W["embedder"].embed(crop)))
        if _W["models"].get("colour"):
            hist.append(encode(colour_hist(crop, masked=cut is not None)))
        if palette:
            plain = vecs and hi is None and cut is None and tuple(seen[:4]) == tuple(b[:4])
            shares.append({} if state == HIDDEN else colour_read(crop, palette, masked=cut is not None,
                                                                 vec=vecs[i] if plain else None))
    out = {"boxes": [list(b) for b in boxes], "ocr": ocr, "ocr_trace": trace, "ocr_ctc": ctc, "ocr_turns": turns,
           "pod": pod, "emb": emb, "overlap": overlap, "masked": masked}
    if hist:
        out["hist"] = hist
    if palette:
        out["car_colour"] = shares
    if keep_regions:
        out["ocr_regions"] = regions
    return out


def colour_read(crop, palette, masked: bool = False, vec=None) -> dict:
    """The crop's colour shares: SigLIP 2 scores when this process has SigLIP 2 (`vec`, the crop's
    image vector when already worked out), else HSV shares. A masked crop's GREY fill never counts:
    HSV leaves it out, and SigLIP 2 sees it painted the median colour of the kept pixels."""
    siglip = _W.get("siglip")
    if siglip:
        if vec is None and masked:
            import numpy as np
            from segment import GREY
            fill = (crop == GREY).all(axis=2)
            if (~fill).any():
                crop = crop.copy()
                crop[fill] = np.median(crop[~fill], axis=0).astype(crop.dtype)
        return siglip.colour_scores(vec if vec is not None else siglip.embed_image(crop), palette)
    return car_colour.colour_shares(crop, palette, masked=masked)


def rescue_frame(job: tuple):
    """(path, candidate box, mate path, mate's encoded embedding) → the frame's analysis with the
    candidate as its one box, or None when its crop doesn't look like the mate's (the sim is under
    RESCUE_MIN_SIM). The analysis carries `rescued` {from, sim}."""
    path, box, mate_path, mate_emb = job
    rgb = decode_rgb(path)
    sim = float((_W["embedder"].embed(crop_box(rgb, box)) * decode(mate_emb)).sum())
    if sim < RESCUE_MIN_SIM:
        return None
    boxes, vecs = check_boxes(rgb, [box])[:2]
    if not boxes:
        return None
    h, w = rgb.shape[:2]
    out = _read_boxes(rgb, boxes, vecs=vecs)
    out.update(note="", frame=[w, h], candidates=[], rescued={"from": os.path.basename(mate_path), "sim": round(sim, 4)})
    return out


def hires_frame(job: tuple):
    """(path, the analysis's boxes, its frame [w, h], the wanted box indices) → those boxes re-read from
    a sharper decode of the frame (the analysis shape, None for the other boxes), or {} when there is
    none: not a RAW, not enough wider than the preview, or framed differently."""
    path, boxes, (w, h), wanted = job
    hi = load_hires(path)
    if hi is None:
        return {}
    if hi.shape[1] < HIRES_MIN_GAIN * w or abs(hi.shape[1] / hi.shape[0] / (w / h) - 1) > HIRES_ASPECT_TOL:
        return {}
    return _read_boxes(None, [tuple(b) for b in boxes], hi, frame=(w, h), wanted=set(wanted))


# ---------------------------------------------------------------- identify mode

def read_manifest(path: str, columns: int, optional: int = 0) -> list:
    """Rows of `columns` + `optional` fields; a row may omit the optional ones (read as "")."""
    with open(path, newline="", encoding="utf-8") as f:
        return [(row + [""] * optional)[:columns + optional] for row in csv.reader(f) if len(row) >= columns]


def box_hint(tag_prefixes: list, sponsor: list) -> tuple:
    """(prefixes, source) for one box. Tag and sponsor prefixes that agree are merged (`both`);
    when they differ the user's tags win."""
    if tag_prefixes and sponsor:
        if all(any(s == t or s.startswith(t + "|") or t.startswith(s + "|") for t in tag_prefixes) for s in sponsor):
            return list(dict.fromkeys(tag_prefixes + sponsor)), "both"
        return tag_prefixes, "tag"
    if tag_prefixes:
        return tag_prefixes, "tag"
    return sponsor, "sponsor" if sponsor else ""


def format_row(image_id: str, r: BoxResult, shot: str = "") -> str:
    return (f"{image_id},{r.box},{r.method},{r.entry_id},{r.alt_entry_id},"
            f"{r.confidence:.3f},{r.unmatched_number},{shot},{'1' if r.order_flag else ''},"
            f"{r.colour},{'1' if r.colour_flag else ''},{r.sponsor},{'1' if r.anchor_flag else ''}")


def describe_box(r: BoxResult, ocr: list, sims: list, box: list, frame: list) -> str:
    seen = "/".join(d for d, _ in ocr) or "-"
    top = ", ".join(f"{e} {s:.3f}" for e, s in sims[:2]) or "no references"
    unmatched = f"; number seen but unmatched: {r.unmatched_number}" if r.unmatched_number else ""
    bw, bh = box[2] - box[0], box[3] - box[1]
    fw, fh = frame
    frac = f"; box {bw:.0f}x{bh:.0f} ({bw * bh / max(fw * fh, 1):.1%} of frame)"
    colour = f"; colour {r.colour}" if r.colour else ""
    colour += f"; sponsor {r.sponsor}" if r.sponsor else ""
    listed = f"; list {r.list_read}" if r.list_read else ""
    return f"box {r.box}: {r.method} {r.entry_id or '-'} (OCR {seen}{listed}; livery {top}{unmatched}{colour}{frac})"


def check_models(models: dict, siglip: bool = True):
    """Every model exists and loads, so a bad one fails the run here, not per frame. Returns the
    loaded embedder (a FaceModel for people collections) for the run's reference index. With
    `siglip`, the loaded number reader and SigLIP 2 (or None) become this process's, so reference_box
    and _siglip don't load them again; jobs that read no crops pass False and skip SigLIP 2."""
    if models["kind"] == "people":
        for label, key in (("face detector", "face_det"), ("face recognizer", "face_rec")):
            if not models[key] or not os.path.isfile(models[key]):
                raise InputError(f"{label} model not found: {models[key] or '(not set)'}")
        try:
            return FaceModel(models["face_det"], models["face_rec"])
        except Exception as e:
            raise InputError(f"face models can't be loaded: {type(e).__name__}: {e}. "
                             f"Download them again (see the README).") from e
    labels =(("object detector", "detector"), ("OCR text detection", "ocr_det"),
              ("OCR text recognition", "ocr_rec"), ("embedder", "embedder"))
    for label, key in labels:
        if not models[key] or not os.path.isfile(models[key]):
            raise InputError(f"{label} model not found: {models[key] or '(not set)'}")
    loaders = (("object detector", "detector", lambda: load_detector(models["detector"])),
               ("OCR", "ocr_det", lambda: NumberReader(models["ocr_det"], models["ocr_rec"])),
               ("embedder", "embedder", lambda: Embedder(models["embedder"])),
               *([("segmenter", "segmenter", lambda: Segmenter(models["segmenter"]))] if models.get("segmenter") else []),
               *([("SigLIP 2", "siglip", lambda: SigLIP(models["siglip"]))] if siglip and models.get("siglip") else []))
    loaded = {}
    for label, key, load in loaders:
        try:
            loaded[key] = load()
        except Exception as e:
            raise InputError(f"{label} model can't be loaded ({models[key]}): {type(e).__name__}: {e}. "
                             f"Download it again (see the README).") from e
    log(f"number reader: {loaded['ocr_det'].rec.name} ({os.path.basename(models['ocr_rec'])}); "
        f"text finder: {os.path.basename(models['ocr_det'])}")
    if not siglip:
        return loaded["embedder"]
    _W["reader"] = loaded["ocr_det"]
    _W["siglip"] = loaded.get("siglip")
    if models.get("siglip"):
        log("box check: on (SigLIP 2)" + ("; colour reader: SigLIP 2" if models.get("car_colour") else ""))
    else:
        log("box check: off (no SigLIP 2 model)" + ("; colour reader: HSV rules" if models.get("car_colour") else ""))
    return loaded["embedder"]


def worker_count(cpus: int) -> int:
    return max(1, min(cpus - 1, MAX_WORKERS))


class WorkerPool:
    """One process pool for every stage of a run (analysis, rescue, re-read), so each worker loads
    the models once per run. Started by the first stage with work to do; a run that is all cache
    hits starts no workers."""

    def __init__(self, models: dict):
        self.models, self.size, self.executor = models, worker_count(os.cpu_count() or 2), None

    def get(self) -> concurrent.futures.ProcessPoolExecutor:
        if self.executor is None:
            log(f"worker pool: {self.size} workers, models load once per worker for the whole run")
            self.executor = concurrent.futures.ProcessPoolExecutor(max_workers=self.size, initializer=_init_worker,
                                                                   initargs=(self.models,))
        return self.executor

    def cancel(self):
        """Stops the workers now, frames in flight included, so a cancelled run exits within the
        plugin's 5 s wait instead of after the slowest running frame (a RAW demosaic, a model load)."""
        if self.executor is None:
            return
        processes = list((self.executor._processes or {}).values())  # shutdown drops the private map
        self.executor.shutdown(wait=False, cancel_futures=True)
        for process in processes:
            process.terminate()
        self.executor = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        if self.executor is not None:
            self.executor.shutdown(wait=True, cancel_futures=True)


def run_frames(paths: list, models: dict, cache: IdentifyCache, progress: str, pool: WorkerPool) -> dict:
    """filepath → analysis (cached or fresh); a frame that fails to decode maps to None."""
    unique = list(dict.fromkeys(paths))  # darktable duplicates and versions share a file
    done, total, out, todo = 0, len(unique), {}, []
    for i, p in enumerate(unique):
        if i % 100 == 0:
            write_progress(progress, i, total, "checking cache")
        hit = cache.get(*frame_key(p, models))
        if hit is not None:
            out[p] = hit
            done += 1
        else:
            todo.append(p)
    log(f"analysing: {total} frames, {done} from cache, {len(todo)} to decode")
    cached = done
    write_progress(progress, done, total, "analysing", cached)
    if not todo:
        log_box_check(out, models)
        log_turns("analysis", out.values())
        return out
    workers = pool.size
    hits, detected, started = 0, 0, time.time()
    # each worker loads every model before its first frame; the first finished frame ends this stage
    write_progress(progress, 0, 1, "starting workers")
    executor = pool.get()
    futures = {executor.submit(analyse_frame, p): p for p in todo}
    for fut in concurrent.futures.as_completed(futures):
        if cancel_requested(progress):
            log("cancelled")
            pool.cancel()
            cache.close()
            sys.exit(130)
        p = futures[fut]
        try:
            out[p] = fut.result()
            if out[p].pop("detection_cached", False):
                hits += 1
            else:
                detected += 1
            cache.put(out[p], *frame_key(p, models))
        except concurrent.futures.process.BrokenProcessPool as e:
            raise InputError(f"an analysis worker died (out of memory or a crashed library?); "
                             f"frames finished so far are cached, rerun to continue: {e}") from e
        except Exception as e:
            log(f"{p}: couldn't analyse ({type(e).__name__}: {e})")
            out[p] = None
        done += 1
        write_progress(progress, done, total, "analysing", cached)
    elapsed = time.time() - started
    log(f"analysis: {len(todo)} frames in {elapsed:.0f}s, {len(todo) * 60 / max(elapsed, 0.001):.0f} frames/min ({workers} workers)")
    if models["kind"] != "people":
        log(f"detections: {hits} cached, {detected} detected")
    log_box_check(out, models)
    log_turns("analysis", out.values())
    return out


def log_box_check(analyses: dict, models: dict):
    """One run-log line counting the boxes the box check dropped, per answer, and the contested
    boxes it kept, per reason (check_boxes)."""
    if models["kind"] == "people" or not models.get("siglip"):
        return
    dropped: dict = {}
    saved = {"share": 0, "score": 0}
    for a in analyses.values():
        for what, n in ((a or {}).get("dropped") or {}).items():
            dropped[what] = dropped.get(what, 0) + n
        for c in (a or {}).get("contested") or []:
            if c["kept"]:
                saved[c["kept"]] += 1
    counts = ", ".join(f"{what} {n}" for what, n in sorted(dropped.items(), key=lambda p: -p[1]))
    log(f"box check: dropped {sum(dropped.values())} boxes" + (f": {counts}" if counts else "")
        + f"; kept {saved['share']} on vehicle share, {saved['score']} on detector score")


def log_turns(stage: str, analyses):
    """One run-log line counting the number reads a turned retry won, per turn (ocr.read_turned), over
    the analyses that carry `ocr_turns`; none when no analysis read numbers."""
    read = [a["ocr_turns"] for a in analyses if a and "ocr_turns" in a]
    if not read:
        return
    won = {turn: sum(t.get(turn, 0) for t in read) for turn in ("180", "90", "270")}
    log(f"{stage}: turned reads won {sum(won.values())} regions (" + ", ".join(f"{t}° {n}" for t, n in won.items()) + ")")


def rescue_frames(rows: list, analyses: dict, models: dict, cache: IdentifyCache, pool: WorkerPool,
                  progress: str = "") -> dict:
    """analyses with the frames the detector missed filled in from burst-mates: for a no-vehicle
    frame in a burst that has vehicle frames, a weak candidate that tracks a mate's box becomes its
    box when its crop looks like the mate's (rescue.py). Each job is cached under rescue_key, so a
    changed burst (another mate) re-runs it and an unchanged one doesn't."""
    bursts: dict = {}
    seen = set()
    for _id, filepath, burst, _protected, _hints, taken, *_rest in rows:
        if filepath in seen or filepath not in analyses:
            continue
        seen.add(filepath)
        bursts.setdefault(burst, []).append((int(taken) if taken.isdigit() else 0, filepath))
    jobs = []
    for members in bursts.values():
        ordered = [(p, analyses[p]) for _, p in sorted(members)]
        for path, (box, mate) in plan_burst(ordered).items():
            jobs.append((path, box, mate, analyses[mate]["emb"][0]))
    if not jobs:
        return analyses
    results = {}
    for job in jobs:
        hit = cache.get(*rescue_key(job, models))
        if hit is not None:
            results[job[0]] = hit or None  # {} is a cached "doesn't look like the mate's car"
    todo = [job for job in jobs if job[0] not in results]
    log(f"rescue: {len(jobs)} frames with no vehicle have a candidate where a burst-mate's car is, "
        f"{len(jobs) - len(todo)} from cache, {len(todo)} to decode")
    write_progress(progress, 0, len(todo), "rescue")
    if todo:
        executor = pool.get()
        for n, (job, result) in enumerate(zip(todo, executor.map(rescue_frame, todo)), 1):
            if cancel_requested(progress):
                log("cancelled")
                pool.cancel()
                sys.exit(130)  # the caller's finally closes the cache
            write_progress(progress, n, len(todo), "rescue")
            cache.put(result or {}, *rescue_key(job, models))
            results[job[0]] = result
    out = dict(analyses)
    for job in jobs:
        result = results[job[0]]
        if result is None:
            log(f"{job[0]}: rescue candidate doesn't look like {os.path.basename(job[2])}'s car, left as no vehicle")
            continue
        log(f"{job[0]}: rescued a vehicle from {result['rescued']['from']} (crop similarity {result['rescued']['sim']})")
        out[job[0]] = result
    return out


def rescue_key(job: tuple, models: dict) -> list:
    """A rescue job's cache key parts: the frame's own key, the candidate box and the mate's file. The
    mate's embedding follows from its file under the same models, so the three fix the result."""
    path, box, mate, _mate_emb = job
    return [*frame_key(path, models), "rescue-1", json.dumps(list(box)), file_key(mate)]


def hires_key(boxes: list, wanted) -> list:
    """The re-read's cache key parts: the box list and the wanted box indices are in it, so a box
    rescued from a burst, or a box not re-read last time, never reuses a re-read made without it."""
    digest = hashlib.sha1(json.dumps([sorted(boxes, key=repr), sorted(wanted)], default=str).encode()).hexdigest()[:12]
    return ["hires-3", digest]


def refine_frames(wanted: dict, analyses: dict, models: dict, cache_path: str, pool: WorkerPool,
                  progress: str = "") -> dict:
    """analyses with the boxes in `wanted` (filepath → box indices) re-read from a sharper decode of
    the frame: OCR, embedding and colour replace the first-pass ones, and `hires` lists the boxes
    that changed. Only the wanted boxes are re-read, and the re-read is cached, so a rerun doesn't
    decode again."""
    cache = IdentifyCache(cache_path)
    try:
        reads, todo = {}, []
        for p in wanted:
            hit = cache.get(*frame_key(p, models), *hires_key(analyses[p]["boxes"], wanted[p]))
            if hit is None:
                todo.append(p)
            else:
                reads[p] = hit
        log(f"refining: {len(wanted)} frames have boxes to re-read at higher detail, {len(reads)} from cache, {len(todo)} to decode")
        if todo:
            executor = pool.get()
            futures = {executor.submit(hires_frame, (p, analyses[p]["boxes"], analyses[p]["frame"], sorted(wanted[p]))): p
                       for p in todo}
            done, started = 0, time.time()
            write_progress(progress, 0, len(todo), "refining")
            for fut in concurrent.futures.as_completed(futures):
                if cancel_requested(progress):
                    log("cancelled")
                    pool.cancel()
                    cache.close()
                    sys.exit(130)
                p = futures[fut]
                try:
                    reads[p] = fut.result()
                    cache.put(reads[p], *frame_key(p, models), *hires_key(analyses[p]["boxes"], wanted[p]))
                except Exception as e:
                    log(f"{p}: couldn't re-read at higher detail ({type(e).__name__}: {e}), first pass kept")
                done += 1
                write_progress(progress, done, len(todo), "refining")
                if done % 10 == 0 or done == len(todo):
                    log(f"refining: {done}/{len(todo)} done, {time.time() - started:.0f}s")
    finally:
        cache.close()
    log_turns("refining", reads.values())
    out = dict(analyses)
    for p, idx in wanted.items():
        read = reads.get(p)
        if not read:
            continue
        a = dict(analyses[p])
        for key in ("ocr", "ocr_trace", "ocr_ctc", "ocr_regions", "emb", "hist", "car_colour"):
            if key in a and key in read:
                a[key] = [read[key][i] if i in idx else v for i, v in enumerate(a[key])]
        a["hires"] = [i in idx for i in range(len(a["boxes"]))]
        out[p] = a
    return out


def hires_wanted(frames: dict, detail: dict, analyses: dict) -> dict:
    """filepath → indices of the boxes worth re-reading at higher detail: those the first pass left
    unidentified (`none`, or `team` with the driver not separated). Hidden (overlapped) boxes are
    left out, since a sharper crop can't uncover them."""
    wanted: dict = {}
    for image_id, results in frames.items():
        path = detail[image_id]["file"]
        a = analyses.get(path)
        for r in results:
            if r.box >= 0 and r.method in ("none", "team") and a and a.get("overlap", [""] * len(a["boxes"]))[r.box] != HIDDEN:
                wanted.setdefault(path, set()).add(r.box)
    return wanted


def pool_burst_livery(frames: dict, burst_of: dict, box0_sims: dict, entries: dict) -> dict:
    """Experimental (rules.burst_livery_pooling): for each burst with 2+ frames, pool
    box-0 livery similarity across them and re-run the livery/team decision once on the
    average. Frames whose box 0 was already resolved by number are left alone; a frame
    the pooled decision still can't resolve keeps its own per-frame result."""
    members: dict = {}
    for image_id in box0_sims:
        members.setdefault(burst_of.get(image_id, image_id), []).append(image_id)
    out = dict(frames)
    for ids in members.values():
        if len(ids) < 2:
            continue
        pooled = pool_sims([box0_sims[i] for i in ids])
        decision = match_livery(0, pooled, entries)
        if decision.method == "none":
            continue
        for image_id in ids:
            box0 = out[image_id][0]
            if box0.method == "number":
                continue
            out[image_id] = [replace(box0, method="pooled", entry_id=decision.entry_id,
                                      alt_entry_id=decision.alt_entry_id,
                                      confidence=decision.confidence)] + out[image_id][1:]
    return out


ARCHIVE_KEEP = 20  # runs kept under --archive-dir; the oldest are deleted


def archive_run(files: list, archive_dir: str, keep: int):
    """Copy a run's output files into <archive_dir>/<YYYYMMDD-HHMMSS>/ and delete all but the
    newest `keep` run folders. A failure is logged, never fatal: the run's own outputs are already written."""
    try:
        dest = os.path.join(archive_dir, time.strftime("%Y%m%d-%H%M%S"))
        os.makedirs(dest, exist_ok=True)
        for path in files:
            shutil.copy2(path, dest)
        runs = sorted(d for d in os.listdir(archive_dir) if re.fullmatch(r"\d{8}-\d{6}", d))
        for old in runs[:-keep]:
            shutil.rmtree(os.path.join(archive_dir, old), ignore_errors=True)
        log(f"archived run: {dest}")
    except OSError as e:
        log(f"could not archive the run: {e}")


def build_boxes(collection: str, frames: dict, shots: dict, detail: dict, entries: dict, counts: dict,
                sponsor_keywords: tuple = (), min_read: float = Rules.min_read) -> dict:
    """The run's per-vehicle record (see the README for the shape). `skipped` lists images
    left alone because they already carry one entry's full tag set; each image's `status` is
    ok, no_vehicle or error. `entries` and `thresholds` give the debug report what it needs."""
    images, skipped = {}, []
    for image_id, results in frames.items():
        if any(r.method == "skipped" for r in results):
            skipped.append(image_id)
            continue
        d = detail[image_id]
        status = "error" if any(r.method == "error" for r in results) else "ok" if d["boxes"] else "no_vehicle"
        boxes = []
        for r in results:
            if r.box < 0:
                continue
            b = d["boxes"][r.box]
            rule, gap = ("overlapped", 0.0) if b.get("overlap") == HIDDEN else decided_by(r, b["sims"], entries)
            boxes.append({"box": r.box, "bbox": b["bbox"], "score": round(b["score"], 3), "entry": r.entry_id, "alt_entry": r.alt_entry_id,
                          "method": r.method, "confidence": round(r.confidence, 4),
                          "candidates": [[e, round(s, 4)] for e, s in b["sims"][:5]],
                          "ocr": b["ocr"], "ocr_trace": b.get("ocr_trace", []), "decided_by": rule, "gap": round(gap, 4),
                          "unmatched_number": r.unmatched_number, "conflict": r.method == "conflict", "order_flag": r.order_flag,
                          "pod": b.get("pod", {}), "pod_colour": b.get("pod_colour", ""), "hint": b.get("hint", {}), "overlap": b.get("overlap", ""), "hires": b.get("hires", False), "masked": b.get("masked", False), "rescued": b.get("rescued", {}),
                          "colour": r.colour, "colour_shares": b.get("colour_shares", {}), "list_read": r.list_read,
                          "read_entry": b.get("read_entry", "")})
            if "ocr_regions" in b:
                boxes[-1].update(ocr_regions=b["ocr_regions"], ocr_ctc=b["ocr_ctc"],
                                 sims=[[e, s] for e, s in b["all_sims"]])
        images[image_id] = {"shot": shots[image_id], "status": status, "file": d["file"], "frame": d["frame"],
                            "burst": d["burst"], "time": d["time"], "note": d["note"], "boxes": boxes,
                            "hand": d.get("hand", ""), "tagged": d.get("tagged", "")}
    return {"collection": collection,
            "thresholds": {"min_sim": MATCH_MIN_SIM, "min_margin": MATCH_MIN_MARGIN,
                           # the number path's knobs, which eval_numbers.py replays and overrides
                           "ocr_min_score": OCR_MIN_SCORE, "number_min_height": NUMBER_MIN_HEIGHT,
                           "min_read": min_read, "weak_read_min": WEAK_READ_MIN,
                           "number_list_margin": NUMBER_LIST_MARGIN, "number_list_floor": NUMBER_LIST_FLOOR},
            "sponsor_keywords": dict(sponsor_keywords),
            "entries": {e.id: {"team": e.team, "number": e.number, "tags": list(e.tags), "camera": e.camera,
                                    "colour": e.colour, "car": e.car, "refs": counts.get(e.id, 0)}
                        for e in entries.values()},
            "images": images, "skipped": skipped}


def write_boxes(path: str, data: dict):
    """Writes build_boxes' record atomically."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with atomic_write(path) as f:
        json.dump(data, f)


def match_frame(image_id: str, a: dict, index: ReferenceIndex, entries: dict, rules: Rules, team_of: dict,
                tag_hints: list, boxes_out: list, box0_sims: dict, quiet: bool = False) -> list:
    """One BoxResult per detected vehicle in the analysed frame `a`. Appends each box's detail
    (bbox, detector score, sims, OCR, hint) to `boxes_out`, and box 0's sims to `box0_sims` when
    burst pooling needs them. `quiet` skips the per-box log lines (a pass that is redone)."""
    results = []
    for i, ocr in enumerate(a["ocr"]):
        sims = index.best_per_entry(decode(a["emb"][i]),
                                    decode(a["hist"][i]) if "hist" in a else None, rules.colour_weight)
        team_sims = [(team_of[k], s) for k, s in sims if k in team_of]
        sims = [(k, s) for k, s in sims if k in entries]
        trace = a["ocr_trace"][i]
        prefixes, source = box_hint(tag_hints if len(a["boxes"]) == 1 else [],
                                    sponsor_prefixes(trace, rules.sponsor_keywords))
        ctc = a["ocr_ctc"][i] if "ocr_ctc" in a else None
        reads = usable_reads([tuple(c) for c in ocr], ctc, rules.min_read)
        overlap = a.get("overlap", [""] * len(a["ocr"]))[i]
        shares = a["car_colour"][i] if "car_colour" in a else {}
        colour = car_colour.decide_colour(shares) if shares and overlap != HIDDEN else ""
        pool, colour_note = colour_pool(entries, colour, reads, sims, rules.min_read)
        r, hint = hinted_match(i, reads, [(k, s) for k, s in sims if k in pool], pool, prefixes, source, ctc, rules.min_read)
        if r.method == "number" and r.list_read and r.confidence < rules.min_read:
            r = replace(r, list_read=r.list_read + " (weak read)")
        read_entry = r.entry_id if r.method == "number" else ""
        r = match_team(r, team_sims, entries)
        pod = a["pod"][i]
        before = r.entry_id
        r = match_camera(r, pod_colour(pod), entries)
        if r.entry_id != before and not quiet:
            log(f"{image_id}: pod {pod_colour(pod)} moved {before} -> {r.entry_id}")
        if overlap == HIDDEN:
            r = BoxResult(i, "none")
        elif shares:
            r = replace(r, colour=colour)
        if overlap != HIDDEN and "sponsor" in rules.families:
            r = replace(r, sponsor=";".join(sponsor_words(trace, rules.sponsor_keywords, dict(rules.sponsor_names))))
        if not quiet:
            log(f"{image_id}: {describe_box(r, ocr, sims, a['boxes'][i], a['frame'])}"
                + (f" [hint {';'.join(prefixes)} ({source}){', dropped: ' + hint['reason'] if hint['dropped'] else ''}]" if hint else "")
                + (f" [colour {colour_note['colour']}: {colour_note['kept']} of {colour_note['kept'] + colour_note['removed']} entries"
                   + (f", dropped: {colour_note['reason']}" if colour_note["dropped"] else "") + "]" if colour_note else "")
                + (" [higher detail]" if a.get("hires", [])[i:i + 1] == [True] else "")
                + (" [masked]" if a.get("masked", [])[i:i + 1] == [True] else ""))
        results.append(r)
        boxes_out.append({"bbox": [float(v) for v in a["boxes"][i][:4]], "score": float(a["boxes"][i][4]),
                          "ocr": ocr, "sims": sims, "ocr_trace": trace, "pod": pod, "pod_colour": pod_colour(pod), "hint": hint,
                          "overlap": overlap, "hires": a.get("hires", [])[i:i + 1] == [True], "masked": a.get("masked", [])[i:i + 1] == [True], "rescued": a.get("rescued", {}),
                          "colour_shares": shares, "colour_filter": colour_note, "read_entry": read_entry})
        if "ocr_regions" in a:
            boxes_out[-1].update(ocr_regions=a["ocr_regions"][i], ocr_ctc=ctc, all_sims=sims)
        if i == 0:
            box0_sims[image_id] = sims
    return results


def with_hand_entries(frames: dict, hand_of: dict) -> dict:
    """`frames` with each hand-tagged image's entry (`hand_of`: image id to entry id) as a `hand`
    result. A frame with no vehicle takes it on its box -1 row. A solo shot takes it on its box when
    the reader named no car, or only that car's team; a box read as another car is left for the
    conflict check. A pack keeps its boxes and gains a box -1 row unless a box already names the entry."""
    out = dict(frames)
    for image_id, eid in hand_of.items():
        results = frames[image_id]
        if any(r.method in ("skipped", "error") for r in results):
            continue
        hand = BoxResult(-1, HAND, eid, confidence=1.0)
        boxes = [r for r in results if r.box >= 0]
        if not boxes:
            out[image_id] = [hand]
        elif len(boxes) == 1:
            out[image_id] = [replace(r, method=HAND, entry_id=eid, alt_entry_id="", confidence=1.0)
                             if r.box >= 0 and (r.method == "none" or r.method == "team" and eid in (r.entry_id, r.alt_entry_id))
                             else r for r in results]
        elif not any(r.entry_id == eid and r.method != "team" for r in boxes):
            out[image_id] = results + [hand]
    return out


def write_results(path: str, frames: dict, shots: dict) -> dict:
    """Writes the results.csv rows atomically and logs the burst and conflict decisions; returns
    the count of vehicles per method."""
    by_method: dict = {}
    with atomic_write(path, newline="") as f:
        for image_id, results in frames.items():
            for r in results:
                if r.method == "burst":
                    log(f"{image_id}: box {r.box}: burst {r.entry_id} ({r.confidence:.2f} of the burst agrees)")
                if r.method == "conflict":
                    log(f"{image_id}: box {r.box}: {r.entry_id} shares no tag with the ones you applied; left as you tagged it")
                by_method[r.method] = by_method.get(r.method, 0) + 1
                f.write(format_row(image_id, r, shots[image_id]) + "\n")
    return by_method


def best_effort(what: str, write):
    """Runs a side-file write after results.csv exists: a failure is a warning, never exit 1."""
    try:
        write()
    except Exception as e:
        log(f"warning: couldn't write {what} ({type(e).__name__}: {e}); the results still apply")


def write_run_outputs(args, data: dict):
    """boxes.json, the report and the archive copy, as the run's flags ask. Best effort."""
    written = []

    def boxes():
        write_boxes(args.boxes_out, data)
        written.append(args.boxes_out)

    def report():
        md_path, json_path = write_report(data, args.report_out, args.report_top)
        written.extend([md_path, json_path])
        log(f"report: {md_path}")

    if args.boxes_out:
        best_effort("boxes.json", boxes)
    if args.report_out:
        best_effort("the report", report)
    if args.archive_dir:
        best_effort("the archive copy", lambda: archive_run(written, args.archive_dir, ARCHIVE_KEEP))


def open_index(collection: str, models: dict, rules: Rules, embedder, progress: str = "") -> ReferenceIndex:
    """The collection's reference index, keyed on whichever models embed its references.
    Re-embedding (new embedder or blur setting) ticks `progress`, so the plugin's stall timer
    doesn't fire, and a cancel stops it; the caller checks cancel_requested afterwards."""
    def on_progress(done, total):
        write_progress(progress, done, total, "references")
        return not cancel_requested(progress)

    if rules.kind == "people":
        return ReferenceIndex.load(collection, embedder, face_model_key(models["face_det"], models["face_rec"]),
                                   dim=FACE_EMBED_DIM, on_progress=on_progress)
    return ReferenceIndex.load(collection, embedder, [embedder_key(models["embedder"]), rules.blur_references],
                               rules.blur_references, dim=embedder.dim, colour=rules.colour_weight > 0,
                               on_progress=on_progress)


def identify_people(args, models: dict, entries: dict, rules: Rules, from_entries: tuple, collection: str,
                    face_model: FaceModel):
    rows = read_manifest(args.manifest, 3, 3)
    protected_of = {r[0]: {t for t in r[3].split(";") if t} for r in rows}
    verify = getattr(args, "verify", False)
    fully_tagged = {i for i, p in protected_of.items() if already_tagged(p, entries)}
    index = open_index(collection, models, rules, face_model, args.progress)
    if cancel_requested(args.progress):
        log("cancelled")
        sys.exit(130)
    counts = index.count_by_entry()
    if not counts:
        log(f"collection {args.collection} has no face references yet: nothing can be identified")
    else:
        log("references: " + ", ".join(f"{e} {counts.get(e, 0)}" for e in entries))
    cache = IdentifyCache(args.cache)
    try:
        with WorkerPool(models) as pool:
            analyses = run_frames([r[1] for r in rows if verify or r[0] not in fully_tagged], models, cache,
                                  args.progress, pool)
    finally:
        cache.close()
    if cancel_requested(args.progress):
        log("cancelled")
        sys.exit(130)
    frames, detail, shots = {}, {}, {}
    for image_id, filepath, burst, _protected, _hints, taken in rows:
        detail[image_id] = {"file": filepath, "frame": [], "faces": [], "note": "", "burst": burst,
                            "time": int(taken) if taken.isdigit() else None}
        if image_id in fully_tagged and not verify:
            log(f"{image_id}: already carries all of {already_tagged(protected_of[image_id], entries)}'s tags, skipped")
            frames[image_id] = [BoxResult(-1, "skipped")]
            continue
        a = analyses.get(filepath)
        if a is None:
            frames[image_id] = [BoxResult(-1, "error")]
            continue
        detail[image_id]["frame"] = a["frame"]
        if not a["boxes"]:
            log(f"{image_id}: {a['note']}")
            detail[image_id]["note"] = a["note"]
            frames[image_id] = [BoxResult(-1, "none")]
            continue
        frames[image_id] = match_frame_people(image_id, a, index, entries, rules, detail[image_id]["faces"])
    for image_id, results in frames.items():
        n_faces = sum(1 for r in results if r.box >= 0)
        shots[image_id] = shot_type(n_faces, MAX_BOXES)
        frames[image_id] = [replace(r, method="conflict") if r.entry_id and (
            disagrees(r, already_tagged(protected_of[image_id], entries), n_faces == 1) if verify and image_id in fully_tagged
            else conflicts(r.entry_id, protected_of[image_id], entries, n_faces == 1)) else r for r in results]
    by_method = write_results(args.results, frames, shots)
    if args.boxes_out or args.report_out:
        write_run_outputs(args, build_boxes_people(args.collection, frames, shots, detail, entries, counts, rules))
    write_collection_outputs(args, collection, entries, rules, from_entries)
    log("faces by method: " + ", ".join(f"{m} {n}" for m, n in sorted(by_method.items())))


def identify(args, models: dict):
    collection = os.path.join(args.collections_root, args.collection)
    entries, rules, from_entries = load_collection(collection, args.settings)
    models["kind"] = rules.kind
    models["colour"] = rules.kind != "people" and rules.colour_weight > 0
    models["car_colour"] = rules.colour_palette if rules.kind != "people" and "colour" in rules.families else None
    models["segmenter"] = segmenter_path(models.get("detector", ""), models.get("segmenter", "")) if rules.kind != "people" else ""
    write_progress(args.progress, 0, 1, "loading models")
    embedder = check_models(models)
    write_progress(args.progress, 1, 1, "loading models")
    if rules.kind == "people":
        return identify_people(args, models, entries, rules, from_entries, collection, embedder)
    rows = read_manifest(args.manifest, 3, 4)
    # 4th column: entry tags the user applied by hand (never ledgered by the plugin), ";"-joined.
    protected_of = {r[0]: {t for t in r[3].split(";") if t} for r in rows}
    verify = getattr(args, "verify", False)
    # --verify keeps every OCR region with its drop reason for eval_numbers.py
    models["ocr_regions"] = verify
    # 5th column: hand-applied team tags (team hints), ";"-joined.
    # --verify checks the tags, so they must not steer the match.
    tag_hints_of = {r[0]: [] if verify else [t for t in r[4].split(";") if t] for r in rows}
    fully_tagged = {i for i, p in protected_of.items() if already_tagged(p, entries)}
    # 7th column: the entry the user's hand number or driver tag names. --verify checks the tags instead.
    # An entry missing here was removed from entries.json after the panel's last Reload.
    for r in rows:
        if r[6] and r[6] not in entries:
            log(f"image {r[0]}: hand-tagged as entry {r[6]}, which is not in entries.json; its hand tag is not used (Reload, then run again)")
    hand_of = {r[0]: r[6] for r in rows if r[6] in entries and not verify and r[0] not in fully_tagged}
    write_progress(args.progress, 0, 1, "references")
    index = open_index(collection, models, rules, embedder, args.progress)
    write_progress(args.progress, 1, 1, "references")
    if cancel_requested(args.progress):
        log("cancelled")
        sys.exit(130)
    counts = index.count_by_entry()
    if not counts:
        log(f"collection {args.collection} has no references yet: only numbers can identify a car")
    else:
        log("references: " + ", ".join(f"{e} {counts.get(e, 0)}" for e in entries))
    unknown = sorted(k for k in set(counts) - set(entries) if not k.startswith(TEAM_KEY))
    team_of = {team_key(p): p for p in team_tags(entries, rules.families)} if rules.partial_references else {}
    if unknown:
        log("references for entries not in entries.json (ignored): " + ", ".join(unknown))
    # team references saved under a tag no entry carries now, e.g. the old tag_prefix|team keys
    stale_teams = sorted(k[len(TEAM_KEY):].replace("__", "|") for k in counts if k.startswith(TEAM_KEY) and k not in team_of)
    if rules.partial_references and stale_teams:
        log("team references for tags no entry carries under the team root (ignored): " + ", ".join(stale_teams))

    with WorkerPool(models) as pool:
        cache = IdentifyCache(args.cache)
        try:
            analyses = run_frames([r[1] for r in rows if verify or r[0] not in fully_tagged], models, cache, args.progress, pool)
            if cancel_requested(args.progress):
                log("cancelled")
                sys.exit(130)
            # --verify compares each frame's own reading with its tags: no inference from burst mates
            if not verify:
                analyses = rescue_frames(rows, analyses, models, cache, pool, args.progress)
        finally:
            cache.close()
        log(index.use_run_centre([decode(e) for a in analyses.values() if a for e in a.get("emb", []) if e]))

        def match_all(analyses: dict, quiet: bool = False) -> tuple:
            frames, burst_of, box0_sims, detail = {}, {}, {}, {}
            for image_id, filepath, burst, _protected, _hints, taken, hand in rows:
                burst_of[image_id] = burst
                # hand and tagged are the truth eval_numbers.py scores a --verify run against
                detail[image_id] = {"file": filepath, "frame": [], "boxes": [], "note": "", "burst": burst,
                                    "time": int(taken) if taken.isdigit() else None,
                                    "hand": hand if hand in entries else "",
                                    "tagged": already_tagged(protected_of[image_id], entries)}
                if image_id in fully_tagged and not verify:
                    if not quiet:
                        log(f"{image_id}: already carries all of {already_tagged(protected_of[image_id], entries)}'s tags, skipped")
                    frames[image_id] = [BoxResult(-1, "skipped")]
                    continue
                a = analyses.get(filepath)
                if a is None:
                    # an error row: assisted_tagging.lua leaves this image's tags alone
                    frames[image_id] = [BoxResult(-1, "error")]
                    continue
                if not a["boxes"]:
                    if not quiet:
                        log(f"{image_id}: {a['note']}")
                    detail[image_id]["note"] = a["note"]
                    frames[image_id] = [BoxResult(-1, "none")]
                    continue
                detail[image_id]["frame"] = a["frame"]
                frames[image_id] = match_frame(image_id, a, index, entries, rules, team_of, tag_hints_of[image_id],
                                               detail[image_id]["boxes"], box0_sims, quiet)
            return frames, burst_of, box0_sims, detail

        # first pass on the cheap analysis; boxes it can't identify are then re-read at higher detail
        frames, burst_of, box0_sims, detail = match_all(analyses, quiet=True)
        wanted = hires_wanted(frames, detail, analyses)
        if wanted and not cancel_requested(args.progress):
            analyses = refine_frames(wanted, analyses, models, args.cache, pool, args.progress)
    write_progress(args.progress, 0, 1, "matching")
    frames, burst_of, box0_sims, detail = match_all(analyses)

    def keep_main_cars(frames: dict, stage: str) -> dict:
        if rules.cars_per_photo != "solo":
            return frames
        frames, ignored = main_car_only(frames)
        for fid, box, method, eid in ignored:
            if eid:
                log(f"{fid}: box {box}: {method} {eid} ignored, not the photo's main car")
        if ignored:
            log(f"main car ({stage}): {len(ignored)} smaller boxes ignored; one counts only with another car's number read")
        return frames

    # before the burst and neighbour passes, so a background box never anchors them
    frames = keep_main_cars(frames, "matching")
    # Each car's anchors: its anchor refs plus this run's strong number reads. Livery, burst and
    # neighbour matches unlike them lose their car (checked before burst and neighbour build on them, then after).
    anchors = None if verify or rules.kind == "people" else \
        Anchors(index, {eid: e.car for eid, e in entries.items()}, rules.colour_weight)
    rejected = Counter()

    def box_vectors(fid: str, box: int) -> tuple:
        a = analyses.get(detail[fid]["file"]) if fid in detail else None
        if not a or not 0 <= box < len(a.get("emb", [])):
            return None, None
        hist = decode(a["hist"][box]) if "hist" in a else None
        return (None, None) if anchors.join and hist is None else (decode(a["emb"][box]), hist)

    def check_anchors(frames: dict, stage: str) -> dict:
        if anchors is None:
            return frames
        out, n, moved, backed = {}, 0, 0, 0
        sure = sure_cars(frames, burst_of, entries, ANCHOR_MIN_READ)
        for fid, rs in frames.items():
            out[fid] = []
            for r in rs:
                check = r.method in ANCHOR_CHECKED and r.entry_id
                if check and r.method == "burst" \
                        and (entries[r.entry_id].car or r.entry_id) in sure.get(burst_of.get(fid, fid), ()):
                    check, backed = False, backed + 1
                vec, hist = box_vectors(fid, r.box) if check else (None, None)
                verdict, own, other_car, other = anchors.unlike(r.entry_id, vec, hist) if vec is not None \
                    else ("", None, "", None)
                if verdict == "unlike":
                    closer = f", closer to {other_car}'s {other:.3f}" if other_car else ""
                    checked = closer_car_match(r, own, other_car, other, entries, rules.closer_car_margin, ANCHOR_MIN_SIM,
                                               {x.entry_id for x in out[fid] + rs[len(out[fid]) + 1:] if x.entry_id},
                                               sure.get(burst_of.get(fid, fid), ()))
                    moved += bool(checked.entry_id)
                    outcome = f"moved to {checked.entry_id}" if checked.entry_id else "dropped"
                    log(f"{fid}: box {r.box}: {r.entry_id} doesn't look like its anchors (sim {own:.3f}{closer}, "
                        f"colour {r.colour or '-'}); {r.method} match {outcome}")
                    rejected[r.entry_id] += 1
                    n += 1
                    r = checked
                out[fid].append(r)
        log(f"anchors ({stage}): {n - moved} matches dropped, {moved} moved to the closer car "
            f"(closer_car_margin {rules.closer_car_margin:g}); {backed} burst matches not checked "
            f"(a {ANCHOR_MIN_READ}+ number read or your tag in the burst names the car)")
        return out

    if anchors is not None:
        strong = 0
        for fid, rs in frames.items():
            for r in rs:
                vec, hist = box_vectors(fid, r.box) if r.method == "number" and r.confidence >= ANCHOR_MIN_READ else (None, None)
                if vec is not None:
                    anchors.add(r.entry_id, vec, hist, f"{fid}_b{r.box}")
                    strong += 1
        log(f"anchors: {len(anchors.rels) - strong} refs + {strong} number reads of {ANCHOR_MIN_READ}+ this run; "
            f"{len(anchors.unanchored(list(entries)))} cars have none (their first match is accepted)")
    frames = check_anchors(frames, "matching")
    if not verify:
        weak = {fid: {i: [tuple(c) for c in b["ocr"] if c[1] >= WEAK_READ_MIN]
                      for i, b in enumerate(d["boxes"]) if b["overlap"] != HIDDEN}
                for fid, d in detail.items()}
        ctc_of = {fid: dict(enumerate((analyses.get(d["file"]) or {}).get("ocr_ctc", []))) for fid, d in detail.items()}
        agreed = agreeing_reads(frames, burst_of, weak, entries, ctc_of)
        for fid, rs in agreed.items():
            for a, b in zip(rs, frames[fid]):
                if a.method != b.method:
                    how = f"list {a.list_read}" if a.list_read else "agreed across the group"
                    log(f"{fid}: box {a.box}: number {a.entry_id} (weak read {a.confidence:.2f}, {how})")
        frames = agreed
    if rules.burst_livery_pooling and not verify:
        frames = pool_burst_livery(frames, burst_of, box0_sims, entries)
    # before neighbour aid and burst consensus, so a hand-tagged frame supports the frames around it
    frames = with_hand_entries(frames, hand_of)
    for image_id, eid in hand_of.items():
        if any(r.method == HAND for r in frames[image_id]):
            log(f"{image_id}: {eid} by the tag you applied")
    shooting_order = {i: (d["time"] if d["time"] is not None else 0, d["file"]) for i, d in detail.items()}
    if not verify and rules.order_weight > 0:
        times = {i: d["time"] or 0 for i, d in detail.items()}
        emb_cache: dict = {}

        def box_emb(fid: str, box: int):
            if fid not in detail:  # a library neighbour: tagged, never analysed
                return None
            if (fid, box) not in emb_cache:
                a = analyses.get(detail[fid]["file"])
                embs = a.get("emb", []) if a else []
                emb_cache[fid, box] = decode(embs[box]) if 0 <= box < len(embs) else None
            return emb_cache[fid, box]

        def similar(fid: str, box: int, ofid: str, obox: int):
            a, b = box_emb(fid, box), box_emb(ofid, obox)
            return None if a is None or b is None else float((a * b).sum())

        lib_path = getattr(args, "neighbours", "")
        library = read_manifest(lib_path, 3) if lib_path and os.path.exists(lib_path) else []
        with_lib, lib_burst_of, lib_times = with_library_neighbours(frames, burst_of, times, library, entries)
        log(f"neighbour: {len(with_lib) - len(frames)} unselected tagged photos lend support")
        # no `guesses`: the best-guess path was 3/14 right on Rallye (ticket 79)
        aided = neighbour_aid(with_lib, lib_burst_of, lib_times, entries, rules.neighbour_tolerance, rules.order_weight,
                              similar)
        aided = {i: rs for i, rs in aided.items() if i in frames}
        resolved = 0
        for i, rs in aided.items():
            for a, b in zip(rs, frames[i]):
                if a.method == "neighbour" and b.method != "neighbour":
                    resolved += 1
                    how = {"order": f"read {b.unmatched_number}, fits the number order",
                           "candidate": "best guess, seen nearby"}.get(a.via, "looks like a nearby car")
                    log(f"{i}: box {a.box}: neighbour {a.entry_id} ({how}, {a.confidence:.3f})")
        flagged = sum(1 for rs in aided.values() for r in rs if r.order_flag)
        log(f"neighbour: resolved {resolved}, flagged {flagged} (order weight {rules.order_weight:g}, tolerance {rules.neighbour_tolerance})")
        frames = aided
    if not verify:
        frames = burst_consensus(frames, burst_of, entries, shooting_order, box0_sims)
        # after consensus, so a burst-filled box votes and takes the car's colour too
        frames, recoloured = burst_colours(frames, burst_of, {(fid, i): b["colour_shares"] for fid, d in detail.items()
                                                              for i, b in enumerate(d["boxes"])})
        for fid, box, old, new, n in recoloured:
            log(f"{fid}: box {box}: colour {old or 'none'} -> {new} (the car's {n} boxes in this burst)")
        if recoloured:
            log(f"colour: {len(recoloured)} boxes took their car's colour across the burst")
        frames = check_anchors(frames, "after burst")
        if rejected:
            log("anchors: dropped or moved per car (a car with many may need a second anchor from another angle): "
                + ", ".join(f"{e} {n}" for e, n in rejected.most_common()))
        # burst consensus and neighbour aid can fill a smaller box again
        frames = keep_main_cars(frames, "after burst")
        frames = colour_check(frames, entries)
        colour_flagged = sum(1 for rs in frames.values() for r in rs if r.colour_flag)
        if colour_flagged:
            log(f"colour: flagged {colour_flagged} number reads whose entry's colour disagrees")

    # After consensus, so a burst-filled box is checked too. Solo shots only: see match.conflicts.
    # A hand-tagged image's box naming another entry is one too, whatever tags the two entries share;
    # one naming the hand-tagged entry never is, though its built tags may not include the tag that named it.
    shots = {}
    for image_id, results in frames.items():
        n_boxes = sum(1 for r in results if r.box >= 0)
        shots[image_id] = shot_type(n_boxes, MAX_BOXES)
        frames[image_id] = [replace(r, method="conflict") if r.entry_id and (
            disagrees(r, already_tagged(protected_of[image_id], entries), n_boxes == 1) if verify and image_id in fully_tagged
            else r.entry_id != hand_of.get(image_id) and conflicts(r.entry_id, protected_of[image_id], entries, n_boxes == 1)
            or image_id in hand_of and disagrees(r, hand_of[image_id], n_boxes == 1)) else r for r in results]

    by_method = write_results(args.results, frames, shots)
    if args.boxes_out or args.report_out:
        write_run_outputs(args, build_boxes(args.collection, frames, shots, detail, entries, counts, rules.sponsor_keywords,
                                            rules.min_read))
    write_collection_outputs(args, collection, entries, rules, from_entries)
    log("vehicles by method: " + ", ".join(f"{m} {n}" for m, n in sorted(by_method.items())))


# ---------------------------------------------------------------- add-reference / list modes

def screen_new_refs(collection: str, index: ReferenceIndex, done: list, mode: str, entries: dict,
                    colour_weight: float) -> list:
    """Checks the refs a job just saved against the refs saved before it, never against each other.
    A non-anchor ref unlike its car's anchors (Anchors.unlike: embedding joined with colour shares at
    `colour_weight`), or flagged by STRONG_MIN_FLAGS+ of the audit's per-ref checks, is bad: mode
    "warn" only logs it, "skip" also deletes it (or puts back the sample it replaced) and, when none
    of a row's refs survive, sets that row's status to "flagged". An anchor is never removed; its
    flags are logged. A car with no anchor before the job accepts its refs. Returns `done` with the
    statuses updated."""
    from audit_refs import STRONG_MIN_FLAGS, screen_refs
    new = [r for _, _, rels in done for r in rels]
    flags = screen_refs(collection, new)
    anchors = Anchors(index, {eid: e.car for eid, e in entries.items()}, colour_weight, skip=new)
    row = {rel: i for i, rel in enumerate(index.path)}
    out, removed = [], False
    for image_id, status, rels in done:
        bad = []
        for r in rels:
            strong = len(flags.get(r, ())) >= STRONG_MIN_FLAGS
            if index.is_anchor(r):
                if strong:
                    log(f"{image_id}: {r} is flagged by {', '.join(flags[r])}; kept, it's an anchor (check it by hand)")
                continue
            i = row[r]
            verdict, own, other_car, other = anchors.unlike(index.entry[i], index.emb[i],
                                                            index.hist[i] if index.colour else None)
            if verdict == "unlike":
                closer = f", closer to {other_car}'s {other:.3f}" if other_car else ""
                flags[r] = flags.get(r, []) + [f"unlike its anchors (sim {own:.3f}{closer})"]
            if verdict == "unlike" or strong:
                bad.append(r)
        for r in bad:
            log(f"{image_id}: {r} is flagged by {', '.join(flags[r])}" + ("; not saved" if mode == "skip" else "; kept, but the next audit would quarantine it"))
            if mode == "skip":
                if not index.restore(r):
                    index.remove(r)
                removed = True
        out.append((image_id, "flagged" if mode == "skip" and bad and len(bad) == len(rels) else status, rels))
    if removed:
        index.save()
    return out


_NOTE_RANK = {"": 0, "already": 1, "set": 2, "differs": 3}


def fill_colours(path: str, entries: dict, rules: Rules, done: list, proposed: list) -> list:
    """Writes the job's colour proposals (`proposed[i]`: [(entry id, colour, by hand)] for row
    `done[i]`; `by hand` may be left out) to entries.json in one entries_file.set_colours call. A
    colour read from the photo only fills an entry without one; a colour tag the user applied (`by
    hand`) also replaces the entry's colour, and is taken before any reading. The first proposal per
    entry wins. Returns each row's colour_note: "set", "differs", "already" (the entry holds that
    colour) or ""; a row with several outcomes reports the more serious (differs, set, then
    already). A file that can't be written is logged and its rows get no note."""
    names = [n for n, _ in rules.colour_palette] + [car_colour.MULTI]
    notes = [""] * len(done)
    chosen, rows_of = {}, {}  # entry id → colour; entry id → rows whose proposal is the chosen one
    replaced = {}  # entry id → the colour a hand tag replaces

    def mark(i, note):
        if _NOTE_RANK[note] > _NOTE_RANK[notes[i]]:
            notes[i] = note

    for hand_pass in (True, False):
        for i, ((image_id, status, _), props) in enumerate(zip(done, proposed)):
            if status == "flagged":
                continue
            for eid, colour, *by_hand in props:
                if bool(by_hand and by_hand[0]) != hand_pass:
                    continue
                if colour not in names:
                    log(f"{image_id}: colour {colour} isn't in rules.colour_palette, so entry {eid} doesn't get it")
                    continue
                stored = entries[eid].colour
                have = chosen.get(eid) or stored
                if eid not in chosen and (not stored or (hand_pass and colour != stored)):
                    chosen[eid] = colour
                    rows_of[eid] = [i]
                    if stored:
                        replaced[eid] = stored
                elif colour == chosen.get(eid):
                    rows_of[eid].append(i)
                elif eid not in chosen and colour == stored:
                    mark(i, "already")
                else:
                    where = "in entries.json" if eid not in chosen else \
                        "from a colour tag in this job" if eid in replaced else "from an earlier reference in this job"
                    what = "has the colour tag" if hand_pass else "reads"
                    log(f"entry {eid}: colour is {have} {where}, this reference {what} {colour}; left as {have}")
                    mark(i, "differs")
    if not chosen:
        return notes
    try:
        written, reason = entries_file.set_colours(path, chosen, replaced)
    except (OSError, ValueError) as e:
        log(f"couldn't update entries.json ({type(e).__name__}: {e})")
        return notes
    if not written:
        return notes
    for eid, colour in chosen.items():
        log(f"entry {eid}: colour changed from {replaced[eid]} to {colour} in entries.json (your colour tag)" if eid in replaced
            else f"entry {eid}: colour set to {colour} in entries.json")
        for i in rows_of[eid]:
            mark(i, "set")
    return notes


def reference_box(rgb, boxes: list, number: str) -> tuple:
    """(the box a hand-tagged frame's reference is cut from, why). `boxes` come largest first. The
    first box whose number reads as `number` wins ("number read"), so a pack shot saves the tagged car;
    else the largest the box check keeps ("largest car"), so a marshal or shed isn't saved; else the
    largest ("largest box", also every pick without SigLIP 2)."""
    reader = _W.get("reader")
    if number and reader and len(boxes) > 1:
        for b in boxes:
            if any(d == number for d, _ in reader.read(crop_box(rgb, b, OCR_CROP_DIM))):
                return b, "number read"
    kept = check_boxes(rgb, boxes)[0] if _W.get("siglip") else []
    return (kept[0], "largest car") if kept else (boxes[0], "largest box")


def run_reference_job(args, models: dict, handle_row, screen: str = "", siglip: bool = True):
    """Runs `handle_row(index, entries, rules, image_id, filepath, entry_id, hand_colour) -> (status,
    proposals[, row_entry])` over the manifest rows (an optional 4th column is the image's hand-applied
    colour), writing one `id,status,colour_note,entry_id` results row and a progress tick per row.
    `proposals` is [(entry id, colour, by hand)] for fill_colours; the row's entry id is `row_entry` when the
    handler gives one, else the first proposal's, else the manifest's (`""` when it has none).
    References added before a cancel are kept, colours aren't
    written; the reference index is saved either way. `screen` ("warn" or "skip") then checks the new
    refs with screen_new_refs; people collections are never screened."""
    collection = os.path.join(args.collections_root, args.collection)
    entries, rules, from_entries = load_collection(collection, args.settings)
    models["kind"] = rules.kind
    models["colour"] = rules.kind != "people" and rules.colour_weight > 0
    models["car_colour"] = rules.colour_palette if rules.kind != "people" and "colour" in rules.families else None
    models["segmenter"] = segmenter_path(models.get("detector", ""), models.get("segmenter", "")) if rules.kind != "people" else ""
    embedder = check_models(models, siglip)
    index = open_index(collection, models, rules, embedder, args.progress)
    rows = read_manifest(args.manifest, 3, optional=1)
    done = []  # (image id, status, refs the row saved)
    proposed = []  # per row: [(entry id, colour)]
    row_entries = []  # per row: the entry id the results row names
    cancelled = False
    for n, (image_id, filepath, entry_id, hand_colour) in enumerate(rows, 1):
        if cancel_requested(args.progress):
            cancelled = True
            break
        index.added = []
        status, proposals, *row_entry = handle_row(index, entries, rules, image_id, filepath, entry_id, hand_colour)
        done.append((image_id, status, list(index.added)))
        proposed.append(proposals)
        row_entries.append(row_entry[0] if row_entry else (proposals[0][0] if proposals else entry_id))
        write_progress(args.progress, n, len(rows), "matching")
    index.save()
    if cancelled:
        log("cancelled; references added so far are kept")
        sys.exit(130)
    if screen and rules.kind != "people":
        done = screen_new_refs(collection, index, done, screen, entries, rules.colour_weight)
    notes = fill_colours(os.path.join(collection, "entries.json"), entries, rules, done, proposed)
    with atomic_write(args.results, newline="") as f:
        f.writelines(f"{image_id},{status},{note},{eid}\n"
                     for (image_id, status, _), note, eid in zip(done, notes, row_entries))
    write_collection_outputs(args, collection, entries, rules, from_entries)


def add_references(args, models: dict):
    """Each manifest image becomes a reference for its entry (and, with the colour family on, reads
    the car's colour into entries.json). `args.colours_only` reads the colour alone: no reference
    is saved, team rows are "unread", and a row is "read" or "unread" by whether a colour came out."""
    teams = None
    colours_only = getattr(args, "colours_only", False)
    source = "picked" if getattr(args, "picked", False) else "hand"

    def handle_people(index, entries, rules, image_id, filepath, entry_id):
        if entry_id not in entries:
            log(f"{image_id}: entry {entry_id} isn't in {args.collection}'s entries.json")
            return "failed", []
        try:
            crop, status = reference_face(decode_rgb(filepath), index.embedder)
            if crop is None:
                log(f"{image_id}: {status.replace('_', ' ')}; a face reference needs a photo with exactly one face")
                return status, []
            log(f"{image_id}: reference {index.add(entry_id, image_id, crop, source)}")
            return "added", []
        except Exception as e:
            log(f"{image_id}: couldn't add reference ({type(e).__name__}: {e})")
            return "failed", []

    def handle(index, entries, rules, image_id, filepath, entry_id, hand_colour):
        nonlocal teams
        if rules.kind == "people":
            return handle_people(index, entries, rules, image_id, filepath, entry_id)
        if teams is None:
            teams = set(team_tags(entries, rules.families))
        # a team tag instead of an entry id: a solo shot tagged only to team level
        is_team = entry_id not in entries and entry_id in teams
        if entry_id not in entries and not is_team:
            log(f"{image_id}: entry {entry_id} isn't in {args.collection}'s entries.json")
            return "failed", []
        if colours_only and is_team:
            log(f"{image_id}: only tagged to {entry_id}; a team has no colour to fill")
            return "unread", []
        if is_team and not rules.partial_references:
            log(f"{image_id}: only tagged to {entry_id}; set rules.partial_references to save team references")
            return "team_refs_off", []
        try:
            rgb = decode_rgb(filepath)
            entry, _ = frame_entry(filepath, rgb, models)
            boxes, note = detect_vehicles(rgb, entry)
            if colours_only:
                colour = hand_colour or (car_colour.decide_colour(colour_read(crop_box(rgb, boxes[0]), rules.colour_palette))
                                         if boxes else "")
                if not colour:
                    log(f"{image_id}: " + (f"no vehicle found ({note})" if not boxes else "couldn't tell the car's colour") + "; colour unread")
                    return "unread", []
                return "read", [(entry_id, colour, bool(hand_colour))]
            if is_team and len(boxes) != 1:
                log(f"{image_id}: {len(boxes)} vehicles found; only a solo shot can be a team reference")
                return "team_not_solo", []
            if not boxes:
                log(f"{image_id}: no vehicle found ({note}); no reference saved")
                return "no_vehicle", []
            box, how = reference_box(rgb, boxes, "" if is_team else entries[entry_id].number)
            crop = crop_box(rgb, box)
            rel = index.add(team_key(entry_id) if is_team else entry_id, image_id, crop, source)
            log(f"{image_id}: reference {rel} ({how})")
            proposals = []
            if "colour" in rules.families and not is_team:
                colour = hand_colour or car_colour.decide_colour(colour_read(crop, rules.colour_palette))
                proposals = [(entry_id, colour, bool(hand_colour))] if colour else []
            return "added", proposals
        except Exception as e:
            log(f"{image_id}: couldn't add reference ({type(e).__name__}: {e})")
            return "failed", []

    if colours_only:
        collection = os.path.join(args.collections_root, args.collection)
        only_rules = load_collection(collection, args.settings)[1]
        if only_rules.kind == "people":
            raise InputError("Fill entry colours is for vehicle collections")
        if "colour" not in only_rules.families:
            raise InputError("Fill entry colours needs the colour family (family_colour) on")
    run_reference_job(args, models, handle, screen="" if colours_only else "warn")


def promote_boxes(args, models: dict):
    """Save each manifest image's confident vehicles (match.promotable) from the last run's
    boxes.json as references, cropped from the box itself, so a pack shot's tags land on the
    right car. Re-promoting a box replaces its sample."""
    try:
        with open(args.boxes_in, encoding="utf-8") as f:
            run = json.load(f)
        images, run_collection = run["images"], run["collection"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise InputError(f"{args.boxes_in}: can't read the last run's boxes ({type(e).__name__}: {e}); run Identify first") from e
    if run_collection != args.collection:
        raise InputError(f"the last run was for collection {run_collection!r}, not {args.collection!r}")
    if run.get("kind") == "people":
        raise InputError("promoting boxes isn't available for people collections; add face references from hand-tagged photos")

    def handle(index, entries, rules, image_id, filepath, _entry, hand_colour):
        record = images.get(image_id)
        wanted = [b for b in record["boxes"] if promotable(b) and b["entry"] in entries] if record else []
        if not wanted:
            return "none_promotable", []
        try:
            rgb = decode_rgb(filepath)
            if [rgb.shape[1], rgb.shape[0]] != record["frame"]:
                log(f"{image_id}: the file no longer matches the last run (frame size changed), skipped")
                return "stale", []
            proposals = []
            for b in wanted:
                rel = index.add(b["entry"], f"{image_id}_b{b['box']}", crop_box(rgb, b["bbox"]), "number", b.get("confidence"))
                log(f"{image_id}: box {b['box']} ({b['method']}) reference {rel}")
                # a boxes.json from before colour reading has no shares, so gives no colour
                by_hand = bool(hand_colour) and len(wanted) == 1
                colour = hand_colour if by_hand else car_colour.decide_colour(b.get("colour_shares", {}))
                if "colour" in rules.families and colour:
                    proposals.append((b["entry"], colour, by_hand))
            return "added", proposals, wanted[0]["entry"]
        except Exception as e:
            log(f"{image_id}: couldn't add references ({type(e).__name__}: {e})")
            return "failed", []

    run_reference_job(args, models, handle, screen="skip", siglip=False)


def audit_references(args, models: dict):
    """Reconciles the collection's index with refs/ (deleted or moved crops, changed models), then
    writes ref-audit.txt beside it. results is one `name,count` line per audit total plus `report,<path>`."""
    from audit_refs import AuditCancelled, write_audit
    collection = os.path.join(args.collections_root, args.collection)
    entries, rules, _ = load_collection(collection, args.settings)
    models["kind"] = rules.kind
    models["colour"] = rules.kind != "people" and rules.colour_weight > 0
    models["car_colour"] = rules.colour_palette if rules.kind != "people" and "colour" in rules.families else None
    models["segmenter"] = ""
    index = open_index(collection, models, rules, check_models(models, siglip=False), args.progress)
    if cancel_requested(args.progress):
        log("cancelled; no audit written")
        sys.exit(130)
    if len(set(index.entry)) < 2:
        raise InputError(f"{args.collection} needs references for at least 2 entries to audit; add some first")
    def on_progress(done, total):
        write_progress(args.progress, done, total)
        return not cancel_requested(args.progress)

    try:
        report, counts = write_audit(collection, detector=models["detector"], on_progress=on_progress,
                                     crops_wanted=args.suggest_crops, quarantine=args.quarantine)
    except AuditCancelled:
        log("cancelled; no audit written")
        sys.exit(130)
    log(f"reference audit: {counts}; wrote {report}")
    if counts["quarantined"]:
        index = open_index(collection, models, rules, check_models(models, siglip=False))  # drops the moved refs now, not at the next audit
        log(f"index refreshed after quarantine: {len(index.entry)} references")
    # Lua reads results once the process exits; never a half-written file
    with atomic_write(args.results, newline="") as f:
        f.writelines(f"{k},{v}\n" for k, v in counts.items())
        f.write(f"report,{report}\n")


def write_collection_outputs(args, collection: str, entries: dict, rules: Rules, from_entries: tuple):
    """entries.csv and rules.csv for assisted_tagging.lua, and the collection's tag-plan.txt for the user.
    Best effort: the run's results are already written."""
    if args.entries_out:
        best_effort("entries.csv", lambda: write_entries_csv(entries, args.entries_out))
    if args.rules_out:
        best_effort("rules.csv", lambda: write_rules_csv(rules, from_entries, args.rules_out))
    best_effort("tag-plan.txt", lambda: log(f"tag plan: {write_tag_plan(collection, args.collection, entries, rules)}"))


def list_mode(args):
    if args.collections_root:
        os.makedirs(args.collections_root, exist_ok=True)  # so the user can find where collections go
    names = list_collections(args.collections_root)
    if args.collections_out:
        with open(args.collections_out, "w", newline="", encoding="utf-8") as f:
            f.writelines(n + "\n" for n in names)
    if args.collection in names:
        collection = os.path.join(args.collections_root, args.collection)
        write_collection_outputs(args, collection, *load_collection(collection, args.settings))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Assisted Tagging identifier")
    parser.add_argument("manifest", help="Manifest CSV (- with --list)")
    parser.add_argument("results", help="Results CSV (- with --list)")
    parser.add_argument("--progress", default="", help="Progress file; <progress>.cancel cancels the run")
    parser.add_argument("--cache", default="", help="SQLite cache of per-frame analysis (empty = off)")
    parser.add_argument("--collections-root", default="", help="Folder holding one folder per collection")
    parser.add_argument("--collection", default="", help="Active collection's folder name")
    parser.add_argument("--settings", default="", help="settings file to use instead of the collection's settings.json")
    parser.add_argument("--detector", default="", help="object detector .onnx (YOLOX, D-FINE or RT-DETR)")
    parser.add_argument("--detections", default="",
                        help="SQLite cache of per-frame detections shared with culling (empty = off)")
    parser.add_argument("--segmenter", default="", help="EfficientSAM .onnx (default: next to the detector, if present)")
    parser.add_argument("--ocr-det", default="", help="text detection .onnx: PP-OCRv3 (opencv_zoo) or PaddleOCR (its .yml beside it)")
    parser.add_argument("--ocr-rec", default="", help="text recognition .onnx: PP-OCRv5 (its .yml beside it) or CRNN")
    parser.add_argument("--embedder", default="", help="DINOv2 .onnx")
    parser.add_argument("--siglip", default="",
                        help="SigLIP 2 vision .onnx (text model and tokenizer beside it): box check and colour reader")
    parser.add_argument("--face-detector", default="", help="YuNet .onnx (people collections)")
    parser.add_argument("--face-recognizer", default="", help="SFace .onnx (people collections)")
    parser.add_argument("--entries-out", default="", help="Write the collection's entries.csv here")
    parser.add_argument("--rules-out", default="", help="Write the collection's rules.csv here")
    parser.add_argument("--collections-out", default="", help="--list: write collection names here")
    parser.add_argument("--boxes-out", default="", help="Write the run's per-vehicle boxes.json here")
    parser.add_argument("--neighbours", default="",
                        help="CSV of unselected tagged photos (image id, capture epoch, entry id) that lend neighbour-aid support")
    parser.add_argument("--report-out", default="",
                        help="Write the run's debug report to <this>.md and <this>.json")
    parser.add_argument("--archive-dir", default="",
                        help="Also copy boxes.json and the report into <dir>/<YYYYMMDD-HHMMSS>/, keeping the newest 20 runs")
    parser.add_argument("--report-top", type=int, default=20, help="Per-category cap on box detail in report.md")
    parser.add_argument("--boxes-in",default="", help="--promote-boxes: the boxes.json to read")
    parser.add_argument("--promote-boxes", action="store_true",
                        help="Add each manifest image's confident vehicles from --boxes-in as references")
    parser.add_argument("--add-reference", action="store_true", help="Add each manifest image as a reference")
    parser.add_argument("--picked", action="store_true",
                        help="With --add-reference: the user chose each image's car (Add as reference); its refs are recorded as picked, not hand")
    parser.add_argument("--colours-only", action="store_true",
                        help="With --add-reference: read each car's colour into entries.json without saving a reference")
    parser.add_argument("--audit-refs", action="store_true",
                        help="Refresh the reference index, then write ref-audit.txt listing refs that look wrongly filed")
    parser.add_argument("--suggest-crops", action="store_true",
                        help="With --audit-refs, also write re-cropped copies of wide refs to ref-audit-crops/ for review")
    parser.add_argument("--quarantine", action="store_true",
                        help="With --audit-refs, move the strongest candidates (2+ checks) into refs-quarantine/ and list them in moved.txt")
    parser.add_argument("--list", action="store_true", help="List collections (and entries) only")
    parser.add_argument("--verify", action="store_true",
                        help="Also analyse fully tagged images and flag the ones whose result differs from their tags (the plugin then changes no tags)")
    args = parser.parse_args(argv)
    models = {"detector": args.detector, "ocr_det": args.ocr_det, "ocr_rec": args.ocr_rec,
              "embedder": args.embedder, "face_det": args.face_detector, "face_rec": args.face_recognizer,
              "segmenter": args.segmenter, "siglip": args.siglip, "detections": args.detections, "kind": DEFAULT_KIND}
    try:
        if args.list:
            list_mode(args)
        elif args.add_reference:
            add_references(args, models)
        elif args.promote_boxes:
            promote_boxes(args, models)
        elif args.audit_refs:
            audit_references(args, models)
        else:
            identify(args, models)
    except InputError as e:
        print(f"Assisted Tagging: {e}", file=sys.stderr, flush=True)
        sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)

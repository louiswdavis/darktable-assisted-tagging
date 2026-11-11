"""Assisted Tagging: identify the vehicles in each frame of a manifest and
write one result row per vehicle for assisted_tagging.lua.

Modes:
  identify.py MANIFEST RESULTS ...            id,filepath,burst_id[,protected tags,hint prefixes,capture epoch] →
                                              id,box,method,entry,alt_entry,confidence,unmatched_number,shot,order_flag,colour,colour_flag
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
import os
import re
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass, replace

from vehicles import MAX_BOXES, crop_box, detect, detect_vehicles, detector_model, file_key, load_full, load_hires, log
from common import atomic_write
from ocr import NumberReader, ocr_key
import car_colour
import entries_file
from colour import colour_hist
from embed import Embedder, decode, embedder_key, encode
from fingerprint import analysis_fingerprint
from match import (MATCH_MIN_MARGIN, MATCH_MIN_SIM, REFERENCE_MIN_MARGIN, WEAK_READ_MIN, BoxResult, Entry, agreeing_reads, already_tagged,
                   burst_consensus, colour_check, conflicts, decided_by, disagrees, entries_under, hinted_match, match_camera, match_livery,
                   match_team, pool_sims, promotable, shot_type, team_key, TEAM_KEY)
from neighbour import neighbour_aid
from overlap import HIDDEN, _inter, visible_boxes
from segment import SEGMENT_CACHE_TOKEN, Segmenter, needs_mask, segmenter_path
from pod import pod_colour, pod_reading
from rescue import RESCUE_MIN_SIM, plan_burst
from sponsors import sponsor_prefixes
from report import write_report
from kinds import DEFAULT_KIND, check_entry_fields, check_kind
from settings import DIAG_DEFAULTS, MOVED_RULES, diagnostics_of, load_settings
from reference_store import ReferenceIndex
from people import FACE_EMBED_DIM, FaceModel, face_model_key
from people_run import analyse_frame_people, build_boxes_people, match_frame_people, reference_face

MAX_WORKERS = 4  # each worker holds every model plus a full-resolution decode
CACHE_MAX_AGE_DAYS = 90
CACHE_COMMIT_EVERY = 50

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
    # Experimental: embed references after downscaling-then-upscaling them (embed.degrade),
    # so their embeddings sit closer to a far-away query crop's degraded detail level.
    blur_references: bool = False
    # ((lowercase keyword, tag prefix), …): a sponsor word read on a car hints its team's prefix
    # (see sponsors.sponsor_prefixes). Empty: off.
    sponsor_keywords: tuple = ()
    # Solo shots carrying only a team-prefix tag are accepted as team-level references.
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
    # Motorsport: a tag prefix for the whole collection. An entry's team is appended to it, its name
    # to that, and the entry's own `tags` are extras (see _entry_tags). "" keeps `tags` as the full list.
    tag_prefix: str = ""
    # Motorsport: how much the groups shot just before and after a photo help a doubtful number read
    # (neighbour.neighbour_aid): 0 ignores them (random order), 1 expects the numbers strictly in order.
    order_weight: float = 0.0
    # Motorsport: how many entries apart (in the sorted number list, wrapping round) a nearby group can be
    # and still support a doubtful read; used when the order weight is above 0.
    neighbour_tolerance: int = 5
    # Motorsport: the least confidence (lower of text detection and the reader's own) a number read needs
    # to count. Weaker reads stay in the box's OCR trace but name nothing.
    min_read: float = 0.85
    # Motorsport: read each car's body colour and write it as a tag (car_colour). Off: nothing runs.
    colour_tags: bool = False
    # ((tag name, ((hue_lo, hue_hi, sat_lo, sat_hi, val_lo, val_hi), ...)), ...): the colours read, in output order.
    colour_palette: tuple = car_colour.PALETTE


def _entry_tags(eid: str, item: dict, team: str, name: str, prefix: str, bad, number: str = "") -> tuple:
    """An entry's tags. Without a prefix, its `tags` list as written. With one: prefix|team,
    prefix|team|name (prefix|name with no team), then any extra `tags`, without repeats. A numbers-only
    entry (a number, no team, name or tags) gets prefix|number."""
    where = f'entry "{eid}": tags'
    if not prefix:
        if name:
            raise bad(f'entry "{eid}": name needs rules.tag_prefix; without one, list the full tags')
        _check_tags(item.get("tags"), where, bad)
        return tuple(item["tags"])
    extra = item.get("tags", [])
    _check_tags(extra, where, bad, allow_empty=True)
    built = [f"{prefix}|{team}"] if team else []
    if name:
        built.append(f"{prefix}|{team}|{name}" if team else f"{prefix}|{name}")
    if not built and not extra and number:
        built = [f"{prefix}|{number}"]
    if not built and not extra:
        raise bad(f'entry "{eid}": needs a team or name to build its tags from rules.tag_prefix, or its own tags')
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
    unknown = sorted(set(raw) - {"team_only", "unidentified", "sponsor_keywords", "tag_prefix", "colour_palette",
                                  "diagnostics", *MOVED_RULES})
    if unknown:
        raise bad(f'unknown rule "{unknown[0]}" (rules are team_only, unidentified, sponsor_keywords, '
                   f'tag_prefix, colour_palette; behaviour settings such as order_weight go in settings.json)')
    defaults = Rules()
    colour_palette = _load_palette(raw["colour_palette"], bad) if "colour_palette" in raw else defaults.colour_palette
    tag_prefix = raw.get("tag_prefix", defaults.tag_prefix)
    if not isinstance(tag_prefix, str) or _BAD_TAG.search(tag_prefix) or tag_prefix != tag_prefix.strip("| "):
        raise bad('rules.tag_prefix must be a tag path like "Motorsport|F1": no , ; " and no leading or trailing |')
    sponsors = raw.get("sponsor_keywords", {})
    if not isinstance(sponsors, dict) or not all(
            isinstance(k, str) and k.strip() and k == k.lower() and isinstance(v, str) and v.strip()
            and not _BAD_TAG.search(v) for k, v in sponsors.items()):
        raise bad("rules.sponsor_keywords must map lowercase keywords to tag prefixes")
    team_only = raw.get("team_only", "shared tags")
    if team_only not in TEAM_ONLY_CHOICES:
        raise bad('rules.team_only must be "shared tags" or "none"')
    unidentified = raw.get("unidentified", [])
    _check_tags(unidentified, "rules.unidentified", bad, allow_empty=True)
    return dict(team_only=team_only, unidentified=tuple(unidentified), sponsor_keywords=tuple(sponsors.items()),
                tag_prefix=tag_prefix, colour_palette=colour_palette)


def load_collection(collection_dir: str, settings_path: str = "") -> tuple:
    """entries.json + settings.json → ({id: Entry} in file order, Rules, the settings keys that came from
    entries.json rules). The file is either a list of entries or {"rules": {...}, "entries": [...]}.
    Raises InputError naming the file."""
    path = os.path.join(collection_dir, "entries.json")

    def bad(why):
        return InputError(f"{path}: {why}")

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
    values, from_entries = load_settings(collection_dir, rules_raw, log, settings_path)
    rules = Rules(**_load_rules(rules_raw, bad), **{k: values[k] for k in MOVED_RULES},
                  diagnostics=diagnostics_of(values), kind=kind)
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
            fields = "id, tags" if kind == "people" else "id, number, team, name, tags, camera, colour"
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
        camera = item.get("camera", "")
        if camera not in ("", "yellow", "black"):
            raise bad(f'entry "{eid}": camera must be "yellow" or "black"')
        colour = item.get("colour", "")
        colours = [n for n, _ in rules.colour_palette] + [car_colour.MULTI]
        if colour != "" and colour not in colours:
            raise bad(f'entry "{eid}": colour "{colour}" is not one of {", ".join(colours)}')
        entries[eid] = Entry(eid, number, team, _entry_tags(eid, item, team, name, rules.tag_prefix, bad, number), camera, colour)
    if kind == "people":
        if rules_raw is None:
            log("warning: entries.json has no rules block, so the face thresholds use defaults")
        return entries, rules, from_entries
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
            f.write(f"{e.id},{e.team},{e.number},{';'.join(e.tags)}\n")


def write_rules_csv(rules: Rules, from_entries: tuple, path: str):
    """key,value lines for assisted_tagging.lua: team_only, unidentified (tags joined by ;), diag_<outcome>,
    each moved setting, and from_entries_json (the settings keys still read from entries.json, joined by ;)."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write(f"team_only,{rules.team_only}\n")
        f.write(f"unidentified,{';'.join(rules.unidentified)}\n")
        for key, name in rules.diagnostics:
            f.write(f"diag_{key},{name}\n")
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
    lines += ["", "Unidentified (no vehicle, or no confident match): rules.unidentified."]
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
            "ocr-trace-2", "read-conf-1", "pod-2", "cand-1", "overlap-2", *(["colour-1"] if models.get("colour") else []),
            *(["car-colour-1", car_colour.palette_digest(models["car_colour"])] if models.get("car_colour") else []),
            *([SEGMENT_CACHE_TOKEN, file_key(models["segmenter"])] if models.get("segmenter") else [])]


# ---------------------------------------------------------------- progress

def write_progress(progress_path: str, cur: int, tot: int):
    if not progress_path:
        return
    for _ in range(8):
        try:
            with open(progress_path, "w", encoding="utf-8") as pf:
                pf.write(f"{cur},{tot}")
            return
        except OSError:
            time.sleep(0.02)


def cancel_requested(progress_path: str) -> bool:
    return bool(progress_path) and os.path.exists(progress_path + ".cancel")


# ---------------------------------------------------------------- per-frame analysis (workers)

_W: dict = {}


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
    _W["reader"] = NumberReader(models["ocr_det"], models["ocr_rec"])
    _W["embedder"] = Embedder(models["embedder"])
    _W["segmenter"] = Segmenter(models["segmenter"]) if models.get("segmenter") else None


def analyse_frame(filepath: str) -> dict:
    """Boxes, OCR candidates and embeddings for one frame: the cached value."""
    rgb = load_full(filepath)
    if _W["models"]["kind"] == "people":
        return analyse_frame_people(rgb, _W["faces"])
    boxes, weak, note = detect(rgb, _W["models"]["detector"])
    h, w = rgb.shape[:2]
    out = _read_boxes(rgb, boxes)
    out.update(note=note, frame=[w, h], candidates=[list(b) for b in weak])
    return out


def _read_boxes(rgb, boxes: list, hi=None) -> dict:
    """OCR candidates, pod reading and embedding of each box, in the analysis shape. With `hi`, a
    sharper decode of the same frame, the crops (OCR, embedding, colour) come from it; boxes stay in
    `rgb`'s pixels."""
    ocr, trace, emb, pod, hist, overlap, masked, shares = [], [], [], [], [], [], [], []
    palette = _W["models"].get("car_colour")
    scale = hi.shape[1] / rgb.shape[1] if hi is not None else 1.0
    seen_boxes = visible_boxes(boxes)
    wants_mask = needs_mask(boxes, [state for _, state in seen_boxes]) if _W.get("segmenter") else [False] * len(boxes)
    for i, (b, (seen, state)) in enumerate(zip(boxes, seen_boxes)):
        overlap.append(state)
        pod.append(pod_reading(rgb, seen))
        src, area = (rgb if hi is None else hi), tuple(v * scale for v in seen[:4])
        cut = None
        if wants_mask[i]:
            near = [tuple(v * scale for v in o[:4]) for j, o in enumerate(boxes) if j != i and _inter(b, o) > 0]
            cut = _W["segmenter"].cut(src, area, near)
        masked.append(cut is not None)
        crop = crop_box(*cut) if cut else crop_box(src, area)
        ocr.append([[d, c] for d, c in _W["reader"].read(crop)])
        trace.append(_W["reader"].last_trace)
        emb.append(encode(_W["embedder"].embed(crop)))
        if _W["models"].get("colour"):
            hist.append(encode(colour_hist(crop)))
        if palette:
            shares.append({} if state == HIDDEN else car_colour.colour_shares(crop, palette, masked=cut is not None))
    out = {"boxes": [list(b) for b in boxes], "ocr": ocr, "ocr_trace": trace, "pod": pod, "emb": emb, "overlap": overlap, "masked": masked}
    if hist:
        out["hist"] = hist
    if palette:
        out["car_colour"] = shares
    return out


def rescue_frame(job: tuple):
    """(path, candidate box, mate path, mate's encoded embedding) → the frame's analysis with the
    candidate as its one box, or None when its crop doesn't look like the mate's (the sim is under
    RESCUE_MIN_SIM). The analysis carries `rescued` {from, sim}."""
    path, box, mate_path, mate_emb = job
    rgb = load_full(path)
    sim = float((_W["embedder"].embed(crop_box(rgb, box)) * decode(mate_emb)).sum())
    if sim < RESCUE_MIN_SIM:
        return None
    h, w = rgb.shape[:2]
    out = _read_boxes(rgb, [box])
    out.update(note="", frame=[w, h], candidates=[], rescued={"from": os.path.basename(mate_path), "sim": round(sim, 4)})
    return out


HIRES_MIN_GAIN = 1.3  # a sharper decode must be this much wider than the preview to be worth re-reading
HIRES_ASPECT_TOL = 0.02  # ...and frame the same picture: aspect ratios within this share


def hires_frame(job: tuple):
    """(path, the analysis's boxes) → every box re-read from a sharper decode of the frame (the analysis
    shape), or {} when there is none: not a RAW, not enough wider than the preview, or framed differently."""
    path, boxes = job
    hi = load_hires(path)
    if hi is None:
        return {}
    rgb = load_full(path)
    if hi.shape[1] < HIRES_MIN_GAIN * rgb.shape[1] or \
            abs(hi.shape[1] / hi.shape[0] / (rgb.shape[1] / rgb.shape[0]) - 1) > HIRES_ASPECT_TOL:
        return {}
    return _read_boxes(rgb, [tuple(b) for b in boxes], hi)


# ---------------------------------------------------------------- identify mode

def read_manifest(path: str, columns: int, optional: int = 0) -> list:
    """Rows of `columns` + `optional` fields; a row may omit the optional ones (read as "")."""
    with open(path, newline="", encoding="utf-8") as f:
        return [(row + [""] * optional)[:columns + optional] for row in csv.reader(f) if len(row) >= columns]


def strict_prefixes(entries: dict) -> list:
    """Every tag path that is a strict prefix of some entry tag, in first-seen order."""
    found = {}
    for e in entries.values():
        for t in e.tags:
            parts = t.split("|")
            for n in range(1, len(parts)):
                found["|".join(parts[:n])] = True
    return list(found)


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
            f"{r.colour},{'1' if r.colour_flag else ''}")


def describe_box(r: BoxResult, ocr: list, sims: list, box: list, frame: list) -> str:
    seen = "/".join(d for d, _ in ocr) or "-"
    top = ", ".join(f"{e} {s:.3f}" for e, s in sims[:2]) or "no references"
    unmatched = f"; number seen but unmatched: {r.unmatched_number}" if r.unmatched_number else ""
    bw, bh = box[2] - box[0], box[3] - box[1]
    fw, fh = frame
    frac = f"; box {bw:.0f}x{bh:.0f} ({bw * bh / max(fw * fh, 1):.1%} of frame)"
    colour = f"; colour {r.colour}" if r.colour else ""
    return f"box {r.box}: {r.method} {r.entry_id or '-'} (OCR {seen}; livery {top}{unmatched}{colour}{frac})"


def check_models(models: dict):
    """Every model exists and loads, so a bad one fails the run here, not per frame. Returns the
    loaded embedder (a FaceModel for people collections) for the run's reference index."""
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
    loaders = (("object detector", "detector", lambda: detector_model(models["detector"])),
               ("OCR", "ocr_det", lambda: NumberReader(models["ocr_det"], models["ocr_rec"])),
               ("embedder", "embedder", lambda: Embedder(models["embedder"])),
               *([("segmenter", "segmenter", lambda: Segmenter(models["segmenter"]))] if models.get("segmenter") else []))
    loaded = {}
    for label, key, load in loaders:
        try:
            loaded[key] = load()
        except Exception as e:
            raise InputError(f"{label} model can't be loaded ({models[key]}): {type(e).__name__}: {e}. "
                             f"Download it again (see the README).") from e
    log(f"number reader: {loaded['ocr_det'].rec.name} ({os.path.basename(models['ocr_rec'])})")
    return loaded["embedder"]


def worker_count(cpus: int) -> int:
    return max(1, min(cpus - 1, MAX_WORKERS))


def run_frames(paths: list, models: dict, cache: IdentifyCache, progress: str) -> dict:
    """filepath → analysis (cached or fresh); a frame that fails to decode maps to None."""
    unique = list(dict.fromkeys(paths))  # darktable duplicates and versions share a file
    done, total, out, todo = 0, len(unique), {}, []
    for p in unique:
        hit = cache.get(*frame_key(p, models))
        if hit is not None:
            out[p] = hit
            done += 1
        else:
            todo.append(p)
    log(f"analysing: {total} frames, {done} from cache, {len(todo)} to decode")
    write_progress(progress, done, total)
    if not todo:
        return out
    workers = worker_count(os.cpu_count() or 2)
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers, initializer=_init_worker,
                                                initargs=(models,)) as executor:
        futures = {executor.submit(analyse_frame, p): p for p in todo}
        for fut in concurrent.futures.as_completed(futures):
            if cancel_requested(progress):
                log("cancelled")
                executor.shutdown(wait=False, cancel_futures=True)
                cache.close()
                sys.exit(130)
            p = futures[fut]
            try:
                out[p] = fut.result()
                cache.put(out[p], *frame_key(p, models))
            except concurrent.futures.process.BrokenProcessPool as e:
                raise InputError(f"an analysis worker died (out of memory or a crashed library?); "
                                 f"frames finished so far are cached, rerun to continue: {e}") from e
            except Exception as e:
                log(f"{p}: couldn't analyse ({type(e).__name__}: {e})")
                out[p] = None
            done += 1
            write_progress(progress, done, total)
    return out


def rescue_frames(rows: list, analyses: dict, models: dict, progress: str = "") -> dict:
    """analyses with the frames the detector missed filled in from burst-mates: for a no-vehicle
    frame in a burst that has vehicle frames, a weak candidate that tracks a mate's box becomes its
    box when its crop looks like the mate's (rescue.py). Not cached: it depends on the burst."""
    bursts: dict = {}
    seen = set()
    for _id, filepath, burst, *_rest, taken in rows:
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
    log(f"rescue: {len(jobs)} frames with no vehicle have a candidate where a burst-mate's car is")
    out = dict(analyses)
    write_progress(progress, 0, len(jobs))
    with concurrent.futures.ProcessPoolExecutor(max_workers=min(worker_count(os.cpu_count() or 2), len(jobs)),
                                                initializer=_init_worker, initargs=(models,)) as executor:
        for n, (job, result) in enumerate(zip(jobs, executor.map(rescue_frame, jobs)), 1):
            if cancel_requested(progress):
                log("cancelled")
                executor.shutdown(wait=False, cancel_futures=True)
                sys.exit(130)
            write_progress(progress, n, len(jobs))
            if result is None:
                log(f"{job[0]}: rescue candidate doesn't look like {os.path.basename(job[2])}'s car, left as no vehicle")
                continue
            log(f"{job[0]}: rescued a vehicle from {result['rescued']['from']} (crop similarity {result['rescued']['sim']})")
            out[job[0]] = result
    return out


def hires_key(boxes: list) -> list:
    """The re-read's cache key parts: the box list is in it, so a box rescued from a burst
    never reuses a re-read made without it."""
    digest = hashlib.sha1(json.dumps(sorted(boxes, key=repr), default=str).encode()).hexdigest()[:12]
    return ["hires-2", digest]


def refine_frames(wanted: dict, analyses: dict, models: dict, cache_path: str, progress: str = "") -> dict:
    """analyses with the boxes in `wanted` (filepath → box indices) re-read from a sharper decode of
    the frame: OCR, embedding and colour replace the first-pass ones, and `hires` lists the boxes
    that changed. The re-read of a frame's every box is cached, so a rerun doesn't decode again."""
    cache = IdentifyCache(cache_path)
    try:
        reads, todo = {}, []
        for p in wanted:
            hit = cache.get(*frame_key(p, models), *hires_key(analyses[p]["boxes"]))
            if hit is None:
                todo.append(p)
            else:
                reads[p] = hit
        log(f"refining: {len(wanted)} frames have boxes to re-read at higher detail, {len(reads)} from cache, {len(todo)} to decode")
        if todo:
            with concurrent.futures.ProcessPoolExecutor(max_workers=min(worker_count(os.cpu_count() or 2), len(todo)),
                                                        initializer=_init_worker, initargs=(models,)) as executor:
                futures = {executor.submit(hires_frame, (p, analyses[p]["boxes"])): p for p in todo}
                done, started = 0, time.time()
                write_progress(progress, 0, len(todo))
                for fut in concurrent.futures.as_completed(futures):
                    if cancel_requested(progress):
                        log("cancelled")
                        executor.shutdown(wait=False, cancel_futures=True)
                        cache.close()
                        sys.exit(130)
                    p = futures[fut]
                    try:
                        reads[p] = fut.result()
                        cache.put(reads[p], *frame_key(p, models), *hires_key(analyses[p]["boxes"]))
                    except Exception as e:
                        log(f"{p}: couldn't re-read at higher detail ({type(e).__name__}: {e}), first pass kept")
                    done += 1
                    write_progress(progress, done, len(todo))
                    if done % 10 == 0 or done == len(todo):
                        log(f"refining: {done}/{len(todo)} done, {time.time() - started:.0f}s")
    finally:
        cache.close()
    out = dict(analyses)
    for p, idx in wanted.items():
        read = reads.get(p)
        if not read:
            continue
        a = dict(analyses[p])
        for key in ("ocr", "ocr_trace", "emb", "hist", "car_colour"):
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
                sponsor_keywords: tuple = ()) -> dict:
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
                          "colour": r.colour, "colour_shares": b.get("colour_shares", {})})
        images[image_id] = {"shot": shots[image_id], "status": status, "file": d["file"], "frame": d["frame"],
                            "burst": d["burst"], "time": d["time"], "note": d["note"], "boxes": boxes}
    return {"collection": collection,
            "thresholds": {"min_sim": MATCH_MIN_SIM, "min_margin": MATCH_MIN_MARGIN,
                           "reference_margin": REFERENCE_MIN_MARGIN},
            "sponsor_keywords": dict(sponsor_keywords),
            "entries": {e.id: {"team": e.team, "number": e.number, "tags": list(e.tags), "camera": e.camera,
                                    "refs": counts.get(e.id, 0)}
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
        reads = [tuple(c) for c in ocr if c[1] >= rules.min_read]
        r, hint = hinted_match(i, reads, sims, entries, prefixes, source)
        r = match_team(r, team_sims, entries)
        pod = a["pod"][i]
        before = r.entry_id
        r = match_camera(r, pod_colour(pod), entries)
        if r.entry_id != before and not quiet:
            log(f"{image_id}: pod {pod_colour(pod)} moved {before} -> {r.entry_id}")
        overlap = a.get("overlap", [""] * len(a["ocr"]))[i]
        shares = a["car_colour"][i] if "car_colour" in a else {}
        if overlap == HIDDEN:
            r = BoxResult(i, "none")
        elif shares:
            r = replace(r, colour=car_colour.decide_colour(shares))
        if not quiet:
            log(f"{image_id}: {describe_box(r, ocr, sims, a['boxes'][i], a['frame'])}"
                + (f" [hint {';'.join(prefixes)} ({source}){', dropped: ' + hint['reason'] if hint['dropped'] else ''}]" if hint else "")
                + (" [higher detail]" if a.get("hires", [])[i:i + 1] == [True] else "")
                + (" [masked]" if a.get("masked", [])[i:i + 1] == [True] else ""))
        results.append(r)
        boxes_out.append({"bbox": [float(v) for v in a["boxes"][i][:4]], "score": float(a["boxes"][i][4]),
                          "ocr": ocr, "sims": sims, "ocr_trace": trace, "pod": pod, "pod_colour": pod_colour(pod), "hint": hint,
                          "overlap": overlap, "hires": a.get("hires", [])[i:i + 1] == [True], "masked": a.get("masked", [])[i:i + 1] == [True], "rescued": a.get("rescued", {}),
                          "colour_shares": shares})
        if i == 0:
            box0_sims[image_id] = sims
    return results


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
        write_progress(progress, done, total)
        return not cancel_requested(progress)

    if rules.kind == "people":
        return ReferenceIndex.load(collection, embedder, face_model_key(models["face_det"], models["face_rec"]),
                                   dim=FACE_EMBED_DIM, on_progress=on_progress)
    return ReferenceIndex.load(collection, embedder, [embedder_key(models["embedder"]), rules.blur_references],
                               rules.blur_references, colour=rules.colour_weight > 0, on_progress=on_progress)


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
        analyses = run_frames([r[1] for r in rows if verify or r[0] not in fully_tagged], models, cache, args.progress)
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
    models["car_colour"] = rules.colour_palette if rules.kind != "people" and rules.colour_tags else None
    models["segmenter"] = segmenter_path(models.get("detector", ""), models.get("segmenter", "")) if rules.kind != "people" else ""
    embedder = check_models(models)
    if rules.kind == "people":
        return identify_people(args, models, entries, rules, from_entries, collection, embedder)
    rows = read_manifest(args.manifest, 3, 3)
    # 4th column: entry tags the user applied by hand (never ledgered by the plugin), ";"-joined.
    protected_of = {r[0]: {t for t in r[3].split(";") if t} for r in rows}
    verify = getattr(args, "verify", False)
    # 5th column: hand-applied tags that are a strict prefix of an entry's tags (team hints), ";"-joined.
    # --verify checks the tags, so they must not steer the match.
    tag_hints_of = {r[0]: [] if verify else [t for t in r[4].split(";") if t] for r in rows}
    fully_tagged = {i for i, p in protected_of.items() if already_tagged(p, entries)}
    index = open_index(collection, models, rules, embedder, args.progress)
    if cancel_requested(args.progress):
        log("cancelled")
        sys.exit(130)
    counts = index.count_by_entry()
    if not counts:
        log(f"collection {args.collection} has no references yet: only numbers can identify a car")
    else:
        log("references: " + ", ".join(f"{e} {counts.get(e, 0)}" for e in entries))
    unknown = sorted(k for k in set(counts) - set(entries) if not k.startswith(TEAM_KEY))
    team_of = {team_key(p): p for p in strict_prefixes(entries)} if rules.partial_references else {}
    if unknown:
        log("references for entries not in entries.json (ignored): " + ", ".join(unknown))

    cache = IdentifyCache(args.cache)
    try:
        analyses = run_frames([r[1] for r in rows if verify or r[0] not in fully_tagged], models, cache, args.progress)
    finally:
        cache.close()
    if cancel_requested(args.progress):
        log("cancelled")
        sys.exit(130)
    # --verify compares each frame's own reading with its tags: no inference from burst mates
    if not verify:
        analyses = rescue_frames(rows, analyses, models, args.progress)

    def match_all(analyses: dict, quiet: bool = False) -> tuple:
        frames, burst_of, box0_sims, detail = {}, {}, {}, {}
        for image_id, filepath, burst, _protected, _hints, taken in rows:
            burst_of[image_id] = burst
            detail[image_id] = {"file": filepath, "frame": [], "boxes": [], "note": "", "burst": burst,
                                "time": int(taken) if taken.isdigit() else None}
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
        analyses = refine_frames(wanted, analyses, models, args.cache, args.progress)
    frames, burst_of, box0_sims, detail = match_all(analyses)
    if not verify:
        weak = {fid: {i: [tuple(c) for c in b["ocr"] if WEAK_READ_MIN <= c[1] < rules.min_read]
                      for i, b in enumerate(d["boxes"]) if b["overlap"] != HIDDEN}
                for fid, d in detail.items()}
        agreed = agreeing_reads(frames, burst_of, weak, entries)
        for fid, rs in agreed.items():
            for a, b in zip(rs, frames[fid]):
                if a.method != b.method:
                    log(f"{fid}: box {a.box}: number {a.entry_id} (weak read {a.confidence:.2f}, agreed across the group)")
        frames = agreed
    if rules.burst_livery_pooling and not verify:
        frames = pool_burst_livery(frames, burst_of, box0_sims, entries)
    shooting_order = {i: (d["time"] if d["time"] is not None else 0, d["file"]) for i, d in detail.items()}
    if not verify and rules.order_weight > 0:
        times = {i: d["time"] or 0 for i, d in detail.items()}
        emb_cache: dict = {}

        def box_emb(fid: str, box: int):
            if (fid, box) not in emb_cache:
                a = analyses.get(detail[fid]["file"])
                embs = a.get("emb", []) if a else []
                emb_cache[fid, box] = decode(embs[box]) if 0 <= box < len(embs) else None
            return emb_cache[fid, box]

        def similar(fid: str, box: int, ofid: str, obox: int):
            a, b = box_emb(fid, box), box_emb(ofid, obox)
            return None if a is None or b is None else float((a * b).sum())

        aided = neighbour_aid(frames, burst_of, times, entries, rules.neighbour_tolerance, rules.order_weight, similar)
        resolved = 0
        for i, rs in aided.items():
            for a, b in zip(rs, frames[i]):
                if a.method == "neighbour" and b.method != "neighbour":
                    resolved += 1
                    how = f"read {b.unmatched_number}, fits the number order" if a.via == "order" else "looks like a nearby car"
                    log(f"{i}: box {a.box}: neighbour {a.entry_id} ({how}, {a.confidence:.3f})")
        flagged = sum(1 for rs in aided.values() for r in rs if r.order_flag)
        log(f"neighbour: resolved {resolved}, flagged {flagged} (order weight {rules.order_weight:g}, tolerance {rules.neighbour_tolerance})")
        frames = aided
    if not verify:
        frames = colour_check(frames, entries)
        colour_flagged = sum(1 for rs in frames.values() for r in rs if r.colour_flag)
        if colour_flagged:
            log(f"colour: flagged {colour_flagged} number reads whose entry's colour disagrees")
        frames = burst_consensus(frames, burst_of, entries, shooting_order, box0_sims)

    # After consensus, so a burst-filled box is checked too. Solo shots only: see match.conflicts.
    shots = {}
    for image_id, results in frames.items():
        n_boxes = sum(1 for r in results if r.box >= 0)
        shots[image_id] = shot_type(n_boxes, MAX_BOXES)
        frames[image_id] = [replace(r, method="conflict") if r.entry_id and (
            disagrees(r, already_tagged(protected_of[image_id], entries), n_boxes == 1) if verify and image_id in fully_tagged
            else conflicts(r.entry_id, protected_of[image_id], entries, n_boxes == 1)) else r for r in results]

    by_method = write_results(args.results, frames, shots)
    if args.boxes_out or args.report_out:
        write_run_outputs(args, build_boxes(args.collection, frames, shots, detail, entries, counts, rules.sponsor_keywords))
    write_collection_outputs(args, collection, entries, rules, from_entries)
    log("vehicles by method: " + ", ".join(f"{m} {n}" for m, n in sorted(by_method.items())))


# ---------------------------------------------------------------- add-reference / list modes

def screen_new_refs(collection: str, index: ReferenceIndex, done: list, mode: str) -> list:
    """Runs the audit's per-ref checks over the refs a job just saved. A ref flagged by
    STRONG_MIN_FLAGS+ checks is one the next audit would quarantine: mode "warn" only logs it,
    "skip" also deletes it (or puts back the sample it replaced) and, when none of a row's refs survive, sets that row's status to
    "flagged". Returns `done` with the statuses updated."""
    from audit_refs import STRONG_MIN_FLAGS, screen_refs
    flags = screen_refs(collection, [r for _, _, rels in done for r in rels])
    out, removed = [], False
    for image_id, status, rels in done:
        bad = [r for r in rels if len(flags.get(r, ())) >= STRONG_MIN_FLAGS]
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


_NOTE_RANK = {"": 0, "set": 1, "differs": 2, "layout": 3}


def fill_colours(path: str, entries: dict, rules: Rules, done: list, proposed: list) -> list:
    """Writes the job's colour proposals (`proposed[i]`: [(entry id, colour)] for row `done[i]`) to
    entries.json in one entries_file.set_colours call. Only entries without a colour get one; the first
    proposal per entry wins. Returns each row's colour_note: "set", "differs", "layout" or ""; a row
    with several outcomes reports the most serious (layout, then differs, then set)."""
    names = [n for n, _ in rules.colour_palette] + [car_colour.MULTI]
    notes = [""] * len(done)
    chosen, rows_of = {}, {}  # entry id → colour; entry id → rows whose proposal is the chosen one

    def mark(i, note):
        if _NOTE_RANK[note] > _NOTE_RANK[notes[i]]:
            notes[i] = note

    for i, ((image_id, status, _), props) in enumerate(zip(done, proposed)):
        if status == "flagged":
            continue
        for eid, colour in props:
            if colour not in names:
                log(f"{image_id}: colour {colour} isn't in rules.colour_palette, so entry {eid} doesn't get it")
                continue
            have = entries[eid].colour or chosen.get(eid, "")
            if not have:
                chosen[eid] = colour
                rows_of.setdefault(eid, []).append(i)
            elif colour == chosen.get(eid) and not entries[eid].colour:
                rows_of[eid].append(i)
            elif colour != have:
                where = "in entries.json" if entries[eid].colour else "from an earlier reference in this job"
                log(f"entry {eid}: colour is {have} {where}, this reference reads {colour}; left as {have}")
                mark(i, "differs")
    if not chosen:
        return notes
    try:
        written, reason = entries_file.set_colours(path, chosen)
    except (OSError, ValueError) as e:
        log(f"couldn't update entries.json ({type(e).__name__}: {e})")
        written, reason = False, "layout"
    for eid, colour in chosen.items():
        if written:
            log(f"entry {eid}: colour set to {colour} in entries.json")
        elif reason == "layout":
            log(f'entries.json isn\'t one entry per line; add "colour": "{colour}" to entry {eid} by hand')
        else:
            continue
        for i in rows_of[eid]:
            mark(i, "set" if written else "layout")
    return notes


def run_reference_job(args, models: dict, handle_row, screen: str = ""):
    """Runs `handle_row(index, entries, rules, image_id, filepath, entry_id, hand_colour) -> (status,
    proposals)` over the manifest rows (an optional 4th column is the image's hand-applied colour),
    writing one `id,status,colour_note` results row and a progress tick per row. `proposals` is
    [(entry id, colour)] for fill_colours. References added before a cancel are kept, colours aren't
    written; the reference index is saved either way. `screen` ("warn" or "skip") then checks the new
    refs with screen_new_refs; people collections are never screened."""
    collection = os.path.join(args.collections_root, args.collection)
    entries, rules, from_entries = load_collection(collection, args.settings)
    models["kind"] = rules.kind
    models["colour"] = rules.kind != "people" and rules.colour_weight > 0
    models["car_colour"] = rules.colour_palette if rules.kind != "people" and rules.colour_tags else None
    models["segmenter"] = segmenter_path(models.get("detector", ""), models.get("segmenter", "")) if rules.kind != "people" else ""
    embedder = check_models(models)
    index = open_index(collection, models, rules, embedder, args.progress)
    rows = read_manifest(args.manifest, 3, optional=1)
    done = []  # (image id, status, refs the row saved)
    proposed = []  # per row: [(entry id, colour)]
    cancelled = False
    for n, (image_id, filepath, entry_id, hand_colour) in enumerate(rows, 1):
        if cancel_requested(args.progress):
            cancelled = True
            break
        index.added = []
        status, proposals = handle_row(index, entries, rules, image_id, filepath, entry_id, hand_colour)
        done.append((image_id, status, list(index.added)))
        proposed.append(proposals)
        write_progress(args.progress, n, len(rows))
    index.save()
    if cancelled:
        log("cancelled; references added so far are kept")
        sys.exit(130)
    if screen and rules.kind != "people":
        done = screen_new_refs(collection, index, done, screen)
    notes = fill_colours(os.path.join(collection, "entries.json"), entries, rules, done, proposed)
    with atomic_write(args.results, newline="") as f:
        f.writelines(f"{image_id},{status},{note}\n" for (image_id, status, _), note in zip(done, notes))
    write_collection_outputs(args, collection, entries, rules, from_entries)


def add_references(args, models: dict):
    teams = None

    def handle_people(index, entries, rules, image_id, filepath, entry_id):
        if entry_id not in entries:
            log(f"{image_id}: entry {entry_id} isn't in {args.collection}'s entries.json")
            return "failed", []
        try:
            crop, status = reference_face(load_full(filepath), index.embedder)
            if crop is None:
                log(f"{image_id}: {status.replace('_', ' ')}; a face reference needs a photo with exactly one face")
                return status, []
            log(f"{image_id}: reference {index.add(entry_id, image_id, crop)}")
            return "added", []
        except Exception as e:
            log(f"{image_id}: couldn't add reference ({type(e).__name__}: {e})")
            return "failed", []

    def handle(index, entries, rules, image_id, filepath, entry_id, hand_colour):
        nonlocal teams
        if rules.kind == "people":
            return handle_people(index, entries, rules, image_id, filepath, entry_id)
        if teams is None:
            teams = set(strict_prefixes(entries))
        # a team prefix instead of an entry id: a solo shot tagged only to team level
        is_team = entry_id not in entries and entry_id in teams
        if entry_id not in entries and not is_team:
            log(f"{image_id}: entry {entry_id} isn't in {args.collection}'s entries.json")
            return "failed", []
        if is_team and not rules.partial_references:
            log(f"{image_id}: only tagged to {entry_id}; set rules.partial_references to save team references")
            return "team_refs_off", []
        try:
            rgb = load_full(filepath)
            boxes, note = detect_vehicles(rgb, models["detector"])
            if is_team and len(boxes) != 1:
                log(f"{image_id}: {len(boxes)} vehicles found; only a solo shot can be a team reference")
                return "team_not_solo", []
            box = boxes[0] if boxes else (0, 0, rgb.shape[1], rgb.shape[0])
            crop = crop_box(rgb, box)
            rel = index.add(team_key(entry_id) if is_team else entry_id, image_id, crop)
            log(f"{image_id}: reference {rel}" + ("" if boxes else f" (whole frame; {note})"))
            proposals = []
            if rules.colour_tags and not is_team:
                colour = hand_colour or (car_colour.decide_colour(car_colour.colour_shares(crop, rules.colour_palette))
                                         if boxes else "")
                proposals = [(entry_id, colour)] if colour else []
            return ("added" if boxes else "no_vehicle_whole_frame"), proposals
        except Exception as e:
            log(f"{image_id}: couldn't add reference ({type(e).__name__}: {e})")
            return "failed", []

    run_reference_job(args, models, handle, screen="warn")


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
            rgb = load_full(filepath)
            if [rgb.shape[1], rgb.shape[0]] != record["frame"]:
                log(f"{image_id}: the file no longer matches the last run (frame size changed), skipped")
                return "stale", []
            proposals = []
            for b in wanted:
                rel = index.add(b["entry"], f"{image_id}_b{b['box']}", crop_box(rgb, b["bbox"]))
                log(f"{image_id}: box {b['box']} ({b['method']}) reference {rel}")
                # a boxes.json from before colour reading has no shares, so gives no colour
                colour = hand_colour if hand_colour and len(wanted) == 1 else car_colour.decide_colour(b.get("colour_shares", {}))
                if rules.colour_tags and colour:
                    proposals.append((b["entry"], colour))
            return "added", proposals
        except Exception as e:
            log(f"{image_id}: couldn't add references ({type(e).__name__}: {e})")
            return "failed", []

    run_reference_job(args, models, handle, screen="skip")


def audit_references(args, models: dict):
    """Reconciles the collection's index with refs/ (deleted or moved crops, changed models), then
    writes ref-audit.txt beside it. results is one `name,count` line per audit total plus `report,<path>`."""
    from audit_refs import AuditCancelled, write_audit
    collection = os.path.join(args.collections_root, args.collection)
    entries, rules, _ = load_collection(collection, args.settings)
    models["kind"] = rules.kind
    models["colour"] = rules.kind != "people" and rules.colour_weight > 0
    models["car_colour"] = rules.colour_palette if rules.kind != "people" and rules.colour_tags else None
    models["segmenter"] = ""
    index = open_index(collection, models, rules, check_models(models), args.progress)
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
        index = open_index(collection, models, rules, check_models(models))  # drops the moved refs now, not at the next audit
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
    parser.add_argument("--detector", default="", help="YOLOX .onnx")
    parser.add_argument("--segmenter", default="", help="EfficientSAM .onnx (default: next to the detector, if present)")
    parser.add_argument("--ocr-det", default="", help="PP-OCRv3 text detection .onnx")
    parser.add_argument("--ocr-rec", default="", help="text recognition .onnx: PP-OCRv5 (its .yml beside it) or CRNN")
    parser.add_argument("--embedder", default="", help="DINOv2 .onnx")
    parser.add_argument("--face-detector", default="", help="YuNet .onnx (people collections)")
    parser.add_argument("--face-recognizer", default="", help="SFace .onnx (people collections)")
    parser.add_argument("--entries-out", default="", help="Write the collection's entries.csv here")
    parser.add_argument("--rules-out", default="", help="Write the collection's rules.csv here")
    parser.add_argument("--collections-out", default="", help="--list: write collection names here")
    parser.add_argument("--boxes-out", default="", help="Write the run's per-vehicle boxes.json here")
    parser.add_argument("--report-out", default="",
                        help="Write the run's debug report to <this>.md and <this>.json")
    parser.add_argument("--archive-dir", default="",
                        help="Also copy boxes.json and the report into <dir>/<YYYYMMDD-HHMMSS>/, keeping the newest 20 runs")
    parser.add_argument("--report-top", type=int, default=20, help="Per-category cap on box detail in report.md")
    parser.add_argument("--boxes-in",default="", help="--promote-boxes: the boxes.json to read")
    parser.add_argument("--promote-boxes", action="store_true",
                        help="Add each manifest image's confident vehicles from --boxes-in as references")
    parser.add_argument("--add-reference", action="store_true", help="Add each manifest image as a reference")
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
              "segmenter": args.segmenter, "kind": DEFAULT_KIND}
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

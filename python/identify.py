"""Assisted Tagging: identify the vehicles in each frame of a manifest and
write one result row per vehicle for assisted_tagging.lua.

Modes:
  identify.py MANIFEST RESULTS ...            id,filepath,burst_id[,protected tags] →
                                              id,box,method,entry,alt_entry,confidence,unmatched_number,shot
                                              (+ --boxes-out: the per-vehicle boxes.json)
  identify.py MANIFEST RESULTS --add-reference id,filepath,entry_id → id,status
  identify.py MANIFEST RESULTS --promote-boxes --boxes-in F   id,filepath,"" → id,status
                                              (confident vehicles from a run's boxes.json become references)
  identify.py - - --list                      collection names (+ entries.csv, rules.csv)

Every mode that reads a collection also writes its tag-plan.txt: the exact tags
each outcome writes, from entries.json.

Exit codes: 0 ok, 2 bad input (message on stderr), 3 missing package, 130 cancelled."""

import argparse
import concurrent.futures
import csv
import json
import os
import re
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass, replace

from vehicles import BOX_MARGIN_TRIM, CROP_DIM, DETECTOR_MIN_SCORE, MAX_BOXES, MIN_BOX_FRAC, crop_box, detect_vehicles, detector_model, file_key, load_full, log
from ocr import OCR_MIN_SCORE, NumberReader, ocr_key
from embed import Embedder, decode, embedder_key, encode
from match import (MATCH_MIN_MARGIN, MATCH_MIN_SIM, REFERENCE_MIN_MARGIN, BoxResult, Entry, already_tagged,
                   burst_consensus, conflicts, decided_by, entries_under, hinted_match, match_box, match_livery,
                   match_team, pool_sims, promotable, shot_type, team_key, TEAM_KEY)
from sponsors import sponsor_prefixes
from report import write_report
from reference_store import ReferenceIndex

IDENTIFY_CACHE_VERSION = 1
MAX_WORKERS = 4  # each worker holds every model plus a full-resolution decode
CACHE_MAX_AGE_DAYS = 90
CACHE_COMMIT_EVERY = 50

# , ; " break the CSV handoff to Lua; the rest can't appear in a Windows folder name
_BAD_ID = re.compile(r'[,;"/\\:*?<>|]')
_BAD_TAG = re.compile(r'[,;"]')


class InputError(Exception):
    """Bad input the user fixes (entries.json, a model path): exit 2, message on stderr."""


# ---------------------------------------------------------------- entries and rules

DIAG_DEFAULTS = {
    "number": "Assisted Tagging|Identification|By number",
    "livery": "Assisted Tagging|Identification|By livery",
    "burst": "Assisted Tagging|Identification|By burst",
    "team": "Assisted Tagging|Identification|Team only",
    "none": "Assisted Tagging|Identification|Unidentified",
    # Suffixed with the literal digits read, e.g. "...|Number seen|115": independent of
    # the outcome above, applied whenever OCR read a number that matched zero or 2+ entries.
    "number_seen": "Assisted Tagging|Identification|Number seen",
    # Written instead of "livery"/"team" when burst_livery_pooling resolved a frame
    # that didn't clear the threshold on its own.
    "pooled": "Assisted Tagging|Identification|By pooled burst",
    # One per image, from how many vehicles were boxed (see match.shot_type).
    "shot_solo": "Assisted Tagging|Identification|Shot|Solo",
    "shot_pack": "Assisted Tagging|Identification|Shot|Pack",
    "shot_crowded": "Assisted Tagging|Identification|Shot|Crowded",
}
TEAM_ONLY_CHOICES = ("shared tags", "none")


@dataclass(frozen=True)
class Rules:
    """What each outcome tags, from entries.json's "rules" block. An empty diagnostic name writes no tag."""
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


def _check_tags(tags, where: str, bad, allow_empty: bool = False):
    if not isinstance(tags, list) or (not tags and not allow_empty) \
            or not all(isinstance(t, str) and t.strip() for t in tags):
        raise bad(f"{where} must be a {'' if allow_empty else 'non-empty '}list of tag names")
    for t in tags:
        if _BAD_TAG.search(t):
            raise bad(f'{where}: tag "{t}" can\'t contain , ; or "')


def _load_rules(raw, bad) -> Rules:
    if raw is None:
        return Rules()
    if not isinstance(raw, dict):
        raise bad('"rules" must be an object')
    unknown = sorted(set(raw) - {"team_only", "unidentified", "diagnostics", "burst_livery_pooling",
                                  "blur_references", "sponsor_keywords", "partial_references"})
    if unknown:
        raise bad(f'unknown rule "{unknown[0]}" (rules are team_only, unidentified, diagnostics, '
                   f'burst_livery_pooling, blur_references, sponsor_keywords, partial_references)')
    sponsors = raw.get("sponsor_keywords", {})
    if not isinstance(sponsors, dict) or not all(
            isinstance(k, str) and k.strip() and k == k.lower() and isinstance(v, str) and v.strip()
            and not _BAD_TAG.search(v) for k, v in sponsors.items()):
        raise bad("rules.sponsor_keywords must map lowercase keywords to tag prefixes")
    partial = raw.get("partial_references", False)
    if not isinstance(partial, bool):
        raise bad("rules.partial_references must be true or false")
    team_only = raw.get("team_only", "shared tags")
    if team_only not in TEAM_ONLY_CHOICES:
        raise bad('rules.team_only must be "shared tags" or "none"')
    unidentified = raw.get("unidentified", [])
    _check_tags(unidentified, "rules.unidentified", bad, allow_empty=True)
    pooling = raw.get("burst_livery_pooling", False)
    if not isinstance(pooling, bool):
        raise bad("rules.burst_livery_pooling must be true or false")
    blur_refs = raw.get("blur_references", False)
    if not isinstance(blur_refs, bool):
        raise bad("rules.blur_references must be true or false")
    diag = dict(DIAG_DEFAULTS)
    given = raw.get("diagnostics", {})
    if not isinstance(given, dict):
        raise bad("rules.diagnostics must be an object")
    for key, name in given.items():
        if key not in DIAG_DEFAULTS:
            raise bad(f'unknown diagnostic "{key}" (they are {", ".join(DIAG_DEFAULTS)})')
        if not isinstance(name, str) or _BAD_TAG.search(name):
            raise bad(f'rules.diagnostics.{key} must be a tag name without , ; or " ("" for none)')
        diag[key] = name.strip()
    return Rules(team_only, tuple(unidentified), tuple(diag.items()), pooling, blur_refs,
                 tuple(sponsors.items()), partial)


def load_collection(collection_dir: str) -> tuple:
    """entries.json → ({id: Entry} in file order, Rules). The file is either a list
    of entries or {"rules": {...}, "entries": [...]}. Raises InputError naming the file."""
    path = os.path.join(collection_dir, "entries.json")

    def bad(why):
        return InputError(f"{path}: {why}")

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise bad("file not found")
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise bad(f"not valid JSON ({e})")
    rules_raw = None
    if isinstance(data, dict):
        unknown = sorted(set(data) - {"rules", "entries"})
        if unknown:
            raise bad(f'unknown key "{unknown[0]}" (the file holds "rules" and "entries")')
        rules_raw, data = data.get("rules"), data.get("entries")
    if not isinstance(data, list):
        raise bad('"entries" must be a list of entries')
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
        unknown = sorted(set(item) - {"id", "number", "team", "tags"})
        if unknown:
            raise bad(f'entry "{eid}": unknown field "{unknown[0]}" (fields are id, number, team, tags)')
        tags = item.get("tags")
        _check_tags(tags, f'entry "{eid}": tags', bad)
        number = item.get("number", "")
        number = str(number) if isinstance(number, int) and not isinstance(number, bool) else number
        if not isinstance(number, str) or (number and not re.fullmatch(r"\d{1,3}", number)):
            raise bad(f'entry "{eid}": number must be 1–3 digits')
        team = item.get("team", "")
        if not isinstance(team, str) or _BAD_TAG.search(team):
            raise bad(f'entry "{eid}": team must be text without , ; or "')
        entries[eid] = Entry(eid, number, team, tuple(tags))
    rules = _load_rules(rules_raw, bad)
    for word, prefix in rules.sponsor_keywords:
        if not entries_under(entries, [prefix]):
            raise bad(f'rules.sponsor_keywords.{word}: no entry has a tag under "{prefix}"')
    return entries, rules


def write_entries_csv(entries: dict, path: str):
    with open(path, "w", newline="", encoding="utf-8") as f:
        for e in entries.values():
            f.write(f"{e.id},{e.team},{e.number},{';'.join(e.tags)}\n")


def write_rules_csv(rules: Rules, path: str):
    """key,value lines for assisted_tagging.lua: team_only, unidentified (tags joined by ;) and diag_<outcome>."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write(f"team_only,{rules.team_only}\n")
        f.write(f"unidentified,{';'.join(rules.unidentified)}\n")
        for key, name in rules.diagnostics:
            f.write(f"diag_{key},{name}\n")


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
        return json.dumps(list(parts) + [IDENTIFY_CACHE_VERSION], separators=(",", ":"))

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
    """Cache key parts for a frame's analysis. Entries and references stay out of it."""
    return [file_key(filepath), file_key(models["detector"]), ocr_key(models["ocr_det"], models["ocr_rec"]),
            embedder_key(models["embedder"]), CROP_DIM, MIN_BOX_FRAC, BOX_MARGIN_TRIM, OCR_MIN_SCORE,
            DETECTOR_MIN_SCORE, "ocr-trace-1"]


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
    _W["reader"] = NumberReader(models["ocr_det"], models["ocr_rec"])
    _W["embedder"] = Embedder(models["embedder"])


def analyse_frame(filepath: str) -> dict:
    """Boxes, OCR candidates and embeddings for one frame: the cached value."""
    rgb = load_full(filepath)
    boxes, note = detect_vehicles(rgb, _W["models"]["detector"])
    ocr, trace, emb = [], [], []
    for b in boxes:
        crop = crop_box(rgb, b)
        ocr.append([[d, c] for d, c in _W["reader"].read(crop)])
        trace.append(_W["reader"].last_trace)
        emb.append(encode(_W["embedder"].embed(crop)))
    h, w = rgb.shape[:2]
    return {"boxes": [list(b) for b in boxes], "ocr": ocr, "ocr_trace": trace, "emb": emb, "note": note,
            "frame": [w, h]}


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
            f"{r.confidence:.3f},{r.unmatched_number},{shot}")


def describe_box(r: BoxResult, ocr: list, sims: list, box: list, frame: list) -> str:
    seen = "/".join(d for d, _ in ocr) or "-"
    top = ", ".join(f"{e} {s:.3f}" for e, s in sims[:2]) or "no references"
    unmatched = f"; number seen but unmatched: {r.unmatched_number}" if r.unmatched_number else ""
    bw, bh = box[2] - box[0], box[3] - box[1]
    fw, fh = frame
    frac = f"; box {bw:.0f}x{bh:.0f} ({bw * bh / max(fw * fh, 1):.1%} of frame)"
    return f"box {r.box}: {r.method} {r.entry_id or '-'} (OCR {seen}; livery {top}{unmatched}{frac})"


def check_models(models: dict):
    """Every model exists and loads, so a bad one fails the run here, not per frame."""
    labels = (("object detector", "detector"), ("OCR text detection", "ocr_det"),
              ("OCR text recognition", "ocr_rec"), ("embedder", "embedder"))
    for label, key in labels:
        if not models[key] or not os.path.isfile(models[key]):
            raise InputError(f"{label} model not found: {models[key] or '(not set)'}")
    loaders = (("object detector", "detector", lambda: detector_model(models["detector"])),
               ("OCR", "ocr_det", lambda: NumberReader(models["ocr_det"], models["ocr_rec"])),
               ("embedder", "embedder", lambda: Embedder(models["embedder"])))
    for label, key, load in loaders:
        try:
            load()
        except Exception as e:
            raise InputError(f"{label} model can't be loaded ({models[key]}): {type(e).__name__}: {e}. "
                             f"Download it again (see the README).") from e


def worker_count(cpus: int) -> int:
    return max(1, min(cpus - 1, MAX_WORKERS))


def run_frames(paths: list, models: dict, cache: IdentifyCache, progress: str) -> dict:
    """filepath → analysis (cached or fresh); a frame that fails to decode maps to None."""
    done, total, out, todo = 0, len(paths), {}, []
    for p in dict.fromkeys(paths):
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
            except Exception as e:
                log(f"{p}: couldn't analyse ({type(e).__name__}: {e})")
                out[p] = None
            done += 1
            write_progress(progress, done, total)
    return out


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


def build_boxes(collection: str, frames: dict, shots: dict, detail: dict, entries: dict, counts: dict) -> dict:
    """The run's per-vehicle record (see the Stage A plan for the shape). `skipped` lists images
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
            rule, gap = decided_by(r, b["sims"], entries)
            boxes.append({"box": r.box, "bbox": b["bbox"], "entry": r.entry_id, "alt_entry": r.alt_entry_id,
                          "method": r.method, "confidence": round(r.confidence, 4),
                          "candidates": [[e, round(s, 4)] for e, s in b["sims"][:5]],
                          "ocr": b["ocr"], "ocr_trace": b.get("ocr_trace", []), "decided_by": rule, "gap": round(gap, 4),
                          "unmatched_number": r.unmatched_number, "conflict": r.method == "conflict",
                          "hint": b.get("hint", {})})
        images[image_id] = {"shot": shots[image_id], "status": status, "file": d["file"], "frame": d["frame"],
                            "burst": d["burst"], "note": d["note"], "boxes": boxes}
    return {"collection": collection,
            "thresholds": {"min_sim": MATCH_MIN_SIM, "min_margin": MATCH_MIN_MARGIN,
                           "reference_margin": REFERENCE_MIN_MARGIN},
            "entries": {e.id: {"team": e.team, "number": e.number, "tags": list(e.tags), "refs": counts.get(e.id, 0)}
                        for e in entries.values()},
            "images": images, "skipped": skipped}


def write_boxes(path: str, data: dict):
    """Writes build_boxes' record atomically."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def identify(args, models: dict):
    collection = os.path.join(args.collections_root, args.collection)
    entries, rules = load_collection(collection)
    check_models(models)
    rows = read_manifest(args.manifest, 3, 2)
    # 4th column: entry tags the user applied by hand (never ledgered by the plugin), ";"-joined.
    protected_of = {r[0]: {t for t in r[3].split(";") if t} for r in rows}
    # 5th column: hand-applied tags that are a strict prefix of an entry's tags (team hints), ";"-joined.
    tag_hints_of = {r[0]: [t for t in r[4].split(";") if t] for r in rows}
    fully_tagged = {i for i, p in protected_of.items() if already_tagged(p, entries)}
    index = ReferenceIndex.load(collection, Embedder(models["embedder"]),
                                 [embedder_key(models["embedder"]), rules.blur_references], rules.blur_references)
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
        analyses = run_frames([r[1] for r in rows if r[0] not in fully_tagged], models, cache, args.progress)
    finally:
        cache.close()
    if cancel_requested(args.progress):
        log("cancelled")
        sys.exit(130)

    frames, burst_of, box0_sims, detail = {}, {}, {}, {}
    for image_id, filepath, burst, _protected, _hints in rows:
        burst_of[image_id] = burst
        detail[image_id] = {"file": filepath, "frame": [], "boxes": [], "note": "", "burst": burst}
        if image_id in fully_tagged:
            log(f"{image_id}: already carries all of {already_tagged(protected_of[image_id], entries)}'s tags, skipped")
            frames[image_id] = [BoxResult(-1, "skipped")]
            continue
        a = analyses.get(filepath)
        if a is None:
            # an error row: assisted_tagging.lua leaves this image's tags alone
            frames[image_id] = [BoxResult(-1, "error")]
            continue
        if not a["boxes"]:
            log(f"{image_id}: {a['note']}")
            detail[image_id]["note"] = a["note"]
            frames[image_id] = [BoxResult(-1, "none")]
            continue
        results = []
        detail[image_id]["frame"] = a["frame"]
        for i, ocr in enumerate(a["ocr"]):
            sims = index.best_per_entry(decode(a["emb"][i]))
            team_sims = [(team_of[k], s) for k, s in sims if k in team_of]
            sims = [(k, s) for k, s in sims if k in entries]
            trace = a.get("ocr_trace", [[]] * len(a["ocr"]))[i]
            prefixes, source = box_hint(tag_hints_of[image_id] if len(a["boxes"]) == 1 else [],
                                        sponsor_prefixes(trace, rules.sponsor_keywords))
            r, hint = hinted_match(i, [tuple(c) for c in ocr], sims, entries, prefixes, source)
            r = match_team(r, team_sims, entries)
            log(f"{image_id}: {describe_box(r, ocr, sims, a['boxes'][i], a['frame'])}"
                + (f" [hint {';'.join(prefixes)} ({source}){', dropped: ' + hint['reason'] if hint['dropped'] else ''}]" if hint else ""))
            results.append(r)
            detail[image_id]["boxes"].append({"bbox": [float(v) for v in a["boxes"][i][:4]], "ocr": ocr, "sims": sims,
                                              "ocr_trace": trace, "hint": hint})
            if i == 0 and rules.burst_livery_pooling:
                box0_sims[image_id] = sims
        frames[image_id] = results
    if rules.burst_livery_pooling:
        frames = pool_burst_livery(frames, burst_of, box0_sims, entries)
    frames = burst_consensus(frames, burst_of, entries)

    # After consensus, so a burst-filled box is checked too. Solo shots only: see match.conflicts.
    shots = {}
    for image_id, results in frames.items():
        n_boxes = sum(1 for r in results if r.box >= 0)
        shots[image_id] = shot_type(n_boxes, MAX_BOXES)
        frames[image_id] = [replace(r, method="conflict") if r.entry_id and conflicts(
            r.entry_id, protected_of[image_id], entries, n_boxes == 1) else r for r in results]

    by_method: dict = {}
    tmp = args.results + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        for image_id, results in frames.items():
            for r in results:
                if r.method == "burst":
                    log(f"{image_id}: box {r.box}: burst {r.entry_id} ({r.confidence:.2f} of the burst agrees)")
                if r.method == "conflict":
                    log(f"{image_id}: box {r.box}: {r.entry_id} shares no tag with the ones you applied; left as you tagged it")
                by_method[r.method] = by_method.get(r.method, 0) + 1
                f.write(format_row(image_id, r, shots[image_id]) + "\n")
    os.replace(tmp, args.results)
    if args.boxes_out or args.report_out:
        data = build_boxes(args.collection, frames, shots, detail, entries, counts)
        written = []
        if args.boxes_out:
            write_boxes(args.boxes_out, data)
            written.append(args.boxes_out)
        if args.report_out:
            md_path, json_path = write_report(data, args.report_out, args.report_top)
            written += [md_path, json_path]
            log(f"report: {md_path}")
        if args.archive_dir:
            archive_run(written, args.archive_dir, ARCHIVE_KEEP)
    write_collection_outputs(args, collection, entries, rules)
    log("vehicles by method: " + ", ".join(f"{m} {n}" for m, n in sorted(by_method.items())))


# ---------------------------------------------------------------- add-reference / list modes

def add_references(args, models: dict):
    collection = os.path.join(args.collections_root, args.collection)
    entries, rules = load_collection(collection)
    check_models(models)
    embedder = Embedder(models["embedder"])
    index = ReferenceIndex.load(collection, embedder,
                                 [embedder_key(models["embedder"]), rules.blur_references], rules.blur_references)
    rows = read_manifest(args.manifest, 3)
    tmp = args.results + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        for n, (image_id, filepath, entry_id) in enumerate(rows, 1):
            if cancel_requested(args.progress):
                log("cancelled; references added so far are kept")
                index.save()
                sys.exit(130)
            status = "failed"
            # a team prefix instead of an entry id: a solo shot tagged only to team level
            is_team = entry_id not in entries and entry_id in strict_prefixes(entries)
            if entry_id not in entries and not is_team:
                log(f"{image_id}: entry {entry_id} isn't in {args.collection}'s entries.json")
            elif is_team and not rules.partial_references:
                status = "team_refs_off"
                log(f"{image_id}: only tagged to {entry_id}; set rules.partial_references to save team references")
            else:
                try:
                    rgb = load_full(filepath)
                    boxes, note = detect_vehicles(rgb, models["detector"])
                    if is_team and len(boxes) != 1:
                        status = "team_not_solo"
                        log(f"{image_id}: {len(boxes)} vehicles found; only a solo shot can be a team reference")
                        f.write(f"{image_id},{status}\n")
                        write_progress(args.progress, n, len(rows))
                        continue
                    box = boxes[0] if boxes else (0, 0, rgb.shape[1], rgb.shape[0])
                    rel = index.add(team_key(entry_id) if is_team else entry_id, image_id, crop_box(rgb, box))
                    status = "added" if boxes else "no_vehicle_whole_frame"
                    log(f"{image_id}: reference {rel}" + ("" if boxes else f" (whole frame; {note})"))
                except Exception as e:
                    log(f"{image_id}: couldn't add reference ({type(e).__name__}: {e})")
            f.write(f"{image_id},{status}\n")
            write_progress(args.progress, n, len(rows))
    index.save()
    os.replace(tmp, args.results)
    write_collection_outputs(args, collection, entries, rules)


def promote_boxes(args, models: dict):
    """Save each manifest image's confident vehicles (match.promotable) from the last run's
    boxes.json as references, cropped from the box itself, so a pack shot's tags land on the
    right car. Re-promoting a box replaces its sample."""
    collection = os.path.join(args.collections_root, args.collection)
    entries, rules = load_collection(collection)
    check_models(models)
    try:
        with open(args.boxes_in, encoding="utf-8") as f:
            run = json.load(f)
    except (OSError, ValueError) as e:
        raise InputError(f"{args.boxes_in}: can't read the last run's boxes ({e}); run Identify first")
    if run.get("collection") != args.collection:
        raise InputError(f"the last run was for collection {run.get('collection')!r}, not {args.collection!r}")
    embedder = Embedder(models["embedder"])
    index = ReferenceIndex.load(collection, embedder,
                                 [embedder_key(models["embedder"]), rules.blur_references], rules.blur_references)
    rows = read_manifest(args.manifest, 3)
    tmp = args.results + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        for n, (image_id, filepath, _entry) in enumerate(rows, 1):
            if cancel_requested(args.progress):
                log("cancelled; references added so far are kept")
                index.save()
                sys.exit(130)
            status = "none_promotable"
            record = run["images"].get(image_id)
            wanted = [b for b in record["boxes"] if promotable(b) and b["entry"] in entries] if record else []
            if wanted:
                try:
                    rgb = load_full(filepath)
                    if [rgb.shape[1], rgb.shape[0]] != record["frame"]:
                        status = "stale"
                        log(f"{image_id}: the file no longer matches the last run (frame size changed), skipped")
                    else:
                        for b in wanted:
                            rel = index.add(b["entry"], f"{image_id}_b{b['box']}", crop_box(rgb, b["bbox"]))
                            log(f"{image_id}: box {b['box']} ({b['method']}) reference {rel}")
                        status = "added"
                except Exception as e:
                    status = "failed"
                    log(f"{image_id}: couldn't add references ({type(e).__name__}: {e})")
            f.write(f"{image_id},{status}\n")
            write_progress(args.progress, n, len(rows))
    index.save()
    os.replace(tmp, args.results)
    write_collection_outputs(args, collection, entries, rules)


def write_collection_outputs(args, collection: str, entries: dict, rules: Rules):
    """entries.csv and rules.csv for assisted_tagging.lua, and the collection's tag-plan.txt for the user."""
    if args.entries_out:
        write_entries_csv(entries, args.entries_out)
    if args.rules_out:
        write_rules_csv(rules, args.rules_out)
    log(f"tag plan: {write_tag_plan(collection, args.collection, entries, rules)}")


def list_mode(args):
    if args.collections_root:
        os.makedirs(args.collections_root, exist_ok=True)  # so the user can find where collections go
    names = list_collections(args.collections_root)
    if args.collections_out:
        with open(args.collections_out, "w", newline="", encoding="utf-8") as f:
            f.writelines(n + "\n" for n in names)
    if args.collection in names:
        collection = os.path.join(args.collections_root, args.collection)
        write_collection_outputs(args, collection, *load_collection(collection))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Assisted Tagging identifier")
    parser.add_argument("manifest", help="Manifest CSV (- with --list)")
    parser.add_argument("results", help="Results CSV (- with --list)")
    parser.add_argument("--progress", default="", help="Progress file; <progress>.cancel cancels the run")
    parser.add_argument("--cache", default="", help="SQLite cache of per-frame analysis (empty = off)")
    parser.add_argument("--collections-root", default="", help="Folder holding one folder per collection")
    parser.add_argument("--collection", default="", help="Active collection's folder name")
    parser.add_argument("--detector", default="", help="YOLOX .onnx")
    parser.add_argument("--ocr-det", default="", help="PP-OCRv3 text detection .onnx")
    parser.add_argument("--ocr-rec", default="", help="CRNN text recognition .onnx")
    parser.add_argument("--embedder", default="", help="DINOv2 .onnx")
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
    parser.add_argument("--list", action="store_true", help="List collections (and entries) only")
    args = parser.parse_args(argv)
    models = {"detector": args.detector, "ocr_det": args.ocr_det, "ocr_rec": args.ocr_rec,
              "embedder": args.embedder}
    try:
        if args.list:
            list_mode(args)
        elif args.add_reference:
            add_references(args, models)
        elif args.promote_boxes:
            promote_boxes(args, models)
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

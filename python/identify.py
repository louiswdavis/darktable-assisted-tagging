"""Assisted Tagging: identify the vehicles in each frame of a manifest and
write one result row per vehicle for tagging.lua.

Modes:
  identify.py MANIFEST RESULTS ...            id,filepath,burst_id → id,box,method,entry,alt_entry,confidence
  identify.py MANIFEST RESULTS --add-reference id,filepath,entry_id → id,status
  identify.py - - --list                      collection names (+ entries.csv)

Exit codes: 0 ok, 2 bad input (message on stderr), 3 missing package, 130 cancelled."""

import argparse
import concurrent.futures
import csv
import json
import os
import re
import sqlite3
import sys
import time

from vehicles import CROP_DIM, MIN_BOX_FRAC, crop_box, detect_vehicles, file_key, load_full, log
from ocr import OCR_MIN_SCORE, NumberReader, ocr_key
from embed import Embedder, decode, embedder_key, encode
from match import BoxResult, Entry, burst_consensus, match_box
from reference_store import ReferenceIndex

IDENTIFY_CACHE_VERSION = 1
CACHE_MAX_AGE_DAYS = 90
CACHE_COMMIT_EVERY = 50

# , ; " break the CSV handoff to Lua; the rest can't appear in a Windows folder name
_BAD_ID = re.compile(r'[,;"/\\:*?<>|]')
_BAD_TAG = re.compile(r'[,;"]')


class InputError(Exception):
    """Bad input the user fixes (entries.json, a model path): exit 2, message on stderr."""


# ---------------------------------------------------------------- entries

def load_entries(collection_dir: str) -> dict:
    """entries.json → {id: Entry} in file order. Raises InputError naming the file."""
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
    if not isinstance(data, list):
        raise bad("must be a list of entries")
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
        tags = item.get("tags")
        if not isinstance(tags, list) or not tags or not all(isinstance(t, str) and t.strip() for t in tags):
            raise bad(f'entry "{eid}": tags must be a non-empty list of tag names')
        for t in tags:
            if _BAD_TAG.search(t):
                raise bad(f'entry "{eid}": tag "{t}" can\'t contain , ; or "')
        number = item.get("number", "")
        number = str(number) if isinstance(number, int) and not isinstance(number, bool) else number
        if not isinstance(number, str) or (number and not re.fullmatch(r"\d{1,3}", number)):
            raise bad(f'entry "{eid}": number must be 1–3 digits')
        team = item.get("team", "")
        if not isinstance(team, str) or _BAD_TAG.search(team):
            raise bad(f'entry "{eid}": team must be text without , ; or "')
        entries[eid] = Entry(eid, number, team, tuple(tags))
    return entries


def write_entries_csv(entries: dict, path: str):
    with open(path, "w", newline="", encoding="utf-8") as f:
        for e in entries.values():
            f.write(f"{e.id},{e.team},{e.number},{';'.join(e.tags)}\n")


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
            embedder_key(models["embedder"]), CROP_DIM, MIN_BOX_FRAC, OCR_MIN_SCORE]


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
    ocr, emb = [], []
    for b in boxes:
        crop = crop_box(rgb, b)
        ocr.append([[d, c] for d, c in _W["reader"].read(crop)])
        emb.append(encode(_W["embedder"].embed(crop)))
    return {"boxes": [list(b) for b in boxes], "ocr": ocr, "emb": emb, "note": note}


# ---------------------------------------------------------------- identify mode

def read_manifest(path: str, columns: int) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        return [row[:columns] for row in csv.reader(f) if len(row) >= columns]


def format_row(image_id: str, r: BoxResult) -> str:
    return f"{image_id},{r.box},{r.method},{r.entry_id},{r.alt_entry_id},{r.confidence:.3f}"


def describe_box(r: BoxResult, ocr: list, sims: list) -> str:
    seen = "/".join(d for d, _ in ocr) or "-"
    top = ", ".join(f"{e} {s:.3f}" for e, s in sims[:2]) or "no references"
    return f"box {r.box}: {r.method} {r.entry_id or '-'} (OCR {seen}; livery {top})"


def check_models(models: dict):
    for label, key in (("object detector", "detector"), ("OCR text detection", "ocr_det"),
                       ("OCR text recognition", "ocr_rec"), ("embedder", "embedder")):
        if not models[key] or not os.path.isfile(models[key]):
            raise InputError(f"{label} model not found: {models[key] or '(not set)'}")


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
    workers = max(1, (os.cpu_count() or 2) - 1)
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


def identify(args, models: dict):
    collection = os.path.join(args.collections_root, args.collection)
    entries = load_entries(collection)
    check_models(models)
    rows = read_manifest(args.manifest, 3)
    index = ReferenceIndex.load(collection, Embedder(models["embedder"]), embedder_key(models["embedder"]))
    counts = index.count_by_entry()
    if not counts:
        log(f"collection {args.collection} has no references yet: only numbers can identify a car")
    else:
        log("references: " + ", ".join(f"{e} {counts.get(e, 0)}" for e in entries))
    unknown = sorted(set(counts) - set(entries))
    if unknown:
        log("references for entries not in entries.json (ignored): " + ", ".join(unknown))

    cache = IdentifyCache(args.cache)
    try:
        analyses = run_frames([r[1] for r in rows], models, cache, args.progress)
    finally:
        cache.close()
    if cancel_requested(args.progress):
        log("cancelled")
        sys.exit(130)

    frames, burst_of = {}, {}
    for image_id, filepath, burst in rows:
        burst_of[image_id] = burst
        a = analyses.get(filepath)
        if not a or not a["boxes"]:
            log(f"{image_id}: {a['note'] if a else 'not analysed'}")
            frames[image_id] = [BoxResult(-1, "none")]
            continue
        results = []
        for i, ocr in enumerate(a["ocr"]):
            sims = index.best_per_entry(decode(a["emb"][i]))
            r = match_box(i, [tuple(c) for c in ocr], sims, entries)
            log(f"{image_id}: {describe_box(r, ocr, sims)}")
            results.append(r)
        frames[image_id] = results
    frames = burst_consensus(frames, burst_of)

    by_method: dict = {}
    tmp = args.results + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        for image_id, results in frames.items():
            for r in results:
                if r.method == "burst":
                    log(f"{image_id}: box {r.box}: burst {r.entry_id} ({r.confidence:.2f} of the burst agrees)")
                by_method[r.method] = by_method.get(r.method, 0) + 1
                f.write(format_row(image_id, r) + "\n")
    os.replace(tmp, args.results)
    if args.entries_out:
        write_entries_csv(entries, args.entries_out)
    log("vehicles by method: " + ", ".join(f"{m} {n}" for m, n in sorted(by_method.items())))


# ---------------------------------------------------------------- add-reference / list modes

def add_references(args, models: dict):
    collection = os.path.join(args.collections_root, args.collection)
    entries = load_entries(collection)
    check_models(models)
    embedder = Embedder(models["embedder"])
    index = ReferenceIndex.load(collection, embedder, embedder_key(models["embedder"]))
    rows = read_manifest(args.manifest, 3)
    tmp = args.results + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        for n, (image_id, filepath, entry_id) in enumerate(rows, 1):
            status = "failed"
            if entry_id not in entries:
                log(f"{image_id}: entry {entry_id} isn't in {args.collection}'s entries.json")
            else:
                try:
                    rgb = load_full(filepath)
                    boxes, note = detect_vehicles(rgb, models["detector"])
                    box = boxes[0] if boxes else (0, 0, rgb.shape[1], rgb.shape[0])
                    rel = index.add(entry_id, image_id, crop_box(rgb, box))
                    status = "added" if boxes else "no_vehicle_whole_frame"
                    log(f"{image_id}: reference {rel}" + ("" if boxes else f" (whole frame; {note})"))
                except Exception as e:
                    log(f"{image_id}: couldn't add reference ({type(e).__name__}: {e})")
            f.write(f"{image_id},{status}\n")
            write_progress(args.progress, n, len(rows))
    index.save()
    os.replace(tmp, args.results)
    if args.entries_out:
        write_entries_csv(entries, args.entries_out)


def list_mode(args):
    if args.collections_root:
        os.makedirs(args.collections_root, exist_ok=True)  # so the user can find where collections go
    names = list_collections(args.collections_root)
    if args.collections_out:
        with open(args.collections_out, "w", newline="", encoding="utf-8") as f:
            f.writelines(n + "\n" for n in names)
    if args.entries_out and args.collection in names:
        write_entries_csv(load_entries(os.path.join(args.collections_root, args.collection)), args.entries_out)


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
    parser.add_argument("--collections-out", default="", help="--list: write collection names here")
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

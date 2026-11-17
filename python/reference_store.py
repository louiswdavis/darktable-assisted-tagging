"""A collection's reference samples. The crops under refs/<entry id>/ are the
source of truth; index.npz only caches their embeddings and is reconciled
against them on every load, so deleting a crop drops it from matching."""

import datetime
import json
import os
import re

import numpy as np
from PIL import Image

from colour import COLOUR_DIM, colour_hist
from common import atomic_write
from embed import degrade
from vehicles import log

INDEX_NAME = "index.npz"
SOURCES_NAME = "sources.json"  # under refs/: rel -> {source, confidence, date}; the index is rebuilt from disk, so the source lives beside the crops
SOURCES = ("hand", "picked", "number")  # Add tagged images / Fill colours; Add as reference (the user chose the car); Add from last run
ANCHOR_MIN_SIM = 0.5  # a ref or box less like every anchor of its car than this doesn't look like the car (ticket 80); set from replay_anchors.py
ANCHOR_MIN_READ = 0.9  # a number ref read at this or more anchors its car (ticket 80); 89% of Rallye 21:02 number boxes reach it
CENTRE_MIN_REFS = 20  # fewer references than this: their mean says too little, so the run's boxes join it (use_run_centre)


def backfilled_source(rel: str) -> dict:
    """The source record of a ref saved before refs/sources.json: `<image_id>_b<n>.jpg` is a `number`
    ref of unknown confidence (promotion), any other `hand`."""
    numbered = re.search(r"_b\d+\.jpg$", rel, re.IGNORECASE)
    return {"source": "number" if numbered else "hand", "confidence": None, "date": ""}


def anchor_source(rec: dict) -> bool:
    """A source record the plugin can trust: the user tagged or picked the ref, or a number read of
    ANCHOR_MIN_READ or more saved it. Unknown confidence counts: promotion has been number-only since
    the 2026-11-17 reset."""
    if rec.get("source") == "number":
        return rec.get("confidence") is None or rec["confidence"] >= ANCHOR_MIN_READ
    return rec.get("source") in ("hand", "picked")


def read_sources(collection_dir: str, paths: list) -> list:
    """Each of `paths`' source record from refs/sources.json, backfilled by file name when missing."""
    try:
        with open(os.path.join(collection_dir, "refs", SOURCES_NAME), encoding="utf-8") as f:
            stored = json.load(f)
    except (OSError, ValueError):
        stored = {}
    return [stored.get(rel) or backfilled_source(rel) for rel in paths]


class ReferenceIndex:
    def __init__(self, collection_dir: str, embedder, key, blur: bool = False, dim=None,
                 colour: bool = False):
        self.dir = collection_dir
        self.refs = os.path.join(collection_dir, "refs")
        self.embedder = embedder
        self.blur = blur
        self.key = json.dumps(key)
        self.colour = colour  # also keep each crop's colour histogram (see best_per_entry)
        self.emb = np.zeros((0, embedder.dim if dim is None else dim), np.float32)
        self.hist = np.zeros((0, COLOUR_DIM), np.float32)
        self.entry: list = []
        self.path: list = []
        self.stat: list = []  # "mtime_ns:size" of each crop when embedded, so a replaced crop is re-embedded
        self.centre = None  # under CENTRE_MIN_REFS references: the mean of references and run boxes (use_run_centre)
        self.added: list = []  # paths add() has saved since a caller last cleared this
        self.replaced: dict = {}  # rel -> (crop bytes, entry, embedding, histogram, source record) add() overwrote
        self.sources: dict = {}  # rel -> {"source", "confidence" (None when unknown), "date"}; see _sync_sources

    @classmethod
    def load(cls, collection_dir: str, embedder, key, blur: bool = False, dim=None,
             colour: bool = False, on_progress=None) -> "ReferenceIndex":
        """dim: embedding length; None reads embedder.dim. on_progress(done, total) is called per reference embedded; returning False stops
        embedding. The refs embedded so far are saved either way, so the next load carries on."""
        idx = cls(collection_dir, embedder, key, blur, dim, colour)
        stored = idx._read()
        on_disk = idx._scan()
        changed = stored is None
        if stored is not None:
            emb, entry, path, stored_key, hist, stat = stored
            if stored_key == idx.key:
                # an index saved without stats keeps every crop still on disk and gains their stats
                keep = [i for i, p in enumerate(path) if p in on_disk and (stat is None or stat[i] == on_disk[p])]
                changed = len(keep) != len(path) or stat is None
                idx.emb, idx.entry, idx.path = emb[keep], [entry[i] for i in keep], [path[i] for i in keep]
                idx.stat = [on_disk[path[i]] for i in keep]
                if colour:
                    if hist is not None and len(hist) == len(path):
                        idx.hist = hist[keep]
                    else:  # an index saved without colour: histograms come from the crops, no re-embedding
                        idx.hist = np.stack([idx._hist_file(r) for r in idx.path]) if idx.path \
                            else np.zeros((0, COLOUR_DIM), np.float32)
                        changed = True
            else:
                changed = True
        known = set(idx.path)
        todo = [rel for rel in sorted(on_disk) if rel not in known]
        if len(todo) > 1:
            log(f"references: embedding {len(todo)} (new or replaced, or the embedder or blur setting changed)")
        # todo paths aren't in the index yet, so new rows are gathered and stacked once:
        # _append's vstack per row is quadratic across a full re-embed
        vecs, hists = [], []
        for n, rel in enumerate(todo, 1):
            try:
                vec, h = idx._embed_file(rel)
            except Exception as e:  # one unreadable crop mustn't stop every run
                log(f"reference {rel} can't be read, skipped ({type(e).__name__}); delete or replace it")
            else:
                vecs.append(np.asarray(vec, np.float32))
                hists.append(h)
                idx.entry.append(rel.split("/")[1])
                idx.path.append(rel)
                idx.stat.append(on_disk[rel])
            if on_progress is not None and on_progress(n, len(todo)) is False:
                log(f"references: stopped after {n} of {len(todo)}; the rest are embedded next time")
                break
        if vecs:
            new = np.stack(vecs)
            # an empty index takes the embedder's own width (see _append)
            idx.emb = new if len(idx.emb) == 0 else np.vstack([idx.emb, new])
            if colour:
                idx.hist = np.vstack([idx.hist, np.asarray(hists, np.float32)])
            changed = True
        if idx._sync_sources() or changed:
            idx.save()
        return idx

    def _sync_sources(self) -> bool:
        """Reads refs/sources.json, drops refs no longer indexed and backfills the rest by file name:
        `<image_id>_b<n>.jpg` is a `number` ref of unknown confidence (promotion), any other `hand`.
        True when the sidecar changed."""
        p = os.path.join(self.refs, SOURCES_NAME)
        try:
            with open(p, encoding="utf-8") as f:
                stored = json.load(f)
        except (OSError, ValueError):
            stored = {}
        indexed = set(self.path)
        self.sources = {rel: rec for rel, rec in stored.items() if rel in indexed}
        missing = [rel for rel in self.path if rel not in self.sources]
        for rel in missing:
            self.sources[rel] = backfilled_source(rel)
        if missing:
            log(f"references: {len(missing)} had no recorded source; set by file name (_b<n> = number read, else hand)")
        return bool(missing) or len(self.sources) != len(stored)

    def is_anchor(self, rel: str) -> bool:
        return anchor_source(self.sources.get(rel, {}))

    def _read(self):
        p = os.path.join(self.dir, INDEX_NAME)
        if not os.path.isfile(p):
            return None
        try:
            with np.load(p, allow_pickle=False) as z:
                return (z["emb"].astype(np.float32), [str(s) for s in z["entry"]],
                        [str(s) for s in z["path"]], str(z["key"]),
                        z["hist"].astype(np.float32) if "hist" in z.files else None,
                        [str(s) for s in z["stat"]] if "stat" in z.files else None)
        except Exception:
            return None  # an unreadable index is rebuilt from the crops

    def _stat(self, rel: str) -> str:
        st = os.stat(os.path.join(self.dir, *rel.split("/")))
        return f"{st.st_mtime_ns}:{st.st_size}"

    def _scan(self) -> dict:
        """rel -> stat of every crop under refs/."""
        found = {}
        if not os.path.isdir(self.refs):
            return found
        for entry_id in os.listdir(self.refs):
            d = os.path.join(self.refs, entry_id)
            if os.path.isdir(d):
                for name in os.listdir(d):
                    if name.lower().endswith(".jpg"):
                        rel = f"refs/{entry_id}/{name}"
                        found[rel] = self._stat(rel)
        return found

    def _read_crop(self, rel: str) -> np.ndarray:
        with Image.open(os.path.join(self.dir, *rel.split("/"))) as im:
            return np.array(im.convert("RGB"))

    def _hist_file(self, rel: str) -> np.ndarray:
        return colour_hist(self._read_crop(rel))

    def _embed_file(self, rel: str) -> tuple:
        """(embedding, colour histogram or None when colour is off)."""
        crop = self._read_crop(rel)
        return (self.embedder.embed(degrade(crop) if self.blur else crop),
                colour_hist(crop) if self.colour else None)

    def _append(self, entry_id: str, rel: str, vec: np.ndarray, hist=None):
        """Records vec for the crop already written at rel."""
        if rel in self.path:
            i = self.path.index(rel)
            self.emb[i], self.entry[i], self.stat[i] = vec, entry_id, self._stat(rel)
            if self.colour:
                self.hist[i] = hist
            return
        if self.colour:
            self.hist = np.vstack([self.hist, np.asarray(hist, np.float32)[np.newaxis]])
        row = np.asarray(vec, np.float32)[np.newaxis]
        # an empty index takes the embedder's own width, so a model of another size (DINOv2 base: 768) works
        self.emb = row if len(self.emb) == 0 else np.vstack([self.emb, row])
        self.entry.append(entry_id)
        self.path.append(rel)
        self.stat.append(self._stat(rel))

    def add(self, entry_id: str, image_id: str, crop_rgb: np.ndarray, source: str = "hand",
            confidence=None) -> str:
        """Saves the crop as refs/<entry_id>/<image_id>.jpg, replacing an earlier sample of the same
        image, records its `source` (SOURCES; `confidence`: a number ref's read) and returns its path
        relative to the collection."""
        assert source in SOURCES, source
        os.makedirs(os.path.join(self.refs, entry_id), exist_ok=True)
        rel = f"refs/{entry_id}/{image_id}.jpg"
        # an image is a sample of one entry: re-adding it elsewhere moves it
        for other in [p for p in self.path if p.endswith(f"/{image_id}.jpg") and p != rel]:
            i = self.path.index(other)
            self.emb = np.delete(self.emb, i, axis=0)
            if self.colour:
                self.hist = np.delete(self.hist, i, axis=0)
            del self.entry[i], self.path[i], self.stat[i]
            self.sources.pop(other, None)
            try:
                os.remove(os.path.join(self.dir, *other.split("/")))
            except OSError:
                pass
        full = os.path.join(self.dir, *rel.split("/"))
        if rel in self.path and os.path.exists(full):
            i = self.path.index(rel)
            with open(full, "rb") as f:
                self.replaced[rel] = (f.read(), self.entry[i], self.emb[i].copy(), self.hist[i].copy() if self.colour else None,
                                      self.sources.get(rel))
        Image.fromarray(crop_rgb).save(full, quality=92)
        self._append(entry_id, rel, self.embedder.embed(degrade(crop_rgb) if self.blur else crop_rgb),
                     colour_hist(crop_rgb) if self.colour else None)
        self.sources[rel] = {"source": source, "confidence": None if confidence is None else round(float(confidence), 4),
                             "date": datetime.date.today().isoformat()}
        self.added.append(rel)
        return rel

    def restore(self, rel: str) -> bool:
        """Puts back the sample add() replaced at rel (call save() after); False when add() replaced
        nothing there, in which case the caller should remove() the new one."""
        old = self.replaced.pop(rel, None)
        if old is None:
            return False
        data, entry_id, vec, hist, source = old
        with open(os.path.join(self.dir, *rel.split("/")), "wb") as f:
            f.write(data)
        self._append(entry_id, rel, vec, hist)
        if source is not None:
            self.sources[rel] = source
        return True

    def remove(self, rel: str):
        """Deletes a reference's crop and drops it from the index (call save() after)."""
        i = self.path.index(rel)
        self.emb = np.delete(self.emb, i, axis=0)
        if self.colour:
            self.hist = np.delete(self.hist, i, axis=0)
        del self.entry[i], self.path[i], self.stat[i]
        self.sources.pop(rel, None)
        os.remove(os.path.join(self.dir, *rel.split("/")))

    def save(self):
        os.makedirs(self.dir, exist_ok=True)
        extra = {"hist": self.hist} if self.colour else {}
        with atomic_write(os.path.join(self.dir, INDEX_NAME), "wb") as f:  # a file object, so savez adds no .npz
            np.savez(f, emb=self.emb, entry=np.array(self.entry, dtype=str),
                     path=np.array(self.path, dtype=str), stat=np.array(self.stat, dtype=str), key=np.array(self.key),
                     **extra)
        if os.path.isdir(self.refs):
            with atomic_write(os.path.join(self.refs, SOURCES_NAME)) as f:
                json.dump(dict(sorted(self.sources.items())), f, indent=1)

    def use_run_centre(self, run_vecs: list) -> str:
        """Under CENTRE_MIN_REFS references, centres best_per_entry on the mean of the references and
        `run_vecs` (this run's box embeddings, the same embedder) when together they reach it, so the
        match thresholds, tuned on centred similarities, mean the same in a small collection. Returns
        the log line naming the regime."""
        n = len(self.emb)
        if n >= CENTRE_MIN_REFS:
            self.centre = None
            return f"livery: centred on {n} references"
        if n + len(run_vecs) < CENTRE_MIN_REFS:
            self.centre = None
            return f"livery: raw similarity ({n} references and {len(run_vecs)} boxes, under {CENTRE_MIN_REFS})"
        both = np.vstack([self.emb, *(np.asarray(v, np.float32)[None] for v in run_vecs)])
        self.centre = both.mean(axis=0)
        return f"livery: centred on {n} references and {len(run_vecs)} boxes from this run"

    def best_per_entry(self, vec: np.ndarray, hist=None, colour_weight: float = 0.0) -> list:
        """[(entry_id, best cosine similarity)], most similar first. The embedder's vectors share a large
        common component (raw cosines sit at 0.92-0.97 for any two cars), so both sides are centred on
        the references' mean first with CENTRE_MIN_REFS or more references, else on use_run_centre's
        mean when set; the index file stays raw.
        With a colour_weight and the query's colour histogram, each side becomes the unit-length join of
        its embedding and weight x its histogram, so colour counts alongside the embedding."""
        if not self.entry:
            return []
        join = colour_weight > 0 and hist is not None and self.colour
        emb = self.project(self.emb, self.hist if join else None, colour_weight)
        vec = self.project(np.asarray(vec, np.float32)[None], np.asarray(hist, np.float32)[None] if join else None,
                           colour_weight)[0]
        sims = emb @ vec
        best: dict = {}
        for e, s in zip(self.entry, sims.tolist()):
            if s > best.get(e, -2.0):
                best[e] = s
        return sorted(best.items(), key=lambda kv: kv[1], reverse=True)

    def project(self, emb: np.ndarray, hist=None, colour_weight: float = 0.0) -> np.ndarray:
        """Rows of `emb` (with `hist`, their colour histograms, or None) in the space best_per_entry
        compares: centred and unit-length when a centre applies, then joined with colour_weight x the
        histogram and unit-length again when `hist` is given."""
        emb = np.asarray(emb, np.float32)
        mean = self.emb.mean(axis=0) if len(self.emb) >= CENTRE_MIN_REFS else self.centre
        if mean is not None:
            emb = emb - mean
            emb = emb / np.maximum(np.linalg.norm(emb, axis=1, keepdims=True), 1e-9)
        if colour_weight > 0 and hist is not None:
            emb = np.hstack([emb, colour_weight * np.asarray(hist, np.float32)])
            emb = emb / np.maximum(np.linalg.norm(emb, axis=1, keepdims=True), 1e-9)
        return emb

    def all_sims(self, vec: np.ndarray) -> list:
        """[(entry_id, raw cosine similarity)] for every reference, in index order. No centring: face
        embeddings spread out already."""
        if not self.entry:
            return []
        return list(zip(self.entry, (self.emb @ np.asarray(vec, np.float32)).tolist()))

    def count_by_entry(self) -> dict:
        counts: dict = {}
        for e in self.entry:
            counts[e] = counts.get(e, 0) + 1
        return counts


class Anchors:
    """Each car's anchors (ReferenceIndex.is_anchor refs, plus any boxes add() gives, e.g. this run's
    number reads) in the index's comparison space. A double-driven car's entries pool theirs: `car_of`
    maps an entry id to its car key (match.Entry.car), ids missing from it are their own car."""

    def __init__(self, index: ReferenceIndex, car_of: dict, colour_weight: float = 0.0, skip=()):
        """`skip`: refs left out, so a job's new refs are never anchors for themselves."""
        self.index, self.car_of = index, car_of
        self.join = colour_weight > 0 and index.colour
        self.weight = colour_weight
        skip = set(skip)
        rows = [i for i, rel in enumerate(index.path) if index.is_anchor(rel) and rel not in skip]
        self.cars = [self._car(index.entry[i]) for i in rows]
        self.rels = [index.path[i] for i in rows]
        self.rows = index.project(index.emb[rows], index.hist[rows] if self.join else None, colour_weight) \
            if rows else np.zeros((0, 0), np.float32)

    def _car(self, entry_id: str) -> str:
        return self.car_of.get(entry_id) or entry_id

    def add(self, entry_id: str, vec, hist=None, rel: str = ""):
        row = self._project(vec, hist)
        self.rows = row if len(self.rows) == 0 else np.vstack([self.rows, row])
        self.cars.append(self._car(entry_id))
        self.rels.append(rel)

    def _project(self, vec, hist) -> np.ndarray:
        return self.index.project(np.asarray(vec, np.float32)[None],
                                  np.asarray(hist, np.float32)[None] if self.join else None, self.weight)

    def has(self, entry_id: str) -> bool:
        return self._car(entry_id) in self.cars

    def unanchored(self, entry_ids) -> list:
        """The entry ids, in order, whose car has no anchor."""
        return [e for e in entry_ids if not self.has(e)]

    def compare(self, entry_id: str, vec, hist=None, skip_rel: str = "") -> tuple:
        """(own, other, other_car): the best similarity to the car's own anchors and to any other
        car's ("" and -1.0 when no other car has one), leaving out the anchor at `skip_rel`. None when
        the car has no anchor besides `skip_rel`."""
        car = self._car(entry_id)
        sims = (self.rows @ self._project(vec, hist)[0]).tolist() if len(self.rows) else []
        own, other, other_car = None, -1.0, ""
        for c, rel, sim in zip(self.cars, self.rels, sims):
            if rel and rel == skip_rel:
                continue
            if c == car:
                own = sim if own is None else max(own, sim)
            elif sim > other:
                other, other_car = sim, c
        return None if own is None else (own, other, other_car)

    def unlike(self, entry_id: str, vec, hist=None, skip_rel: str = "") -> tuple:
        """(verdict, own, other_car): verdict is "unanchored" when the car has no anchor (its first
        match is accepted), "unlike" when the best own anchor is under ANCHOR_MIN_SIM or another
        car's anchor is closer, else "like"."""
        got = self.compare(entry_id, vec, hist, skip_rel)
        if got is None:
            return "unanchored", None, ""
        own, other, other_car = got
        if own < ANCHOR_MIN_SIM or other > own:
            return "unlike", own, other_car if other > own else ""
        return "like", own, ""

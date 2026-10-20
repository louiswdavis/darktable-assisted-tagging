"""A collection's reference samples. The crops under refs/<entry id>/ are the
source of truth; index.npz only caches their embeddings and is reconciled
against them on every load, so deleting a crop drops it from matching."""

import json
import os

import numpy as np
from PIL import Image

from colour import COLOUR_DIM, colour_hist
from embed import EMBED_DIM, degrade
from vehicles import log

INDEX_NAME = "index.npz"
CENTRE_MIN_REFS = 20  # fewer references than this: their mean says too little, so similarity stays raw


class ReferenceIndex:
    def __init__(self, collection_dir: str, embedder, key, blur: bool = False, dim: int = EMBED_DIM,
                 colour: bool = False):
        self.dir = collection_dir
        self.refs = os.path.join(collection_dir, "refs")
        self.embedder = embedder
        self.blur = blur
        self.key = json.dumps(key)
        self.colour = colour  # also keep each crop's colour histogram (see best_per_entry)
        self.emb = np.zeros((0, dim), np.float32)
        self.hist = np.zeros((0, COLOUR_DIM), np.float32)
        self.entry: list = []
        self.path: list = []
        self.added: list = []  # paths add() has saved since a caller last cleared this
        self.replaced: dict = {}  # rel -> (crop bytes, entry, embedding, histogram) add() overwrote

    @classmethod
    def load(cls, collection_dir: str, embedder, key, blur: bool = False, dim: int = EMBED_DIM,
             colour: bool = False) -> "ReferenceIndex":
        idx = cls(collection_dir, embedder, key, blur, dim, colour)
        stored = idx._read()
        on_disk = idx._scan()
        changed = stored is None
        if stored is not None:
            emb, entry, path, stored_key, hist = stored
            if stored_key == idx.key:
                keep = [i for i, p in enumerate(path) if p in on_disk]
                changed = len(keep) != len(path)
                idx.emb, idx.entry, idx.path = emb[keep], [entry[i] for i in keep], [path[i] for i in keep]
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
        for rel in sorted(on_disk):
            if rel not in known:
                try:
                    vec, h = idx._embed_file(rel)
                except Exception as e:  # one unreadable crop mustn't stop every run
                    log(f"reference {rel} can't be read, skipped ({type(e).__name__}); delete or replace it")
                    continue
                idx._append(rel.split("/")[1], rel, vec, h)
                changed = True
        if changed:
            idx.save()
        return idx

    def _read(self):
        p = os.path.join(self.dir, INDEX_NAME)
        if not os.path.isfile(p):
            return None
        try:
            with np.load(p, allow_pickle=False) as z:
                return (z["emb"].astype(np.float32), [str(s) for s in z["entry"]],
                        [str(s) for s in z["path"]], str(z["key"]),
                        z["hist"].astype(np.float32) if "hist" in z.files else None)
        except Exception:
            return None  # an unreadable index is rebuilt from the crops

    def _scan(self) -> set:
        found = set()
        if not os.path.isdir(self.refs):
            return found
        for entry_id in os.listdir(self.refs):
            d = os.path.join(self.refs, entry_id)
            if os.path.isdir(d):
                for name in os.listdir(d):
                    if name.lower().endswith(".jpg"):
                        found.add(f"refs/{entry_id}/{name}")
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
        if rel in self.path:
            i = self.path.index(rel)
            self.emb[i], self.entry[i] = vec, entry_id
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

    def add(self, entry_id: str, image_id: str, crop_rgb: np.ndarray) -> str:
        """Saves the crop as refs/<entry_id>/<image_id>.jpg, replacing an earlier
        sample of the same image, and returns its path relative to the collection."""
        os.makedirs(os.path.join(self.refs, entry_id), exist_ok=True)
        rel = f"refs/{entry_id}/{image_id}.jpg"
        # an image is a sample of one entry: re-adding it elsewhere moves it
        for other in [p for p in self.path if p.endswith(f"/{image_id}.jpg") and p != rel]:
            i = self.path.index(other)
            self.emb = np.delete(self.emb, i, axis=0)
            if self.colour:
                self.hist = np.delete(self.hist, i, axis=0)
            del self.entry[i], self.path[i]
            try:
                os.remove(os.path.join(self.dir, *other.split("/")))
            except OSError:
                pass
        full = os.path.join(self.dir, *rel.split("/"))
        if rel in self.path and os.path.exists(full):
            i = self.path.index(rel)
            with open(full, "rb") as f:
                self.replaced[rel] = (f.read(), self.entry[i], self.emb[i].copy(), self.hist[i].copy() if self.colour else None)
        Image.fromarray(crop_rgb).save(full, quality=92)
        self._append(entry_id, rel, self.embedder.embed(degrade(crop_rgb) if self.blur else crop_rgb),
                     colour_hist(crop_rgb) if self.colour else None)
        self.added.append(rel)
        return rel

    def restore(self, rel: str) -> bool:
        """Puts back the sample add() replaced at rel (call save() after); False when add() replaced
        nothing there, in which case the caller should remove() the new one."""
        old = self.replaced.pop(rel, None)
        if old is None:
            return False
        data, entry_id, vec, hist = old
        with open(os.path.join(self.dir, *rel.split("/")), "wb") as f:
            f.write(data)
        self._append(entry_id, rel, vec, hist)
        return True

    def remove(self, rel: str):
        """Deletes a reference's crop and drops it from the index (call save() after)."""
        i = self.path.index(rel)
        self.emb = np.delete(self.emb, i, axis=0)
        if self.colour:
            self.hist = np.delete(self.hist, i, axis=0)
        del self.entry[i], self.path[i]
        os.remove(os.path.join(self.dir, *rel.split("/")))

    def save(self):
        os.makedirs(self.dir, exist_ok=True)
        tmp = os.path.join(self.dir, INDEX_NAME + ".tmp.npz")
        extra = {"hist": self.hist} if self.colour else {}
        np.savez(tmp, emb=self.emb, entry=np.array(self.entry, dtype=str),
                 path=np.array(self.path, dtype=str), key=np.array(self.key), **extra)
        os.replace(tmp, os.path.join(self.dir, INDEX_NAME))

    def best_per_entry(self, vec: np.ndarray, hist=None, colour_weight: float = 0.0) -> list:
        """[(entry_id, best cosine similarity)], most similar first. The embedder's vectors share a large
        common component (raw cosines sit at 0.92-0.97 for any two cars), so with CENTRE_MIN_REFS or more
        references both sides are centred on the references' mean first; the index file stays raw.
        With a colour_weight and the query's colour histogram, each side becomes the unit-length join of
        its embedding and weight x its histogram, so colour counts alongside the embedding."""
        if not self.entry:
            return []
        emb, vec = self.emb, np.asarray(vec, np.float32)
        if len(emb) >= CENTRE_MIN_REFS:
            mean = emb.mean(axis=0)
            emb, vec = emb - mean, vec - mean
            emb = emb / np.maximum(np.linalg.norm(emb, axis=1, keepdims=True), 1e-9)
            vec = vec / max(float(np.linalg.norm(vec)), 1e-9)
        if colour_weight > 0 and hist is not None and self.colour:
            emb = np.hstack([emb, colour_weight * self.hist])
            vec = np.concatenate([vec, colour_weight * np.asarray(hist, np.float32)])
            emb = emb / np.maximum(np.linalg.norm(emb, axis=1, keepdims=True), 1e-9)
            vec = vec / max(float(np.linalg.norm(vec)), 1e-9)
        sims = emb @ vec
        best: dict = {}
        for e, s in zip(self.entry, sims.tolist()):
            if s > best.get(e, -2.0):
                best[e] = s
        return sorted(best.items(), key=lambda kv: kv[1], reverse=True)

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

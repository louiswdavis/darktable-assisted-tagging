"""A collection's reference samples. The crops under refs/<entry id>/ are the
source of truth; index.npz only caches their embeddings and is reconciled
against them on every load, so deleting a crop drops it from matching."""

import json
import os

import numpy as np
from PIL import Image

from embed import EMBED_DIM, degrade
from vehicles import log

INDEX_NAME = "index.npz"
CENTRE_MIN_REFS = 20  # fewer references than this: their mean says too little, so similarity stays raw


class ReferenceIndex:
    def __init__(self, collection_dir: str, embedder, key, blur: bool = False, dim: int = EMBED_DIM):
        self.dir = collection_dir
        self.refs = os.path.join(collection_dir, "refs")
        self.embedder = embedder
        self.blur = blur
        self.key = json.dumps(key)
        self.emb = np.zeros((0, dim), np.float32)
        self.entry: list = []
        self.path: list = []

    @classmethod
    def load(cls, collection_dir: str, embedder, key, blur: bool = False, dim: int = EMBED_DIM) -> "ReferenceIndex":
        idx = cls(collection_dir, embedder, key, blur, dim)
        stored = idx._read()
        on_disk = idx._scan()
        changed = stored is None
        if stored is not None:
            emb, entry, path, stored_key = stored
            if stored_key == idx.key:
                keep = [i for i, p in enumerate(path) if p in on_disk]
                changed = len(keep) != len(path)
                idx.emb, idx.entry, idx.path = emb[keep], [entry[i] for i in keep], [path[i] for i in keep]
            else:
                changed = True
        known = set(idx.path)
        for rel in sorted(on_disk):
            if rel not in known:
                try:
                    vec = idx._embed_file(rel)
                except Exception as e:  # one unreadable crop mustn't stop every run
                    log(f"reference {rel} can't be read, skipped ({type(e).__name__}); delete or replace it")
                    continue
                idx._append(rel.split("/")[1], rel, vec)
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
                        [str(s) for s in z["path"]], str(z["key"]))
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

    def _embed_file(self, rel: str) -> np.ndarray:
        with Image.open(os.path.join(self.dir, *rel.split("/"))) as im:
            crop = np.array(im.convert("RGB"))
        return self.embedder.embed(degrade(crop) if self.blur else crop)

    def _append(self, entry_id: str, rel: str, vec: np.ndarray):
        if rel in self.path:
            i = self.path.index(rel)
            self.emb[i], self.entry[i] = vec, entry_id
            return
        self.emb = np.vstack([self.emb, np.asarray(vec, np.float32)[np.newaxis]])
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
            del self.entry[i], self.path[i]
            try:
                os.remove(os.path.join(self.dir, *other.split("/")))
            except OSError:
                pass
        Image.fromarray(crop_rgb).save(os.path.join(self.dir, *rel.split("/")), quality=92)
        self._append(entry_id, rel, self.embedder.embed(degrade(crop_rgb) if self.blur else crop_rgb))
        return rel

    def save(self):
        os.makedirs(self.dir, exist_ok=True)
        tmp = os.path.join(self.dir, INDEX_NAME + ".tmp.npz")
        np.savez(tmp, emb=self.emb, entry=np.array(self.entry, dtype=str),
                 path=np.array(self.path, dtype=str), key=np.array(self.key))
        os.replace(tmp, os.path.join(self.dir, INDEX_NAME))

    def best_per_entry(self, vec: np.ndarray) -> list:
        """[(entry_id, best cosine similarity)], most similar first. The embedder's vectors share a large
        common component (raw cosines sit at 0.92-0.97 for any two cars), so with CENTRE_MIN_REFS or more
        references both sides are centred on the references' mean first; the index file stays raw."""
        if not self.entry:
            return []
        emb, vec = self.emb, np.asarray(vec, np.float32)
        if len(emb) >= CENTRE_MIN_REFS:
            mean = emb.mean(axis=0)
            emb, vec = emb - mean, vec - mean
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

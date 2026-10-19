"""Frame analysis, matching and reference selection for `people` collections. Orchestration
(manifest, cache, results rows) stays in identify.py."""

from embed import decode, encode
from match_people import entry_scores, match_face, resolve_duplicates
from vehicles import log

CANDIDATES_KEPT = 5


def analyse_frame_people(rgb, model) -> dict:
    """The cached value for one frame: every face's box [x, y, w, h, score] and encoded embedding."""
    h, w = rgb.shape[:2]
    faces = model.detect(rgb)
    return {"frame": [w, h], "note": "" if faces else "no face found",
            "boxes": [[f.x, f.y, f.w, f.h, f.score] for f in faces],
            "emb": [encode(model.embed_face(rgb, f)) for f in faces]}


def match_frame_people(image_id: str, a: dict, index, entries: dict, rules, boxes_out: list) -> list:
    """One BoxResult per face in analysis `a`. Appends each face's detail (box, width, final status,
    best candidates) to `boxes_out`; the status is the one after duplicate resolution."""
    pairs, cands = [], []
    for i, box in enumerate(a["boxes"]):
        scores = [(e, s) for e, s in entry_scores(index.all_sims(decode(a["emb"][i]))) if e in entries]
        cands.append(scores[:CANDIDATES_KEPT])
        pairs.append(match_face(i, box[2], scores, rules.min_sim, rules.margin, rules.min_face_px))
    pairs = resolve_duplicates(pairs)
    for i, (r, status) in enumerate(pairs):
        box = a["boxes"][i]
        top = f"{cands[i][0][0]} {cands[i][0][1]:.2f}" if cands[i] else "no candidates"
        log(f"{image_id}: face {i}: {status} {r.entry_id or '-'} ({box[2]:.0f}px wide; best {top})")
        boxes_out.append({"face": i, "bbox": [float(v) for v in box[:4]], "score": float(box[4]),
                          "width_px": float(box[2]), "status": status,
                          "candidates": [[e, round(s, 4)] for e, s in cands[i]]})
    return [r for r, _ in pairs]


def build_boxes_people(collection: str, frames: dict, shots: dict, detail: dict, entries: dict, counts: dict, rules) -> dict:
    """The run's per-face record for the report. `skipped` lists images left alone because they already
    carry one entry's full tag set; each image's `status` is ok, no_face or error."""
    images, skipped = {}, []
    for image_id, results in frames.items():
        if any(r.method == "skipped" for r in results):
            skipped.append(image_id)
            continue
        d = detail[image_id]
        status = "error" if any(r.method == "error" for r in results) else "ok" if d["faces"] else "no_face"
        faces = []
        for r in results:
            if r.box < 0:
                continue
            row = dict(d["faces"][r.box], entry=r.entry_id, alt_entry=r.alt_entry_id, confidence=round(r.confidence, 4),
                       method=r.method, conflict=r.method == "conflict")
            faces.append(row)
        images[image_id] = {"shot": shots[image_id], "status": status, "file": d["file"], "frame": d["frame"],
                            "burst": d["burst"], "time": d["time"], "note": d["note"], "faces": faces}
    return {"kind": "people", "collection": collection,
            "thresholds": {"min_sim": rules.min_sim, "margin": rules.margin, "min_face_px": rules.min_face_px},
            "entries": {e.id: {"tags": list(e.tags), "refs": counts.get(e.id, 0)} for e in entries.values()},
            "images": images, "skipped": skipped}


def reference_face(rgb, model) -> tuple:
    """(aligned crop, "ok") when the photo has exactly one face; (None, "no_face") or
    (None, "multiple_faces") otherwise, since a tag can't say which face of several it names."""
    faces = model.detect(rgb)
    if not faces:
        return None, "no_face"
    if len(faces) > 1:
        return None, "multiple_faces"
    return model.align_crop(rgb, faces[0]), "ok"

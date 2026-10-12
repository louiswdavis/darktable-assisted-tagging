# SAM-based subject tracking for sharpness scoring

## Purpose

Add a sharpness mode that uses darktable's native `darktable.ai` SAM-style
segmentation model to isolate the actual subject in a frame before scoring
sharpness, instead of assuming the subject is near the center. Keeps the
existing "subject bias (center-weighted)" heuristic mode untouched as a
new 6th option.

## Why this needs a new pipeline stage, not a one-line change

`darktable.ai` only runs inside darktable's own Lua process
(`lua/culling.lua`). The actual Laplacian sharpness math runs in a separate
external process (`python/score_images.py`). SAM also needs a point/box
prompt per image, and darktable exposes no AF-point/focus-point coordinate
(only a scalar `exif_focus_distance`, confirmed absent of any x/y field in
darktable's source). So this requires:

1. A classical-CV pass to find a plausible subject point (Python, has
   OpenCV).
2. A SAM inference pass using that point as the prompt (Lua, has
   `darktable.ai`).
3. The existing sharpness-scoring pass, now mask-aware (Python).

## Pipeline

**Stage A — saliency pre-pass (Python, new).**
`score_images.py` gains an `--emit-saliency-points` mode, invoked by Lua
before the main scoring run, same manifest in (`id,filepath,burst_id`).
For each image: reuse the existing `load_image()` (same RAW/JPEG decode
path already in the file), divide the working-resolution frame into a
tile grid, score each tile by edge energy (`cv2.Laplacian` variance,
same primitive already used elsewhere in this file) plus color
distinctiveness (Lab-space distance of the tile's mean color from the
frame's overall mean color), and take the highest-scoring tile's center.
Output: a new sidecar CSV, `id,x_frac,y_frac` (point as a 0–1 fraction of
width/height, not pixel coordinates — stage A and stage B/C may decode the
same source file at different resolutions, so the point must be
resolution-independent).

**Stage B — SAM mask (Lua, new).**
Before stage A even runs, `culling.lua` checks:
`dt.ai ~= nil and dt.ai.model_for_task("mask") ~= nil`. If either is
false, the run fails immediately with a clear `dt.print`/error (per the
approved fallback decision) — no manifest or temp files are written, same
as today's "score_images.py not found" precondition failure.

If the precondition passes: Lua loads the mask model **once per run**
(not once per image) via `dt.ai.load_model(model_id)`, keeping the
context alive across the batch and calling `ctx:close()` when done. For
each image in the stage-A points CSV: convert `(x_frac, y_frac)` to pixel
coordinates against whatever tensor `dt.ai.load_image(image_obj)` returns
for that image, run the model with that point as prompt (exact `ctx:run`
input/output tensor shape is model-specific — confirm against the actual
registered mask model during implementation, since `ai.c` only documents
the generic calling convention), and `tensor:save(path)` the resulting
mask as an 8-bit PNG to a new per-id temp file,
`dt_assisted_culling_mask_<id>.png`.

Per-image failures here (inference error, bad prompt, etc.) are caught
with `pcall`; that image's mask path is left unset. This is a *different*
failure mode from the precondition check above — a single bad image
degrades gracefully (stage C falls back to the heuristic for that one
image, same pattern as `face_detect`'s "no face found" fallback), while a
missing/unavailable model fails the whole run up front.

**Stage C — mask-aware scoring (Python, extended).**
Lua writes the real manifest with an optional 4th column:
`id,filepath,burst_id,mask_path` (empty string when stage B produced
nothing for that id, or for every other sharpness mode — this mode is the
only writer of a 4th column). `score_images.py`'s manifest reader must
accept both 3- and 4-column rows so every other mode, `tools/e2e_cli.lua`,
and `stress_test_cull.py`'s mock manifest keep working unmodified.

`sharpness_score()` gains an optional `mask` argument. When a mask path is
present and loads successfully: resize/threshold the mask (nearest
neighbor) to the already-loaded `rgb` image's dimensions, and restrict the
Laplacian variance computation to pixels where the mask is set. When the
mask is missing, empty, or fails to load: fall through to the existing
`subject_focus` center-weighted-patch code path — this mode never hard-fails
per-image, only at the run-level precondition in stage B.

## UI

New 6th entry in `sharp_opts`/the sharpness combobox — append in matching
order this time (the whole reason this session started was `sharp_opts`
drifting out of sync with its labels). Suggested label: "subject tracking
(SAM)" to distinguish it from the "(AI)"-labeled heuristic naming mistake
already corrected this session. Tooltip should state plainly that this
mode is slower than the others (decodes every image twice, runs a real
model per image) and suit smaller batches / final-pass refinement rather
than bulk culling.

## Temp file lifecycle

Follows the existing pattern in `M.score_images` (the block of
`pcall(os.remove, ...)` calls at the start of each run): add removal of
the points CSV and any previous run's mask PNGs before a new run starts,
and clean them up at the end alongside `MANIFEST_PATH`/`RESULTS_PATH`.
Mask PNGs are named by image id, so cleanup can iterate the current
image list rather than needing a glob.

## Performance

This mode decodes every image twice (stage A, stage C) and adds one SAM
encoder+decoder pass per image in stage B — categorically slower than
every existing mode. Document this plainly in the README and the
combobox tooltip; do not make it a preset default for any genre.

## Testing

- Python: the saliency tile-scorer (edge energy + color contrast → point)
  and the mask-aware cropping/fallback logic in `sharpness_score()` are
  pure functions — unit-testable the same way `sharpness_score()`'s
  existing modes are structured, with synthetic arrays, no model loading
  required.
- Lua: the SAM-calling code lives in the darktable-integration half of
  `culling.lua`, which has no automated coverage today (by existing
  project convention — only the pure-logic half under `test_assisted_culling.lua`
  is tested). This stays consistent: no new automated Lua test, manual
  verification via an extended `tools/e2e_cli.lua` run against a real
  darktable library with the mask model installed.

## Explicitly out of scope

- Multi-point/grid prompting (approved: single saliency point only).
- Any attempt to read AF-point coordinates from EXIF/maker-notes —
  confirmed not exposed anywhere in darktable's source.
- Replacing or removing the existing "subject bias (center-weighted)"
  heuristic mode.

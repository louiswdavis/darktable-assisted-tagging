# SAM Subject Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 6th sharpness mode, `sam_subject`, that uses darktable's native `darktable.ai` SAM-style mask model to isolate the real subject in a frame before scoring sharpness, replacing the current whole-frame guesswork for that one mode only.

**Architecture:** Three sequential stages instead of today's two. Stage A (Python, `score_images.py --emit-saliency-points`) finds one plausible subject point per image using a classical edge+color heuristic. Stage B (Lua, `culling.lua`) feeds that point to the darktable-native SAM model via `darktable.ai` and saves a mask PNG per image. Stage C (Python, the existing `score_images.py` scoring run) restricts the Laplacian sharpness calculation to the masked region when a mask is present, falling back to the existing center-weighted heuristic otherwise.

**Tech Stack:** Lua 5.4 (darktable Lua API, `darktable.ai`), Python 3.10+ (OpenCV, NumPy, Pillow, rawpy — all already dependencies, no new ones added).

**Spec:** `docs/superpowers/specs/2026-10-12-sam-subject-tracking-design.md`

## Global Constraints

- **Commit steps are hand-off checkpoints, not actions.** The implementer never runs `git add`/`git commit`; stop at each "Commit" step, report the changed files and suggested message, and let the user commit.
- No new Python dependencies — the saliency heuristic uses only `cv2`/`numpy`, already in `python/requirements.txt`.
- `manifest.csv`'s reader must still accept 3-column rows (every mode except `sam_subject`, plus `tools/e2e_cli.lua` and `python/stress_test_cull.py`'s mock manifest) unmodified.
- `sharp_opts` (lua/culling.lua) and its combobox's label list must stay in the same order, entry-for-entry — this is the exact bug fixed earlier this session; the new 6th entry goes at the end of both lists in lockstep.
- A missing/unavailable SAM mask model fails the whole `sam_subject` run immediately, before any manifest or temp file is written. A failure on one image's SAM inference *within* an otherwise-working run degrades only that image (falls back to the heuristic), per the approved spec.
- Saliency tile grid is fixed at 5×5 (`SALIENCY_GRID = 5` in `score_images.py`) — not user-configurable in this version.
- Points are stored as `x_frac,y_frac` (0–1 fractions of width/height), never pixel coordinates — stage A and stage C may decode the same source file at different resolutions.

## Review Focus

- **A burst where every image fails SAM inference** (model present but every per-image call errors, e.g. a corrupt image) — every image in that burst must still get a usable sharpness score via the fallback, not a crashed run. Covered in Task 2's fallback test and Task 3's per-image `pcall`.
- **A path containing a comma in the saliency-points CSV** — same manifest-comma limitation the README already documents; the points CSV writer/reader must use the same quoting as `write_manifest`, not a naive `string.format("%s,%f,%f")`. Covered in Task 3.
- **An image whose SAM mask ends up empty or all-zero** (point landed on a background region SAM couldn't segment) — `sharpness_score` must detect zero masked pixels and fall back rather than computing `variance()` of an empty array (which raises in NumPy). Covered in Task 2.
- **A user who selects `sam_subject` without ever having opened darktable's AI preferences** (model registered but never downloaded, so `model_for_task("mask")` returns an id but `load_model` fails) — the precondition check in Task 3 only checks `model_for_task`, not downloadedness, so this must be caught by wrapping the one-time `load_model` call in the same hard-fail path, not deferred into the per-image `pcall`.
- **Re-running `sam_subject` over the same selection twice in a row** — stage A/B temp files (points CSV, per-id mask PNGs) from the first run must not leak into the second if the second run uses a different sharpness mode or a different image subset; covered by extending the existing cleanup block in Task 3.

---

## Task 1: Saliency tile-scorer and `--emit-saliency-points` CLI mode

**Files:**
- Modify: `python/score_images.py`
- Create: `python/test_score_images.py` (plain-assert style, mirroring `lua/test_assisted_culling.lua`'s `check(name, got, want)` helper — this project has no pytest dependency and none should be added; run with plain `python`)

**Interfaces:**
- Produces: `saliency_point(rgb: np.ndarray, grid: int = SALIENCY_GRID) -> tuple[float, float]` — returns `(x_frac, y_frac)` of the highest-scoring tile's center.
- Produces: a new CLI mode, flag `--emit-saliency-points` (`action="store_true"`). When set, the existing positional `results` argument is reinterpreted as the output path for the points CSV (`id,x_frac,y_frac`), not the normal results CSV — document this reuse in the module docstring since it's not obvious from the arg name.
- Consumes: `load_image()` (existing, unchanged) for decode.

- [ ] **Step 1: Write `python/test_score_images.py` with the saliency scoring test**

Add the `check(name, got, want)` helper (same shape as the Lua test's). Build a synthetic 90×90 RGB `np.ndarray` that is flat gray everywhere except a 10×10 bright, high-contrast patch placed off-center (e.g. top-left tile of a 5×5 grid, so it's unambiguous which tile should win). Assert `saliency_point(img)` returns fractions that land inside that patch's tile (e.g. `x_frac < 0.3 and y_frac < 0.3` for a top-left patch in a 90×90 image).

- [ ] **Step 2: Run it to verify it fails**

Run: `python python/test_score_images.py`
Expected: fails with `NameError`/`AttributeError` — `saliency_point` doesn't exist yet.

- [ ] **Step 3: Implement `saliency_point` in `score_images.py`**

Add module constant `SALIENCY_GRID = 5` near the other mode constants (`STAR_THRESHOLDS` etc.). Implement by: convert `rgb` to Lab via `cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)`; compute the frame's mean Lab color; for each of the `grid × grid` tiles, compute (a) edge energy as `cv2.Laplacian(gray_tile, cv2.CV_64F).var()` on the grayscale tile (reuse the same `cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)` the rest of the file already does), and (b) color distinctiveness as the Euclidean distance between the tile's mean Lab color and the frame's mean Lab color; normalize each of the two arrays across all tiles to 0–1 (divide by their own max, guarding divide-by-zero by skipping normalization when the max is 0); combine as `0.5 * edge_norm + 0.5 * color_norm`; return the `(x_frac, y_frac)` center of the argmax tile.

- [ ] **Step 4: Run test to verify it passes**

Run: `python python/test_score_images.py`
Expected: all checks print `ok`.

- [ ] **Step 5: Add the `--emit-saliency-points` CLI mode**

In the `argparse` block (end of file), add `parser.add_argument("--emit-saliency-points", action="store_true", help="Write id,x_frac,y_frac to the 'results' path instead of scoring")`. In `main(args)`, at the very top (before the burst-grouping logic), branch: if `args.emit_saliency_points`, loop the manifest with the same `ProcessPoolExecutor`/`_init_worker` pattern `main()` already uses for scoring (one worker function per file, e.g. `process_single_saliency(filepath, fast_jpeg)` that calls `load_image` then `saliency_point`), write each result as it completes via `csv.writer` in append mode to `args.results` (same incrementally-open-then-append pattern `process_burst_logic` already uses for the real results file), call `write_progress` the same way the scoring path does, then `return` before reaching the burst/keeper code. No live progress bar is required for this stage in Lua (Task 3 does not poll `PROGRESS_PATH` during stage A) — still call `write_progress` so the file exists and is harmless if something does poll it later.

- [ ] **Step 6: Manual smoke test against a real folder**

Run: `python python/score_images.py manifest.csv points.csv --emit-saliency-points` against a small real `manifest.csv` (same format the README's "Testing" section already documents for standalone scorer runs). Expected: `points.csv` contains one `id,x_frac,y_frac` row per manifest row, with both fractions in `[0, 1]`.

- [ ] **Step 7: Commit**

```bash
git add python/score_images.py python/test_score_images.py
git commit -m "feat: add saliency-point scoring for SAM subject prompting"
```

---

## Task 2: 4-column manifest support and mask-aware `sharpness_score`

**Files:**
- Modify: `python/score_images.py`
- Modify: `python/test_score_images.py`

**Interfaces:**
- Consumes: nothing new from Task 1 at runtime (this task's manifest/mask-reading code is independent of the saliency scorer; they only share the file).
- Produces: `sharpness_score(rgb, mode, mask_path="")` — note the added third parameter; `process_single_image` and its caller in `main()` must pass it through.

- [ ] **Step 1: Write the manifest-parsing test**

In `python/test_score_images.py`, add a test that writes a temp 4-column CSV (`id,path,burst_id,mask_path`, one row with a non-empty 4th field, one row with an empty 4th field) and a temp 3-column CSV, and asserts both parse to 4-tuples with `""` filled in for the missing field on the 3-column one. (Test the parsing expression directly rather than importing a private closure — extract the manifest-row-to-tuple logic into a small module-level function `parse_manifest_row(row: list[str]) -> tuple[str, str, str, str]` so it's testable in isolation; `main()` calls it instead of the inline tuple literal.)

- [ ] **Step 2: Run it to verify it fails**

Run: `python python/test_score_images.py`
Expected: fails — `parse_manifest_row` doesn't exist yet.

- [ ] **Step 3: Implement `parse_manifest_row` and wire it into `main()`**

Add `parse_manifest_row(row)` returning `(row[0], row[1], row[2], row[3] if len(row) > 3 else "")`. Replace `main()`'s current `manifest = [(row[0], row[1], row[2]) for row in csv.reader(f) if row]` with `manifest = [parse_manifest_row(row) for row in csv.reader(f) if row]`. Update the `burst_groups`-building loop and the `executor.submit(process_single_image, ...)` call to unpack and pass through the new 4th field (`mask_path`) alongside `image_id, filepath`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python python/test_score_images.py`
Expected: all checks print `ok`.

- [ ] **Step 5: Write the mask-aware scoring tests**

Add three cases to `python/test_score_images.py`:
1. A synthetic image with a sharp region inside a mask and a blurrier region outside it; a mask PNG covering only the sharp region; assert `sharpness_score(img, "sam_subject", mask_path=<that mask>)` is higher than `sharpness_score(img, "sam_subject", mask_path="")` on the same image (the unmasked call falls back to the center-weighted heuristic).
2. A mask path that doesn't exist on disk; assert `sharpness_score` doesn't raise and returns the same value as the no-mask (fallback) call.
3. An all-zero mask PNG (valid file, no masked pixels); assert `sharpness_score` doesn't raise `ValueError`/`RuntimeWarning` from an empty-array `.var()` call, and falls back to the heuristic value.

- [ ] **Step 6: Run tests to verify they fail**

Run: `python python/test_score_images.py`
Expected: fails — `sharpness_score` doesn't accept a `mask_path` argument yet.

- [ ] **Step 7: Implement mask-aware scoring in `sharpness_score`**

Change the signature to `sharpness_score(rgb: np.ndarray, mode: str, mask_path: str = "") -> float`. At the top, before the existing `mode == "center"`/`"peak"`/`"face_detect"` checks, add: if `mode == "sam_subject" and mask_path`, attempt `mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)`; if that's not `None`, resize to `denoised`'s shape with `cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)` (compute `denoised`/`h, w` first by moving the existing `gray = cv2.cvtColor(...)` / `denoised = cv2.bilateralFilter(...)` lines above this new block), threshold at `127` to a boolean array, compute `lap = cv2.Laplacian(denoised, cv2.CV_64F)`, and if `lap[mask_bool].size > 0` return `float(lap[mask_bool].var())`. Any failure in that path (file missing, unreadable, empty mask) falls through to the existing mode-dispatch code below — do not return early on failure. Change the existing generic-branch condition from `if mode == "subject_focus":` to `if mode in ("subject_focus", "sam_subject"):` so an unmasked or failed `sam_subject` call uses the center-weighted heuristic (matching the spec's approved fallback), not the uniform-weighted `tiles_uniformity` formula.

- [ ] **Step 8: Update `process_single_image` and its caller**

Add `mask_path: str = ""` parameter to `process_single_image`, pass it to `sharpness_score`. In `main()`'s `executor.submit(process_single_image, filepath, args.sharp_mode, args.exp_mode, cancel_path, args.fast_jpeg)` call, add the per-row `mask_path` as an additional argument (update `process_single_image`'s parameter order to accept it, and update the `future_to_item` bookkeeping tuple if it needs to carry the mask path through — check against the existing tuple shape at that call site before changing it).

- [ ] **Step 9: Run tests to verify they pass**

Run: `python python/test_score_images.py`
Expected: all checks print `ok`.

- [ ] **Step 10: Regression-check the existing stress test still runs**

Run: `python python/stress_test_cull.py`
Expected: completes with `Test passed successfully!` — its mock manifest is still 3 columns, confirming the 3-column back-compat path works end to end, not just in the unit test.

- [ ] **Step 11: Commit**

```bash
git add python/score_images.py python/test_score_images.py
git commit -m "feat: mask-aware sharpness scoring with 4-column manifest support"
```

---

## Task 3: `culling.lua` — SAM precondition, model lifecycle, per-image inference, mask lifecycle

No automated test for this task — it's GUI/`darktable`-dependent code in the same untested half of `culling.lua` as the rest of `M.score_images` today (`lua/test_assisted_culling.lua` only covers the pure-logic functions above the `pcall(require, "darktable")` line). Verification is manual, via `tools/e2e_cli.lua`, per the spec's Testing section.

**Files:**
- Modify: `lua/culling.lua`

**Interfaces:**
- Consumes: Task 1's `--emit-saliency-points` CLI mode (same `shell_quote`/`py_bin`/`sc_script` variables `M.score_images` already builds for the main scorer command); Task 2's `mask_path` 4th manifest column.
- Produces: a 4th column on the manifest, consumed by Task 2's `parse_manifest_row`; mask PNG files at a path format other code doesn't need to know, since Lua both writes and reads its own naming scheme.

- [ ] **Step 1: Add new temp-path constants**

Next to `MANIFEST_PATH`/`RESULTS_PATH`/etc. (around line 99), add `POINTS_PATH = TMP_DIR .. "/dt_assisted_culling_points.csv"` and `POINTS_DONE_PATH = POINTS_PATH .. ".done"`. Add a helper `local function mask_path_for(id) return TMP_DIR .. "/dt_assisted_culling_mask_" .. tostring(id) .. ".png" end`.

- [ ] **Step 2: Add the precondition check**

Add `local function sam_mask_ready() return dt.ai ~= nil and dt.ai.model_for_task("mask") ~= nil end` near the other small helpers (e.g. next to `file_exists`). In `M.score_images`, immediately after the existing `if sharp_mode == ...` normalization at the top of the function, add: `if sharp_mode == "sam_subject" and not sam_mask_ready() then error("Assisted Culling: subject tracking (SAM) needs darktable's AI mask model enabled and downloaded — see preferences → lua options / AI models.") end`. This lands inside the function's outer `pcall(function() ... end)` (the one assigned to `success, run_err`), matching the existing `error("score_images.py not found at: " .. sc_script)` precondent's failure path — no separate error handling needed.

- [ ] **Step 3: Extend the per-run cleanup block**

In the existing `pcall(os.remove, ...)` block (lines ~340–346), add `pcall(os.remove, POINTS_PATH)` and `pcall(os.remove, POINTS_DONE_PATH)`. After that block (still before `write_manifest`), when `sharp_mode == "sam_subject"`, loop `primaries` and `pcall(os.remove, mask_path_for(img.id))` for each — this clears any mask PNGs left over from a prior `sam_subject` run over an overlapping selection, matching the Review Focus item on re-runs.

- [ ] **Step 4: Run stage A (saliency pre-pass) when `sharp_mode == "sam_subject"`**

After the precondition check and before `write_manifest`, when `sharp_mode == "sam_subject"`: build a command the same way the existing main `cmd` is built (same `shell_quote(py_bin)`, `shell_quote(sc_script)` pattern at lines 376–386) but targeting `MANIFEST_PATH`-equivalent input — write a *first* manifest (`write_manifest(primaries, burst_of)`, called here instead of at its current later call site, since stage A needs it too) and point stage A's output at `POINTS_PATH` with `--emit-saliency-points` appended and no `--sharp-mode`/`--exp-mode`/etc. flags (those are irrelevant to this mode). Run it with `run_async_command(cmd, POINTS_DONE_PATH)`, then block with a plain polling loop mirroring the existing wait structure used later in the file for the main scorer (`dt.control.sleep` in a loop checking for `POINTS_DONE_PATH`'s existence) — no `PROGRESS_PATH`/percent updates for this stage, per the Global Constraints decision; just a static `dt.print_hinter(_("Assisted Culling: finding subjects..."))` for the duration. On timeout or missing `POINTS_DONE_PATH` content, treat it as a hard failure the same way the main run treats a missing scorer (`error(...)`, caught by the outer `pcall`).

- [ ] **Step 5: Run stage B (SAM mask) when `sharp_mode == "sam_subject"`**

Read `POINTS_PATH` with `M.parse_csv_line(line, 3)` (reuse the existing CSV parser — this is why points must be written with the same quoting `write_manifest`/`M.csv_line` use, not a naive format string, per the Review Focus item on commas in paths — points rows don't contain paths, but reusing the shared parser keeps the quoting rule uniform and avoids a second ad hoc format). Load the model once: `local model_id = dt.ai.model_for_task("mask")`, `local ctx = dt.ai.load_model(model_id)` — wrap this single call in `pcall`; failure here (model id present but not downloaded) is a hard failure (`error(...)`), per the Review Focus item distinguishing this from per-image failures. For each `(id, x_frac, y_frac)` row: find the matching image object from `primaries`, call `dt.ai.load_image(img)` to get its tensor, convert the fractions to pixel coordinates against that tensor's shape, call `ctx:run(...)` with the point prompt (confirm the exact input/output tensor argument names against the actual registered mask model at implementation time — `ai.c`'s doc comment only guarantees the generic `ctx:run({inputs},{outputs})` / `ctx:run(input1, input2, ...)` calling conventions, not this specific model's tensor names), and on success call `:save(mask_path_for(id))` on the resulting mask tensor. Wrap each per-image iteration's body in its own `pcall`; on failure, skip writing that id's mask file (it stays absent, which Task 2's fallback handles) — do not abort the loop. After the loop, `ctx:close()`.

- [ ] **Step 6: Thread `mask_path` into the real manifest**

Change `write_manifest(images, burst_of)` to accept an optional third parameter, e.g. `write_manifest(images, burst_of, mask_for_id)`, where `mask_for_id` is `nil` for every other mode and, for `sam_subject`, a table built in Step 5 mapping `id -> mask_path_for(id)` (only for ids that got a mask written). In the function body, append a 4th CSV field: `mask_for_id and mask_for_id[img.id] or ""`. Update `M.score_images`'s later `write_manifest(primaries, burst_of)` call (the one that already exists before building the main `cmd`) to pass this table when applicable; skip the Step 4 early `write_manifest` call's duplication by having Step 4 and this call share the same manifest write only if the image list is identical — simplest correct approach: call `write_manifest` twice (once before stage A with no mask table, once again here with the mask table), since it's cheap and keeps each stage's manifest self-contained.

- [ ] **Step 7: Manual end-to-end verification**

Follow the README's existing `tools/e2e_cli.lua` recipe (same `darktable-cli` invocation already documented), but select a sharpness mode of `sam_subject` via `DT_AI_CULL_*` env vars or a small edit to `tools/e2e_cli.lua`'s hardcoded config for this test run. Point `DT_AI_CULL_FOLDER` at a handful of real photos with a clear single subject against a plainer background. Expected: the TSV report shows ratings/groups as usual, and `dt_assisted_culling_mask_<id>.png` files exist in darktable's temp dir for each scored image, each a non-trivial (not all-black/all-white) mask roughly over the subject.

- [ ] **Step 8: Commit**

```bash
git add lua/culling.lua
git commit -m "feat: SAM-based subject masking pipeline in culling.lua"
```

---

## Task 4: New sharpness option in the panel

**Files:**
- Modify: `lua/culling.lua`

**Interfaces:**
- Consumes: `sharp_mode == "sam_subject"` string, now meaningful to both Task 2 (Python) and Task 3 (Lua).

- [ ] **Step 1: Add the 6th entry to both lists, in the same position**

In `sharp_opts` (currently `{"center", "tiles_uniformity", "peak", "face_detect", "subject_focus"}`), append `"sam_subject"` as the 6th element. In the `sharp_combo` widget's label list (currently `_("center crop"), _("edge-to-edge uniformity"), _("absolute peak 1%"), _("face & eyes (OpenCV)"), _("subject bias (center-weighted)")`), append `_("subject tracking (SAM)")` as the 6th label, in the same position. These two lists must only ever be edited together, index for index — this is the exact class of bug fixed earlier this session.

- [ ] **Step 2: Update the preference range**

`dt.preferences.register("assisted_culling", "last_sharp_mode", "integer", "Last Sharpness Mode", "", 1, 1, 5)` has a hardcoded max of `5`; change the last argument to `6` so the preference can store the new option's index.

- [ ] **Step 3: Update the combobox tooltip**

Extend the tooltip edited earlier this session (currently ends with the `face_detect` fallback note) with a sentence on `sam_subject`'s cost: state plainly that this mode decodes every image twice and runs a real model per image, so it's slower than every other option — recommend it for smaller batches or a final refinement pass, not bulk culling.

- [ ] **Step 4: Manual verification**

Start darktable with `-d lua`, open the Assisted Culling panel, confirm the sharpness dropdown shows 6 entries ending in "subject tracking (SAM)", and that selecting each of the 6 entries in turn and checking `dt.preferences.read("assisted_culling", "last_sharp_mode", "integer")` (e.g. via the darktable Lua console if available, or by restarting and confirming the selection persisted) matches the entry you picked — this is the regression check for the ordering bug class.

- [ ] **Step 5: Commit**

```bash
git add lua/culling.lua
git commit -m "feat: expose SAM subject tracking as a sharpness panel option"
```

---

## Task 5: README documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add the mode to the Panel options sharpness list**

In the `### Panel options` section's `**sharpness**` bullet list (added earlier this session), add a 6th sub-bullet for *subject tracking (SAM)* describing: it uses darktable's native `darktable.ai` SAM mask model, prompted with an automatically-found saliency point (not a click); it's slower than every other mode since it decodes each image twice and runs a model per image — suited to smaller batches or a final refinement pass; it requires the mask model to be enabled and downloaded via darktable's AI preferences, and the whole run fails up front with a clear message if it isn't.

- [ ] **Step 2: Update the Requirements section if applicable**

No new Python dependency to add (confirmed in Task 1/2 — only `cv2`/`numpy`, already listed). Add one line noting that `subject tracking (SAM)` additionally requires darktable 5.6+ with the AI mask model downloaded (the version floor where `darktable.ai` exists, consistent with the "Limitations and ideas" section's existing framing).

- [ ] **Step 3: Rewrite the `darktable.ai` paragraph in "Limitations and ideas"**

Replace the current "parked idea, not worth it yet" framing (written before this feature was built) with a short note that this has since been implemented as the `subject tracking (SAM)` mode, linking back to this trade-off: it's real segmentation, not a heuristic, but meaningfully slower — the center-weighted heuristic mode remains for speed/no-dependency use. Keep the explanation of *why* it needed a three-stage pipeline (the `darktable.ai`-runs-in-Lua-only, Python-does-the-scoring split) since that context is still true and useful to a future contributor.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document the SAM subject tracking sharpness mode"
```

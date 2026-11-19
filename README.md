# darktable-assisted-tagging

A tagging assistant for [darktable](https://www.darktable.org/) that recognises the motorsport vehicles in your photos. Select a batch in lighttable, click one button, and for every car or bike in each frame it will:

- **read its race number** and look it up in your entry list
- if the number isn't readable, **match its livery** against reference samples you picked
- if that's still unclear, **borrow the answer from the rest of its group** (a darktable group or an Assisted Grouping tag group, see [Grouping support](#grouping-support))
- tag the image with that entry's tags, e.g. `Assisted Tagging|Motorsport|Team|Red Bull` and `Assisted Tagging|Motorsport|Driver|Max Verstappen`

Teammates in identical liveries that it can't tell apart get only their shared team tag, never a guessed driver. Everything runs locally: a Lua plugin inside darktable and a Python identifier it shells out to. No API keys, no cloud. It only adds and removes tags from your entry list and its own `Assisted Tagging|…` tags; your other tags, ratings and colour labels are never touched.

Forked from [darktable-assisted-culling](https://github.com/louiswdavis/darktable-assisted-culling). The two can be installed side by side.

## Contents

- [Requirements](#requirements)
- [Install](#install)
- [Using it](#using-it)
  - [Starting a collection](#starting-a-collection)
  - [Building references](#building-references)
  - [Identifying](#identifying)
- [Presets](#presets)
- [Panel options](#panel-options)
- [Preferences](#preferences)
- [How it works](#how-it-works)
- [Tuning](#tuning)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)
- [Acceptance checklist](#acceptance-checklist)
- [Development](#development)

## Requirements

- darktable 5.6, built with Lua (the official builds are).
- Python 3.10+ with the packages in `python/requirements.txt`: `opencv-python-headless` (4.x, pinned `<5`), `numpy`, `Pillow`, `rawpy`, `onnxruntime` and `PyYAML` (only the PaddleOCR text finder and readers use it).
- About 160 MB of models, listed below.

`rawpy` needs `libraw`. The Windows and macOS wheels bundle it; on Linux install `libraw-dev` first, or skip `rawpy` if you only shoot JPEG.

## Install

### 1. Python side

```
git clone https://github.com/louiswdavis/darktable-assisted-tagging
cd darktable-assisted-tagging

# Windows (Command Prompt or PowerShell)
python -m venv .venv
.venv\Scripts\python -m pip install -r python\requirements.txt

# Linux / macOS
python3 -m venv .venv
.venv/bin/python -m pip install -r python/requirements.txt
```

### 2. Models

Download them into a `models` folder in the repo. The plugin looks there, `.gitignore` skips the whole folder, and `git pull` leaves it alone. Run every curl block below from the repo root, the folder holding `README.md`, not `python/`; `--create-dirs` makes `models/`.

The plugin picks the model for each job itself. Each table below lists one job's files best first; the plugin uses the best one in `models/` and ignores the rest. The row marked `(base)` comes with the base install; a row below it is an older fallback. A job with none of its files installed stops the run with an error naming the file to get (the face models are the exception: only people collections need them).

The run log names each pick, plus any better file you haven't installed, e.g. `vehicles: object_detection_yolox_2022nov.onnx (better, not installed: dfine_x_coco.onnx, …)`. Adding or removing a file changes the pick on the next run:

- a new vehicle finder, text finder or number reader re-reads every photo once, because the model is part of the cache key
- a new livery embedder re-embeds every reference before analysing (the progress bar counts the references; on a large collection this takes minutes, and a cancel keeps those already done)

**Base install** (Windows 10+ ships `curl`):

```
curl -L --create-dirs -o models/object_detection_yolox_2022nov.onnx https://github.com/opencv/opencv_zoo/raw/main/models/object_detection_yolox/object_detection_yolox_2022nov.onnx
curl -L --create-dirs -o models/text_detection_en_ppocrv3_2023may.onnx https://github.com/opencv/opencv_zoo/raw/main/models/text_detection_ppocr/text_detection_en_ppocrv3_2023may.onnx
curl -L --create-dirs -o models/en_PP-OCRv5_mobile_rec.onnx https://huggingface.co/PaddlePaddle/en_PP-OCRv5_mobile_rec_onnx/resolve/main/inference.onnx
curl -L --create-dirs -o models/en_PP-OCRv5_mobile_rec.yml https://huggingface.co/PaddlePaddle/en_PP-OCRv5_mobile_rec_onnx/resolve/main/inference.yml
curl -L --create-dirs -o models/dinov2_small.onnx https://huggingface.co/onnx-community/dinov2-small/resolve/main/onnx/model.onnx
```

**Recommended extras** (about 2.2 GB). These find more cars, read more numbers and car colours, and match liveries better than the base install. Then `pip install -r` again (SigLIP 2 needs the `tokenizers` package, D-FINE needs `onnxruntime`):

```
curl -L --create-dirs -o models/dfine_x_coco.onnx https://huggingface.co/onnx-community/dfine_x_coco-ONNX/resolve/main/onnx/model.onnx
curl -L --create-dirs -o models/siglip2_base_vision.onnx https://huggingface.co/onnx-community/siglip2-base-patch16-224-ONNX/resolve/main/onnx/vision_model.onnx
curl -L --create-dirs -o models/siglip2_base_text.onnx https://huggingface.co/onnx-community/siglip2-base-patch16-224-ONNX/resolve/main/onnx/text_model.onnx
curl -L --create-dirs -o models/siglip2_base_tokenizer.json https://huggingface.co/onnx-community/siglip2-base-patch16-224-ONNX/resolve/main/tokenizer.json
curl -L --create-dirs -o models/PP-OCRv5_server_rec.onnx https://huggingface.co/PaddlePaddle/PP-OCRv5_server_rec_onnx/resolve/main/inference.onnx
curl -L --create-dirs -o models/PP-OCRv5_server_rec.yml https://huggingface.co/PaddlePaddle/PP-OCRv5_server_rec_onnx/resolve/main/inference.yml
curl -L --create-dirs -o models/dinov2_base.onnx https://huggingface.co/onnx-community/dinov2-base/resolve/main/onnx/model.onnx
curl -L --create-dirs -o models/image_segmentation_efficientsam_ti_2025april.onnx https://github.com/opencv/opencv_zoo/raw/main/models/image_segmentation_efficientsam/image_segmentation_efficientsam_ti_2025april.onnx
```

| Files | Turns on |
|---|---|
| `dfine_x_coco.onnx` | the best [vehicle finder](#vehicles) (finds more cars than YOLOX) |
| `siglip2_base_*` (3 files) | [box check and colour reader](#box-check-and-colour-reader-optional-siglip-2) |
| `PP-OCRv5_server_rec.*` | the better [number reader](#number-reader) |
| `dinov2_base.onnx` | the better [livery embedder](#livery-embedder) |
| `image_segmentation_efficientsam_*` | the [segmenter](#segmenter-optional) for overlapping cars |

**Largest livery embedder** (1.22 GB, optional). Matches liveries best but embeds slowest. Once it's in `models/`, the plugin uses it instead of `dinov2_base`:

```
curl -L --create-dirs -o models/dinov2_large.onnx https://huggingface.co/onnx-community/dinov2-large/resolve/main/onnx/model.onnx
```

**People collections only** (face models; motorsport doesn't use them):

```
curl -L --create-dirs -o models/face_detection_yunet_2023mar.onnx https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
curl -L --create-dirs -o models/face_recognition_sface_2021dec.onnx https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
```

Not in any block on purpose: the other vehicle finders (`dfine_l`, `rtdetr_v2`, `dfine_m`, `dfine_s`: smaller or slower steps between YOLOX and D-FINE-X), the CRNN reader (an older fallback) and PP-OCRv6 small (on trial, see [Trying PP-OCRv6 small](#trying-pp-ocrv6-small)). Their downloads are in the tables below.

**curl says `client returned ERROR on write` (error 23)?** curl got the data but couldn't save it. It isn't because the file already exists: curl overwrites. Either `models/` doesn't exist where you ran it (run from the repo root, with `--create-dirs`), or the file is in use (close darktable, or wait for a run to finish, then retry).

**Check what's installed.** Each file must be named exactly as above (curl's `-o` does that; a browser download saves `vision_model.onnx`, `inference.onnx` and so on, which the plugin can't find). The start of the run log lists what each job picked:

```
number reader: … (PP-OCRv5_server_rec.onnx); text finder: …
box check: on (SigLIP 2); colour reader: SigLIP 2
```

`box check: off (no SigLIP 2 model); colour reader: HSV rules` means the SigLIP 2 files are missing or misnamed. `(better, not installed: …)` names files you could add. The first run after adding any of these re-reads every photo once, so expect it to take longer.

The tables give the download for every other file. Save each under the name in the File column.

#### Vehicles

| File | Size | Download | Source, licence |
|---|---|---|---|
| `dfine_x_coco.onnx` | 251 MB | `https://huggingface.co/onnx-community/dfine_x_coco-ONNX/resolve/main/onnx/model.onnx` | D-FINE-X COCO via onnx-community, Apache-2.0 |
| `dfine_l_coco.onnx` | 125 MB | `https://huggingface.co/onnx-community/dfine_l_coco-ONNX/resolve/main/onnx/model.onnx` | D-FINE-L COCO via onnx-community, Apache-2.0 |
| `rtdetr_v2_r50vd.onnx` | 172 MB | `https://huggingface.co/onnx-community/rtdetr_v2_r50vd-ONNX/resolve/main/onnx/model.onnx` | RT-DETRv2 R50 via onnx-community, Apache-2.0 |
| `dfine_m_coco.onnx` | 79 MB | `https://huggingface.co/onnx-community/dfine_m_coco-ONNX/resolve/main/onnx/model.onnx` | D-FINE-M COCO via onnx-community, Apache-2.0 |
| `dfine_s_coco.onnx` | 42 MB | `https://huggingface.co/onnx-community/dfine_s_coco-ONNX/resolve/main/onnx/model.onnx` | D-FINE-S COCO via onnx-community, Apache-2.0 |
| `object_detection_yolox_2022nov.onnx` (base) | 36 MB | base install above | OpenCV model zoo (YOLOX), Apache-2.0 |

To compare two vehicle finders on your own photos (frames with a car, cars missed, boxes per frame, CPU ms per frame at three score thresholds, plus a CSV of the frames where they disagree on box count):

```
python python/compare_detectors.py --detector models/object_detection_yolox_2022nov.onnx --detector models/dfine_s_coco.onnx --truth results.csv --manifest manifest.csv --out compare_detectors.csv --disagree disagree.csv <a folder of photos>
```

`--truth` is a tagging run's `results.csv` and `--manifest` its `id,filepath` manifest (both optional, both together): a frame with a box there counts as a frame with a car, and a detector that finds no box on it at a threshold has missed it. It also prints the summary as a markdown table, ready to paste into notes or an issue.

#### Segmenter (optional)

For pack shots with overlapping cars. With it in `models`, a box that overlaps another is read through a car-shaped mask, with the background and the neighbouring car painted grey. The plugin works without it.

| File | Size | Download | Source, licence |
|---|---|---|---|
| `image_segmentation_efficientsam_ti_2025april.onnx` | 48 MB | `https://github.com/opencv/opencv_zoo/raw/main/models/image_segmentation_efficientsam/image_segmentation_efficientsam_ti_2025april.onnx` | OpenCV model zoo (EfficientSAM), Apache-2.0 |

#### Text finder

| File | Size | Download | Source, licence |
|---|---|---|---|
| `text_detection_en_ppocrv3_2023may.onnx` (base) | 2.4 MB | base install above | OpenCV model zoo (PP-OCRv3), Apache-2.0 |
| `PP-OCRv6_small_det.onnx` + `.yml` (on trial) | 9.9 MB | `https://huggingface.co/PaddlePaddle/PP-OCRv6_small_det_onnx/resolve/main/inference.onnx` and `…/inference.yml` | PaddleOCR via PaddlePaddle on Hugging Face, Apache-2.0 |

A PaddleOCR text finder runs on onnxruntime with the thresholds and normalisation from its `.yml`, which must sit beside it under the same name. It is on trial (see [Trying PP-OCRv6 small](#trying-pp-ocrv6-small)): the plugin uses it only when the PP-OCRv3 file is not in `models/`.

#### Number reader

A PaddleOCR reader needs its `.yml` (its dictionary) beside it under the same name; a yml whose dictionary doesn't fit the model stops the run at the start with an error.

| File | Size | Download | Source, licence |
|---|---|---|---|
| `PP-OCRv5_server_rec.onnx` + `.yml` | 84.5 MB | `https://huggingface.co/PaddlePaddle/PP-OCRv5_server_rec_onnx/resolve/main/inference.onnx` and `https://huggingface.co/PaddlePaddle/PP-OCRv5_server_rec_onnx/resolve/main/inference.yml` | PaddleOCR via PaddlePaddle on Hugging Face, Apache-2.0 |
| `en_PP-OCRv5_mobile_rec.onnx` + `.yml` (base) | 7.9 MB | base install above | PaddleOCR via PaddlePaddle on Hugging Face, Apache-2.0 |
| `PP-OCRv6_small_rec.onnx` + `.yml` (on trial) | 21.2 MB | `https://huggingface.co/PaddlePaddle/PP-OCRv6_small_rec_onnx/resolve/main/inference.onnx` and `…/inference.yml` | PaddleOCR via PaddlePaddle on Hugging Face, Apache-2.0 |
| `text_recognition_CRNN_EN_2021sep.onnx` | 34 MB | `https://github.com/opencv/opencv_zoo/raw/main/models/text_recognition_crnn/text_recognition_CRNN_EN_2021sep.onnx` | OpenCV model zoo (CRNN), Apache-2.0 |

The CRNN is the plugin's first reader. It reads grey crops at a smaller size and misses more numbers (on 202 rally photos it read a number on 45 vehicles where PP-OCRv5 read 76), so the plugin uses it only when no v5 reader is installed. To compare readers on your own photos, print each vehicle's reads from both, with the ones that differ marked and a count of how many vehicles each got a number on:

```
python python/compare_ocr.py --rec models/text_recognition_CRNN_EN_2021sep.onnx --rec models/en_PP-OCRv5_mobile_rec.onnx --out compare.csv <a folder of photos>
```

#### Trying PP-OCRv6 small

PP-OCRv6 small (text finder and reader, 31 MB together) may read angled numbers better than PP-OCRv3 + PP-OCRv5 mobile. Paddle's own benchmark puts its detection on rotated text at 93.7 against 64.7 and its reading at 81.3 against 73.7; those are the publisher's figures, not measured here. It stays on trial until a measured run on your photos beats today's models. To measure it:

1. Download both v6 files and their `.yml` into `models/`, named as in the tables above.
2. Select hand-tagged photos and run **Verify selection**. Copy the run's `boxes.json` aside (the next run overwrites it) and run `python python/eval_numbers.py COPY.json`. Note *read right* and *wrong entry*, and the run log's `analysis: … frames/min` line.
3. Move `text_detection_en_ppocrv3_2023may.onnx`, `en_PP-OCRv5_mobile_rec.onnx` (+ `.yml`), and `PP-OCRv5_server_rec.onnx` and the CRNN if you have them, out of `models/`. The run log should now say `text finder: PP-OCRv6_small_det.onnx` and `number reader: PP-OCRv6_small_rec.onnx`.
4. Repeat step 2 (changing models re-reads every photo once), then move the files back.

v6 small is worth making the default if it reads more numbers right without more wrong entries, at a speed you can live with (Paddle reports ~0.6 s per image on CPU). Its detection scores come from a different model, so `OCR_MIN_SCORE` may need tuning: `eval_numbers.py --set OCR_MIN_SCORE=0.7` replays the run at another threshold.

#### Livery embedder

| File | Size | Download | Source, licence |
|---|---|---|---|
| `dinov2_large.onnx` | 1.22 GB | `https://huggingface.co/onnx-community/dinov2-large/resolve/main/onnx/model.onnx` | DINOv2 ViT-L/14 via onnx-community, Apache-2.0 |
| `dinov2_base.onnx` | 347 MB | `https://huggingface.co/onnx-community/dinov2-base/resolve/main/onnx/model.onnx` | DINOv2 ViT-B/14 via onnx-community, Apache-2.0 |
| `dinov2_small.onnx` (base) | 89 MB | base install above | DINOv2 ViT-S/14 via onnx-community, Apache-2.0 |

Compare a larger embedder before installing it with `python python/eval_matching.py COLLECTION_DIR --embedder models/dinov2_base.onnx --fresh-embed` (re-embeds the refs with that model in memory; `index.npz` is untouched).

Score the number reader against your hand tags with `python python/eval_numbers.py BOXES.json`, on the boxes.json of a `--verify` run (which stores every OCR region and why it was dropped). It reports how many single-box frames are read right, why each miss was missed (no region, region dropped, under `min_read`, recognised wrong, lost in matching), and the misreads. `--set OCR_MIN_SCORE=0.7` (also `NUMBER_MIN_HEIGHT`, `min_read`, `WEAK_READ_MIN`, `NUMBER_LIST_MARGIN`, `NUMBER_LIST_FLOOR`) replays the run at another threshold without re-reading any image. The replay works out the noise numbers again from the stored regions at its own thresholds, since they depend on `min_read`; with no `--set` they are the run's own.

#### Box check and colour reader (optional, SigLIP 2)

The vehicle detector also boxes marshals, sheds and railings. With SigLIP 2 in `models`, each box is checked before it is read: a box that looks more like a person, a building, a railing, spectators, trees or an empty road than a vehicle (a rally car, a race car, a motorbike or quad, or a truck) is dropped, and the log counts what was dropped (`box check: dropped 4 boxes: person 3, railing 1`). **Add as reference** uses the check to pick its box (a frame's largest box that fails it is passed over), but never drops a frame for it. The same model reads each car's paintwork colour for the [Colour family](#tag-families) in place of the built-in hue rules, comparing the car with "a photo of a red rally car." and so on for each palette name, plus "multicoloured"; an unsure read (top score under 0.4, or within 0.1 of the next) gives no colour. Without it, every box is read and colour comes from the hue rules. Adding or removing it re-reads every photo once. People collections don't use it.

##### Number gate (experimental, SigLIP 2)

`number_gate` in `settings.json` (off by default, not in the panel) asks SigLIP 2 one more question of each box before the number reader runs: does the crop show a racing number at all? A box whose number share is under `NUMBER_GATE_MIN` (a distant car, a car seen from behind, a blurred pass) is not read, which saves the read and stops stray text on it being taken for a number. Its `ocr_trace` in `boxes.json` is `[[0.0, "gated"]]` and the log counts them (`number gate: 12 of 80 boxes not read`). A box that is read again at higher detail, cropped with a mask or found by burst rescue is always read. Turning it on re-reads every photo once.

To choose the threshold, turn `number_gate` on, run **Verify selection** on hand-tagged photos (a verify run still reads the gated boxes, for the replay only), then compare `python python/eval_numbers.py BOXES.json` with `python python/eval_numbers.py BOXES.json --set NUMBER_GATE_MIN=0`: the second is the same run with the gate open. Misses the gate caused are counted under `gated`.

Download the three files and rename them; the plugin finds the text model and tokenizer beside the vision file by name, and stops with a message naming any that is missing. Python also needs the `tokenizers` package (in `requirements.txt`).

| File | Download (rename to the file name) | Source, licence |
|---|---|---|
| `siglip2_base_vision.onnx` | `https://huggingface.co/onnx-community/siglip2-base-patch16-224-ONNX/resolve/main/onnx/vision_model.onnx` | SigLIP 2 base (Google, Apache-2.0) via onnx-community; the export states no licence |
| `siglip2_base_text.onnx` | `https://huggingface.co/onnx-community/siglip2-base-patch16-224-ONNX/resolve/main/onnx/text_model.onnx` | same |
| `siglip2_base_tokenizer.json` | `https://huggingface.co/onnx-community/siglip2-base-patch16-224-ONNX/resolve/main/tokenizer.json` | same |

#### Face detector and face recognizer (people collections only)

People collections (`"kind": "people"` in entries.json) need these two. Motorsport collections don't:

| File | Job | Download | Source, licence |
|---|---|---|---|
| `face_detection_yunet_2023mar.onnx` | finds faces | `https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx` | OpenCV model zoo (YuNet), MIT |
| `face_recognition_sface_2021dec.onnx` | turns each face into a 128-number fingerprint | `https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx` | OpenCV model zoo (SFace), Apache-2.0 |

A people entry has only `id` and `tags`; references are photos with exactly one face, so tag those photos by hand first. Choose `min_sim`, `margin` and `min_face_px` in `settings.json` with `python python/eval_people.py <collection> --face-detector … --face-recognizer …`.

**Audit references** (panel button, `python/audit_refs.py`) needs nothing beyond the packages in `requirements.txt` and the models above.

### 3. darktable side

darktable's config directory is `~/.config/darktable` on Linux/macOS and `%LOCALAPPDATA%\darktable` on Windows. Link the plugin into it and load it from `luarc`. The plugin is `lua/assisted_tagging.lua` plus `lua/plugin_common.lua`, the module the three Assisted plugins share; a link into the repo finds the module beside the plugin by itself.

Linux / macOS:

```
mkdir -p ~/.config/darktable/lua/contrib
ln -s "$(pwd)/lua/assisted_tagging.lua" ~/.config/darktable/lua/contrib/assisted_tagging.lua
echo 'require "contrib/assisted_tagging"' >> ~/.config/darktable/luarc
```

Windows (Command Prompt). Creating symbolic links needs an Administrator prompt unless Developer Mode is enabled.

```
if not exist "%LOCALAPPDATA%\darktable\lua\contrib" mkdir "%LOCALAPPDATA%\darktable\lua\contrib"
mklink "%LOCALAPPDATA%\darktable\lua\contrib\assisted_tagging.lua" "%CD%\lua\assisted_tagging.lua"
echo require "contrib/assisted_tagging" >> "%LOCALAPPDATA%\darktable\luarc"
```

Windows without Administrator rights or Developer Mode: copy `assisted_tagging.lua` into `%LOCALAPPDATA%\darktable\lua\contrib` instead of linking it, and add the same `luarc` line. Re-copy it after every update. With the **plugins folder** preference (next step) set, the plugin loads `plugin_common.lua` from that folder's `lua/`; copy it into `contrib` too if you want darktable to start with the preference unset (the three plugins' copies are identical, so one copy serves all of them).

### 4. Point the plugin at the repo

Start darktable, open **preferences → lua options**, and set **plugins folder (holds the three assisted-* folders)** to the folder that holds `darktable-assisted-tagging` (and the other assisted plugins). From there the plugin finds `python/identify.py`, the `models` folder and the `.venv` by itself. The preference is shared by the assisted plugins; the older per-plugin **Assisted Tagging: plugin folder** preference still works, and the log says once to move it. There is no interpreter preference: the plugin runs its own `.venv` (else `python`/`python3` on `PATH`), because each assisted plugin has different requirements.

## Using it

The **Assisted Tagging** panel is in lighttable. Start a collection, give its entries some references, then identify a selection.

Running all three plugins? [WORKFLOW.md](../darktable-assisted-grouping/WORKFLOW.md) says which order to pick and what to re-run after what.

### Starting a collection

A **collection** is one entry list plus its reference samples: normally one series and season (`F1 2026`), or one event (`BTCC 2026 Brands Hatch`). Collections live in the collections folder, by default `assisted_tagging/collections` in darktable's config directory (the panel creates it the first time it loads). Each one is a folder:

```
collections/
  F1 2026/
    entries.json      # built for you, or write it yourself
    refs/             # the plugin fills this when you add references
      VER/1234.jpg
      index.npz
```

Build one of two ways:

#### From already-tagged images (recommended)

If you've already hand-tagged a handful of photos — one per competitor, e.g. `Motorsport|F1|Red Bull` on both Red Bull cars and `Motorsport|F1|Red Bull|Max Verstappen` on just his — the panel can turn those into a working collection in one click. This isn't motorsport-specific: it only ever reads whatever `A|B|C`-style tags you've already used, so the same button builds a collection for any set of visually-distinguishable, hierarchically-tagged subjects.

1. In lighttable, select a handful of already-tagged photos — **at least 2 per target**, from different angles.
2. Under **new collection** in the panel, type a name for the collection, e.g. `F1 2026`.
3. Under **new collection**, click **From tagged images**.

It reads each selected image's tags down to wherever two images stop being identical: images carrying the exact same tags become one entry, and whatever tag is unique to a photo (the driver tag) is what tells two teammates apart. From that it:

- creates the collection folder with an `entries.json` built from those tag sets, inferring each entry's `team` where a tag is shared with some but not all of the other entries, and its race `number` when the deepest tag's leaf is 1-3 digits (e.g. a `Car|Number|44` convention sets `number: "44"` automatically)
- adds every selected image as a reference sample of its entry, exactly like [**Add tagged images**](#building-references)
- switches the panel to the new collection and reloads it

Two kinds of selected image don't become an entry, and are reported in the done message rather than silently dropped:

- an image with no tag that looks like `A|B` has nothing to build an entry from
- a tag that only 1 selected image carries is skipped rather than turned into a single-sample entry — a lone sample tells the matcher nothing about how that target varies across angles and light, so it's better surfaced as "needs more references" than quietly matched (and likely mismatched) later. Select at least 2 photos per target to avoid this.

If you want number-based identification but your tags don't already encode the number, or you want custom [rules](#rules), add those by hand afterward (see below). If a collection with that name already exists, nothing is overwritten — pick a new name, or switch to the existing one and use **Add tagged images** instead.

#### From an example

No tagged photos yet, or just want to see the shape of a working `entries.json`? The **example** dropdown in the panel lists the collections shipped in [`examples/`](examples) — no images needed, since these ship with their structure already filled in (with placeholder names, not real references):

1. Pick one in the **example** dropdown.
2. Click **View example** to open its `entries.json` in your editor and read it, or
3. type a name under **new collection** and click **From example** to copy it into a real collection.

Either way, a created collection still needs its placeholder names replaced with your own competitors (and references added, for anything you want livery-matched) before it identifies anything correctly — click **Open entries.json** at the top of the panel at any time to open the *active* collection's file the same way.

#### By hand

Write `entries.json` yourself for more control than tags alone give you: a race `number`, or custom [rules](#rules). It holds the collection's **entries**, one per competitor, and its **rules**: what each outcome tags. For example:

```json
{
  "rules": {
    "team_only": "shared tags",
    "unidentified": ["Motorsport|Unidentified"]
  },
  "entries": [
    { "id": "VER", "number": "1",  "team": "Red Bull", "name": "Max Verstappen" },
    { "id": "TSU", "number": "22", "team": "Red Bull", "name": "Yuki Tsunoda" },
    { "id": "SAFETY", "name": "Safety Car" }
  ]
}
```

Here VER gets `Assisted Tagging|Motorsport|Number|1`, `Assisted Tagging|Motorsport|Team|Red Bull` and `Assisted Tagging|Motorsport|Driver|Max Verstappen`, and SAFETY gets `Assisted Tagging|Motorsport|Driver|Safety Car`: one tag per [tag family](#tag-families) the entry has a value for. Add a `tags` list to an entry for extra tags on top.

A file that's just the `[ … ]` list of entries works too, with the default rules — this is the shape **new collection → From tagged images** writes, each entry with its tags in full. You can hand-edit the result to add numbers or rules.

[`examples/`](examples) has four collections — pick one from the panel's **example** dropdown (see [above](#from-an-example)), which copies its `entries.json` and `settings.json`, or copy its folder into the collections folder by hand. Each has a README on what it shows and how to supply its references:

- [`f1-season`](examples/f1-season): a season with near-identical teammates, a one-off livery and number-less cars
- [`btcc-event`](examples/btcc-event): one race weekend, with a "check me" tag for misses and no team-only tags
- [`minimal`](examples/minimal): a bare entry list on the default rules
- [`rally`](examples/rally): number-only entries for cars of no known livery, with the neighbour aid on (`order_weight`) and its own family roots, and grouping support set to Grouping tags, all set in its `settings.json`

#### Entries

| Field | Required | Rules |
|---|---|---|
| `id` | yes | unique within the collection; it's also the folder name under `refs/`, so it can't contain `, ; " / \ : * ? < > \|` |
| `tags` | only when no [tag family](#tag-families) builds a tag for the entry | one or more darktable tag names (`\|` makes a hierarchy); no `,` `;` or `"`. Extras added after the family tags |
| `name` | no | the driver's display name, e.g. `Max Verstappen`; the Driver family writes it as `<root>\|<name>` |
| `co_driver` | no | a rally co-driver's display name; the Co-driver family writes it as `<root>\|<co_driver>`. No `,` `;` or `"`. Entries without one get no co-driver tag |
| `number` | no | the race number, 1–3 digits. Leave it out for a car with no number; it can then only be identified by livery. Two entries with the same number are allowed, but that number then identifies neither. |
| numbers-only entry | | `{"id": "12", "number": "12"}`: an entry with a number and no `team`, `name` or `tags` gets the Number family's tag, `Assisted Tagging\|Motorsport\|Number\|12` by default. Build a whole list from a CSV with `python python/import_numbers.py numbers.csv entries.json`, or add a full start list (names, teams, classes) with the panel's **Import start list** (see [1 collection](#1-collection)); see [`rally`](examples/rally) |
| `team` | no | the Team family writes it as `<root>\|<team>`; entries with the same team can fall back to their shared tags when their liveries are too close to call |
| `extra` | no | the entry's class (the start list's Class column); the Class family writes it as `<root>\|<extra>`. No `\|` `,` `;` or `"` |
| `make`, `model` | no | the car's make and model; the Vehicle family writes `<root>\|<make>\|<model>`, or `<root>\|<make>` without a model. A `model` needs a `make`. No `\|` `,` `;` or `"` |
| `colour` | no | the car's paintwork colour: a name in the active palette, or `Multi` (needs the [Colour family](#tag-families)). Breaks ties between number candidates and flags a number read that disagrees; never a hard filter. The reference actions fill it in when it is missing |
| `car` | no | a double-driven car: the id of the other entry in the same car, set on the higher-numbered entry only (`"car": "30"` on 730). Both entries then carry each other's tags, so any match on the car (number read, livery, hand tag) tags both drivers, and their livery references count as one car. Two entries per car at most. A combined number on the car (`8108`) stays unknown: tag `Number seen\|108` by hand |
| `shows` | no | other numbers the car carries besides its entry number, as a list (`"shows": ["44"]`): an old event's number left on the door, or a covered digit (`808` on 108). A read of a shown number names this entry; when another entry has that number too, livery picks between them. 1–3 digits each, not the entry's own number |
| `paddock` | no | where the car parks, as printed on the entry list (`"paddock": "H3"`). Free text, never read by a match; the start-list import fills it from the **Paddock** column. A demonstration entry also uses it as its id |

Teammates share their team tag, so a team-only result carries exactly the team tag. The examples leave the year out of the tags: the collection already separates seasons for matching, and darktable's collections module filters by capture date. A **livery change** mid-season is a new entry (`VER-miami`, with the same tags and no `number`, so the number still identifies `VER`) or a new collection.

#### Tag families

A family is one kind of tag the plugin writes. Each has a switch and a root in the collection's [`settings.json`](#collection-settings-settingsjson) (panel page **4 tags written**, heading **tag families**), and writes `<root>|<value>`:

| Family | Value | Switch | Root setting | Default root |
|---|---|---|---|---|
| Colour | the paintwork colour read from the photo | `family_colour` | `family_colour_root` | `Assisted Tagging\|Motorsport\|Colour` |
| Number | the entry's `number` | `family_number` | `family_number_root` | `Assisted Tagging\|Motorsport\|Number` |
| Team | the entry's `team` | `family_team` | `family_team_root` | `Assisted Tagging\|Motorsport\|Team` |
| Driver | the entry's `name` | `family_driver` | `family_driver_root` | `Assisted Tagging\|Motorsport\|Driver` |
| Co-driver | the entry's `co_driver` | `family_co_driver` | `family_co_driver_root` | `Assisted Tagging\|Motorsport\|Co-driver` |
| Class | the entry's `extra` | `family_extra` | `family_extra_root` | `Assisted Tagging\|Motorsport\|Class` |
| Vehicle | the entry's `make` and `model`, as `<make>\|<model>` | `family_vehicle` | `family_vehicle_root` | `Assisted Tagging\|Motorsport\|Vehicle` |
| Sponsor | each [`sponsor_keywords`](#rules) word read inside a vehicle box, title-cased (`castrol` → `Castrol`) unless [`sponsor_names`](#rules) spells it; words read on banners or not listed are never written. Off by default | `family_sponsor` | `family_sponsor_root` | `Assisted Tagging\|Motorsport\|Sponsor` |

All eight are on by default except Sponsor. An identified entry gets one tag per family that is on and that it has a value for, then its own `tags`. An entry that builds no tag at all stops the run.

An older entries.json may hold `Motorsport|Class|…` and `Motorsport|Vehicle|…` entry tags from an earlier start-list import. The next reload moves them into the `extra`, `make` and `model` fields and keeps the previous file as `entries.json.bak`. A field that disagrees with its tag, or a tag deeper than `Motorsport|Class|<class>` or `Motorsport|Vehicle|<make>|<model>`, stops the load and names the entry; fix it by hand.

A root is a tag path: no `,` `;` or `"`, and it can't start or end with `|` or a space. Each family needs its own root: no root may equal another or sit under it. Switching a family off stops runs writing its tags; the Colour family also reads the colour, so switching it on re-reads every photo once.

**Coming from `tag_prefix`.** `rules.tag_prefix`, `colour_tags`, `tag_colour` and `tag_colour_name` no longer exist, and a collection that still has one stops with a message naming the replacement. In each collection:

1. Delete `"tag_prefix"` from `rules` in `entries.json`. Where it built `prefix|team|name`, the families write `<root>|<team>` and `<root>|<name>` separately.
2. Delete `colour_tags`, `tag_colour` and `tag_colour_name` from `settings.json`, and set `family_colour` to what `colour_tags` was.
3. To keep tags under the old prefix, set the roots below it, e.g. `"family_team_root": "Motorsport|F1|Team"`.
4. Point each `rules.sponsor_keywords` value at the team's new tag.

Tags a previous run wrote under the old names stay on images until you remove them.

#### Rules

Every key is optional; leave one out for its default.

| Rule | Default | What it does |
|---|---|---|
| `team_only` | `"shared tags"` | when two teammates are too close to call: `"shared tags"` adds the tags both entries carry, `"none"` adds no collection tags (only the *Team only* diagnostic) |
| `unidentified` | `[]` | tags added to an image where no vehicle was identified, e.g. a "check me" tag for the shoot |
| `colour_palette` | the 11 built-in colours | an object mapping each tag name to a built-in colour (`"Red"`, `"Orange"`, `"Yellow"`, `"Green"`, `"Blue"`, `"Purple"`, `"Pink"`, `"Brown"`, `"White"`, `"Grey"`, `"Black"`) or to a list of bounds in OpenCV HSV, e.g. `{"Red": "Red", "Teal": [{"hue": [80, 95], "sat": [90, 255]}], "Silver": "Grey"}`. Each bounds object needs `hue` (0–179) and may have `sat` and `val` (0–255); a missing one is the full range. A pixel goes to the first colour that matches. A name can't be `Multi` or contain `\|`. Entry colours must be in the palette. Unlisted built-ins are dropped. With SigLIP 2 installed only the names count: each becomes a prompt and the bounds are not used |
| `sponsor_keywords` | `{}` | maps a lowercase sponsor word to its team's tag, e.g. `{"petronas": "Assisted Tagging\|Motorsport\|Team\|Mercedes"}`. A word read on a car (OCR confidence 0.90+; one typo allowed in words of 6+ letters) narrows matching to that team. Sponsors of two teams on one car give no hint. A prefix no entry sits under stops the run. |
| `sponsor_names` | `{}` | how the Sponsor family writes a `sponsor_keywords` word, e.g. `{"dhl": "DHL", "mcdonalds": "McDonald's"}`. A word not listed is title-cased. Each key must be a `sponsor_keywords` word; values can't hold `,` `;` `"` or `\|`. |

Behaviour settings live in settings.json, not `rules`. An entries.json whose `rules` still hold one loads: each is copied into settings.json once and logged.

An unknown key, or a misspelt one, stops the run and names it, so a typo can't silently do nothing.

#### Collection settings (settings.json)

Every other setting lives in the collection's `settings.json`, beside `entries.json`. The panel's **update preset** writes it and **Reload** re-reads it; a UTF-8 BOM at the start is accepted. A key missing from the file uses its default, and a value that is out of range or the wrong type falls back to the default with one log line. Most settings have a field in the panel; the seven marked `no` are set only in the file.

| Key | What it does | Allowed values | Default | In panel |
|---|---|---|---|---|
| `use_hints` | a team tag you applied narrows matching on a solo shot | `true`, `false` | `true` | yes |
| `group_support` | which groups the burst step borrows answers from, see [Grouping support](#grouping-support) | `"native"`, `"tags"`, `"none"` | `"native"` | yes |
| `group_node` | the grouping tag node used when `group_support` is `"tags"`; blank uses each photo's own latest Assisted Grouping run | text | `""` | yes |
| `run_tag` | stamps images with `Assisted Tagging\|Run\|YYYY-MM-DD HH:MM`: `changed` only copies whose tags the run added or removed, `all` every copy it processes (slow on large shoots). Old `true`/`false` files read as `all`/`none` | `none`, `changed`, `all` | `none` | yes |
| `suggest_crops` | **Audit references** suggests re-crops | `true`, `false` | `false` | yes |
| `quarantine` | **Audit references** quarantines poor references | `true`, `false` | `false` | yes |
| `cars_per_photo` | `solo`: only each photo's largest car is tagged; a smaller car counts only when its number is read, so background cars add no car or colour tags. `packs`: every car found is tagged (circuit racing) | `solo`, `packs` | `solo` | yes |
| `closer_car_margin` | a livery, burst or neighbour match that doesn't look like its car's anchors is normally left without an entry tag. Above `0`, a livery match that is closer to another car's anchors by this much similarity or more is tagged as that car instead, still with *Check match* (burst and neighbour matches are never moved). `0.12` was right in 11 of 11 checkable moves on a 3,655-photo rally. It never moves to a car two entries share (it can't say which driver), to a car another box of the photo already has, or to a car other than the ones a number read of 0.90 or more, or a tag you applied, names in the same burst. `0`: never moved | number, 0 to 1 | `0` | no |
| `order_weight` | how closely the cars pass in number order: `0` is random (the neighbour aid is off), `1` is strictly in order. Above 0, groups shot just before and after a doubtful read help identify it, including unselected photos in the same film rolls already tagged with an entry; from `0.5` up an unsupported doubtful read is flagged *Check order*; see [How it works](#how-it-works) | number, 0 to 1 | `0` | yes |
| `neighbour_tolerance` | the most places apart in the sorted number list a neighbouring car can be and still support a read; `order_weight` sets how much of it is used (up to `order_weight × (tolerance + 1)` places) | whole number, 0 or more | `5` | yes |
| `min_read` | how sure a number read must be to count. A read's confidence is the lower of two scores: how sure the text detector is that it found text, and how sure the reader is of its least certain digit. Raise it if plates or signs get read as numbers; lower it if clear numbers are missed | number, 0 to 1 | `0.85` | yes |
| `colour_weight` | how much the colour histogram counts in livery matching, from `0` (off) up. Separate from the Colour family | number, 0 or more | `0` | yes |
| `partial_references` | **Add tagged images** also accepts a solo shot tagged only to team level (e.g. `Assisted Tagging\|Motorsport\|Team\|Red Bull`) and saves it as a team reference under `refs/@team@…`. When no driver is clear but one team's references lead clearly, the result is *team* (shared tags only) | `true`, `false` | `false` | yes |
| `min_sim` | people collections: the least face similarity that counts as a match | number, above 0 up to 1 | `0.5` | no |
| `margin` | people collections: how far the best face match must lead the runner-up | number, 0 up to but not including 1 | `0.05` | no |
| `min_face_px` | people collections: the smallest face, in pixels, that is used | whole number, 1 or more | `48` | no |
| `burst_livery_pooling` | experimental: resolves a burst frame that didn't clear the threshold from the burst's pooled livery similarity (*By pooled burst*). Only a clear pooled match names a car, never a team tie; a burst with a frame read as another car is left alone, and so is a frame whose main box is overlapped, already identified, a team result for another team, or under a tag or sponsor hint that leaves the car out. A frame whose colour read differs from the pooled car's colour is left out of the pool and the fill; the rest are pooled again without it | `true`, `false` | `false` | no |
| `blur_references` | blurs reference crops before they are compared | `true`, `false` | `false` | no |
| `number_gate` | experimental: skips the number read on a box where SigLIP 2 sees no number (see [Number gate](#number-gate-experimental-siglip-2)); does nothing without SigLIP 2 | `true`, `false` | `false` | no |
| `family_colour`, `family_number`, `family_team`, `family_driver`, `family_co_driver`, `family_extra`, `family_vehicle`, `family_sponsor` | write that [tag family](#tag-families); `family_colour` also reads each car's paintwork colour, and turning it on re-reads every photo once | `true`, `false` | `true` (`family_sponsor`: `false`) | yes |
| `family_colour_root`, `family_number_root`, `family_team_root`, `family_driver_root`, `family_co_driver_root`, `family_extra_root`, `family_vehicle_root`, `family_sponsor_root` | the root each family's tags sit under | a tag path | see [Tag families](#tag-families) | yes |
| `tag_number`, `tag_number_name` | write the *By number* diagnostic; the tag it writes | `true`/`false`; a tag name | `true`; `Assisted Tagging\|Identification\|By number` | yes |
| `tag_livery`, `tag_livery_name` | *By livery* | same | `true`; `Assisted Tagging\|Identification\|By livery` | yes |
| `tag_burst`, `tag_burst_name` | *By burst* | same | `true`; `Assisted Tagging\|Identification\|By burst` | yes |
| `tag_pooled`, `tag_pooled_name` | *By pooled burst* | same | `true`; `Assisted Tagging\|Identification\|By pooled burst` | yes |
| `tag_neighbour`, `tag_neighbour_name` | *By neighbour* | same | `true`; `Assisted Tagging\|Identification\|By neighbour` | yes |
| `tag_check_order`, `tag_check_order_name` | *Check order* | same | `true`; `Assisted Tagging\|Identification\|Check order` | yes |
| `tag_team`, `tag_team_name` | *Team only* | same | `true`; `Assisted Tagging\|Identification\|Team only` | yes |
| `tag_none`, `tag_none_name` | *Unidentified* | same | `true`; `Assisted Tagging\|Identification\|Unidentified` | yes |
| `tag_number_seen`, `tag_number_seen_name` | *Number seen* (the digits are added as a leaf) | same | `true`; `Assisted Tagging\|Identification\|Number seen` | yes |
| `tag_check_colour`, `tag_check_colour_name` | *Check colour* (needs the Colour family) | same | `true`; `Assisted Tagging\|Identification\|Check colour` | yes |
| `tag_check_match`, `tag_check_match_name` | *Check match*: a livery, burst or neighbour match unlike its car's anchors, left without an entry tag (or tagged as the closer car, see `closer_car_margin`). A burst match is not checked when a number read of 0.90 or more, or a tag you applied, names that car in the same burst | same | `true`; `Assisted Tagging\|Identification\|Check match` | yes |
| `tag_shot`, `tag_shot_name` | the *Shot* tag (`Solo` or `Pack` is added as a leaf) | same | `true`; `Assisted Tagging\|Identification\|Shot` | yes |
| `tag_shot_crowded`, `tag_shot_crowded_name` | *Shot crowded* (leaf `Crowded`) | same | `true`; `Assisted Tagging\|Identification\|Shot`, the same base as `tag_shot_name` | yes |

A `tag_<key>_name` can't be blank or contain `,`, `;` or `"`; to stop writing a diagnostic, set its `tag_<key>` to `false`. An old `rules.diagnostics.<key>` in `entries.json` is copied here once (`""` becomes `tag_<key>: false`) and logged as deprecated.

#### Renaming tags

To rename a diagnostic tag for one collection:

1. In the panel, open **4 tags written**.
2. Type the new base name in the text box under the diagnostic's switch (it shows the default name as a placeholder; blank means the default).
3. Choose **actions** → **update preset**.

The next run writes the new name. `settings.json` ends up with, for example:

```json
"tag_number_seen_name": "Cars|Number seen",
"tag_shot_name": "Cars|Framing"
```

Tags written under the old name stay on images the run doesn't touch; darktable keeps the old name in its tag list until you delete it.

#### Checking what it will tag

Click **Show tag plan** in the panel. It writes `tag-plan.txt` next to the collection's `entries.json` and opens it in your system's app for .txt files, listing exactly what each outcome writes: every entry's tags and reference count, the team-only tags for each pair of teammates, the unidentified tags (headed `unidentified tags (yours)`), and the diagnostic tags. It also lists entries that can only be identified by number, and entries that can't be identified at all until they have references. The file is rewritten on every run and **Reload**, so it always matches `entries.json`.

After editing `entries.json`, click **Reload** in the panel. A mistake in the file stops the run with the file name and what's wrong.

### Building references

Numbers aren't readable in every shot (rear views, motion blur, a number hidden by the halo), so each entry also needs a few **reference samples**: crops of that car the plugin compares new photos against. 3–5 per car from different angles is a good start; add more for the angles it gets wrong. **new collection → From tagged images** already does this for the images it was given; add more at any time with the panel's **6 references** page:

- **Add as reference**: pick the entry in the **entry** list, select photos of that car, click. Each photo saves one vehicle under that entry: the one whose number reads as the entry's, else the largest the [box check](#box-check-and-colour-reader-optional-siglip-2) keeps, else the largest. The log names which (`number read`, `largest car`, `largest box`). A photo where no vehicle is found saves nothing, and the done message says how many.
- **Add tagged images**: select photos you've already tagged by hand. Each one carrying *all* of one entry's tags is added under that entry. Only your own tags count: tags the plugin wrote (its ledger) never make a photo a reference, so selecting a whole collection is safe. A photo with only a shared team tag, or with two drivers' tags, is skipped.
- **Add from last run**: select photos from the last **Identify selection** run. Each vehicle whose number that run read is saved under the entry it found. This works for pack shots: the saved crop is that one car, not the whole photo, so the entry's tag doesn't have to describe the frame. Burst, team-only and held-back results are never saved. Photos changed since the run are skipped.
- **Fill entry colours** (needs the **Colour** family on, page 4): select photos that already carry one entry's tags, click. Each car's paintwork colour is read and written as that entry's `colour` in `entries.json` when it has none; no reference is saved. The entry's selected photos vote: the colour most of them read is written when it and the colours near it (listed under **Colour tags** in How it works) are two thirds of the reads, so one burst in odd light can't set it; a tie writes nothing. A colour tag you applied to the photo is used instead of the reading and replaces a colour the entry already has, so to correct a wrong entry colour, tag one photo of that car with the right colour and click. The entry tags Identify wrote name the entry as well as yours, so check the photos really show that car. Without a colour tag of yours, the colour tags Identify wrote stand in for it when at least 3 of the entry's selected photos carry the leading colour or one near it and they are two thirds of its colour-tagged selected photos (photos tagged Check colour don't count): select a run of photos of one car that Identify tagged with the right colour and click. The log names the count per entry. A reading on its own never replaces a stored colour: the log names each one that differs. The done message counts the entries set, those that already had that colour and the images where no car or colour could be read, and names the file. A photo that lacks some of an entry's tags still counts when its number, driver or co-driver tag names one entry. A photo whose tags match no single entry is skipped, and the log says which entry is nearest and which of its tags the photo lacks.
- **Entry colour** (**Colour** family on): the three add actions above also fill an entry's missing `colour` in `entries.json` from the one colour tag you applied by hand to the photo, else from the plugin's reading of the saved car. An entry that already has a different colour is never overwritten; the log says so and the done message counts it. `entries.json.bak` keeps the previous file. A file not laid out one entry per line is rewritten that way. The reference job's result rows are `id,status,colour_note,entry_id`.
- **Add-time screening** (vehicle collections): after saving, both reference actions run the audit's mislabel, copy, outlier, colour and crop checks on the new refs. **Add confident vehicles** does not save a box that 2+ checks flag (the log names them; the summary counts them as not saved). **Add references** keeps the ref but logs the flags, since you named the car. Entries with too few refs for a check pass it, and the whole-frame and attractor checks don't run at add time.
- **Audit references**: needs no selected photos. Refreshes the collection's `index.npz` from `refs/` (deleted or moved crops drop out, new ones are embedded), then writes `ref-audit.txt` in the collection folder. Sections: *strongest candidates* (refs flagged by two or more of the checks below; start there), *mislabel suspects* (closer to another entry's refs than its own by 0.2 or more), *cross-entry copies* (near-identical crop filed under two entries), *outliers* (far from the rest of its entry), *odd crops* (crop size or shape far from the entry's usual: a distant car, a whole frame, a nose-only cut; unusual angles are not flagged by this one), *whole frames* (the vehicle detector finds no car in the ref, or one under 15% of it, so scenery drives its matches; re-crop or delete), *attractors* (correctly filed refs that are the closest match for three or more refs of other teams' entries, so an odd angle or size pulls other cars toward them; teammates' pulls are shown but not counted), *colour outliers* (livery hue and saturation unlike the entry's typical colours from the same event, brightness ignored; refs are grouped into events by filename id, where ids more than 1000 apart are different race weekends, and the event ranges are printed at the top of the report; `looks like [entry]` names a better colour match) and *redundant* (near-duplicates within an entry) and *duplicate groups* (near-identical crops with their similarity; many are burst frames of the same car and fine to keep, so judge by eye). The whole-frame check also fires when the detector misses a dark or blurred car (tight crops often do), so look before deleting; refs with no car found are listed but don't count toward *strongest candidates*. The report shows the first 40 per section and every whole frame is in `ref-audit-frames.txt`. Each ref's car share is cached in `frame-share-cache.json`, so only the first audit is slow (about 8 minutes for 2000 refs, then seconds). Starting another action while one runs queues it; cancelling drops the queue. Two panel checkboxes above the button, both off by default: **Audit: suggest re-crops** also writes re-cut copies of wide refs where the detector found exactly one car into `ref-audit-crops/<entry>/` for you to review and copy over the ref (nothing in `refs/` changes; the first run with it ticked re-detects every ref, about 8 minutes), and **Audit: quarantine poor refs** moves the refs flagged by 2+ checks into `refs-quarantine/<entry>/` after the report is written, listing each in `moved.txt` there, then refreshes `index.npz`. To undo, copy a file back into `refs/<entry>/` and re-run the audit. On a terminal: `--suggest-crops` and `--quarantine`. The audit never moves or deletes anything: check the listed crops, then delete or move them yourself. Entries with 4 to 5 or more refs are needed for the outlier checks. It also runs from a terminal: `python python/audit_refs.py COLLECTION_DIR` (embedding, colour and crop checks only, no index refresh; add `--detector path/to/yolox.onnx` for the whole-frame check). The run log is rewritten, so audit before reading an Identify log.

Each sample is a JPG in `refs/<entry id>/`, named after the darktable image id. Adding the same photo again replaces its sample. A selected RAW whose JPEG is also in darktable (same folder, same name before the extension) is read from the JPEG, so the sample is named after the JPEG's id; its entry still comes from the tags on the photo you selected. **Add confident vehicles** swaps a RAW for its JPEG the same way, since Identify recorded the JPEG's vehicles. To remove a bad sample, delete its JPG; the next run notices.

### Identifying

In lighttable, select a batch and click **Identify selection** in the **Assisted Tagging** panel. Progress shows in darktable's message area; click the button again to cancel. A cancelled run changes no tags.

Every vehicle that gets an entry adds that entry's tags to the image, so a photo of two cars battling gets both; the collection's [rules](#rules) decide what team-only and unidentified images get. Images also get a tag saying how they were identified. These are the default names; [`settings.json`](#collection-settings-settingsjson) can rename each one per collection (see [Renaming tags](#renaming-tags)), and the switches under **tags written** [turn each one off](#choosing-which-diagnostics-are-written):

| Tag | Meaning |
|---|---|
| `Assisted Tagging\|Identification\|By number` | its race number was read |
| `Assisted Tagging\|Identification\|By livery` | matched against reference samples |
| `Assisted Tagging\|Identification\|By burst` | the rest of its burst agreed on one entry |
| `Assisted Tagging\|Identification\|By pooled burst` | the experimental `burst_livery_pooling` rule resolved it from its burst's pooled livery similarity |
| `Assisted Tagging\|Identification\|By neighbour` | a doubtful number read was settled by the groups shot just before and after (needs `order_weight` above 0) |
| `Assisted Tagging\|Identification\|Check order` | a low-confidence number read that no neighbouring group supports; the entry tag stays. Delete the tag once checked |
| `Assisted Tagging\|Identification\|Check colour` | a number read whose entry's `colour` differs from the car's paintwork colour (needs the Colour family); the entry tag stays. Delete the tag once checked |
| `Assisted Tagging\|Identification\|Team only` | two teammates were too close to call; only their shared tags were added |
| `Assisted Tagging\|Identification\|Unidentified` | no vehicle, or no confident match |
| `Assisted Tagging\|Identification\|Number seen\|<digits>` | OCR read these digits but they didn't resolve to one entry; added alongside the outcome tag |
| `Assisted Tagging\|Motorsport\|Sponsor\|<Word>` | a listed sponsor word OCR read on the car (Sponsor family, off by default) |
| `Assisted Tagging\|Motorsport\|Colour\|<name>` | the car's paintwork colour (`Red`, `Orange`, `Yellow`, `Green`, `Blue`, `Purple`, `Pink`, `Brown`, `White`, `Grey`, `Black`, or `Multi` for a two-tone car; silver reads as `Grey`; read by SigLIP 2 when it is installed, else by hue rules, see [Box check and colour reader](#box-check-and-colour-reader-optional-siglip-2)); the Colour family, under `family_colour_root`. Filter on it to hand-sort cars by colour |
| `Assisted Tagging\|Identification\|Shot\|Solo` | one vehicle was found in the frame |
| `Assisted Tagging\|Identification\|Shot\|Pack` | two or three vehicles were found |
| `Assisted Tagging\|Identification\|Shot\|Crowded` | the detector's limit (`MAX_BOXES`) was reached, so there may be more cars than were identified |

#### Choosing which diagnostics are written

Each row above has its own switch under **tags written** in the panel, saved in the collection's `settings.json` and all on by default (`Shot` is one switch for `Solo` and `Pack`; `Shot crowded` has its own). Each switch's tooltip names the tag it writes under this collection's settings. Turn off the ones you don't use to keep darktable's tag list short:

- **Off** = the next run stops writing that diagnostic and removes it from the images it processes, under whatever name the collection's settings give it. One never written never shows up in the tag list.
- **Identification doesn't change.** Entry tags, team-only and unidentified tags from `entries.json` are still written.
- Images outside the run keep their old diagnostics. darktable keeps tag names nobody uses any more in its tag list; delete them in the tagging module's dictionary.

Filter on `Assisted Tagging|Identification|By livery` and `Assisted Tagging|Identification|Unidentified` in the **collections** module to spot-check the uncertain ones; an image it got wrong is often a good new reference.

Tick **Tag each run** in the panel to also stamp every image a run writes with `Assisted Tagging|Run|YYYY-MM-DD HH:MM`, so the latest run's photos can be filtered apart from earlier ones. Stamps are never removed by later runs; delete old ones in darktable's tag manager.

Re-running is safe: each image's entry and diagnostic tags are synced to the new result, so a frame that moves from one driver to another loses the old driver's tags. Tags that aren't in the active collection are never touched.

#### Tags you apply by hand

The plugin keeps a ledger (`assisted_tagging/ledger.csv` in darktable's config directory, lines `<library>,id,tag`) of the tags it attached to each image. `<library>` is a hash of the library file's path, so two libraries that reuse the same image ids keep separate ledger lines (lines from before this column belong to the library in use when they're first read; a library opened with `--library` on the command line isn't visible to the plugin and counts as the configured one). Lines for images removed from the library are dropped whenever the ledger is saved, and a failed save is tried once more before an on-screen error. An entry tag on an image that isn't in its ledger is yours, at any depth (team or driver), and a run never removes it. So a photo you tagged to a team stays that way even when the run can't tell the driver.

**Clear tagging marks** reads the same ledger, so hand-applied tags survive it even when they sit under the plugin's roots.

- A **number, driver or co-driver tag** you applied (such as `Assisted Tagging|Motorsport|Number|4` or `Assisted Tagging|Motorsport|Driver|Norris`; needs that family on) **identifies the car**: the run adds the entry's other tags and counts the image as *by your tag*. A solo shot read as a different car is held back as a conflict. A driver or co-driver name two entries share, or tags naming two different entries, identify no car; the log says so and the tags stay.
- A hand-tagged frame also supports its burst and the frames shot around it, like a confident number read.
- Hand-applied family tags (number, driver, team, colour), listed in `entries.json` or not, are never removed unless **Replace manual tags** is ticked.
- A **solo shot** whose result disagrees with the tags you applied is left as you had it: nothing is added, it doesn't get the *Unidentified* tags, and the done message counts it. Packs aren't checked, since you may have tagged just one of the cars.
- A **team tag** you applied (an entry's Team family tag, such as `Assisted Tagging|Motorsport|Team|Red Bull`; needs the Team family on) is a **hint** on a solo shot: matching is limited to the entries under it. If none of them looks similar enough, or the number read belongs to a car outside it, the hint is dropped and the normal match runs. The report lists each hint and any that were dropped. Packs get no tag hints, since the tag may describe only one car. Untick **Use team tags as hints** in the panel to ignore team tags instead: matching isn't narrowed, and a differing result is not held back as a conflict, so the run can override your team tag. The tag itself stays on the image beside whatever the run adds (tick **Replace manual tags** too to have the run overwrite it). Driver-level tags still protect their images either way.
- An image already carrying all of one entry's tags is **skipped** without being analysed.
- To let a run replace your tags, tick **Replace manual tags** under **Identify selection**. It stays ticked across runs and restarts until you untick it.
- If you remove a tag the plugin attached and later apply it again by hand, it counts as yours.
- After you rename or remove an entry, the next run over those images takes off the old tags the plugin attached. This covers tags under the collection's own top-level tags (e.g. `Motorsport|…`), so tags another collection attached stay.
- Images tagged by an older version have no ledger, so all their entry tags count as yours.
- A colour tag you apply by hand is never removed by a run; only the colour tag the plugin attached is replaced. The same goes for a diagnostic, *Unidentified* or *Number seen* tag you applied by hand: it stays (the identifier is not told about it, so it never reads as an entry tag).

**After culling.** To tag only the keepers, collect by the tag `Assisted Culling|Keeper` in darktable's collections module, select them and click **Identify selection**. Consensus then runs over the keepers alone, so expect more *By livery* and *Unidentified* results; re-run on the full burst to fill them in.

## Presets

In Assisted Tagging each collection is a preset: the **preset** picker at the top of the panel lists your collections, and a collection's panel settings live in its folder as `settings.json`, beside `entries.json`.

- **preset**: `template` first, then every collection folder with an `entries.json`, by name. Picking one loads its entries and its settings. The panel opens on the last one you picked.
- **template**: the built-in defaults. It shows only the **new collection** controls; pick a collection to identify. A collection can't be named `template`.
- **actions** beside it: **update preset "<name>"** saves the panel's settings into the collection's `settings.json`; **rename preset…** renames the collection folder (type the name, then **OK**); **delete preset** asks first, then deletes `settings.json` only, never the folder, `entries.json` or the references, so the collection goes back to the defaults. **store new preset…** copies the selected collection to a new folder (entries, references and all) with the panel's settings: type the name, **OK**, then it shows how many reference crops and MB it will copy and waits for **Store**. It is refused on **template** and while a run is going. Empty new collections still come from the **new collection** controls.
- **unsaved changes** shows under the picker when the panel differs from the saved settings. Switching collections drops them. Text fields have no change signal, so their edits show when **actions** is opened or a run starts.
- Every run and reference action uses the settings the panel shows, whether or not you clicked **update preset**: the action writes them to a temporary settings file for that job. **unsaved changes** only means the panel differs from `settings.json`; it never means a run will use older values.
- A new collection has no `settings.json` and uses the defaults until its first **update preset**. A setting missing from the file uses its default; **update preset** writes every setting. A value that's no longer valid uses the default and logs one line naming the collection and setting.
- A `settings.json` that can't be read or parsed: the panel says so, names the file, and keeps its current values. The plugin never rewrites a broken file; fix or delete it.
- While a run is going (or queued), switching, renaming and deleting are refused until it finishes.

## Panel options

At the top: the **preset** picker and **actions** (see [Presets](#presets)), and **Reload**, which rereads the collections folder and the active collection's `entries.json` and `settings.json`. On `template` the panel shows only **new collection**. On a collection it shows **Open entries.json** and **Open settings.json** (see [1 collection](#1-collection)), then the page buttons **1 collection ▸**, **2 bursts ▸**, **3 matching ▸**, **4 tags written ▸**, **5 run ▸** and **6 references ▸**: clicking one opens its contents below it (its label ends in **▾**) and folds the others; clicking the open one folds it. The open page is remembered across restarts. darktable's reset button (↺ in the panel header) puts every setting back to the template defaults.

### new collection

- **Name** (text field, e.g. `F1 2026`). The folder name for a new collection.
- **From tagged images.** Builds the collection from the selected images' tags (see [From already-tagged images](#from-already-tagged-images-recommended)).
- **example**, **View example**, **From example.** Pick a shipped example, open its `entries.json`, or copy it into a new collection (see [From an example](#from-an-example)).

### 1 collection

- **Show tag plan.** Writes `tag-plan.txt` and opens it (see [Checking what it will tag](#checking-what-it-will-tag)).
- **Open entries.json.** In the top area, above the page buttons, so it shows whichever page is open. It opens the collection's `entries.json` in the app your system uses for `.json` files; save it there, then click **Reload**. If the file can't be opened, the message names its path.
- **Open settings.json.** Beside **Open entries.json**, the same way for the collection's `settings.json`: for a hand edit such as deleting a removed setting (see [Coming from `tag_prefix`](#tag-families)). Click **Reload** after saving; unsaved panel changes are replaced. A collection whose settings were never saved has no `settings.json`, and the message names the path.
- **start list** → **Import start list.** Adds a start list to the collection's `entries.json` without typing the entries. Two tabs pick the source, and the import reads the open one. **CSV file:** choose a CSV with a header row (number, driver, co-driver, team, class, make, model, shares car with, paddock; any other columns are ignored). **paste text:** paste the text copied from a PDF entry list, one entry per line with the number first (`12 Smith / Jones`). On the CSV tab, choosing the file fills one picker per role (number, driver, co-driver, team, class, make, model, shares car with, paddock) with its headers, preset to the usual names; change any that guessed wrong, or set it to **(none)**. Only `number` is required. With co-driver on (none), a driver cell holding both crew (`Smith / Jones`) is split. Each entry becomes `{"id": "<number>", "number": "<number>", "name": "<driver>", "co_driver": "<co-driver>", "team": "<team>", "extra": "<class>", "make": "<make>", "model": "<model>", "paddock": "<paddock>"}`, with the empty fields left out; a model needs a make. The [Class and Vehicle families](#tag-families) write the tags. A double-driven car: a **Shares Car With** column (role `shares-car`) names the other entry in the same car; both rows must name each other, and the higher number gets `"car": "<lower number>"`, so every photo of that car gets both entries' tags. Demonstration runs: a row whose **Class** starts with "Demo" gets its **Paddock** value as id (`{"id": "A11", "number": "14"}`; spaces dropped, so `Office 1` is `Office1`), so demo 14 and race car 14 are separate entries and its refs live in `refs/A11/`; it still gets the Number tag `14`. A demo row with no paddock stops the import, and the paste tab has no paddock, so demo rows need the CSV. An entry already in the file as `14` or `D14` with the same driver is renamed to its paddock id, and its refs folder, `refs/sources.json` records and any `car` naming it follow. Other ids already in the file, and race numbers another race entry holds, are kept and listed in the message, the previous file is saved as `entries.json.bak`, and the lists reload. A file not in the one-entry-per-line layout is rewritten that way. Same thing from a shell: `python python/import_start_list.py <collection folder> --csv start.csv [--columns "number=No."]` or `--text pasted.txt`; `--columns "team="` leaves a role out, and `--csv start.csv --header` prints the headers and their guessed roles.
- **Find new entries** → **Add ticked to entries.json.** Adds the cars and fields the photos show but `entries.json` lacks:
  1. Select photos and click **Find new entries**. It lists each number read (`Number seen`) or tagged by hand under the number root that no entry has, and each team, driver or co-driver you tagged by hand on a photo whose number names an entry with that field empty, most photos first. An entry imported before co-drivers had their own field, whose `name` is still `Smith / Jones` with no `co_driver`, gets a **split** row: `12: split "Smith / Jones" → driver Smith, co-driver Jones`. A name with more than one ` / ` or an empty half gets none.
  2. Tick the rows to add. Nothing unticked is added, and one team, driver or co-driver per entry may be ticked; a split can't be ticked with a driver or co-driver for the same entry.
  3. Click **Add ticked to entries.json**. New numbers become `{"id": "<n>", "number": "<n>"}`, teams, drivers and co-drivers fill their entry, and a split sets `name` to the driver and `co_driver` to the co-driver; the previous file is saved as `entries.json.bak` and the lists reload. If the file changed since the list was made (a number already added, a field already set), nothing is written and the reason is shown.
  4. Photos that read an added number get its number tag in place of `Number seen|<n>`, as the plugin's own tag; hand-tagged photos keep their tags. After a split, the next Identify writes the driver and co-driver tags; the old `Driver|Smith / Jones` tag on photos tagged before stays until you delete it. Same thing from a shell: `python python/entries_file.py add <entries.json> <additions.csv>`, rows `number,<n>`, `split,<entry id>` and `field,<entry id>,<team|name|co_driver>,<value>`.

### 2 bursts

- **grouping support** (Native groups, Grouping tags, None). What the burst step borrows answers from (see [Grouping support](#grouping-support)).
- **Grouping tag node (blank = latest run per photo)** (text field). The tag node in Grouping tags mode.

### 3 matching

- **Use team tags as hints** (on by default). A team tag you applied narrows matching on a solo shot.
- **order weight** (text field, default 0). `order_weight` in `settings.json`: a number from 0 to 1, where 0 turns the neighbour aid off. Anything else is refused.
- **neighbour tolerance** (text field, default 5). The most places apart in the sorted number list a neighbouring car can be and still support a read; `order_weight` sets how much of it is used (up to `order_weight × (tolerance + 1)` places). A whole number, 0 or more (anything else refuses the run). Only used when `order_weight` is above 0.

### 4 tags written

First the four [tag families](#tag-families): a switch each, with its root beside it (blank means the default root). Then one switch per diagnostic (default on), each on one line with the tag name it writes beside it, under two headings: **checks** (`Check order`, `Unidentified (check)`, `Check colour`, `Shot`, `Shot crowded`) and **how it decided** (`By number`, `By livery`, `By burst`, `By pooled burst`, `By neighbour`, `Team only`, `Number seen`). Off removes that diagnostic on the next run; see [Choosing which diagnostics are written](#choosing-which-diagnostics-are-written). A switch whose tag needs another setting shows why it is off in its label, e.g. `Check colour (off: the Colour family is off)`, and is greyed until that setting is on. A `settings.json` from before *Shot crowded* existed loads with `tag_shot_crowded` and `tag_shot_crowded_name` copied from the Shot switch, once, and the log says so.

### 5 run

- **Replace manual tags.** Lets runs replace tags you applied by hand; stays ticked until you untick it (see [Tags you apply by hand](#tags-you-apply-by-hand)).
- **Tag each run.** Stamps every image a run writes with `Assisted Tagging|Run|YYYY-MM-DD HH:MM`.
- **Verify selection.** Identifies the selection, fully tagged images included, and reports where the result differs from your tags. No tags change.
The page has three groups: **identify** (models; writes tags), **derive** (lookups only; adds tags) and **undo**.

- **Identify selection.** Identifies and tags the selection (see [Identifying](#identifying)). Click again to cancel. When a box's colour is read and no number is, only entries whose colour can match are compared. The filter is dropped when a confident number names an entry of another colour, or when no remaining entry is similar enough, so colour alone never identifies a car. Writes darktable tags, the tag ledger, `boxes.json` and the report; never `entries.json`.
- **Derive from number.** For each image whose number tag you applied names exactly one entry, adds that entry's tags. No models run; plugin-written number tags don't count. Writes darktable tags and the tag ledger only.
- **Derive from colour.** For each image with one colour tag and no number tag, adds the tags of the one entry with that colour (your team tags narrow it). Skipped when several entries share the colour. Writes darktable tags and the tag ledger only.
- Both Derive buttons only add tags, log why each skipped image was skipped, and add **Check colour** when your number tag's entry and the colour tag disagree. Each tag source is marked `Assisted Tagging|Derived|From number`, `From driver`, `From colour` or `From identification` (option **Derived from** in 4 tags written). A later Identify run replaces Derive's markers with its own.
- **Clear tagging marks.** Removes every tag the ledger says the plugin attached to the selected images (entries, colours, diagnostics, unidentified), from any collection, and forgets those images in the ledger, so a later **Identify selection** treats them as fresh. The ledger alone decides: tags you applied by hand stay, even under the plugin's roots, and so do **Tag each run** stamps, which are not ledgered. Images with no ledger row are left alone.

### 6 references

The page has three sections. Only the first uses the **entry** list.

- **add to one entry**: **entry** (the entry **Add as reference** saves under) and **Add as reference**.
- **add by tags or last run**: **Add tagged images**, **Fill entry colours**, **Add from last run.** Each finds the entry from the image's tags or the last run; the **entry** list is not used.
- **audit**: **Audit: suggest re-crops**, **Audit: quarantine poor refs** (both off by default), **Audit references.** See **Audit references** under [Building references](#building-references).

See [Building references](#building-references) for each action. The three add actions also fill the entry's colour in `entries.json` when the **Colour** family is on, and a colour tag you applied replaces the stored one.

Everything in pages 2 to 6 except **Replace manual tags** is saved with the collection by **update preset**. **Replace manual tags** is saved in darktable's preferences instead, so it carries across collections and restarts.

## Preferences

All under **preferences → lua options**. Everything else is a collection setting, see [Presets](#presets).

| Preference | Default | What it does |
|---|---|---|
| plugins folder (`assisted_plugins/plugins_root`) | empty (auto-detect) | The folder holding the assisted-* repos; this plugin uses `<plugins folder>/darktable-assisted-tagging`, where `python/`, `models/`, `examples/` and `.venv` are found. The old `assisted_tagging/plugin_folder` (this repo's folder) is still read and logged as deprecated |
| Assisted Tagging: collections folder | empty (`assisted_tagging/collections` in the config directory) | Where collections live |

## How it works

```
assisted_tagging.lua groups the selection by Grouping support (native, tags or none), writes manifest.csv, runs identify.py
        |
        v
identify.py, per frame:  fast small decode → YOLOX vehicle boxes (up to 4)
        |                → full-resolution decode, only when a box passes
        |                → per box: crop (EfficientSAM mask when boxes overlap)
        |                → read numbers → DINOv2 embedding         (all cached)
        |                no vehicle found → a weaker candidate box that looks like a
        |                group mate's car is kept (rescue)
        v
noise numbers: a number read (min read or surer) beside 3 different start-list numbers across the
           run, and beside one in most of the boxes that read it, is on many cars (a class number,
           a sponsor's digits): it is left out of every box that has another read, and kept where
           it is the only read. The log lists them
        |
        v
match, pass 1, per box:  sponsor words on the car (or a team tag you applied) narrow the candidates to one team, then
           every start-list number scored against the reader's digit
           probabilities (reads down to 0.7 sure, not just min read);
           a clear winner matching one entry → number
           (a close call skips straight to livery; a reader with no
           probabilities: one number read matches one entry → number)
           else best livery match clear of the next one → livery
           else best two are teammates                  → team (shared tags only)
           else                                         → none
        |
        v
hires re-read: boxes still unidentified are read again from a half-size RAW decode → match, pass 2
        |
        v
weak reads: the start-list scores of a group's unidentified boxes (reads at least 0.7 sure) are
           added up across its frames, one box per frame; a total that clears the margin → number
           on each of those boxes, when nothing else in the group names another entry. Boxes with no
           digit probabilities (an older cache): 2+ frames reading the same number → number
        |
        v
neighbour aid (only when order weight > 0), against the 3 groups shot before and after (at most 20 seconds from one group's last frame to the next one's first),
taken from the selection and from unselected photos in the same film rolls that already carry an entry's tags
(those only lend support for number order, never a look-alike, and are never tagged):
           a misread or unmatched number near a nearby entry in the list → neighbour (order)
           a box with no number read that looks like a nearby identified car → neighbour (look-alike)
           unsupported low-confidence read → "Check order" tag
           Colour family on (`family_colour`): the box's paintwork colour breaks ties; see below
        |
        v
per group: frames with nothing identified take the group's entry when
           it is anchored by number, livery or neighbour results,
           2+ frames agree on it (or one number read is 0.95+ sure),
           none disagree, and it covers at least half the group → burst
           frames where no vehicle was found are filled too (box -1);
           frames that errored or were skipped never are
           (experimental: pool livery similarity across the burst → pooled)
        |
        v
assisted_tagging.lua reads results.csv and syncs tags
```

Each outcome above is one of these methods, named consistently from `identify.py`'s `method` field through to the diagnostic tag it writes (see [Rules](#rules) to rename or drop one):

| Method | Decided by | Diagnostic tag |
|---|---|---|
| `number` | OCR reading an entry's `number` | `…\|By number` |
| `livery` | the DINOv2 embedding, against reference samples | `…\|By livery` |
| `neighbour` | the groups shot before and after: a number that was misread or didn't match, or a box with no number that looks like a nearby car (needs `order_weight`) | `…\|By neighbour` |
| `burst` | the rest of the burst agreeing, when number and livery didn't | `…\|By burst` |
| `pooled` | the burst's pooled livery similarity (experimental `burst_livery_pooling` rule) | `…\|By pooled burst` |
| `team` | two teammates too close to call by livery (shared tags only) | `…\|Team only` |
| `none` | nothing matched | `…\|Unidentified` |

Frames are decoded at native resolution (a raw file's embedded preview) and each vehicle is cropped from that before reading its number, since a number only a few pixels tall in a downscaled frame is readable in the crop. OCR text and embeddings are cached per frame in `assisted_tagging/cache.sqlite` in darktable's config directory, and vehicle detections in the shared detection cache below. Matching isn't, so adding references or editing `entries.json` takes effect on the next run without decoding anything again. The cache key includes the file (path, modified time, size), every model file and a fingerprint of the constants and package versions that change the cached data, so the first run after an update or a constants edit re-reads everything once; unused entries are dropped after 90 days, once at the start of a run. The file is in SQLite's WAL mode, so `cache.sqlite-wal` and `cache.sqlite-shm` sit beside it while a run is open. Delete the file to start over.

**Shared detection cache.** Vehicle boxes are cached in `assisted_plugins/detections.sqlite` in darktable's config directory, shared with the culling plugin so a frame both plugins see is detected once. The key is the file (path, modified time, size), the detector model file and a fingerprint of the shared detector code, so a new detector or a `vehicle_detect.py` change re-detects everything once; rows unused for 90 days are dropped. Delete the file to start over.

**Colour tags.** With the [Colour family](#tag-families) on, each car's paintwork is measured on the middle of its crop (margin, roofline and the lower tyre band are left out) and becomes the palette colour with the largest share. White, grey and black count half, since tarmac, glass and shadow are also in the crop. It is `Multi` when the second colour is close to the first. The decided colour is written as `<family_colour_root>|<name>`. An entry's `colour` is a tie-breaker only, never a filter. A weak number read for an entry whose colour differs from the car's doesn't count towards a group's agreement; the neighbour aid drops candidates whose colour differs and a look-alike car only lends its entry when the colours don't differ; a confident number read is never blocked, but when its entry's colour differs from the car's the image gets *Check colour*. An entry with no `colour`, or a car whose colour can't be told, is neutral. Colours too close to call never count as differing: `Multi` against a single colour, white against grey, grey against black, and the hue neighbours blue/purple, blue/green, red/pink, red/orange, orange/yellow, purple/pink and orange/brown. Turning the family on re-reads every photo once.

**RAW+JPEG pairs are read once, from the JPEG.** A RAW and a JPEG in the same folder with the same name before the extension (case ignored, as darktable pairs them on import) are one shot, and so are darktable duplicates of a file. The JPEG is read: it has the camera's exposure and colour at full size. Every file in the shot gets the same tags, and a hand tag on any of them is protected for the whole shot. A RAW with no JPEG is read from the RAW. Same name in another folder is a separate shot.

### Grouping support

Tagging no longer clusters photos by capture time. Consensus (the "borrow the answer from the rest of the group" step) runs over groups that something else already made, and the panel's **grouping support** combobox picks which:

- **Native groups** (default): darktable's own image groups. A photo's group is its group leader.
- **Grouping tags**: the children of an [Assisted Grouping](../darktable-assisted-grouping/README.md) tag node, e.g. `Assisted Grouping|2026-01-01 12:00:00|Group|NNNN`. The **Grouping tag node (blank = latest run per photo)** entry names the node. Blank uses each photo's own latest Assisted Grouping run, so after regrouping part of a shoot the regrouped photos use the new run and the rest keep the old one. Assisted Grouping must have **Group tags** on, or there is nothing to find. In Native groups mode, if no photo is in a group but grouping tags are present, the log and a notice say to switch to Grouping tags.
- **None**: every photo is its own group, so nothing is borrowed.

A photo with no group (no native group, or no child tag under the node) is its own group. Groups are not size-checked: a coarse group (a long hand-made stack, or Assisted Grouping's Camera or Parent layers) is treated as one car pass, so the missed-detection rescue may carry an identification across the whole group. The log records the mechanism, how many photos landed in groups of 2 or more, and (in Grouping tags mode only) the node used.

A coarse group is your grouping settings at work: if Assisted Grouping's time gap is set high, or its Camera or Parent layers join unrelated shots, consensus can fill an entry across different cars. Tighten the grouping, switch to **None**, or fix the group, rather than expecting tagging to split it.

## Tuning

The thresholds are starting points, not tuned defaults. Each is a named constant:

| Constant | File | Default | What it does |
|---|---|---|---|
| `OCR_MIN_SCORE` | `ocr.py` | 0.80 | how sure the text detector must be before a number is read |
| `NUMBER_MAX_DIGITS` | `ocr.py` | 3 | a text region's runs of digits become number reads up to this length, so `14 RALLYE` and `#7` read as 14 and 7, while a year or phone number on a sticker gives nothing. Look-alikes fold to digits only in a token that is otherwise all digits (`l4` → 14); the start-list check also folds s, b, z and g, but a read's tag keeps the letter |
| `NUMBER_MIN_HEIGHT` | `ocr.py` | 0.07 | a number's text region must be at least this share of the vehicle crop's height, so plate characters and lone sticker letters aren't read as numbers. A first guess: the report's "ocr saw" line shows each region's share (`h0.12`). Raise it if plates still get read; lower it if small but real numbers are dropped |
| `OCR_CROP_DIM` | `ocr.py` | 1600 | the long side of the crop the number reader gets. Text is found on a 736-px copy, then each region is read from this crop, so a small number keeps its detail. A box re-read at higher detail gains from it too |
| `TURN_RETRY_BELOW` | `ocr.py` | 0.85 | a region read less surely than this is read again turned 180°, for a number upside down on a rolled or roof-on car. The run log's `turned reads won` line counts the reads a retry changed |
| `TALL_QUAD` | `ocr.py` | 1.5 | a weak region at least this many times taller than wide is also read turned 90° both ways, for a number on its side |
| `NUMBER_LIST_MARGIN` | `match.py` | 2.3 | every start-list number is scored against the reader's digit-by-digit probabilities (natural log). The best one counts as the number read only when it leads the runner-up by this much (10×); otherwise the box is a close call and goes to livery. The log and the report show greedy read, best and runner-up with their scores, marked `(weak read)` when the read was under min read and `(burst of N)` when a group's summed scores decided (the margin then applies to the totals) |
| `NUMBER_LIST_FLOOR` | `match.py` | 4.6 | the best start-list number must also be within this of what the reader actually spelled (100×), or there is no list read |
| `MATCH_MIN_SIM` | `match.py` | 0.60 | the livery similarity a match needs at all |
| `MATCH_MIN_MARGIN` | `match.py` | 0.10 | how far the best entry must be ahead of the next one. Similarities are centred on the references' mean once a collection has 20+ references, which spreads them out, so the gate is wider than it looks; `python/eval_matching.py` sweeps it on your own references |
| `BURST_MIN_AGREE` | `match.py` | 2 | frames that must agree before a burst fills in the rest |
| `SOLO_ANCHOR_CONF` | `match.py` | 0.95 | a number read this sure fills a burst that names no other entry on its own, however few frames agree |
| `NOISE_MIN_PARTNERS` | `match.py` | 3 | a number read at min read or more in the same box as this many different start-list numbers, counted across the whole run, is a noise number when it also passes `NOISE_MIN_BESIDE_SHARE`: it is on many cars, so it is left out of a box's reads when the box has another (a box that reads only it keeps it). The log's `noise numbers:` line lists each with its count, a box that left one out says `[noise number 3 not used]`, and boxes.json keeps them under `noise_numbers`. Two cars that share a box give each number one partner however often it happens; raise this if real numbers show up in the line |
| `NOISE_MIN_BESIDE_SHARE` | `match.py` | 0.5 | a number is a noise number only when more than this share of the boxes that read it (at min read or more) also read a start-list number. A class number sits beside the car's own number in nearly every box; a real car's number is mostly alone in its box, so a car photographed in a few packs keeps its number. Lower it if a class number that is often the only read stays out of the `noise numbers:` line; raise it if a real number gets in |
| `WEAK_READ_MIN` | `match.py` | 0.7 | the lowest read the start-list scoring takes, alone or summed across a group, below min read |
| `WEAK_AGREE_MIN` | `match.py` | 2 | how many frames of a group must have weak reads before their scores are summed (or, without digit probabilities, agree on one number) |
| `BURST_MIN_CONFIDENCE` | `match.py` | 0.5 | the share of the group the entry must cover before a burst fill is written |
| `LOOKALIKE_MIN_SIM` | `neighbour.py` | 0.85 | how alike a box with no number and a nearby identified car must look for the neighbour look-alike |
| `LOOKALIKE_MARGIN` | `neighbour.py` | 0.05 | how far that car must lead the best-looking other car nearby |
| `CANDIDATE_MIN_SIM` | `neighbour.py` | 0.50 | lowest livery similarity at which an unread box takes its best guess because that car was identified nearby |
| `CANDIDATE_RIVALS` | `neighbour.py` | 3 | that best guess and the next guesses checked; it is only taken when none of the others was nearby |
| `DOUBT_CONF` | `neighbour.py` | 0.90 | a number read below this is doubtful, so the neighbour aid checks it |
| `ACHROMATIC_WEIGHT` | `car_colour.py` | 0.5 | how much a white, grey or black share counts against a colour's. Raise it if coloured cars with a small sponsor patch lose their white, grey or black tag; lower it if tarmac and shadow make coloured cars come out grey or black. Applied at match time, so a change needs no re-read |
| `MULTI_RATIO` | `car_colour.py` | 0.6 | how close the second colour's weighted share must be to the first's for `Multi`. Raise it if too many cars come out `Multi`; lower it if clear two-tone cars get one colour. Applied at match time, so a change needs no re-read |
| `MIN_BOX_FRAC` | `vehicles.py` | 0.005 | the smallest vehicle, as a share of the frame, worth identifying |
| `MAX_BOXES` | `vehicles.py` | 4 | vehicles identified per frame |
| `CROP_DIM` | `vehicles.py` | 640 | the long side each vehicle crop is reduced to for the livery embedding and colour (the number reader's is `OCR_CROP_DIM`) |
| `DETECTOR_MIN_SCORE` | `vehicles.py` | 0.20 | the confidence a vehicle detection needs |

The run log has one line per vehicle with the numbers read and the top two livery matches with their similarity, e.g. `box 0: livery VER (OCR -; livery VER 0.712, TSU 0.694)`. Read a few from a shoot to see where the right and wrong answers fall before changing `MATCH_MIN_SIM` or `MATCH_MIN_MARGIN`.

Editing a constant of a per-frame module (`vehicles.py`, `ocr.py`, `embed.py`, `segment.py`, `overlap.py`, `pod.py`, `colour.py`, `car_colour.py`, `people.py`) or upgrading OpenCV, Pillow, rawpy or numpy changes the fingerprint `fingerprint.py` puts in every cache key, so the next run re-reads every frame by itself. `fingerprint.py` lists each constant as a cache input or as neutral (only used at matching time); `test_identify.py` fails until a new constant is filed. A code-only change to a cached stage needs its token in `frame_key` bumped (`ocr-trace-2`, `pod-2`, `mask-1`, ...) or `cache.sqlite` deleted. Changes to `match.py`, `rescue.py` and `neighbour.py` never need either.

**Higher-detail re-read.** Frames are first analysed from the RAW's embedded preview (fast). After the first match, each box left unidentified (`none`, or `team` with the driver not separated; overlapped boxes excluded) is re-read from a half-size decode of the RAW itself, which gives OCR and the embedding several times the pixels on a small car. Boxes stay in preview coordinates; only their crops come from the sharper decode. Non-RAW files and previews already near full width are left alone. A re-read replaces that box's OCR, embedding and colour only, and the box record carries `"hires": true`. The re-read of a frame is cached separately (`hires-2`, keyed on the frame's box list), so a rerun doesn't decode again, while a box rescued from a burst gets a fresh re-read. Reference crops are still taken from previews.

**Car-shaped masks.** When the segmentation model is present, each box that overlaps another (`overlap.py` geometry, hidden boxes excluded) is outlined by EfficientSAM, prompted with three points on the car body. The crop used for OCR, the embedding and colour has everything outside the outline painted grey. The mask must not contain the centre of an overlapping box and must cover at least 15% of the visible box, otherwise the plain crop is used. The box record carries `"masked": true`. Pod readings and reference crops are unmasked. Having the model adds `mask-1` and the model file to the cache key, so the first run with it, or with a replaced model file, re-reads every frame.

## Troubleshooting

- **The panel isn't there.** Start darktable with `-d lua` and look for `LUA ERROR` in the log. On Windows the log is `Documents\Darktable\darktable-log.txt`.
- **Every run writes a log** to `assisted_tagging.log` in darktable's config directory (e.g. `%LOCALAPPDATA%\darktable` on Windows); the 5 runs before it are kept as `assisted_tagging.prev.log` (the last one), `assisted_tagging.prev2.log` … `assisted_tagging.prev5.log`. Each line is written as it happens, so a crash leaves the last step in the file; each stage logs `started` and `done` with its seconds, and a failed write names its image. It has the exact command, the reference counts per entry, one line per vehicle with what was read and matched, and any per-image errors.
- **"…/entries.json: …"** The run stopped on a mistake in that file; the message says which entry and what's wrong.
- **"… model not found: …"** A model file is missing. Download it into `models/` (see [Install](#2-models)). A job with none of its files installed stops the run with `Assisted Tagging: no <job> model in models/. Install <file> (README, "Models").`
- **"Python is missing a package."** `darktable-assisted-tagging/.venv` doesn't have `requirements.txt` installed; the log names the package.
- **"no collections yet."** Create a folder with an `entries.json` in the collections folder the message names, then click **Reload**.
- **Everything comes back `Unidentified`.** Check the log's `references:` line: an entry with 0 references can only be found by its number. The `entry list:` lines under it, logged before any photo is read, name what in entries.json will cost matches: a number on more than one car (a read of it names neither, so only livery can), entries with no references, and entries with neither a number nor references.
- **"cache … is unreadable".** Delete `assisted_tagging/cache.sqlite` in darktable's config directory; the next run rebuilds it.

## Limitations

Known gaps, not yet fixed:

- **Entries with no references** can only be identified by a readable number.
- **Identical teammates** get only their shared team tag, never a guessed driver.
- **Packs** get no team-tag hints, and are not checked against the tags you applied.
- **Groups are not size-checked.** A coarse group can carry one identification across different cars (see [Grouping support](#grouping-support)).
- **Four vehicles per frame** at most (`MAX_BOXES`); a frame that reaches it gets the *Crowded* tag.
- **Thresholds are starting points**, not tuned defaults (see [Tuning](#tuning)).
- **Reference crops** come from previews, unmasked, even when the run re-read a box at higher detail.
- **Older tags count as yours.** Images tagged before the ledger existed have no ledger rows, so a run never removes their entry tags.
- **The audit's whole-frame check** also fires on dark or blurred cars, and the first audit is slow (about 8 minutes for 2000 refs).
- **Run stamps** from **Tag each run** are never removed by the plugin.

## Acceptance checklist

The darktable side of grouping support, the neighbour aid and the `settings:` log line has not been run in darktable yet. Work through these steps on Windows, in order, and note the result of each. The log is `%LOCALAPPDATA%\darktable\assisted_tagging.log`; each run ends with `run finished`.

**Setup**

1. **Python tests.** In the repo folder: `.venv\Scripts\python python\run_tests.py`. *Expect:* every test passes, including `test_neighbour`, `test_import_numbers`, `test_import_start_list` and `test_identify`.
2. **Install the plugin** as in [Install](#3-darktable-side) and start darktable. *Expect:* an **Assisted Tagging** panel in lighttable showing *new collection* on the `template` preset; on a collection, **Open entries.json**, the page buttons *1 collection ▾* (open, its settings below it) to *6 references ▸*. No `LUA ERROR` in the darktable log.
3. **A collection.** Set the plugins folder preference, then make a collection (from tagged images, or from the `f1-season` example plus a few references). *Expect:* it appears in the **preset** dropdown.

**Grouping support** (one run per mode, on a selection holding a burst)

4. **Native groups.** Put the burst in a darktable group, pick *Native groups*, click **Identify selection**. *Expect:* in the log, `identify started`, then `settings: … grouping support native, node (blank), neighbour tolerance 5`, then `group support native: N of M photos in groups of 2+` with N counting the burst.
5. **Grouping tags, blank node.** Run Assisted Grouping on the selection with **Group tags** on. Back in tagging, pick *Grouping tags*, leave the node blank, run. *Expect:* `group support tags: N of M photos in groups of 2+, latest run per photo (1 runs)`.
6. **Grouping tags, wrong node.** Type a node no selected photo carries, run. *Expect:* `group support tags: 0 of M photos in groups of 2+, node <what you typed> (matches no selected photo)`; every photo is its own group.
7. **None.** Pick *None*, run. *Expect:* `group support none: 0 of M photos in groups of 2+`.

**Neighbour aid and references**

8. **Neighbour aid.** Make a collection from the `rally` example and run on cars shot roughly in number order. *Expect:* `neighbour: resolved N, flagged M (order weight …, tolerance 5)`; frames it settled get *By neighbour*, unsupported low-confidence reads get *Check order*. Set **neighbour tolerance** to 3 and re-run: both the `settings:` and `neighbour:` lines say 3. Then select only a few frames from the middle of an already-tagged run and Identify again. *Expect:* `neighbour: N unselected tagged photos shot near the selection` with N above 0, the same count in `unselected tagged photos lend support`, and no tags changed on the unselected photos.
9. **Zero references.** Run on a collection with no references. *Expect:* `collection … has no references yet: only numbers can identify a car`; the run finishes, and cars with no readable number are *Unidentified*.

**Panel**

10. **Cancel.** Start **Identify selection** on a large selection and click it again. *Expect:* "Assisted Tagging: cancelled, no tags were changed."
11. **No selection.** Clear the selection and click **Identify selection**. *Expect:* "Assisted Tagging: select some images first".
12. **Diagnostic switches.** Identify a batch with every switch on. Under **tags written** in the panel, turn off *Shot* and *By livery*, choose **actions** → **update preset**, then identify the same batch again. *Expect:* the same entry tags as before; no image in the batch has `…|Identification|Shot|…` or `…|By livery`; the other diagnostics are still there. No `LUA ERROR`.
13. **Start list import.** Save a 100-row CSV (`No.;Driver;Co-Driver;Entrant;Class`), choose it under **start list** and click **Import start list**. *Expect:* "added 100 entries to …entries.json"; the entries have `name` (the driver), `co_driver`, `team` and `extra` (the class); `entries.json.bak` is the previous file. Click **Import start list** again. *Expect:* "added 0 entries … skipped 100 already listed: 1, 2, …". Open the **paste text** tab, paste `7 Smith / Jones` and a line without a number, and import. *Expect:* "added 1 entries … 1 line(s) without a leading number ignored" when 7 is new, and the box is cleared. In an `entries.json` copy, set one entry's `name` to `Smith / Jones` with no `co_driver`, select a photo carrying its number tag and click **Find new entries**. *Expect:* a `split "Smith / Jones" → driver Smith, co-driver Jones` row; ticking it and adding gives that entry `"name": "Smith", "co_driver": "Jones"`.

14. **Old settings.** Remove `tag_shot_crowded` and `tag_shot_crowded_name` from a collection's `settings.json` (keep `tag_shot` off), then click **Reload**. *Expect:* the log shows `settings.json: tag_shot_crowded, tag_shot_crowded_name copied from the Shot switch (old settings)`, and *Shot crowded* is off in **4 tags written**.
15. **Clear tagging marks.** Identify a burst, then add `Rally|2026|12` to one image by hand. Select the burst and click **Clear tagging marks**. *Expect:* "Assisted Tagging: cleared N tags from M images."; every tag the plugin attached is gone, the hand tag stays, and a later **Identify selection** treats the images as fresh. Click it again on the same selection. *Expect:* "Assisted Tagging: nothing to clear; the selection has no tagging marks."

### Report what breaks

For each step that doesn't match, send back:

- the step number, and what happened instead (screenshot if it's visual)
- `assisted_tagging.log` from `%LOCALAPPDATA%\darktable` (copy it right after the failing step; the next run moves it to `assisted_tagging.prev.log`)
- any `LUA ERROR` lines from `Documents\Darktable\darktable-log.txt`, with darktable started with `-d lua`

## Development

### Tests

From the repo root. The Python tests use synthetic images and stub models, so they need no model files. `run_tests.py` runs every `python/test_*.py` and the Lua suites `lua/test_assisted_tagging.lua` (the darktable-independent functions) and `lua/test_assisted_gui.lua` (builds the panel and runs the button functions against a fake darktable and a fake identify.py process) (or only the ones named, e.g. `match neighbour assisted_tagging`), prints one summary line each and writes each one's output to `tests/<name>.txt`. The Lua suite uses a `lua` on PATH if there is one, else lupa: run `pip install lupa` in the venv once (Windows has no `lua` by default):

```
# Linux / macOS
.venv/bin/python python/run_tests.py

# Windows
.venv\Scripts\python python\run_tests.py
```

On a Mac or any machine without numpy and OpenCV, the standard-library tests still run (`python python/test_settings.py`, `python python/test_import_numbers.py`), as do the Lua suites; the rest need the venv.

The Lua suite alone: `.venv\Scripts\python python\run_tests.py assisted_tagging` (or `cd lua && lua test_assisted_tagging.lua` with Lua 5.4).

### Running the identifier on its own

`manifest.csv` is `id,filepath,burst_id` per line, with an optional fourth column, the `;`-joined entry tags the user applied by hand (an image carrying all of one entry's are skipped; a solo result sharing none of them is held back as `conflict`). Further optional columns: the fifth is the `;`-joined team tags used as hints, the sixth the capture time in seconds, the seventh the id of the entry the user's own number or driver tag names (results use the method `hand` for it):

```
python python/identify.py manifest.csv results.csv --collections-root collections --collection "F1 2026" \
    --detector models/object_detection_yolox_2022nov.onnx --ocr-det models/text_detection_en_ppocrv3_2023may.onnx \
    --ocr-rec models/en_PP-OCRv5_mobile_rec.onnx --embedder models/dinov2_small.onnx
```

`--ocr-rec` takes the CRNN model too. `--settings PATH` uses that settings file instead of the collection's `settings.json` (the panel passes a temporary one for its runs; `promote_boxes.py`, `audit_refs.py` and the list modes take it too). Set `order_weight` and `neighbour_tolerance` in that file.

`results.csv` gets `id,box,method,entry_id,alt_entry_id,confidence,unmatched_number,shot,order_flag,colour,colour_flag` per vehicle (box −1 for a frame with no vehicle; method `skipped` or `conflict` as above). Exit codes: 0 ok, 2 bad input (the message is on stderr), 3 missing package, 130 cancelled.

`--boxes-out PATH` also writes `boxes.json`, one record per vehicle: `{"collection", "thresholds" ({min_sim, min_margin, ocr_min_score, number_min_height, min_read, weak_read_min, number_list_margin, number_list_floor, noise_min_partners, noise_min_beside_share, number_gate_min}: the values the run used), "noise_numbers" ({digits: how many start-list numbers it was read beside}), "entry_list" (the run's `entry list:` log lines), "sponsor_keywords" ({word: tag prefix}), "entries": {id: {"team", "number", "tags", "camera", "colour", "car", "refs"}}, "images": {id: {"shot", "status" (ok, no_vehicle or error), "file", "frame", "burst", "time" (capture epoch seconds, null if EXIF is missing), "note" (the detector's text when it found no vehicle), "boxes": [{"box", "bbox", "score" (detector confidence), "entry", "alt_entry", "method", "confidence", "candidates" (top 5 entry/similarity), "ocr", "ocr_trace" (the five most confident text regions, [confidence, text, height share of the crop]), "pod" ({yellow, aspect}: the camera-pod reading), "overlap" ("" , "trimmed" when read on the part not covered by a car in front, "hidden" when too little was left to match), "rescued" ({from, sim} when burst rescue found this box, else {}), "decided_by", "gap", "unmatched_number", "conflict", "hint" (prefixes, source, restricted, dropped, reason; {} without one), "order_flag" (a doubtful number read no neighbour supports), "pod_colour", "hires" (read again from the larger decode), "masked" (cropped with a mask), "colour", "colour_shares", "list_read" (the start-list scoring of the read), "read_entry" (the entry the number read alone named), "number_share" (with `number_gate` on: how strongly SigLIP 2 saw a number on the crop, 0 to 1; null where the gate did not look)}], "hand" (the entry your own number or driver tag names), "tagged" (the entry whose tags the photo already carries)}}, "skipped": [ids]}`. With `--verify` each box also has `ocr_regions`, `ocr_ctc` and `sims`, which `eval_numbers.py` replays. For `none` boxes `decided_by` names the rule that failed (`no_references`, `below_min_sim`, `margin_too_small`) and `gap` how far short it fell. The plugin writes it to `last-run/<collection>.boxes.json` in its config directory; `--promote-boxes --boxes-in PATH` (same manifest, `id,filepath,""`) saves its confident boxes as references.

### Debug report

Every run also writes `last-run/<collection>.report.md` and `.report.json` in the plugin's config directory (the path is logged as `report: …` in `assisted_tagging.log`). Each vehicle gets one category: `identified`, `team-obvious` (team clear, driver not separated), `weak-match`, `no-references`, `number-unmatched`, `conflict` (disagrees with a tag you applied), `overlapped` (a car mostly covered by another in a pack: not matched, its visible part was too small), `already-tagged`, `no-vehicle`. The `.md` gives per-category counts and shares, the identified rate, median top-1 similarity and margin for `team-obvious` and `weak-match`, then the worst boxes per category with their candidates, the failing rule and a suggested lever. It has no images, so it pastes into chat as is. `--report-top N` (default 20) caps the boxes listed per category; the `.json` always has every row, each with its `category`. To rebuild a report from a saved `boxes.json` without re-identifying: `python report.py BOXES_JSON OUT_PREFIX --report-top N`. Photos that failed analysis are counted on a separate line, not in a category. Each `no-vehicle` image is listed with its burst and the detector's note (the strongest class and score it saw), which says whether a miss was a low score or a small box. Each box shows its detector score. The summary also lists the run's noise numbers and its `entry list:` findings (the `.json` carries them as `noise_numbers` and `entry_list`), read from `boxes.json`, so a report rebuilt from a `boxes.json` written before them has neither. Three more sections follow the summary (they appear when `--report-top` is above 0, and the `.json` carries them as `detector_bands`, `sponsor_suggestions` and `bursts`): `## detector score` (boxes and identified count per score band, to judge the `DETECTOR_MIN_SCORE` cutoff), `## sponsor keyword suggestions` (words OCR read on identified boxes of one tag prefix that aren't in `rules.sponsor_keywords` yet, with how many unidentified boxes each would hint), and `## bursts` (capture-time gaps within and between the groups the plugin read, per group id). After the categories, `## resolved by pooled burst` lists the frames the experimental `burst_livery_pooling` rule named, weakest first, with the entry each took. `--archive-dir DIR` also copies `boxes.json` and the report into `DIR/<YYYYMMDD-HHMMSS>/` and keeps the newest 20 runs; the plugin passes `runs/` in its config directory, so earlier runs survive for comparison while `last-run/` stays the latest.

### Notes from the darktable source

- **`register_lib` takes eight positional arguments**: `(plugin_name, name, expandable, resetable, containers, widget, view_enter, view_leave)`. Leaving out `resetable` shifts the container table into a boolean slot and the panel never registers.
- **Registering a lib straight from `luarc` is a startup race.** darktable can report lighttable as the current view before the view has finished initialising, and a lib registered in that window is silently never attached (`src/views/view.c` documents it; the lua-scripts hit it as #19197). The plugin installs its panel from the `view-changed` event into lighttable instead, which fires only once the view is fully up.
- **`darktable-cli` never runs your `luarc`.** Since 5.6 the user `luarc` is loaded by `script_manager` (GUI only); before that the C code only loaded it when a GUI existed. `--luacmd` still runs, and it's the way to test headlessly. Anything GTK-wrapped (`register_lib`, `preferences.register`) blocks forever headless, so the plugin gates those on `dt.gui`.
- **Windows runs start with `start "" /B pythonw.exe launch.py <job>`.** The script and its arguments go in a job file, so none of them pass through cmd.exe. The command starts with `start`, not a quote, so cmd.exe keeps its quoted items intact (`lib/dtutils/system.lua` in darktable's lua-scripts wraps commands in a `.bat` because a command that starts with a quote gets mangled). There's no `.vbs`/`.bat` chain: antivirus behaviour checks (Bitdefender Advanced Threat Defense) flag a script host starting a hidden cmd from temp files. `pythonw.exe` must sit beside the `python.exe` the preference points at, as it does in a venv or a python.org install.
- **Native groups are read from `img.group_leader`.** Photos sharing a leader are one group, and a photo with no leader, or that is the only photo sharing its leader, is its own group. A RAW+JPEG import pair is a native group (darktable groups them on import), so it counts as one group under **Native groups**. Assisted Grouping writes native groups only when its **Apply darktable groups** is on; with it off, **Native groups** sees just the import pairs and any groups you made by hand.
- **Combobox `changed_callback` runs asynchronously, and every `selected` assignment fires it** (`src/lua/widget/combobox.c`, `src/bauhaus/bauhaus.c`), even when refilling the list. So the collection list acts only when its value differs from the stored collection.

## License

MIT, see [LICENSE](LICENSE).

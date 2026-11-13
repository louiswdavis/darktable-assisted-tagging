# darktable-assisted-tagging

A tagging assistant for [darktable](https://www.darktable.org/) that recognises the motorsport vehicles in your photos. Select a batch in lighttable, click one button, and for every car or bike in each frame it will:

- **read its race number** and look it up in your entry list
- if the number isn't readable, **match its livery** against reference samples you picked
- if that's still unclear, **borrow the answer from the rest of its group** (a darktable group or an Assisted Grouping tag group, see [Grouping support](#grouping-support))
- tag the image with that entry's tags, e.g. `Motorsport|F1|Red Bull|Max Verstappen`

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
- Python 3.10+ with the packages in `python/requirements.txt`: `opencv-python-headless` (4.x, pinned `<5`), `numpy`, `Pillow`, `rawpy`, `onnxruntime` and `PyYAML` (only the PP-OCRv5 number reader uses it).
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

Download them into a `models` folder in the repo. The plugin looks there, `.gitignore` already skips `*.onnx` and `*.yml`, and `git pull` leaves them alone. From the repo root (Windows 10+ ships `curl`):

```
mkdir models
curl -L -o models/object_detection_yolox_2022nov.onnx https://github.com/opencv/opencv_zoo/raw/main/models/object_detection_yolox/object_detection_yolox_2022nov.onnx
curl -L -o models/text_detection_en_ppocrv3_2023may.onnx https://github.com/opencv/opencv_zoo/raw/main/models/text_detection_ppocr/text_detection_en_ppocrv3_2023may.onnx
curl -L -o models/en_PP-OCRv5_mobile_rec.onnx https://huggingface.co/PaddlePaddle/en_PP-OCRv5_mobile_rec_onnx/resolve/main/inference.onnx
curl -L -o models/en_PP-OCRv5_mobile_rec.yml https://huggingface.co/PaddlePaddle/en_PP-OCRv5_mobile_rec_onnx/resolve/main/inference.yml
curl -L -o models/dinov2_small.onnx https://huggingface.co/onnx-community/dinov2-small/resolve/main/onnx/model.onnx
```

| File | Size | Job | Source, licence |
|---|---|---|---|
| `object_detection_yolox_2022nov.onnx` | 36 MB | finds the cars and bikes | OpenCV model zoo, Apache-2.0 |
| `text_detection_en_ppocrv3_2023may.onnx` | 2.4 MB | finds text on each vehicle | OpenCV model zoo (PP-OCRv3), Apache-2.0 |
| `en_PP-OCRv5_mobile_rec.onnx` + `.yml` | 7.9 MB | reads that text (the yml is its dictionary; the plugin treats a recogniser as PaddleOCR when the yml sits beside it under the same name) | PaddleOCR via PaddlePaddle on Hugging Face, Apache-2.0 |
| `dinov2_small.onnx` | 89 MB | livery matching | DINOv2 ViT-S/14 via onnx-community, Apache-2.0 |
| `dfine_s_coco.onnx` (optional) | 42 MB | a second vehicle detector, for `compare_detectors.py`; the plugin uses it only when `detector_model` in `MODEL_FILES` (`lua/assisted_tagging.lua`) names it | D-FINE-S COCO via onnx-community (`dfine_s_coco-ONNX`, `onnx/model.onnx`), Apache-2.0 |

The first run after switching to a new reader re-reads every box, because the recogniser is part of the cache key. The run log's `number reader:` line names the recogniser in use.

Optional models. The plugin works without them:

- **Segmentation**, for pack shots with overlapping cars. With it in `models`, a box that overlaps another is read through a car-shaped mask, with the background and the neighbouring car painted grey.
- **Larger livery embedder.** Not used unless you type `dinov2_base.onnx` into the collection's **embedder model file** option in the panel (and **update preset**); the next run then re-embeds every reference before analysing (the progress bar counts the references; on a large collection this takes minutes, and a cancel keeps those already done). Compare it first with `python/eval_matching.py COLLECTION_DIR --embedder models/dinov2_base.onnx --fresh-embed` (re-embeds the refs with that model in memory; `index.npz` is untouched).

```
curl -L -o models/image_segmentation_efficientsam_ti_2025april.onnx https://github.com/opencv/opencv_zoo/raw/main/models/image_segmentation_efficientsam/image_segmentation_efficientsam_ti_2025april.onnx
curl -L -o models/dinov2_base.onnx https://huggingface.co/onnx-community/dinov2-base/resolve/main/onnx/model.onnx
```

| File | Size | Job | Source, licence |
|---|---|---|---|
| `image_segmentation_efficientsam_ti_2025april.onnx` | | outlines an overlapped car | OpenCV model zoo (EfficientSAM), Apache-2.0 |
| `dinov2_base.onnx` | about 350 MB | livery matching, larger than `dinov2_small.onnx` | DINOv2 ViT-B/14 via onnx-community, Apache-2.0 |

**Older number reader (CRNN).** The plugin's first recogniser, opencv_zoo's CRNN, still works: it reads grey crops at a smaller size and misses more numbers (on 202 rally photos it read a number on 45 vehicles where PP-OCRv5 read 76). An install without the v5 files falls back to it with one `number reader:` warning in the log, so an older setup keeps running:

```
curl -L -o models/text_recognition_CRNN_EN_2021sep.onnx https://github.com/opencv/opencv_zoo/raw/main/models/text_recognition_crnn/text_recognition_CRNN_EN_2021sep.onnx
```

| File | Size | Job | Source, licence |
|---|---|---|---|
| `text_recognition_CRNN_EN_2021sep.onnx` | 34 MB | reads the text, older than PP-OCRv5 | OpenCV model zoo (CRNN), Apache-2.0 |

To compare the two on your own photos, print each vehicle's reads from both, with the ones that differ marked and a count of how many vehicles each got a number on:

```
python python/compare_ocr.py --rec models/text_recognition_CRNN_EN_2021sep.onnx --rec models/en_PP-OCRv5_mobile_rec.onnx --out compare.csv <a folder of photos>
```

To compare two vehicle detectors on your own photos (frames with a car, cars missed, boxes per frame, CPU ms per frame at three score thresholds, plus a CSV of the frames where they disagree on box count), download the candidate and run:

```
curl -L -o models/dfine_s_coco.onnx https://huggingface.co/onnx-community/dfine_s_coco-ONNX/resolve/main/onnx/model.onnx
python python/compare_detectors.py --detector models/object_detection_yolox_2022nov.onnx --detector models/dfine_s_coco.onnx --truth results.csv --manifest manifest.csv --out compare_detectors.csv --disagree disagree.csv <a folder of photos>
```

`--truth` is a tagging run's `results.csv` and `--manifest` its `id,filepath` manifest (both optional, both together): a frame with a box there counts as a frame with a car, and a detector that finds no box on it at a threshold has missed it. The markdown table it prints goes into `<plugins folder>/docs/superpowers/specs/backlog/darktable-plugins-tickets/13-detector-comparison.md`.

To go back to the CRNN for a collection, type `text_recognition_CRNN_EN_2021sep.onnx` into its **number reader model file** option and **update preset**. A yml whose dictionary doesn't fit the model stops the run at the start with an error.

**Audit references** (panel button, `python/audit_refs.py`) needs nothing beyond the packages in `requirements.txt` and the models above.

People collections (`"kind": "people"` in entries.json) also need these two. Motorsport collections don't:

```
curl -L -o models/face_detection_yunet_2023mar.onnx https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
curl -L -o models/face_recognition_sface_2021dec.onnx https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
```

| File | Job | Source, licence |
|---|---|---|
| `face_detection_yunet_2023mar.onnx` | finds faces | OpenCV model zoo (YuNet), MIT |
| `face_recognition_sface_2021dec.onnx` | turns each face into a 128-number fingerprint | OpenCV model zoo (SFace), Apache-2.0 |

A people entry has only `id` and `tags`; references are photos with exactly one face, so tag those photos by hand first. Choose `min_sim`, `margin` and `min_face_px` in `settings.json` with `python python/eval_people.py <collection> --face-detector … --face-recognizer …`.

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

Either way, a created collection still needs its placeholder names replaced with your own competitors (and references added, for anything you want livery-matched) before it identifies anything correctly — click **Edit entries.json ▸** at the top of the panel at any time to open the *active* collection's file the same way.

#### By hand

Write `entries.json` yourself for more control than tags alone give you: a race `number`, or custom [rules](#rules). It holds the collection's **entries**, one per competitor, and its **rules**: what each outcome tags. For example:

```json
{
  "rules": {
    "tag_prefix": "Motorsport|F1",
    "team_only": "shared tags",
    "unidentified": ["Motorsport|F1|Unidentified"]
  },
  "entries": [
    { "id": "VER", "number": "1",  "team": "Red Bull", "name": "Max Verstappen" },
    { "id": "TSU", "number": "22", "team": "Red Bull", "name": "Yuki Tsunoda" },
    { "id": "SAFETY", "name": "Safety Car" }
  ]
}
```

Here VER gets `Motorsport|F1|Red Bull` and `Motorsport|F1|Red Bull|Max Verstappen`, and SAFETY gets `Motorsport|F1|Safety Car`. Add a `tags` list to an entry for extra tags on top; without `tag_prefix`, `tags` is the full list as before.

A file that's just the `[ … ]` list of entries works too, with the default rules — this is the shape **new collection → From tagged images** writes when its tags don't share one prefix. When every car's tags are `prefix|team` and `prefix|team|name` under the same prefix, it writes the `tag_prefix` form above instead (with `name` per entry). Either way you can hand-edit the result to add numbers or rules.

[`examples/`](examples) has four collections — pick one from the panel's **example** dropdown (see [above](#from-an-example)), which copies its `entries.json` and `settings.json`, or copy its folder into the collections folder by hand. Each has a README on what it shows and how to supply its references:

- [`f1-season`](examples/f1-season): a season with near-identical teammates, a one-off livery and number-less cars
- [`btcc-event`](examples/btcc-event): one race weekend, with a "check me" tag for misses and no team-only tags
- [`minimal`](examples/minimal): a bare entry list on the default rules
- [`rally`](examples/rally): number-only entries for cars of no known livery, with the neighbour aid on (`order_weight`) and colour tags on (`colour_tags`), and grouping support set to Grouping tags, all set in its `settings.json`

#### Entries

| Field | Required | Rules |
|---|---|---|
| `id` | yes | unique within the collection; it's also the folder name under `refs/`, so it can't contain `, ; " / \ : * ? < > \|` |
| `tags` | yes, unless `rules.tag_prefix` is set | one or more darktable tag names (`\|` makes a hierarchy); no `,` `;` or `"`. With `rules.tag_prefix` these are extras added after the built tags |
| `name` | no | the driver's display name, e.g. `Max Verstappen`; needs `rules.tag_prefix`, which builds `prefix\|team\|name` from it |
| `number` | no | the race number, 1–3 digits. Leave it out for a car with no number; it can then only be identified by livery. Two entries with the same number are allowed, but that number then identifies neither. |
| numbers-only entry | | `{"id": "12", "number": "12"}`: an entry with a number and no `team`, `name` or `tags`, under `rules.tag_prefix`, gets the tag `prefix\|12`. Build a whole list from a CSV with `python python/import_numbers.py numbers.csv entries.json --tag-prefix "Rally\|2026"`, or add a full start list (names, teams, classes) with the panel's **Import start list** (see [1 collection](#1-collection)); see [`rally`](examples/rally) |
| `team` | no | entries with the same team can fall back to their shared tags when their liveries are too close to call |
| `colour` | no | the car's paintwork colour: a name in the active palette, or `Multi` (needs [`colour_tags`](#collection-settings-settingsjson)). Breaks ties between number candidates and flags a number read that disagrees; never a hard filter. The reference actions fill it in when it is missing |

The tags are yours to design: put the team tag on both teammates and the driver tag on one, and a team-only result carries exactly the team tag. The examples leave the year out of the tags: the collection already separates seasons for matching, and darktable's collections module filters by capture date. A **livery change** mid-season is a new entry (`VER-miami`, with the same tags and no `number`, so the number still identifies `VER`) or a new collection.

#### Rules

Every key is optional; leave one out for its default.

| Rule | Default | What it does |
|---|---|---|
| `team_only` | `"shared tags"` | when two teammates are too close to call: `"shared tags"` adds the tags both entries carry, `"none"` adds no collection tags (only the *Team only* diagnostic) |
| `unidentified` | `[]` | tags added to an image where no vehicle was identified, e.g. a "check me" tag for the shoot |
| `colour_palette` | the six built-in colours | an object mapping each tag name to a built-in colour (`"Red"`, `"Blue"`, `"Green"`, `"Yellow"`, `"White"`, `"Black"`) or to a list of bounds in OpenCV HSV, e.g. `{"Red": "Red", "Orange": [{"hue": [9, 19], "sat": [90, 255]}], "Silver": "White"}`. Each bounds object needs `hue` (0–179) and may have `sat` and `val` (0–255); a missing one is the full range. A pixel goes to the first colour that matches. A name can't be `Multi` or contain `\|`. Entry colours must be in the palette. Unlisted built-ins are dropped |
| `sponsor_keywords` | `{}` | maps a lowercase sponsor word to the tag prefix of its team, e.g. `{"petronas": "Motorsport\|F1\|Mercedes"}`. A word read on a car (OCR confidence 0.90+; one typo allowed in words of 6+ letters) narrows matching to that team. Sponsors of two teams on one car give no hint. A prefix no entry sits under stops the run. |
| `tag_prefix` | `""` | a tag path for the whole collection, e.g. `Motorsport\|F1`. Each entry's tags are then built: `prefix\|team`, then `prefix\|team\|name` (`prefix\|name` with no team), then its own `tags` as extras. A driver match writes all of them; a team-only result writes the shared `prefix\|team`. Empty keeps `tags` as the full list. |

Behaviour settings moved to settings.json on 2026-11-11; an old entries.json still loads, each old rule is copied into settings.json once and logged.

An unknown key, or a misspelt one, stops the run and names it, so a typo can't silently do nothing.

#### Collection settings (settings.json)

Every other setting lives in the collection's `settings.json`, beside `entries.json`. The panel's **update preset** writes it and **Reload** re-reads it; a UTF-8 BOM at the start is accepted. A key missing from the file uses its default, and a value that is out of range or the wrong type falls back to the default with one log line. Most settings have a field in the panel; the five marked `no` are set only in the file.

| Key | What it does | Allowed values | Default | In panel |
|---|---|---|---|---|
| `use_hints` | a team tag you applied narrows matching on a solo shot | `true`, `false` | `true` | yes |
| `group_support` | which groups the burst step borrows answers from, see [Grouping support](#grouping-support) | `"native"`, `"tags"`, `"none"` | `"native"` | yes |
| `group_node` | the grouping tag node used when `group_support` is `"tags"`; blank is the newest Assisted Grouping run | text | `""` | yes |
| `run_tag` | stamps every image a run writes with `Assisted Tagging\|Run\|YYYY-MM-DD HH:MM` | `true`, `false` | `false` | yes |
| `suggest_crops` | **Audit references** suggests re-crops | `true`, `false` | `false` | yes |
| `quarantine` | **Audit references** quarantines poor references | `true`, `false` | `false` | yes |
| `embedder_file` | file name in `models/` used to compare liveries; blank uses `dinov2_small.onnx`. Changing it re-embeds every reference | text | `""` | yes |
| `ocr_rec_file` | file name in `models/` of the number reader; blank is PP-OCRv5, or the CRNN when the v5 files are missing. Changing it re-reads every photo | text | `""` | yes |
| `order_weight` | how far the cars pass in number order: `0` is random (the neighbour aid is off), `1` is strictly in order. Above 0, groups shot just before and after a doubtful read help identify it, including unselected photos in the same film rolls already tagged with an entry; from `0.5` up an unsupported doubtful read is flagged *Check order*; see [How it works](#how-it-works) | number, 0 to 1 | `0` | yes |
| `neighbour_tolerance` | the most places apart in the sorted number list a neighbouring car can be and still support a read; `order_weight` sets how much of it is used (up to `order_weight × (tolerance + 1)` places) | whole number, 0 or more | `5` | yes |
| `min_read` | how sure a number read must be to count. A read's confidence is the lower of two scores: how sure the text detector is that it found text, and how sure the reader is of its least certain digit. Raise it if plates or signs get read as numbers; lower it if clear numbers are missed | number, 0 to 1 | `0.85` | yes |
| `colour_weight` | how much the colour histogram counts in livery matching, from `0` (off) up. Separate from `colour_tags` | number, 0 or more | `0` | yes |
| `colour_tags` | reads each car's paintwork colour, writes it as a `Colour` tag and uses an entry's `colour` to break ties and flag number reads that disagree; see [How it works](#how-it-works). Turning it on re-reads every photo once | `true`, `false` | `false` | yes |
| `partial_references` | **Add tagged images** also accepts a solo shot tagged only to team level (e.g. `Motorsport\|F1\|Red Bull`) and saves it as a team reference under `refs/@team@…`. When no driver is clear but one team's references lead clearly, the result is *team* (shared tags only) | `true`, `false` | `false` | yes |
| `min_sim` | people collections: the least face similarity that counts as a match | number, above 0 up to 1 | `0.5` | no |
| `margin` | people collections: how far the best face match must lead the runner-up | number, 0 up to but not including 1 | `0.05` | no |
| `min_face_px` | people collections: the smallest face, in pixels, that is used | whole number, 1 or more | `48` | no |
| `burst_livery_pooling` | experimental: resolves a burst frame that didn't clear the threshold from the burst's pooled livery similarity (*By pooled burst*) | `true`, `false` | `false` | no |
| `blur_references` | blurs reference crops before they are compared | `true`, `false` | `false` | no |
| `tag_number`, `tag_number_name` | write the *By number* diagnostic; the tag it writes | `true`/`false`; a tag name | `true`; `Assisted Tagging\|Identification\|By number` | yes |
| `tag_livery`, `tag_livery_name` | *By livery* | same | `true`; `Assisted Tagging\|Identification\|By livery` | yes |
| `tag_burst`, `tag_burst_name` | *By burst* | same | `true`; `Assisted Tagging\|Identification\|By burst` | yes |
| `tag_pooled`, `tag_pooled_name` | *By pooled burst* | same | `true`; `Assisted Tagging\|Identification\|By pooled burst` | yes |
| `tag_neighbour`, `tag_neighbour_name` | *By neighbour* | same | `true`; `Assisted Tagging\|Identification\|By neighbour` | yes |
| `tag_check_order`, `tag_check_order_name` | *Check order* | same | `true`; `Assisted Tagging\|Identification\|Check order` | yes |
| `tag_team`, `tag_team_name` | *Team only* | same | `true`; `Assisted Tagging\|Identification\|Team only` | yes |
| `tag_none`, `tag_none_name` | *Unidentified* | same | `true`; `Assisted Tagging\|Identification\|Unidentified` | yes |
| `tag_number_seen`, `tag_number_seen_name` | *Number seen* (the digits are added as a leaf) | same | `true`; `Assisted Tagging\|Identification\|Number seen` | yes |
| `tag_colour`, `tag_colour_name` | the *Colour* tag (the colour is added as a leaf; needs `colour_tags`) | same | `true`; `Assisted Tagging\|Colour` | yes |
| `tag_check_colour`, `tag_check_colour_name` | *Check colour* (needs `colour_tags`) | same | `true`; `Assisted Tagging\|Identification\|Check colour` | yes |
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
"tag_colour_name": "Cars|Paint",
"tag_shot_name": "Cars|Framing"
```

Tags written under the old name stay on images the run doesn't touch; darktable keeps the old name in its tag list until you delete it.

#### Checking what it will tag

Click **Show tag plan** in the panel. It writes `tag-plan.txt` next to the collection's `entries.json`, listing exactly what each outcome writes: every entry's tags and reference count, the team-only tags for each pair of teammates, the unidentified tags (headed `unidentified tags (yours)`), and the diagnostic tags. It also lists entries that can only be identified by number, and entries that can't be identified at all until they have references. The file is rewritten on every run and **Reload**, so it always matches `entries.json`.

After editing `entries.json`, click **Reload** in the panel. A mistake in the file stops the run with the file name and what's wrong.

### Building references

Numbers aren't readable in every shot (rear views, motion blur, a number hidden by the halo), so each entry also needs a few **reference samples**: crops of that car the plugin compares new photos against. 3–5 per car from different angles is a good start; add more for the angles it gets wrong. **new collection → From tagged images** already does this for the images it was given; add more at any time with the panel's **6 references** page:

- **Add as reference**: pick the entry in the **entry** list, select photos of that car, click. The largest vehicle in each photo is cropped and saved under that entry. A photo where no vehicle is found is saved whole, and the done message says how many.
- **Add tagged images**: select photos you've already tagged by hand. Each one carrying *all* of one entry's tags is added under that entry. A photo with only a shared team tag, or with two drivers' tags, is skipped.
- **Add from last run**: select photos from the last **Identify selection** run. Each vehicle that run was sure of (its number was read, or its livery led the runner-up by `REFERENCE_MIN_MARGIN`) is saved under the entry it found. This works for pack shots: the saved crop is that one car, not the whole photo, so the entry's tag doesn't have to describe the frame. Burst, team-only and held-back results are never saved. Photos changed since the run are skipped.
- **Fill entry colours** (needs **read car colour** on, section 3): select photos that already carry one entry's tags, click. Each car's paintwork colour is read and written as that entry's `colour` in `entries.json`; no reference is saved. The done message counts the entries set, those that already had that colour and the images where no car or colour could be read, and names the file. A photo whose tags match no single entry is skipped.
- **Entry colour** (**read car colour** on): the three add actions above also fill an entry's missing `colour` in `entries.json` from the one colour tag you applied by hand to the photo, else from the plugin's reading of the saved car. An entry that already has a different colour is never overwritten; the log says so and the done message counts it. `entries.json.bak` keeps the previous file. A file not laid out one entry per line is rewritten that way. The reference job's result rows are `id,status,colour_note,entry_id`.
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
| `Assisted Tagging\|Identification\|Check colour` | a number read whose entry's `colour` differs from the car's paintwork colour (needs `colour_tags`); the entry tag stays. Delete the tag once checked |
| `Assisted Tagging\|Identification\|Team only` | two teammates were too close to call; only their shared tags were added |
| `Assisted Tagging\|Identification\|Unidentified` | no vehicle, or no confident match |
| `Assisted Tagging\|Identification\|Number seen\|<digits>` | OCR read these digits but they didn't resolve to one entry; added alongside the outcome tag |
| `Assisted Tagging\|Colour\|<name>` | the car's paintwork colour (`Red`, `Blue`, `Green`, `Yellow`, `White`, `Black`, or `Multi` for a two-tone car); needs `colour_tags`. Filter on it to hand-sort cars by colour |
| `Assisted Tagging\|Identification\|Shot\|Solo` | one vehicle was found in the frame |
| `Assisted Tagging\|Identification\|Shot\|Pack` | two or three vehicles were found |
| `Assisted Tagging\|Identification\|Shot\|Crowded` | the detector's limit (`MAX_BOXES`) was reached, so there may be more cars than were identified |

#### Choosing which diagnostics are written

Each row above has its own switch under **tags written** in the panel, saved in the collection's `settings.json` and all on by default (`Shot` is one switch for `Solo` and `Pack`; `Shot crowded` has its own). Each switch's tooltip names the tag it writes under this collection's settings. Turn off the ones you don't use to keep darktable's tag list short:

- **Off** = the next run stops writing that diagnostic and removes it from the images it processes, under whatever name the collection's settings give it. One never written never shows up in the tag list.
- **Identification doesn't change.** Entry tags, team-only and unidentified tags from `entries.json` are written as before.
- Images outside the run keep their old diagnostics. darktable keeps tag names nobody uses any more in its tag list; delete them in the tagging module's dictionary.

Filter on `Assisted Tagging|Identification|By livery` and `Assisted Tagging|Identification|Unidentified` in the **collections** module to spot-check the uncertain ones; an image it got wrong is often a good new reference.

Tick **Tag each run** in the panel to also stamp every image a run writes with `Assisted Tagging|Run|YYYY-MM-DD HH:MM`, so the latest run's photos can be filtered apart from earlier ones. Stamps are never removed by later runs; delete old ones in darktable's tag manager.

Re-running is safe: each image's entry and diagnostic tags are synced to the new result, so a frame that moves from one driver to another loses the old driver's tags. Tags that aren't in the active collection are never touched.

#### Tags you apply by hand

The plugin keeps a ledger (`assisted_tagging/ledger.csv` in darktable's config directory, lines `<library>,id,tag`) of the tags it attached to each image. `<library>` is a hash of the library file's path, so two libraries that reuse the same image ids keep separate ledger lines (lines from before this column belong to the library in use when they're first read; a library opened with `--library` on the command line isn't visible to the plugin and counts as the configured one). Lines for images removed from the library are dropped whenever the ledger is saved, and a failed save is tried once more before an on-screen error. An entry tag on an image that isn't in its ledger is yours, at any depth (team or driver), and a run never removes it. So a photo you tagged to a team stays that way even when the run can't tell the driver.

**Clear tagging marks** reads the same ledger, so hand-applied tags survive it even when they sit under the plugin's roots.

- A **solo shot** whose result disagrees with the tags you applied is left as you had it: nothing is added, it doesn't get the *Unidentified* tags, and the done message counts it. Packs aren't checked, since you may have tagged just one of the cars.
- A **team tag** you applied (a tag that is a prefix of an entry's tags, such as `Motorsport|F1|Red Bull`) is a **hint** on a solo shot: matching is limited to the entries under it. If none of them looks similar enough, or the number read belongs to a car outside it, the hint is dropped and the normal match runs. The report lists each hint and any that were dropped. Packs get no tag hints, since the tag may describe only one car. Untick **Use team tags as hints** in the panel to ignore team tags instead: matching isn't narrowed, and a differing result is not held back as a conflict, so the run can override your team tag. The tag itself stays on the image beside whatever the run adds (tick **Replace manual tags** too to have the run overwrite it). Driver-level tags still protect their images either way.
- An image already carrying all of one entry's tags is **skipped** without being analysed.
- To let a run replace your tags, tick **Replace manual tags** under **Identify selection**. It applies to the next run only and clears itself.
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

At the top: the **preset** picker and **actions** (see [Presets](#presets)), and **Reload**, which rereads the collections folder and the active collection's `entries.json`. On `template` the panel shows only **new collection**. On a collection it shows **Edit entries.json ▸** (see [1 collection](#1-collection)), then the page buttons **1 collection ▸**, **2 bursts ▸**, **3 matching ▸**, **4 tags written ▸**, **5 run ▸** and **6 references ▸**: clicking one opens its contents below it (its label ends in **▾**) and folds the others; clicking the open one folds it. The open page is remembered across restarts. darktable's reset button (↺ in the panel header) puts every setting back to the template defaults.

### new collection

- **Name** (text field, e.g. `F1 2026`). The folder name for a new collection.
- **From tagged images.** Builds the collection from the selected images' tags (see [From already-tagged images](#from-already-tagged-images-recommended)).
- **example**, **View example**, **From example.** Pick a shipped example, open its `entries.json`, or copy it into a new collection (see [From an example](#from-an-example)).

### 1 collection

- **Show tag plan.** Writes `tag-plan.txt` (see [Checking what it will tag](#checking-what-it-will-tag)).
- **Edit entries.json ▸.** A toggle in the top area, above the page buttons, so it shows whichever page is open. It opens the file in an editor below it, with **Save entries.json** and **Cancel edit**, and reads **▾** while open; clicking it again, saving, cancelling or switching collection closes it.
- **start list** → **Import start list.** Adds a start list to the collection's `entries.json` without typing the entries. Either choose a CSV with a header row (number, driver, co-driver, team, class; any other columns are ignored), or paste the text copied from a PDF entry list into the box, one entry per line with the number first (`12 Smith / Jones`); pasted text is used when both are given. The **columns** field maps a header to a role when its name isn't one of the usual ones, as `role=header` pairs: `number=Start No.; driver=Pilot`; only `number` is required. Each entry becomes `{"id": "<number>", "number": "<number>", "name": "<driver> / <co-driver>", "team": "<team>", "tags": ["<prefix>|Class|<class>"]}` under the collection's `rules.tag_prefix`, with the empty fields left out. Numbers already in the file are kept and listed in the message, the previous file is saved as `entries.json.bak`, and the lists reload. A file not in the one-entry-per-line layout is rewritten that way. Same thing from a shell: `python python/import_start_list.py <collection folder> --csv start.csv [--columns "number=No."]` or `--text pasted.txt` (`--tag-prefix` only when the file has no prefix yet).

### 2 bursts

- **grouping support** (Native groups, Grouping tags, None). What the burst step borrows answers from (see [Grouping support](#grouping-support)).
- **Grouping tag node (blank = newest run)** (text field). The tag node in Grouping tags mode.

### 3 matching

- **read car colour** (off by default). Reads each car's paintwork colour: it breaks ties between number candidates, flags a number read whose entry colour disagrees, and feeds the Colour and Check colour tags and **Fill entry colours**. `colour_tags` in `settings.json`.
- **Use team tags as hints** (on by default). A team tag you applied narrows matching on a solo shot.
- **embedder model file (blank = bundled)** (text field). File name in `models/` used to compare liveries, e.g. `dinov2_base.onnx`; blank uses `dinov2_small.onnx`. Changing it re-embeds every reference on the next run.
- **number reader model file** (text field, blank = PP-OCRv5, or the CRNN when the v5 files are missing). File name in `models/` of the text recogniser, e.g. `text_recognition_CRNN_EN_2021sep.onnx` for the older reader (see [Models](#2-models)). Changing it re-reads every photo on the next run.
- **order weight** (text field, default 0). `order_weight` in `settings.json`: a number from 0 to 1, where 0 turns the neighbour aid off. Anything else is refused.
- **neighbour tolerance** (text field, default 5). The most places apart in the sorted number list a neighbouring car can be and still support a read; `order_weight` sets how much of it is used (up to `order_weight × (tolerance + 1)` places). A whole number, 0 or more (anything else refuses the run). Only used when `order_weight` is above 0.

### 4 tags written

One switch per diagnostic (default on), each on one line with the tag name it writes beside it, under three headings: **outputs** (`Colour`), **checks** (`Check order`, `Unidentified (check)`, `Check colour`, `Shot`, `Shot crowded`) and **how it decided** (`By number`, `By livery`, `By burst`, `By pooled burst`, `By neighbour`, `Team only`, `Number seen`). Off removes that diagnostic on the next run; see [Choosing which diagnostics are written](#choosing-which-diagnostics-are-written). A switch whose tag needs another setting shows why it is off in its label, e.g. `Colour (off: read car colour is off)`, and is greyed until that setting is on. A `settings.json` from before *Shot crowded* existed loads with `tag_shot_crowded` and `tag_shot_crowded_name` copied from the Shot switch, once, and the log says so.

### 5 run

- **Replace manual tags.** Lets the next run replace tags you applied by hand; clears itself after the run (see [Tags you apply by hand](#tags-you-apply-by-hand)).
- **Tag each run.** Stamps every image a run writes with `Assisted Tagging|Run|YYYY-MM-DD HH:MM`.
- **Verify selection.** Identifies the selection, fully tagged images included, and reports where the result differs from your tags. No tags change.
- **Identify selection.** Identifies and tags the selection (see [Identifying](#identifying)). Click again to cancel.
- **Clear tagging marks.** Removes every tag the ledger says the plugin attached to the selected images (entries, colours, diagnostics, unidentified), from any collection, and forgets those images in the ledger, so a later **Identify selection** treats them as fresh. The ledger alone decides: tags you applied by hand stay, even under the plugin's roots, and so do **Tag each run** stamps, which are not ledgered. Images with no ledger row are left alone.

### 6 references

- **entry.** The entry **Add as reference** saves under.
- **Add as reference**, **Add tagged images**, **Fill entry colours**, **Add from last run.** See [Building references](#building-references). The three add actions also fill the entry's colour in `entries.json` when **read car colour** is on.
- **Audit: suggest re-crops**, **Audit: quarantine poor refs** (both off by default), **Audit references.** See **Audit references** under [Building references](#building-references).

Everything in pages 2 to 6 except **Replace manual tags** is saved with the collection by **update preset**. **Replace manual tags** applies to the next run only.

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
identify.py, per frame:  decode at full resolution → YOLOX vehicle boxes (up to 4)
        |                → per box: crop (EfficientSAM mask when boxes overlap)
        |                → read numbers → DINOv2 embedding         (all cached)
        |                no vehicle found → a weaker candidate box that looks like a
        |                group mate's car is kept (rescue)
        v
match, pass 1, per box:  sponsor words on the car (or a team tag you applied) narrow the candidates to one team, then
           one number matches one entry                 → number
           else best livery match clear of the next one → livery
           else best two are teammates                  → team (shared tags only)
           else                                         → none
        |
        v
hires re-read: boxes still unidentified are read again from a half-size RAW decode → match, pass 2
        |
        v
weak reads: a number read under min read (but at least 0.7) on unidentified boxes of 2+ frames
           of one group → number, when only one entry is read that way and nothing else in the group
           names another entry
        |
        v
neighbour aid (only when order weight > 0), against the 3 groups shot before and after (within 20 seconds),
taken from the selection and from unselected photos in the same film rolls that already carry an entry's tags
(those only lend support for number order, never a look-alike, and are never tagged):
           a misread or unmatched number near a nearby entry in the list → neighbour (order)
           a box with no number read that looks like a nearby identified car → neighbour (look-alike)
           unsupported low-confidence read → "Check order" tag
           colour tags on (`colour_tags`): the box's paintwork colour breaks ties; see below
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

Frames are decoded at native resolution (a raw file's embedded preview) and each vehicle is cropped from that before reading its number, since a number only a few pixels tall in a downscaled frame is readable in the crop. OCR text and embeddings are cached per frame in `assisted_tagging/cache.sqlite` in darktable's config directory, and vehicle detections in the shared detection cache below. Matching isn't, so adding references or editing `entries.json` takes effect on the next run without decoding anything again. The cache key includes the file (path, modified time, size), every model file and a fingerprint of the constants and package versions that change the cached data, so the first run after an update or a constants edit re-reads everything once; unused entries are dropped after 90 days. Delete the file to start over.

**Shared detection cache.** Vehicle boxes are cached in `assisted_plugins/detections.sqlite` in darktable's config directory, shared with the culling plugin so a frame both plugins see is detected once. The key is the file (path, modified time, size), the detector model file and a fingerprint of the shared detector code, so a new detector or a `vehicle_detect.py` change re-detects everything once; rows unused for 90 days are dropped. Delete the file to start over.

**Colour tags.** With `colour_tags` on (a [collection setting](#collection-settings-settingsjson); rename the tag with [Renaming tags](#renaming-tags)), each car's paintwork is measured on the middle of its crop (margin, roofline and the lower tyre band are left out) and becomes a colour from the palette, `Multi` for a clear two-tone car, or nothing when it can't tell. The decided colour is written as `…|Colour|<name>`. An entry's `colour` is a tie-breaker only, never a filter. A weak number read for an entry whose colour differs from the car's doesn't count towards a group's agreement; the neighbour aid drops candidates whose colour differs and a look-alike car only lends its entry when the colours don't differ; a confident number read is never blocked, but when its entry's colour differs from the car's the image gets *Check colour*. An entry with no `colour`, or a car whose colour can't be told, is neutral. `Multi` agrees only with `Multi`. Turning `colour_tags` on re-reads every photo once.

**RAW+JPEG pairs are read once, from the JPEG.** A RAW and a JPEG in the same folder with the same name before the extension (case ignored, as darktable pairs them on import) are one shot, and so are darktable duplicates of a file. The JPEG is read: it has the camera's exposure and colour at full size. Every file in the shot gets the same tags, and a hand tag on any of them is protected for the whole shot. A RAW with no JPEG is read as before. Same name in another folder is a separate shot.

### Grouping support

Tagging no longer clusters photos by capture time. Consensus (the "borrow the answer from the rest of the group" step) runs over groups that something else already made, and the panel's **grouping support** combobox picks which:

- **Native groups** (default): darktable's own image groups. A photo's group is its group leader.
- **Grouping tags**: the children of an [Assisted Grouping](../darktable-assisted-grouping/README.md) tag node, e.g. `Assisted Grouping|2026-01-01 12:00:00|Group|NNNN`. The **Grouping tag node (blank = newest run)** entry names the node. Blank uses the newest Assisted Grouping run found on the selected photos. Assisted Grouping must have **Write group tags** on, or there is nothing to find.
- **None**: every photo is its own group, so nothing is borrowed.

A photo with no group (no native group, or no child tag under the node) is its own group. Groups are not size-checked: a coarse group (a long hand-made stack, or Assisted Grouping's Camera or Parent layers) is treated as one car pass, so the missed-detection rescue may carry an identification across the whole group. The log records the mechanism, how many photos landed in groups of 2 or more, and (in Grouping tags mode only) the node used.

A coarse group is your grouping settings at work: if Assisted Grouping's time gap is set high, or its Camera or Parent layers join unrelated shots, consensus can fill an entry across different cars. Tighten the grouping, switch to **None**, or fix the group, rather than expecting tagging to split it.

## Tuning

The thresholds are starting points, not tuned defaults. Each is a named constant:

| Constant | File | Default | What it does |
|---|---|---|---|
| `OCR_MIN_SCORE` | `ocr.py` | 0.80 | how sure the text detector must be before a number is read |
| `NUMBER_MIN_HEIGHT` | `ocr.py` | 0.07 | a number's text region must be at least this share of the vehicle crop's height, so plate characters and lone sticker letters aren't read as numbers. A first guess: the report's "ocr saw" line shows each region's share (`h0.12`). Raise it if plates still get read; lower it if small but real numbers are dropped |
| `MATCH_MIN_SIM` | `match.py` | 0.60 | the livery similarity a match needs at all |
| `MATCH_MIN_MARGIN` | `match.py` | 0.10 | how far the best entry must be ahead of the next one. Similarities are centred on the references' mean once a collection has 20+ references, which spreads them out, so the gate is wider than it looks; `python/eval_matching.py` sweeps it on your own references |
| `BURST_MIN_AGREE` | `match.py` | 2 | frames that must agree before a burst fills in the rest |
| `SOLO_ANCHOR_CONF` | `match.py` | 0.95 | a number read this sure fills a burst that names no other entry on its own, however few frames agree |
| `WEAK_READ_MIN` | `match.py` | 0.7 | the lowest read that counts when frames of one group agree on a number below min read |
| `WEAK_AGREE_MIN` | `match.py` | 2 | how many frames of the group must agree on it |
| `BURST_MIN_CONFIDENCE` | `match.py` | 0.5 | the share of the group the entry must cover before a burst fill is written |
| `LOOKALIKE_MIN_SIM` | `neighbour.py` | 0.85 | how alike a box with no number and a nearby identified car must look for the neighbour look-alike |
| `LOOKALIKE_MARGIN` | `neighbour.py` | 0.05 | how far that car must lead the best-looking other car nearby |
| `DOUBT_CONF` | `neighbour.py` | 0.90 | a number read below this is doubtful, so the neighbour aid checks it |
| `COLOUR_SOLE_MIN` | `car_colour.py` | 0.60 | the share of the car's paintwork one colour needs to be its colour, and the share two colours need together for `Multi`. Raise it if too many cars come out `Multi`; lower it if clear two-tone cars get no tag |
| `COLOUR_PART_MIN` | `car_colour.py` | 0.30 | the share a colour needs to count as one of a car's two colours. Raise it if stickers and number boards cause `Multi`; lower it if clear two-tone cars get no tag. Neither constant needs a re-read: the report's colour shares show the effect |
| `REFERENCE_MIN_MARGIN` | `match.py` | 0.10 | how far a livery match must lead to be saved by **Add from last run** |
| `MIN_BOX_FRAC` | `vehicles.py` | 0.005 | the smallest vehicle, as a share of the frame, worth identifying |
| `MAX_BOXES` | `vehicles.py` | 4 | vehicles identified per frame |
| `CROP_DIM` | `vehicles.py` | 640 | the long side each vehicle crop is reduced to |
| `DETECTOR_MIN_SCORE` | `vehicles.py` | 0.20 | the confidence a vehicle detection needs |

The run log has one line per vehicle with the numbers read and the top two livery matches with their similarity, e.g. `box 0: livery VER (OCR -; livery VER 0.712, TSU 0.694)`. Read a few from a shoot to see where the right and wrong answers fall before changing `MATCH_MIN_SIM` or `MATCH_MIN_MARGIN`.

Editing a constant of a per-frame module (`vehicles.py`, `ocr.py`, `embed.py`, `segment.py`, `overlap.py`, `pod.py`, `colour.py`, `car_colour.py`, `people.py`) or upgrading OpenCV, Pillow, rawpy or numpy changes the fingerprint `fingerprint.py` puts in every cache key, so the next run re-reads every frame by itself. `fingerprint.py` lists each constant as a cache input or as neutral (only used at matching time); `test_identify.py` fails until a new constant is filed. A code-only change to a cached stage needs its token in `frame_key` bumped (`ocr-trace-2`, `pod-2`, `mask-1`, ...) or `cache.sqlite` deleted. Changes to `match.py`, `rescue.py` and `neighbour.py` never need either.

**Higher-detail re-read.** Frames are first analysed from the RAW's embedded preview (fast). After the first match, each box left unidentified (`none`, or `team` with the driver not separated; overlapped boxes excluded) is re-read from a half-size decode of the RAW itself, which gives OCR and the embedding several times the pixels on a small car. Boxes stay in preview coordinates; only their crops come from the sharper decode. Non-RAW files and previews already near full width are left alone. A re-read replaces that box's OCR, embedding and colour only, and the box record carries `"hires": true`. The re-read of a frame is cached separately (`hires-2`, keyed on the frame's box list), so a rerun doesn't decode again, while a box rescued from a burst gets a fresh re-read. Reference crops are still taken from previews.

**Car-shaped masks.** When the segmentation model is present, each box that overlaps another (`overlap.py` geometry, hidden boxes excluded) is outlined by EfficientSAM, prompted with three points on the car body. The crop used for OCR, the embedding and colour has everything outside the outline painted grey. The mask must not contain the centre of an overlapping box and must cover at least 15% of the visible box, otherwise the plain crop is used. The box record carries `"masked": true`. Pod readings and reference crops are unmasked. Having the model adds `mask-1` and the model file to the cache key, so the first run with it, or with a replaced model file, re-reads every frame.

## Troubleshooting

- **The panel isn't there.** Start darktable with `-d lua` and look for `LUA ERROR` in the log. On Windows the log is `Documents\Darktable\darktable-log.txt`.
- **Every run writes a log** to `assisted_tagging.log` in darktable's config directory (e.g. `%LOCALAPPDATA%\darktable` on Windows); the run before it is kept as `assisted_tagging.prev.log`. It has the exact command, the reference counts per entry, one line per vehicle with what was read and matched, and any per-image errors.
- **"…/entries.json: …"** The run stopped on a mistake in that file; the message says which entry and what's wrong.
- **"… model not found: …"** A model file is missing. Download it into `models/` (see [Install](#2-models)) or fix the collection's **embedder model file** option.
- **"Python is missing a package."** `darktable-assisted-tagging/.venv` doesn't have `requirements.txt` installed; the log names the package.
- **"no collections yet."** Create a folder with an `entries.json` in the collections folder the message names, then click **Reload**.
- **Everything comes back `Unidentified`.** Check the log's `references:` line: an entry with 0 references can only be found by its number.
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
2. **Install the plugin** as in [Install](#3-darktable-side) and start darktable. *Expect:* an **Assisted Tagging** panel in lighttable showing *new collection* on the `template` preset; on a collection, **Edit entries.json ▸**, the page buttons *1 collection ▾* (open, its settings below it) to *6 references ▸*. No `LUA ERROR` in the darktable log.
3. **A collection.** Set the plugins folder preference, then make a collection (from tagged images, or from the `f1-season` example plus a few references). *Expect:* it appears in the **preset** dropdown.

**Grouping support** (one run per mode, on a selection holding a burst)

4. **Native groups.** Put the burst in a darktable group, pick *Native groups*, click **Identify selection**. *Expect:* in the log, `identify started`, then `settings: … grouping support native, node (blank), neighbour tolerance 5`, then `group support native: N of M photos in groups of 2+` with N counting the burst.
5. **Grouping tags, blank node.** Run Assisted Grouping on the selection with **Write group tags** on. Back in tagging, pick *Grouping tags*, leave the node blank, run. *Expect:* `group support tags: N of M photos in groups of 2+, node Assisted Grouping|<stamp>|Group` naming the newest run.
6. **Grouping tags, wrong node.** Type a node no selected photo carries, run. *Expect:* `group support tags: 0 of M photos in groups of 2+, node <what you typed> (matches no selected photo)`; every photo is its own group.
7. **None.** Pick *None*, run. *Expect:* `group support none: 0 of M photos in groups of 2+`.

**Neighbour aid and references**

8. **Neighbour aid.** Make a collection from the `rally` example and run on cars shot roughly in number order. *Expect:* `neighbour: resolved N, flagged M (order weight …, tolerance 5)`; frames it settled get *By neighbour*, unsupported low-confidence reads get *Check order*. Set **neighbour tolerance** to 3 and re-run: both the `settings:` and `neighbour:` lines say 3. Then select only a few frames from the middle of an already-tagged run and Identify again. *Expect:* `neighbour: N unselected tagged photos shot near the selection` with N above 0, the same count in `unselected tagged photos lend support`, and no tags changed on the unselected photos.
9. **Zero references.** Run on a collection with no references. *Expect:* `collection … has no references yet: only numbers can identify a car`; the run finishes, and cars with no readable number are *Unidentified*.

**Panel**

10. **Cancel.** Start **Identify selection** on a large selection and click it again. *Expect:* "Assisted Tagging: cancelled, no tags were changed."
11. **No selection.** Clear the selection and click **Identify selection**. *Expect:* "Assisted Tagging: select some images first".
12. **Diagnostic switches.** Identify a batch with every switch on. Under **tags written** in the panel, turn off *Shot* and *By livery*, choose **actions** → **update preset**, then identify the same batch again. *Expect:* the same entry tags as before; no image in the batch has `…|Identification|Shot|…` or `…|By livery`; the other diagnostics are still there. No `LUA ERROR`.
13. **Start list import.** Save a 100-row CSV (`No.;Driver;Co-Driver;Entrant;Class`), choose it under **start list** and click **Import start list**. *Expect:* "added 100 entries to …entries.json"; the entries have `name`, `team` and a `…|Class|…` tag; `entries.json.bak` is the previous file. Click **Import start list** again. *Expect:* "added 0 entries … skipped 100 already listed: 1, 2, …". Paste `7 Smith / Jones` and a line without a number into the box and import. *Expect:* "added 1 entries … 1 line(s) without a leading number ignored" when 7 is new, and the box is cleared.

14. **Old settings.** Remove `tag_shot_crowded` and `tag_shot_crowded_name` from a collection's `settings.json` (keep `tag_shot` off), then click **Reload**. *Expect:* the log shows `settings.json: tag_shot_crowded, tag_shot_crowded_name copied from the Shot switch (old settings)`, and *Shot crowded* is off in **4 tags written**.
15. **Clear tagging marks.** Identify a burst, then add `Rally|2026|12` to one image by hand. Select the burst and click **Clear tagging marks**. *Expect:* "Assisted Tagging: cleared N tags from M images."; every tag the plugin attached is gone, the hand tag stays, and a later **Identify selection** treats the images as fresh. Click it again on the same selection. *Expect:* "Assisted Tagging: nothing to clear; the selection has no tagging marks."

### Report what breaks

For each step that doesn't match, send back:

- the step number, and what happened instead (screenshot if it's visual)
- `assisted_tagging.log` from `%LOCALAPPDATA%\darktable` (copy it right after the failing step; the next run moves it to `assisted_tagging.prev.log`)
- any `LUA ERROR` lines from `Documents\Darktable\darktable-log.txt`, with darktable started with `-d lua`

## Development

### Tests

From the repo root. The Python tests use synthetic images and stub models, so they need no model files. `run_tests.py` runs every `python/test_*.py` (or only the ones named, e.g. `match neighbour`), prints one summary line each and writes each one's output to `tests/<name>.txt`:

```
# Linux / macOS
.venv/bin/python python/run_tests.py

# Windows
.venv\Scripts\python python\run_tests.py
```

On a Mac or any machine without numpy and OpenCV, the standard-library tests still run (`python python/test_settings.py`, `python python/test_import_numbers.py`), as do the Lua suites; the rest need the venv.

The pure-logic half of the plugin runs under any Lua 5.4 (`cd lua && lua test_assisted_tagging.lua`). No `lua` binary? `pip install lupa` in the venv, then:

```
.venv/bin/python -c "import lupa; L=lupa.LuaRuntime(); L.execute('package.path=\"./lua/?.lua;\"..package.path; dofile(\"lua/test_assisted_tagging.lua\")')"
```

### Running the identifier on its own

`manifest.csv` is `id,filepath,burst_id` per line, with an optional fourth column, the `;`-joined entry tags the user applied by hand (an image carrying all of one entry's are skipped; a solo result sharing none of them is held back as `conflict`):

```
python python/identify.py manifest.csv results.csv --collections-root collections --collection "F1 2026" \
    --detector models/object_detection_yolox_2022nov.onnx --ocr-det models/text_detection_en_ppocrv3_2023may.onnx \
    --ocr-rec models/en_PP-OCRv5_mobile_rec.onnx --embedder models/dinov2_small.onnx
```

`--ocr-rec` takes the CRNN model too. `--settings PATH` uses that settings file instead of the collection's `settings.json` (the panel passes a temporary one for its runs; `promote_boxes.py`, `audit_refs.py` and the list modes take it too). Set `order_weight` and `neighbour_tolerance` in that file.

`results.csv` gets `id,box,method,entry_id,alt_entry_id,confidence,unmatched_number,shot,order_flag,colour,colour_flag` per vehicle (box −1 for a frame with no vehicle; method `skipped` or `conflict` as above). Exit codes: 0 ok, 2 bad input (the message is on stderr), 3 missing package, 130 cancelled.

`--boxes-out PATH` also writes `boxes.json`, one record per vehicle: `{"collection", "thresholds" ({min_sim, min_margin, reference_margin}), "sponsor_keywords" ({word: tag prefix}), "entries": {id: {"team", "number", "tags", "refs"}}, "images": {id: {"shot", "status" (ok, no_vehicle or error), "file", "frame", "burst", "time" (capture epoch seconds, null if EXIF is missing), "note" (the detector's text when it found no vehicle), "boxes": [{"box", "bbox", "score" (detector confidence), "entry", "alt_entry", "method", "confidence", "candidates" (top 5 entry/similarity), "ocr", "ocr_trace" (the five most confident text regions, [confidence, text, height share of the crop]), "pod" ({yellow, aspect}: the camera-pod reading), "overlap" ("" , "trimmed" when read on the part not covered by a car in front, "hidden" when too little was left to match), "rescued" ({from, sim} when burst rescue found this box, else {}), "decided_by", "gap", "unmatched_number", "conflict", "hint" (prefixes, source, restricted, dropped, reason; {} without one)}]}}, "skipped": [ids]}`. For `none` boxes `decided_by` names the rule that failed (`no_references`, `below_min_sim`, `margin_too_small`) and `gap` how far short it fell. The plugin writes it to `last-run/<collection>.boxes.json` in its config directory; `--promote-boxes --boxes-in PATH` (same manifest, `id,filepath,""`) saves its confident boxes as references.

### Debug report

Every run also writes `last-run/<collection>.report.md` and `.report.json` in the plugin's config directory (the path is logged as `report: …` in `assisted_tagging.log`). Each vehicle gets one category: `identified`, `team-obvious` (team clear, driver not separated), `weak-match`, `no-references`, `number-unmatched`, `conflict` (disagrees with a tag you applied), `overlapped` (a car mostly covered by another in a pack: not matched, its visible part was too small), `already-tagged`, `no-vehicle`. The `.md` gives per-category counts and shares, the identified rate, median top-1 similarity and margin for `team-obvious` and `weak-match`, then the worst boxes per category with their candidates, the failing rule and a suggested lever. It has no images, so it pastes into chat as is. `--report-top N` (default 20) caps the boxes listed per category; the `.json` always has every row, each with its `category`. To rebuild a report from a saved `boxes.json` without re-identifying: `python report.py BOXES_JSON OUT_PREFIX --report-top N`. Photos that failed analysis are counted on a separate line, not in a category. Each `no-vehicle` image is listed with its burst and the detector's note (the strongest class and score it saw), which says whether a miss was a low score or a small box. Each box shows its detector score. Three more sections follow the summary (they appear when `--report-top` is above 0, and the `.json` carries them as `detector_bands`, `sponsor_suggestions` and `bursts`): `## detector score` (boxes and identified count per score band, to judge the `DETECTOR_MIN_SCORE` cutoff), `## sponsor keyword suggestions` (words OCR read on identified boxes of one tag prefix that aren't in `rules.sponsor_keywords` yet, with how many unidentified boxes each would hint), and `## bursts` (capture-time gaps within and between the groups the plugin read, per group id). `--archive-dir DIR` also copies `boxes.json` and the report into `DIR/<YYYYMMDD-HHMMSS>/` and keeps the newest 20 runs; the plugin passes `runs/` in its config directory, so earlier runs survive for comparison while `last-run/` stays the latest.

### Notes from the darktable source

- **`register_lib` takes eight positional arguments**: `(plugin_name, name, expandable, resetable, containers, widget, view_enter, view_leave)`. Leaving out `resetable` shifts the container table into a boolean slot and the panel never registers.
- **Registering a lib straight from `luarc` is a startup race.** darktable can report lighttable as the current view before the view has finished initialising, and a lib registered in that window is silently never attached (`src/views/view.c` documents it; the lua-scripts hit it as #19197). The plugin installs its panel from the `view-changed` event into lighttable instead, which fires only once the view is fully up.
- **`darktable-cli` never runs your `luarc`.** Since 5.6 the user `luarc` is loaded by `script_manager` (GUI only); before that the C code only loaded it when a GUI existed. `--luacmd` still runs, and it's the way to test headlessly. Anything GTK-wrapped (`register_lib`, `preferences.register`) blocks forever headless, so the plugin gates those on `dt.gui`.
- **Windows runs start with `start "" /B pythonw.exe launch.py <job>`.** The script and its arguments go in a job file, so none of them pass through cmd.exe. The command starts with `start`, not a quote, so cmd.exe keeps its quoted items intact (`lib/dtutils/system.lua` in darktable's lua-scripts wraps commands in a `.bat` because a command that starts with a quote gets mangled). There's no `.vbs`/`.bat` chain: antivirus behaviour checks (Bitdefender Advanced Threat Defense) flag a script host starting a hidden cmd from temp files. `pythonw.exe` must sit beside the `python.exe` the preference points at, as it does in a venv or a python.org install.
- **Native groups are read from `img.group_leader`.** Photos sharing a leader are one group, and a photo with no leader, or that is the only photo sharing its leader, is its own group. A RAW+JPEG import pair is a native group (darktable groups them on import), so it counts as one group under **Native groups**. Assisted Grouping writes native groups only when its **Apply darktable groups** is on; with it off, **Native groups** sees just the import pairs and any groups you made by hand.
- **Combobox `changed_callback` runs asynchronously, and every `selected` assignment fires it** (`src/lua/widget/combobox.c`, `src/bauhaus/bauhaus.c`), even when refilling the list. So the collection list acts only when its value differs from the stored collection.

## License

MIT, see [LICENSE](LICENSE).

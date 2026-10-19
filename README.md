# darktable-assisted-tagging

A tagging assistant for [darktable](https://www.darktable.org/) that recognises the motorsport vehicles in your photos. Select a batch in lighttable, click one button, and for every car or bike in each frame it will:

- **read its race number** and look it up in your entry list
- if the number isn't readable, **match its livery** against reference samples you picked
- if that's still unclear, **borrow the answer from the rest of the burst**
- tag the image with that entry's tags, e.g. `Motorsport|F1|Red Bull|Max Verstappen`

Teammates in identical liveries that it can't tell apart get only their shared team tag, never a guessed driver. Everything runs locally: a Lua plugin inside darktable and a Python identifier it shells out to. No API keys, no cloud. It only adds and removes tags from your entry list and its own `Assisted Tagging|…` tags; your other tags, ratings and colour labels are never touched.

Forked from [darktable-assisted-culling](https://github.com/louiswdavis/darktable-assisted-culling). The two can be installed side by side.

## Contents

- [Requirements](#requirements)
- [Install](#install)
- [Starting a collection](#starting-a-collection)
- [Building references](#building-references)
- [Identifying](#identifying)
- [Preferences](#preferences)
- [How it decides](#how-it-decides)
- [Tuning](#tuning)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

## Requirements

- darktable 5.6, built with Lua (the official builds are).
- Python 3.10+ with the packages in `python/requirements.txt`: `opencv-python-headless` (4.x, pinned `<5`), `numpy`, `Pillow`, `rawpy` and `onnxruntime`.
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

Download all four into a `models` folder in the repo. The plugin looks there, `.gitignore` already skips `*.onnx`, and `git pull` leaves them alone. From the repo root (Windows 10+ ships `curl`):

```
mkdir models
curl -L -o models/object_detection_yolox_2022nov.onnx https://github.com/opencv/opencv_zoo/raw/main/models/object_detection_yolox/object_detection_yolox_2022nov.onnx
curl -L -o models/text_detection_en_ppocrv3_2023may.onnx https://github.com/opencv/opencv_zoo/raw/main/models/text_detection_ppocr/text_detection_en_ppocrv3_2023may.onnx
curl -L -o models/text_recognition_CRNN_EN_2021sep.onnx https://github.com/opencv/opencv_zoo/raw/main/models/text_recognition_crnn/text_recognition_CRNN_EN_2021sep.onnx
curl -L -o models/dinov2_small.onnx https://huggingface.co/onnx-community/dinov2-small/resolve/main/onnx/model.onnx
```

| File | Size | Job | Source, licence |
|---|---|---|---|
| `object_detection_yolox_2022nov.onnx` | 36 MB | finds the cars and bikes | OpenCV model zoo, Apache-2.0 |
| `text_detection_en_ppocrv3_2023may.onnx` | 2.4 MB | finds text on each vehicle | OpenCV model zoo (PP-OCRv3), Apache-2.0 |
| `text_recognition_CRNN_EN_2021sep.onnx` | 34 MB | reads that text | OpenCV model zoo (CRNN), Apache-2.0 |
| `dinov2_small.onnx` | 89 MB | livery matching | DINOv2 ViT-S/14 via onnx-community, Apache-2.0 |

Optional models. The plugin works without them:

- **Segmentation**, for pack shots with overlapping cars. With it in `models`, a box that overlaps another is read through a car-shaped mask, with the background and the neighbouring car painted grey.
- **Larger livery embedder.** Not used unless you set **Assisted Tagging: livery embedder model** (preferences → lua options) to `dinov2_base.onnx`; the next run then re-embeds every reference. Compare it first with `python/eval_matching.py COLLECTION_DIR --embedder models/dinov2_base.onnx --fresh-embed` (re-embeds the refs with that model in memory; `index.npz` is untouched).

```
curl -L -o models/image_segmentation_efficientsam_ti_2025april.onnx https://github.com/opencv/opencv_zoo/raw/main/models/image_segmentation_efficientsam/image_segmentation_efficientsam_ti_2025april.onnx
curl -L -o models/dinov2_base.onnx https://huggingface.co/onnx-community/dinov2-base/resolve/main/onnx/model.onnx
```

| File | Size | Job | Source, licence |
|---|---|---|---|
| `image_segmentation_efficientsam_ti_2025april.onnx` | | outlines an overlapped car | OpenCV model zoo (EfficientSAM), Apache-2.0 |
| `dinov2_base.onnx` | about 350 MB | livery matching, larger than `dinov2_small.onnx` | DINOv2 ViT-B/14 via onnx-community, Apache-2.0 |

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

A people entry has only `id` and `tags`; references are photos with exactly one face, so tag those photos by hand first. Choose `rules.min_sim`, `margin` and `min_face_px` with `python python/eval_people.py <collection> --face-detector … --face-recognizer …`.

### 3. darktable side

darktable's config directory is `~/.config/darktable` on Linux/macOS and `%LOCALAPPDATA%\darktable` on Windows. Link the plugin into it and load it from `luarc`.

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

### 4. Point the plugin at the repo

Start darktable, open **preferences → lua options**, and set **Assisted Tagging: plugin folder** to this repo's folder. From there the plugin finds `python/identify.py`, the `models` folder and the `.venv` by itself. Set **Assisted Tagging: Python interpreter** only if yours lives somewhere else.

## Starting a collection

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

### From already-tagged images (recommended)

If you've already hand-tagged a handful of photos — one per competitor, e.g. `Motorsport|F1|Red Bull` on both Red Bull cars and `Motorsport|F1|Red Bull|Max Verstappen` on just his — the panel can turn those into a working collection in one click. This isn't motorsport-specific: it only ever reads whatever `A|B|C`-style tags you've already used, so the same button builds a collection for any set of visually-distinguishable, hierarchically-tagged subjects.

1. In lighttable, select a handful of already-tagged photos — **at least 2 per target**, from different angles.
2. Under **new collection** in the panel, type a name for the collection, e.g. `F1 2026`.
3. Click **Create collection from tagged images**.

It reads each selected image's tags down to wherever two images stop being identical: images carrying the exact same tags become one entry, and whatever tag is unique to a photo (the driver tag) is what tells two teammates apart. From that it:

- creates the collection folder with an `entries.json` built from those tag sets, inferring each entry's `team` where a tag is shared with some but not all of the other entries, and its race `number` when the deepest tag's leaf is 1-3 digits (e.g. a `Car|Number|44` convention sets `number: "44"` automatically)
- adds every selected image as a reference sample of its entry, exactly like [**Add tagged images as references**](#building-references)
- switches the panel to the new collection and reloads it

Two kinds of selected image don't become an entry, and are reported in the done message rather than silently dropped:

- an image with no tag that looks like `A|B` has nothing to build an entry from
- a tag that only 1 selected image carries is skipped rather than turned into a single-sample entry — a lone sample tells the matcher nothing about how that target varies across angles and light, so it's better surfaced as "needs more references" than quietly matched (and likely mismatched) later. Select at least 2 photos per target to avoid this.

If you want number-based identification but your tags don't already encode the number, or you want custom [rules](#rules), add those by hand afterward (see below). If a collection with that name already exists, nothing is overwritten — pick a new name, or switch to the existing one and use **Add tagged images as references** instead.

### From an example

No tagged photos yet, or just want to see the shape of a working `entries.json`? The **example** dropdown in the panel lists the collections shipped in [`examples/`](examples) — no images needed, since these ship with their structure already filled in (with placeholder names, not real references):

1. Pick one in the **example** dropdown.
2. Click **View example** to open its `entries.json` in your editor and read it, or
3. type a name under **new collection** and click **Create collection from example** to copy it into a real collection.

Either way, a created collection still needs its placeholder names replaced with your own competitors (and references added, for anything you want livery-matched) before it identifies anything correctly — click **Edit entries.json** in the panel's **collection** section at any time to open the *active* collection's file the same way.

### By hand

Write `entries.json` yourself for more control than tags alone give you: a race `number`, or custom [rules](#rules). It holds the collection's **entries**, one per competitor, and its **rules**: what each outcome tags. For example:

```json
{
  "rules": {
    "team_only": "shared tags",
    "unidentified": ["Motorsport|F1|Unidentified"],
    "diagnostics": { "burst": "" }
  },
  "entries": [
    { "id": "VER", "number": "1",  "team": "Red Bull", "tags": ["Motorsport|F1|Red Bull", "Motorsport|F1|Red Bull|Max Verstappen"] },
    { "id": "TSU", "number": "22", "team": "Red Bull", "tags": ["Motorsport|F1|Red Bull", "Motorsport|F1|Red Bull|Yuki Tsunoda"] },
    { "id": "SAFETY", "tags": ["Motorsport|F1|Safety Car"] }
  ]
}
```

A file that's just the `[ … ]` list of entries works too, with the default rules — this is exactly the shape **Create collection from tagged images** writes, so you can build one that way and then hand-edit it in to add numbers or rules.

[`examples/`](examples) has three collections — pick one from the panel's **example** dropdown (see [above](#from-an-example)), or copy its folder into the collections folder by hand. Each has a README on what it shows and how to supply its references:

- [`f1-season`](examples/f1-season): a season with near-identical teammates, a one-off livery and number-less cars
- [`btcc-event`](examples/btcc-event): one race weekend, with a "check me" tag for misses and no team-only tags
- [`minimal`](examples/minimal): a bare entry list on the default rules

### Entries

| Field | Required | Rules |
|---|---|---|
| `id` | yes | unique within the collection; it's also the folder name under `refs/`, so it can't contain `, ; " / \ : * ? < > \|` |
| `tags` | yes | one or more darktable tag names (`\|` makes a hierarchy); no `,` `;` or `"` |
| `number` | no | the race number, 1–3 digits. Leave it out for a car with no number; it can then only be identified by livery. Two entries with the same number are allowed, but that number then identifies neither. |
| `team` | no | entries with the same team can fall back to their shared tags when their liveries are too close to call |

The tags are yours to design: put the team tag on both teammates and the driver tag on one, and a team-only result carries exactly the team tag. The examples leave the year out of the tags: the collection already separates seasons for matching, and darktable's collections module filters by capture date. A **livery change** mid-season is a new entry (`VER-miami`, with the same tags and no `number`, so the number still identifies `VER`) or a new collection.

### Rules

Every key is optional; leave one out for its default.

| Rule | Default | What it does |
|---|---|---|
| `team_only` | `"shared tags"` | when two teammates are too close to call: `"shared tags"` adds the tags both entries carry, `"none"` adds no collection tags (only the *Team only* diagnostic) |
| `unidentified` | `[]` | tags added to an image where no vehicle was identified, e.g. a "check me" tag for the shoot |
| `diagnostics` | the `Assisted Tagging\|Identification\|…` tags | the diagnostic tag per outcome (`number`, `livery`, `burst`, `pooled`, `team`, `none`, `number_seen`, plus `shot_solo`, `shot_pack`, `shot_crowded`); rename one, or set it to `""` to write none. The *diagnostic tags* preference still turns them all off. |

| `sponsor_keywords` | `{}` | maps a lowercase sponsor word to the tag prefix of its team, e.g. `{"petronas": "Motorsport\|F1\|Mercedes"}`. A word read on a car (OCR confidence 0.90+; one typo allowed in words of 6+ letters) narrows matching to that team. Sponsors of two teams on one car give no hint. A prefix no entry sits under stops the run. |
| `partial_references` | `false` | **Add tagged images as references** also accepts a solo shot tagged only to team level (e.g. `Motorsport\|F1\|Red Bull`) and saves it as a team reference under `refs/@team@…`. When no driver is clear but one team's references lead clearly, the result is *team* (shared tags only). |

An unknown key, or a misspelt one, stops the run and names it, so a typo can't silently do nothing.

### Checking what it will tag

Click **Show tag plan** in the panel. It writes `tag-plan.txt` next to the collection's `entries.json`, listing exactly what each outcome writes: every entry's tags and reference count, the team-only tags for each pair of teammates, the unidentified tags, and the diagnostic tags. It also lists entries that can only be identified by number, and entries that can't be identified at all until they have references. The file is rewritten on every run and **Reload**, so it always matches `entries.json`.

After editing `entries.json`, click **Reload** in the panel. A mistake in the file stops the run with the file name and what's wrong.

## Building references

Numbers aren't readable in every shot (rear views, motion blur, a number hidden by the halo), so each entry also needs a few **reference samples**: crops of that car the plugin compares new photos against. 3–5 per car from different angles is a good start; add more for the angles it gets wrong. **Create collection from tagged images** already does this for the images it was given; add more at any time with the panel's **references** section, below **new collection** and **collection**:

- **Add as reference**: pick the entry in the **entry** list, select photos of that car, click. The largest vehicle in each photo is cropped and saved under that entry. A photo where no vehicle is found is saved whole, and the done message says how many.
- **Add tagged images as references**: select photos you've already tagged by hand. Each one carrying *all* of one entry's tags is added under that entry. A photo with only a shared team tag, or with two drivers' tags, is skipped.
- **Add confident vehicles from last run**: select photos from the last **Identify selection** run. Each vehicle that run was sure of (its number was read, or its livery led the runner-up by `REFERENCE_MIN_MARGIN`) is saved under the entry it found. This works for pack shots: the saved crop is that one car, not the whole photo, so the entry's tag doesn't have to describe the frame. Burst, team-only and held-back results are never saved. Photos changed since the run are skipped.
- **Audit references**: needs no selected photos. Refreshes the collection's `index.npz` from `refs/` (deleted or moved crops drop out, new ones are embedded), then writes `ref-audit.txt` in the collection folder. Sections: *strongest candidates* (refs flagged by two or more of the checks below; start there), *mislabel suspects* (closer to another entry's refs than its own by 0.2 or more), *cross-entry copies* (near-identical crop filed under two entries), *outliers* (far from the rest of its entry), *odd crops* (crop size or shape far from the entry's usual: a distant car, a whole frame, a nose-only cut; unusual angles are not flagged by this one), *whole frames* (the vehicle detector finds no car in the ref, or one under 15% of it, so scenery drives its matches; re-crop or delete), *colour outliers* (livery hue and saturation unlike the entry's typical colours, brightness ignored; `looks like [entry]` names a better colour match) and *redundant* (near-duplicates within an entry). Nothing is moved or deleted: check the listed crops, then delete or move them yourself. Entries with 4 to 5 or more refs are needed for the outlier checks. It also runs from a terminal: `python python/audit_refs.py COLLECTION_DIR` (embedding, colour and crop checks only, no index refresh; add `--detector path/to/yolox.onnx` for the whole-frame check). The run log is rewritten, so audit before reading an Identify log.

Each sample is a JPG in `refs/<entry id>/`, named after the darktable image id. Adding the same photo again replaces its sample. To remove a bad sample, delete its JPG; the next run notices.

## Identifying

In lighttable, select a batch and click **Identify selection** in the **Assisted Tagging** panel. Progress shows in darktable's message area; click the button again to cancel. A cancelled run changes no tags.

Every vehicle that gets an entry adds that entry's tags to the image, so a photo of two cars battling gets both; the collection's [rules](#rules) decide what team-only and unidentified images get. With the *diagnostic tags* preference on (the default), images also get a tag saying how they were identified. These are the default names; rules can rename or drop each one:

| Tag | Meaning |
|---|---|
| `Assisted Tagging\|Identification\|By number` | its race number was read |
| `Assisted Tagging\|Identification\|By livery` | matched against reference samples |
| `Assisted Tagging\|Identification\|By burst` | the rest of its burst agreed on one entry |
| `Assisted Tagging\|Identification\|By pooled burst` | the experimental `burst_livery_pooling` rule resolved it from its burst's pooled livery similarity |
| `Assisted Tagging\|Identification\|Team only` | two teammates were too close to call; only their shared tags were added |
| `Assisted Tagging\|Identification\|Unidentified` | no vehicle, or no confident match |
| `Assisted Tagging\|Identification\|Number seen\|<digits>` | OCR read these digits but they didn't resolve to one entry; added alongside the outcome tag |
| `Assisted Tagging\|Identification\|Shot\|Solo` | one vehicle was found in the frame |
| `Assisted Tagging\|Identification\|Shot\|Pack` | two or three vehicles were found |
| `Assisted Tagging\|Identification\|Shot\|Crowded` | the detector's limit (`MAX_BOXES`) was reached, so there may be more cars than were identified |

Filter on `Assisted Tagging|Identification|By livery` and `Assisted Tagging|Identification|Unidentified` in the **collections** module to spot-check the uncertain ones; an image it got wrong is often a good new reference.

Re-running is safe: each image's entry and diagnostic tags are synced to the new result, so a frame that moves from one driver to another loses the old driver's tags. Tags that aren't in the active collection are never touched.

### Tags you apply by hand

The plugin keeps a ledger (`assisted_tagging/ledger.csv` in darktable's config directory) of the tags it attached to each image. An entry tag on an image that isn't in its ledger is yours, at any depth (team or driver), and a run never removes it. So a photo you tagged to a team stays that way even when the run can't tell the driver.

- A **solo shot** whose result disagrees with the tags you applied is left as you had it: nothing is added, it doesn't get the *Unidentified* tags, and the done message counts it. Packs aren't checked, since you may have tagged just one of the cars.
- A **team tag** you applied (a tag that is a prefix of an entry's tags, such as `Motorsport|F1|Red Bull`) is a **hint** on a solo shot: matching is limited to the entries under it. If none of them looks similar enough, or the number read belongs to a car outside it, the hint is dropped and the normal match runs. The report lists each hint and any that were dropped. Packs get no tag hints, since the tag may describe only one car.
- An image already carrying all of one entry's tags is **skipped** without being analysed.
- To let a run replace your tags, tick **Replace manual tags** under **Identify selection**. It applies to the next run only and clears itself.
- If you remove a tag the plugin attached and later apply it again by hand, it counts as yours.
- Images tagged by an older version have no ledger, so all their entry tags count as yours.

## Preferences

All under **preferences → lua options**.

| Preference | Default | What it does |
|---|---|---|
| Assisted Tagging: Python interpreter | empty (the repo's `.venv`) | Python with `requirements.txt` installed |
| Assisted Tagging: plugin folder | empty (auto-detect) | This repo's folder; `python/`, `models/`, `examples/` and `.venv` are all found inside it. A folder without `python/identify.py` is an error |
| Assisted Tagging: collections folder | empty (`assisted_tagging/collections` in the config directory) | Where collections live |
| Assisted Tagging: livery embedder model | empty (`dinov2_small.onnx`) | File name in `models/` used to compare liveries, e.g. `dinov2_base.onnx`. Changing it re-embeds every reference on the next run |
| Assisted Tagging: diagnostic tags | on | The `By number` / `By livery` / … tags above; off removes them on the next run |
| Assisted Tagging: burst gap (seconds) | 2 | Photos closer together than this are one burst |

## How it decides

```
assisted_tagging.lua groups the selection into bursts by capture time, writes manifest.csv, runs identify.py
        |
        v
identify.py, per frame:  decode at full resolution → YOLOX vehicle boxes (up to 4)
        |                → per box: crop → read numbers → DINOv2 embedding
        v
per box:   sponsor words on the car (or a team tag you applied) narrow the candidates to one team, then
           one number matches one entry                 → number
           else best livery match clear of the next one → livery
           else best two are teammates                  → team (shared tags only)
           else                                         → none
        |
        v
per burst: frames with nothing identified take the burst's entry
           when 2+ frames agree on it and none disagree → burst
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
| `burst` | the rest of the burst agreeing, when number and livery didn't | `…\|By burst` |
| `pooled` | the burst's pooled livery similarity (experimental `burst_livery_pooling` rule) | `…\|By pooled burst` |
| `team` | two teammates too close to call by livery (shared tags only) | `…\|Team only` |
| `none` | nothing matched | `…\|Unidentified` |

Frames are decoded at native resolution (a raw file's embedded preview) and each vehicle is cropped from that before reading its number, since a number only a few pixels tall in a downscaled frame is readable in the crop. Detection, OCR text and embeddings are cached per frame in `assisted_tagging/cache.sqlite` in darktable's config directory. Matching isn't, so adding references or editing `entries.json` takes effect on the next run without decoding anything again. The cache key includes the file (path, modified time, size), every model file and the constants that change the cached data; unused entries are dropped after 90 days. Delete the file to start over.

## Tuning

The thresholds are starting points, not tuned defaults. Each is a named constant:

| Constant | File | Default | What it does |
|---|---|---|---|
| `OCR_MIN_SCORE` | `ocr.py` | 0.80 | how sure the text detector must be before a number is read |
| `MATCH_MIN_SIM` | `match.py` | 0.60 | the livery similarity a match needs at all |
| `MATCH_MIN_MARGIN` | `match.py` | 0.10 | how far the best entry must be ahead of the next one. Similarities are centred on the references' mean once a collection has 20+ references, which spreads them out, so the gate is wider than it looks; `python/eval_matching.py` sweeps it on your own references |
| `BURST_MIN_AGREE` | `match.py` | 2 | frames that must agree before a burst fills in the rest |
| `REFERENCE_MIN_MARGIN` | `match.py` | 0.10 | how far a livery match must lead to be saved by **Add confident vehicles from last run** |
| `MIN_BOX_FRAC` | `vehicles.py` | 0.005 | the smallest vehicle, as a share of the frame, worth identifying |
| `MAX_BOXES` | `vehicles.py` | 4 | vehicles identified per frame |
| `CROP_DIM` | `vehicles.py` | 640 | the long side each vehicle crop is reduced to |
| `DETECTOR_MIN_SCORE` | `vehicles.py` | 0.20 | the confidence a vehicle detection needs |

The run log has one line per vehicle with the numbers read and the top two livery matches with their similarity, e.g. `box 0: livery VER (OCR -; livery VER 0.712, TSU 0.694)`. Read a few from a shoot to see where the right and wrong answers fall before changing `MATCH_MIN_SIM` or `MATCH_MIN_MARGIN`.

After changing `OCR_MIN_SCORE`, `MIN_BOX_FRAC`, `CROP_DIM` or the detection, OCR or embedding code, bump `IDENTIFY_CACHE_VERSION` in `identify.py` (`CROP_DIM`, `MIN_BOX_FRAC`, `BOX_MARGIN_TRIM`, `OCR_MIN_SCORE` and `DETECTOR_MIN_SCORE` are already in the cache key; code changes aren't). Changes to `match.py` never need it.

**Higher-detail re-read.** Frames are first analysed from the RAW's embedded preview (fast). After the first match, each box left unidentified (`none`, or `team` with the driver not separated; overlapped boxes excluded) is re-read from a half-size decode of the RAW itself, which gives OCR and the embedding several times the pixels on a small car. Boxes stay in preview coordinates; only their crops come from the sharper decode. Non-RAW files and previews already near full width are left alone. A re-read replaces that box's OCR, embedding and colour only, and the box record carries `"hires": true`. The re-read of a frame is cached separately (`hires-1`), so a rerun doesn't decode again. Reference crops are still taken from previews.

**Car-shaped masks.** When the segmentation model is present, each box that overlaps another (`overlap.py` geometry, hidden boxes excluded) is outlined by EfficientSAM, prompted with three points on the car body. The crop used for OCR, the embedding and colour has everything outside the outline painted grey. The mask must not contain the centre of an overlapping box and must cover at least 15% of the visible box, otherwise the plain crop is used. The box record carries `"masked": true`. Pod readings and reference crops are unmasked. Having the model adds `mask-1` to the cache key, so the first run with it re-reads every frame.

## Troubleshooting

- **The panel isn't there.** Start darktable with `-d lua` and look for `LUA ERROR` in the log. On Windows the log is `Documents\Darktable\darktable-log.txt`.
- **Every run writes a log** to `assisted_tagging.log` in darktable's config directory (e.g. `%LOCALAPPDATA%\darktable` on Windows); the run before it is kept as `assisted_tagging.prev.log`. It has the exact command, the reference counts per entry, one line per vehicle with what was read and matched, and any per-image errors.
- **"…/entries.json: …"** The run stopped on a mistake in that file; the message says which entry and what's wrong.
- **"… model not found: …"** A model file is missing. Download it into `models/` (see [Install](#2-models)) or fix its preference.
- **"Python is missing a package."** The interpreter the plugin uses doesn't have `requirements.txt` installed; the log names the package.
- **"no collections yet."** Create a folder with an `entries.json` in the collections folder the message names, then click **Reload**.
- **Everything comes back `Unidentified`.** Check the log's `references:` line: an entry with 0 references can only be found by its number.
- **"cache … is unreadable".** Delete `assisted_tagging/cache.sqlite` in darktable's config directory; the next run rebuilds it.

## Development

### Tests

From the repo root. The Python tests use synthetic images and stub models, so they need no model files:

```
# Linux / macOS
.venv/bin/python python/test_match.py
.venv/bin/python python/test_report.py
.venv/bin/python python/test_sponsors.py
.venv/bin/python python/test_identify.py
.venv/bin/python python/test_reference_store.py

# Windows
.venv\Scripts\python python\test_match.py
.venv\Scripts\python python\test_report.py
.venv\Scripts\python python\test_sponsors.py
.venv\Scripts\python python\test_identify.py
.venv\Scripts\python python\test_reference_store.py
```

The pure-logic half of the plugin runs under any Lua 5.4 (`cd lua && lua test_assisted_tagging.lua`). No `lua` binary? `pip install lupa` in the venv, then:

```
.venv/bin/python -c "import lupa; L=lupa.LuaRuntime(); L.execute('package.path=\"./lua/?.lua;\"..package.path; dofile(\"lua/test_assisted_tagging.lua\")')"
```

### Running the identifier on its own

`manifest.csv` is `id,filepath,burst_id` per line, with an optional fourth column, the `;`-joined entry tags the user applied by hand (an image carrying all of one entry's are skipped; a solo result sharing none of them is held back as `conflict`):

```
python python/identify.py manifest.csv results.csv --collections-root collections --collection "F1 2026" \
    --detector models/object_detection_yolox_2022nov.onnx --ocr-det models/text_detection_en_ppocrv3_2023may.onnx \
    --ocr-rec models/text_recognition_CRNN_EN_2021sep.onnx --embedder models/dinov2_small.onnx
```

`results.csv` gets `id,box,method,entry_id,alt_entry_id,confidence,unmatched_number,shot` per vehicle (box −1 for a frame with no vehicle; method `skipped` or `conflict` as above). Exit codes: 0 ok, 2 bad input (the message is on stderr), 3 missing package, 130 cancelled.

`--boxes-out PATH` also writes `boxes.json`, one record per vehicle: `{"collection", "thresholds" ({min_sim, min_margin, reference_margin}), "sponsor_keywords" ({word: tag prefix}), "entries": {id: {"team", "number", "tags", "refs"}}, "images": {id: {"shot", "status" (ok, no_vehicle or error), "file", "frame", "burst", "time" (capture epoch seconds, null if EXIF is missing), "note" (the detector's text when it found no vehicle), "boxes": [{"box", "bbox", "score" (detector confidence), "entry", "alt_entry", "method", "confidence", "candidates" (top 5 entry/similarity), "ocr", "ocr_trace" (the five most confident text regions, [confidence, text]), "pod" ({yellow, aspect}: the camera-pod reading), "overlap" ("" , "trimmed" when read on the part not covered by a car in front, "hidden" when too little was left to match), "rescued" ({from, sim} when burst rescue found this box, else {}), "decided_by", "gap", "unmatched_number", "conflict", "hint" (prefixes, source, restricted, dropped, reason; {} without one)}]}}, "skipped": [ids]}`. For `none` boxes `decided_by` names the rule that failed (`no_references`, `below_min_sim`, `margin_too_small`) and `gap` how far short it fell. The plugin writes it to `last-run/<collection>.boxes.json` in its config directory; `--promote-boxes --boxes-in PATH` (same manifest, `id,filepath,""`) saves its confident boxes as references.

### Debug report

Every run also writes `last-run/<collection>.report.md` and `.report.json` in the plugin's config directory (the path is logged as `report: …` in `assisted_tagging.log`). Each vehicle gets one category: `identified`, `team-obvious` (team clear, driver not separated), `weak-match`, `no-references`, `number-unmatched`, `conflict` (disagrees with a tag you applied), `overlapped` (a car mostly covered by another in a pack: not matched, its visible part was too small), `already-tagged`, `no-vehicle`. The `.md` gives per-category counts and shares, the identified rate, median top-1 similarity and margin for `team-obvious` and `weak-match`, then the worst boxes per category with their candidates, the failing rule and a suggested lever. It has no images, so it pastes into chat as is. `--report-top N` (default 20) caps the boxes listed per category; the `.json` always has every row, each with its `category`. To rebuild a report from a saved `boxes.json` without re-identifying: `python report.py BOXES_JSON OUT_PREFIX --report-top N`. Photos that failed analysis are counted on a separate line, not in a category. Each `no-vehicle` image is listed with its burst and the detector's note (the strongest class and score it saw), which says whether a miss was a low score or a small box. Each box shows its detector score. Three more sections follow the summary (they appear when `--report-top` is above 0, and the `.json` carries them as `detector_bands`, `sponsor_suggestions` and `bursts`): `## detector score` (boxes and identified count per score band, to judge the `DETECTOR_MIN_SCORE` cutoff), `## sponsor keyword suggestions` (words OCR read on identified boxes of one tag prefix that aren't in `rules.sponsor_keywords` yet, with how many unidentified boxes each would hint), and `## bursts` (capture-time gaps within and between bursts, to judge burst splitting). `--archive-dir DIR` also copies `boxes.json` and the report into `DIR/<YYYYMMDD-HHMMSS>/` and keeps the newest 20 runs; the plugin passes `runs/` in its config directory, so earlier runs survive for comparison while `last-run/` stays the latest.

### Notes from the darktable source

- **`register_lib` takes eight positional arguments**: `(plugin_name, name, expandable, resetable, containers, widget, view_enter, view_leave)`. Leaving out `resetable` shifts the container table into a boolean slot and the panel never registers.
- **Registering a lib straight from `luarc` is a startup race.** darktable can report lighttable as the current view before the view has finished initialising, and a lib registered in that window is silently never attached (`src/views/view.c` documents it; the lua-scripts hit it as #19197). The plugin installs its panel from the `view-changed` event into lighttable instead, which fires only once the view is fully up.
- **`darktable-cli` never runs your `luarc`.** Since 5.6 the user `luarc` is loaded by `script_manager` (GUI only); before that the C code only loaded it when a GUI existed. `--luacmd` still runs, and it's the way to test headlessly. Anything GTK-wrapped (`register_lib`, `preferences.register`) blocks forever headless, so the plugin gates those on `dt.gui`.
- **Windows shell-outs go through a `.bat` file**, following `lib/dtutils/system.lua` in darktable's lua-scripts: cmd.exe mangles a command line with more than one quoted item. In that file, write the exit code with the redirect first (`> "f" echo %ERRORLEVEL%`): `echo 0> "f"` reads as "redirect handle 0" and leaves `f` empty.
- **Combobox `changed_callback` runs asynchronously, and every `selected` assignment fires it** (`src/lua/widget/combobox.c`, `src/bauhaus/bauhaus.c`), even when refilling the list. So the collection list acts only when its value differs from the stored collection.

## License

MIT, see [LICENSE](LICENSE).

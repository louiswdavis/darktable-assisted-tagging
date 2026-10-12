# darktable-assisted-tagging

A tagging assistant for [darktable](https://www.darktable.org/) that recognises the motorsport vehicles in your photos. Select a batch in lighttable, click one button, and for every car or bike in each frame it will:

- **read its race number** and look it up in your entry list
- if the number isn't readable, **match its livery** against reference samples you picked
- if that's still unclear, **borrow the answer from the rest of the burst**
- tag the image with that entry's tags, e.g. `Motorsport|F1|2026|Red Bull|Max Verstappen`

Teammates in identical liveries that it can't tell apart get only their shared team tag, never a guessed driver. Everything runs locally: a Lua plugin inside darktable and a Python identifier it shells out to. No API keys, no cloud. It only adds and removes tags from your entry list and its own `Assisted Tagging|…` tags; your other tags, ratings and colour labels are never touched.

Forked from [darktable-assisted-culling](https://github.com/louiswdavis/darktable-assisted-culling). The two can be installed side by side.

## Contents

- [Requirements](#requirements)
- [Install](#install)
- [Collections and entries](#collections-and-entries)
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

Download all four into a `models` folder in the repo. When the model preferences are empty the plugin looks there, `.gitignore` already skips `*.onnx`, and `git pull` leaves them alone. From the repo root (Windows 10+ ships `curl`):

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

### 3. darktable side

darktable's config directory is `~/.config/darktable` on Linux/macOS and `%LOCALAPPDATA%\darktable` on Windows. Link the plugin into it and load it from `luarc`.

Linux / macOS:

```
mkdir -p ~/.config/darktable/lua/contrib
ln -s "$(pwd)/lua/tagging.lua" ~/.config/darktable/lua/contrib/tagging.lua
echo 'require "contrib/tagging"' >> ~/.config/darktable/luarc
```

Windows (Command Prompt). Creating symbolic links needs an Administrator prompt unless Developer Mode is enabled.

```
if not exist "%LOCALAPPDATA%\darktable\lua\contrib" mkdir "%LOCALAPPDATA%\darktable\lua\contrib"
mklink "%LOCALAPPDATA%\darktable\lua\contrib\tagging.lua" "%CD%\lua\tagging.lua"
echo require "contrib/tagging" >> "%LOCALAPPDATA%\darktable\luarc"
```

### 4. Point the plugin at the repo

Start darktable, open **preferences → lua options**, and set **Assisted Tagging: identify.py** to `python/identify.py` in this repo. From that path the plugin finds the repo's `.venv` and `models` folder by itself. Set **Assisted Tagging: Python interpreter** or the model preferences only if yours live somewhere else.

## Collections and entries

A **collection** is one entry list plus its reference samples: normally one series and season (`F1 2026`), or one event (`BTCC 2026 Brands Hatch`). Collections live in the collections folder, by default `assisted_tagging/collections` in darktable's config directory (the panel creates it the first time it loads). Each one is a folder:

```
collections/
  F1 2026/
    entries.json      # you write this
    refs/             # the plugin fills this when you add references
      VER/1234.jpg
      index.npz
```

`entries.json` holds the collection's **entries**, one per competitor, and its **rules**: what each outcome tags. [`docs/entries.example.json`](docs/entries.example.json) is a starting point:

```json
{
  "rules": {
    "team_only": "shared tags",
    "unidentified": ["Motorsport|F1|2026|Unidentified"],
    "diagnostics": { "burst": "" }
  },
  "entries": [
    { "id": "VER", "number": "1",  "team": "Red Bull", "tags": ["Motorsport|F1|2026|Red Bull", "Motorsport|F1|2026|Red Bull|Max Verstappen"] },
    { "id": "TSU", "number": "22", "team": "Red Bull", "tags": ["Motorsport|F1|2026|Red Bull", "Motorsport|F1|2026|Red Bull|Yuki Tsunoda"] },
    { "id": "SAFETY", "tags": ["Motorsport|F1|2026|Safety Car"] }
  ]
}
```

A file that's just the `[ … ]` list of entries works too, with the default rules.

### Entries

| Field | Required | Rules |
|---|---|---|
| `id` | yes | unique within the collection; it's also the folder name under `refs/`, so it can't contain `, ; " / \ : * ? < > \|` |
| `tags` | yes | one or more darktable tag names (`\|` makes a hierarchy); no `,` `;` or `"` |
| `number` | no | the race number, 1–3 digits. Leave it out for a car with no number; it can then only be identified by livery. Two entries with the same number are allowed, but that number then identifies neither. |
| `team` | no | entries with the same team can fall back to their shared tags when their liveries are too close to call |

The tags are yours to design: put the team tag on both teammates and the driver tag on one, and a team-only result carries exactly the team tag. A **livery change** mid-season is a new entry (`VER-miami`, with the same tags) or a new collection.

### Rules

Every key is optional; leave one out for its default.

| Rule | Default | What it does |
|---|---|---|
| `team_only` | `"shared tags"` | when two teammates are too close to call: `"shared tags"` adds the tags both entries carry, `"none"` adds no collection tags (only the *Team only* diagnostic) |
| `unidentified` | `[]` | tags added to an image where no vehicle was identified, e.g. a "check me" tag for the shoot |
| `diagnostics` | the five `Assisted Tagging\|…` tags | the diagnostic tag per outcome (`number`, `livery`, `burst`, `team`, `none`); rename one, or set it to `""` to write none. The *diagnostic tags* preference still turns them all off. |

An unknown key, or a misspelt one, stops the run and names it, so a typo can't silently do nothing.

### Checking what it will tag

Click **Show tag plan** in the panel. It writes `tag-plan.txt` next to the collection's `entries.json`, listing exactly what each outcome writes: every entry's tags and reference count, the team-only tags for each pair of teammates, the unidentified tags, and the diagnostic tags. It also lists entries that can only be identified by number, and entries that can't be identified at all until they have references. The file is rewritten on every run and **Reload**, so it always matches `entries.json`.

After editing `entries.json`, click **Reload** in the panel. A mistake in the file stops the run with the file name and what's wrong.

## Building references

Numbers aren't readable in every shot (rear views, motion blur, a number hidden by the halo), so each entry also needs a few **reference samples**: crops of that car the plugin compares new photos against. 3–5 per car from different angles is a good start; add more for the angles it gets wrong.

Two buttons in the panel's **references** section:

- **Add as reference**: pick the entry in the **entry** list, select photos of that car, click. The largest vehicle in each photo is cropped and saved under that entry. A photo where no vehicle is found is saved whole, and the done message says how many.
- **Add tagged images as references**: select photos you've already tagged by hand. Each one carrying *all* of one entry's tags is added under that entry. A photo with only a shared team tag, or with two drivers' tags, is skipped.

Each sample is a JPG in `refs/<entry id>/`, named after the darktable image id. Adding the same photo again replaces its sample. To remove a bad sample, delete its JPG; the next run notices.

## Identifying

In lighttable, select a batch and click **Identify selection** in the **Assisted Tagging** panel. Progress shows in darktable's message area; click the button again to cancel. A cancelled run changes no tags.

Every vehicle that gets an entry adds that entry's tags to the image, so a photo of two cars battling gets both; the collection's [rules](#rules) decide what team-only and unidentified images get. With the *diagnostic tags* preference on (the default), images also get a tag saying how they were identified. These are the default names; rules can rename or drop each one:

| Tag | Meaning |
|---|---|
| `Assisted Tagging\|By number` | its race number was read |
| `Assisted Tagging\|By livery` | matched against reference samples |
| `Assisted Tagging\|By burst` | the rest of its burst agreed on one entry |
| `Assisted Tagging\|Team only` | two teammates were too close to call; only their shared tags were added |
| `Assisted Tagging\|Unidentified` | no vehicle, or no confident match |

Filter on `Assisted Tagging|By livery` and `|Unidentified` in the **collections** module to spot-check the uncertain ones; an image it got wrong is often a good new reference.

Re-running is safe: each image's entry and diagnostic tags are synced to the new result, so a frame that moves from one driver to another loses the old driver's tags. Tags that aren't in the active collection are never touched.

## Preferences

All under **preferences → lua options**.

| Preference | Default | What it does |
|---|---|---|
| Assisted Tagging: Python interpreter | empty (the repo's `.venv`) | Python with `requirements.txt` installed |
| Assisted Tagging: identify.py | empty (auto-detect) | Path to the identifier; set it, and the venv and models are found from it |
| Assisted Tagging: vehicle detector model | empty (`models/` in the repo) | YOLOX `.onnx` |
| Assisted Tagging: number detection model | empty (`models/`) | PP-OCRv3 `.onnx` |
| Assisted Tagging: number reading model | empty (`models/`) | CRNN `.onnx` |
| Assisted Tagging: livery matching model | empty (`models/`) | DINOv2 `.onnx` |
| Assisted Tagging: collections folder | empty (`assisted_tagging/collections` in the config directory) | Where collections live |
| Assisted Tagging: diagnostic tags | on | The `By number` / `By livery` / … tags above; off removes them on the next run |
| Assisted Tagging: burst gap (seconds) | 2 | Photos closer together than this are one burst |

## How it decides

```
tagging.lua groups the selection into bursts by capture time, writes manifest.csv, runs identify.py
        |
        v
identify.py, per frame:  decode at full resolution → YOLOX vehicle boxes (up to 4)
        |                → per box: crop → read numbers → DINOv2 embedding
        v
per box:   one number matches one entry                 → number
           else best livery match clear of the next one → livery
           else best two are teammates                  → team (shared tags only)
           else                                         → none
        |
        v
per burst: frames with nothing identified take the burst's entry
           when 2+ frames agree on it and none disagree → burst
        |
        v
tagging.lua reads results.csv and syncs tags
```

Frames are decoded at native resolution (a raw file's embedded preview) and each vehicle is cropped from that before reading its number, since a number only a few pixels tall in a downscaled frame is readable in the crop. Detection, OCR text and embeddings are cached per frame in `assisted_tagging/cache.sqlite` in darktable's config directory. Matching isn't, so adding references or editing `entries.json` takes effect on the next run without decoding anything again. The cache key includes the file (path, modified time, size), every model file and the constants that change the cached data; unused entries are dropped after 90 days. Delete the file to start over.

## Tuning

The thresholds are starting points, not tuned defaults. Each is a named constant:

| Constant | File | Default | What it does |
|---|---|---|---|
| `OCR_MIN_SCORE` | `ocr.py` | 0.80 | how sure the text detector must be before a number is read |
| `MATCH_MIN_SIM` | `match.py` | 0.60 | the livery similarity a match needs at all |
| `MATCH_MIN_MARGIN` | `match.py` | 0.05 | how far the best entry must be ahead of the next one |
| `BURST_MIN_AGREE` | `match.py` | 2 | frames that must agree before a burst fills in the rest |
| `MIN_BOX_FRAC` | `vehicles.py` | 0.02 | the smallest vehicle, as a share of the frame, worth identifying |
| `MAX_BOXES` | `vehicles.py` | 4 | vehicles identified per frame |
| `CROP_DIM` | `vehicles.py` | 640 | the long side each vehicle crop is reduced to |
| `DETECTOR_MIN_SCORE` | `vehicles.py` | 0.35 | the confidence a vehicle detection needs |

The run log has one line per vehicle with the numbers read and the top two livery matches with their similarity, e.g. `box 0: livery VER (OCR -; livery VER 0.712, TSU 0.694)`. Read a few from a shoot to see where the right and wrong answers fall before changing `MATCH_MIN_SIM` or `MATCH_MIN_MARGIN`.

After changing `OCR_MIN_SCORE`, `MIN_BOX_FRAC`, `CROP_DIM` or the detection, OCR or embedding code, bump `IDENTIFY_CACHE_VERSION` in `identify.py` (the three constants are already in the cache key; code changes aren't). Changes to `match.py` never need it.

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
.venv/bin/python python/test_identify.py
.venv/bin/python python/test_reference_store.py

# Windows
.venv\Scripts\python python\test_match.py
.venv\Scripts\python python\test_identify.py
.venv\Scripts\python python\test_reference_store.py
```

The pure-logic half of the plugin runs under any Lua 5.4 (`cd lua && lua test_assisted_tagging.lua`). No `lua` binary? `pip install lupa` in the venv, then:

```
.venv/bin/python -c "import lupa; L=lupa.LuaRuntime(); L.execute('package.path=\"./lua/?.lua;\"..package.path; dofile(\"lua/test_assisted_tagging.lua\")')"
```

### Running the identifier on its own

`manifest.csv` is `id,filepath,burst_id` per line:

```
python python/identify.py manifest.csv results.csv --collections-root collections --collection "F1 2026" \
    --detector models/object_detection_yolox_2022nov.onnx --ocr-det models/text_detection_en_ppocrv3_2023may.onnx \
    --ocr-rec models/text_recognition_CRNN_EN_2021sep.onnx --embedder models/dinov2_small.onnx
```

`results.csv` gets `id,box,method,entry_id,alt_entry_id,confidence` per vehicle (box −1 for a frame with no vehicle). Exit codes: 0 ok, 2 bad input (the message is on stderr), 3 missing package, 130 cancelled.

### Notes from the darktable source

- **`register_lib` takes eight positional arguments**: `(plugin_name, name, expandable, resetable, containers, widget, view_enter, view_leave)`. Leaving out `resetable` shifts the container table into a boolean slot and the panel never registers.
- **Registering a lib straight from `luarc` is a startup race.** darktable can report lighttable as the current view before the view has finished initialising, and a lib registered in that window is silently never attached (`src/views/view.c` documents it; the lua-scripts hit it as #19197). The plugin installs its panel from the `view-changed` event into lighttable instead, which fires only once the view is fully up.
- **`darktable-cli` never runs your `luarc`.** Since 5.6 the user `luarc` is loaded by `script_manager` (GUI only); before that the C code only loaded it when a GUI existed. `--luacmd` still runs, and it's the way to test headlessly. Anything GTK-wrapped (`register_lib`, `preferences.register`) blocks forever headless, so the plugin gates those on `dt.gui`.
- **Windows shell-outs go through a `.bat` file**, following `lib/dtutils/system.lua` in darktable's lua-scripts: cmd.exe mangles a command line with more than one quoted item. In that file, write the exit code with the redirect first (`> "f" echo %ERRORLEVEL%`): `echo 0> "f"` reads as "redirect handle 0" and leaves `f` empty.
- **Combobox `changed_callback` runs asynchronously, and every `selected` assignment fires it** (`src/lua/widget/combobox.c`, `src/bauhaus/bauhaus.c`), even when refilling the list. So the collection list acts only when its value differs from the stored collection.

## License

MIT, see [LICENSE](LICENSE).

# darktable-assisted-tagging

A tagging assistant for [darktable](https://www.darktable.org/) that recognises the motorsport vehicles in your images. Select a batch in lighttable, click one button, and for every car or bike in each frame it will:

- **read its race number** and look it up in your entry list
- if the number isn't readable, **match its livery** against reference samples you picked
- if that's still unclear, **borrow the answer from the rest of its group** (a darktable group or an Assisted Grouping tag group, see [Grouping support](docs/how-it-works.md#grouping-support))
- tag the image with that entry's tags, e.g. `Assisted Tagging|Motorsport|Team|Red Bull` and `Assisted Tagging|Motorsport|Driver|Max Verstappen`

Teammates in identical liveries that it can't tell apart get only their shared team tag, never a guessed driver. Everything runs locally: a Lua plugin inside darktable and a Python identifier it shells out to. No API keys, no cloud. It only adds and removes tags from your entry list and its own `Assisted Tagging|…` tags; your other tags, ratings and colour labels are never touched.

Forked from [darktable-assisted-culling](https://github.com/louiswdavis/darktable-assisted-culling). The two can be installed side by side.

## Contents

- [Requirements](#requirements)
- [Install](#install)
- [Documentation](#documentation)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)

## Requirements

- darktable 5.6, built with Lua (the official builds are).
- Python 3.10+ with the packages in `python/requirements.txt`: `opencv-python-headless` (4.x, pinned `<5`), `numpy`, `Pillow`, `rawpy`, `onnxruntime` and `PyYAML` (only the PaddleOCR text finder and readers use it).
- About 160 MB of models, listed below.
- Windows: `git` and `curl` (Windows 10+ ships `curl`). Linking the plugin needs Developer Mode on (`Win + R`, then `ms-settings:developers`) or an Administrator prompt; without either, copy the files instead (step 2).

`rawpy` needs `libraw`. The Windows and macOS wheels bundle it; on Linux install `libraw-dev` first, or skip `rawpy` if you only shoot JPEG.

## Install

Do the steps in order: Python, darktable, plugins folder, models.
Commands come first under each step; the reasons follow them.

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

### 2. darktable side

Run the block for your system from the repo root, the folder holding `README.md`. It puts the plugin's two files into darktable's `lua/contrib` folder and appends `lua/assisted_tagging.luarc`, this plugin's own few lines, to `luarc`. Each plugin adds only its own line, and the last line of each block skips it when `luarc` already has one for this plugin, so running a block twice, or running one from each plugin's repo, adds nothing twice.

Linux / macOS (links):

```
mkdir -p ~/.config/darktable/lua/contrib
ln -sf "$(pwd)/lua/assisted_tagging.lua" ~/.config/darktable/lua/contrib/assisted_tagging.lua
ln -sf "$(pwd)/lua/plugin_common.lua" ~/.config/darktable/lua/contrib/plugin_common.lua
grep -qs 'contrib/assisted_tagging' ~/.config/darktable/luarc || cat lua/assisted_tagging.luarc >> ~/.config/darktable/luarc
```

Windows (Command Prompt, copies; no Administrator or Developer Mode needed, re-run after every update):

```
if not exist "%LOCALAPPDATA%\darktable\lua\contrib" mkdir "%LOCALAPPDATA%\darktable\lua\contrib"
copy /Y lua\assisted_tagging.lua "%LOCALAPPDATA%\darktable\lua\contrib\"
copy /Y lua\plugin_common.lua "%LOCALAPPDATA%\darktable\lua\contrib\"
findstr /C:"contrib/assisted_tagging" "%LOCALAPPDATA%\darktable\luarc" >nul 2>&1 || type lua\assisted_tagging.luarc >> "%LOCALAPPDATA%\darktable\luarc"
```

Windows (Command Prompt, links; needs Developer Mode on, `Win + R` then `ms-settings:developers`, or an Administrator prompt; links follow the repo, so no re-run after an update):

```
if not exist "%LOCALAPPDATA%\darktable\lua\contrib" mkdir "%LOCALAPPDATA%\darktable\lua\contrib"
del "%LOCALAPPDATA%\darktable\lua\contrib\assisted_tagging.lua" "%LOCALAPPDATA%\darktable\lua\contrib\plugin_common.lua" 2>nul
mklink "%LOCALAPPDATA%\darktable\lua\contrib\assisted_tagging.lua" "%CD%\lua\assisted_tagging.lua"
mklink "%LOCALAPPDATA%\darktable\lua\contrib\plugin_common.lua" "%CD%\lua\plugin_common.lua"
findstr /C:"contrib/assisted_tagging" "%LOCALAPPDATA%\darktable\luarc" >nul 2>&1 || type lua\assisted_tagging.luarc >> "%LOCALAPPDATA%\darktable\luarc"
```

Then restart darktable and open `dt-lua-errors.txt` in the config directory (`~/.config/darktable` on Linux/macOS, `%LOCALAPPDATA%\darktable` on Windows). `assisted_tagging loaded` means it worked: the panel appears in lighttable once the view has finished loading. `assisted_tagging FAILED ...` gives the reason.

**Why these steps.**

- The plugin is two files, and both must sit in `lua/contrib`: `lua/assisted_tagging.lua` and `lua/plugin_common.lua`. `plugin_common.lua` is the module the three Assisted plugins share. The three copies are identical, so each plugin's block overwrites the same file harmlessly.
- Without `plugin_common.lua` the plugin fails with `module 'plugin_common' not found`. It has no `luarc` line of its own: the plugin loads it with `loadfile`, looking beside itself first, then in the **plugins folder** preference. Nothing copies it for you, and on a new device the preference does not exist yet (it is registered only after the plugin loads), so put it in `lua/contrib`.
- `lua/assisted_tagging.luarc` is a short readable snippet kept in the repo, so each block just appends it and `luarc` shows the plugin on separate lines. It loads the plugin inside `pcall` and appends `loaded` or `FAILED <reason>` to `dt-lua-errors.txt`, so a plugin that does not appear says why. The skip test looks for the text `contrib/assisted_tagging` in `luarc`. If your `luarc` already loads this plugin another way, such as a loop that builds the name, the test does not see it: skip the last line of the block.
- Keep `require "tools/script_manager"` (the scripts panel, from the separate `lua-scripts` repo) on the first line of `luarc`. If the scripts panel is missing, remove the Assisted lines, restart, and add them back one at a time; `dt-lua-errors.txt` shows which one fails.
- Copies must be re-made after every update; links follow the repo.

### 3. Point the plugin at the repo

Start darktable, open **preferences → lua options**, and set **plugins folder (holds the three assisted-* folders)** to the folder that holds `darktable-assisted-tagging` (and the other assisted plugins). From there the plugin finds `python/identify.py`, the `models` folder and the `.venv` by itself. The preference is shared by the assisted plugins; the older per-plugin **Assisted Tagging: plugin folder** preference still works, and the log says once to move it. There is no interpreter preference: the plugin runs its own `.venv` (else `python`/`python3` on `PATH`), because each assisted plugin has different requirements.

### 4. Models

Download them into a `models` folder in the repo. The plugin looks there, `.gitignore` skips the whole folder, and `git pull` leaves it alone. Run every curl block below from the repo root, the folder holding `README.md`, not `python/`; `--create-dirs` makes `models/`.

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

Everything else about models is on [Models](docs/models.md): what each extra turns on, the larger livery embedder, the face models for people collections, how the plugin picks a file, a curl error 23 fix, how to check what is installed, and the download for every other file.

## Documentation

- [Models](docs/models.md): What each extra turns on, how the plugin picks a file, and every other download.
- [Using it](docs/usage.md): Starting a collection, building references, identifying, and the report.
- [Panel options](docs/panel-options.md): Presets, every panel setting, and the preferences.
- [How it works and tuning](docs/how-it-works.md): The pipeline, grouping support, and the tuning constants.
- [Testing and development](docs/testing.md): The Windows acceptance checklist, the tests and the helper tools.

## Troubleshooting

- **The panel isn't there.** Start darktable with `-d lua` and look for `LUA ERROR` in the log. On Windows the log is `Documents\Darktable\darktable-log.txt`.
- **Every run writes a log** to `assisted_tagging.log` in darktable's config directory (e.g. `%LOCALAPPDATA%\darktable` on Windows); the 5 runs before it are kept as `assisted_tagging.prev.log` (the last one), `assisted_tagging.prev2.log` … `assisted_tagging.prev5.log`. Each line is written as it happens, so a crash leaves the last step in the file; each stage logs `started` and `done` with its seconds, and a failed write names its image. It has the exact command, the reference counts per entry, one line per vehicle with what was read and matched, and any per-image errors.
- **"…/entries.json: …"** The run stopped on a mistake in that file; the message says which entry and what's wrong.
- **"… model not found: …"** A model file is missing. Download it into `models/` (see [Install](#4-models)). A job with none of its files installed stops the run with `Assisted Tagging: No <job> model in models/. Install <file> (README, "Models").`
- **"Python is missing a package."** `darktable-assisted-tagging/.venv` doesn't have `requirements.txt` installed; the log names the package.
- **"no collections yet."** Create a folder with an `entries.json` in the collections folder the message names, then click **Reload**.
- **Everything comes back `Unidentified`.** Check the log's `references:` line: an entry with 0 references can only be found by its number. The `entry list:` lines under it, logged before any image is read, name what in entries.json will cost matches: a number on more than one car (a read of it names neither, so only livery can), entries with no references, and entries with neither a number nor references.
- **"cache … is unreadable".** Delete `assisted_tagging/cache.sqlite` in darktable's config directory; the next run rebuilds it.

## Limitations

Known gaps, not yet fixed:

- **Entries with no references** can only be identified by a readable number.
- **Identical teammates** get only their shared team tag, never a guessed driver.
- **Packs** get no team-tag hints, and are not checked against the tags you applied.
- **Groups are not size-checked.** A coarse group can carry one identification across different cars (see [Grouping support](docs/how-it-works.md#grouping-support)).
- **Four vehicles per frame** at most (`MAX_BOXES`); a frame that reaches it gets the *Crowded* tag.
- **Thresholds are starting points**, not tuned defaults (see [Tuning](docs/how-it-works.md#tuning)).
- **Reference crops** come from previews, unmasked, even when the run re-read a box at higher detail.
- **Older tags count as yours.** Images tagged before the ledger existed have no ledger rows, so a run never removes their entry tags.
- **The audit's whole-frame check** also fires on dark or blurred cars, and the first audit is slow (about 8 minutes for 2000 refs).
- **Run stamps** from **Tag Each Run** are never removed by the plugin.

## License

MIT, see [LICENSE](LICENSE).

# Models

Part of [darktable-assisted-tagging](../README.md). The base and recommended downloads are in [Install, step 4](../README.md#4-models); this page covers the rest.

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

`box check: off (no SigLIP 2 model); colour reader: HSV rules` means the SigLIP 2 files are missing or misnamed. `(better, not installed: …)` names files you could add. The first run after adding any of these re-reads every image once, so expect it to take longer.

**How the plugin picks a model.**

The plugin picks the model for each job itself. Each table below lists one job's files best first; the plugin uses the best one in `models/` and ignores the rest. The row marked `(base)` comes with the base install; a row below it is an older fallback. A job with none of its files installed stops the run with an error naming the file to get (the face models are the exception: only people collections need them).

The run log names each pick, plus any better file you haven't installed, e.g. `vehicles: object_detection_yolox_2022nov.onnx (better, not installed: dfine_x_coco.onnx, …)`. Adding or removing a file changes the pick on the next run:

- a new vehicle finder, text finder or number reader re-reads every image once, because the model is part of the cache key
- a new livery embedder re-embeds every reference before analysing (the progress bar counts the references; on a large collection this takes minutes, and a cancel keeps those already done)

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

To compare two vehicle finders on your own images (frames with a car, cars missed, boxes per frame, CPU ms per frame at three score thresholds, plus a CSV of the frames where they disagree on box count):

```
python python/compare_detectors.py --detector models/object_detection_yolox_2022nov.onnx --detector models/dfine_s_coco.onnx --truth results.csv --manifest manifest.csv --out compare_detectors.csv --disagree disagree.csv <a folder of images>
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

The CRNN is the plugin's first reader. It reads grey crops at a smaller size and misses more numbers (on 202 rally images it read a number on 45 vehicles where PP-OCRv5 read 76), so the plugin uses it only when no v5 reader is installed. To compare readers on your own images, print each vehicle's reads from both, with the ones that differ marked and a count of how many vehicles each got a number on:

```
python python/compare_ocr.py --rec models/text_recognition_CRNN_EN_2021sep.onnx --rec models/en_PP-OCRv5_mobile_rec.onnx --out compare.csv <a folder of images>
```

##### Second reader (optional, PARSeq)

`second_reader` in `settings.json` (off by default, not in the panel) reads every text region with digits a second time, with PARSeq, from the same quad turned the same way. A number counts only when both readers read it: a region whose numbers PARSeq did not read too gives no number (its `dropped` in `ocr_regions` is `disagree`), so the image is Unsure unless the livery decides it. The log counts them (`second reader disagreed on 3 of 41 regions with digits; those give no number`). Turning it on re-reads every image once. It does nothing in a people collection.

Download the model, and save its `config.json` beside it as `parseq-00b40714.json`; the plugin stops with a message if the `.json` is missing.

| File | Size | Download | Source, licence |
|---|---|---|---|
| `parseq-00b40714.onnx` + `.json` | 96.6 MB | `https://github.com/felixdittrich92/OnnxTR/releases/download/v0.0.1/parseq-00b40714.onnx` and `https://huggingface.co/Felix92/onnxtr-parseq/resolve/main/config.json` | OnnxTR (docTR's PARSeq), Apache-2.0 |

#### Trying PP-OCRv6 small

PP-OCRv6 small (text finder and reader, 31 MB together) may read angled numbers better than PP-OCRv3 + PP-OCRv5 mobile. Paddle's own benchmark puts its detection on rotated text at 93.7 against 64.7 and its reading at 81.3 against 73.7; those are the publisher's figures, not measured here. It stays on trial until a measured run on your images beats today's models. To measure it:

1. Download both v6 files and their `.yml` into `models/`, named as in the tables above.
2. Select hand-tagged images and run **Verify Selection**. Copy the run's `boxes.json` aside (the next run overwrites it) and run `python python/eval_numbers.py COPY.json`. Note *read right* and *wrong entry*, and the run log's `analysis: … frames/min` line.
3. Move `text_detection_en_ppocrv3_2023may.onnx`, `en_PP-OCRv5_mobile_rec.onnx` (+ `.yml`), and `PP-OCRv5_server_rec.onnx` and the CRNN if you have them, out of `models/`. The run log should now say `text finder: PP-OCRv6_small_det.onnx` and `number reader: PP-OCRv6_small_rec.onnx`.
4. Repeat step 2 (changing models re-reads every image once), then move the files back.

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

The vehicle detector also boxes marshals, sheds and railings. With SigLIP 2 in `models`, each box is checked before it is read: a box that looks more like a person, a building, a railing, spectators, trees or an empty road than a vehicle (a rally car, a race car, a motorbike or quad, or a truck) is dropped, and the log counts what was dropped (`box check: dropped 4 boxes: person 3, railing 1`). **Add as Reference** uses the check to pick its box (a frame's largest box that fails it is passed over), but never drops a frame for it. The same model reads each car's paintwork colour for the [Colour family](usage.md#tag-families) in place of the built-in hue rules, comparing the car with "an image of a red rally car." and so on for each palette name, plus "multicoloured"; an unsure read (top score under 0.4, or within 0.1 of the next) gives no colour. Without it, every box is read and colour comes from the hue rules. Adding or removing it re-reads every image once. People collections don't use it.

##### Number gate (experimental, SigLIP 2)

`number_gate` in `settings.json` (off by default, not in the panel) asks SigLIP 2 one more question of each box before the number reader runs: does the crop show a racing number at all? A box whose number share is under `NUMBER_GATE_MIN` (a distant car, a car seen from behind, a blurred pass) is not read, which saves the read and stops stray text on it being taken for a number. Its `ocr_trace` in `boxes.json` is `[[0.0, "gated"]]` and the log counts them (`number gate: 12 of 80 boxes not read`). A box that is read again at higher detail, cropped with a mask or found by burst rescue is always read. Turning it on re-reads every image once.

To choose the threshold, turn `number_gate` on, run **Verify Selection** on hand-tagged images (a verify run still reads the gated boxes, for the replay only), then compare `python python/eval_numbers.py BOXES.json` with `python python/eval_numbers.py BOXES.json --set NUMBER_GATE_MIN=0`: the second is the same run with the gate open. Misses the gate caused are counted under `gated`.

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

A people entry has only `id` and `tags`; references are images with exactly one face, so tag those images by hand first. Choose `min_sim`, `margin` and `min_face_px` in `settings.json` with `python python/eval_people.py <collection> --face-detector … --face-recognizer …`.

**Audit References** (panel button, `python/audit_refs.py`) needs nothing beyond the packages in `requirements.txt` and the models above.

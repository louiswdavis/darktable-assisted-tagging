# Roadmap

Ideas worth doing deliberately later, not bolted onto whatever's being fixed today.

## Generalize beyond motorsport

`Entry` (`match.py`), the OCR number lookup, and the "team" tie-break in `match_box`
are motorsport-specific. The underlying pipeline — detect → crop → embed (DINOv2) →
match against a collection's reference crops → burst consensus — is already
domain-agnostic (`vehicles.py`, `embed.py`, `reference_store.py`).

Other domains that would fit the same pipeline with different identifying
attributes instead of race number / team:

- **Other sports** (jersey number stands in directly for race number)
- **People** — built as the `people` collection kind (YuNet + SFace face embeddings); thresholds still to be set from a Windows `eval_people.py` run
- **Landmarks** — no number, no "team" grouping concept at all
- **Flowers / birds / animals** — species/genus grouping could replace "team"
  (e.g. a "same species, can't tell which individual" tie-break)

Needs a schema redesign (`Entry` fields become domain-specific, or a pluggable
"identifying attribute" concept) rather than reusing `number`/`team` as-is.

### Proposed shape: per-collection workflow type

Rather than one generic `Entry` schema stretched to cover every domain, give each
collection a `workflow` (or `type`) field — similar in spirit to how
darktable-assisted-culling selects an action type — that determines:

- which `Entry` fields are valid/required (e.g. `number`+`team` for motorsport,
  nothing but an id for landmarks, `species` instead of `team` for
  flowers/birds/animals)
- which embedding/matching model the pipeline uses (DINOv2 crop-embedding stays
  the default; people may need a face-embedding model instead)
- which tie-break logic `match_box` applies when a crop is ambiguous (team
  tie-break for motorsport, species tie-break for animals, no tie-break at all
  for landmarks)

A collection's `entries.json` would declare its `workflow` once at the top level;
`match.py`/`vehicles.py` would dispatch on it rather than assuming motorsport
fields exist. The OCR number-matching path (`match.py`) stays motorsport-only and
is simply absent for workflows that don't declare it.

Scope this as its own task once the motorsport pipeline (current F1 fix, `Number
seen` diagnostic, in-panel editor) is tested and stable — don't bolt it onto the
in-progress work.

## One-off special liveries

A team sometimes runs a one-off livery for a single race. Its cars look nothing like that
team's reference crops, so livery similarity (embedding and the colour score) points away
from the right team, and colour weight makes that worse. The user has photos from two events
where this happens, which makes them the test set.

Ideas, roughly in order of cost:

- Number reading still works regardless of livery; check the number path wins over a
  disagreeing livery score.
- Per-event reference crops: let a reference be tagged with an event/season so a special-livery
  set is used only for photos from that event (date range or folder), and the normal set
  isn't polluted.
- A "special livery" flag on an entry or team, so its refs are exempt from the colour term
  and from centred-mean computation.
- Evaluate on the two known events before choosing.

## Car-shaped outlines instead of boxes

YOLOX (`vehicles.py`) returns only rectangles, so a box includes background and the
neighbouring car in pack shots. An instance-segmentation model (YOLOv8-seg or Mask R-CNN
as ONNX, or SAM prompted with each box) would give a mask or polygon per car.

What it would improve:

- `overlap.py` could trim a covered car to its visible pixels instead of a rectangle span.
- The DINOv2 livery crop would drop the background and the car next to it.
- The camera pod crop would be more reliable.

Costs: another model download (roughly 40–150 MB), slower detection, a new detection cache
token, and masks stored in boxes.json and the reports. The `cv2.dnn` path for a
segmentation ONNX is untested on Windows.

Cheaper first step, built but untested (`segment.py`, EfficientSAM from opencv_zoo): YOLOX
still finds the cars, and the mask model runs only on boxes that overlap another box. It
only masks the crop for OCR, the embedding and colour. Still to do: run it on Windows
(`cv2.dnn` loading, speed per box), check the masked crops against the four pack frames,
then consider masks in `overlap.py`, the pod crop and the reference crops.

## Smaller known gaps

- "Edit entries.json" button prints a mangled path instead of opening/editing the
  file when `open_in_app` fails on Windows — consider an in-app darktable dialog
  with a text-entry widget instead of relying on the OS file association.

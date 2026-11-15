# Roadmap

Ideas worth doing deliberately later, not bolted onto whatever's being fixed today.

## Generalize beyond motorsport

`Entry` (`match.py`), the OCR number lookup, and the "team" tie-break in `match_box`
are motorsport-specific. The underlying pipeline — detect → crop → embed (DINOv2) →
match against a collection's reference crops → burst consensus — is already
domain-agnostic (`vehicles.py`, `embed.py`, `reference_store.py`).

Other domains that would fit the same pipeline with different identifying
attributes instead of race number / team:

- **Other sports** (jersey number stands in directly for race number). Numbers-only entries and the `order_weight` neighbour aid already cover events where cars are told apart by number alone (see `examples/rally`)
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

Partly built: the top-level `"kind"` in entries.json (`motorsport`, the default, or `people`)
is this field. Landmarks and animals are still open.

## Vehicle sub-kind: cars, bikes

Ticket 28. A motorsport collection says nothing about its vehicles: the detector keeps COCO
car, motorcycle and truck (`vehicle_detect.py`, classes 2, 3, 7) for every shoot. A sub-kind
next to `kind` (key and values decided in a brainstorm) would:

- keep only the matching classes: cars → car + truck, bikes → motorcycle, cutting false boxes
- pick a settings preset as a starting point. Rally: numbers-only, neighbour order, co-driver.
  Circuit/F1: team, driver, livery matching, team-only for teammates. Bikes: rider for driver.
- let bikes use better models (a motorcycle detector or number reader) through the per-job
  model lists

Open: rally versus F1 may be a preset rather than a sub-kind, since both are cars to the
detector. Number OCR and the side-on guess (`pod.py`) assume car shapes; check what bikes break
first. `kind: people` stays separate.

## More tag families

- **Co-driver** (ticket 22, rally): co-drivers get their own tag instead of sharing the
  driver's.
- **Sponsor** (ticket 23): a sponsor word read on a car becomes a tag, e.g.
  `<sponsor root>|Castrol`.
- **Learn colours from your tags** (ticket 24): colour tags you set by hand teach the plugin
  how your camera and light render each colour. Waits until wrong colour tags show up in real
  use.
- **Start-list column mapping** (ticket 20, rest): map the columns in the import dialog
  instead of typing a column spec.

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

## Viewpoint-aware references

A front three-quarter reference matches a rear shot of the same car poorly, and can look
closer to another team's car seen from the same angle. That likely feeds the teammate and
look-alike confusions (Hamilton/LeClerc, Audi/Aston Martin).

Idea: estimate each crop's view (front, rear, side, three-quarter left/right; aspect ratio
for a first cut, a small classifier later), store it in `index.npz`, and at match time
compare a query mainly to refs of a similar view. `audit_refs.py` could report view
coverage per entry ("Gasly: no rear refs").

Evidence (first `audit_refs.py` run on F1, 2026-10-19): the top candidates were all correctly
filed. They looked wrong only because of an unusual angle (low, hazy, from behind), a distant
or uncropped shot, one-off aero paint, or a nose-only crop. The embedding and colour checks
can't tell "wrong car" from "unusual view", so view-awareness would also cut audit noise.

Costs: the auto-labelling, a matching change, a cache token, and thinner per-view ref
counts (Hulkenburg has 5 refs in total). Measure with `eval_matching.py` before wiring.

## Stronger models

In order of payoff for effort:

1. Larger embedder: built as the best-first model lists (`M.MODEL_LISTS`, ticket 25), which
   pick DINOv2 large/base, D-FINE and PP-OCRv5 server rec when installed. Still to confirm on
   Windows: (a) base models only, (b) add PP-OCRv5_server_rec → re-read, (c) add dinov2_base →
   re-embed. Measuring which model is better waits for a hand-fixed truth set.
1a. SigLIP 2 for colour and orientation (ticket 27): a ~2-hour throwaway test of whether it
   names a car's colour and facing well enough to replace the HSV colour rules and the
   aspect-ratio side-on guess.
2. Fine-tune the embedder on the refs so teammates separate.
3. A vision-language model as a tiebreaker on abstained or near-tie boxes. Per-image cost,
   latency, and photos leaving the machine: the user's decision.
4. Stronger number reading (the `1`/`14`/`44` misreads), by a better OCR or a VLM.

## Which driver drove a double-driven car

A double-driven car (30 and 730 at Rallye Prescott) gets both entries' tags (entries.json `car`,
or the importer's **Shares Car With** column), since the car alone can't tell the drivers apart. Telling them apart takes the run order: each driver's
runs come at set points in the running order, so photo timestamps against the published order (or
the gap between the two drivers' consecutive runs) could pick the driver. Needs a running-order
input and per-event timing; aimed at shooters who deliver per-driver galleries.

## Smaller known gaps

- "Open entries.json" on Windows: the `start` command now gets cmd.exe's outer quote
  pair (the old mangled-path failure); confirm on the real pass, step 5.
- Changing any `family_*_root` strands tags under the old root: cleanup only looks
  under the current one. The default roots moved to `Assisted Tagging|Motorsport|<Family>`
  (2026-11-15), so collections tagged under the old `Motorsport|<Family>` defaults hit this
  unless their settings.json pins the old roots. Owning the old root's first segment would also own the run stamps
  (`Assisted Tagging|Run|…`), so a fix needs the old root kept somewhere (settings or ledger).
  Workaround: select the photos, Clear tagging marks, run again.

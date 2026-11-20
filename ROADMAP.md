# Roadmap

Ideas worth doing deliberately later, not bolted onto whatever's being fixed today.

A desk-research pass on 2026-11-19 added items from the off-road racer-number paper (Tyo et al., arXiv 2402.08025) and race-photo services that pair number reading with faces. Vendor figures are claims, not checked.

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

A motorsport collection says nothing about its vehicles: the detector keeps COCO
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

- **Co-driver** (rally): co-drivers get their own tag instead of sharing the
  driver's.
- **Sponsor**: a sponsor word read on a car becomes a tag, e.g.
  `<sponsor root>|Castrol`.
- **Sponsor logos with no text.** One-shot matching: the user gives one logo crop per sponsor,
  the plugin embeds it and matches inside each car box. Catches logos OCR can't read. Use: a
  per-sponsor delivery set ("every frame where the X logo is visible and sharp"). Leads:
  open-set logo detection (Logos in the Wild, licence unchecked); ExposureEngine is YOLO-based
  (AGPL family), so ideas only. Effort M.
- **Conditions**: `Conditions|Rain`, `|Snow`, `|Night`, `|Dust`, `|Gravel` from SigLIP 2 zero-shot,
  sharing the model with 1a under Stronger models. ClearVision reports 94% per weather class
  after fine-tuning (night 85.9%); no zero-shot or road-surface figures found, so run a
  throwaway prompt test first. Effort S–M once SigLIP 2 is in.
- **Shot type**: `Shot|Action`, `|Portrait`, `|Podium`, `|Paddock`, `|Detail`, `|Crowd`,
  `|Incident` from SigLIP 2 zero-shot. Editors ask for that variety, so the user can check a set
  covers it. Effort M (shares SigLIP 2). Research:
  `docs/superpowers/research/2026-11-19-motorsport-styles.md`.
- **Style**: `Style|Panning`, `|Frozen`, `|Zoom burst`, `|Camera movement`, `|Light trails`,
  `|Environmental`. The streak-based ones from culling's `motion_tiles` (streak direction and
  shutter), the rest from SigLIP 2 or a Photozilla-style few-shot embedding. Classifiers confuse
  long exposure with motion blur (AVA), so test on real frames first. Effort M.
- **Learn colours from your tags**: colour tags you set by hand teach the plugin
  how your camera and light render each colour. Waits until wrong colour tags show up in real
  use.
- **Start-list column mapping** (the rest of start-list import): map the columns in the import dialog
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

1. Larger embedder: built as the best-first model lists (`M.MODEL_LISTS`), which
   pick DINOv2 large/base, D-FINE and PP-OCRv5 server rec when installed. Still to confirm on
   Windows: (a) base models only, (b) add PP-OCRv5_server_rec → re-read, (c) add dinov2_base →
   re-embed. Measuring which model is better waits for a hand-fixed truth set.
1a. SigLIP 2 for colour and orientation: a ~2-hour throwaway test of whether it
   names a car's colour and facing well enough to replace the HSV colour rules and the
   aspect-ratio side-on guess.
2. Fine-tune the embedder on the refs so teammates separate.
3. A vision-language model as a tiebreaker on abstained or near-tie boxes. Per-image cost,
   latency, and photos leaving the machine: the user's decision.
4. Stronger number reading (the `1`/`14`/`44` misreads), by a better OCR or a VLM.
   Candidates (desk research, November 2026; no CPU timings measured):
   PP-OCRv6 first: released 2026-06-11 with PaddleOCR 3.7.0, tiny/small/medium tiers
   (1.5M/7.7M/34.5M params), English among its 50 languages. Medium is reported 5.2× faster than
   PP-OCRv5 server on CPU (vendor claim). Official ONNX exists for the detector; the recogniser
   ONNX is community-only so far. Add it to the top of the reader list in `M.MODEL_LISTS`.
   Then Florence-2 base as a fallback reader on low-confidence reads (MIT, ~270 MB INT8).
5. DINOv2 on segmenter-masked crops, so background and other cars don't enter the embedding.
6. Helmet-crop embedding to tell two drivers of one car apart, where the helmet is visible.

Licence-rejected: YOLO11/26 and YOLO-seg (AGPL), PaliGemma 2.

## Unknown cars and review

Ideas from competitor tools (Aftershoot, Narrative Select, Lightroom, Photo Mechanic and similar; vendor descriptions, not tested):
- **Cluster unknown cars, name later.** Boxes that match no entry are grouped by look, so the
  user names a cluster once instead of tagging each photo.
- **Ignore state.** A photo or box marked "ignore" (marshal car, spectator car) gets no identity
  and is skipped on later runs. Hand-tag protection already keeps hand-set tags per family; this
  covers "nobody", which today has no tag.
- **Second pass on leftovers.** Re-run only on photos still without a number tag.
- **Partial-number search.** Find photos whose read number contains the typed digits
  (`14` finds 114 and 144), for photos where the OCR read part of the number.
- **Entry-list sanity report.** Before a run: duplicate numbers, entries with 0 refs, a team
  with one entry, numbers with no driver. Folds in the "0 refs" notice. Built 2026-11-18 as
  `entry list:` log lines (`entry_list_check` in `identify.py`), not shown in the panel.
- **Copy tags to group (built 2026-11-20, ticket 87).** Fix one photo, then copy its entry and
  family tags over the rest of its darktable group. The copies are hand tags.
- **"Checked" marker (built, ticket 39).** A tag the user sets on photos whose tags they confirmed. Those photos
  become the truth set the model measuring in "Stronger models" waits for.
- **Confirm per cluster.** Show every crop tagged with one number side by side, so the user
  confirms or removes them in one pass. Tyo et al. (arXiv 2402.08025) seeded identity clusters
  from read numbers and cut checking time from over 30 minutes to under 10 per rider.

## Number reading against the start list

From desk research on bib, jersey-number and plate reading (mostly from search snippets,
nothing tested). Aimed at the `1`/`14`/`44` misreads:
- **Closed vocabulary.** Built: `match.list_read` scores every start-list number against the
  reader's digit matrix (`ctc_log_likelihood`) and abstains below `NUMBER_LIST_FLOOR` or
  `NUMBER_LIST_MARGIN`.
- **Fuse reads across a burst.** Built: `match.burst_list_read` sums the per-frame list scores
  over a group.
- **"Readable?" gate.** Built as SigLIP zero-shot (`number_gate`, `NUMBER_GATE_MIN`), off by
  default; awaiting a Windows `eval_numbers.py` run. A small trained head only if that is weak.
- **Two readers must agree.** Built as `second_reader` (OnnxTR's PARSeq, `ocr.ParseqRecogniser`),
  off by default: a region's number counts only when PARSeq reads it too (`drop_reason`
  `"disagree"`), so disagreement becomes Unsure unless the livery decides. Awaiting a Windows run
  with the model installed. A wrong tag costs more than a blank one.
- **Several numbers per entry**, plus a filter for digits that repeat unmatched across the shoot
  (sponsor or class numbers on the car). Both built: an entry's `shows` (`match.numbers_of`) and
  `match.noise_numbers`.
- **Group voting.** A number read with confidence in one frame votes for the same car's box in
  every frame of its grouping-plugin group, so frames where the number is hidden still get tagged.
  Burst consensus already does part of this; check what it covers before building. Effort M.
  Copy tags to group (ticket 87) is the manual version.
- **Compare reads on absolute fit (bug, not fixed).** `list_read` scores each read against its
  own greedy text, so a weak read's faint extra digit beats an exact strong read: DSC08780 read
  `100` (0.92) and `2` (0.82, sponsor `AREAS2`) and got 52. Roadmap idea row 68. ~30 min.
- **Rotated numbers.** A car on its side, a roof number or a tilted crop reads badly. When a
  crop gives no list match, read it again at 90°, 180° and 270° and keep the best list score.
  Tyo et al. list odd orientations after crashes among the main misreads. Effort S.
- **Measure reads by condition.** Tyo et al.'s off-road number reading dropped from 0.599 F1 on
  clean numbers to 0.470 with mud (44% of their test images) and 0.289 with glare. Split
  `eval_numbers.py` results by `Conditions|` tag (once built) so mud and glare are measured
  apart, and lean on livery and burst votes when a crop is muddy.

## The car the shooter aimed at

From how culling tools pick the subject (Aftershoot's "intended car" check is a vendor claim):
- **AF-point priority.** Read the AF point from EXIF (maker notes, per maker) and tag the box
  nearest it as the photo's main car. Other identified cars go under an `Also seen` tag, so a
  per-driver export doesn't fill up with background cars. Fall back to the largest or most central
  box. Culling would use the same "targeted car" pick. Effort S once the EXIF read exists.
  The read itself is set out in culling's ROADMAP ("Targeted car"): Sony maker-note
  `FocusLocation` (width, height, X, Y in pixels; `Exif.Sony1.FocusLocation` via exiv2) first,
  normalised and rotated by EXIF orientation; Panasonic `AFPointPosition` is already 0–1; Canon,
  Nikon, Fuji and OM behind one interface, `exiftool -j -n` as fallback. Build it once in a
  shared helper.
- **Calibrate the embedding thresholds.** Livery-match cut-offs need numbers from ~100 labelled
  same-car / different-car pairs from a real shoot. SSCD's 0.75 is for edited copies, and DINOv2
  has no standard cut-off. Share the labelled set with grouping.

## Livery matching that knows its limits

- **Same view first.** Match against references of the same view (front, side, rear) first,
  other views at a penalty. A cheap form of viewpoint-aware re-ID; needs a view label per ref
  (SigLIP 2 zero-shot, once its colour/orientation test passes).
- **Rank-pattern rejection.** Accept a match only when the entry's other references also rank
  near the top, not on one distance threshold (arXiv 2508.06357). Teammates with near-identical
  liveries become Unsure instead of a guess.
- **Self-train per shoot.** Fit a small livery head on crops confirmed by number reads.
  A running-race study reports F1 85.8 this way vs 74 for text alone; an off-road motorcycle paper
  (Tyo et al.) reports rider re-ID going from 33% to 79% rank-1 after fine-tuning.

## Better references

Ideas found in old specs, audits and plans that the code doesn't have yet:
- **Refs from confident number reads.** A box whose number was read with high confidence adds
  its crop as a livery reference for that entry.
- **Refs from the hi-res or masked crop**, not the downscaled detection crop.
- **Size-check groups.** One coarse group can carry an identity across two cars; split or skip
  groups whose boxes disagree too much.
- **Raise the `MAX_BOXES`=4 cap** for crowded starts and pit lanes.
- **Windscreen name cross-check** and **pack team hints** as extra tie-breaks.
- **Reference audit speed:** ~8 min for 2000 refs; build the index in one stack in
  `reference_store.py` (audit P1) and cut the false positives.

## Per-driver export

Export one folder (plus a CSV) per driver or entry, built from the number tags. The
competitor research rates this the highest-impact gap for shooters who sell per-driver galleries.

Most of it is already in darktable: export paths accept `$(CATEGORY[n,category])`
("tag name of level n of selected category"), so an export path ending in the driver family's
root (e.g. `…/$(CATEGORY[0,Assisted Tagging|Motorsport|Driver])/$(FILE_NAME)`) gives one folder
per driver with no plugin code. Plugin work shrinks to:
- a README recipe and, if possible, a shipped export preset
- a check for photos with two driver tags (double-driven cars, `Also seen`), which the variable
  can't split into two folders
- the CSV (photo → entry) as a small optional script

## Privacy blur at export

An opt-in export step that blurs spectator faces and road-car plates (service roads, car parks),
never a competing car's plate or number. Candidates: EgoBlur (Meta; face and plate detectors,
Apache-2.0, about 400 MB each, trained on egocentric footage, CPU time unknown), deface (face only,
CenterFace). Tagging already finds people (YuNet), and plate reading is planned (Registration
plates), so the boxes may already exist: blur the person boxes' faces and any plate not matched
to the start list. Effort M. Research: `docs/superpowers/research/2026-11-19-new-signals-across-plugins.md` §5.

## Captions from tags

Sports desks expect a caption on every photo, and Photo Mechanic's "code replacement" (type a
number, get the driver's name) is the tool many sports shooters use for it (well known, not
checked here). The tagging plugin already knows the entry, so it can write the caption itself:
- Lua `dt_lua_image_t` has writable `title` and `description`; exports carry them as
  `Xmp.dc.title` / `Xmp.dc.description`
- template in settings, e.g. `#{number} {driver}, {team}, {vehicle} – {event}`, with the event
  name from the collection
- a caption the user wrote or changed by hand is never overwritten: the ledger keeps a hash of
  the caption it last wrote and skips the photo when the text no longer matches
- two cars → caption names the targeted car only (see "The car the shooter aimed at")

Effort ~1 day. Builds on the co-driver tag family (a separate co-driver field) for a correct `driver / co-driver`.

## Timing data: which car was on track at that moment

At hillclimbs and sprints (Rallye Prescott) only one or two cars are on the course at once, and
the organiser publishes each run's start time. With the camera clock synced, a photo's timestamp
narrows it to one or two entries before any model runs:
- **Import run times** from the results/timing sheet (CSV, or pasted text like the start-list
  import): entry, run, start time, and finish time when given
- **Your spot on the course**: one setting (seconds after the start, or a fraction of the run
  time) moves each car's window to when it passes the photographer
- **Use it as evidence, not truth**: entries whose window covers the photo get a prior that the
  number reader and livery match must agree with. A disagreement becomes Unsure
- solves the double-driven car (30 / 730) case above without guessing from the running order

Circuit races need lap-by-lap passing times (transponder loops). Those are seldom published as
files, so this is hillclimb/sprint first. Effort M; needs camera clock sync (below).

## Registration plates

Road rallies, targa events and club sprints often run road-registered cars, and some entry
lists carry the registration. A plate is a second, very regular number per entry:
- optional `registration` field in entries.json (importer column "Reg")
- read plates with the same OCR, match against the list only (closed vocabulary), so spectator
  and car-park plates never get tagged
- UK format check (`AB12 CDE`) before matching, to drop half-reads
Effort S–M. Only useful where lists carry plates; check a few real lists first.

## Season library

The same cars come back every round of a championship. Today each collection builds its
references from scratch.
- **Carry references forward**: import refs from an earlier collection's photos the user
  marked "Checked", matched on entry number + driver
- special one-off liveries stay per event (see "One-off special liveries")
- a stale ref (car resprayed) is caught by the rank-pattern check and dropped
Effort M. Biggest win for a shooter covering a whole season.

## Camera clock offset

Everything time-based (timing data, double-driven cars, a second camera body) needs the camera
clock to match real time. Two ways in:
- a per-collection offset setting (`+00:01:23`)
- **sync from a photo of a clock**: the user photographs a phone or timing-screen clock, types
  the time shown, and the plugin sets the offset from that frame's timestamp

The offset is applied when reading times. It never rewrites `exif_datetime_taken` (writable in Lua), so
nothing is lost if it's wrong. Grouping needs the same offset per camera body.

## Which driver drove a double-driven car

A double-driven car (30 and 730 at Rallye Prescott) gets both entries' tags (entries.json `car`,
or the importer's **Shares Car With** column), since the car alone can't tell the drivers apart. Telling them apart takes the run order: each driver's
runs come at set points in the running order, so photo timestamps against the published order (or
the gap between the two drivers' consecutive runs) could pick the driver. Needs a running-order
input and per-event timing; aimed at shooters who deliver per-driver galleries.

## Driver portraits get the car's tag

Race-photo services pair bib reading with face matching, so a runner's photos without a visible
bib still reach them (FotoOwl's 2026 workflow; vendor description). For motorsport: a frame where
a confidently read car and a face appear together (driver at the car, helmet off) links that face
to the entry. Later paddock and podium frames with the same face (SFace embedding, from the
`people` kind) get the entry's driver tag. Needs the people thresholds from `eval_people.py`
first; a double-driven car links two faces. Effort M.

## Export and import presets

**Status (2026-11-19):** layers 1–3 built, awaiting the Windows run (README acceptance step 16).
**export preset…** and **import preset…** in the actions menu write and read a `<name>.atpreset`
folder: `manifest.json`, `preset.json` (the collection's `settings.json`) and `entries.json`. A
**references** tick box (off each time the box opens, label shows file count and MB) adds the whole
`refs/` folder; `index.npz` stays behind and the import's first run embeds the copied crops. Faces
have no box of their own: in a people collection the refs are the faces, and the tooltip says so.
Import never overwrites: a taken name becomes `<name> (2)`. Not built yet: refs for start-list
entries only, replace/merge on import, zip bundles and the cross-plugin rally set. The design below
still holds for those.

Asked for 2026-11-19: hand a working setup to another machine or another shooter. Today a preset
lives only where it was saved: tagging's in the collection folder (`settings.json` next to
`entries.json`), grouping's in `<config dir>/assisted_grouping/presets/`, culling's in
`<config dir>/assisted_culling/presets/`. Not to be confused with darktable's own export presets.

**Export dialog.** An **Export preset…** action next to *store new preset…* opens a dialog with
one tick box per layer, and shows each layer's file count and size before writing:

| Layer | Files | Default | Notes |
|---|---|---|---|
| 1. Panel settings | preset JSON | on | small; all three plugins have it |
| 2. Entry list | `entries.json` | on | tagging only; the start list plus tag families |
| 3. References | `refs/<entry>/*.jpg`, `refs/sources.json` | off | the big one (hundreds of MB for a season); see below |
| 4. Run caches | `.boxes.json`, `index.npz`, `frame-share-cache.json` | never offered | see below |
| + other plugins | grouping and culling presets of the same name | off | the "rally set" from grouping's WORKFLOW.md in one bundle |

**References (layer 3)** are the reason to export at all when handing a collection over, and the
riskiest:
- size: show it, and offer "only entries in the start list" to drop old cars
- `people` refs are photos of faces: a separate tick box, off, with a line saying what it holds
- photos are the shooter's own work: the dialog says the refs go out as full JPG crops
- refs are named by darktable image id, which means nothing in another library; on import keep
  the names (they're only unique keys) and record the origin in `sources.json`
- skip `index.npz`: import runs **Audit references**, which re-embeds `refs/` with the
  receiver's embedder, so a different model or version never meets stale vectors

**Run caches (layer 4) stay out.** Boxes are keyed by image id and detector version, so they're
wrong in another library and stale after a model change; the frame-share cache rebuilds itself.

**Bundle format.** A plain folder `<name>.atpreset/` with a `manifest.json` (plugin, layers,
plugin version, preset schema version, export date, files with sizes). Lua has no zip; a folder
copies with Explorer and needs no new code. A zip is a later option through the Python side
(`zipfile`).

**Import** (**Import preset…**, pick the folder or its manifest):
- runs old keys through the existing upgrade path (`upgrade_preset_text` in grouping, culling's
  equivalent) and refuses a newer schema with the version it needs
- a preset name that exists already asks: replace or keep both (`name (2)`)
- entries: replace (old saved as `entries.json.bak`, as the start-list import does) or merge
  (add entries whose id is new; list clashes, as the importer does)
- refs: copy into `refs/<entry>/`, never overwrite a same-named file, then audit

**Paths inside settings.** Any setting holding a file path (model files, face detector) is
written relative to the plugin folder when it sits under it, otherwise flagged in the export
message, so the bundle carries no `C:\Users\<name>` paths that break on the next machine.

**Where the code goes.** The manifest writer, folder copy and import prompts belong in
`plugin_common.lua` so the three panels behave the same: one edit across all three repos with
COMMON_HASH updated. Layers 2 and 3 are tagging-only code on top.

Open choices (recommendation first):
- refs default **off**, faces a separate box: size and privacy beat convenience
- folder bundle **before** zip: zero new dependencies
- cross-plugin bundle as a **later step**: layer 1 per plugin first
Effort M for layers 1–2 in all three plugins; M again for refs with import + audit.

## Smaller known gaps

- "Open entries.json" on Windows: the `start` command now gets cmd.exe's outer quote
  pair (the old mangled-path failure); confirm on the real pass, step 5.
- Changing any `family_*_root` strands tags under the old root: cleanup only looks
  under the current one. The default roots moved to `Assisted Tagging|Motorsport|<Family>`
  (2026-11-15), so collections tagged under the old `Motorsport|<Family>` defaults hit this
  unless their settings.json pins the old roots. Owning the old root's first segment would also own the run stamps
  (`Assisted Tagging|Run|…`), so a fix needs the old root kept somewhere (settings or ledger).
  Workaround: select the photos, Clear tagging marks, run again.
- A refused run consumes the "Replace manual tags" box (audit N3); it should stay ticked.
- entries.json is written without validating the result first (audit N5).
- Tags set before the ledger existed aren't adopted, and old `Run` stamps are never cleared.
- Combined numbers (8108), struck-through digits and entries with 3+ drivers aren't handled.
- A hand-formatted entries.json gets no colour filler.

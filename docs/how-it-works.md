# How it works and tuning

Part of [darktable-assisted-tagging](../README.md). The pipeline, grouping support, and the tuning constants.

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
taken from the selection and from unselected images in the same film rolls that already carry an entry's tags
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

Each outcome above is one of these methods, named consistently from `identify.py`'s `method` field through to the diagnostic tag it writes (see [Rules](usage.md#rules) to rename or drop one):

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

**Colour tags.** With the [Colour family](usage.md#tag-families) on, each car's paintwork is measured on the middle of its crop (margin, roofline and the lower tyre band are left out) and becomes the palette colour with the largest share. White, grey and black count half, since tarmac, glass and shadow are also in the crop. It is `Multi` when the second colour is close to the first. The decided colour is written as `<family_colour_root>|<name>`. An entry's `colour` is a tie-breaker only, never a filter. A weak number read for an entry whose colour differs from the car's doesn't count towards a group's agreement; the neighbour aid drops candidates whose colour differs and a look-alike car only lends its entry when the colours don't differ; a confident number read is never blocked, but when its entry's colour differs from the car's the image gets *Check colour*. An entry with no `colour`, or a car whose colour can't be told, is neutral. Colours too close to call never count as differing: `Multi` against a single colour, white against grey, grey against black, and the hue neighbours blue/purple, blue/green, red/pink, red/orange, orange/yellow, purple/pink and orange/brown. Turning the family on re-reads every image once.

**RAW+JPEG pairs are read once, from the JPEG.** A RAW and a JPEG in the same folder with the same name before the extension (case ignored, as darktable pairs them on import) are one shot, and so are darktable duplicates of a file. The JPEG is read: it has the camera's exposure and colour at full size. Every file in the shot gets the same tags, and a hand tag on any of them is protected for the whole shot. A RAW with no JPEG is read from the RAW. Same name in another folder is a separate shot.

### Grouping support

Tagging no longer clusters images by capture time. Consensus (the "borrow the answer from the rest of the group" step) runs over groups that something else already made, and the panel's **Grouping Support** combobox picks which:

- **Native groups** (default): darktable's own image groups. An image's group is its group leader.
- **Grouping tags**: the children of an [Assisted Grouping](../../darktable-assisted-grouping/README.md) tag node, e.g. `Assisted Grouping|2026-01-01 12:00:00|Group|NNNN`. The **Grouping tag node (blank = latest run per image)** entry names the node. Blank uses each image's own latest Assisted Grouping run, so after regrouping part of a shoot the regrouped images use the new run and the rest keep the old one. Assisted Grouping must have **Group tags** on, or there is nothing to find. In Native groups mode, if no image is in a group but grouping tags are present, the log and a notice say to switch to Grouping tags.
- **None**: every image is its own group, so nothing is borrowed.

An image with no group (no native group, or no child tag under the node) is its own group. Groups are not size-checked: a coarse group (a long hand-made stack, or Assisted Grouping's Camera or Parent layers) is treated as one car pass, so the missed-detection rescue may carry an identification across the whole group. The log records the mechanism, how many images landed in groups of 2 or more, and (in Grouping tags mode only) the node used.

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

# Using it

Part of [darktable-assisted-tagging](../README.md). Starting a collection, building references, identifying, and the report.

## Using it

The **Assisted Tagging** panel is in lighttable. Start a collection, give its entries some references, then identify a selection.

Running all three plugins? [WORKFLOW.md](../../darktable-assisted-grouping/WORKFLOW.md) says which order to pick and what to re-run after what.

### Starting a collection

A **Collection** is one entry list plus its reference samples: normally one series and season (`F1 2026`), or one event (`BTCC 2026 Brands Hatch`). Collections live in the collections folder, by default `assisted_tagging/collections` in darktable's config directory (the panel creates it the first time it loads). Each one is a folder:

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

If you've already hand-tagged a handful of images — one per competitor, e.g. `Motorsport|F1|Red Bull` on both Red Bull cars and `Motorsport|F1|Red Bull|Max Verstappen` on just his — the panel can turn those into a working collection in one click. This isn't motorsport-specific: it only ever reads whatever `A|B|C`-style tags you've already used, so the same button builds a collection for any set of visually-distinguishable, hierarchically-tagged subjects.

1. In lighttable, select a handful of already-tagged images — **at least 2 per target**, from different angles.
2. Under **New Collection** in the panel, type a name for the collection, e.g. `F1 2026`.
3. Under **New Collection**, click **From Tagged Images**.

It reads each selected image's tags down to wherever two images stop being identical: images carrying the exact same tags become one entry, and whatever tag is unique to an image (the driver tag) is what tells two teammates apart. From that it:

- creates the collection folder with an `entries.json` built from those tag sets, inferring each entry's `team` where a tag is shared with some but not all of the other entries, and its race `number` when the deepest tag's leaf is 1-3 digits (e.g. a `Car|Number|44` convention sets `number: "44"` automatically)
- adds every selected image as a reference sample of its entry, exactly like [**Add Tagged Images**](#building-references)
- switches the panel to the new collection and reloads it

Two kinds of selected image don't become an entry, and are reported in the done message rather than silently dropped:

- an image with no tag that looks like `A|B` has nothing to build an entry from
- a tag that only 1 selected image carries is skipped rather than turned into a single-sample entry — a lone sample tells the matcher nothing about how that target varies across angles and light, so it's better surfaced as "needs more references" than quietly matched (and likely mismatched) later. Select at least 2 images per target to avoid this.

If you want number-based identification but your tags don't already encode the number, or you want custom [rules](#rules), add those by hand afterward (see below). If a collection with that name already exists, nothing is overwritten — pick a new name, or switch to the existing one and use **Add Tagged Images** instead.

#### From an example

No tagged images yet, or just want to see the shape of a working `entries.json`? The **Example** dropdown in the panel lists the collections shipped in [`examples/`](../examples) — no images needed, since these ship with their structure already filled in (with placeholder names, not real references):

1. Pick one in the **Example** dropdown.
2. Click **View Example** to open its `entries.json` in your editor and read it, or
3. type a name under **New Collection** and click **From Example** to copy it into a real collection.

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

A file that's just the `[ … ]` list of entries works too, with the default rules — this is the shape **new collection → From Tagged Images** writes, each entry with its tags in full. You can hand-edit the result to add numbers or rules.

[`examples/`](../examples) has four collections — pick one from the panel's **Example** dropdown (see [above](#from-an-example)), which copies its `entries.json` and `settings.json`, or copy its folder into the collections folder by hand. Each has a README on what it shows and how to supply its references:

- [`f1-season`](../examples/f1-season): a season with near-identical teammates, a one-off livery and number-less cars
- [`btcc-event`](../examples/btcc-event): one race weekend, with a "check me" tag for misses and no team-only tags
- [`minimal`](../examples/minimal): a bare entry list on the default rules
- [`rally`](../examples/rally): number-only entries for cars of no known livery, with the neighbour aid on (`order_weight`) and its own family roots, and grouping support set to Grouping tags, all set in its `settings.json`

#### Entries

| Field | Required | Rules |
|---|---|---|
| `id` | yes | unique within the collection; it's also the folder name under `refs/`, so it can't contain `, ; " / \ : * ? < > \|` |
| `tags` | only when no [tag family](#tag-families) builds a tag for the entry | one or more darktable tag names (`\|` makes a hierarchy); no `,` `;` or `"`. Extras added after the family tags |
| `name` | no | the driver's display name, e.g. `Max Verstappen`; the Driver family writes it as `<root>\|<name>` |
| `co_driver` | no | a rally co-driver's display name; the Co-driver family writes it as `<root>\|<co_driver>`. No `,` `;` or `"`. Entries without one get no co-driver tag |
| `number` | no | the race number, 1–3 digits. Leave it out for a car with no number; it can then only be identified by livery. Set it to `"-"` by hand for a car that genuinely has no number but still needs the number key filled: it builds the tag `<number root>\|-`, is never read from an image or imported, and never identifies a car. Two entries with the same number are allowed, but that number then identifies neither. |
| numbers-only entry | | `{"id": "12", "number": "12"}`: an entry with a number and no `team`, `name` or `tags` gets the Number family's tag, `Assisted Tagging\|Motorsport\|Number\|12` by default. Build a whole list from a CSV with `python python/import_numbers.py numbers.csv entries.json`, or add a full start list (names, teams, classes) with the panel's **Import Start List** (see [1 collection](panel-options.md#1-collection)); see [`rally`](../examples/rally) |
| `team` | no | the Team family writes it as `<root>\|<team>`; entries with the same team can fall back to their shared tags when their liveries are too close to call |
| `extra` | no | the entry's class (the start list's Class column); the Class family writes it as `<root>\|<extra>`. No `\|` `,` `;` or `"` |
| `make`, `model` | no | the car's make and model; the Vehicle family writes `<root>\|<make>\|<model>`, or `<root>\|<make>` without a model. A `model` needs a `make`. No `\|` `,` `;` or `"` |
| `colour` | no | the car's paintwork colour: a name in the active palette, or `Multi` (needs the [Colour family](#tag-families)). Breaks ties between number candidates and flags a number read that disagrees; never a hard filter. The reference actions fill it in when it is missing |
| `car` | no | a double-driven car: the id of the other entry in the same car, set on the higher-numbered entry only (`"car": "30"` on 730). Both entries then carry each other's tags, so any match on the car (number read, livery, hand tag) tags both drivers, and their livery references count as one car. Two entries per car at most. A combined number on the car (`8108`) stays unknown: tag `Number seen\|108` by hand |
| `shows` | no | other numbers the car carries besides its entry number, as a list (`"shows": ["44"]`): an old event's number left on the door, or a covered digit (`808` on 108). A read of a shown number names this entry; when another entry has that number too, livery picks only between the entries carrying it. 1–3 digits each, not the entry's own number |
| `paddock` | no | where the car parks, as printed on the entry list (`"paddock": "H3"`). Free text, never read by a match; the start-list import fills it from the **Paddock** column. A demonstration entry also uses it as its id |

Teammates share their team tag, so a team-only result carries exactly the team tag. The examples leave the year out of the tags: the collection already separates seasons for matching, and darktable's collections module filters by capture date. A **livery change** mid-season is a new entry (`VER-miami`, with the same tags and no `number`, so the number still identifies `VER`) or a new collection.

#### Tag families

A family is one kind of tag the plugin writes. Each has a switch and a root in the collection's [`settings.json`](#collection-settings-settingsjson) (panel page **4 Tags Written**, heading **Tag Families**), and writes `<root>|<value>`:

| Family | Value | Switch | Root setting | Default root |
|---|---|---|---|---|
| Colour | the paintwork colour read from the image | `family_colour` | `family_colour_root` | `Assisted Tagging\|Motorsport\|Colour` |
| Number | the entry's `number` | `family_number` | `family_number_root` | `Assisted Tagging\|Motorsport\|Number` |
| Team | the entry's `team` | `family_team` | `family_team_root` | `Assisted Tagging\|Motorsport\|Team` |
| Driver | the entry's `name` | `family_driver` | `family_driver_root` | `Assisted Tagging\|Motorsport\|Driver` |
| Co-driver | the entry's `co_driver` | `family_co_driver` | `family_co_driver_root` | `Assisted Tagging\|Motorsport\|Co-driver` |
| Class | the entry's `extra` | `family_extra` | `family_extra_root` | `Assisted Tagging\|Motorsport\|Class` |
| Vehicle | the entry's `make` and `model`, as `<make>\|<model>` | `family_vehicle` | `family_vehicle_root` | `Assisted Tagging\|Motorsport\|Vehicle` |
| Paddock | the entry's `paddock` id | `family_paddock` | `family_paddock_root` | `Assisted Tagging\|Motorsport\|Paddock` |
| Sponsor | each [`sponsor_keywords`](#rules) word read inside a vehicle box, title-cased (`castrol` → `Castrol`) unless [`sponsor_names`](#rules) spells it; words read on banners or not listed are never written. Off by default | `family_sponsor` | `family_sponsor_root` | `Assisted Tagging\|Motorsport\|Sponsor` |

All nine are on by default except Sponsor. An identified entry gets one tag per family that is on and that it has a value for, then its own `tags`. An entry that builds no tag at all stops the run.

An older entries.json may hold `Motorsport|Class|…` and `Motorsport|Vehicle|…` entry tags from an earlier start-list import. The next reload moves them into the `extra`, `make` and `model` fields and keeps the previous file as `entries.json.bak`. A field that disagrees with its tag, or a tag deeper than `Motorsport|Class|<class>` or `Motorsport|Vehicle|<make>|<model>`, stops the load and names the entry; fix it by hand.

A root is a tag path: no `,` `;` or `"`, and it can't start or end with `|` or a space. Each family needs its own root: no root may equal another or sit under it. Switching a family off stops runs writing its tags; the Colour family also reads the colour, so switching it on re-reads every image once.

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
| `group_support` | which groups the burst step borrows answers from, see [Grouping support](how-it-works.md#grouping-support) | `"native"`, `"tags"`, `"none"` | `"native"` | yes |
| `group_node` | the grouping tag node used when `group_support` is `"tags"`; blank uses each image's own latest Assisted Grouping run | text | `""` | yes |
| `run_tag` | stamps images with `Assisted Tagging\|Run\|YYYY-MM-DD HH:MM`: `changed` only copies whose tags the run added or removed, `all` every copy it processes (slow on large shoots). Old `true`/`false` files read as `all`/`none` | `none`, `changed`, `all` | `none` | yes |
| `suggest_crops` | **Audit References** suggests re-crops | `true`, `false` | `false` | yes |
| `quarantine` | **Audit References** quarantines poor references | `true`, `false` | `false` | yes |
| `cars_per_photo` | `solo`: only each image's largest car is tagged; a smaller car counts only when its number is read, so background cars add no car or colour tags. `packs`: every car found is tagged (circuit racing) | `solo`, `packs` | `solo` | yes |
| `closer_car_margin` | a livery, burst or neighbour match that doesn't look like its car's anchors is normally left without an entry tag. Above `0`, a livery match that is closer to another car's anchors by this much similarity or more is tagged as that car instead, still with *Check match* (burst and neighbour matches are never moved). `0.12` was right in 11 of 11 checkable moves on a 3,655-image rally. It never moves to a car two entries share (it can't say which driver), to a car another box of the image already has, or to a car other than the ones a number read of 0.90 or more, or a tag you applied, names in the same burst. `0`: never moved | number, 0 to 1 | `0` | no |
| `order_weight` | how closely the cars pass in number order: `0` is random (the neighbour aid is off), `1` is strictly in order. Above 0, groups shot just before and after a doubtful read help identify it, including unselected images in the same film rolls already tagged with an entry; from `0.5` up an unsupported doubtful read is flagged *Check order*; see [How it works](how-it-works.md#how-it-works) | number, 0 to 1 | `0` | yes |
| `neighbour_tolerance` | the most places apart in the sorted number list a neighbouring car can be and still support a read; `order_weight` sets how much of it is used (up to `order_weight × (tolerance + 1)` places) | whole number, 0 or more | `5` | yes |
| `min_read` | how sure a number read must be to count. A read's confidence is the lower of two scores: how sure the text detector is that it found text, and how sure the reader is of its least certain digit. Raise it if plates or signs get read as numbers; lower it if clear numbers are missed | number, 0 to 1 | `0.85` | yes |
| `colour_weight` | how much the colour histogram counts in livery matching, from `0` (off) up. Separate from the Colour family | number, 0 or more | `0` | yes |
| `partial_references` | **Add Tagged Images** also accepts a solo shot tagged only to team level (e.g. `Assisted Tagging\|Motorsport\|Team\|Red Bull`) and saves it as a team reference under `refs/@team@…`. When no driver is clear but one team's references lead clearly, the result is *team* (shared tags only) | `true`, `false` | `false` | yes |
| `min_sim` | people collections: the least face similarity that counts as a match | number, above 0 up to 1 | `0.5` | no |
| `margin` | people collections: how far the best face match must lead the runner-up | number, 0 up to but not including 1 | `0.05` | no |
| `min_face_px` | people collections: the smallest face, in pixels, that is used | whole number, 1 or more | `48` | no |
| `burst_livery_pooling` | experimental: resolves a burst frame that didn't clear the threshold from the burst's pooled livery similarity (*By pooled burst*). Only a clear pooled match names a car, never a team tie; a burst with a frame read as another car is left alone, and so is a frame whose main box is overlapped, already identified, a team result for another team, or under a tag or sponsor hint that leaves the car out. A frame whose colour read differs from the pooled car's colour is left out of the pool and the fill; the rest are pooled again without it | `true`, `false` | `false` | no |
| `blur_references` | blurs reference crops before they are compared | `true`, `false` | `false` | no |
| `number_gate` | experimental: skips the number read on a box where SigLIP 2 sees no number (see [Number gate](models.md#number-gate-experimental-siglip-2)); does nothing without SigLIP 2 | `true`, `false` | `false` | no |
| `second_reader` | a number counts only when PARSeq reads it too (see [Second reader](models.md#second-reader-optional-parseq)); does nothing without the PARSeq model | `true`, `false` | `false` | no |
| `family_colour`, `family_number`, `family_team`, `family_driver`, `family_co_driver`, `family_extra`, `family_vehicle`, `family_sponsor` | write that [tag family](#tag-families); `family_colour` also reads each car's paintwork colour, and turning it on re-reads every image once | `true`, `false` | `true` (`family_sponsor`: `false`) | yes |
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

1. In the panel, open **4 Tags Written**.
2. Type the new base name in the text box under the diagnostic's switch (it shows the default name as a placeholder; blank means the default).
3. Choose **Actions** → **update preset**.

The next run writes the new name. `settings.json` ends up with, for example:

```json
"tag_number_seen_name": "Cars|Number seen",
"tag_shot_name": "Cars|Framing"
```

Tags written under the old name stay on images the run doesn't touch; darktable keeps the old name in its tag list until you delete it.

#### Checking what it will tag

Click **Show Tag Plan** in the panel. It writes `tag-plan.txt` next to the collection's `entries.json` and opens it in your system's app for .txt files, listing exactly what each outcome writes: every entry's tags and reference count, the team-only tags for each pair of teammates, the unidentified tags (headed `unidentified tags (yours)`), and the diagnostic tags. It also lists entries that can only be identified by number, and entries that can't be identified at all until they have references. The file is rewritten on every run and **Reload**, so it always matches `entries.json`.

After editing `entries.json`, click **Reload** in the panel. A mistake in the file stops the run with the file name and what's wrong.

### Building references

Numbers aren't readable in every shot (rear views, motion blur, a number hidden by the halo), so each entry also needs a few **reference samples**: crops of that car the plugin compares new images against. 3–5 per car from different angles is a good start; add more for the angles it gets wrong. **new collection → From Tagged Images** already does this for the images it was given; add more at any time with the panel's **6 references** page:

- **Add as Reference**: pick the entry in the **Entry** list, select images of that car, click. Each image saves one vehicle under that entry: the one whose number reads as the entry's, else the largest the [box check](models.md#box-check-and-colour-reader-optional-siglip-2) keeps, else the largest. The log names which (`number read`, `largest car`, `largest box`). An image where no vehicle is found saves nothing, and the done message says how many.
- **Add Tagged Images**: select images you've already tagged by hand. Each one carrying *all* of one entry's tags is added under that entry. Only your own tags count: tags the plugin wrote (its ledger) never make an image a reference, so selecting a whole collection is safe. An image with only a shared team tag, or with two drivers' tags, is skipped.
- **Add from Last Run**: select images from the last **Identify Selection** run. Each vehicle whose number that run read is saved under the entry it found. This works for pack shots: the saved crop is that one car, not the whole image, so the entry's tag doesn't have to describe the frame. Burst, team-only and held-back results are never saved. Images changed since the run are skipped.
- **Identify Colour for Group / for Selection** (Run page; needs the **Colour** family on, page 4): select images, click. Works like Copy Tags: the selected images are read from the paintwork of their largest car (a selected image's colour tag counts as its reading), and the colour two thirds of them agree on (near colours count with it) becomes `<colour root>|<colour>` on every image without a colour tag, in the selection (**for Selection**) or in each selected image's darktable group (**for Group**, one vote per group). Readings that disagree tag nothing, and the done message counts those images. **for Group** with no selected image in a group of two or more says so and reads nothing. The tag counts as the plugin's (the ledger holds it), so Identify may replace it. An image that already has a colour tag, or is locked, keeps its tags. No reference is saved. Images that also name one entry vote on that entry's `colour` in `entries.json`, which is written when it has none: the colour most of them read is written when it and the colours near it (listed under **Colour tags** in How it works) are two thirds of the reads, so one burst in odd light can't set it; a tie writes nothing. A colour tag you applied to the image is used instead of the reading and replaces a colour the entry already has, so to correct a wrong entry colour, tag one image of that car with the right colour and click. The entry tags Identify wrote name the entry as well as yours, so check the images really show that car. Without a colour tag of yours, the colour tags Identify wrote stand in for it when at least 3 of the entry's selected images carry the leading colour or one near it and they are two thirds of its colour-tagged selected images (images tagged Check colour don't count): select a run of images of one car that Identify tagged with the right colour and click. The log names the count per entry. Readings replace a stored colour only when at least 5 of the entry's selected images were read and 90% of them back one colour that clashes with it (a near colour or `Multi` never does); the log names the count, and `entries.json.bak` keeps the old file. Short of that, the stored colour stays and the log names each reading that differs. The done message counts the images tagged, the entries set, those that already had that colour and the images where no car or colour could be read, and names the file. An image that lacks some of an entry's tags still names it when its number, driver or co-driver tag names one entry. An image that has a colour tag and whose tags match no single entry has nothing to do and is skipped; the log says which entry is nearest and which of its tags the image lacks.
- **Entry colour** (**Colour** family on): the three add actions above also fill an entry's missing `colour` in `entries.json` from the one colour tag you applied by hand to the image, else from the plugin's reading of the saved car. An entry that already has a different colour keeps it unless the job's readings overturn it as in **Identify Colour**; otherwise the log says so and the done message counts it. `entries.json.bak` keeps the previous file. A file not laid out one entry per line is rewritten that way. The reference job's result rows are `id,status,colour_note,entry_id`; a Identify Colour row that read a colour adds it as a fifth column.
- **Add-time screening** (vehicle collections): after saving, both reference actions run the audit's mislabel, copy, outlier, colour and crop checks on the new refs. **Add confident vehicles** does not save a box that 2+ checks flag (the log names them; the summary counts them as not saved). **Add references** keeps the ref but logs the flags, since you named the car. Entries with too few refs for a check pass it, and the whole-frame and attractor checks don't run at add time.
- **Audit References**: needs no selected images. Refreshes the collection's `index.npz` from `refs/` (deleted or moved crops drop out, new ones are embedded), then writes `ref-audit.txt` in the collection folder. Sections: *strongest candidates* (refs flagged by two or more of the checks below; start there), *mislabel suspects* (closer to another entry's refs than its own by 0.2 or more), *cross-entry copies* (near-identical crop filed under two entries), *outliers* (far from the rest of its entry), *odd crops* (crop size or shape far from the entry's usual: a distant car, a whole frame, a nose-only cut; unusual angles are not flagged by this one), *whole frames* (the vehicle detector finds no car in the ref, or one under 15% of it, so scenery drives its matches; re-crop or delete), *attractors* (correctly filed refs that are the closest match for three or more refs of other teams' entries, so an odd angle or size pulls other cars toward them; teammates' pulls are shown but not counted), *colour outliers* (livery hue and saturation unlike the entry's typical colours from the same event, brightness ignored; refs are grouped into events by filename id, where ids more than 1000 apart are different race weekends, and the event ranges are printed at the top of the report; `looks like [entry]` names a better colour match) and *redundant* (near-duplicates within an entry) and *duplicate groups* (near-identical crops with their similarity; many are burst frames of the same car and fine to keep, so judge by eye). The whole-frame check also fires when the detector misses a dark or blurred car (tight crops often do), so look before deleting; refs with no car found are listed but don't count toward *strongest candidates*. The report shows the first 40 per section and every whole frame is in `ref-audit-frames.txt`. Each ref's car share is cached in `frame-share-cache.json`, so only the first audit is slow (about 8 minutes for 2000 refs, then seconds). Starting another action while one runs queues it; cancelling drops the queue. Two panel checkboxes above the button, both off by default: **Audit: Suggest Re-Crops** also writes re-cut copies of wide refs where the detector found exactly one car into `ref-audit-crops/<entry>/` for you to review and copy over the ref (nothing in `refs/` changes; the first run with it ticked re-detects every ref, about 8 minutes), and **Audit: Quarantine Poor Refs** moves the refs flagged by 2+ checks into `refs-quarantine/<entry>/` after the report is written, listing each in `moved.txt` there, then refreshes `index.npz`. To undo, copy a file back into `refs/<entry>/` and re-run the audit. On a terminal: `--suggest-crops` and `--quarantine`. The audit never moves or deletes anything: check the listed crops, then delete or move them yourself. An entry needs 5 or more refs for the *outliers* check, and 4 or more for *colour outliers* and *odd crops*; smaller entries are skipped by those checks. It also runs from a terminal: `python python/audit_refs.py COLLECTION_DIR` (embedding, colour and crop checks only, no index refresh; add `--detector path/to/yolox.onnx` for the whole-frame check). The run log is rewritten, so audit before reading an Identify log.

Each sample is a JPG in `refs/<entry id>/`, named after the darktable image id. Adding the same image again replaces its sample. A selected RAW whose JPEG is also in darktable (same folder, same name before the extension) is read from the JPEG, so the sample is named after the JPEG's id; its entry still comes from the tags on the image you selected. **Add confident vehicles** swaps a RAW for its JPEG the same way, since Identify recorded the JPEG's vehicles. To remove a bad sample, delete its JPG; the next run notices.

### Identifying

In lighttable, select a batch and click **Identify Selection** in the **Assisted Tagging** panel. Progress shows in darktable's message area; click the button again to cancel. A cancelled run changes no tags.

Every vehicle that gets an entry adds that entry's tags to the image, so an image of two cars battling gets both; the collection's [rules](#rules) decide what team-only and unidentified images get. Images also get a tag saying how they were identified. These are the default names; [`settings.json`](#collection-settings-settingsjson) can rename each one per collection (see [Renaming tags](#renaming-tags)), and the switches under **Tags Written** [turn each one off](#choosing-which-diagnostics-are-written):

| Tag | Meaning |
|---|---|
| `Assisted Tagging\|Identification\|By number` | its race number was read |
| `Assisted Tagging\|Identification\|By livery` | matched against reference samples |
| `Assisted Tagging\|Identification\|By burst` | the rest of its burst agreed on one entry |
| `Assisted Tagging\|Identification\|By pooled burst` | the experimental `burst_livery_pooling` rule resolved it from its burst's pooled livery similarity |
| `Assisted Tagging\|Identification\|By neighbour` | a doubtful number read was settled by the groups shot just before and after (needs `order_weight` above 0) |
| `Assisted Tagging\|Identification\|Check order` | a low-confidence number read that no neighbouring group supports; the entry tag stays. Delete the tag once checked |
| `Assisted Tagging\|Identification\|Check colour` | a number read whose entry's `colour` differs from the car's paintwork colour (needs the Colour family); the entry tag stays. Delete the tag once checked. When at least 5 of an entry's number reads are made and 90% of them back one clashing colour, the run log adds `colour: check entry <id>: <stored> in entries.json, N of its M number reads see <colour>`: its stored colour is likely wrong (fix it with **Identify Colour**). A run never changes entries.json |
| `Assisted Tagging\|Identification\|Team only` | two teammates were too close to call; only their shared tags were added |
| `Assisted Tagging\|Identification\|Unidentified` | no vehicle, or no confident match |
| `Assisted Tagging\|Identification\|Number seen\|<digits>` | OCR read these digits but they didn't resolve to one entry; added alongside the outcome tag. Also set, even on an identified image, for a 1 to 3 digit number no entry has that is read at weak read min or more on 3+ images of one burst, so **Find New Entries** lists it |
| `Assisted Tagging\|Motorsport\|Sponsor\|<Word>` | a listed sponsor word OCR read on the car (Sponsor family, off by default) |
| `Assisted Tagging\|Motorsport\|Colour\|<name>` | the car's paintwork colour (`Red`, `Orange`, `Yellow`, `Green`, `Blue`, `Purple`, `Pink`, `Brown`, `White`, `Grey`, `Black`, or `Multi` for a two-tone car; silver reads as `Grey`; read by SigLIP 2 when it is installed, else by hue rules, see [Box check and colour reader](models.md#box-check-and-colour-reader-optional-siglip-2)); the Colour family, under `family_colour_root`. Filter on it to hand-sort cars by colour |
| `Assisted Tagging\|Identification\|Shot\|Solo` | one vehicle was found in the frame |
| `Assisted Tagging\|Identification\|Shot\|Pack` | two or three vehicles were found |
| `Assisted Tagging\|Identification\|Shot\|Crowded` | the detector's limit (`MAX_BOXES`) was reached, so there may be more cars than were identified |

#### Choosing which diagnostics are written

Each row above has its own switch under **Tags Written** in the panel, saved in the collection's `settings.json` and all on by default (`Shot` is one switch for `Solo` and `Pack`; `Shot crowded` has its own). Each switch's tooltip names the tag it writes under this collection's settings. Turn off the ones you don't use to keep darktable's tag list short:

- **Off** = the next run stops writing that diagnostic and removes it from the images it processes, under whatever name the collection's settings give it. One never written never shows up in the tag list.
- **Identification doesn't change.** Entry tags, team-only and unidentified tags from `entries.json` are still written.
- Images outside the run keep their old diagnostics. darktable keeps tag names nobody uses any more in its tag list; delete them in the tagging module's dictionary.

Filter on `Assisted Tagging|Identification|By livery` and `Assisted Tagging|Identification|Unidentified` in the **collections** module to spot-check the uncertain ones; an image it got wrong is often a good new reference.

Tick **Tag Each Run** in the panel to also stamp every image a run writes with `Assisted Tagging|Run|YYYY-MM-DD HH:MM`, so the latest run's images can be filtered apart from earlier ones. Stamps are never removed by later runs; delete old ones in darktable's tag manager.

Re-running is safe: each image's entry and diagnostic tags are synced to the new result, so a frame that moves from one driver to another loses the old driver's tags. Tags that aren't in the active collection are never touched.

#### Tags you apply by hand

The plugin keeps a ledger (`assisted_tagging/ledger.csv` in darktable's config directory, lines `<library>,id,tag`) of the tags it attached to each image. `<library>` is a hash of the library file's path, so two libraries that reuse the same image ids keep separate ledger lines (lines from before this column belong to the library in use when they're first read; a library opened with `--library` on the command line isn't visible to the plugin and counts as the configured one). Lines for images removed from the library are dropped whenever the ledger is saved, and a failed save is tried once more before an on-screen error. An entry tag on an image that isn't in its ledger is yours, at any depth (team or driver), and a run never removes it. So an image you tagged to a team stays that way even when the run can't tell the driver.

**Clear Tagging Marks** reads the same ledger, so hand-applied tags survive it even when they sit under the plugin's roots.

- A **number, driver or co-driver tag** you applied (such as `Assisted Tagging|Motorsport|Number|4` or `Assisted Tagging|Motorsport|Driver|Norris`; needs that family on) **identifies the car**: the run adds the entry's other tags and counts the image as *by your tag*. A solo shot read as a different car is held back as a conflict. A driver or co-driver name two entries share, or tags naming two different entries, identify no car; the log says so and the tags stay.
- A hand-tagged frame also supports its burst and the frames shot around it, like a confident number read.
- Hand-applied family tags (number, driver, team, colour), listed in `entries.json` or not, are never removed unless **Replace Manual Tags** is ticked.
- A **solo shot** whose result disagrees with the tags you applied is left as you had it: nothing is added, it doesn't get the *Unidentified* tags, and the done message counts it. Packs aren't checked, since you may have tagged just one of the cars.
- A **team tag** you applied (an entry's Team family tag, such as `Assisted Tagging|Motorsport|Team|Red Bull`; needs the Team family on) is a **hint** on a solo shot: matching is limited to the entries under it. If none of them looks similar enough, or the number read belongs to a car outside it, the hint is dropped and the normal match runs. The report lists each hint and any that were dropped. Packs get no tag hints, since the tag may describe only one car. Untick **Use Team Tags as Hints** in the panel to ignore team tags instead: matching isn't narrowed, and a differing result is not held back as a conflict, so the run can override your team tag. The tag itself stays on the image beside whatever the run adds (tick **Replace Manual Tags** too to have the run overwrite it). Driver-level tags still protect their images either way.
- An image already carrying all of one entry's tags is **skipped** without being analysed.
- A **locked** image (**Lock In Tags**, page 7) is never changed, even with **Replace Manual Tags** ticked; the log says `<id>: locked, skipped`. It is still analysed, so the entry its tags name supports its burst like any hand tag.
- To let a run replace your tags, tick **Replace Manual Tags** under **Identify Selection**. It stays ticked across runs and restarts until you untick it.
- If you remove a tag the plugin attached and later apply it again by hand, it counts as yours.
- After you rename or remove an entry, the next run over those images takes off the old tags the plugin attached. This covers tags under the collection's own top-level tags (e.g. `Motorsport|…`), so tags another collection attached stay.
- Images tagged by an older version have no ledger, so all their entry tags count as yours.
- A colour tag you apply by hand is never removed by a run; only the colour tag the plugin attached is replaced. The same goes for a diagnostic, *Unidentified* or *Number seen* tag you applied by hand: it stays (the identifier is not told about it, so it never reads as an entry tag). The one exception is the *Unidentified* tags: once a run identifies the image, holds it to your own car tags, or skips it as already carrying all of one entry's tags, they no longer hold and are removed, whoever attached them.

**After culling.** To tag only the keepers, collect by the tag `Assisted Culling|Keeper` in darktable's collections module, select them and click **Identify Selection**. Consensus then runs over the keepers alone, so expect more *By livery* and *Unidentified* results; re-run on the full burst to fill them in.

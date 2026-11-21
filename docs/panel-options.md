# Panel options

Part of [darktable-assisted-tagging](../README.md). Presets, every panel setting, and the preferences.

## Presets

In Assisted Tagging each collection is a preset: the **Preset** picker at the top of the panel lists your collections, and a collection's panel settings live in its folder as `settings.json`, beside `entries.json`.

- **Preset**: `template` first, then every collection folder with an `entries.json`, by name. Picking one loads its entries and its settings. The panel opens on the last one you picked.
- **template**: the built-in defaults. It shows only the **New Collection** controls; pick a collection to identify. A collection can't be named `template`.
- **Actions** beside it: **update preset "<name>"** saves the panel's settings into the collection's `settings.json`; **rename preset…** renames the collection folder (type the name, then **OK**); **delete preset** asks first, then deletes `settings.json` only, never the folder, `entries.json` or the references, so the collection goes back to the defaults. **store new preset…** copies the selected collection to a new folder (entries, references and all) with the panel's settings: type the name, **OK**, then it shows how many reference crops and MB it will copy and waits for **Store**. It is refused on **template** and while a run is going. Empty new collections still come from the **New Collection** controls.
- **Unsaved Changes** shows under the picker when the panel differs from the saved settings. Switching collections drops them. Text fields have no change signal, so their edits show when **Actions** is opened or a run starts.
- Every run and reference action uses the settings the panel shows, whether or not you clicked **update preset**: the action writes them to a temporary settings file for that job. **Unsaved Changes** only means the panel differs from `settings.json`; it never means a run will use older values.
- A new collection has no `settings.json` and uses the defaults until its first **update preset**. A setting missing from the file uses its default; **update preset** writes every setting. A value that's no longer valid uses the default and logs one line naming the collection and setting.
- A `settings.json` that can't be read or parsed: the panel says so, names the file, and keeps its current values. The plugin never rewrites a broken file; fix or delete it.
- While a run is going (or queued), switching, renaming and deleting are refused until it finishes.

## Panel options

At the top: the **Preset** picker and **Actions** (see [Presets](#presets)), and **Reload**, which rereads the collections folder and the active collection's `entries.json` and `settings.json`. On `template` the panel shows only **New Collection**. On a collection it shows **Open entries.json** and **Open settings.json** (see [1 collection](#1-collection)), then the page buttons **1 collection ▸**, **2 bursts ▸**, **3 matching ▸**, **4 tags written ▸**, **5 run ▸** and **6 references ▸**: clicking one opens its contents below it (its label ends in **▾**) and folds the others; clicking the open one folds it. The open page is remembered across restarts. Below the pages sit the [To check](#to-check) box and the progress line. darktable's reset button (↺ in the panel header) puts every setting back to the template defaults.

### New Collection

- **Name** (text field, e.g. `F1 2026`). The folder name for a new collection.
- **From Tagged Images.** Builds the collection from the selected images' tags (see [From already-tagged images](usage.md#from-already-tagged-images-recommended)).
- **Example**, **View Example**, **From Example.** Pick a shipped example, open its `entries.json`, or copy it into a new collection (see [From an example](usage.md#from-an-example)).

### 1 Collection

- **Show Tag Plan.** Writes `tag-plan.txt` and opens it (see [Checking what it will tag](usage.md#checking-what-it-will-tag)).
- **Open entries.json.** In the top area, above the page buttons, so it shows whichever page is open. It opens the collection's `entries.json` in the app your system uses for `.json` files; save it there, then click **Reload**. If the file can't be opened, the message names its path.
- **Open settings.json.** Beside **Open entries.json**, the same way for the collection's `settings.json`: for a hand edit such as deleting a removed setting (see [Coming from `tag_prefix`](usage.md#tag-families)). Click **Reload** after saving; unsaved panel changes are replaced. A collection whose settings were never saved has no `settings.json`, and the message names the path.
- **Start List** → **Import Start List CSV** / **Add Entry.** Adds entries to the collection's `entries.json`. Two tabs pick the source, the button's label follows the open tab (**Import Start List CSV** on the CSV tab, **Add Entry** on the **Single Entry** tab), and the button reads the open one. **CSV File:** choose a CSV with a header row (number, driver, co-driver, team, class, make, model, colour, shares car with, paddock; any other columns are ignored). **Single Entry:** type a single entry, one box per role (number, driver, co-driver, team, class, make, model, colour, paddock); only number is required, and the boxes clear after the import. It goes through the same import as a one-row CSV, so the rules below hold. It has no shares car with box: both entries of a shared car must be in the same list, so use the CSV for those. On the CSV tab, choosing the file fills one picker per role (number, driver, co-driver, team, class, make, model, colour, shares car with, paddock) with its headers, preset to the usual names; change any that guessed wrong, or set it to **(none)**. Only `number` is required. With co-driver on (none), a driver cell holding both crew (`Smith / Jones`) is split. Each entry becomes `{"id": "<number>", "number": "<number>", "name": "<driver>", "co_driver": "<co-driver>", "team": "<team>", "extra": "<class>", "make": "<make>", "model": "<model>", "colour": "<colour>", "paddock": "<paddock>"}`, with the empty fields left out; a model needs a make. The [Class and Vehicle families](usage.md#tag-families) write the tags. A double-driven car: a **Shares Car With** column (role `shares-car`) names the other entry in the same car; both rows must name each other, and the higher number gets `"car": "<lower number>"`, so every image of that car gets both entries' tags. Demonstration runs: a row whose **Class** starts with "Demo" gets its **Paddock** value as id (`{"id": "A11", "number": "14"}`; spaces dropped, so `Office 1` is `Office1`), so demo 14 and race car 14 are separate entries and its refs live in `refs/A11/`; it still gets the Number tag `14`. A demo row with no paddock stops the import, so demo rows need the CSV or a paddock typed on the **Single Entry** tab. An entry already in the file as `14` or `D14` with the same driver is renamed to its paddock id, and its refs folder, `refs/sources.json` records and any `car` naming it follow. Other ids already in the file, and race numbers another race entry holds, are kept and listed in the message, the previous file is saved as `entries.json.bak`, and the lists reload. A file not in the one-entry-per-line layout is rewritten that way. Same thing from a shell: `python python/import_start_list.py <collection folder> --csv start.csv [--columns "number=No."]` or `--text pasted.txt`; `--columns "team="` leaves a role out, and `--csv start.csv --header` prints the headers and their guessed roles.

### 2 Bursts

- **Grouping Support** (Native groups, Grouping tags, None). What the burst step borrows answers from (see [Grouping support](how-it-works.md#grouping-support)).
- **Grouping tag node (blank = latest run per image)** (text field). The tag node in Grouping tags mode.

### 3 Matching

- **Use Team Tags as Hints** (on by default). A team tag you applied narrows matching on a solo shot.
- **Order Weight** (text field, default 0). `order_weight` in `settings.json`: a number from 0 to 1, where 0 turns the neighbour aid off. Anything else is refused.
- **Neighbour Tolerance** (text field, default 5). The most places apart in the sorted number list a neighbouring car can be and still support a read; `order_weight` sets how much of it is used (up to `order_weight × (tolerance + 1)` places). A whole number, 0 or more (anything else refuses the run). Only used when `order_weight` is above 0.

### 4 Tags Written

First the four [tag families](usage.md#tag-families): a switch each, with its root beside it (blank means the default root). Then one switch per diagnostic (default on), each on one line with the tag name it writes beside it, under two headings: **Checks** (`Check order`, `Unidentified (check)`, `Check colour`, `Shot`, `Shot crowded`) and **How It Decided** (`By number`, `By livery`, `By burst`, `By pooled burst`, `By neighbour`, `Team only`, `Number seen`). Off removes that diagnostic on the next run; see [Choosing which diagnostics are written](usage.md#choosing-which-diagnostics-are-written). A switch whose tag needs another setting shows why it is off in its label, e.g. `Check colour (off: the Colour family is off)`, and is greyed until that setting is on. A `settings.json` from before *Shot crowded* existed loads with `tag_shot_crowded` and `tag_shot_crowded_name` copied from the Shot switch, once, and the log says so.

### 5 Run

The page holds the identify runs (models; writes tags).

- **Replace Manual Tags.** Lets runs replace tags you applied by hand; stays ticked until you untick it (see [Tags you apply by hand](usage.md#tags-you-apply-by-hand)).
- **Tag Each Run.** Stamps every image a run writes with `Assisted Tagging|Run|YYYY-MM-DD HH:MM`.
- **Identify Selection.** Identifies and tags the selection (see [Identifying](usage.md#identifying)). Click again to cancel. When a box's colour is read and no number is, only entries whose colour can match are compared. The filter is dropped when a confident number names an entry of another colour, or when no remaining entry is similar enough, so colour alone never identifies a car. Writes darktable tags, the tag ledger, `boxes.json` and the report; never `entries.json`.
- **Verify Selection.** Identifies the selection, fully tagged images included, and reports where the result differs from your tags. No tags change.
- **Identify Missing Entries.** Identifies the selected images that name no entry, choosing only from the missing entries: those no image in the current collection carries (both entries of a shared car count as carried when either is). Number reads, bursts and the neighbour aid still use the whole start list, so a carried car is never pushed onto a missing one. Every image it names gets Check match: review them with **Verify Selection**. The log lists the missing entries; the done message counts how many were found.

### 6 References

The page has three sections. Only the first uses the **Entry** list.

- **Add to One Entry**: a search box, **Match**, **Apply Entry to Selected**, **Entry** (the entry **Add as Reference** saves under) and **Add as Reference**. The search box matches every word you type against every field of every entry: id, team, number, name, co-driver, colour, car, paddock and tags, so `maz` finds a Mazda tag and a model like Maze. Matches are listed below it (the first 20) with the tags that matched, and fill **Match**. **Apply Entry to Selected** adds the shown entry's tags to the selected images as tags you applied by hand (no model runs, and a later **Identify Selection** keeps them unless **Replace Manual Tags** is ticked). Writes darktable tags only.
- **Add by Tags or Last Run**: **Add Tagged Images**, **Add from Last Run.** Each finds the entry from the image's tags or the last run; the **Entry** list is not used.
- **Audit**: **Audit: Suggest Re-Crops**, **Audit: Quarantine Poor Refs** (both off by default), **Audit References.** See **Audit References** under [Building references](usage.md#building-references).

See [Building references](usage.md#building-references) for each action. The three add actions also fill the entry's colour in `entries.json` when the **Colour** family is on, and a colour tag you applied replaces the stored one.

Everything in pages 2 to 6 except **Replace Manual Tags** is saved with the collection by **update preset**. **Replace Manual Tags** is saved in darktable's preferences instead, so it carries across collections and restarts.

### 7 Tools

Hand fixes and undo. The page has four groups: **Derive** (lookups only; adds tags), **Copy** (writes tags as your own), **Lock** (writes tags as your own) and **Undo**. None runs a model. Identify Colour is on the Run page.

- **Derive from Number.** For each image whose number tag or paddock tag (Paddock family) you applied names exactly one entry, adds that entry's tags. Two cars with one number are told apart by a paddock tag, and a car with no number by its paddock tag alone (marker `From paddock`). An image with no colour tag also gets the entry's colour tag when the entry has a colour (saved by Identify Colour) and the Colour family is on. No models run; plugin-written number tags don't count. Writes darktable tags and the tag ledger only.
- **Derive from Colour.** For each image with one colour tag and no number tag, adds the tags of the one entry with that colour (your team tags narrow it). Skipped when several entries share the colour. Writes darktable tags and the tag ledger only.
- Both Derive buttons only add tags, log why each skipped image was skipped, and add **Check colour** when your number tag's entry and the colour tag disagree. Each tag source is marked `Assisted Tagging|Derived|From number`, `From driver`, `From colour` or `From identification` (option **Derived From** on page 4 Tags Written). A later Identify run replaces Derive's markers with its own.
- **Copy Tags to Group**. For each darktable group holding selected images, the selected images' entry tags and family tags (number, colour, team, driver…) replace those on every other image in the group, so the whole group matches. When the copy names an entry, the checks it settles go: *Check match* from every image, and *Unidentified*, the collection's unidentified tags and *Number seen* from an image that had no entry (on an identified image *Number seen* can be a second car, so it stays). Other diagnostics, **Tag Each Run** stamps and your other tags stay. Tags never cross from one group to another. The copies count as tags you applied by hand (they leave the ledger), so a later **Identify Selection** keeps them unless **Replace Manual Tags** is ticked. When two selected images in one group carry different tags, a box under the button asks first (also when the two entries of a double-driven car sit on different images, since number and driver may really be swapped; images that each hold both copy straight away): **Merge and Copy** gives every image in that group all of their tags; **Cancel** writes nothing. Writes darktable tags and the tag ledger only.
- **Copy Tags from Group**. The reverse of **Copy Tags to Group**: each selected image takes the entry and family tags of the other, unselected images in its darktable group, replacing its own of those. A group whose other images carry none is skipped with a message. The settled checks go and the copies count as hand tags, as for **Copy Tags to Group**. When the group's other images hold different tags of one family, the same box asks first. Writes darktable tags and the tag ledger only.
- **Copy Tags to Selection**. Merges the selected images' entry tags and family tags across all of them, so each fills in the tags it lacks: one image with the number and another with the colour both end up with both. Images outside the selection, group mates too, are untouched. The settled checks go and the copies count as hand tags, as for **Copy Tags to Group**. When two selected images carry different tags of one family, the same box asks first; **Merge and Copy** gives every selected image all of them. Writes darktable tags and the tag ledger only.
- **Lock In Tags**. For images whose tags you are certain of. Every tag on the selected images becomes yours (it leaves the ledger) and the images get `Assisted Tagging|Locked`, which you can filter on in darktable. After that nothing changes a locked image's tags: **Identify** skips it even with **Replace Manual Tags** ticked, Copy Tags leaves it alone as a target (it can still be the source), and Derive and Identify Colour skip it. Its entry still counts in Identify as a tag you applied, so it fills the unread frames of its burst. To make it a reference as well, run **Add Tagged Images** on it. Writes darktable tags and the tag ledger only.
- **Unlock Tags**. Takes `Assisted Tagging|Locked` off the selected images. Their tags stay yours.
- **Find New Entries** → **Add Ticked to entries.json.** Adds the cars and fields the images show but `entries.json` lacks:
  1. Select images and click **Find New Entries**. It lists each number read (`Number seen`) or tagged by hand under the number root that no entry has, and each team, driver or co-driver you tagged by hand on an image whose number names an entry with that field empty, most images first. An entry imported before co-drivers had their own field, whose `name` is still `Smith / Jones` with no `co_driver`, gets a **split** row: `12: split "Smith / Jones" → driver Smith, co-driver Jones`. A name with more than one ` / ` or an empty half gets none.
  2. Tick the rows to add. Nothing unticked is added, and one team, driver or co-driver per entry may be ticked; a split can't be ticked with a driver or co-driver for the same entry.
  3. Click **Add Ticked to entries.json**. New numbers become `{"id": "<n>", "number": "<n>"}`, teams, drivers and co-drivers fill their entry, and a split sets `name` to the driver and `co_driver` to the co-driver; the previous file is saved as `entries.json.bak` and the lists reload. If the file changed since the list was made (a number already added, a field already set), nothing is written and the reason is shown.
  4. Images that read an added number get its number tag in place of `Number seen|<n>`, as the plugin's own tag; hand-tagged images keep their tags. After a split, the next Identify writes the driver and co-driver tags; the old `Driver|Smith / Jones` tag on images tagged before stays until you delete it. Same thing from a shell: `python python/entries_file.py add <entries.json> <additions.csv>`, rows `number,<n>`, `split,<entry id>` and `field,<entry id>,<team|name|co_driver>,<value>`.
- **Clear Tagging Marks.** Removes every tag the ledger says the plugin attached to the selected images (entries, colours, diagnostics, unidentified), from any collection, and forgets those images in the ledger, so a later **Identify Selection** treats them as fresh. The ledger alone decides: tags you applied by hand stay, even under the plugin's roots, and so do **Tag Each Run** stamps, which are not ledgered. Images with no ledger row are left alone.

### To Check

A box headed **To Check**, above the progress line, lists what a run leaves for you to look at, so a toast that went by unseen isn't lost. It shows only when it has items. Each item reads `<action>: <what happened>` in full, wrapped over as many lines as it needs. Where the run knows which images and why, a read-only list under it gives one line per image: `<file>: <reason>`. The buttons sit below. The newest run's items sit on top. Older runs' items move below an *Earlier runs (before HH:MM): may not hold any more* line, since a later run can have settled them; they stay until you remove them, so a Fix still works.

- errors from any action;
- **Identify**: images tagged by each check tag (Check colour and the others that are on), images that couldn't be read or updated; possible new entries ("Possible new entries: 115 (3 images). Find New Entries (Tools page) adds them."): numbers no entry has, read on 3+ images of a burst, one line per image;
- **Verify** (verify only) checks solo shots of fully tagged images and changes nothing. One item per kind of problem:
  - images that read a different entry from the one their tags name. **Fix** runs Identify on just those images with replace manual on;
  - images that read a different colour from their entry's colour in entries.json. The tag or the entry can be wrong, so **Fix** adds the Check colour tag and leaves the entry tag alone;
  - images whose Colour tag differs from the colour read. **Fix** replaces the Colour tag with the colour read;
  - an entry whose colour most of its images overturn ("Entry 112 is Pink in entries.json, but 5 of its 6 images read Blue"). **Fix** sets the entry's colour in entries.json to the colour read. **Identify** lists this item too;
- **Derive from Number**, **Derive from Colour**: images marked Check colour, skipped, or not tagged;
- **Identify Colour**: images that read a different colour from their entry's, images that couldn't be read, and images that couldn't be tagged.

- **Select** beside a line selects its images in the lighttable. Images removed from the library since are skipped, and a toast counts them. Lines about images darktable couldn't read or update have no **Select**: those images may be gone.
- **Fix** beside a line makes the change that line describes, to its images only, and removes the line. Lines without a fix have no **Fix**.
- The next run of the same action replaces that action's lines; other actions' lines stay. **Clear List**, under the items, empties the box.
- Six lines show; more add `and N more (see the log)`. The list is saved to `assisted_tagging.checks.txt` in darktable's config folder, so it survives a restart.

## Preferences

All under **preferences → lua options**. Everything else is a collection setting, see [Presets](#presets).

| Preference | Default | What it does |
|---|---|---|
| plugins folder (`assisted_plugins/plugins_root`) | empty (auto-detect) | The folder holding the assisted-* repos; this plugin uses `<plugins folder>/darktable-assisted-tagging`, where `python/`, `models/`, `examples/` and `.venv` are found. The old `assisted_tagging/plugin_folder` (this repo's folder) is still read and logged as deprecated |
| Assisted Tagging: collections folder | empty (`assisted_tagging/collections` in the config directory) | Where collections live |

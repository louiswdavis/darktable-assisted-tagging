# Example: a season series

One collection for a whole season of a series where teammates run near-identical liveries. The drivers and numbers are illustrative; replace them with the season's entry list.

What it shows:

- **Teammates share a team tag.** Each driver's entry carries the team tag plus their own driver tag, and both entries set `team`. When two teammates' cars are too close to call, `team_only: "shared tags"` still adds the team tag.
- **A one-off livery** (`HAM-special`) is its own entry with the same tags as `HAM` and **no number**. A readable 44 still lands on `HAM`; the special livery is matched only against its own references. Don't give it the number too: two entries with the same number means that number identifies neither.
- **Cars without a number** (`SAFETY`, `MEDICAL`) are identified by livery only, so they need references before they're ever found.

## Using it

1. Copy this folder into the collections folder (`assisted_tagging/collections` in darktable's config directory) and rename it, e.g. `F1 2026`.
2. Edit `entries.json`, click **Reload**, then **Show tag plan** and read `tag-plan.txt` next to it.

## References

Numbers on these cars are small and often hidden (the halo, rear views, motion blur), so references do most of the work here.

- **Per driver, 3–5 shots from different angles**: front three-quarter, side, rear. The rear view matters most, since that's where the number is rarely readable.
- **Teammates need more than the others.** The livery is the same on both cars, so the plugin tells them apart by small details (camera pod colour, helmet). Add references from the angles where those show, and expect some `Team only` results anyway.
- **Number-less entries need references from the start.** Until `SAFETY`, `MEDICAL` and `HAM-special` have some, the tag plan lists them as "never identified".

How to add them:

1. Shoot or pick a clean frame of each car: one car in shot, not heavily cropped by the frame edge.
2. In the panel's **references** section, pick the entry in the **entry** list, select the frames, and click **Add as reference**. The largest vehicle in each frame is cropped and saved under `refs/<entry id>/`.
3. Already tagged a race weekend by hand? Select those frames and click **Add tagged images as references** instead. Each frame carrying all of one entry's tags is added to that entry; frames with only a team tag are skipped.

After a run, filter on `Assisted Tagging|Motorsport|Identified|By livery` and `Assisted Tagging|Motorsport|Team only`. A frame it got wrong, fixed by hand, is usually the best next reference.

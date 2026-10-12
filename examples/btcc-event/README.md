# Example: a single event

One collection for one race weekend: a big grid of similar-shaped cars with distinct liveries and large, readable numbers. The teams and drivers are placeholders.

What it shows:

- **`team_only: "none"`**: when two teammates are too close to call, no collection tags are added, only the `Team only` diagnostic. Use it when a team tag alone isn't worth having.
- **`unidentified: ["Shoot|Check me"]`**: every frame where no car was identified gets a tag of your own, so the frames to check are one filter away.
- **`diagnostics: { "burst": "" }`**: drops the `By burst` diagnostic tag; the other four keep their defaults.
- **An independent entry** (`car-116`) with no `team`, and a 3-digit number.
- **`PACE`**, the pace car, has no number, so it's identified by livery only.

## Using it

1. Copy this folder into the collections folder (`assisted_tagging/collections` in darktable's config directory) and rename it for the event, e.g. `BTCC 2026 Brands Hatch`.
2. Fill in the entry list, click **Reload**, then **Show tag plan** and read `tag-plan.txt` next to it.

## References

With big door and windscreen numbers, most frames are identified by number, so references here are a safety net for head-on and rear shots, and for cars in a pack.

- **2–3 per car is usually enough**: the angle where the number is hardest to read (head-on, or the rear) plus one side view.
- **Shoot them in the first session.** Practice or qualifying gives clean, single-car frames; add them before identifying the race.
- **`PACE` needs references** or it's never identified.

How to add them:

1. Pick a clean frame of each car: one car in shot, not cut off by the frame edge.
2. In the panel's **references** section, pick the entry in the **entry** list, select the frames, and click **Add as reference**. The largest vehicle in each frame is cropped and saved under `refs/<entry id>/`.
3. Or tag a handful of practice frames by hand, select them, and click **Add tagged images as references**. Each frame carrying all of one entry's tags is added to that entry.

After a run, filter on `Shoot|Check me` for what it missed. A frame it got wrong, fixed by hand, is usually the best next reference. To drop a bad reference, delete its JPG from `refs/<entry id>/`; the next run notices.

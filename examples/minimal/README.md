# Example: minimal starter

The smallest working collection: a bare list of entries, no `rules` block, so every rule takes its default. Good for a club race where you only care which car is in the frame.

Each entry is just an `id`, a `number` and its `tags`, written in full here. The other examples build tags from `rules.tag_prefix`, `team` and `name` instead. Add a `team` to entries that share one, and a `rules` block when a default doesn't suit you (see the other examples).

## Using it

1. Copy this folder into the collections folder (`assisted_tagging/collections` in darktable's config directory) and rename it, e.g. `Club Race Snetterton`.
2. Replace the three entries with the grid, click **Reload**, then **Show tag plan**.

## References

Optional here. Every entry has a number, so it works with none, but only on frames where the number is readable. Once the first run's `Assisted Tagging|Identification|Unidentified` frames show which cars it struggles with, add 2–3 references for those: pick the entry in the **entry** list, select the frames, and click **Add as reference**.

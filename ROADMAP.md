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
- **People** — no number; livery embedding alone, maybe swapped for a face-embedding model
- **Landmarks** — no number, no "team" grouping concept at all
- **Flowers / birds / animals** — species/genus grouping could replace "team"
  (e.g. a "same species, can't tell which individual" tie-break)

Needs a schema redesign (`Entry` fields become domain-specific, or a pluggable
"identifying attribute" concept) rather than reusing `number`/`team` as-is.

## Smaller known gaps

- "Edit entries.json" button prints a mangled path instead of opening/editing the
  file when `open_in_app` fails on Windows — consider an in-app darktable dialog
  with a text-entry widget instead of relying on the OS file association.

# Rally

Cars of no known livery, passing in loops, identified by their race number alone. Each entry is just a number (`{"id": "12", "number": "12"}`); the tag it writes is `Rally|2026|12`. With no references, a car whose number can't be read stays *Unidentified*, unless its neighbours help (below).

## Using it

1. Copy this folder's `entries.json` into a new collection folder, or build one from your own list: put one number per line in a CSV, then run `python python/import_numbers.py numbers.csv entries.json --tag-prefix "Rally|2026" --order-weight 0.5`. It refuses to overwrite an existing file and stops on a duplicate or non-number.
2. Click **Reload**, then **Identify selection** on the batch.

## Order weight

`rules.order_weight` says how much the cars pass in number order:

| Weight | Meaning |
|---|---|
| `0` (default) | random order: neighbours are ignored, identical to a collection with no weight |
| `0.5` | loosely in order: neighbours can settle a doubtful read |
| `1` | strictly in order |

Cars may skip numbers (withdrawn, not yet arrived) and may pass out of order, so only the position in the sorted list counts: a gap in the list costs nothing. The list is a **loop**: after the highest number the lowest comes next, so a stage that laps is fine.

## What the neighbour step does

It looks at the three groups shot before and after a doubtful read, within 2 minutes (a longer pause is a stage break, and neighbours across it are ignored).

- A car whose number wasn't read, but is one confusable digit away from an entry (5/6, 1/7, 0/6, 0/8, 3/8, 3/5, 1/4) or has a digit added or dropped, takes that entry when its neighbours sit close to it in the list. Tagged `Assisted Tagging|Identification|By neighbour`.
- A number read at under 0.90 confidence with no neighbour near it keeps its tag and gets `Assisted Tagging|Identification|Check order`. Filter on it to spot-check; delete the tag once you've checked (or fixed) the photo.

**Tolerance** is how many list positions away still counts as near. Set it under **preferences → lua options → Assisted Tagging: neighbour tolerance** (default 5; a whole number).

"""Build a numbers-only entries.json from a list of car numbers.

  python python/import_numbers.py NUMBERS_CSV OUT_ENTRIES_JSON --tag-prefix PREFIX

NUMBERS_CSV holds one number per line (first column; a first line that isn't digits is a header and
is skipped). Each entry gets the tag `PREFIX|<number>` (see identify.py's numbers-only entries).
Refuses to overwrite OUT_ENTRIES_JSON. Exit 2 with a message on bad input.
Settings such as order_weight live in the collection's settings.json, not in entries.json."""

import argparse
import csv
import json
import os
import sys


def fail(message: str):
    print(f"import_numbers: {message}", file=sys.stderr)
    sys.exit(2)


def read_numbers(path: str) -> list:
    numbers = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for i, row in enumerate(csv.reader(f)):
            cell = row[0].strip() if row else ""
            if not cell:
                continue
            if not cell.isdigit():
                if i == 0:
                    continue
                fail(f'line {i + 1}: "{cell}" is not a number')
            if cell in numbers:
                fail(f"number {cell} is listed twice")
            numbers.append(cell)
    if not numbers:
        fail(f"{path} has no numbers")
    return numbers


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a numbers-only entries.json from a list of car numbers")
    parser.add_argument("numbers_csv")
    parser.add_argument("out_entries_json")
    parser.add_argument("--tag-prefix", required=True, help="Tag prefix; each car is tagged PREFIX|<number>")
    args = parser.parse_args(argv)
    if os.path.exists(args.out_entries_json):
        fail(f"{args.out_entries_json} already exists; not overwriting")
    numbers = read_numbers(args.numbers_csv)
    data = {"rules": {"tag_prefix": args.tag_prefix}, "entries": [{"id": n, "number": n} for n in numbers]}
    with open(args.out_entries_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"wrote {len(numbers)} entries to {args.out_entries_json}")


if __name__ == "__main__":
    main()

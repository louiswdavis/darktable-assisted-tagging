"""Add a start list to a collection's entries.json.

  python python/import_start_list.py COLLECTION_DIR --csv START_LIST.csv [--columns MAP]
  python python/import_start_list.py COLLECTION_DIR --text PASTED.txt
  python python/import_start_list.py COLLECTION_DIR --csv START_LIST.csv --header

A CSV has a header row; MAP says which header holds which role, as `role=header` pairs joined
by ";" (roles: number, driver, co-driver, team, class, make, model, shares-car, paddock); `role=` says the
CSV has none. A role left out of MAP is found by its usual names (ALIASES); only `number` is
required. --header prints the headers and that mapping for the panel's column pickers. Pasted text (an entry list copied from a PDF)
has one entry per line, number first, then "driver / co-driver"; lines without a leading number
are skipped and counted. Each entry becomes {"id": number, "number": number, "name": driver,
"co_driver": co-driver, "team": team, "extra": class, "make": make, "model": model, "paddock": paddock}, with the empty fields
left out; a model needs a make. The Class and Vehicle tag families build the tags from them. A `shares-car` column names the other entry
driving the same car; both rows must name each other, and the higher number gets `"car": "<lower id>"`.
A row whose `class` starts with "Demo" (a demonstration run) gets its own `paddock` value as id
(`A11`, spaces dropped: `Office1`) and keeps its number, so demo 14 and race car 14 are separate
entries; a demo row with no paddock is bad input. Pasted text has no paddock, so it can't hold demo
rows. An entry already in entries.json under the bare number, or under the earlier `D<number>` id,
with the same driver is renamed to its paddock id, along with its refs folder and refs/sources.json records. Other ids already in entries.json, and
race numbers another race entry holds, are skipped and listed, never overwritten. The previous file is
kept as entries.json.bak. A file not in the one-entry-per-line layout is reflowed into it. Exit 2
with a message on bad input."""

import argparse
import csv
import io
import json
import os
import re
import shutil
import sys

from common import atomic_write
from entries_file import dump

ROLES = ("number", "driver", "co-driver", "team", "class", "make", "model", "shares-car", "paddock")
ALIASES = {
    "number": ("number", "no", "no.", "#", "nr", "num", "car", "car no", "car no.", "car number", "start no", "start number"),
    "driver": ("driver", "name", "pilot", "driver name", "competitor"),
    "co-driver": ("co-driver", "codriver", "co driver", "co-pilot", "navigator"),
    "team": ("team", "entrant", "entrant / team", "entrant/team"),
    "class": ("class", "category", "cat", "cat."),
    "make": ("make", "manufacturer"),
    "model": ("model",),
    "shares-car": ("shares car with", "shares car", "shared car"),
    "paddock": ("paddock", "paddock id", "paddock no"),
}
PADDOCK_ID = re.compile(r"[A-Za-z][A-Za-z0-9]*")
_LINE = re.compile(r"^\s*#?(\d{1,3})(?!\d)[\s.:)\-–]*(.*?)\s*$")
_BAD = re.compile(r'[,;"]')
_BAD_TAG = re.compile(r'[,;"|]')


class BadInput(Exception):
    pass


def is_demo_id(entry_id) -> bool:
    """Race entries are keyed by their number; a demo is keyed by its paddock id, never all digits."""
    return not str(entry_id).isdigit()


def parse_columns(spec: str) -> dict:
    """`role=header;role=header` → {role: header}; `role=` (no header) means the CSV has no such
    column. An unknown role or a missing "=" is BadInput."""
    out = {}
    for part in filter(None, (p.strip() for p in (spec or "").split(";"))):
        role, eq, header = part.partition("=")
        role = role.strip().lower()
        if not eq or role not in ROLES:
            raise BadInput(f'--columns: "{part}" should be role=header, with the role one of {", ".join(ROLES)}')
        out[role] = header.strip()
    return out


def read_header(text: str) -> tuple:
    """(header row, reader over the data rows); the delimiter is the one of , ; and tab the header
    row uses most (csv.Sniffer differs between Python builds)."""
    header_line = next((line for line in text.splitlines() if line.strip()), "")
    reader = csv.reader(io.StringIO(text), delimiter=max(",;\t", key=header_line.count))
    header = next(reader, None)
    if not header:
        raise BadInput("the CSV is empty")
    return header, reader


def map_header(header: list, columns: dict, need_number: bool = True) -> dict:
    """{role: column index} from the header row, by --columns first and the aliases second. A role
    given as "" in `columns` gets no column."""
    lowered = [h.strip().lower() for h in header]
    found = {}
    for role in ROLES:
        if role in columns:
            want = columns[role]
            if not want:
                continue
            if want.lower() not in lowered:
                raise BadInput(f'no "{want}" column for {role}; the header is {", ".join(h.strip() for h in header)}')
            found[role] = lowered.index(want.lower())
        else:
            hit = next((i for i, h in enumerate(lowered) if h in ALIASES[role]), None)
            if hit is not None and hit not in found.values():
                found[role] = hit
    if need_number and "number" not in found:
        raise BadInput(f'no number column found in the header ({", ".join(h.strip() for h in header)}); '
                       'name it with --columns "number=<header>"')
    return found


def rows_from_csv(text: str, columns: dict) -> list:
    """One {role: value} per data row of a CSV with a header. With no co-driver column, a driver
    cell "Smith / Jones" gives driver Smith, co-driver Jones (rally lists often share one cell)."""
    header, reader = read_header(text)
    at = map_header(header, columns)
    rows = []
    for row in reader:
        if not any(c.strip() for c in row):
            continue
        out = {role: (row[i].strip() if i < len(row) else "") for role, i in at.items()}
        if "co-driver" not in at and " / " in out.get("driver", ""):
            driver, _, co = out["driver"].partition(" / ")
            out["driver"], out["co-driver"] = driver.strip(), co.strip()
        rows.append(out)
    return rows


def header_report(text: str) -> str:
    """For the panel's column pickers: one `header<TAB><name>` line per CSV column, then one
    `role<TAB><role><TAB><header or "">` line per role, as the aliases map it."""
    header, _ = read_header(text)
    at = map_header(header, {}, need_number=False)
    lines = [f"header\t{h.strip()}" for h in header]
    lines += [f"role\t{role}\t{header[at[role]].strip() if role in at else ''}" for role in ROLES]
    return "\n".join(lines)


def rows_from_text(text: str) -> tuple:
    """Pasted lines → (rows, skipped line count). "12 Smith / Jones" gives driver Smith, co-driver Jones.
    A line starting "Demo" (a PDF's Demonstrations heading) makes the numbered lines after it demo rows."""
    rows, skipped, demo = [], 0, False
    for line in text.splitlines():
        if not line.strip():
            continue
        m = _LINE.match(line)
        if not m:
            if line.strip().lower().startswith("demo"):
                demo = True
            skipped += 1
            continue
        driver, _, co = m.group(2).partition(" / ")
        row = {"number": m.group(1), "driver": driver.strip(), "co-driver": co.strip()}
        if demo:
            row["class"] = "Demonstration"
        rows.append(row)
    return rows, skipped


def entries_from(rows: list) -> tuple:
    """Rows → (entries, cleaned names): numbers are checked, drivers, co-drivers and teams lose , ; and ". Class
    (as `extra`), make and model lose , ; " and |."""
    entries, cleaned, seen = [], [], set()
    for n, row in enumerate(rows, 1):
        number = row.get("number", "").strip().lstrip("#")
        if not re.fullmatch(r"\d{1,3}", number):
            raise BadInput(f'row {n}: "{row.get("number", "")}" is not a 1–3 digit number')
        number = str(int(number))
        demo = row.get("class", "").strip().lower().startswith("demo")
        entry_id = demo_id(row, n) if demo else number
        if entry_id in seen:
            raise BadInput(f"{'demo paddock' if demo else 'number'} {entry_id} is listed twice")
        seen.add(entry_id)
        name, co_driver, team = (row.get(k, "").strip() for k in ("driver", "co-driver", "team"))
        if _BAD.search(name + co_driver + team):
            cleaned.append(number)
            name, co_driver, team = (_BAD.sub("", v).strip() for v in (name, co_driver, team))
        entry = {"id": entry_id, "number": number}
        if name:
            entry["name"] = name
        if co_driver:
            entry["co_driver"] = co_driver
        if team:
            entry["team"] = team
        klass, make, model = (_BAD_TAG.sub("", row.get(k, "")).strip() for k in ("class", "make", "model"))
        if model and not make:
            raise BadInput(f"row {n}: model {model} has no make")
        paddock = _BAD_TAG.sub("", row.get("paddock", "")).strip()
        for key, value in (("extra", klass), ("make", make), ("model", model), ("paddock", paddock)):
            if value:
                entry[key] = value
        entries.append(entry)
    if not entries:
        raise BadInput("no entries found")
    _pair_cars([(e, r) for e, r in zip(entries, rows) if e["id"] == e["number"]])
    return entries, cleaned


def demo_id(row: dict, n: int) -> str:
    """A demo row's paddock id with spaces dropped ("Office 1" → "Office1"); BadInput when the row has
    none, or one that isn't a letter then letters and digits (an all-digit id would clash with a race number)."""
    paddock = re.sub(r"\s+", "", row.get("paddock", ""))
    if not PADDOCK_ID.fullmatch(paddock):
        raise BadInput(f'row {n}: demo {row.get("number", "")} needs a paddock id (a letter, then letters or digits), got "{row.get("paddock", "")}"')
    return paddock


def _pair_cars(pairs: list):
    """Sets `car` on the higher number of each pair the shares-car column names, over the race
    entries' (entry, row) pairs. Both rows must name each other; a partner that isn't a listed 1–3
    digit number is BadInput."""
    entries = [e for e, _ in pairs]
    partner = {}
    for entry, row in pairs:
        other = row.get("shares-car", "").strip().lstrip("#")
        if not other:
            continue
        if not re.fullmatch(r"\d{1,3}", other):
            raise BadInput(f'number {entry["number"]}: shares car with "{other}", which is not a 1–3 digit number')
        if str(int(other)) == entry["number"]:
            raise BadInput(f"number {other} shares a car with itself")
        partner[entry["number"]] = str(int(other))
    for number, other in partner.items():
        if other not in partner:
            listed = any(e["number"] == other for e in entries)
            raise BadInput(f"number {number} shares a car with {other}, but {other} "
                           + ("doesn't name it back" if listed else "is not in the list"))
        if partner[other] != number:
            raise BadInput(f"number {number} shares a car with {other}, but {other} names {partner[other]}")
    for entry in entries:
        other = partner.get(entry["number"])
        if other and int(other) < int(entry["number"]):
            entry["car"] = other


def merge(collection_dir: str, entries: list) -> dict:
    """Renames existing entries to their demo id (_rename_demos), then appends the entries whose id
    is new, and whose race number no existing race entry holds. Returns {"added", "skipped",
    "renamed", "path"}. A file in dump's layout keeps it; any other layout is reflowed into the
    canonical one."""
    path = os.path.join(collection_dir, "entries.json")
    if not os.path.exists(path):
        data, text, inline = {"entries": []}, None, False
    else:
        with open(path, encoding="utf-8-sig", newline="") as f:
            text = f.read().replace("\r\n", "\n")
        data = json.loads(text)
        if not isinstance(data, dict):
            raise BadInput(f"{path} is a bare list; make it {{\"entries\": [...]}} first")
        inline = next((i for i in (False, True) if dump(json.loads(text), i).rstrip() == text.rstrip()), None)
    existing = data.setdefault("entries", [])
    renamed = _rename_demos(existing, entries)
    filled = _fill_paddocks(existing, entries)
    ids = {e.get("id") for e in existing if isinstance(e, dict)}
    race_numbers = {str(e.get("number", "")) for e in existing
                    if isinstance(e, dict) and not is_demo_id(e.get("id", ""))}
    taken = [e for e in entries if e["id"] in ids or (e["id"] == e["number"] and e["number"] in race_numbers)]
    new = [e for e in entries if e not in taken]
    skipped = [e["id"] for e in taken if e["id"] not in {n for _, n in renamed}]
    if not new and not renamed and not filled:
        return {"added": 0, "skipped": skipped, "renamed": [], "filled": 0, "path": path}
    existing.extend(new)
    with atomic_write(path) as f:
        f.write(dump(data, bool(inline)))
        if text is not None:
            shutil.copy2(path, path + ".bak")  # the original, before the replace on exit
    for old, new_id in renamed:
        _rename_refs(collection_dir, old, new_id)
    return {"added": len(new), "skipped": skipped, "renamed": renamed, "filled": filled, "path": path}


def _rename_demos(existing: list, entries: list) -> list:
    """[(old id, demo id)]: each existing entry whose id is the bare number, or the earlier D<number>,
    of an imported demo entry, with that number and the same driver (when both name one), takes the
    paddock id; `car` fields naming the old id follow. An existing paddock id is left alone. An old entry's name may
    be the older importers' "driver / co-driver", so only its driver part is compared."""
    by_id = {e.get("id"): e for e in existing if isinstance(e, dict)}
    renamed = []
    for entry in entries:
        if not is_demo_id(entry["id"]) or entry["id"] in by_id:
            continue
        old_id = next((i for i in (f"D{entry['number']}", entry["number"]) if i in by_id), None)
        if old_id is None:
            continue
        old = by_id[old_id]
        if str(old.get("number", "")) != entry["number"]:
            continue
        if old.get("name") and entry.get("name") and old["name"].split(" / ")[0] != entry["name"]:
            continue
        old["id"] = entry["id"]
        by_id[entry["id"]] = by_id.pop(old_id)
        renamed.append((old_id, entry["id"]))
    for old_id, new_id in renamed:
        for e in by_id.values():
            if e.get("car") == old_id:
                e["car"] = new_id
    return renamed


def _fill_paddocks(existing: list, entries: list) -> int:
    """Sets `paddock` on each existing entry the import lists with one and that has none; a paddock
    already on the entry is kept. Returns how many were set."""
    by_id = {e.get("id"): e for e in existing if isinstance(e, dict)}
    filled = 0
    for entry in entries:
        old = by_id.get(entry["id"])
        if old is not None and entry.get("paddock") and not old.get("paddock"):
            old["paddock"] = entry["paddock"]
            filled += 1
    return filled


def _rename_refs(collection_dir: str, old: str, new: str):
    """Moves refs/<old>/ to refs/<new>/ and rekeys its refs/sources.json records. A crop already at
    the new name is kept and the old one left in place."""
    refs = os.path.join(collection_dir, "refs")
    src, dst = os.path.join(refs, old), os.path.join(refs, new)
    if os.path.isdir(src):
        os.makedirs(dst, exist_ok=True)
        for name in os.listdir(src):
            if not os.path.exists(os.path.join(dst, name)):
                os.replace(os.path.join(src, name), os.path.join(dst, name))
        if not os.listdir(src):
            os.rmdir(src)
    sources = os.path.join(refs, "sources.json")
    if not os.path.isfile(sources):
        return
    with open(sources, encoding="utf-8") as f:
        records = json.load(f)
    before, after = f"refs/{old}/", f"refs/{new}/"
    moved = {(after + rel[len(before):] if rel.startswith(before) and
              os.path.exists(os.path.join(dst, rel[len(before):])) else rel): rec for rel, rec in records.items()}
    if moved != records:
        with atomic_write(sources) as f:
            json.dump(moved, f, indent=1)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Add a start list to a collection's entries.json")
    parser.add_argument("collection_dir")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", help="a start list with a header row")
    src.add_argument("--text", help="pasted lines, number first")
    parser.add_argument("--columns", default="", help='role=header pairs joined by ";" (roles: number, driver, co-driver, team, class, make, model, shares-car, paddock); role= for none')
    parser.add_argument("--header", action="store_true", help="with --csv: print the headers and how the usual names map them, write nothing")
    args = parser.parse_args(argv)
    if args.header and not args.csv:
        parser.error("--header needs --csv")
    try:
        with open(args.csv or args.text, encoding="utf-8-sig", newline="") as f:
            text = f.read()
        if args.header:
            print(header_report(text))
            return
        skipped_lines = 0
        if args.csv:
            rows = rows_from_csv(text, parse_columns(args.columns))
        else:
            rows, skipped_lines = rows_from_text(text)
        entries, cleaned = entries_from(rows)
        result = merge(args.collection_dir, entries)
    except (BadInput, OSError, json.JSONDecodeError) as e:
        print(f"import_start_list: {e}", file=sys.stderr)
        sys.exit(2)
    notes = []
    if result["renamed"]:
        notes.append(f"renamed {len(result['renamed'])} to paddock ids: "
                     + ", ".join(f"{o}→{n}" for o, n in result["renamed"]))
    if result["filled"]:
        notes.append(f"paddock set on {result['filled']} existing entries")
    if result["skipped"]:
        notes.append(f"skipped {len(result['skipped'])} already listed: {', '.join(result['skipped'])}")
    if skipped_lines:
        notes.append(f"{skipped_lines} line(s) without a leading number ignored")
    if cleaned:
        notes.append(f', ; and " removed from the names of {", ".join(cleaned)}')
    print(f"added {result['added']} {'entry' if result['added'] == 1 else 'entries'} to {os.path.basename(result['path'])}" +("; " + "; ".join(notes) if notes else ""))


if __name__ == "__main__":
    main()

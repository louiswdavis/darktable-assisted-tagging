"""Add a start list to a collection's entries.json.

  python python/import_start_list.py COLLECTION_DIR --csv START_LIST.csv [--columns MAP] [--tag-prefix PREFIX]
  python python/import_start_list.py COLLECTION_DIR --text PASTED.txt [--tag-prefix PREFIX]

A CSV has a header row; MAP says which header holds which role, as `role=header` pairs joined
by ";" (roles: number, driver, co-driver, team, class). A role left out of MAP is found by its
usual names (ALIASES); only `number` is required. Pasted text (an entry list copied from a PDF)
has one entry per line, number first, then "driver / co-driver"; lines without a leading number
are skipped and counted. Each entry becomes {"id": number, "number": number, "name": "driver /
co-driver", "team": team, "tags": ["<prefix>|Class|<class>"]}, with the empty fields left out.
Numbers already in entries.json are skipped and listed, never overwritten. The previous file is
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

ROLES = ("number", "driver", "co-driver", "team", "class")
ALIASES = {
    "number": ("number", "no", "no.", "#", "nr", "num", "car", "car no", "car no.", "car number", "start no", "start number"),
    "driver": ("driver", "name", "pilot", "driver name", "competitor"),
    "co-driver": ("co-driver", "codriver", "co driver", "co-pilot", "navigator"),
    "team": ("team", "entrant", "entrant / team", "entrant/team"),
    "class": ("class", "category", "cat", "cat."),
}
_LINE = re.compile(r"^\s*#?(\d{1,3})(?!\d)[\s.:)\-–]*(.*?)\s*$")
_BAD = re.compile(r'[,;"]')


class BadInput(Exception):
    pass


def parse_columns(spec: str) -> dict:
    """`role=header;role=header` → {role: header}; an unknown role or a missing "=" is BadInput."""
    out = {}
    for part in filter(None, (p.strip() for p in (spec or "").split(";"))):
        role, eq, header = part.partition("=")
        role = role.strip().lower()
        if not eq or role not in ROLES or not header.strip():
            raise BadInput(f'--columns: "{part}" should be role=header, with the role one of {", ".join(ROLES)}')
        out[role] = header.strip()
    return out


def map_header(header: list, columns: dict) -> dict:
    """{role: column index} from the header row, by --columns first and the aliases second."""
    lowered = [h.strip().lower() for h in header]
    found = {}
    for role in ROLES:
        want = columns.get(role)
        if want:
            if want.lower() not in lowered:
                raise BadInput(f'no "{want}" column for {role}; the header is {", ".join(h.strip() for h in header)}')
            found[role] = lowered.index(want.lower())
        else:
            hit = next((i for i, h in enumerate(lowered) if h in ALIASES[role]), None)
            if hit is not None and hit not in found.values():
                found[role] = hit
    if "number" not in found:
        raise BadInput(f'no number column found in the header ({", ".join(h.strip() for h in header)}); '
                       'name it with --columns "number=<header>"')
    return found


def rows_from_csv(text: str, columns: dict) -> list:
    """One {role: value} per data row of a CSV with a header; the delimiter is the one of
    , ; and tab the header row uses most (csv.Sniffer differs between Python builds)."""
    header_line = next((line for line in text.splitlines() if line.strip()), "")
    reader = csv.reader(io.StringIO(text), delimiter=max(",;\t", key=header_line.count))
    header = next(reader, None)
    if not header:
        raise BadInput("the CSV is empty")
    at = map_header(header, columns)
    rows = []
    for row in reader:
        if not any(c.strip() for c in row):
            continue
        rows.append({role: (row[i].strip() if i < len(row) else "") for role, i in at.items()})
    return rows


def rows_from_text(text: str) -> tuple:
    """Pasted lines → (rows, skipped line count). "12 Smith / Jones" gives driver Smith, co-driver Jones."""
    rows, skipped = [], 0
    for line in text.splitlines():
        if not line.strip():
            continue
        m = _LINE.match(line)
        if not m:
            skipped += 1
            continue
        driver, _, co = m.group(2).partition(" / ")
        rows.append({"number": m.group(1), "driver": driver.strip(), "co-driver": co.strip()})
    return rows, skipped


def entries_from(rows: list) -> tuple:
    """Rows → (entries, cleaned names): numbers are checked, names and teams lose , ; and ". A class
    stays under "class" until merge knows the tag prefix to build its tag with."""
    entries, cleaned, seen = [], [], set()
    for n, row in enumerate(rows, 1):
        number = row.get("number", "").strip().lstrip("#")
        if not re.fullmatch(r"\d{1,3}", number):
            raise BadInput(f'row {n}: "{row.get("number", "")}" is not a 1–3 digit number')
        number = str(int(number))
        if number in seen:
            raise BadInput(f"number {number} is listed twice")
        seen.add(number)
        name = " / ".join(filter(None, (row.get("driver", ""), row.get("co-driver", ""))))
        team = row.get("team", "")
        if _BAD.search(name + team):
            cleaned.append(number)
            name, team = _BAD.sub("", name).strip(), _BAD.sub("", team).strip()
        entry = {"id": number, "number": number}
        if name:
            entry["name"] = name
        if team:
            entry["team"] = team
        if row.get("class"):
            entry["class"] = _BAD.sub("", row["class"]).strip()
        entries.append(entry)
    if not entries:
        raise BadInput("no entries found")
    return entries, cleaned


def merge(collection_dir: str, entries: list, tag_prefix: str) -> dict:
    """Appends the entries whose number (and id) is new. Returns {"added", "skipped", "path"}. A file
    in dump's layout keeps it; any other layout is reflowed into the canonical one."""
    path = os.path.join(collection_dir, "entries.json")
    if not os.path.exists(path):
        if not tag_prefix:
            raise BadInput(f"{path} doesn't exist yet; give --tag-prefix to create it")
        data, text, inline = {"rules": {"tag_prefix": tag_prefix}, "entries": []}, None, False
    else:
        with open(path, encoding="utf-8-sig", newline="") as f:
            text = f.read().replace("\r\n", "\n")
        data = json.loads(text)
        if not isinstance(data, dict):
            raise BadInput(f"{path} is a bare list with no rules.tag_prefix; make it {{\"rules\": ..., \"entries\": [...]}} first")
        rules = data.setdefault("rules", {})
        if not rules.get("tag_prefix"):
            if not tag_prefix:
                raise BadInput(f"{path} has no rules.tag_prefix, which the names need; give --tag-prefix")
            rules["tag_prefix"] = tag_prefix
        inline = next((i for i in (False, True) if dump(json.loads(text), i).rstrip() == text.rstrip()), None)
    existing = data.setdefault("entries", [])
    have = {str(e.get("number", "")) for e in existing if isinstance(e, dict)} | {e.get("id") for e in existing if isinstance(e, dict)}
    prefix = data["rules"]["tag_prefix"]
    new = [{**{k: v for k, v in e.items() if k != "class"}, **({"tags": [f"{prefix}|Class|{e['class']}"]} if e.get("class") else {})}
           for e in entries if e["number"] not in have and e["id"] not in have]
    skipped = [e["number"] for e in entries if e["number"] in have or e["id"] in have]
    if not new:
        return {"added": 0, "skipped": skipped, "path": path}
    existing.extend(new)
    with atomic_write(path) as f:
        f.write(dump(data, bool(inline)))
        if text is not None:
            shutil.copy2(path, path + ".bak")  # the original, before the replace on exit
    return {"added": len(new), "skipped": skipped, "path": path}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Add a start list to a collection's entries.json")
    parser.add_argument("collection_dir")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", help="a start list with a header row")
    src.add_argument("--text", help="pasted lines, number first")
    parser.add_argument("--columns", default="", help='role=header pairs joined by ";" (roles: number, driver, co-driver, team, class)')
    parser.add_argument("--tag-prefix", default="", help="rules.tag_prefix for a new entries.json, or one without a prefix")
    args = parser.parse_args(argv)
    try:
        with open(args.csv or args.text, encoding="utf-8-sig", newline="") as f:
            text = f.read()
        skipped_lines = 0
        if args.csv:
            rows = rows_from_csv(text, parse_columns(args.columns))
        else:
            rows, skipped_lines = rows_from_text(text)
        entries, cleaned = entries_from(rows)
        result = merge(args.collection_dir, entries, args.tag_prefix)
    except (BadInput, OSError, json.JSONDecodeError) as e:
        print(f"import_start_list: {e}", file=sys.stderr)
        sys.exit(2)
    notes = []
    if result["skipped"]:
        notes.append(f"skipped {len(result['skipped'])} already listed: {', '.join(result['skipped'])}")
    if skipped_lines:
        notes.append(f"{skipped_lines} line(s) without a leading number ignored")
    if cleaned:
        notes.append(f', ; and " removed from the names of {", ".join(cleaned)}')
    print(f"added {result['added']} entries to {result['path']}" + ("; " + "; ".join(notes) if notes else ""))


if __name__ == "__main__":
    main()

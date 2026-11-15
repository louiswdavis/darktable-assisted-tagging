"""entries.json round trip: fills an entry's `colour` (the reference actions) and adds confirmed
entries and fields (the panel's Find new entries) without changing anything else. A file already in
the canonical layout (`dump`) keeps its layout; any other layout is reflowed into the canonical one,
with the previous file kept as entries.json.bak. A UTF-8 BOM at the start is accepted and not
written back. `upgrade` moves old Motorsport|Class / Motorsport|Vehicle entry tags into the `extra`,
`make` and `model` fields (identify.load_collection runs it before every load).

From a shell: python entries_file.py add <entries.json> <additions.csv>, the CSV holding rows
`number,<n>` and `field,<entry id>,<team|name>,<value>`."""

import csv
import json
import re
import shutil
import sys

from common import atomic_write


def _entry(entry: dict) -> str:
    inner = json.dumps(entry, ensure_ascii=False)[1:-1]
    return "{ " + inner + " }" if inner else "{}"


def dump(data, inline_rules: bool = False) -> str:
    """The canonical layout, as the examples and assisted_tagging.lua's M.entries_json write it: one
    entry per line (`{ "id": ..., ... }`), indented 4 under an object's "entries" and 2 in a bare
    list; every other top-level value (the rules block) is 2-space indented JSON, or with
    `inline_rules` one line. Key order is kept."""
    if isinstance(data, list):
        return "[\n" + ",\n".join("  " + _entry(e) for e in data) + "\n]\n"
    lines = []
    for key, value in data.items():
        if key == "entries" and isinstance(value, list):
            text = "[\n" + ",\n".join("    " + _entry(e) for e in value) + "\n  ]" if value else "[]"
        elif inline_rules and isinstance(value, dict):
            text = _entry(value)
        else:
            text = json.dumps(value, indent=2, ensure_ascii=False).replace("\n", "\n  ")
        lines.append(f"  {json.dumps(key, ensure_ascii=False)}: {text}")
    return "{\n" + ",\n".join(lines) + "\n}\n"


def set_colours(path: str, colours: dict) -> tuple:
    """Gives each entry in `colours` ({entry id: colour}) that has no colour yet its colour, appended
    as its last key. Entries that already have a colour are never touched. Returns (written, reason):
    (True, "set"), or (False, "unchanged") when no entry needed one. A file in `dump`'s layout
    (trailing whitespace aside) keeps its layout, line endings and trailing whitespace; any other
    layout is reflowed into the canonical one. Writes a temp file, keeps the previous file as
    entries.json.bak, then replaces it."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        raw = f.read()
    eol = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    data = json.loads(text)
    entries = data.get("entries") if isinstance(data, dict) else data
    changed = False
    for e in entries if isinstance(entries, list) else []:
        colour = colours.get(e.get("id")) if isinstance(e, dict) else None
        if colour and not e.get("colour"):
            e.pop("colour", None)
            e["colour"] = colour
            changed = True
    if not changed:
        return False, "unchanged"
    _write(path, text, data, eol)
    return True, "set"


def _write(path: str, text: str, data, eol: str) -> None:
    """Replaces the file whose \\n-normalised content is `text` with `data`, in `text`'s layout when
    that is one of `dump`'s, keeping the previous file as <path>.bak."""
    original = json.loads(text)
    inline = next((i for i in (False, True) if dump(original, i).rstrip() == text.rstrip()), None)
    out = dump(data, False) if inline is None else dump(data, inline).rstrip() + text[len(text.rstrip()):]
    with atomic_write(path, newline="") as f:
        f.write(out.replace("\n", eol))
        shutil.copy2(path, path + ".bak")  # the original, before the replace on exit


OLD_CLASS = "Motorsport|Class|"
OLD_VEHICLE = "Motorsport|Vehicle|"


def _upgrade_entry(e: dict) -> bool:
    """Moves `e`'s old class/vehicle tags into fields, in place. True when `e` changed."""
    tags = e.get("tags")
    if not isinstance(tags, list):
        return False
    eid = e.get("id")
    found, kept = {}, []
    for tag in tags:
        kind = "class" if isinstance(tag, str) and tag.startswith(OLD_CLASS) else \
            "vehicle" if isinstance(tag, str) and tag.startswith(OLD_VEHICLE) else None
        if kind is None:
            kept.append(tag)
            continue
        if kind in found:
            raise ValueError(f'entry "{eid}": two {(OLD_CLASS if kind == "class" else OLD_VEHICLE)[:-1]} tags')
        found[kind] = tag
    if not found:
        return False
    new = {}
    if "class" in found:
        new["extra"] = found["class"][len(OLD_CLASS):]
    if "vehicle" in found:
        parts = found["vehicle"][len(OLD_VEHICLE):].split("|")
        if len(parts) > 2 or not all(parts):
            raise ValueError(f'entry "{eid}": tag "{found["vehicle"]}" is not {OLD_VEHICLE}<make>[|<model>]')
        new.update(zip(("make", "model"), parts))
    tag_of = {"extra": found.get("class"), "make": found.get("vehicle"), "model": found.get("vehicle")}
    for key, value in new.items():
        if e.get(key) not in (None, "", value):
            raise ValueError(f'entry "{eid}": {key} "{e[key]}" disagrees with tag "{tag_of[key]}"')
    new = {k: v for k, v in new.items() if e.get(k) != v}
    after = max((i for i, k in enumerate(e) if k in ("id", "number", "name", "team")), default=-1)
    out = {}
    for i, (k, v) in enumerate(list(e.items())):
        if k in new:
            continue
        if k == "tags":
            if kept:
                out[k] = kept
        else:
            out[k] = v
        if i == after:
            out.update(new)
    if after == -1:
        out.update(new)
    e.clear()
    e.update(out)
    return True


def upgrade(path: str) -> int:
    """Moves each motorsport entry's old `Motorsport|Class|<class>` tag into `extra` and
    `Motorsport|Vehicle|<make>[|<model>]` into `make`/`model`, after the entry's id, number, name and
    team; a `tags` list left empty is removed. Only those literal roots are matched. A field already
    holding the same value just loses the tag. Returns the number of entries changed; 0 writes
    nothing (also for a file that does not parse, has no entry list, or is kind people). Raises
    ValueError, writing nothing, when a field disagrees with its tag, an entry has two class or two
    vehicle tags, or a vehicle tag has more than make|model. Layout, line endings and the .bak are as
    in set_colours."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        raw = f.read()
    eol = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    try:
        data = json.loads(text)
    except ValueError:
        return 0
    if isinstance(data, dict) and data.get("kind", "motorsport") != "motorsport":
        return 0
    entries = data.get("entries") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        return 0
    n = sum(_upgrade_entry(e) for e in entries if isinstance(e, dict))
    if n:
        _write(path, text, data, eol)
    return n


FIELD_NOUNS = {"team": "team", "name": "driver"}
_BAD_TEXT = re.compile(r'[,;"]')  # identify.py rejects these in a team or name


def add_entries(path: str, numbers: list, fields: list) -> int:
    """Appends an entry `{"id": n, "number": n}` for each of `numbers` and sets each of `fields`
    ((entry id, "team" | "name", value)) on its entry. Returns the number of changes written.
    Raises ValueError, writing nothing, when the file does not parse, a number is already an
    entry's id or number or not 1-3 digits, a value holds , ; or ", a field's entry is missing or already has a value, or two rows set the
    same field of one entry. Layout, line endings and the .bak are as in set_colours."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        raw = f.read()
    eol = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    try:
        data = json.loads(text)
    except ValueError as e:
        raise ValueError(f"entries.json does not parse ({e})") from None
    entries = data.get("entries") if isinstance(data, dict) else data
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise ValueError("entries.json has no list of entries")
    taken = {str(e[k]) for e in entries for k in ("id", "number") if e.get(k) not in (None, "")}
    for n in numbers:
        if not n:
            raise ValueError("a new entry needs a number")
        if not re.fullmatch(r"\d{1,3}", n):
            raise ValueError(f"{n} is not a race number (1-3 digits)")
        if n in taken:
            raise ValueError(f"{n} is already an entry")
        taken.add(n)
    by_id = {str(e.get("id")): e for e in entries}
    seen = set()
    for entry_id, key, value in fields:
        if key not in FIELD_NOUNS:
            raise ValueError(f"{key} is not a field this adds (team or name)")
        if not value:
            raise ValueError(f"entry {entry_id}: the {FIELD_NOUNS[key]} to add is empty")
        if _BAD_TEXT.search(value):
            raise ValueError(f'entry {entry_id}: the {FIELD_NOUNS[key]} "{value}" can\'t contain , ; or "')
        entry = by_id.get(entry_id)
        if entry is None:
            raise ValueError(f"entry {entry_id} is not in entries.json")
        if entry.get(key):
            raise ValueError(f"entry {entry_id} already has a {FIELD_NOUNS[key]}: {entry[key]}")
        if (entry_id, key) in seen:
            raise ValueError(f"entry {entry_id} is given two {FIELD_NOUNS[key]}s")
        seen.add((entry_id, key))
    if not numbers and not fields:
        return 0
    for n in numbers:
        entries.append({"id": n, "number": n})
    for entry_id, key, value in fields:
        by_id[entry_id][key] = value
    _write(path, text, data, eol)
    return len(numbers) + len(fields)


def read_additions(path: str) -> tuple:
    """(numbers, fields) from an additions CSV. Raises ValueError on any other row."""
    numbers, fields = [], []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.reader(f):
            if len(row) == 2 and row[0] == "number":
                numbers.append(row[1])
            elif len(row) == 4 and row[0] == "field":
                fields.append((row[1], row[2], row[3]))
            elif row:
                raise ValueError(f"additions: unreadable row {row}")
    return numbers, fields


def main(argv) -> int:
    if len(argv) != 3 or argv[0] != "add":
        print("usage: entries_file.py add <entries.json> <additions.csv>")
        return 2
    try:
        numbers, fields = read_additions(argv[2])
        add_entries(argv[1], numbers, fields)
    except (ValueError, OSError) as e:
        print(f"entries.json was not changed: {e}")
        return 1
    print(f"added {len(numbers)} entries and {len(fields)} fields to entries.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

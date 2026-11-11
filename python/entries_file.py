"""entries.json round trip for the reference actions: fills an entry's `colour` without changing
anything else. A file already in the canonical layout (`dump`) keeps its layout; any other layout
is reflowed into the canonical one, with the previous file kept as entries.json.bak."""

import json
import shutil

from common import atomic_write


def _entry(entry: dict) -> str:
    inner = json.dumps(entry, ensure_ascii=False)[1:-1]
    return "{ " + inner + " }" if inner else "{}"


def dump(data, inline_rules: bool = False) -> str:
    """The canonical layout, as the examples and assisted_tagging.lua's M.entries_json write it: one
    entry per line (`{ "id": ..., ... }`), indented 4 under an object's "entries" and 2 in a bare
    list; every other top-level value (the rules block) is 2-space indented JSON, or with
    `inline_rules` one line (`{ "tag_prefix": ... }`, as M.entries_json writes it). Key order is kept."""
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
    with open(path, encoding="utf-8", newline="") as f:
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
    original = json.loads(text)
    inline = next((i for i in (False, True) if dump(original, i).rstrip() == text.rstrip()), None)
    out = dump(data, False) if inline is None else dump(data, inline).rstrip() + text[len(text.rstrip()):]
    with atomic_write(path, newline="") as f:
        f.write(out.replace("\n", eol))
        shutil.copy2(path, path + ".bak")  # the original, before the replace on exit
    return True, "set"

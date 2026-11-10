"""entries.json round trip for the reference actions: fills an entry's `colour` without changing
anything else. Only a file already in the canonical layout (`dump`) is rewritten; any other layout
is left alone, so a hand-formatted file never gets reflowed."""

import json
import os
import shutil


def _entry(entry: dict) -> str:
    inner = json.dumps(entry, ensure_ascii=False)[1:-1]
    return "{ " + inner + " }" if inner else "{}"


def dump(data) -> str:
    """The canonical layout, as the examples and assisted_tagging.lua's M.entries_json write it: one
    entry per line (`{ "id": ..., ... }`), indented 4 under an object's "entries" and 2 in a bare
    list; every other top-level value (the rules block) is 2-space indented JSON. Key order is kept."""
    if isinstance(data, list):
        return "[\n" + ",\n".join("  " + _entry(e) for e in data) + "\n]\n"
    lines = []
    for key, value in data.items():
        if key == "entries" and isinstance(value, list):
            text = "[\n" + ",\n".join("    " + _entry(e) for e in value) + "\n  ]" if value else "[]"
        else:
            text = json.dumps(value, indent=2, ensure_ascii=False).replace("\n", "\n  ")
        lines.append(f"  {json.dumps(key, ensure_ascii=False)}: {text}")
    return "{\n" + ",\n".join(lines) + "\n}\n"


def set_colours(path: str, colours: dict) -> tuple:
    """Gives each entry in `colours` ({entry id: colour}) that has no colour yet its colour, appended
    as its last key. Entries that already have a colour are never touched. Returns (written, reason):
    (True, "set"), or (False, "unchanged") when no entry needed one, or (False, "layout") when the file
    isn't in `dump`'s layout (trailing whitespace aside). Writes a temp file, keeps the previous file
    as entries.json.bak, then replaces it; line endings and trailing whitespace are kept."""
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
    if dump(json.loads(text)).rstrip() != text.rstrip():
        return False, "layout"
    out = dump(data).rstrip() + text[len(text.rstrip()):]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(out.replace("\n", eol))
    shutil.copy2(path, path + ".bak")
    os.replace(tmp, path)
    return True, "set"

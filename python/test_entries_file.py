"""entries_file: the canonical one-entry-per-line layout and the colour writer. Run: python test_entries_file.py"""

import json
import os
import shutil
import sys
import tempfile

import entries_file as F

failures = 0
EXAMPLES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "examples")


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


def copy_example(name: str) -> str:
    path = os.path.join(tempfile.mkdtemp(), "entries.json")
    shutil.copyfile(os.path.join(EXAMPLES, name, "entries.json"), path)
    return path


def write(text: str) -> str:
    path = os.path.join(tempfile.mkdtemp(), "entries.json")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return path


def read(path: str) -> str:
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def run_tests():
    rally = copy_example("rally")
    text = read(rally)
    check("rally's entries.json is in the canonical layout", F.dump(json.loads(text)).rstrip(), text.rstrip())

    # f1-season spreads each entry over several lines, so the writer leaves it alone
    f1 = copy_example("f1-season")
    f1_text = read(f1)
    check("f1-season's entries.json isn't one entry per line", F.dump(json.loads(f1_text)).rstrip() == f1_text.rstrip(), False)
    check("f1-season is refused for layout", F.set_colours(f1, {"LEC": "Red"}), (False, "layout"))
    check("a refused f1-season file is unchanged", read(f1), f1_text)

    check("adding a colour writes", F.set_colours(rally, {"12": "Red"}), (True, "set"))
    new = read(rally)
    old_lines, new_lines = text.splitlines(), new.splitlines()
    changed = [i for i, (a, b) in enumerate(zip(old_lines, new_lines)) if a != b]
    check("only the coloured entry's line changes", (len(old_lines) == len(new_lines), [new_lines[i] for i in changed]),
          (True, ['    { "id": "12", "number": "12", "colour": "Red" },']))
    check("the coloured line ends with the colour", new_lines[changed[0]].rstrip(",").endswith('"colour": "Red" }'), True)
    check("the previous file is kept as entries.json.bak", read(rally + ".bak"), text)
    check("no temp file is left", os.path.exists(rally + ".tmp"), False)

    blue = write('[\n  { "id": "A", "colour": "Blue" }\n]\n')
    before = read(blue)
    check("an entry with a colour is never changed", F.set_colours(blue, {"A": "Red"}), (False, "unchanged"))
    check("an unchanged file keeps its bytes", read(blue), before)
    check("an unchanged file gets no .bak", os.path.exists(blue + ".bak"), False)

    split = write('{\n  "rules": {},\n  "entries": [\n    { "id": "A",\n      "number": "1" }\n  ]\n}\n')
    before = read(split)
    check("an entry split over two lines is refused for layout", F.set_colours(split, {"A": "Red"}), (False, "layout"))
    check("a refused file keeps its bytes", read(split), before)

    lua_form = write('{\n  "rules": { "tag_prefix": "F1" },\n  "entries": [\n'
                     '    { "id": "A", "number": "1", "team": "", "name": "A" }\n  ]\n}\n')
    check("the panel's one-line rules layout writes", F.set_colours(lua_form, {"A": "Red"}), (True, "set"))
    check("the one-line rules layout is kept", read(lua_form),
          '{\n  "rules": { "tag_prefix": "F1" },\n  "entries": [\n'
          '    { "id": "A", "number": "1", "team": "", "name": "A", "colour": "Red" }\n  ]\n}\n')

    bare = write('[\n  { "id": "A", "number": "1" },\n  { "id": "B", "number": "2" }\n]\n')
    check("a bare list writes", F.set_colours(bare, {"B": "Green"}), (True, "set"))
    check("a bare list stays a bare list",
          read(bare), '[\n  { "id": "A", "number": "1" },\n  { "id": "B", "number": "2", "colour": "Green" }\n]\n')

    empty = write('[\n  { "id": "A", "colour": "" }\n]\n')
    F.set_colours(empty, {"A": "Red"})
    check("an empty colour is filled and moved to the last key", json.loads(read(empty)), [{"id": "A", "colour": "Red"}])

    crlf = write('[\r\n  { "id": "A" }\r\n]\r\n')
    F.set_colours(crlf, {"A": "Red"})
    check("CRLF line endings are kept", read(crlf), '[\r\n  { "id": "A", "colour": "Red" }\r\n]\r\n')

    print("")
    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

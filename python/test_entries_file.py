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


def raised(fn) -> str:
    try:
        fn()
    except ValueError as e:
        return str(e)
    return "(no error)"


PLAIN = '{\n  "rules": {\n    "team_only": "none"\n  },\n  "entries": [\n    { "id": "12", "number": "12" },\n' \
        '    { "id": "A", "number": "7", "team": "Ferrari", "name": "" }\n  ]\n}\n'


def test_add_entries():
    # test_add_number
    path = write(PLAIN)
    check("add: a number is written", F.add_entries(path, ["115"], []), 1)
    check("add: the new entry is appended as id and number strings", read(path),
          PLAIN.replace('"name": "" }\n', '"name": "" },\n    { "id": "115", "number": "115" }\n'))
    check("add: the previous file is kept as .bak", read(path + ".bak"), PLAIN)

    # test_add_field
    path = write(PLAIN)
    check("add: fields are written", F.add_entries(path, [], [("12", "team", "AF Corse"), ("A", "name", "Leclerc")]), 2)
    check("add: a missing field is appended and an empty one filled", json.loads(read(path))["entries"],
          [{"id": "12", "number": "12", "team": "AF Corse"}, {"id": "A", "number": "7", "team": "Ferrari", "name": "Leclerc"}])
    check("add: nothing to add writes nothing", (F.add_entries(path, [], []), read(path + ".bak")), (0, PLAIN))

    # test_add_entries_stale
    for name, numbers, fields, want in (
            ("a number that is an entry's number", ["7"], [], "7 is already an entry"),
            ("a number that is an entry's id", ["12"], [], "12 is already an entry"),
            ("the same number twice", ["115", "115"], [], "115 is already an entry"),
            ("a field already set", ["115"], [("A", "team", "Sauber")], "entry A already has a team: Ferrari"),
            ("a field of a missing entry", [], [("99", "team", "Sauber")], "entry 99 is not in entries.json"),
            ("a number that isn't 1-3 digits", ["1234"], [], "1234 is not a race number (1-3 digits)"),
            ("a team holding a comma", ["115"], [("12", "team", "Smith, Jones")],
             'entry 12: the team "Smith, Jones" can\'t contain , ; or "'),
            ("a driver holding a quote", [], [("12", "name", 'O"Neil')], 'entry 12: the driver "O"Neil" can\'t contain , ; or "')):
        path = write(PLAIN)
        check(f"add: {name} raises", raised(lambda: F.add_entries(path, numbers, fields)), want)
        check(f"add: {name} leaves the file and writes no .bak", (read(path), os.path.exists(path + ".bak")), (PLAIN, False))
    broken = write('{ "entries": [')
    check("add: a file that no longer parses raises",
          raised(lambda: F.add_entries(broken, ["115"], [])).startswith("entries.json does not parse"), True)
    check("add: a file that no longer parses is left alone", (read(broken), os.path.exists(broken + ".bak")), ('{ "entries": [', False))

    # test_add_same_field_twice
    path = write(PLAIN)
    check("add: two values for one field raise",
          raised(lambda: F.add_entries(path, [], [("12", "team", "Ferrari"), ("12", "team", "AF Corse")])),
          "entry 12 is given two teams")
    check("add: two values for one field leave the file", read(path), PLAIN)

    # test_add_bom
    path = write("\ufeff" + PLAIN)
    F.add_entries(path, ["115"], [])
    check("add: a file saved with a BOM is read and written back without it", read(path),
          PLAIN.replace('"name": "" }\n', '"name": "" },\n    { "id": "115", "number": "115" }\n'))

    # test_add_keeps_layout
    inline = write('{\n  "rules": { "team_only": "none" },\n  "entries": [\n    { "id": "A", "number": "1" }\n  ]\n}\n')
    F.add_entries(inline, ["2"], [("A", "team", "Ferrari")])
    check("add: the one-line rules layout is kept", read(inline),
          '{\n  "rules": { "team_only": "none" },\n  "entries": [\n    { "id": "A", "number": "1", "team": "Ferrari" },\n'
          '    { "id": "2", "number": "2" }\n  ]\n}\n')
    crlf = write('[\r\n  { "id": "A", "number": "1" }\r\n]\r\n')
    F.add_entries(crlf, ["2"], [])
    check("add: a bare list and CRLF line endings are kept", read(crlf),
          '[\r\n  { "id": "A", "number": "1" },\r\n  { "id": "2", "number": "2" }\r\n]\r\n')

    # the shell form the panel runs
    path = write(PLAIN)
    rows = os.path.join(os.path.dirname(path), "additions.csv")
    with open(rows, "w", encoding="utf-8", newline="") as f:
        f.write('number,115\nfield,12,team,"AF Corse"\n')
    check("add: the shell form writes and exits 0", F.main(["add", path, rows]), 0)
    check("add: the shell form reads quoted values", json.loads(read(path))["entries"][0]["team"], "AF Corse")
    check("add: the shell form exits 1 on stale rows", F.main(["add", path, rows]), 1)


def run_tests():
    rally = copy_example("rally")
    text = read(rally)
    check("rally's entries.json is in the canonical layout", F.dump(json.loads(text)).rstrip(), text.rstrip())

    # f1-season spreads each entry over several lines, so the writer reflows it into the canonical layout
    f1 = copy_example("f1-season")
    f1_text = read(f1)
    check("f1-season's entries.json isn't one entry per line", F.dump(json.loads(f1_text)).rstrip() == f1_text.rstrip(), False)
    check("f1-season is written", F.set_colours(f1, {"LEC": "Red"}), (True, "set"))
    f1_data = json.loads(f1_text)
    next(e for e in f1_data["entries"] if e["id"] == "LEC")["colour"] = "Red"
    check("a reflowed f1-season file is canonical with the colour set", read(f1), F.dump(f1_data))
    check("the reflowed file's previous bytes are kept as .bak", read(f1 + ".bak"), f1_text)

    check("adding a colour writes", F.set_colours(rally, {"12": "Red"}), (True, "set"))
    new = read(rally)
    old_lines, new_lines = text.splitlines(), new.splitlines()
    changed = [i for i, (a, b) in enumerate(zip(old_lines, new_lines)) if a != b]
    check("only the coloured entry's line changes", (len(old_lines) == len(new_lines), [new_lines[i] for i in changed]),
          (True, ['    { "id": "12", "number": "12", "colour": "Red" },']))
    check("the coloured line ends with the colour", new_lines[changed[0]].rstrip(",").endswith('"colour": "Red" }'), True)
    check("the previous file is kept as entries.json.bak", read(rally + ".bak"), text)
    check("no temp file is left", [n for n in os.listdir(os.path.dirname(rally)) if n.endswith(".tmp")], [])

    blue = write('[\n  { "id": "A", "colour": "Blue" }\n]\n')
    before = read(blue)
    check("an entry with a colour is never changed", F.set_colours(blue, {"A": "Red"}), (False, "unchanged"))
    check("an unchanged file keeps its bytes", read(blue), before)
    check("an unchanged file gets no .bak", os.path.exists(blue + ".bak"), False)

    split = write('{\n  "rules": {},\n  "entries": [\n    { "id": "A",\n      "number": "1" }\n  ]\n}\n')
    check("an entry split over two lines is written", F.set_colours(split, {"A": "Red"}), (True, "set"))
    check("a split entry is reflowed onto one line", read(split),
          '{\n  "rules": {},\n  "entries": [\n    { "id": "A", "number": "1", "colour": "Red" }\n  ]\n}\n')

    lua_form = write('{\n  "rules": { "team_only": "none" },\n  "entries": [\n'
                     '    { "id": "A", "number": "1", "team": "", "name": "A" }\n  ]\n}\n')
    check("the panel's one-line rules layout writes", F.set_colours(lua_form, {"A": "Red"}), (True, "set"))
    check("the one-line rules layout is kept", read(lua_form),
          '{\n  "rules": { "team_only": "none" },\n  "entries": [\n'
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

    test_add_entries()

    print("")
    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

# Run with: python python/test_import_start_list.py
# Exercises import_start_list.py: CSV and pasted start lists into entries.json; temp files only.

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import import_start_list as M
from entries_file import dump

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


def exits_2(argv):
    try:
        M.main(argv)
    except SystemExit as e:
        return e.code
    return None


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def entries_of(cdir):
    return json.load(open(os.path.join(cdir, "entries.json"), encoding="utf-8"))["entries"]


def run_tests():
    with tempfile.TemporaryDirectory() as tmp:
        cdir = os.path.join(tmp, "rally")
        os.makedirs(cdir)
        csv_path = os.path.join(tmp, "start.csv")
        write(csv_path, "No.;Driver;Co-Driver;Entrant;Class\n1;Smith;Jones;Team A;RC1\n#12;Doe, J;;;\n7;Lee;Kim;Team B;RC2\n\n")

        check("a new entries.json needs a prefix", exits_2([cdir, "--csv", csv_path]), 2)
        M.main([cdir, "--csv", csv_path, "--tag-prefix", "Rally|2026"])
        data = json.load(open(os.path.join(cdir, "entries.json"), encoding="utf-8"))
        check("a CSV creates entries.json with the prefix", data["rules"], {"tag_prefix": "Rally|2026"})
        check("header aliases map the columns; class becomes a tag; commas are cleaned", data["entries"], [
            {"id": "1", "number": "1", "name": "Smith / Jones", "team": "Team A", "tags": ["Rally|2026|Class|RC1"]},
            {"id": "12", "number": "12", "name": "Doe J"},
            {"id": "7", "number": "7", "name": "Lee / Kim", "team": "Team B", "tags": ["Rally|2026|Class|RC2"]},
        ])
        check("the file is in the canonical layout", open(os.path.join(cdir, "entries.json"), encoding="utf-8").read(),
              dump(data))

        M.main([cdir, "--csv", csv_path])
        check("re-importing the same CSV adds nothing", [e["id"] for e in entries_of(cdir)], ["1", "12", "7"])
        check("a no-op import writes no .bak", os.path.exists(os.path.join(cdir, "entries.json.bak")), False)

        pasted = os.path.join(tmp, "pasted.txt")
        write(pasted, "Entry list\n7. Lee / Kim\n21 - Brown / Green\n#105 Solo\nnot an entry\n")
        M.main([cdir, "--text", pasted])
        check("pasted lines add only the new numbers", [e["id"] for e in entries_of(cdir)], ["1", "12", "7", "21", "105"])
        check("a pasted line splits driver / co-driver", entries_of(cdir)[3], {"id": "21", "number": "21", "name": "Brown / Green"})
        check("the previous file is kept as .bak",
              [e["id"] for e in json.load(open(os.path.join(cdir, "entries.json.bak"), encoding="utf-8"))["entries"]], ["1", "12", "7"])

        rows, skipped = M.rows_from_text("Entry list\n3 A / B\nx\n")
        check("rows_from_text counts lines without a number", (rows, skipped),
              ([{"number": "3", "driver": "A", "co-driver": "B"}], 2))
        check("rows_from_csv takes the header's delimiter, CRLF included",
              [r["number"] for r in M.rows_from_csv("No.;Driver\r\n1;Smith, J\r\n2;Lee\r\n", {})], ["1", "2"])
        check("rows_from_csv falls back to a comma", M.rows_from_csv("No.,Driver\n4,Kim\n", {})[0]["driver"], "Kim")

        cols = M.parse_columns("number=Nr; driver=Pilot")
        check("parse_columns reads role=header pairs", cols, {"number": "Nr", "driver": "Pilot"})
        mapped = M.map_header(["Pilot", "Nr", "Team"], cols)
        check("map_header uses --columns first and aliases for the rest", mapped, {"number": 1, "driver": 0, "team": 2})
        try:
            M.map_header(["Pilot", "Team"], {})
            check("map_header needs a number column", None, "BadInput")
        except M.BadInput:
            check("map_header needs a number column", "BadInput", "BadInput")
        try:
            M.parse_columns("colour=Paint")
            check("parse_columns rejects an unknown role", None, "BadInput")
        except M.BadInput:
            check("parse_columns rejects an unknown role", "BadInput", "BadInput")

        bad = os.path.join(tmp, "bad.csv")
        write(bad, "number,driver\n1234,Too long\n")
        check("a number over 3 digits fails", exits_2([cdir, "--csv", bad]), 2)
        twice = os.path.join(tmp, "twice.csv")
        write(twice, "number,driver\n9,A\n9,B\n")
        check("a number listed twice fails", exits_2([cdir, "--csv", twice]), 2)

        hand = os.path.join(tmp, "hand")
        os.makedirs(hand)
        write(os.path.join(hand, "entries.json"), '{"rules": {"tag_prefix": "R"},\n "entries": [{"id": "1", "number": "1"}]}\n')
        M.main([hand, "--text", pasted])
        check("a hand-formatted file is left alone", open(os.path.join(hand, "entries.json"), encoding="utf-8").read(),
              '{"rules": {"tag_prefix": "R"},\n "entries": [{"id": "1", "number": "1"}]}\n')
        side = json.load(open(os.path.join(hand, "start-list.new.json"), encoding="utf-8"))
        check("its new entries go to start-list.new.json", [e["id"] for e in side], ["7", "21", "105"])

        bare = os.path.join(tmp, "bare")
        os.makedirs(bare)
        write(os.path.join(bare, "entries.json"), '[\n  { "id": "1", "tags": ["X"] }\n]\n')
        check("a bare list without rules fails", exits_2([bare, "--text", pasted, "--tag-prefix", "R"]), 2)

    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

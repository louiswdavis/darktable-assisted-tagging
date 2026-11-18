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

        check("the removed --tag-prefix flag is rejected", exits_2([cdir, "--csv", csv_path, "--tag-prefix", "Rally|2026"]), 2)
        check("a rejected run writes no entries.json", os.path.exists(os.path.join(cdir, "entries.json")), False)
        M.main([cdir, "--csv", csv_path])
        data = json.load(open(os.path.join(cdir, "entries.json"), encoding="utf-8"))
        check("a CSV creates entries.json with no rules", list(data), ["entries"])
        check("header aliases map the columns; class becomes a tag; commas are cleaned", data["entries"], [
            {"id": "1", "number": "1", "name": "Smith", "co_driver": "Jones", "team": "Team A", "extra": "RC1"},
            {"id": "12", "number": "12", "name": "Doe J"},
            {"id": "7", "number": "7", "name": "Lee", "co_driver": "Kim", "team": "Team B", "extra": "RC2"},
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
        check("a pasted line splits driver / co-driver", entries_of(cdir)[3],
              {"id": "21", "number": "21", "name": "Brown", "co_driver": "Green"})
        check("a pasted line without a co-driver has no co_driver", entries_of(cdir)[4], {"id": "105", "number": "105", "name": "Solo"})
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
        check("parse_columns: role= means no column", M.parse_columns("team="), {"team": ""})
        check("map_header: a role given as none skips its alias",
              M.map_header(["No.", "Driver", "Team"], {"team": ""}), {"number": 0, "driver": 1})
        check("map_header: need_number=False allows no number", M.map_header(["Pilot"], {}, need_number=False), {"driver": 0})
        check("rows_from_csv splits a shared driver cell with no co-driver column",
              M.rows_from_csv("No.,Driver\n5,Smith / Jones\n", {})[0], {"number": "5", "driver": "Smith", "co-driver": "Jones"})
        check("rows_from_csv keeps the cell when a co-driver column exists",
              M.rows_from_csv("No.,Driver,Co-driver\n5,Smith / Jones,\n", {})[0]["driver"], "Smith / Jones")
        check("header_report lists headers then each role's mapped header",
              M.header_report("Nr;Pilot;Team\n1;A;B\n").split("\n"),
              ["header\tNr", "header\tPilot", "header\tTeam", "role\tnumber\tNr", "role\tdriver\tPilot", "role\tco-driver\t",
               "role\tteam\tTeam", "role\tclass\t", "role\tmake\t", "role\tmodel\t", "role\tshares-car\t", "role\tsection\t"])

        codir = os.path.join(tmp, "codrivers")
        os.makedirs(codir)
        cocsv = os.path.join(tmp, "codrivers.csv")
        write(cocsv, 'No.,Driver,Co-Driver\n5,,"Ray, J"\n')
        M.main([codir, "--csv", cocsv])
        check("a co-driver alone gets co_driver, cleaned of , ; and \"", entries_of(codir),
              [{"id": "5", "number": "5", "co_driver": "Ray J"}])

        vdir = os.path.join(tmp, "vehicles")
        os.makedirs(vdir)
        vcsv = os.path.join(tmp, "vehicles.csv")
        write(vcsv, "Car No,Driver,Vehicle,Make,Model,Class\n30,Ames,Ford Escort Mk1,Ford,Escort Mk1,Class 2\n"
                    "31,Bell,Lotus,Lotus,,\n32,Cole,,,,\n33,Dent,,Mini|BMW,Cooper; S,\n")
        M.main([vdir, "--csv", vcsv])
        check("class column → extra, make+model → make, model, make only → make; | and ; are removed; no tags",
              entries_of(vdir),
              [{"id": "30", "number": "30", "name": "Ames", "extra": "Class 2", "make": "Ford", "model": "Escort Mk1"},
               {"id": "31", "number": "31", "name": "Bell", "make": "Lotus"},
               {"id": "32", "number": "32", "name": "Cole"},
               {"id": "33", "number": "33", "name": "Dent", "make": "MiniBMW", "model": "Cooper S"}])
        check("fields follow id, number, name, team order", list(entries_of(vdir)[0]),
              ["id", "number", "name", "extra", "make", "model"])
        check("the Vehicle column isn't read as a role", "vehicle" in M.map_header(["Car No", "Vehicle"], {}), False)
        nomake = os.path.join(tmp, "nomake.csv")
        write(nomake, "number,model\n5,Escort\n")
        check("a model with no make fails", exits_2([vdir, "--csv", nomake]), 2)

        sdir = os.path.join(tmp, "shared")
        os.makedirs(sdir)
        scsv = os.path.join(tmp, "shared.csv")
        write(scsv, "Car No,Driver,Shares Car With\n30,Ames,730\n12,Bell,\n730,Cole,30\n")
        M.main([sdir, "--csv", scsv])
        check("the higher number of a shared car names the lower; the lower and unshared rows get no car",
              [(e["id"], e.get("car")) for e in entries_of(sdir)], [("30", None), ("12", None), ("730", "30")])
        for label, text in (("a one-way pair fails", "number,shares car\n30,730\n730,\n"),
                            ("a partner not in the list fails", "number,shares car\n30,730\n"),
                            ("a partner naming a third number fails", "number,shares car\n30,730\n730,31\n31,730\n"),
                            ("a partner that isn't a number fails", "number,shares car\n30,x\n"),
                            ("a car shared with itself fails", "number,shares car\n30,30\n")):
            path = os.path.join(tmp, "pair.csv")
            write(path, text)
            check(label, exits_2([os.path.join(tmp, "unused"), "--csv", path]), 2)

        bad = os.path.join(tmp, "bad.csv")
        write(bad, "number,driver\n1234,Too long\n")
        check("a number over 3 digits fails", exits_2([cdir, "--csv", bad]), 2)
        twice = os.path.join(tmp, "twice.csv")
        write(twice, "number,driver\n9,A\n9,B\n")
        check("a number listed twice fails", exits_2([cdir, "--csv", twice]), 2)

        hand = os.path.join(tmp, "hand")
        os.makedirs(hand)
        write(os.path.join(hand, "entries.json"), '{"rules": {"team_only": "none"},\n "entries": [{"id": "1", "number": "1"}]}\n')
        M.main([hand, "--text", pasted])
        reflowed = json.load(open(os.path.join(hand, "entries.json"), encoding="utf-8"))
        check("a hand-formatted file gets the new entries", [e["id"] for e in reflowed["entries"]], ["1", "7", "21", "105"])
        check("a hand-formatted file is reflowed into the canonical layout",
              open(os.path.join(hand, "entries.json"), encoding="utf-8").read(), dump(reflowed))
        check("the hand-formatted original is kept as .bak", open(os.path.join(hand, "entries.json.bak"), encoding="utf-8").read(),
              '{"rules": {"team_only": "none"},\n "entries": [{"id": "1", "number": "1"}]}\n')

        demo = os.path.join(tmp, "demo")
        os.makedirs(demo)
        demo_csv = os.path.join(tmp, "demo.csv")
        write(demo_csv, "Car No,Driver,Section\n8,Race Eight,Entry\n14,Race Fourteen,Entry\n8,Demo Eight,Demonstration\n")
        M.main([demo, "--csv", demo_csv])
        check("a Demonstration row gets id D<number>; demo 8 and race 8 are separate entries",
              [(e["id"], e["number"], e.get("name")) for e in entries_of(demo)],
              [("8", "8", "Race Eight"), ("14", "14", "Race Fourteen"), ("D8", "8", "Demo Eight")])
        demo_twice = os.path.join(tmp, "demo_twice.csv")
        write(demo_twice, "Car No,Driver,Section\n3,A,Demonstration\n3,B,Demonstration\n")
        check("a demo number listed twice fails", exits_2([demo, "--csv", demo_twice]), 2)
        rows, _ = M.rows_from_text("1 Smith / Jones\nDemonstrations\nDemo No Driver Licence Paddock\n4 Lee\n")
        check("pasted lines after a Demo heading are demo rows",
              [(r["number"], r.get("section", "")) for r in rows], [("1", ""), ("4", "Demonstration")])

        rekey = os.path.join(tmp, "rekey")
        os.makedirs(os.path.join(rekey, "refs", "14"))
        os.makedirs(os.path.join(rekey, "refs", "60"))
        write(os.path.join(rekey, "refs", "14", "a.jpg"), "x")
        write(os.path.join(rekey, "refs", "14", "a_b3.jpg"), "y")
        write(os.path.join(rekey, "refs", "60", "c.jpg"), "z")
        write(os.path.join(rekey, "refs", "sources.json"), json.dumps({
            "refs/14/a.jpg": {"source": "hand", "confidence": None, "date": "2026-11-17"},
            "refs/60/c.jpg": {"source": "picked", "confidence": None, "date": "2026-11-17"}}))
        write(os.path.join(rekey, "entries.json"), dump({"entries": [
            {"id": "14", "number": "14", "name": "Demo Fourteen", "shows": ["44"]},
            {"id": "15", "number": "15", "name": "Other", "car": "14"},
            {"id": "60", "number": "60", "name": "Race Sixty"}]}))
        rekey_csv = os.path.join(tmp, "rekey.csv")
        write(rekey_csv, "Car No,Driver,Section\n60,Race Sixty,Entry\n14,Demo Fourteen,Demonstration\n")
        M.main([rekey, "--csv", rekey_csv])
        got = entries_of(rekey)
        check("an existing bare-number entry is renamed to its demo id, keeping its fields",
              [(e["id"], e["number"], e.get("shows")) for e in got],
              [("D14", "14", ["44"]), ("15", "15", None), ("60", "60", None)])
        check("a car field naming the old id follows the rename", got[1].get("car"), "D14")
        check("the refs folder moves to the demo id",
              (sorted(os.listdir(os.path.join(rekey, "refs", "D14"))), os.path.exists(os.path.join(rekey, "refs", "14"))),
              (["a.jpg", "a_b3.jpg"], False))
        check("sources.json records follow the move; other cars' records stay",
              sorted(json.load(open(os.path.join(rekey, "refs", "sources.json"), encoding="utf-8"))),
              ["refs/60/c.jpg", "refs/D14/a.jpg"])

        clash = os.path.join(tmp, "clash")
        os.makedirs(clash)
        write(os.path.join(clash, "entries.json"), dump({"entries": [{"id": "14", "number": "14", "name": "Someone Else"}]}))
        M.main([clash, "--csv", rekey_csv])
        check("a bare-number entry with a different driver isn't renamed; the demo is added beside it",
              [(e["id"], e.get("name")) for e in entries_of(clash)],
              [("14", "Someone Else"), ("60", "Race Sixty"), ("D14", "Demo Fourteen")])

        bare = os.path.join(tmp, "bare")
        os.makedirs(bare)
        write(os.path.join(bare, "entries.json"), '[\n  { "id": "1", "tags": ["X"] }\n]\n')
        check("a bare list fails", exits_2([bare, "--text", pasted]), 2)

    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

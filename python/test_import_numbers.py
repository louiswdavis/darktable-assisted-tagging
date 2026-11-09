# Run with: python python/test_import_numbers.py
# Exercises import_numbers.py's numbers-only entries.json builder; temp files only.

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import import_numbers as M

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


def run_tests():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "numbers.csv")
        out = os.path.join(tmp, "entries.json")

        with open(src, "w", encoding="utf-8") as f:
            f.write("number,driver\n12,Smith\n7\n 101 ,x\n\n")
        M.main([src, out, "--tag-prefix", "Rally|2026", "--order-weight", "0.5"])
        data = json.load(open(out, encoding="utf-8"))
        check("import writes numbers-only entries", data["entries"],
              [{"id": "12", "number": "12"}, {"id": "7", "number": "7"}, {"id": "101", "number": "101"}])
        check("import writes the rules", data["rules"], {"tag_prefix": "Rally|2026", "order_weight": 0.5})

        check("import refuses to overwrite", exits_2([src, out, "--tag-prefix", "Rally|2026"]), 2)

        dup = os.path.join(tmp, "dup.csv")
        with open(dup, "w", encoding="utf-8") as f:
            f.write("12\n7\n12\n")
        check("import rejects a duplicate number", exits_2([dup, os.path.join(tmp, "d.json"), "--tag-prefix", "R"]), 2)

        empty = os.path.join(tmp, "empty.csv")
        with open(empty, "w", encoding="utf-8") as f:
            f.write("number\n")
        check("import rejects an empty list", exits_2([empty, os.path.join(tmp, "e.json"), "--tag-prefix", "R"]), 2)

        check("import rejects an order weight out of range",
              exits_2([src, os.path.join(tmp, "w.json"), "--tag-prefix", "R", "--order-weight", "2"]), 2)

        M.main([src, os.path.join(tmp, "nw.json"), "--tag-prefix", "R"])
        check("no weight given leaves it out of the rules",
              json.load(open(os.path.join(tmp, "nw.json"), encoding="utf-8"))["rules"], {"tag_prefix": "R"})

    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

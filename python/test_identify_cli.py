"""identify.py's command line: --list, the entries/rules CSV outputs, exit codes on bad input, and the
entry-list check. Real functions throughout; the only fakes are folders and files on disk."""
import contextlib
import io
import json
import os
import sys
import tempfile
import types

import numpy as np
from PIL import Image

import identify as I

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


def make_collection(root: str, name: str, entries) -> str:
    folder = os.path.join(root, name)
    os.makedirs(folder)
    with open(os.path.join(folder, "entries.json"), "w", encoding="utf-8") as f:
        json.dump(entries, f)
    with open(os.path.join(folder, "settings.json"), "w", encoding="utf-8") as f:
        json.dump({"family_team_root": "F1"}, f)
    return folder


def run_main(argv: list) -> tuple:
    """(exit code, stderr text) of identify.main(argv); 0 when it returns."""
    err = io.StringIO()
    code = 0
    with contextlib.redirect_stderr(err):
        try:
            I.main(argv)
        except SystemExit as e:
            code = e.code
    return code, err.getvalue()


def run_tests():
    VER = {"id": "VER", "number": "1", "team": "Red Bull", "tags": ["F1|Red Bull"]}
    TSU = {"id": "TSU", "number": "22", "team": "Red Bull", "tags": ["F1|Red Bull"]}

    with tempfile.TemporaryDirectory() as tmp:
        # ---- list_collections
        check("list_collections: empty root is no collections", I.list_collections(""), [])
        check("list_collections: missing folder is no collections", I.list_collections(os.path.join(tmp, "nope")), [])
        root = os.path.join(tmp, "collections")
        make_collection(tmp, "collections", [])  # a folder holding entries.json is not a root of collections
        os.remove(os.path.join(root, "entries.json"))
        os.remove(os.path.join(root, "settings.json"))
        make_collection(root, "rally", [VER, TSU])
        make_collection(root, "Alpha", [VER])
        os.makedirs(os.path.join(root, "no-entries"))
        check("list_collections: only folders with entries.json, case-insensitive order",
              I.list_collections(root), ["Alpha", "rally"])

        # ---- --list writes names, and the active collection's CSVs
        names_out = os.path.join(tmp, "names.txt")
        entries_out = os.path.join(tmp, "entries.csv")
        rules_out = os.path.join(tmp, "rules.csv")
        code, _ = run_main(["-", "-", "--list", "--collections-root", root, "--collections-out", names_out,
                            "--collection", "rally", "--entries-out", entries_out, "--rules-out", rules_out])
        check("--list exits 0", code, 0)
        with open(names_out, encoding="utf-8") as f:
            check("--list writes one name per line", f.read(), "Alpha\nrally\n")
        with open(entries_out, encoding="utf-8") as f:
            check("--list writes entries.csv with both entries", [l for l in f.read().splitlines() if "VER" in l or "TSU" in l].__len__(), 2)
        check("--list writes rules.csv", os.path.getsize(rules_out) > 0, True)
        check("--list writes tag-plan.txt beside entries.json", os.path.isfile(os.path.join(root, "rally", "tag-plan.txt")), True)

        # ---- --list creates a missing collections root so the user can find it
        fresh = os.path.join(tmp, "fresh-root")
        code, _ = run_main(["-", "-", "--list", "--collections-root", fresh])
        check("--list creates the collections root", os.path.isdir(fresh), True)
        check("--list with no collections exits 0", code, 0)

        # ---- --list names an unknown collection without writing its outputs
        other_entries = os.path.join(tmp, "other-entries.csv")
        run_main(["-", "-", "--list", "--collections-root", root, "--collection", "ghost", "--entries-out", other_entries])
        check("--list skips CSVs for a collection that doesn't exist", os.path.exists(other_entries), False)

        # ---- bad input: exit 2 and a message naming the file
        broken = os.path.join(root, "broken")
        os.makedirs(broken)
        with open(os.path.join(broken, "entries.json"), "w", encoding="utf-8") as f:
            f.write("{not json")
        code, err = run_main(["-", "-", "--list", "--collections-root", root, "--collection", "broken"])
        check("a malformed entries.json exits 2", code, 2)
        check("the message names entries.json", "entries.json" in err and "Assisted Tagging:" in err, True)

    # ---- entry_list_check
    def entry_lines(raw: list, counts: dict) -> list:
        with tempfile.TemporaryDirectory() as tmp:
            folder = make_collection(tmp, "c", raw)
            entries, _rules, _fe = I.load_collection(folder, os.path.join(folder, "settings.json"))
        return I.entry_list_check(entries, counts)

    check("entry list: a clean list with references logs nothing", entry_lines([VER, TSU], {"VER": 1, "TSU": 1}), [])
    shared = entry_lines([VER, dict(TSU, number="1")], {"VER": 1, "TSU": 1})
    check("entry list: a number on two cars is reported", len(shared), 1)
    check("entry list: the shared-number line names both entries", "VER" in shared[0] and "TSU" in shared[0], True)
    check("entry list: a double-driven car's two entries are one car",
          entry_lines([VER, dict(TSU, number="1", car="VER")], {"VER": 1}), [])
    no_refs = entry_lines([VER, TSU], {"VER": 2})
    check("entry list: entries without references are reported when any exist", len(no_refs), 1)
    check("entry list: the no-references line names the entry", "TSU" in no_refs[0], True)
    check("entry list: no counts at all logs no references line", entry_lines([VER, TSU], {}), [])
    nothing = entry_lines([{"id": "X", "number": "-", "team": "T", "tags": ["F1|T"]}], {})
    check("entry list: an entry with no number, paddock or references is unfindable",
          len(nothing) == 1 and "nothing can identify it" in nothing[0], True)
    many = entry_lines([dict(VER, id=f"E{i}", number=str(i + 1)) for i in range(40)], {"E0": 1})
    check("entry list: a long list of names is capped with 'and N more'", "and " in many[0] and " more" in many[0], True)

    # ---- open_index: a real re-embed reports "embedding references" (the plugin's full job bar)
    class OneHotEmbedder:
        dim = 8

        def embed(self, crop):
            return np.eye(8, dtype=np.float32)[int(crop.mean()) % 8]

    with tempfile.TemporaryDirectory() as tmp:
        model = os.path.join(tmp, "embedder.onnx")
        with open(model, "wb") as f:
            f.write(b"x")
        rules = types.SimpleNamespace(kind="cars", blur_references=False, colour_weight=0)
        progress = os.path.join(tmp, "progress.txt")

        def add_crops(*names):
            for name in names:
                path = os.path.join(tmp, "refs", "A", name)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                Image.new("RGB", (40, 30), (60, 60, 60)).save(path)

        add_crops("1.jpg", "2.jpg", "3.jpg")
        I.open_index(tmp, {"embedder": model}, rules, OneHotEmbedder(), progress)
        with open(progress, encoding="utf-8") as pf:
            check("open_index: re-embedding three references reports the embedding stage", pf.read(), "embedding references,3,3,0")
        add_crops("4.jpg")
        I.open_index(tmp, {"embedder": model}, rules, OneHotEmbedder(), progress)
        with open(progress, encoding="utf-8") as pf:
            check("open_index: one new reference stays in the short references stage", pf.read(), "references,1,1,0")

    print("")
    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

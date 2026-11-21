"""Tests for families.py. Run: python python/test_families.py

Covers the family table, resolve (defaults, switched-off families, bad and overlapping roots),
team_tags, and that M.FAMILIES in lua/assisted_tagging.lua lists the same rows."""

import os
import re
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import families as F
import settings as S

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


def defaults(**over) -> dict:
    return {**{s.key: s.default for s in S.SETTINGS_SCHEMA}, **over}


def resolve_error(**over) -> str:
    try:
        F.resolve(defaults(**over))
    except ValueError as e:
        return str(e)
    return "(no error)"


def test_order():
    check("family order", [f.key for f in F.FAMILIES],
          ["colour", "number", "team", "driver", "co_driver", "extra", "vehicle", "paddock", "plate", "sponsor"])
    check("family sources", [f.sources for f in F.FAMILIES],
          [(), ("number",), ("team",), ("name",), ("co_driver",), ("extra",), ("make", "model"), ("paddock",), ("plate",), ()])
    check("only the plate and sponsor families are off by default", [f.key for f in F.FAMILIES if not f.default_on], ["plate", "sponsor"])
    check("setting keys", (F.switch_key("team"), F.root_key("team")), ("family_team", "family_team_root"))
    check("family_tag", F.family_tag("Assisted Tagging|Motorsport|Team", "Ferrari"), "Assisted Tagging|Motorsport|Team|Ferrari")
    check("schema defaults are the family defaults",
          [(defaults()[F.switch_key(f.key)], defaults()[F.root_key(f.key)]) for f in F.FAMILIES],
          [(f.default_on, f.default_root) for f in F.FAMILIES])


def test_resolve_defaults():
    roots = F.resolve(defaults())
    check("resolve: defaults", roots, {
        "colour": "Assisted Tagging|Motorsport|Colour", "number": "Assisted Tagging|Motorsport|Number",
        "team": "Assisted Tagging|Motorsport|Team", "driver": "Assisted Tagging|Motorsport|Driver",
        "co_driver": "Assisted Tagging|Motorsport|Co-driver",
        "extra": "Assisted Tagging|Motorsport|Class", "vehicle": "Assisted Tagging|Motorsport|Vehicle",
        "paddock": "Assisted Tagging|Motorsport|Paddock"})
    check("resolve: family order", list(roots), ["colour", "number", "team", "driver", "co_driver", "extra", "vehicle", "paddock"])
    check("resolve: custom root", F.resolve(defaults(family_team_root="Cars|Team"))["team"], "Cars|Team")
    check("resolve: sibling roots are fine",
          resolve_error(family_number_root="Cars|Number", family_team_root="Cars|Numbers"), "(no error)")


def test_resolve_off():
    roots = F.resolve(defaults(family_colour=False, family_driver=False))
    check("resolve: off families left out", list(roots), ["number", "team", "co_driver", "extra", "vehicle", "paddock"])
    check("resolve: all off", F.resolve(defaults(family_colour=False, family_number=False,
                                                 family_team=False, family_driver=False, family_co_driver=False,
                                                 family_extra=False, family_vehicle=False, family_paddock=False)), {})
    check("resolve: a switched-off family's root is not checked",
          F.resolve(defaults(family_driver=False, family_driver_root=""))["team"], "Assisted Tagging|Motorsport|Team")
    check("resolve: a switched-off family's root can overlap",
          resolve_error(family_driver=False, family_driver_root="Assisted Tagging|Motorsport|Team|Driver"), "(no error)")


def test_empty_root_names_setting():
    check("empty root", resolve_error(family_team_root=""), "family_team_root is empty")
    check("root of spaces", resolve_error(family_number_root="   "), "family_number_root is empty")
    check("root that is not text", resolve_error(family_colour_root=None), "family_colour_root is empty")


def test_bad_root_chars():
    for bad in ("Cars,Team", "Cars;Team", 'Cars"Team'):
        check(f"root {bad!r}", resolve_error(family_team_root=bad), 'family_team_root can\'t contain , ; or "')
    for bad in ("|Cars", "Cars|", " Cars", "Cars "):
        check(f"root {bad!r}", resolve_error(family_team_root=bad),
              "family_team_root can't start or end with | or a space")
    check("root_problem: a good root", F.root_problem("Cars|Team"), "")


def test_roots_must_not_nest():
    check("equal roots", resolve_error(family_number_root="Cars", family_team_root="Cars"),
          'family_number_root ("Cars") and family_team_root ("Cars") overlap; each family needs its own root')
    check("later root under an earlier one", resolve_error(family_number_root="Cars", family_team_root="Cars|Team"),
          'family_number_root ("Cars") and family_team_root ("Cars|Team") overlap; each family needs its own root')
    check("earlier root under a later one", resolve_error(family_number_root="Cars|Number", family_driver_root="Cars"),
          'family_number_root ("Cars|Number") and family_driver_root ("Cars") overlap; each family needs its own root')
    check("colour root counts too", resolve_error(family_colour_root="Assisted Tagging|Motorsport|Team|Colour"),
          'family_colour_root ("Assisted Tagging|Motorsport|Team|Colour") and family_team_root ("Assisted Tagging|Motorsport|Team") overlap; '
          "each family needs its own root")


def test_team_tags():
    entries = {i: SimpleNamespace(team=t) for i, t in
               (("16", "Ferrari"), ("1", "Red Bull"), ("55", "Ferrari"), ("99", ""))}
    check("team_tags: distinct, first seen first", F.team_tags(entries, {"team": "F1"}), ["F1|Ferrari", "F1|Red Bull"])
    check("team_tags: team family off", F.team_tags(entries, {"number": "F1"}), [])
    check("team_tags: no entries", F.team_tags({}, {"team": "F1"}), [])


def test_lua_mirror():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "lua", "assisted_tagging.lua"), encoding="utf-8") as f:
        src = f.read()
    found = re.search(r"M\.FAMILIES = \{(.*?)\n\}", src, re.S)
    check("lua M.FAMILIES block found", found is not None, True)
    rows = re.findall(r'\{ key = "(\w+)", sources = \{([^}]*)\}, default_root = "([^"]+)" \}', found.group(1) if found else "")
    rows = [(k, tuple(re.findall(r'"(\w+)"', s)), r) for k, s, r in rows]
    check("lua M.FAMILIES rows", rows, [(f.key, f.sources, f.default_root) for f in F.FAMILIES])


for t in (test_order, test_resolve_defaults, test_resolve_off, test_empty_root_names_setting,
          test_bad_root_chars, test_roots_must_not_nest, test_team_tags, test_lua_mirror):
    t()
print(f"\n{failures} failure(s)")
sys.exit(1 if failures else 0)

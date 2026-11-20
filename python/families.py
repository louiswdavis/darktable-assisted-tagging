"""Tag families: each is one kind of tag the plugin writes (a car's colour, number, team, driver,
co-driver, class, make/model, paddock id and sponsor),
with a switch and a root tag in settings.json. M.FAMILIES in lua/assisted_tagging.lua mirrors the
table. Stdlib only."""

import re
from dataclasses import dataclass

_BAD_ROOT = re.compile(r'[,;"]')


@dataclass(frozen=True)
class Family:
    key: str
    # the entry fields its value comes from, joined with | (empty ones skipped); () when read from the photo
    sources: tuple
    default_root: str
    default_on: bool = True


FAMILIES = (
    Family("colour", (), "Assisted Tagging|Motorsport|Colour"),
    Family("number", ("number",), "Assisted Tagging|Motorsport|Number"),
    Family("team", ("team",), "Assisted Tagging|Motorsport|Team"),
    Family("driver", ("name",), "Assisted Tagging|Motorsport|Driver"),
    Family("co_driver", ("co_driver",), "Assisted Tagging|Motorsport|Co-driver"),
    Family("extra", ("extra",), "Assisted Tagging|Motorsport|Class"),
    Family("vehicle", ("make", "model"), "Assisted Tagging|Motorsport|Vehicle"),
    Family("paddock", ("paddock",), "Assisted Tagging|Motorsport|Paddock"),
    # a rules.sponsor_keywords word read inside a vehicle box; off by default
    Family("sponsor", (), "Assisted Tagging|Motorsport|Sponsor", default_on=False),
)


def switch_key(key: str) -> str:
    return f"family_{key}"


def root_key(key: str) -> str:
    return f"family_{key}_root"


def family_tag(root: str, value: str) -> str:
    return f"{root}|{value}"


def root_problem(root) -> str:
    """Why `root` can't be a family root, or "" when it can."""
    if not isinstance(root, str) or not root.strip():
        return "is empty"
    if _BAD_ROOT.search(root):
        return 'can\'t contain , ; or "'
    if root != root.strip("| "):
        return "can't start or end with | or a space"
    return ""


def resolve(settings: dict) -> dict:
    """{family key: root} for each family switched on, in family order. Raises ValueError naming the
    setting for a root that can't be a tag path, and both settings when one on root equals or sits
    under another (a tag under both would belong to two families)."""
    roots = {}
    for fam in FAMILIES:
        if not settings[switch_key(fam.key)]:
            continue
        root = settings[root_key(fam.key)]
        why = root_problem(root)
        if why:
            raise ValueError(f"{root_key(fam.key)} {why}")
        for other, taken in roots.items():
            if root == taken or root.startswith(taken + "|") or taken.startswith(root + "|"):
                raise ValueError(f'{root_key(other)} ("{taken}") and {root_key(fam.key)} ("{root}") overlap; '
                                 f"each family needs its own root")
        roots[fam.key] = root
    return roots


def team_tags(entries: dict, roots: dict) -> list:
    """The distinct team tags of `entries`, in first-seen order; [] when the team family is off."""
    if "team" not in roots:
        return []
    return list(dict.fromkeys(family_tag(roots["team"], e.team) for e in entries.values() if e.team))

"""Collection kinds: what a collection tags, and which entry fields that kind accepts."""

DEFAULT_KIND = "motorsport"

KINDS = {
    "motorsport": frozenset({"id", "number", "team", "name", "co_driver", "extra", "make", "model", "tags", "camera", "colour", "car", "shows", "paddock", "plate"}),
    "people": frozenset({"id", "tags"}),
}

# Entry fields that deliberately have no tag family (the opt-out list). Every other field of a kind
# must be a source of a family in families.py; check_registries.py fails when one is neither, so a new
# entry key gets a family or is listed here with its reason.
NO_TAG_FAMILY = {
    "id": "the entry's key, not a property of the car",
    "tags": "the entry's own tags, already written as they are",
    "camera": "a hint for matching, not a tag",
    "car": "links two entries that share a car",
    "shows": "numbers the car may show, used for matching only",
    "colour": "a check value; the Colour family is read from the photo, not from the entry",
}


def check_kind(kind) -> str:
    """The kind itself; raises ValueError listing the valid kinds for anything else."""
    if not isinstance(kind, str) or kind not in KINDS:
        raise ValueError(f'unknown kind {kind!r} (kinds are {", ".join(KINDS)})')
    return kind


def check_entry_fields(kind: str, item: dict):
    """The first field of `item` that `kind` doesn't accept, or None."""
    unknown = sorted(set(item) - KINDS[kind])
    return unknown[0] if unknown else None

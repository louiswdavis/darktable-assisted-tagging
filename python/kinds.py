"""Collection kinds: what a collection tags, and which entry fields that kind accepts."""

DEFAULT_KIND = "motorsport"

KINDS = {
    "motorsport": frozenset({"id", "number", "team", "tags", "camera"}),
    "people": frozenset({"id", "tags"}),
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

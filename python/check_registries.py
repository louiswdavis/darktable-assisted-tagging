"""Bookkeeping checks that run anywhere with plain Python (no cv2, numpy or onnx):
- every constant of a module fingerprint.py lists is filed once in CACHE_INPUTS or
  CACHE_NEUTRAL, and nothing filed is missing (read from the source, nothing imported)
- every entry field has a tag family or is listed in kinds.NO_TAG_FAMILY
- lua/assisted_tagging.lua's PRESET_SCHEMA matches settings.SETTINGS_SCHEMA
  (settings.py is stdlib-only, so it is imported)
The same checks run in test_identify.py and test_settings.py; this catches them first.

Run with: python python/check_registries.py   (exit 1 and a list when something is off)"""

import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def parse(name: str) -> ast.Module:
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return ast.parse(f.read())


def module_constants(tree: ast.Module) -> list:
    """Top-level UPPER_CASE assignments, as test_identify.py collects them."""
    return [t.id for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign))
            for t in (node.targets if isinstance(node, ast.Assign) else [node.target])
            if isinstance(t, ast.Name) and t.id.lstrip("_").isupper() and t.id != "__all__"]


def filed_tables(tree: ast.Module) -> dict:
    """{"CACHE_INPUTS": {module: [names]}, "CACHE_NEUTRAL": {...}} from fingerprint.py."""
    tables = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            name = node.targets[0].id
            if name in ("CACHE_INPUTS", "CACHE_NEUTRAL"):
                tables[name] = {k.id: [e.value for e in v.elts] for k, v in zip(node.value.keys, node.value.values)}
    return tables


def fingerprint_problems() -> list:
    tables = filed_tables(parse("fingerprint.py"))
    out = []
    for mod in sorted(set(tables["CACHE_INPUTS"]) | set(tables["CACHE_NEUTRAL"])):
        names = module_constants(parse(mod + ".py"))
        filed = tables["CACHE_INPUTS"].get(mod, []) + tables["CACHE_NEUTRAL"].get(mod, [])
        out += [f"{mod}: {n} is filed {filed.count(n)} times in fingerprint.py, want 1"
                for n in sorted(set(names)) if filed.count(n) != 1]
        out += [f"{mod}: {n} is filed in fingerprint.py but doesn't exist" for n in sorted(set(filed) - set(names))]
    return out


def lua_value(text: str):
    text = text.strip()
    if text in ("true", "false"):
        return text == "true"
    if text.startswith('"'):
        return text[1:-1]
    return float(text) if "." in text else int(text)


def schema_problems() -> list:
    sys.path.insert(0, HERE)
    import settings
    with open(os.path.join(os.path.dirname(HERE), "lua", "assisted_tagging.lua"), encoding="utf-8") as f:
        found = re.search(r"M\.PRESET_SCHEMA = \{(.*?)\n\}", f.read(), re.S)
    if found is None:
        return ["lua: M.PRESET_SCHEMA block not found"]
    rows = re.findall(r'\{ key = "(\w+)", kind = "(\w+)"(?:, choices = \{([^}]*)\})?, default = ([^}]+) \}',
                      found.group(1))
    lua = {r[0]: (r[1], tuple(re.findall(r'"(\w+)"', r[2])), lua_value(r[3])) for r in rows}
    py = {s.key: (s.kind, s.choices, s.default) for s in settings.SETTINGS_SCHEMA}
    out = [f"schema: {k} is in settings.py but not lua PRESET_SCHEMA" for k in py if k not in lua]
    out += [f"schema: {k} is in lua PRESET_SCHEMA but not settings.py" for k in lua if k not in py]
    out += [f"schema: {k} differs (kind, choices, default): lua {lua[k]}, python {py[k]}"
            for k in py if k in lua and lua[k] != py[k]]
    if not out and list(lua) != list(py):
        out.append("schema: same keys, different order in lua and settings.py")
    return out


def shadow_problems() -> list:
    """Lines of assisted_tagging.lua that call the translate function `_` where a local or a loop
    variable named `_` hides it ("attempt to call a nil/table value" in darktable). A `local _` hides
    it up to the end of the file's indentation block, a `for _, ...` loop inside its body."""
    with open(os.path.join(os.path.dirname(HERE), "lua", "assisted_tagging.lua"), encoding="utf-8") as f:
        lines = f.read().split("\n")
    out = []
    for n, line in enumerate(lines):
        bound = re.match(r"(\s*)(local _\s*[,=]|for _\s*[,=])", line)
        if not bound:
            continue
        indent, is_loop = len(bound.group(1)), bound.group(2).startswith("for")
        for m in range(n + 1, len(lines)):
            body = lines[m]
            depth = len(body) - len(body.lstrip())
            if body.strip() and (depth < indent or (is_loop and depth == indent)):
                break
            if re.search(r"(?<![\w.])_\(", body):
                out.append(f"lua: line {m + 1} calls _() but line {n + 1} binds a variable named _")
    return out


def family_problems() -> list:
    """Entry fields of a kind that are neither a source of a tag family nor listed in kinds.NO_TAG_FAMILY,
    and opt-outs naming a field no kind has or one a family now covers."""
    sys.path.insert(0, HERE)
    from families import FAMILIES
    from kinds import KINDS, NO_TAG_FAMILY
    covered = {s for fam in FAMILIES for s in fam.sources}
    fields = set().union(*KINDS.values())
    out = [f'entry field "{f}" has no tag family: add a Family with it as a source in families.py (and the Lua mirror), '
           f"or list it in kinds.NO_TAG_FAMILY with a reason" for f in sorted(fields - covered - set(NO_TAG_FAMILY))]
    out += [f'kinds.NO_TAG_FAMILY lists "{f}", which no kind accepts' for f in sorted(set(NO_TAG_FAMILY) - fields)]
    out += [f'kinds.NO_TAG_FAMILY lists "{f}", but a family now uses it' for f in sorted(set(NO_TAG_FAMILY) & covered)]
    return out


if __name__ == "__main__":
    found = fingerprint_problems() + schema_problems() + shadow_problems() + family_problems()
    print("\n".join(found) if found else "registries ok")
    sys.exit(1 if found else 0)

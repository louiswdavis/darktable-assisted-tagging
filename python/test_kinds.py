# Run with: python python/test_kinds.py
# Exercises kinds.py; no models or files needed.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kinds as K

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


def error_of(fn, *args):
    try:
        fn(*args)
    except ValueError as e:
        return str(e)
    return ""


def run_tests():
    check("default kind", K.DEFAULT_KIND, "motorsport")
    check("check_kind: motorsport", K.check_kind("motorsport"), "motorsport")
    check("check_kind: people", K.check_kind("people"), "people")
    msg = error_of(K.check_kind, "faces")
    check("check_kind: unknown kind names both valid kinds", ("motorsport" in msg, "people" in msg), (True, True))
    item = {"id": "a", "tags": [], "number": "3"}
    check("people rejects number", K.check_entry_fields("people", item), "number")
    check("motorsport allows number", K.check_entry_fields("motorsport", item), None)
    check("people allows id and tags", K.check_entry_fields("people", {"id": "a", "tags": []}), None)
    check("motorsport rejects an unknown field", K.check_entry_fields("motorsport", {"id": "a", "face": 1}), "face")

    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

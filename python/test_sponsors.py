# Run with: python python/test_sponsors.py
# Exercises sponsors.py; no models or files needed.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sponsors as S

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


KW = (("petronas", "F1|Mercedes"), ("redbull", "F1|Red Bull"), ("oracle", "F1|Red Bull"), ("visa", "F1|RB"))


def run_tests():
    check("exact keyword", S.sponsor_prefixes([[0.99, "petronas"]], KW), ["F1|Mercedes"])
    check("one substitution on a long keyword", S.sponsor_prefixes([[0.99, "petronis"]], KW), ["F1|Mercedes"])
    check("one deletion on a long keyword", S.sponsor_prefixes([[0.99, "redbul"]], KW), ["F1|Red Bull"])
    check("one insertion on a long keyword", S.sponsor_prefixes([[0.99, "petronass"]], KW), ["F1|Mercedes"])
    check("two edits is too far", S.sponsor_prefixes([[0.99, "petrxnis"]], KW), [])
    check("a short keyword must match exactly", S.sponsor_prefixes([[0.99, "visx"]], KW), [])
    check("case is ignored", S.sponsor_prefixes([[0.99, "Oracle"]], KW), ["F1|Red Bull"])
    check("confidence under 0.90 is ignored", S.sponsor_prefixes([[0.89, "petronas"]], KW), [])
    check("two words of one team collapse", S.sponsor_prefixes([[0.99, "oracle"], [0.95, "redbull"]], KW), ["F1|Red Bull"])
    check("sponsors of two teams give no hint", S.sponsor_prefixes([[0.99, "oracle"], [0.99, "petronas"]], KW), [])
    check("no trace, no hint", S.sponsor_prefixes([], KW), [])

    print("")
    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

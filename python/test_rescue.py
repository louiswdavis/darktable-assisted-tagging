# Run with: python python/test_rescue.py
# Exercises rescue.py's candidate tracking; no models or files needed.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rescue as R

failures = 0


def check(name, got, want):
    global failures
    if got != want:
        failures += 1
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    else:
        print(f"ok   {name}")


MATE = (100, 100, 300, 160, 0.5, 2)  # 200 x 60


def run_tests():
    near = (130, 105, 330, 165, 0.15, 2)
    check("a nearby candidate of similar size tracks", R.track_candidate(MATE, [near]), 0)
    check("a far candidate doesn't", R.track_candidate(MATE, [(700, 100, 900, 160, 0.15, 2)]), None)
    check("a candidate of a very different size doesn't", R.track_candidate(MATE, [(110, 100, 150, 120, 0.15, 2)]), None)
    check("the highest-scoring tracking candidate wins", R.track_candidate(MATE, [near, (120, 100, 320, 160, 0.18, 2)]), 1)
    check("no candidates", R.track_candidate(MATE, []), None)
    check("a degenerate mate box tracks nothing", R.track_candidate((5, 5, 5, 9, 0.5, 2), [near]), None)

    def frame(boxes, cands):
        return {"boxes": boxes, "candidates": cands}

    burst = [("a", frame([list(MATE)], [])), ("b", frame([], [list(near)])), ("c", frame([list(MATE)], [])),
             ("d", frame([], []))]
    plan = R.plan_burst(burst)
    check("only the missed frame with a tracking candidate is planned", sorted(plan), ["b"])
    check("the nearest mate is used (a before c on a tie)", plan["b"][1], "a")
    check("a frame with no candidates isn't planned", "d" in plan, False)
    check("a burst with no vehicle anywhere plans nothing", R.plan_burst([("a", frame([], [list(near)]))]), {})
    check("an unanalysed frame is skipped", R.plan_burst([("a", None), ("b", frame([list(MATE)], []))]), {})

    if failures == 0:
        print("all tests passed")
        sys.exit(0)
    print(f"{failures} test(s) failed")
    sys.exit(1)


if __name__ == "__main__":
    run_tests()

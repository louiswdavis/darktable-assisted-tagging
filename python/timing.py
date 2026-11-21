"""Seconds and calls per model file, counted where each onnxruntime session runs (ticket 95, step 1).

A session wrapped by `timed` adds its `run` time to this process's totals. A worker hands its totals
to the parent with `take()` after each frame; the parent adds them with `merge()` and logs `report()`.
The wrapper forwards every other attribute, so callers keep using the session as before."""
import os
import time

_TOTALS: dict = {}  # model file name → [calls, seconds]


class TimedSession:
    def __init__(self, session, label: str):
        self._session, self._label = session, label

    def run(self, *args, **kwargs):
        start = time.perf_counter()
        try:
            return self._session.run(*args, **kwargs)
        finally:
            add(self._label, 1, time.perf_counter() - start)

    def __getattr__(self, name):
        return getattr(self._session, name)


def timed(session, path: str) -> TimedSession:
    """`session` whose `run` time is counted under the model file's name."""
    return TimedSession(session, os.path.basename(str(path)))


def add(label: str, calls: int, seconds: float):
    total = _TOTALS.setdefault(label, [0, 0.0])
    total[0] += calls
    total[1] += seconds


def take() -> dict:
    """This process's totals since the last `take`, then cleared: {model: [calls, seconds]}."""
    taken = {label: list(total) for label, total in _TOTALS.items()}
    _TOTALS.clear()
    return taken


def merge(totals: dict):
    """Adds a worker's `take()` result to this process's totals."""
    for label, (calls, seconds) in (totals or {}).items():
        add(label, calls, seconds)


def report(label: str = "model time") -> str:
    """One log line, slowest model first: `name seconds (calls, ms per call)`. Empty when nothing ran."""
    rows = sorted(_TOTALS.items(), key=lambda row: -row[1][1])
    return f"{label}: " + "; ".join(f"{name} {seconds:.0f}s ({calls} calls, {seconds * 1000 / calls:.0f} ms each)"
                                    for name, (calls, seconds) in rows) if rows else ""

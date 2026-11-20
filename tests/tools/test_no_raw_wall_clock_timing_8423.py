"""#8423: refuse new tests that judge elapsed wall-clock time via time.time() / time.perf_counter() / time.monotonic().

Loaded CI runners stall wall-clock timers and cause spurious red-main failures. New speed/linearity tests must use
the shared CPU-clock helper (or JVM ThreadMXBean CPU time for cobolrt) instead of raw wall-clock differences.
Existing offenders are listed in WALL_CLOCK_OFFENDERS (shrink-only: adding a new one or leaving a fixed one fails).
"""

from __future__ import annotations

import re
from pathlib import Path

from gitgalaxy.core.source_text import read_source

REPO = Path(__file__).resolve().parents[2]
TESTS = REPO / "tests"

WALL_CLOCKS = ("time", "perf_counter", "monotonic")
WALL_CLOCK_CALL = re.compile(r"\btime\.(?:time|perf_counter|monotonic)(?:_ns)?\(\)")
_MODULE_ALIAS = re.compile(r"^[ \t]*import[ \t]+time[ \t]+as[ \t]+(\w+)", re.M)
_FROM_IMPORT = re.compile(r"^[ \t]*from[ \t]+time[ \t]+import[ \t]+(.+)$", re.M)

# Not test assertions: the shared CPU-clock helper, CLI scripts that time subprocesses, golden fixtures.
SKIP_PREFIXES = ("tests/_timing.py", "tests/tools/", "tests/extraction/tools/", "tests/golden_master")


def wall_clock_calls(text: str) -> int:
    """Count raw wall-clock calls, resolving `import time as t` and `from time import perf_counter as pc`."""
    count = len(WALL_CLOCK_CALL.findall(text))
    for alias in _MODULE_ALIAS.findall(text):
        count += len(re.findall(rf"\b{re.escape(alias)}\.(?:time|perf_counter|monotonic)(?:_ns)?\(\)", text))
    for names in _FROM_IMPORT.findall(text):
        for part in names.replace("(", "").replace(")", "").split(","):
            bits = part.split("#")[0].split()
            if bits and bits[0] in WALL_CLOCKS:
                local = bits[-1]
                count += len(re.findall(rf"(?<![.\w]){re.escape(local)}(?:_ns)?\(\)", text))
    return count


# Existing test files that take >= 2 wall-clock timestamps (a difference) and have not been converted. Shrink-only (#8423).
WALL_CLOCK_OFFENDERS: frozenset[str] = frozenset()

# Tests where a wall clock is the right instrument, each with the reason. Not a backlog: a new entry needs a
# reason that CPU time of the calling thread cannot measure the thing.
WALL_CLOCK_ALLOWED: dict[str, str] = {
    "tests/security_auditing/test_redos_poison.py": (
        "a supervisor watching spawned worker processes for a hang or a stall: the work runs in other processes, "
        "so the parent's CPU time says nothing about it, and the 10 s / 120 s limits sit far above any honest run"
    ),
}


def _find_wall_clock_diff_tests() -> set[str]:
    found: set[str] = set()
    for path in TESTS.rglob("*.py"):
        rel = path.relative_to(REPO).as_posix()
        if path == Path(__file__).resolve() or rel.startswith(SKIP_PREFIXES):
            continue
        if wall_clock_calls(read_source(path).text) >= 2:
            found.add(rel)
    return found


def test_no_new_raw_wall_clock_timing_tests():
    actual = _find_wall_clock_diff_tests()
    unexpected = sorted(actual - WALL_CLOCK_OFFENDERS - set(WALL_CLOCK_ALLOWED))
    if unexpected:
        raise AssertionError(
            "New test(s) take wall-clock time differences (use CPU time / shared helper instead, #8423):\n"
            + "\n".join(f"  - {p}" for p in unexpected)
        )
    stale = sorted((WALL_CLOCK_OFFENDERS | set(WALL_CLOCK_ALLOWED)) - actual)
    if stale:
        raise AssertionError(
            "Fixed/removed wall-clock offender(s) still listed in WALL_CLOCK_OFFENDERS (shrink the list, #8423):\n"
            + "\n".join(f"  - {p}" for p in stale)
        )


def test_every_allowed_wall_clock_test_states_a_reason():
    assert not set(WALL_CLOCK_ALLOWED) & WALL_CLOCK_OFFENDERS
    for path, reason in WALL_CLOCK_ALLOWED.items():
        assert len(reason.split()) >= 8, f"{path}: say why CPU time cannot measure this (#8423)"

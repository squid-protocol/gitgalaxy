"""The shared CPU-clock helper (#8423): fastest-of-N, retry only after an over-limit run, one stated ReDoS limit."""

import sys
from pathlib import Path

_TESTS = str(Path(__file__).resolve().parents[1])
if _TESTS not in sys.path:
    sys.path.insert(0, _TESTS)

from _timing import REDOS_LIMIT_S, best_cpu_seconds, cpu_best_of  # noqa: E402


def _clock(costs):
    """A fake clock: each run of the work advances it by the next cost."""
    state = {"t": 0.0, "i": 0, "start": True}

    def clock():
        if state["start"]:
            state["start"] = False
            return state["t"]
        state["start"] = True
        state["t"] += costs[state["i"]]
        state["i"] += 1
        return state["t"]

    return clock, state


def test_best_cpu_seconds_takes_the_fastest_run():
    clock, _ = _clock([0.9, 0.2, 0.5])
    assert abs(best_cpu_seconds(lambda: None, 3, clock=clock) - 0.2) < 1e-9


def test_a_passing_first_run_is_not_repeated():
    clock, state = _clock([0.1, 5.0, 5.0])
    assert cpu_best_of(lambda: None, REDOS_LIMIT_S, clock=clock) == 0.1
    assert state["i"] == 1


def test_a_stalled_first_run_is_retried_and_the_fastest_wins():
    clock, state = _clock([3.0, 0.4, 0.2])
    assert abs(cpu_best_of(lambda: None, REDOS_LIMIT_S, clock=clock) - 0.4) < 1e-9
    assert state["i"] == 2


def test_a_run_slow_every_time_stays_over_the_limit():
    clock, state = _clock([3.0, 2.0, 4.0])
    assert cpu_best_of(lambda: None, REDOS_LIMIT_S, clock=clock) == 2.0
    assert state["i"] == 3


def test_the_redos_harnesses_take_their_default_limit_from_the_helper():
    import inspect

    langs = str(Path(__file__).resolve().parents[1] / "extraction" / "languages")
    ext = str(Path(__file__).resolve().parents[1] / "extraction")
    for d in (langs, ext):
        if d not in sys.path:
            sys.path.insert(0, d)
    import _extraction_harness
    import _strict_harness

    for mod in (_strict_harness, _extraction_harness):
        assert inspect.signature(mod.assert_redos_immune).parameters["timeout_sec"].default == REDOS_LIMIT_S

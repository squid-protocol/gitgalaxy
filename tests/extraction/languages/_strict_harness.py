"""
Shared ReDoS-testing harness for tests/extraction/languages/test_<lang>_strict.py.

Moved verbatim out of the top of tests/core_engine/test_language_standards_strict.py
when that file was split into one file per language, then colocated here
alongside the extraction gauntlets' own _extraction_harness.py (whose role
this mirrors, one per test concern rather than shared, to keep each
concern's helpers independently auditable).
"""

import multiprocessing
import re
import time


# ==============================================================================
# THE BLAST CHAMBER (ReDoS Detonator)
# ==============================================================================
def _detonate(pattern: re.Pattern, payload: str, result_queue: multiprocessing.Queue):
    """
    Executes a regex against a payload inside an isolated OS process.
    Passes the duration back via a multiprocessing Queue.
    """
    start = time.perf_counter()
    list(pattern.finditer(payload))
    result_queue.put(time.perf_counter() - start)


def assert_redos_immune(pattern: re.Pattern, payload: str, timeout_sec: float = 1.0):
    """
    Runs a regex in an isolated process. If it exceeds timeout_sec, it is
    flagged as a Catastrophic Backtracking (ReDoS) vulnerability, and the
    OS process is violently terminated to prevent pytest from hanging.
    """
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()

    p = ctx.Process(target=_detonate, args=(pattern, payload, result_queue))
    p.start()
    p.join(timeout_sec)

    if p.is_alive():
        # THE FIX: Violently kill the OS process so it doesn't trap pytest's atexit handler
        p.terminate()
        p.join()  # Reap the zombie process instantly
        raise AssertionError(f"🔥 ReDoS TRIGGERED! Regex hung on payload:\n{payload}\nRegex: {pattern.pattern}")

    if not result_queue.empty():
        duration = result_queue.get()
        assert duration < timeout_sec, f"Regex took too long: {duration:.4f}s"


def _best_of_timing(pattern: re.Pattern, payload: str, trials: int = 5) -> float:
    """
    Times a single in-process `.search()` call, taking the minimum of
    several trials to filter out one-off OS scheduling noise (e.g. a
    preceding subprocess-based ReDoS test leaving a scheduling hiccup on
    the very next timing measurement). Used for scale-relative ReDoS
    sanity checks, which compare a ratio between two sizes rather than
    asserting an absolute wall-clock threshold -- absolute thresholds are
    flaky across CI hardware of varying speed.

    trials defaults to 5 (raised from 3, #713): a real CI failure on a
    contended macOS/Python-3.9 smoke-test runner measured a genuinely
    quadratic pattern's ratio at 2.49x -- just under the (also lowered,
    see the ratio callers) 2.5 threshold -- purely from timing noise
    under heavy parallel load. More trials tightens the min-of-N
    distribution further without changing what's being proven.
    """
    best = float("inf")
    for _ in range(trials):
        start = time.perf_counter()
        pattern.search(payload)
        best = min(best, time.perf_counter() - start)
    return best

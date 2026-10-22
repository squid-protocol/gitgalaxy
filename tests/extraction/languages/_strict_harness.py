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
def _plain(pattern: re.Pattern) -> re.Pattern:
    """A real compiled pattern for `pattern` (#3914: registry rules are `LazyPattern`s). A
    LazyPattern unpickles through gitgalaxy's language registry, so a spawned child would import
    all of it (~1.6 s) inside the ReDoS timeout and be read as hung; a plain pattern unpickles
    through `re` alone. Compiling here, in the parent, also keeps compilation out of any timing."""
    if isinstance(pattern, re.Pattern) or not hasattr(pattern, "pattern"):
        return pattern  # a real pattern, or a disabled rule (None) the sweeps pass through as they always did
    return re.compile(pattern.pattern, pattern.flags)


def _hang_cap(timeout_sec: float) -> float:
    """Wall-clock seconds to wait before declaring the child hung and killing it (#4477).

    The property under test is the regex's CPU time (`_detonate` measures it in the child and the caller bounds
    it by `timeout_sec`); wall time is only the kill switch for a truly non-terminating pattern, so it sits an
    order of magnitude above the CPU bound: a loaded CI runner stretches a 0.09 s call past 1 s of wall time,
    while a catastrophic pattern runs for minutes to years."""
    return max(10.0, timeout_sec * 10)


def _detonate(pattern: re.Pattern, payload: str, result_queue: multiprocessing.Queue, started=None):
    """
    Executes a regex against a payload inside an isolated OS process.
    Passes the duration back via a multiprocessing Queue.
    """
    if started is not None:
        started.set()  # the parent's clock starts here, not at spawn (slow on Windows, #4494)
    start = time.thread_time()  # CPU time of the child, not wall time (#4477)
    list(pattern.finditer(payload))
    result_queue.put(time.thread_time() - start)


# One spawned child per test process, reused: a call sends (pattern, payload) down a pipe and the child answers with the
# regex's CPU seconds, measured as _detonate measures them. A fresh interpreter per call (~0.3-1 s on a runner) was most
# of these tests' time (Smoke Tests: the language contracts' *_rules_are_redos_immune alone, 16 files, ~22% of the suite).
# A regex past the hang cap kills the child (and fails, as before); the next call starts another.
_CHAMBER: list = []  # [(process, connection)] while one is up


def _chamber_loop(conn, started):
    started.set()
    while True:
        try:
            pattern, payload = conn.recv()
        except EOFError:
            return
        start = time.thread_time()  # CPU time of the child, not wall time (#4477)
        list(pattern.finditer(payload))
        conn.send(time.thread_time() - start)


def _chamber():
    if _CHAMBER and _CHAMBER[0][0].is_alive():
        return _CHAMBER[0]
    _discard()
    ctx = multiprocessing.get_context("spawn")
    conn, child = ctx.Pipe()
    started = ctx.Event()
    p = ctx.Process(target=_chamber_loop, args=(child, started), daemon=True)
    p.start()
    child.close()
    # The timeout bounds the regex, not interpreter start-up: a spawned child on a loaded Windows runner
    # can take over a second before it runs anything (#4494).
    assert started.wait(60), "the ReDoS child process never started"
    _CHAMBER[:] = [(p, conn)]
    return p, conn


def _discard():
    if _CHAMBER:
        p, conn = _CHAMBER.pop()
        if p.is_alive():
            p.terminate()  # Violently kill the OS process so it doesn't trap pytest's atexit handler
        p.join()  # Reap the zombie process instantly
        conn.close()


def assert_redos_immune(pattern: re.Pattern, payload: str, timeout_sec: float = 1.0):
    """
    Runs a regex in an isolated process. If it exceeds timeout_sec, it is
    flagged as a Catastrophic Backtracking (ReDoS) vulnerability, and the
    OS process is violently terminated to prevent pytest from hanging.
    """
    plain = _plain(pattern)
    if plain is None:  # a disabled rule: nothing to detonate (its one-shot child died with nothing to report)
        return
    _, conn = _chamber()
    conn.send((plain, payload))
    if not conn.poll(_hang_cap(timeout_sec)):
        _discard()
        raise AssertionError(f"🔥 ReDoS TRIGGERED! Regex hung on payload:\n{payload}\nRegex: {pattern.pattern}")
    try:
        duration = conn.recv()
    except EOFError:  # the child died on it (a MemoryError ...): the one-shot child reported nothing either
        _discard()
        return
    assert duration < timeout_sec, f"Regex took too long: {duration:.4f}s"


def _detonate_all(jobs: list, conn, started=None):
    """`_detonate` over a list of (pattern, payload), one duration per job, in order (#5166).
    The durations go down a Pipe, not a Queue: a Queue's feeder thread cannot flush while the next
    job's regex holds the GIL, so an earlier result would be stuck behind a later hang."""
    if started is not None:
        started.set()
    for pattern, payload in jobs:
        start = time.thread_time()
        list(pattern.finditer(payload))
        conn.send(time.thread_time() - start)


def assert_redos_immune_all(pairs, timeout_sec: float = 1.0):
    """`assert_redos_immune` for many (pattern, payload) pairs in ONE isolated process (#5166).

    A sweep of N pairs paid N interpreter spawns, which was most of its time. Every pair is still
    timed on the child's own CPU clock and bounded by `timeout_sec`; a pair that does not finish
    within the hang cap kills the child and fails naming that pair's payload and regex."""
    pairs = [(pat, payload) for pat, payload in pairs if pat is not None]  # a disabled rule has nothing to detonate
    if not pairs:
        return
    ctx = multiprocessing.get_context("spawn")
    receiver, sender = ctx.Pipe(duplex=False)
    started = ctx.Event()
    p = ctx.Process(target=_detonate_all, args=([(_plain(pat), payload) for pat, payload in pairs], sender, started))
    p.start()
    sender.close()  # the child holds the only write end, so its death reads as EOF below
    try:
        assert started.wait(60), "the ReDoS child process never started"
        for pattern, payload in pairs:
            if not receiver.poll(_hang_cap(timeout_sec)):
                p.terminate()
                raise AssertionError(f"🔥 ReDoS TRIGGERED! Regex hung on payload:\n{payload}\nRegex: {pattern.pattern}")
            try:
                duration = receiver.recv()
            except EOFError:
                raise AssertionError(
                    f"the ReDoS child died on payload {payload[:60]!r} for {pattern.pattern}"
                ) from None
            assert duration < timeout_sec, (
                f"Regex took too long: {duration:.4f}s on payload {payload[:60]!r} for {pattern.pattern}"
            )
    finally:
        if p.is_alive():
            p.terminate()
        p.join()


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
    pattern = _plain(pattern)  # compiled before the clock starts
    best = float("inf")
    for _ in range(trials):
        start = time.thread_time()
        pattern.search(payload)
        best = min(best, time.thread_time() - start)
    return best

import multiprocessing as mp
import os
import queue
import re
import time
import unittest

import pytest

# Adjust these imports to match your project structure
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# ==============================================================================
# THE TOXIC ARSENAL (Classic ReDoS Vectors)
# ==============================================================================
EVIL_STRINGS = [
    "a" * 100 + "!",  # Standard overlapping repetition trap
    " " * 500 + "a",  # Trailing whitespace backtracking
    "((((((((((((((((((((((((((((((",  # Unclosed group avalanche
    '"\\' * 50 + '"',  # Escaped quote hell (String literal traps)
    "/*" + "*" * 500 + "/",  # Runaway block comments
    "<?php" + " " * 500 + "?>",  # Unbounded lookaheads
    "{" + "{\n" * 100 + "}",  # Recursive brace/scope depth
    "import " + "a." * 100 + "b",  # Pathological dot-notation chaining
    "class " + "A" * 100 + " extends " + "B" * 100,  # Inheritance declaration bloat
]

# ... [Keep Part 1: TestReDoSPoisoning exactly as it is] ...

# ==============================================================================
# PART 2: PRODUCTION REGEX FUZZER (Optimized Hybrid Engine)
# ==============================================================================
HANG_SECONDS = 10.0  # one regex over every payload: a real one takes microseconds
STALL_SECONDS = 120.0  # no message at all (workers still importing, or wedged)


def _fuzz_chunk(tasks_chunk, status_queue):
    """
    Worker process. Evaluates a massive chunk of regexes instantly.
    Reports START and DONE. If it hits ReDoS, it hangs and never reports DONE.
    """
    for lang, rule_name, pattern_str, flags in tasks_chunk:
        status_queue.put((lang, rule_name, "START"))
        try:
            compiled = re.compile(pattern_str, flags)
            for payload in EVIL_STRINGS:
                list(compiled.finditer(payload))
        except Exception:
            pass  # Compilation errors are caught by the Syntax Integrity test
        status_queue.put((lang, rule_name, "DONE"))  # finished either way: only a hang never reports


def _fuzz(tasks, hang_seconds=HANG_SECONDS, num_workers=None):
    """Run every (lang, rule, pattern, flags) task over EVIL_STRINGS in spawned workers.
    Returns (hung task or None, tasks completed, stalled)."""
    num_workers = num_workers or min(8, os.cpu_count() or 4)
    chunks = [tasks[i::num_workers] for i in range(num_workers)]
    # 'spawn' avoids the OS fork() deadlock warning in the pytest logs
    ctx = mp.get_context("spawn")
    manager = ctx.Manager()
    status_queue = manager.Queue()
    workers = []
    for chunk in chunks:
        if chunk:
            p = ctx.Process(target=_fuzz_chunk, args=(chunk, status_queue))
            p.start()
            workers.append(p)

    # The kill-switch monitor. A well-written regex runs these payloads in well under a
    # millisecond; a catastrophic one (exponential backtracking) never finishes. So a regex is
    # flagged only once it has run for `hang_seconds` -- a bound no real regex approaches, and one
    # CPU contention cannot fake. #3913: this used to flag any 0.25 s of queue silence, which a
    # busy 4-core runner (8 spawned fuzzers, each importing the registry, beside 3 other xdist
    # workers) produced by itself: it blamed a different innocent regex each run (dart, then cpp
    # func_start). The same rule let the test pass having checked nothing when no worker had
    # started within 0.25 s.
    started: dict[str, float] = {}  # task -> when its START arrived
    completed = 0
    vulnerable = None
    stalled = False
    last_progress = time.monotonic()
    try:
        while completed < len(tasks):
            try:
                lang, rule, status = status_queue.get(timeout=0.5)
            except queue.Empty:
                if not any(p.is_alive() for p in workers) or time.monotonic() - last_progress > STALL_SECONDS:
                    stalled = True
                    break
            else:
                task_id = f"{lang}::{rule}"
                last_progress = time.monotonic()
                if status == "START":
                    started[task_id] = last_progress
                elif status == "DONE":
                    started.pop(task_id, None)
                    completed += 1
            now = time.monotonic()
            stuck = sorted(t for t, at in started.items() if now - at > hang_seconds)
            if stuck:
                vulnerable = stuck[0]
                break
    finally:  # the hard kill-switch: never leave a fuzzer spinning
        for p in workers:
            if p.is_alive():
                p.terminate()
            p.join()
        manager.shutdown()
    return vulnerable, completed, stalled


class TestProductionRegexSecurity:
    def test_production_regex_redos_immunity(self):
        """
        Extracts every single regex from the production standards and blasts them
        with ReDoS payloads, in spawned worker processes.
        """
        tasks = []
        for lang, config in LANGUAGE_DEFINITIONS.items():
            for rule_name, pattern in config.get("rules", {}).items():
                if pattern and hasattr(pattern, "pattern"):
                    tasks.append((lang, rule_name, pattern.pattern, pattern.flags))
        assert len(tasks) > 1000

        vulnerable, completed, stalled = _fuzz(tasks)
        if vulnerable:
            pytest.fail(f"🔥 SECURITY BREACH: ReDoS vulnerability detected! Regex hung on:\n{vulnerable}")
        assert not stalled, f"fuzzer made no progress: {completed}/{len(tasks)} regexes checked"
        assert completed == len(tasks)  # never a pass that checked nothing

    def test_the_kill_switch_still_catches_a_catastrophic_regex(self):
        """#3913: the per-regex bound replaced a 0.25 s silence rule -- prove it is not blind."""
        tasks = [("probe", "safe", r"a+!", 0), ("probe", "evil", r"^(a+)+$", 0)]
        vulnerable, completed, _ = _fuzz(tasks, hang_seconds=3.0, num_workers=2)
        assert vulnerable == "probe::evil"
        assert completed == 1


if __name__ == "__main__":
    unittest.main()

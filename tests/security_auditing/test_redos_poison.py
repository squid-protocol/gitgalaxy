import multiprocessing as mp
import os
import queue
import re
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
            status_queue.put((lang, rule_name, "DONE"))
        except Exception:
            pass  # Compilation errors are caught by the Syntax Integrity test


class TestProductionRegexSecurity:
    def test_production_regex_redos_immunity(self):
        """
        Extracts every single regex from the production standards and blasts them
        with ReDoS payloads. Uses an 8-core isolated multiprocessing pool to
        reduce overhead from 80 seconds down to ~0.5 seconds.
        """
        # 1. Gather all compiled patterns
        tasks = []
        for lang, config in LANGUAGE_DEFINITIONS.items():
            for rule_name, pattern in config.get("rules", {}).items():
                if pattern and hasattr(pattern, "pattern"):
                    tasks.append((lang, rule_name, pattern.pattern, pattern.flags))

        # 2. Divide the 1,200+ regexes into efficient chunks
        num_workers = min(8, os.cpu_count() or 4)
        chunks = [tasks[i::num_workers] for i in range(num_workers)]

        # 3. Use 'spawn' to fix the OS fork() deadlock warning in the Pytest logs
        ctx = mp.get_context("spawn")
        manager = ctx.Manager()
        status_queue = manager.Queue()

        # 4. Ignite the workers
        workers = []
        for chunk in chunks:
            if not chunk:
                continue
            p = ctx.Process(target=_fuzz_chunk, args=(chunk, status_queue))
            p.start()
            workers.append(p)

        active_tasks = set()
        completed_tasks = 0
        vulnerable = None

        # 5. The Kill-Switch Monitor
        # A well-written regex processes a 100-char string in 0.0001 seconds.
        # If the queue is silent for 0.25s, a worker is stuck in an infinite ReDoS loop.
        while completed_tasks < len(tasks):
            try:
                lang, rule, status = status_queue.get(timeout=0.25)
                task_id = f"{lang}::{rule}"

                if status == "START":
                    active_tasks.add(task_id)
                elif status == "DONE":
                    active_tasks.discard(task_id)
                    completed_tasks += 1
            except queue.Empty:
                if active_tasks:
                    vulnerable = list(active_tasks)[0]
                break

        # 6. Execute the hard kill-switch to prevent the test suite from hanging
        for p in workers:
            if p.is_alive():
                p.terminate()
            p.join()

        if vulnerable:
            pytest.fail(f"🔥 SECURITY BREACH: ReDoS vulnerability detected! Regex hung on:\n{vulnerable}")


if __name__ == "__main__":
    unittest.main()

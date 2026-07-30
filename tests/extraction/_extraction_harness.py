"""
Shared assertion helpers for the per-language extraction test files under
tests/extraction/languages/. See tests/extraction/how_to_harden_extraction.md
for the methodology these support.

Each per-language file owns its own case dicts and thin
pytest.mark.parametrize-decorated test functions; this module holds only the
common valid/invalid/pathological assertion logic (lifted from the four
original monolithic gauntlets: test_function_extraction_strict.py,
test_args_extraction_strict.py, test_class_extraction_strict.py,
test_dependency_extraction_strict.py) so it isn't duplicated four times per
language.

Per-language files should import this module via a `sys.path` insertion of
this file's own directory (see any tests/extraction/languages/test_*.py for
the exact pattern), not via a `tests.extraction._extraction_harness`-style
dotted import -- this repo's `tests/` tree has no `__init__.py` files, so a
dotted import only works by accident locally (e.g. `python -m pytest` from
the repo root happens to put the root on `sys.path`) and fails in CI, which
invokes the `pytest` console script directly.
"""

import multiprocessing
import re
import time


def _detonate(pattern: re.Pattern, payload: str, result_queue: "multiprocessing.Queue"):
    """Executes a regex against a payload inside an isolated OS process."""
    start = time.perf_counter()
    list(pattern.finditer(payload))
    result_queue.put(time.perf_counter() - start)


def assert_redos_immune(pattern: re.Pattern, payload: str, timeout_sec: float = 1.0):
    """
    Runs a regex in an isolated process; if it exceeds timeout_sec, flags it
    as a Catastrophic Backtracking (ReDoS) vulnerability and violently
    terminates the OS process so pytest doesn't hang. Identical to (and
    duplicated from, deliberately, to avoid a cross-test-module import)
    tests/core_engine/test_language_standards_strict.py's own helper of the
    same name.
    """
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()

    p = ctx.Process(target=_detonate, args=(pattern, payload, result_queue))
    p.start()
    p.join(timeout_sec)

    if p.is_alive():
        p.terminate()
        p.join()
        raise AssertionError(f"🔥 ReDoS TRIGGERED! Regex hung on payload:\n{payload}\nRegex: {pattern.pattern}")

    if not result_queue.empty():
        duration = result_queue.get()
        assert duration < timeout_sec, f"Regex took too long: {duration:.4f}s"


def assert_valid_match(pattern, payload, expected_name, label):
    """
    Positive case: the payload MUST match, and -- if a capture group exists --
    the expected name must appear among the non-None captured groups (not just
    the whole match, which would include dirty modifiers/return types).
    Patterns with no capture group are checked via substring on the whole
    match instead.
    """
    match = pattern.search(payload)
    assert match is not None, f"[{label}] Iron Wall Blocked Valid Case: {payload!r}"

    if expected_name is None:
        return

    if pattern.groups > 0:
        captured = [g for g in match.groups() if g is not None]
        assert captured, f"[{label}] Matched but captured nothing: {payload!r}"
        assert any(expected_name in g for g in captured), (
            f"[{label}] Captured {captured!r} instead of clean target {expected_name!r} from {payload!r}"
        )
    else:
        assert expected_name in match.group(0), (
            f"[{label}] Matched string {match.group(0)!r} failed to contain target {expected_name!r}"
        )


def assert_invalid_no_match(pattern, payload, label):
    """Negative case: a structural lookalike MUST NOT match at all."""
    match = pattern.search(payload)
    if match is not None:
        raise AssertionError(
            f"[{label}] Ghost hallucinated a match on lookalike: {payload!r} (matched {match.group(0)!r})"
        )


def assert_pathological_match(pattern, payload, expected_name, label):
    """
    Adversarial case: same assertion shape as assert_valid_match, but kept as
    a separate function so pathological-tier failures get their own message
    (this is a ReDoS/vertical-formatting survival proof, not a baseline
    correctness proof, even though the check is identical).
    """
    match = pattern.search(payload)
    assert match is not None, f"[{label}] Engine choked on pathological formatting: {payload!r}"

    if expected_name is None:
        return

    if pattern.groups > 0:
        captured = [g for g in match.groups() if g is not None]
        assert captured, f"[{label}] Matched but captured nothing: {payload!r}"
        assert any(expected_name in g for g in captured), (
            f"[{label}] Captured {captured!r} instead of clean target {expected_name!r} from {payload!r}"
        )
    else:
        assert expected_name in match.group(0), (
            f"[{label}] Matched string {match.group(0)!r} failed to contain target {expected_name!r}"
        )


def assert_valid_dependency_match(pattern, payload, expected_path, label):
    """
    _dependency_capture's positive case is stricter than the other three
    rules: it MUST use a capture group (there's no "whole match" fallback,
    since the whole match usually includes the import/require keyword itself,
    not just the clean path) and the expected path must appear in one of the
    non-None groups (some languages use alternate groups for import vs.
    require-style syntax).
    """
    match = pattern.search(payload)
    assert match is not None, f"[{label}] Iron Wall Blocked Valid Import: {payload!r}"

    if pattern.groups == 0:
        raise AssertionError(f"[{label}] _dependency_capture MUST use a capture group to isolate the path!")

    captured = [g for g in match.groups() if g is not None]
    assert captured, f"[{label}] Matched but captured nothing: {payload!r}"
    assert any(expected_path in g for g in captured), (
        f"[{label}] Captured {captured!r} instead of clean path {expected_path!r} from {payload!r}"
    )


def assert_pathological_dependency_match(pattern, payload, expected_path, label):
    """Pathological-tier counterpart to assert_valid_dependency_match."""
    match = pattern.search(payload)
    assert match is not None, f"[{label}] Engine choked on pathological import formatting: {payload!r}"

    if pattern.groups == 0:
        raise AssertionError(f"[{label}] _dependency_capture MUST use a capture group to isolate the path!")

    captured = [g for g in match.groups() if g is not None]
    assert captured, f"[{label}] Matched but captured nothing: {payload!r}"
    assert any(expected_path in g for g in captured), (
        f"[{label}] Captured {captured!r} instead of clean path {expected_path!r} from {payload!r}"
    )

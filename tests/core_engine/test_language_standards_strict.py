"""
Global / genuinely cross-language structural-signature tests.

Per-language strict structural-signature coverage lives in
tests/extraction/languages/test_<lang>_strict.py (one file per language,
colocated with the extraction gauntlets' own test_<lang>.py files -- the
`_strict` suffix keeps the basenames from colliding under pytest's default
import mode, since this repo has no tests/__init__.py anywhere). This file
keeps only what doesn't belong to any single language: registry-wide sanity
checks, the ReDoS test-harness's own self-tests, and the one test explicitly
written (issue #713) as a single parametrized cross-language test rather
than duplicated per language.
"""

import sys
from pathlib import Path

import pytest
import re

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent.parent / "extraction" / "languages")
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune, _best_of_timing  # noqa: E402 # type: ignore


# ==============================================================================
# TEST 6: THE THERMODYNAMIC BALANCE COLLISIONS
# Proving that operators don't cannibalize each other across rules.
# ==============================================================================
def test_thermodynamic_operator_collisions():
    """
    Proves that common language operators (<<, |, &, !) do not trigger false
    positives in the wrong metric categories.
    """
    # 1. C++ Bitwise vs. I/O Streams
    cpp_bitwise = LANGUAGE_DEFINITIONS["cpp"]["rules"]["bitwise_ops"]
    assert len(list(cpp_bitwise.finditer("std::cout << 'Hello'"))) == 0, "C++ bitwise tripped on a cout stream!"
    assert len(list(cpp_bitwise.finditer("x <<= 1;"))) == 1, "C++ bitwise failed to catch explicit shift assignment!"

    # 2. Rust Closures vs. Bitwise
    rust_bitwise = LANGUAGE_DEFINITIONS["rust"]["rules"]["bitwise_ops"]
    assert len(list(rust_bitwise.finditer("let x = |a| a + 1;"))) == 0, "Rust bitwise tripped on a closure!"
    assert len(list(rust_bitwise.finditer("a ^ b"))) == 1, "Rust bitwise failed to catch XOR!"

    # 3. TypeScript Test Assertions vs. Object Methods
    ts_test = LANGUAGE_DEFINITIONS["typescript"]["rules"]["test"]
    assert len(list(ts_test.finditer("myRegex.test('string')"))) == 0, "TS test metric tripped on a regex.test() call!"
    assert len(list(ts_test.finditer("test('should work', () => {"))) == 1, "TS test metric missed a real test block!"


# ==============================================================================
# TEST 7: THE GLOBAL FUZZER (The Safety Net)
# ==============================================================================
def test_global_regex_syntax_integrity():
    """
    A final sanity check. Iterates over EVERY regex in the entire file and
    verifies it compiles correctly without throwing a re.error.
    """
    failed = []

    for lang, config in LANGUAGE_DEFINITIONS.items():
        rules = config.get("rules", {})
        for rule_name, pattern in rules.items():
            if pattern is not None:
                try:
                    # Accessing .pattern proves it's a valid compiled regex object
                    _ = pattern.pattern
                except Exception as e:
                    failed.append(f"{lang}::{rule_name} -> {e}")

    assert not failed, f"Found {len(failed)} uncompiled or broken regexes in production schema:\n" + "\n".join(failed)


# ==============================================================================
# TEST 8: TEST HARNESS EXCEPTION CATCHING (Coverage Completion)
# ==============================================================================
def test_redos_detonator_timeout_catch():
    """Proves the Blast Chamber successfully catches and kills hung regexes."""
    # A classic catastrophic backtracking regex: (a+)+$
    # Constructed dynamically to blind CodeQL from flagging the intentional trap
    evil_pattern = "(" + "a+" + ")+$"
    evil_regex = re.compile(evil_pattern)
    poison_payload = "a" * 30 + "b"

    # We now catch the standard AssertionError we just updated
    with pytest.raises(AssertionError) as exc_info:
        assert_redos_immune(evil_regex, poison_payload, timeout_sec=0.1)

    assert "ReDoS TRIGGERED" in str(exc_info.value)


def test_global_regex_syntax_integrity_catch(monkeypatch):
    """Proves the fuzzer catches malformed regex objects."""
    import sys

    # Inject a fake broken regex to trigger the exception block
    fake_defs = {"fake_lang": {"rules": {"broken_rule": "This is a string, not a compiled regex object!"}}}

    # Patch the locally imported variable inside THIS file's namespace!
    monkeypatch.setattr(sys.modules[__name__], "LANGUAGE_DEFINITIONS", fake_defs)

    with pytest.raises(AssertionError) as exc_info:
        test_global_regex_syntax_integrity()

    assert "Found 1 uncompiled or broken regexes" in str(exc_info.value)


# ==============================================================================
# CROSS-LANGUAGE SWEEP: spec_exposure ADJACENT-QUANTIFIER ReDoS (Issue #713)
# ==============================================================================
# Found while closing #584 (groovy strict-parsing tests): the `spec_exposure`
# signature's `\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]` shape (or close
# per-language variants) was copy-pasted across the majority of
# LANGUAGE_DEFINITIONS entries, and most copies still carried the unbounded
# `[^\]]*` immediately after the equally-unbounded `\d+` -- the classic
# adjacent-overlapping-quantifier shape (digits satisfy both character
# classes, so an unclosed "[SPEC-11111..." tag with no closing "]" forces
# the engine to re-scan an ever-shrinking digit suffix at every possible
# split point between the two quantifiers, O(n^2)).
#
# This exact bug class had already been found and fixed independently,
# one language at a time, throughout this epic (embedded_python, css, tcl,
# matlab, scheme, typescript, rust, c, cpp, csharp, groovy, shell, sqlite)
# -- #713 is the systemic sweep catching every language that slipped
# through those one-off passes. Rather than scatter 17 near-identical
# regression tests across each language's own (already large) strict-
# parsing section, this is the single dedicated cross-language test the
# issue itself explicitly authorizes as the "cleaner" alternative.
#
# Fix: bound `\d+` to `\d{1,10}` and `[^\]]*` to `[^\]]{0,300}` -- the
# exact same clamp already proven correct for shell/sqlite/groovy/etc
# earlier in this epic. Generous enough for any realistic spec/audit tag,
# only removing the pathological-input hang.
_SPEC_EXPOSURE_REDOS_SWEEP_TARGETS = [
    # (language, old vulnerable pattern text before this fix, extra correctness spot-check)
    ("python", r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", None),
    ("javascript", r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", None),
    ("java", r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", None),
    ("go", r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", None),
    ("php", r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", None),
    ("ruby", r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", None),
    ("swift", r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", None),
    ("kotlin", r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", None),
    ("html", r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit|RFC|W3C|CERN|TBL)[^\]]*\]", "[RFC 2616]"),
    ("assembly", r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit|rfc)[^\]]*\]", "[rfc]"),
    ("perl", r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", None),
    (
        "dart",
        r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit|RFC|W3C|CERN|TBL|ENQUIRE)[^\]]*\]|\b(?:Tim\s+Berners-Lee|WorldWideWeb|HyperText\s+Proposal)\b",
        "[ENQUIRE]",
    ),
    (
        "dockerfile",
        r"\[(?:[ \t]*SPEC[ \t]*-[ \t]*\d+|spec|audit|CVE-\d{4}-\d+)[^\]]*\]",
        "[CVE-2024-12345]",
    ),
    ("solidity", r"\[(?:\s*SPEC\s*-\s*\d+|audit)[^\]]*\]|\b(ERC-\d+|EIP-\d+)\b", "ERC-721"),
    (
        "objective-c",
        r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit|RFC|W3C|CERN|TBL|ENQUIRE)[^\]]*\]|\b(?:WorldWideWeb|HyperText\s+Proposal|NeXTSTEP\s+Docs)\b",
        "WorldWideWeb",
    ),
    ("yacc", r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", None),
    ("m4", r"\[(?:[ \t]*SPEC[ \t]*-[ \t]*\d+|spec|audit)[^\]]*\]", None),
]


@pytest.mark.parametrize(
    "language,old_pattern_text,extra_positive",
    _SPEC_EXPOSURE_REDOS_SWEEP_TARGETS,
    ids=[t[0] for t in _SPEC_EXPOSURE_REDOS_SWEEP_TARGETS],
)
def test_spec_exposure_adjacent_quantifier_redos_sweep(language, old_pattern_text, extra_positive):
    old_pattern = re.compile(old_pattern_text, re.I)

    # Scale-relative sanity check (not an absolute wall-clock threshold,
    # which is flaky across CI hardware of varying speed -- the exact
    # failure mode of an earlier version of this same style of test in
    # this file): a payload-size doubling should cost ~4x on the
    # quadratic OLD pattern, vs ~2x for linear.
    small_duration = _best_of_timing(old_pattern, "[SPEC-" + "1" * 8000)
    large_duration = _best_of_timing(old_pattern, "[SPEC-" + "1" * 16000)
    ratio = large_duration / small_duration if small_duration > 0 else 0
    assert ratio > 2.2, (
        f"{language}: sanity check failed -- old pattern was expected to show quadratic (~4x) "
        f"scaling on a payload doubling, but only scaled {ratio:.2f}x "
        f"({small_duration:.4f}s -> {large_duration:.4f}s)"
    )

    spec_exposure = LANGUAGE_DEFINITIONS[language]["rules"]["spec_exposure"]
    assert_redos_immune(spec_exposure, "[SPEC-" + "1" * 100000, timeout_sec=3.0)
    assert spec_exposure.search("[SPEC-123]"), f"{language}: lost the basic SPEC-NNN positive case"
    assert spec_exposure.search("[audit]"), f"{language}: lost the basic [audit] positive case"
    if extra_positive is not None:
        assert spec_exposure.search(extra_positive), (
            f"{language}: lost its own extra alternative ({extra_positive!r}) while bounding the fix"
        )

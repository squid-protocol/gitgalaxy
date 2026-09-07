# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""
The `test` contract (#2852, docs/test_rule_contract.md), held across every
corpus language in one place.

    One hit is a site that engages a testing framework: a test-case or fixture
    declaration, a framework assertion or expectation, or the framework named
    as such -- never the language's own runtime guard.

The per-language strict suites keep their one positive/negative pair per
signal; this module pins the contract's corollaries -- exactly the shapes the
46-language audit found the old rules disagreeing on:

  C1 the runtime guard is safety's: the language's built-in production
     assertion (C's assert.h macro, python/embedded_python's `assert`
     statement, Lua's `assert(`) guards the running program and is safety's
     hit (#2626's python precedent, extended); a framework's assertion form
     (CU_ASSERT, ASSERT_*/EXPECT_*, assertEquals, luassert's assert.<chain>)
     is test's
  C2 one statement is one hit; a module qualifier is not a separate hit from
     the call it qualifies (perl `Test::More::ok(` = 1, was 2)
  C3 the ambiguity anchor: an everyday word fires only anchored to its
     framework form -- dart's bare `test`/`group` matched a predicate
     parameter and a loop variable, php's bare `test`/`mock` matched Twig's
     `->test(` method and a `$mock` variable, cobol's `TEST-CASE` matched
     hyphenated identifiers (`UT-TEST-CASE-COUNT`, the #2622 shape)
  C4 naming the framework counts, once: an unambiguous framework name
     (pytest, unittest, PHPUnit, Test::More, busted) is test evidence
     wherever it appears
  C5 stated absence: a language with no per-case idiom a framework executes
     records None (yacc -- `%expect` is a one-shot declarative pragma;
     jcl/markdown are n/a)

Each language lists (positives, negatives). A positive must match at least
once; a negative must not match at all. `COUNTS` pins one-statement-one-hit
shapes.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _strict_harness import assert_redos_immune  # type: ignore


def _rule(lang, signal="test"):
    return LANGUAGE_DEFINITIONS[lang]["rules"][signal]


# lang -> (positives, negatives)
CASES = {
    # --- C1: the runtime guard is safety's ---------------------------------------
    "c": (
        ["TEST(kit);", "RUN_TEST(kit);", "CU_ASSERT(x);", "EXPECT_EQ(a, b);", "ASSERT_TYPE_LOCK_HELD();"],
        ["assert(value);", "assert (x > 0);", "static_assert(sizeof(int) == 4);"],
    ),
    "embedded_python": (
        ["suite = unittest", "bench = pytest", "def test_boot():", "m = Mock()"],
        ["assert isinstance(value, int)", "assert x == 1"],
    ),
    "lua": (
        ["busted(kit)", "luassert(kit)", "assert.are.equal(a, b)", "assert.True(ok)", 'describe("x", f)'],
        ["assert(os.remove(file))", "assert(f:close())", "local assert = tasty.assert"],
    ),
    # --- C2: a qualifier is not a separate hit -----------------------------------
    "perl": (
        ["Test::More::ok($kit);", "subtest($kit);", "use Test::More;", "cmp_ok($a, '==', $b);"],
        ["croak($value);", "confess($value);", "okay(1, 'fine');"],
    ),
    # --- C3: the ambiguity anchor ------------------------------------------------
    "dart": (
        ["group('kit', kit);", "setUp(kit);", "test('adds', body);", "expect(a, b);", "testWidgets"],
        ["if (test(element)) {", "for (final g in group) {", "testMode = true;", "regroup(items);"],
    ),
    "php": (
        ["PHPUnit::run($kit);", "assertTrue($kit);", "test('adds', function () {", "$this->expects($this->once())"],
        ["$this->stream->current->test(Token::STRING_TYPE)", "$mock = static::isMock()", "unit test notes"],
    ),
    "cobol": (
        ["ASSERT RESULT-ONE.", "ZUNIT RESULT-TWO.", "READY TRACE."],
        ["MOVE UT-TEST-CASE-COUNT TO UT-TEST-CASE-NUMBER", "UT-TEST-CASE-NUMBER '. '"],
    ),
}

# One statement is one hit (C2), and the plant shapes stay pinned.
COUNTS = [
    ("perl", "Test::More::ok($kit);", 1),
    ("perl", "    Test::More::ok($kit);\n    subtest($kit);", 2),
    (
        "c",
        "int probe_test(int kit) {\n    TEST(kit);\n    RUN_TEST(kit);\n}\nint probe_safety(int v) {\n    assert(v);\n}",
        2,
    ),
    (
        "embedded_python",
        "def probe_test(kit):\n    suite = unittest\n    bench = pytest\ndef probe_safety(value):\n    assert isinstance(value, int)",
        2,
    ),
    ("dart", "int probeTest(int kit) {\n  group('kit', kit);\n  setUp(kit);\n}", 2),
    ("lua", "function probe_test(kit)\n  busted(kit)\n  luassert(kit)\nend", 2),
    ("cobol", "       PROBE-TEST.\n           ASSERT RESULT-ONE.\n           ZUNIT RESULT-TWO.", 2),
    ("php", "public function probe_test($kit) {\n    PHPUnit::run($kit);\n    assertTrue($kit);\n}", 2),
]

PAYLOADS = [
    "assert" * 30000,
    "assert(" * 20000,
    "Test::More::" * 20000,
    "test(" * 30000,
    "test('" + "a" * 100000,
    "group(  " * 20000,
    "-TEST-CASE" * 20000,
    "UT-TEST-CASE-" * 20000,
    "\t" * 50000 + "expect(",
    "ok(" * 40000,
]


@pytest.mark.parametrize("lang", sorted(CASES))
def test_test_contract_positive_and_negative(lang):
    rule = _rule(lang)
    positives, negatives = CASES[lang]
    for text in positives:
        assert rule.search(text), f"{lang}: contract positive did not match: {text!r}"
    for text in negatives:
        hits = [m.group(0) for m in rule.finditer(text)]
        assert not hits, f"{lang}: contract negative matched {hits!r} in {text!r}"


@pytest.mark.parametrize("lang,text,expected", COUNTS)
def test_test_one_statement_is_one_hit(lang, text, expected):
    hits = [m.group(0) for m in _rule(lang).finditer(text)]
    assert len(hits) == expected, f"{lang}: expected {expected} hits, got {hits!r}"


def test_test_runtime_guard_is_safetys_hit_alone():
    """C1: the retired duals stay single-owner -- safety still claims the
    runtime guard the test rule dropped (mass conserved, #2765's shape)."""
    for lang, guard in [
        ("c", "assert(value);"),
        ("embedded_python", "assert isinstance(value, int)"),
        ("lua", "assert(os.remove(file))"),
        ("python", "assert x == 1"),
    ]:
        assert _rule(lang, "safety").search(guard), f"{lang}: safety lost {guard!r}"
        assert not _rule(lang).search(guard), f"{lang}: test still claims {guard!r}"


def test_test_stated_absence_rows_carry_no_rule():
    """C5: yacc's absence is deliberate (ledger yacc-test-no-native-testing-
    concept); the rule stays None rather than an empty pattern."""
    assert LANGUAGE_DEFINITIONS["yacc"]["rules"].get("test") is None


@pytest.mark.parametrize("lang", sorted(CASES))
def test_test_contract_rules_are_redos_immune(lang):
    rule = _rule(lang)
    for payload in PAYLOADS:
        assert_redos_immune(rule, payload, timeout_sec=3.0)

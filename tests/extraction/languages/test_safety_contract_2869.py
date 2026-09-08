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
The `safety` contract (#2869, docs/safety_rule_contract.md), held across
every edited corpus language in one place.

    A site that handles or forestalls a runtime failure at the value level --
    a guarded region's opener or its typed handler, a runtime assertion or
    validation call, a fallback or handled-absence form, an installed
    failure handler or watchdog, or a hardening instruction -- in a form an
    ordinary identifier, type annotation or constructor cannot match.

The per-language strict suites keep their one positive/negative pair per
signal; this module pins the contract's corollaries -- exactly the shapes the
audit found the old rules disagreeing on:

  C1 value-level, not declaration-level: a type name, constructor or
     annotation is invisible (haskell's `Just x`, rust's `Option<T>`,
     scala's `Option[Int]`, python's `TypeGuard`/`@override`, java's
     `Optional<T>`); the runtime call, guarded arm or handled-absence form
     is the shape that counts.
  C2 raising is not handling: `errors.New`, lua's `error(`, kotlin's
     `error(`, haskell's `throw`, livecode's `throw` -- all raise a failure,
     none handle or forestall one.
  C3 one verified owner: a token that also belongs to another signal's
     contract is that signal's alone unless the ledger names a genuine dual
     -- haskell's `finally`/`bracket`/`onException` are cleanup's, lua's
     `<close>`/`<toclose>` are cleanup's, go's `sync.*` is concurrency's,
     cobol's `ON ERROR`/`AT END`/`INVALID KEY` stay branch's.
  C4 structure and reflection are not safety: cobol's `END-*` closers,
     assembly's frame/alignment mechanics, shell's quoted-expansion form,
     python's bare `getattr` (reflection_metaprogramming's) are dropped.
  C5 the ambiguity anchor: an everyday word fires only in its runtime-guard
     form -- shell's `${VAR:-fallback}` behind the fallback operator (a
     bare `"${VAR}"` is ordinary quoting), objective-c's bare `nil` is every
     null literal so only the ARC/assertion vocabulary stays, kotlin's bare
     `fold` is an ordinary fold.
  C6 deliberate duals are kept, not retired: scala's `Try` (immutability_locks
     dual, #2772), rust's `if let` (branch dual, pre-existing), go's
     `errors.Is` (encapsulation dual, #2766), dockerfile's `HEALTHCHECK`
     (func_start dual, #2856).

Each language lists (positives, negatives). A positive must match at least
once; a negative must not match at all. `COUNTS` pins one-site-one-hit
shapes. `DUALS` pins the tokens that fire a different signal, never safety.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _strict_harness import assert_redos_immune  # type: ignore


def _rule(lang, signal="safety"):
    return LANGUAGE_DEFINITIONS[lang]["rules"][signal]


# lang -> (positives, negatives)
CASES = {
    # --- C1: value-level, not declaration-level -----------------------------------
    "python": (
        [
            "try:",
            "assert x > 0",
            "isinstance(x, int)",
            "except ValueError:",
            "issubclass(C, Base)",
            "hasattr(obj, 'x')",
            "class M(BaseModel):",
        ],
        [
            "except:",
            "except Exception:",
            "except BaseException:",
            "getattr(obj, 'x')",
            "@dataclass",
            "x: TypeGuard[int]",
            "@override",
        ],
    ),
    "embedded_python": (
        [
            "try:",
            "assert x",
            "isinstance(x, int)",
            "except ValueError:",
            "machine.WDT()",
            "alloc_emergency_exception_buf()",
        ],
        ["except:", "except Exception:", "getattr(obj, 'x')"],
    ),
    "haskell": (
        ["try (evaluate x)", "catch handler onErr", "fromMaybe 0 y", "Nothing ->", "mask $ \\restore -> restore act"],
        [
            "Just x -> x",
            "Right y",
            "bracket open close use",
            "onException act handler",
            "probeSafety :: Maybe Int -> Either Int Int",
        ],
    ),
    "rust": (
        ["if let Some(x) = y {", "while let Some(x) = it.next() {", "let x = y.unwrap_or(0);", "None => {"],
        ["match x {", "Some(x) => x,", "let x: Option<i32> = None;", "fn f() -> Result<T, E> {"],
    ),
    "scala": (
        ["require(x > 0)", "assert(x > 0)", "assume(x > 0)", "Try(risky())", "Try {"],
        ["val x: Option[Int] = None", "sealed trait X", "Some(x)", "x | Null"],
    ),
    "java": (
        [
            "try {",
            "catch (Exception e) {",
            "finally {",
            "assert x > 0;",
            "Objects.requireNonNull(x)",
            "instanceof String",
            "@Valid",
            "@NotNull",
        ],
        ["Optional<String> x", "@Immutable", "@Transactional"],
    ),
    # --- C2: raising is not handling -----------------------------------------------
    "go": (
        ["err != nil", "errors.Is(err, target)", "errors.Join(e1, e2)", "recover()"],
        ['errors.New("x")', "sync.WaitGroup", "sync.Once", "context.Context"],
    ),
    "lua": (
        ["pcall(f, x)", "xpcall(f, handler)", "assert(x)"],
        ['error("x")', "type(x)", "getmetatable(x)", "pairs(t)", "ipairs(t)", "<const>", "<close>"],
    ),
    "kotlin": (
        [
            "require(x > 0)",
            "requireNotNull(x)",
            "check(x)",
            "checkNotNull(x)",
            "x is String",
            "x !is String",
            "runCatching { f() }",
            "result.onSuccess { }",
            "result.onFailure { }",
            "as?",
        ],
        ['error("x")', "sealed class X", "val r: Result<Int>", "list.fold(0) { acc, x -> acc + x }"],
    ),
    "livecode": (
        [
            "try",
            "catch tError",
            "finally",
            "lock screen",
            "lock messages",
            "lock errordialogs",
            "assert pValue",
            "strict compilation",
            "is a",
            "is strictly",
        ],
        ["throw x"],
    ),
    # --- C4: structure and reflection are not safety --------------------------------
    "cobol": (
        ["VALIDATE REC-A.", "CHECK REC-B.", "DECLARATIVES."],
        ["END-IF", "END-PERFORM", "END-EVALUATE", "PARA-VALIDATE.", "VALIDATE-X"],
    ),
    "assembly": (
        ["endbr64", "paciasp", "autiasp", "bti", "retab"],
        ["enter", "leave", ".align", ".p2align", "stp x29, x30"],
    ),
    "groovy": (
        ["try {", "catch (Exception e) {", "finally {", "assert x > 0", "instanceof String", "@Valid", "@NotNull"],
        ["Optional<String> x", "@Immutable"],
    ),
    # --- C5: the ambiguity anchor ----------------------------------------------------
    "shell": (
        ["set -e", "set -eu", "trap cleanup EXIT", "command -v gcc", "${HOME:-/root}"],
        ['"${HOME}"', '"$@"', '"$*"'],
    ),
    "objective-c": (
        [
            "@try {",
            "@catch (NSException *e) {",
            "@finally {",
            "__weak id x",
            "__strong id x",
            "__auto_type x",
            'NSAssert(x, @"y")',
            "NSParameterAssert(x)",
        ],
        ["nil", "Nil", "NSError *err"],
    ),
    # --- conformant anchors -----------------------------------------------------------
    "zig": (
        ["errdefer unlock();"],
        ["unreachable;", "@intCast(x)"],
    ),
    "swift": (
        ["precondition(value > 0)"],
        ["default:", "let x = 5"],
    ),
}

# (lang, text, expected hits): one guarded site is one hit; the canonical
# dual-form site (an assertion whose argument is itself a runtime type
# check) is two.
COUNTS = [
    ("python", "assert isinstance(v, int)", 2),
    ("embedded_python", "except:", 0),
    ("embedded_python", "except ValueError:", 1),
    ("haskell", "probeSafety :: Maybe Int -> Either Int Int", 0),
    ("haskell", "x = fromMaybe 0 y", 1),
    ("typescript", "try {\n} catch {\n}", 2),
    ("cobol", "END-IF", 0),
    ("cobol", "VALIDATE REC-A.", 1),
    ("shell", '"${HOME}"', 0),
    ("shell", "${HOME:-/root}", 1),
    ("rust", "match x {", 0),
    ("rust", "None => {", 1),
]

# (lang, text, dual_signal): a token the #2869 audit verified belongs to
# another signal alone -- it must never fire safety.
DUALS = [
    ("haskell", "hClose `finally` conn", "cleanup"),
    ("livecode", "throw x", "panics_and_aborts"),
    ("go", "sync.WaitGroup", None),
    ("scala", "val x: Option[Int]", None),
]

PAYLOADS = [
    "try " * 20000,
    "except" + " " * 50000 + "Exception",
    "except " * 20000,
    "assert " * 20000,
    "None => " * 20000,
    "unwrap_or_else " * 20000,
    "fromMaybe " * 20000,
    "Nothing" + " " * 50000 + "->",
    "err != nil " * 20000,
    "require(" * 20000,
    "Try" + " " * 50000 + "(",
    "DECLARATIVES" * 20000,
    "VALIDATE-" * 20000,
    "set -" + "e" * 50000,
    "trap " + "x" * 100000 + " EXIT",
    "${" + "a" * 30000 + ":-" + "b" * 30000 + "}",
    "endbr64 " * 20000,
    "__weak " * 20000,
    "instanceof " * 20000,
    "runCatching " * 20000,
    "lock screen " * 20000,
    "pcall(" * 20000,
]


@pytest.mark.parametrize("lang", sorted(CASES))
def test_safety_contract_positive_and_negative(lang):
    rule = _rule(lang)
    positives, negatives = CASES[lang]
    for text in positives:
        assert rule.search(text), f"{lang}: contract positive did not match: {text!r}"
    for text in negatives:
        hits = [m.group(0) for m in rule.finditer(text)]
        assert not hits, f"{lang}: contract negative matched {hits!r} in {text!r}"


@pytest.mark.parametrize("lang,text,expected", COUNTS)
def test_safety_one_site_is_one_hit(lang, text, expected):
    hits = [m.group(0) for m in _rule(lang).finditer(text)]
    assert len(hits) == expected, f"{lang}: expected {expected} hits, got {hits!r}"


@pytest.mark.parametrize("lang,text,dual_signal", DUALS)
def test_safety_deliberate_duals_never_fire_safety(lang, text, dual_signal):
    """C3: a token verified to belong to another signal's contract must
    never fire safety, whether or not that other signal is itself pinned
    here (mass conserved, the fortran-COMMON shape read in reverse)."""
    hits = [m.group(0) for m in _rule(lang).finditer(text)]
    assert not hits, f"{lang}: safety fired on the verified {dual_signal or 'other-owner'} dual {text!r}: {hits!r}"
    if dual_signal is not None:
        assert _rule(lang, dual_signal).search(text), f"{lang}: expected {dual_signal!r} to own {text!r}"


def test_safety_markdown_has_no_rule():
    """C4/absence: markdown has no runtime-guard morphology; the rule stays
    unset, not an empty pattern."""
    assert LANGUAGE_DEFINITIONS["markdown"]["rules"].get("safety") is None


@pytest.mark.parametrize("lang", sorted(CASES))
def test_safety_contract_rules_are_redos_immune(lang):
    rule = _rule(lang)
    for payload in PAYLOADS:
        assert_redos_immune(rule, payload, timeout_sec=3.0)

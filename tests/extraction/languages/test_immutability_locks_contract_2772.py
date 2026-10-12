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
The `immutability_locks` contract (#2772, rule half;
docs/immutability_locks_rule_contract.md), held across every edited corpus
language in one place.

    An added marker or lock call that prevents a binding or value from being
    changed after initialisation, where the language's default would permit
    it; the language's ordinary binding keyword is a binding choice, not a
    lock, and a language whose bindings are immutable by default records the
    stated absence.

The disease this contract exists to cure is an inversion: rust's immutable-by-
default `let` scored 0 while swift's `let` -- the same guarantee -- scored 11,
because swift's ordinary declaration keyword happened to be in its own rule.
The signal is subtracted at half weight inside `_calc_state_flux`, so the
inversion moved a *gated* metric. Corollaries:

  C1 the ordinary binding keyword is not a lock: swift `let`, kotlin/scala
     `val`, js/ts/zig `const`, dart `final` -- these are how the language
     declares every local; counting them rewards a notation. The added forms
     count: kotlin `const val`, scala `final val`, ts `readonly`/`as const`,
     dart `const`.
  C2 a lock on something other than data is not this signal: `final class` /
     `sealed` lock a hierarchy, solidity `view`/`pure` and rust `const fn`
     lock behavior, html `disabled`/`inert` gate interactivity, abap `FINAL`
     locks subclassing.
  C3 a name is not a lock: shell's `readonly='readonly'` inside echo'd HTML,
     cobol's `AN-CONSTANT` hyphenated names, powershell's pattern strings,
     rust's `&'static` lifetimes and `*const` pointer spelling.
  C4 immutable-by-default is an absence, not a zero-matching rule: haskell
     (whose old rule counted monadic `return`), swift and zig are `None`
     with a ledgered contract-level absence, the io/solidity precedent.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _strict_harness import assert_redos_immune  # type: ignore


def _rule(lang, signal="immutability_locks"):
    return LANGUAGE_DEFINITIONS[lang]["rules"][signal]


# lang -> (positives, negatives)
CASES = {
    # --- C1: the ordinary binding keyword is not a lock ---------------------------
    "javascript": (
        ["Object.freeze(config)", "Object.seal(state)"],
        ["const region = process.env;", "const pending = [];"],
    ),
    "typescript": (
        ["readonly expression: Expression;", "Object.freeze(x)", "x as const"],
        ["const pos = getNodePos();", "final"],
    ),
    "kotlin": (
        ["const val VERSION = 3"],
        ["val loose = shape as Int", "private val calls = ArrayDeque<AsyncCall>()"],
    ),
    "scala": (
        ["final val MaxSize = 10", "immutable.HashMap[Int, Node]"],
        ["val clientId = request.header.clientId", "sealed trait Shape"],
    ),
    "dart": (
        ["@immutable", "const MultiChildRenderObjectWidget({super.key});"],
        ["final Matrix4 transform;", "final note = 'x';"],
    ),
    "rust": (
        ["const MAX: u32 = 10;", "static NANOS_PER_SEC: u32 = 1_000_000_000;"],
        ["name: &'static str,", "*const Entry", "const fn new() -> Self {"],
    ),
    "go": (
        ["const prefix = \"GODEBUG=\""],
        [],
    ),
    # --- C2: locks on non-data are not this signal --------------------------------
    "abap": (
        ["CONSTANTS c_zero TYPE i VALUE 0.", "DATA gv_x TYPE i READ-ONLY."],
        ["FINAL."],
    ),
    "solidity": (
        ["uint256 public constant ROLE = 0x00;", "address public immutable owner;"],
        ["function hasRole() public view virtual returns (bool) {", "function f() internal pure {"],
    ),
    "html": (
        ["<input required readonly>"],
        ['<button disabled="disabled">Go</button>', "<div inert>"],
    ),
    # --- C3: a name is not a lock --------------------------------------------------
    "shell": (
        ["readonly STDERR=$(mktemp)", "declare -r X=1", "x=1; readonly x"],
        ["echo \"<input value='a' readonly='readonly'/>\""],
    ),
    "cobol": (
        ["01 C CONSTANT AS 5."],
        ["01 CONSTANT-VALUES.", "02 AN-CONSTANT PIC X(5).", 'MOVE "X" TO NUM-CONSTANT'],
    ),
    "powershell": (
        ["New-Variable -Name x -Value 1 -Option Constant", "Set-Variable y -Option ReadOnly"],
        ["$s = 'public readonly struct Ctx'"],
    ),
    "scheme": (
        ["(string->immutable-string s)"],
        ["'()", "(quote (1 2 3))", "#'(if (string? x)"],
    ),
    # --- unchanged opt-in forms stay ------------------------------------------------
    "java": (
        ["private final Resources resourceProperties;"],
        [],
    ),
    "c": (
        ["const char *name = 0;", "static const int N = 3;"],
        [],
    ),
    "csharp": (
        ["private readonly int _n;", "ImmutableArray<int> xs;"],
        [],
    ),
    "fortran": (
        ["INTEGER, PARAMETER :: LIMIT = 3", "INTEGER, INTENT(IN) :: ids"],
        [],
    ),
    "lua": (
        ["local kNil <const> = nil"],
        ["local x = 1"],
    ),
    "ruby": (
        ["value.freeze"],
        [],
    ),
}


@pytest.mark.parametrize("lang", sorted(CASES))
def test_immutability_locks_contract_cases(lang):
    rule = _rule(lang)
    positives, negatives = CASES[lang]
    for snippet in positives:
        assert rule.search(snippet), f"{lang}: expected lock hit in {snippet!r}"
    for snippet in negatives:
        assert not rule.search(snippet), f"{lang}: unexpected lock hit in {snippet!r}"


# C4: immutable-by-default languages record the stated absence.
@pytest.mark.parametrize("lang", ["haskell", "swift", "zig"])
def test_immutability_locks_stated_absence(lang):
    assert _rule(lang) is None, f"{lang}: expected None (contract-level absence)"


def test_immutability_locks_redos_sweep():
    payloads = [
        "readonly " + "a" * 50000,
        "const" + " " * 50000,
        ";" * 200 + "readonly " + "b" * 50000,
        "New-Variable " + "x" * 50000,
        "final " + "val" * 20000,
    ]
    for lang in sorted(CASES):
        rule = _rule(lang)
        for payload in payloads:
            assert_redos_immune(rule, payload, timeout_sec=3.0)

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
The `branch` contract (#2822, docs/branch_rule_contract.md), held across every
corpus language in one place.

    One hit is a keyword or operator that opens a runtime choice between
    control-flow paths: the choosing construct itself or one of its
    alternative arms.

The per-language strict suites keep their one positive/negative pair per signal;
this module pins the contract's corollaries, which are exactly the shapes the
46-language audit found the old rules disagreeing on:

  1. a handler is not a decision: catch/rescue/except/finally/ensure/trap and
     the guarded-region opener (try, @try, do-catch, begin) are safety's; the
     decision was made by the throw
  2. one conditional is one hit per arm-opener: continuation words (then, of,
     THEN), closing words (fi, esac, done, END, ENDIF, end if), re-matches of
     the opening keyword inside a closer, the test brackets, and a syntax word
     mandated by an already-counted construct (a guard's own else) do not count
  3. an unconditional transfer is not a decision: goto leaves branch exactly
     like return (#2545) and jmp/call/ret (#2764) did; COBOL's bare
     `PERFORM <paragraph>` is the language's call form, and its loop forms
     count at their condition words (UNTIL/VARYING/TIMES)

Each language lists (positives, negatives). A positive must match at least once;
a negative must not match at all. `COUNTS` pins one-construct-one-hit shapes.
The typescript mirror (`safety` must not count type keywords) rides here because
it is the same corollary-4 question from the other side.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _strict_harness import assert_redos_immune  # type: ignore


def _rule(lang, signal="branch"):
    return LANGUAGE_DEFINITIONS[lang]["rules"][signal]


# lang -> (positives, negatives)
CASES = {
    # --- corollary 1: a handler is not a decision ----------------------------------
    "cpp": (
        ["if (x) {", "} else {", "switch (k) {", "a ? b : c"],
        ["catch (...) {", "goto error;", "try {"],
    ),
    "ruby": (
        ["if flag > 0", "elsif flag < 0", "else", "case x", "when 1"],
        ["rescue StandardError", "ensure", "begin", "retry"],
    ),
    "java": (
        ["if (x) {", "} else {", "switch (k) {", "do {"],
        ["try {", "catch (Exception e) {", "finally {"],
    ),
    "javascript": (
        ["if (x) {", "} else {", "for (;;) {"],
        ["try {", "catch (e) {", "} finally {"],
    ),
    "typescript": (
        ["if (x) {", "switch (kind) {", "x ?? y"],
        ["try {", "catch (e) {", "} finally {"],
    ),
    "python": (
        ["if x:", "elif y:", "else:", "match p:", "case 1:"],
        ["try:", "finally:"],
    ),
    "embedded_python": (
        ["if x:", "elif y:", "while True:"],
        ["try:", "finally:"],
    ),
    "matlab": (
        ["if (x)", "elseif y", "otherwise"],
        ["try", "catch ME"],
    ),
    "scala": (
        ["if (x)", "x match {", "case _ =>"],
        ["try {", "} catch {", "} finally {", "throw ex", "then"],
    ),
    "groovy": (
        ["if (x) {", "} else {", "switch (k) {"],
        ["try {", "catch (e) {", "finally {"],
    ),
    "dart": (
        ["if (x) {", "} else {", "switch (k) {"],
        ["try {", "on FormatException catch (e) {", "finally {"],
    ),
    "apex": (
        ["if (x == 1) {", "switch on k {", "when 'A' {"],
        ["try {", "catch (Exception e) {", "finally {"],
    ),
    "kotlin": (
        ["if (x) {", "when (flag) {", "do {"],
        ["try {", "catch (e: Exception) {", "finally {"],
    ),
    "tcl": (
        ["if {$x > 0} {", "} elseif {$y} {", "switch $k {"],
        ["catch {db close}", "try {", "trap $value", "finally { bar }"],
    ),
    "powershell": (
        ["if ($x -gt 0) {", "} else {", "switch ($k) {"],
        ["try {", "catch {", "} finally {", "trap {", "throw 'x'"],
    ),
    "perl": (
        ["if ($x) {", "unless ($y) {", "given ($k) {"],
        ["try {", "catch ($e) {", "finally {", "goto LABEL;", "defer {"],
    ),
    "php": (
        ["if ($x) {", "} else {", "match ($k) {"],
        ["try {", "catch (Throwable $t) {", "finally {", "goto end;"],
    ),
    "solidity": (
        ["if (x) {", "} else {", "do { x--; } while (x > 0);"],
        ["try feed.getData(t) returns (uint v) {", "catch Error(string memory r) {"],
    ),
    "zig": (
        ["if (x) {", "} else {", "switch (k) {", "const a = b orelse c;"],
        ["try doSomething();", "catch |err| return err;"],
    ),
    "abap": (
        ["IF sy-subrc = 0.", "ELSEIF lv_x < 0.", "CASE lv_x.", "CHECK lv_ok = abap_true."],
        ["TRY.", "CATCH cx_root INTO DATA(lx).", "CLEANUP.", "RETURN."],
    ),
    "livecode": (
        ["if pFlag > 0 then", "else", "repeat with i = 1 to 3", "next repeat"],
        ["try", "catch tError", "finally", "throw pValue", "end if", "end repeat", "end switch"],
    ),
    # --- corollary 2: one conditional is one hit per arm-opener --------------------
    "ada": (
        ["if Flag > 0 then", "elsif Flag < 0 then", "else", "case K is", "when 1 =>"],
        ["end if;", "end case;", "end loop;"],
    ),
    "sqlite": (
        ["CASE", "WHEN 1", "ELSE 3", "WHERE c = 3", "IFNULL(a, b)"],
        ["THEN 2", "END", "END;"],
    ),
    "shell": (
        ["if true; then :; fi", "elif [ -z x ]; then", "until [ -z x ]; do", "case $x in"],
        ["fi", "esac", "done", '[ "$x" = "y" ]', "[[ -n $y ]]"],
    ),
    "dockerfile": (
        ["RUN if true; then :; fi", "RUN test -f x && echo y"],
        ["fi", "esac", "done"],
    ),
    "yaml": (
        ["if true; then :; fi", "elif false; then :;"],
        ["fi", "esac", "done"],
    ),
    "haskell": (
        ["if flag > 0", "else 2", "case v of"],
        ["then 1", "of"],
    ),
    "lua": (
        ["if flag > 0", "elseif flag < 0", "repeat", "while x"],
        ["then", "do", "until x > 3", "goto skip"],
    ),
    "jcl": (
        ["//PROBEBR IF (RC EQ 0)", "//BRELSE ELSE"],
        ["//BREND ENDIF", "//         ENDIF"],
    ),
    "makefile": (
        ["ifeq ($(FLAG),1)", "else", "ifdef DEBUG"],
        ["endif"],
    ),
    "fortran": (
        ["IF (FLAG > 0) THEN", "ELSEIF (FLAG < 0) THEN", "ELSE", "DO I = 1, N"],
        ["END IF", "END DO", "END WHERE", "GOTO 100", "GO TO 100"],
    ),
    "swift": (
        ["if flag > 0 {", "} else {", "guard flag > 0 else { return 3 }", "repeat {"],
        ["catch let e {", "try foo()", "throws(Error)", "defer { cleanup() }"],
    ),
    # --- corollary 3: an unconditional transfer is not a decision ------------------
    "c": (
        ["if (flag > 0) {", "} else {", "switch (flag) {}"],
        ["goto error;"],
    ),
    "csharp": (
        ["if (x) {", "} else {", "foreach (var x in xs) {"],
        ["goto MyLabel;", "try {", "catch (Exception e) {", "finally {"],
    ),
    "go": (
        ["if x != nil {", "} else {", "select {", "switch k {"],
        ["goto L"],
    ),
    "objective-c": (
        ["if (x) {", "} else {", "do {"],
        ["goto label;", "@try {", "@catch (NSException *e) {", "@finally {"],
    ),
    "cobol": (
        [
            "IF FLAG-ONE = 1",
            "ELSE",
            "EVALUATE FLAG-ONE.",
            "WHEN OTHER",
            "PERFORM VARYING I FROM 1 BY 1 UNTIL I > 5",
        ],
        ["END-IF", "END-IF.", "END-EVALUATE", "PERFORM POPULATE-TIME-DATE", "PERFORM A THRU B"],
    ),
    "lua_goto": (  # alias handled below; kept for readability of the audit doc
        [],
        [],
    ),
}
del CASES["lua_goto"]

# (lang, text, expected exact hit count) -- one construct is one hit per arm-opener
COUNTS = [
    ("c", "if (flag > 0) {\n    return 1;\n} else {\n    return 2;\n}\nswitch (flag) {}", 3),
    ("shell", "if [ 1 -gt 0 ]; then\n    :\nelse\n    :\nfi\nwhile false; do\n    :\ndone", 3),
    ("sqlite", "SELECT CASE WHEN 1 THEN 2 ELSE 3 END;", 3),
    ("swift", "if flag > 0 {\n} else {\n}\nguard flag > 0 else { return 3 }", 3),
    ("ada", "if Flag > 0 then\n   null;\nelsif Flag < 0 then\n   null;\nelse\n   null;\nend if;", 3),
    ("haskell", "probeBranch flag = case flag of\n  0 -> 3\n  _ -> if flag > 0 then 1 else 2", 3),
    ("lua", "if flag > 0 then\n  return 1\nelse\n  return 2\nend\nwhile false do\nend", 3),
    ("fortran", "IF (FLAG > 0) THEN\nELSE\nEND IF\nDO I = 1, N\nEND DO", 3),
    ("cobol", "IF FLAG-ONE = 1\nELSE\nEND-IF.\nPERFORM PROBE-IO.\nPERFORM CALC UNTIL DONE = 1.", 3),
    ("livecode", "if pFlag > 0 then\n  get 1\nelse\n  get 2\nend if\nrepeat 1 times\nend repeat", 3),
    ("jcl", "//PROBEBR IF (RC EQ 0)\n//BRELSE ELSE\n//BREND ENDIF", 2),
    ("powershell", "trap { }\nif ($flag -gt 0) {\n} else {\n}\nswitch ($flag) {}", 3),
    ("csharp", "if (x) {\n} else {\n}\nswitch (x) {}\ngoto done;", 3),
    ("makefile", "ifeq ($(FLAG),1)\nelse\nendif", 2),
    ("go", "for i := range xs {", 1),  # range rides the for it continues
]

# The typescript mirror: type keywords are not runtime guards (safety side).
TS_SAFETY_POSITIVES = ["try {", "catch (e) {", "finally {", "x ?? y", "satisfies Config"]
TS_SAFETY_NEGATIVES = ["function f(x: unknown) {}", "let v: never", "function g(): void {}"]

PAYLOADS = [
    "if" * 50000,
    "else " * 30000,
    "end " * 50000 + "if",
    "END-" * 40000 + "IF",
    "}" * 60000 + " else",
    "//" + "A" * 100000 + " IF",
    "PERFORM " * 20000,
    "[" * 60000,
    "?" * 80000,
    "\t" * 50000 + "when",
]


@pytest.mark.parametrize("lang", sorted(CASES))
def test_branch_contract_positive_and_negative(lang):
    rule = _rule(lang)
    positives, negatives = CASES[lang]
    for text in positives:
        assert rule.search(text), f"{lang}: contract positive did not match: {text!r}"
    for text in negatives:
        hits = [m.group(0) for m in rule.finditer(text)]
        assert not hits, f"{lang}: contract negative matched {hits!r} in {text!r}"


@pytest.mark.parametrize("lang,text,expected", COUNTS)
def test_branch_one_construct_is_one_hit_per_arm(lang, text, expected):
    hits = [m.group(0) for m in _rule(lang).finditer(text)]
    assert len(hits) == expected, f"{lang}: expected {expected} hits, got {hits!r}"


def test_typescript_safety_type_keywords_are_not_guards():
    rule = _rule("typescript", "safety")
    for text in TS_SAFETY_POSITIVES:
        assert rule.search(text), f"typescript safety positive did not match: {text!r}"
    for text in TS_SAFETY_NEGATIVES:
        hits = [m.group(0) for m in rule.finditer(text)]
        assert not hits, f"typescript safety matched type keywords {hits!r} in {text!r}"


@pytest.mark.parametrize("lang", sorted(CASES))
def test_branch_contract_rules_are_redos_immune(lang):
    rule = _rule(lang)
    for payload in PAYLOADS:
        assert_redos_immune(rule, payload, timeout_sec=3.0)

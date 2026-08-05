"""m4 strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py, then
colocated here in tests/extraction/languages/ alongside the extraction
gauntlets' own test_<lang>.py files (the `_strict` suffix on this filename
avoids a basename collision between the two under pytest's default import
mode). See tests/core_engine/test_language_standards_strict.py's git history
for the original single-file layout and section banners (Issue references, etc).
"""

import sys
from pathlib import Path

import pytest
import re

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore


# ==============================================================================
# M4: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #595, part of epic #518)
# ==============================================================================
M4_RULES = LANGUAGE_DEFINITIONS["m4"]["rules"]

_M4_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "AS_IF([test x = y], [true])", "AC_SUBST(FOO)"),
    ("args", "$1", "FOO"),
    ("structural_boundaries", "AC_REQUIRE([_FOO])", "AC_SUBST(FOO)"),
    ("func_start", "AC_DEFUN([MY_MACRO], [", "AC_SUBST(FOO)"),
    ("safety", "AC_CHECK_LIB([m], [cos])", "AC_SUBST(FOO)"),
    ("safety_bypasses", "changequote(<<, >>)", "AC_SUBST(FOO)"),
    ("high_risk_execution", "esyscmd(uname -a)", "AC_SUBST(FOO)"),
    ("io", "AC_CONFIG_FILES([Makefile])", "AC_SUBST(FOO)"),
    ("api", "AC_SUBST(FOO)", "AC_REQUIRE([_FOO])"),
    ("state_mutation", "pushdef([foo], [bar])", "AC_SUBST(FOO)"),
    ("dead_code", "dnl define(OLD_MACRO, [x])", "dnl just a note"),
    ("doc", "dnl @param x the input", "dnl just a note"),
    ("test", "AT_SETUP([my test])", "AC_SUBST(FOO)"),
    ("globals", "AC_ARG_VAR([FOO], [description])", "AC_SUBST(FOO)"),
    ("comprehensions", "m4_foreach([x], [a, b, c], [FOO(x)])", "AC_SUBST(FOO)"),
    ("scientific", "m4_eval(1 + 2)", "AC_SUBST(FOO)"),
    ("reflection_metaprogramming", "patsubst(FOO, o, 0)", "AC_SUBST(FOO)"),
    ("import", "include(foo.m4)", "AC_SUBST(FOO)"),
    ("ownership", "dnl Author: Jane Doe", "dnl just a note"),
    ("planned_debt", "dnl TODO: fix this", "dnl done"),
    ("fragile_debt", "dnl HACK: workaround", "dnl clean"),
    ("spec_exposure", "[SPEC-123]", "dnl just a note"),
    ("dependency_injection", "AC_REQUIRE([_FOO])", "AC_SUBST(FOO)"),
    ("macros", "AC_DEFINE([HAVE_FOO], [1], [description])", "AC_SUBST(FOO)"),
    ("telemetry", "AC_MSG_CHECKING([for foo])", "AC_SUBST(FOO)"),
    ("debug_prints", "errprint(debug message)", "AC_SUBST(FOO)"),
    ("panics_and_aborts", "AC_MSG_ERROR([fatal])", "AC_SUBST(FOO)"),
    ("thread_sleeps", "sleep 5", "AC_SUBST(FOO)"),
    ("cleanup", "AT_CLEANUP", "AC_SUBST(FOO)"),
    ("encapsulation", "m4_pattern_forbid([^MY_])", "AC_SUBST(FOO)"),
    ("test_skip", "AT_SKIP_IF([test x = y])", "AC_SUBST(FOO)"),
]


@pytest.mark.parametrize("signature,positive,negative", _M4_SIMPLE_CASES)
def test_m4_signature_positive_and_negative(signature, positive, negative):
    pattern = M4_RULES[signature]
    assert pattern is not None, f"m4's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"m4 {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"m4 {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_m4_comment_style_completeness_dead_code_doc_ownership_regression():
    """
    Real bug found and fixed (Engine Rule 12 -- Comment-Style Completeness):
    `dead_code`, `doc`, and `ownership` were all anchored ONLY on `dnl`, but
    GNU M4's actual default lexer-level comment delimiter is `#`-to-newline
    (confirmed in the shared `line_exclusive` family table in
    gitgalaxy_config.py, which prism.py uses to carve out the comment
    stream for every line_exclusive language -- `dnl` is a separate,
    macro-level discard mechanism). Confirmed via the real language-crucible
    corpus (curl/gnucobol configure.ac) that `#` comments are at least as
    common as `dnl` ones in real Autoconf files, including `# FIXME:`/
    `# Copyright` lines. Checking only `dnl` silently missed the dominant
    style in real code.
    """
    old_dead_code = re.compile(r"^[ \t]*dnl[ \t]+(?:m4_define|define|AC_DEFUN|ifelse|AS_IF)\b", re.M)
    old_doc = re.compile(r"^[ \t]*dnl[ \t]+@(?:param|return|brief)|AC_COPYRIGHT\b", re.M)
    old_ownership = re.compile(r"^[ \t]*dnl[ \t]+(?:Author|Maintainer|Copyright|License):|AC_COPYRIGHT", re.I | re.M)

    realistic_dead_code = "# define OLD_MACRO(x)"
    realistic_doc = "# @param x the input value"
    realistic_ownership = "# Author: Jane Doe"

    assert not old_dead_code.search(realistic_dead_code), "sanity check: dead_code bug must reproduce"
    assert not old_doc.search(realistic_doc), "sanity check: doc bug must reproduce"
    assert not old_ownership.search(realistic_ownership), "sanity check: ownership bug must reproduce"

    assert M4_RULES["dead_code"].search(realistic_dead_code)
    assert M4_RULES["doc"].search(realistic_doc)
    m = M4_RULES["ownership"].search(realistic_ownership)
    assert m

    # the dnl forms these rules were already correct for must still work
    assert M4_RULES["dead_code"].search("dnl define(OLD_MACRO, [x])")
    assert M4_RULES["doc"].search("dnl @param x the input")
    assert M4_RULES["ownership"].search("dnl Author: Jane Doe")

    # a mid-line '#' that isn't a real column-anchored comment must not count
    assert not M4_RULES["dead_code"].search("x = val # define OLD_MACRO(x)")


def test_m4_func_start_excludes_commented_lines_structurally():
    """
    Lexical-family note from the issue: `line_exclusive` has no block
    syntax, and func_start's own `^[ \\t]*` anchor only tolerates leading
    whitespace -- neither `dnl` nor `#` is a whitespace character, so a
    commented-out macro definition can never satisfy func_start's anchor
    at the raw-regex level itself (a stronger guarantee than relying on
    prism.py's comment/code stream separation alone).
    """
    func_start = M4_RULES["func_start"]
    assert not func_start.search("dnl define OLD_MACRO(x)")
    assert not func_start.search("dnl AC_DEFUN([OLD_MACRO], [])")
    assert not func_start.search("# define OLD_MACRO(x)")
    assert func_start.search("define(`OLD_MACRO', `x')"), "a genuine uncommented define must still match"


def test_m4_func_start_vs_macros_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a run of macro/
    preprocessor lines fooling func_start, as seen in C++). m4's macros
    signature tracks C-preprocessor-hook configuration calls (AC_DEFINE/
    AC_DEFINE_UNQUOTED/AH_TEMPLATE), structurally distinct from
    func_start's macro-*definition* keywords (m4_define/define/AC_DEFUN/
    AU_DEFUN/m4_defun) -- no realistic overlap. Also confirms func_start
    survives a long run of macros-shaped input without pathological
    backtracking.
    """
    func_start = M4_RULES["func_start"]
    macros = M4_RULES["macros"]

    macro_call = "AC_DEFINE([HAVE_FOO], [1], [description])"
    assert macros.search(macro_call)
    assert not func_start.search(macro_call)

    definition = "AC_DEFUN([MY_MACRO], [...])"
    assert func_start.search(definition)
    assert not macros.search(definition)

    assert_redos_immune(func_start, "AC_DEFINE([A])\n" * 20000, timeout_sec=3.0)


def test_m4_api_vs_macros_ac_define_intentional_double_classification():
    """
    Ambiguity sweep finding: `AC_DEFINE(...)` legitimately fires both `api`
    (exports a symbol into the generated C header, part of the public
    configure-time surface) and `macros` (configures a C-level preprocessor
    hook) -- both true simultaneously, an intentional double-classification
    per this rule set's own doc comments, not a false collision.
    """
    line = "AC_DEFINE([HAVE_FOO], [1], [description])"
    assert M4_RULES["api"].search(line)
    assert M4_RULES["macros"].search(line)


def test_m4_cleanup_vs_state_mutation_popdef_intentional_double_classification():
    """
    Ambiguity sweep finding: `popdef(...)` legitimately fires both
    `state_mutation` (restoring the previous stack-pushed macro definition
    is itself a mutation of macro state) and `cleanup` (releasing/undoing
    a pushdef stack frame) -- both true at once, intentional.
    """
    line = "popdef([foo])"
    assert M4_RULES["state_mutation"].search(line)
    assert M4_RULES["cleanup"].search(line)


def test_m4_cleanup_vs_test_at_cleanup_intentional_double_classification():
    """
    Ambiguity sweep finding: `AT_CLEANUP` legitimately fires both `test`
    (it's an Autotest framework directive) and `cleanup` (it's literally
    the test-teardown/resource-release step) -- both true at once,
    intentional.
    """
    line = "AT_CLEANUP"
    assert M4_RULES["test"].search(line)
    assert M4_RULES["cleanup"].search(line)


def test_m4_dependency_injection_vs_structural_boundaries_ac_require_intentional_double_classification():
    """
    Ambiguity sweep finding: `AC_REQUIRE([_FOO])` legitimately fires both
    `structural_boundaries` (dependency-ordering directive controlling
    macro-expansion sequencing) and `dependency_injection` (ensuring a
    macro is defined before use, the same IoC-container-style dependency
    resolution the signature is meant to capture in other languages) --
    both true at once, intentional.
    """
    line = "AC_REQUIRE([_MY_INIT])"
    assert M4_RULES["structural_boundaries"].search(line)
    assert M4_RULES["dependency_injection"].search(line)


def test_m4_doc_vs_ownership_ac_copyright_intentional_double_classification():
    """
    Ambiguity sweep finding (mirrors the abap/fortran doc-vs-ownership
    cases): `AC_COPYRIGHT(...)` legitimately fires both `doc` (it inserts
    licensing documentation into the generated output) and `ownership`
    (it's authorship/copyright metadata) -- both true at once, intentional.
    """
    line = "AC_COPYRIGHT([Copyright (C) 2026 Jane Doe])"
    assert M4_RULES["doc"].search(line)
    assert M4_RULES["ownership"].search(line)


def test_m4_no_block_comment_family_confusion():
    """
    Lexical-family audit: m4 is `line_exclusive` -- it has no native
    multi-line block-comment syntax, and none of its rules reference C-style
    `/* */` delimiters. Confirms a stray `/* */`-shaped sequence (which can
    legitimately appear as literal embedded C code being generated by the
    macros, not a real m4 comment) doesn't accidentally trigger dead_code
    or doc.
    """
    stray = "/* not a real m4 comment, just embedded C output */"
    assert not M4_RULES["dead_code"].search(stray)
    assert not M4_RULES["doc"].search(stray)


def test_m4_redos_immunity_sweep():
    """
    ReDoS immunity sweep across m4's rules with unbounded-looking
    quantifiers, verified via a systematic scaling sweep (n=2000/4000/8000/
    16000/32000) before writing this test -- all rules showed ~2x time per
    doubling (linear), not the ~4x signature of catastrophic backtracking.
    """
    assert_redos_immune(M4_RULES["func_start"], "m4_define" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(M4_RULES["dead_code"], "#" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(M4_RULES["doc"], "dnl " + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(M4_RULES["ownership"], "# " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(M4_RULES["spec_exposure"], "[SPEC-1" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(M4_RULES["import"], "include" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(M4_RULES["args"], "$" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert M4_RULES["func_start"].search("AC_DEFUN([MY_MACRO], [")
    assert M4_RULES["dead_code"].search("dnl define(OLD_MACRO, [x])")
    assert M4_RULES["ownership"].search("dnl Author: Jane Doe")

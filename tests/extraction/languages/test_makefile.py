"""
Makefile extraction hardening (epic #813, issue #844). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers three of the four extraction gauntlets for makefile in one file:
func_start, args, _dependency_capture (makefile has no `class_start` -- it's
strictly declarative, no OO constructs, see
LANGUAGE_DEFINITIONS["makefile"]["rules"]["class_start"] == None -- so there
is no CLASS_CASES section here, matching the issue's own scope). Migrated
out of the two old monolithic dict files that had makefile entries
(test_function_extraction_strict.py, test_dependency_extraction_strict.py --
test_args_extraction_strict.py and test_class_extraction_strict.py had no
makefile entry at all).
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# tests/ has no __init__.py anywhere in this repo, so a dotted
# `tests.extraction._extraction_harness` import only works by accident
# locally (e.g. `python -m pytest` from the repo root happens to put the
# root on sys.path) and fails in CI, which invokes the `pytest` console
# script directly. Insert this file's parent (tests/extraction/) onto
# sys.path instead, so the harness imports as a plain top-level module.
_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from typing import Any

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_pathological_dependency_match,
    assert_pathological_match,
    assert_redos_immune,
    assert_valid_dependency_match,
    assert_valid_match,
)

MAKEFILE_RULES = LANGUAGE_DEFINITIONS["makefile"]["rules"]

# ==============================================================================
# FUNC_START (func_start) -- makefile's "function" is a target/rule declaration.
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        ("target:", "target"),
        ("target::", "target"),
        ("%.o: %.c", "%.o"),  # pattern rule
        ("build/%.o: src/%.c", "build/%.o"),  # directory-prefixed pattern rule
        ("  target:", "target"),  # space-indented (e.g. inside a conditional)
        ("target : dep1 dep2", "target"),  # space before colon
        ("a b c: dep", "a"),  # multi-target rule -- was a real bug, now fixed
        ("all clean install: deps", "all"),  # multi-target rule
        (".PHONYTARGET:", ".PHONYTARGET"),  # not over-excluded by prefix match with a real special target
    ],
    "invalid": [
        ".PHONY: clean",  # special target, excluded
        "MY_VAR := value",  # simply-expanded assignment -- was a real bug, now fixed
        "MY_VAR ::= value",  # POSIX immediate assignment -- was a real bug, now fixed
        "MY_VAR ?= value",  # conditional assignment (no bare colon)
        "MY_VAR = value",  # plain assignment (no colon at all)
        "# target: dep",  # commented-out target
        '\techo "note: this matters"',  # recipe, colon inside a quoted string
        "\tcurl http://example.com/file",  # recipe, URL colon -- was a real bug, now fixed
        "\techo 10:30",  # recipe, time-shaped colon -- was a real bug, now fixed
    ],
    "pathological": [
        ("TargetFunc \t :", "TargetFunc"),  # carried-forward: tab before colon
        ("a   b\tc  :  dep", "a"),  # multi-target with heavy/mixed whitespace
        (
            "obj/deep/nested/%.o: src/deep/nested/%.c",
            "obj/deep/nested/%.o",
        ),  # deeply-pathed pattern rule
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_makefile_func_start_valid(payload, expected_name):
    assert_valid_match(MAKEFILE_RULES["func_start"], payload, expected_name, "makefile.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_makefile_func_start_invalid(payload):
    assert_invalid_no_match(MAKEFILE_RULES["func_start"], payload, "makefile.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_makefile_func_start_pathological(payload, expected_name):
    assert_pathological_match(MAKEFILE_RULES["func_start"], payload, expected_name, "makefile.func_start")


def test_makefile_func_start_assignment_operator_regression():
    """
    Regression test for a real bug (epic #813/#844): the trailing lookahead
    only checked for a bare `:`/`::`, with no exclusion for an
    immediately-following `=` -- so `MY_VAR := value` and `MY_VAR ::= value`
    (GNU Make's two immediate-expansion assignment operators, arguably THE
    most common modern Make idiom) were both misidentified as real target
    declarations. Fixed with a negative lookahead so neither colon form can
    be immediately followed by `=`.
    """
    func_start = MAKEFILE_RULES["func_start"]
    assert not func_start.search("MY_VAR := value"), "simply-expanded assignment regressed"
    assert not func_start.search("MY_VAR ::= value"), "POSIX immediate assignment regressed"
    assert func_start.search("target:"), "real target must still match"


def test_makefile_func_start_multi_target_regression():
    """
    Regression test for a real bug (epic #813/#844): a multi-target rule
    (`a b c: deps`, a real and common Make idiom for sharing one recipe
    across several targets) wasn't detected AT ALL -- the identifier class
    stopped at the first space, then the colon lookahead failed against the
    next target name instead of a colon, and there's no second `^` anchor
    point later on the same line to retry from. Fixed by allowing
    additional space-separated co-target tokens before the colon lookahead.
    """
    func_start = MAKEFILE_RULES["func_start"]
    m = func_start.search("all clean install: deps")
    assert m and m.group(1) == "all", "multi-target rule regressed"


def test_makefile_func_start_recipe_line_no_false_collision_regression():
    """
    Regression test for a regression I introduced while fixing the
    multi-target bug above, caught before shipping: allowing space-separated
    co-target tokens reopened a NEW false-positive vector -- a recipe line
    with multiple words where a later word contains a colon not followed by
    `=` (a URL's `://`, a bare time value `10:30`) misparsed as "co-target
    tokens then a real target-defining colon". Fixed by narrowing the
    leading-whitespace class from `[ \\t]*` to `[ ]*` (spaces only) --
    a tab-initial line is ALWAYS a recipe command in Make's own lexical
    rules (never a directive, absent a custom .RECIPEPREFIX), so this
    structurally excludes every recipe line from the target-declaration path
    without limiting the multi-target fix itself.
    """
    func_start = MAKEFILE_RULES["func_start"]
    for recipe_line in ['\techo "note: this matters"', "\tcurl http://example.com/file", "\techo 10:30"]:
        assert not func_start.search(recipe_line), f"recipe line incorrectly matched as a target: {recipe_line!r}"


def test_makefile_func_start_known_limitation_variable_referenced_target_not_matched():
    """
    Documents a known, deliberately-NOT-fixed limitation: a
    variable-referenced target name (`$(TARGET): $(OBJECTS)`, also common in
    real Makefiles) is invisible to func_start -- `$`/`(`/`)` are outside the
    character class. NOT an oversight: test_language_standards_strict.py's
    test_makefile_func_start_and_macros_no_false_collision deliberately locks
    in that `$(1): $(2)` (a `define...endef` template's macro-positional-
    parameter placeholder) must NOT satisfy func_start, and this rule has no
    block/context tracking (line_exclusive lexical family) to distinguish
    that shape from a real `$(TARGET):` reference at the regex level.
    Safely separating the two would need a structured token (real variable
    names vs. bare positional-parameter digits), not a flat character-class
    widening -- judged out of scope for this issue.
    """
    func_start = MAKEFILE_RULES["func_start"]
    assert not func_start.search("$(TARGET): $(OBJECTS)"), (
        "documents current (expected, deliberately-not-fixed) regex behavior"
    )


def test_makefile_func_start_redos_immunity():
    """ReDoS sweep for the widened multi-target co-target loop and the assignment-operator lookahead."""
    func_start = MAKEFILE_RULES["func_start"]
    assert_redos_immune(func_start, ("a " * 200000) + ":=", timeout_sec=3.0)
    assert_redos_immune(func_start, "a" * 200000 + ":", timeout_sec=3.0)
    assert func_start.search("target:")


# ==============================================================================
# ARGS (args) -- Make's $(1)/$(call ...) macro-argument references.
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("echo $(1)", "$(1)"),
        ("echo $(10)", "$(10)"),
        ("echo $(0)", "$(0)"),  # macro's own name reference, real GNU Make semantics
        ("$(call foo,a,b)", "$(call foo"),
        ("$(call my-func, $(1))", "$(call my-func"),  # nested arg ref
        ("echo $1", "$1"),  # bare single-digit
    ],
    "invalid": [
        "echo $(TARGET)",  # ordinary variable, not positional
        "echo $@",  # automatic variable (target)
        "echo $<",  # automatic variable (first prereq)
        "echo $^",  # automatic variable (all prereqs)
        "echo $$1",  # escaped literal dollar -- was a real bug, now fixed
        "echo $$(1)",  # escaped literal dollar, parenthesized form
    ],
    "pathological": [
        ("echo $(call foo)", "$(call foo"),  # call with no args
        ("echo $1 and $2", "$1"),  # two independent refs on one line
        ("echo $PATH $(1)", "$(1)"),  # unrelated $ earlier on the line shouldn't interfere
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_makefile_args_valid(payload, expected_name):
    assert_valid_match(MAKEFILE_RULES["args"], payload, expected_name, "makefile.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_makefile_args_invalid(payload):
    assert_invalid_no_match(MAKEFILE_RULES["args"], payload, "makefile.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_makefile_args_pathological(payload, expected_name):
    assert_pathological_match(MAKEFILE_RULES["args"], payload, expected_name, "makefile.args")


def test_makefile_args_escaped_dollar_regression():
    """
    Regression test for a real bug (epic #813/#844): the rule had no
    awareness of Make's own `$$` escaping convention (a doubled `$` means "a
    literal `$`, unescaped, for whatever consumes this text next"). Recipe
    lines commonly write `$$1`/`$$(1)` specifically to pass a literal `$1`
    through to the SHELL (the shell's own first positional parameter) --
    unrelated to Make's own macro-call mechanism, since Make's own `$`
    expansion already happened one layer up. Fixed with a negative
    lookbehind so a `$` immediately preceded by another `$` can never start
    a match.
    """
    args = MAKEFILE_RULES["args"]
    assert not args.search("echo $$1"), "escaped bare positional regressed"
    assert not args.search("echo $$(1)"), "escaped parenthesized positional regressed"
    assert not args.search("echo $$(call foo)"), "escaped call form regressed"
    assert args.search("echo $1"), "real (unescaped) positional must still match"


def test_makefile_args_redos_immunity():
    """ReDoS sweep for the new negative lookbehind."""
    args = MAKEFILE_RULES["args"]
    assert_redos_immune(args, "$" * 200000 + "1", timeout_sec=3.0)
    assert args.search("$1")


# ==============================================================================
# NOTE: makefile has no class_start -- LANGUAGE_DEFINITIONS["makefile"]
# ["rules"]["class_start"] is None (strictly declarative, no OO constructs).
# No CLASS_CASES section, matching this issue's own scope (#844 only lists
# func_start, args, _dependency_capture as in-scope rules).
# ==============================================================================

# ==============================================================================
# DEPENDENCY (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("include config.mk", "config.mk"),  # carried-forward
        ("-include deps.mk", "deps.mk"),  # carried-forward
        ("sinclude deps.mk", "deps.mk"),  # BSD-style silent include
        ("  include foo.mk", "foo.mk"),  # space-indented
        ("include foo.mk # a comment", "foo.mk"),  # trailing comment excluded from capture
    ],
    "invalid": [
        "include_path := foo",  # carried-forward: substring-of-keyword lookalike
        "# include foo.mk",  # commented-out include
        "ifeq ($(INCLUDE_EXTRA),1)",  # substring lookalike, not a real include
    ],
    "pathological": [
        ("-include \n .depend", ".depend"),  # carried-forward: vertical spacing
        ("\tinclude /etc/motd", None),  # NOT a real match -- see regression test below
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_makefile_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(
        MAKEFILE_RULES["_dependency_capture"], payload, expected_path, "makefile._dependency_capture"
    )


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_makefile_dependency_capture_invalid(payload):
    assert_invalid_no_match(MAKEFILE_RULES["_dependency_capture"], payload, "makefile._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", [c for c in DEPENDENCY_CASES["pathological"] if c[1] is not None])
def test_makefile_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        MAKEFILE_RULES["_dependency_capture"], payload, expected_path, "makefile._dependency_capture"
    )


def test_makefile_dependency_capture_recipe_line_no_false_collision_regression():
    """
    Regression test for a real bug (epic #813/#844): the leading `[ \\t]*`
    allowed a TAB, but a tab-initial line is ALWAYS a recipe command in
    Make's own lexical rules (never a directive, absent a custom
    .RECIPEPREFIX) -- same root cause and fix as func_start's own multi-
    target regression fix. A recipe line whose command happens to be
    literally named "include"/"sinclude" (e.g. `\\tinclude /etc/motd`) was
    misidentified as a real include directive. Narrowed to `[ ]*` (spaces
    only).
    """
    dep = MAKEFILE_RULES["_dependency_capture"]
    assert not dep.search("\tinclude /etc/motd"), "tab-indented recipe line incorrectly matched as an include"
    assert dep.search("include /etc/motd"), "real (non-tab-indented) include must still match"


def test_makefile_dependency_capture_known_limitation_multiple_files_first_only():
    """
    Documents a known, NOT-fixed limitation: `include a.mk b.mk c.mk` (a
    single include directive listing multiple files, valid real Make
    syntax) only captures the first file (`a.mk`) -- the capture group's
    `[^\\s#]+` class stops at the first whitespace. Judged acceptable: every
    other language's _dependency_capture in this engine captures one path
    per match too, and a single-capture-group regex has no natural way to
    additionally report subsequent whitespace-separated files.
    """
    dep = MAKEFILE_RULES["_dependency_capture"]
    m = dep.search("include a.mk b.mk c.mk")
    assert m and m.group(1) == "a.mk", "documents current (expected, not-yet-fixed) first-file-only capture"


def test_makefile_dependency_capture_redos_immunity():
    """ReDoS sweep for the narrowed leading-whitespace class."""
    dep = MAKEFILE_RULES["_dependency_capture"]
    assert_redos_immune(dep, " " * 200000 + "include x.mk", timeout_sec=3.0)
    assert dep.search("include x.mk")

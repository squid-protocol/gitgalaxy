"""
Go extraction hardening (epic #813, issue #817). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for go in one file: func_start, args,
class_start, _dependency_capture. Migrated out of the four old monolithic
dict files (test_function_extraction_strict.py, test_args_extraction_strict.py,
test_class_extraction_strict.py, test_dependency_extraction_strict.py) --
go's entries were removed from those four when this file was added.
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

GO_RULES = LANGUAGE_DEFINITIONS["go"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        # Modern idiom (carried forward)
        ("func TargetFunc()", "TargetFunc"),
        ("func (s *MyStruct) TargetFunc(a int) error {", "TargetFunc"),
        # Syntax-era / feature coverage
        ("func (s MyStruct) TargetFunc(a int) error {", "TargetFunc"),  # value receiver
        (
            "func TargetFunc[T constraints.Ordered](a, b T) T {",
            "TargetFunc",
        ),  # Go 1.18+ generic function -- was a real bug, now fixed
        (
            "func TargetFunc[K comparable, V any](m map[K]V) []K {",
            "TargetFunc",
        ),  # multiple type params with constraints
        ("func (s *MyStruct[T]) TargetFunc(a T) T {", "TargetFunc"),  # generic receiver method
        ("func TargetFunc() (int, error) {", "TargetFunc"),  # multiple return values
        ("func TargetFunc(items ...int) {", "TargetFunc"),  # variadic params
        ("func TargetFunc() (result int) {", "TargetFunc"),  # named return value
        # Testing-framework-shaped functions that ARE real functions
        ("func TestTargetFunc(t *testing.T) {", "TestTargetFunc"),
        ("func BenchmarkTargetFunc(b *testing.B) {", "BenchmarkTargetFunc"),
        ("func ExampleTargetFunc() {", "ExampleTargetFunc"),
    ],
    "invalid": [
        "type TargetFunc struct",  # type decl lookalike
        "go TargetFunc()",  # goroutine launch
        "var TargetFunc =",  # var decl lookalike
        "return TargetFunc()",  # return call
    ],
    "pathological": [
        (
            "func \n ( \n s \n * \n MyStruct \n ) \n TargetFunc \n (",
            "TargetFunc",
        ),  # carried-forward: receiver split across newlines
        (
            "func \n TargetFunc \n [ \n T \n constraints.Ordered \n ] \n ( \n a, \n b \n T \n ) \n T \n {",
            "TargetFunc",
        ),  # generic function split at every plausible boundary
        (
            "func (s *MyStruct[T, U constraints.Ordered]) TargetFunc(a T, b U) {",
            "TargetFunc",
        ),  # generic receiver with multiple constrained type params
        (
            "func \n ( \n s \n * \n MyStruct[T] \n ) \n TargetFunc \n [ \n U \n any \n ] \n ( \n a \n T, \n b \n U \n ) \n {",
            "TargetFunc",
        ),  # generic receiver AND generic method, vertically split
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_go_func_start_valid(payload, expected_name):
    assert_valid_match(GO_RULES["func_start"], payload, expected_name, "go.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_go_func_start_invalid(payload):
    assert_invalid_no_match(GO_RULES["func_start"], payload, "go.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_go_func_start_pathological(payload, expected_name):
    assert_pathological_match(GO_RULES["func_start"], payload, expected_name, "go.func_start")


def test_go_func_start_generic_function_regression():
    """
    Regression test for a real bug (epic #813/#817), the known finding
    #817 started from: a top-level generic function's own type-parameter
    list (`func Foo[T constraints.Ordered](a, b T) T {`, mainstream Go
    since 1.18/2022) went straight from the captured name to `[ \\t\\n]*\\(`
    with no allowance for a `[...]` list in between, so the whole function
    was invisible to the engine. Generic *methods* with a receiver already
    matched by accident (the receiver's own `[^)]+` char class doesn't care
    about brackets), and class_start/args already had this exact
    step-over -- func_start was the outlier.
    """
    func_start = GO_RULES["func_start"]
    m = func_start.search("func TargetFunc[T constraints.Ordered](a, b T) T {")
    assert m and m.group(1) == "TargetFunc", "generic function detection regressed"


def test_go_func_start_redos_immunity():
    """ReDoS sweep for the new generic type-parameter step-over."""
    func_start = GO_RULES["func_start"]
    assert_redos_immune(func_start, "func Foo[" + "a" * 100000, timeout_sec=3.0)
    assert func_start.search("func Foo[T constraints.Ordered](a, b T) T {")


def test_go_func_start_known_limitation_raw_string_lookalike_still_matches_at_regex_level():
    """
    Documents a known, NOT-fixed limitation: func_start's own regex has no
    string/comment awareness, so function-shaped text inside a Go raw
    string literal (backtick-delimited, commonly used for embedded
    SQL/templates/regex) that happens to land at true line start still
    matches -- the same architectural class of bug confirmed for
    javascript/typescript template literals and Java 15+ text blocks
    (recurring bug class 3 in how_to_harden_extraction.md), now confirmed
    on a THIRD, unrelated syntax feature. The real fix (matching against
    shielded code) lives in detector.py's _slice_by_braces and is currently
    gated to javascript/typescript only; broadening it to other Mode B
    languages (go included) is tracked as its own future audited
    follow-up, not fixed here.
    """
    func_start = GO_RULES["func_start"]
    raw_string = "s := `\nfunc TargetFunc() {\n`"
    assert func_start.search(raw_string), "documents current (expected, pipeline-level-fixed-elsewhere) regex behavior"


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("func TargetFunc(a int, b string) error {", "TargetFunc"),
        ("func (s *Server) TargetFunc(ctx context.Context) {", "TargetFunc"),
        ("func TargetFunc[T constraints.Ordered](a, b T) T {", "TargetFunc"),  # generic function args
    ],
    "invalid": [
        "TargetFunc(a, b)",
        "if err != nil {",
    ],
    "pathological": [
        (
            # NOTE: expected_name is None here (not "TargetFunc") deliberately --
            # args has no capture group at all for go, so the pathological-tier
            # assertion falls back to substring-checking the WHOLE match. This
            # specific vertically-split-receiver-then-newline-then-name payload
            # (carried forward from the original monolithic suite) actually
            # anchors to the receiver's own parens instead of the real
            # parameter list (`func \n (s *Server)` is the full match) --
            # the original harness's `test_pathological_args_extraction` never
            # checked the name for ANY language's args pathological tier (only
            # `match is not None`), so this imprecision predates this pass and
            # is the same "args proves capture, not name-anchoring" convention
            # already documented for typescript's own args pathological cases.
            "func \n (s *Server) \n TargetFunc \n [T any] \n (\n  ctx context.Context,\n  cb func(err error)\n)",
            None,
        ),
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_go_args_valid(payload, expected_name):
    assert_valid_match(GO_RULES["args"], payload, expected_name, "go.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_go_args_invalid(payload):
    assert_invalid_no_match(GO_RULES["args"], payload, "go.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_go_args_pathological(payload, expected_name):
    assert_pathological_match(GO_RULES["args"], payload, expected_name, "go.args")


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("type TargetEntity struct {", "TargetEntity"),
        ("type TargetEntity interface {", "TargetEntity"),
        ("type TargetEntity[T any] struct", "TargetEntity"),
        ("type TargetEntity[T constraints.Ordered] interface {", "TargetEntity"),  # generic w/ constraint
        ("type TargetEntity[K comparable, V any] struct {", "TargetEntity"),  # multiple type params
    ],
    "invalid": [
        "type TargetEntity func()",
        "var x struct {}",
        "func (s *TargetEntity) method()",
    ],
    "pathological": [
        (
            "type \n TargetEntity \n [ \n T \n any \n ] \n struct \n {",
            "TargetEntity",
        ),  # carried-forward: struct broken across lines
        (
            "type \n TargetEntity \n [ \n K \n comparable, \n V \n any \n ] \n interface \n {",
            "TargetEntity",
        ),  # multi-param generic interface, vertically split
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_go_class_start_valid(payload, expected_name):
    assert_valid_match(GO_RULES["class_start"], payload, expected_name, "go.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_go_class_start_invalid(payload):
    assert_invalid_no_match(GO_RULES["class_start"], payload, "go.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_go_class_start_pathological(payload, expected_name):
    assert_pathological_match(GO_RULES["class_start"], payload, expected_name, "go.class_start")


# ==============================================================================
# DEPENDENCY (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ('import "net/http"', "net/http"),
        ('import fmt "fmt"', "fmt"),
        ('import _ "database/sql/driver"', "database/sql/driver"),  # blank import
        ('import . "fmt"', "fmt"),  # dot import
    ],
    "invalid": [
        'var importPath = "foo"',
    ],
    "pathological": [
        (
            'import \n ( \n  customAlias \n "my_internal_pkg/core_lib" \n )',
            "my_internal_pkg/core_lib",
        ),  # carried-forward: vertical aliased import in block
        (
            'import \n ( \n  _ \n "database/sql/driver" \n )',
            "database/sql/driver",
        ),  # vertical blank import in block
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_go_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(GO_RULES["_dependency_capture"], payload, expected_path, "go._dependency_capture")


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_go_dependency_capture_invalid(payload):
    assert_invalid_no_match(GO_RULES["_dependency_capture"], payload, "go._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_go_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        GO_RULES["_dependency_capture"], payload, expected_path, "go._dependency_capture"
    )


def test_go_dependency_capture_known_limitation_raw_string_lookalike_still_matches_at_regex_level():
    """
    Companion to func_start's own raw-string known-limitation test above:
    _dependency_capture is matched against fully unshielded raw file
    content for every language (see the java pass's #816 finding), so an
    `import "...";`-shaped line inside a Go raw string literal at true line
    start still produces a phantom dependency-graph edge. Documented, not
    fixed here -- see how_to_harden_extraction.md's recurring bug class 10.
    """
    dependency_capture = GO_RULES["_dependency_capture"]
    raw_string = 's := `\nimport "net/http"\n`'
    assert dependency_capture.search(raw_string), "documents current (accepted, unfixed) regex behavior"

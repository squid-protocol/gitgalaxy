"""
PowerShell extraction hardening (epic #813, issue #834). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for powershell in one file: func_start,
args, class_start, _dependency_capture. Migrated out of the four old
monolithic dict files (test_function_extraction_strict.py,
test_args_extraction_strict.py, test_class_extraction_strict.py,
test_dependency_extraction_strict.py) -- powershell's entries were removed
from those four when this file was added. (test_class_extraction_strict.py
had no powershell entry at all -- class_start had zero prior test coverage.)
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

POWERSHELL_RULES = LANGUAGE_DEFINITIONS["powershell"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        # Modern idiom (carried forward)
        ("function TargetFunc {", "TargetFunc"),
        ("filter TargetFunc {", "TargetFunc"),
        # Syntax-era / feature coverage
        ("workflow TargetFunc {", "TargetFunc"),  # PS Workflow (Windows PowerShell era)
        ("[int] TargetFunc() {", "TargetFunc"),  # PS class typed method
        (
            "[Dictionary[string,int]] TargetFunc() {",
            "TargetFunc",
        ),  # nested generic return type -- was a real bug, now fixed
        ("TargetFunc([string]$name) {", "TargetFunc"),  # PS class constructor -- was a real bug, now fixed
        ("TargetFunc() {", "TargetFunc"),  # parameterless constructor -- was a real bug, now fixed
        ("function global:TargetFunc {", "TargetFunc"),  # scope-qualified -- was a real bug, now fixed
        ("function script:TargetFunc {", "TargetFunc"),
    ],
    "invalid": [
        "class TargetFunc",  # class decl lookalike
        "Invoke-Command",  # bare cmdlet call lookalike
        "$TargetFunc =",  # variable assignment lookalike
        "TargetFunc -a 'foo'",  # bare cmdlet-style call (space-separated args, no parens)
        "TargetFunc($a, $b)",  # bare call w/ parens, no trailing body -- must not collide with the constructor fix
        "# function TargetFunc {",  # commented-out declaration
        "if ($a -eq $b) {",  # control-flow lookalike -- must not collide with the constructor fix
        "while ($x -lt 10) {",
        "switch ($x) {",
        "foreach ($item in $list) {",
    ],
    "pathological": [
        ("function \n TargetFunc \n {", "TargetFunc"),  # carried-forward: vertical spacing
        (
            "[System.Collections.Generic.List[string]] \n TargetFunc \n (\n) \n {",
            "TargetFunc",
        ),  # nested generic return type, vertically split
        (
            "TargetFunc \n (\n  [string]$name \n) \n {",
            "TargetFunc",
        ),  # constructor, vertically split
        (
            "function \n global:TargetFunc \n {",
            "TargetFunc",
        ),  # scope-qualifier kept as one token (realistic -- see regression test below for why a
        # split INSIDE "global:TargetFunc" itself is deliberately not attempted)
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_powershell_func_start_valid(payload, expected_name):
    assert_valid_match(POWERSHELL_RULES["func_start"], payload, expected_name, "powershell.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_powershell_func_start_invalid(payload):
    assert_invalid_no_match(POWERSHELL_RULES["func_start"], payload, "powershell.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_powershell_func_start_pathological(payload, expected_name):
    assert_pathological_match(POWERSHELL_RULES["func_start"], payload, expected_name, "powershell.func_start")


def test_powershell_func_start_constructor_regression():
    """
    Regression test for a real bug (epic #813/#834): PS class constructors
    (`Foo([string]$name) { ... }`) have neither a leading `function` keyword
    nor a return-type bracket, so they were entirely invisible to this rule.
    Fixed as a third alternative anchored to a trailing `{` specifically so
    it can't also match a bare call statement.
    """
    func_start = POWERSHELL_RULES["func_start"]
    m = func_start.search("Foo([string]$name) {")
    assert m and m.group(m.lastindex) == "Foo", "constructor detection regressed"


def test_powershell_func_start_constructor_fix_no_control_flow_collision_regression():
    """
    Regression test for a false positive introduced (then fixed) by the
    constructor fix above: PowerShell's own control-flow statements (`if
    (...) {`, `while (...) {`, `switch (...) {`, `for (...) {`, `foreach
    (...) {`, `elseif (...) {`) share the exact "identifier, parens,
    trailing brace" shape a constructor call has. Caught by hand-testing the
    fix's own invalid case before shipping (not by crucible) -- fixed with a
    negative-lookahead keyword exclusion.
    """
    func_start = POWERSHELL_RULES["func_start"]
    for stmt in [
        "if ($a -eq $b) {",
        "while ($x -lt 10) {",
        "switch ($x) {",
        "for ($i=0; $i -lt 10; $i++) {",
        "foreach ($item in $list) {",
        "elseif ($x) {",
    ]:
        assert not func_start.search(stmt), f"control-flow statement incorrectly matched as a constructor: {stmt!r}"


def test_powershell_func_start_scope_qualifier_regression():
    """
    Regression test for a real bug (epic #813/#834): PowerShell allows an
    explicit scope modifier before a function name (`function global:Foo
    {}`, also `script:`/`local:`/`private:`). The identifier class doesn't
    include `:`, so the capture greedily consumed only the scope keyword
    itself (e.g. "global") as if it were the function name -- silently
    wrong, not just a non-match.
    """
    func_start = POWERSHELL_RULES["func_start"]
    m = func_start.search("function global:TargetFunc {")
    assert m and m.group(m.lastindex) == "TargetFunc", "scope-qualified function name detection regressed"


def test_powershell_func_start_redos_immunity():
    """ReDoS sweep for the new constructor alternative and its keyword-exclusion lookahead."""
    func_start = POWERSHELL_RULES["func_start"]
    assert_redos_immune(func_start, "Foo(" + "(" * 100000, timeout_sec=3.0)
    assert_redos_immune(func_start, "iffoo(" + "(" * 100000, timeout_sec=3.0)
    assert func_start.search("Foo([string]$name) {")


def test_powershell_func_start_known_limitation_here_string_lookalikes_still_match_at_regex_level():
    """
    Documents a known, NOT-fixed limitation: func_start's own regex has no
    string/comment awareness, so function-shaped text inside a PowerShell
    here-string (`@"..."@`) that happens to land at true line start still
    matches -- the same architectural class of bug confirmed for
    javascript/typescript template literals, Java text blocks, Go/Rust raw
    strings, C# verbatim/raw strings, Kotlin/Swift/Scala raw or
    triple-quoted strings (recurring bug class 3 in
    how_to_harden_extraction.md), now confirmed on a TENTH language.
    Not fixed here -- tracked as its own future audited follow-up in the epic.
    """
    func_start = POWERSHELL_RULES["func_start"]
    here_string = '$s = @"\nfunction TargetFunc {\n"@'
    assert func_start.search(here_string), "documents current (expected, pipeline-level-fixed-elsewhere) regex behavior"


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("param([string]$a, [int]$b)", "param"),
        ("function TargetFunc ([string]$a) {", "TargetFunc"),
        (
            "param($Config = (Get-DefaultConfig))",
            "param",
        ),  # nested paren in default-value expression -- was a real bug, now fixed
        ("Foo([string]$name) { }", "Foo"),  # PS class constructor -- was a real bug, now fixed
        ("function global:TargetFunc($a) { }", "TargetFunc"),  # scope-qualified -- was a real bug, now fixed
    ],
    "invalid": [
        "TargetFunc -a 'foo'",  # bare cmdlet-style call, space-separated args
        "if ($a -eq $b) {",  # control-flow lookalike -- must not collide with the constructor fix
        "while ($x -lt 10) {",
        "switch ($x) {",
        "foreach ($item in $list) {",
    ],
    "pathological": [
        (
            "function \n TargetFunc \n (\n  [Parameter(Mandatory=$true)]\n  [ValidateNotNullOrEmpty()]\n  [string[]]$items\n)",
            "TargetFunc",
        ),  # carried-forward: extreme parameter attribute stacking
        (
            "TargetFunc \n (\n  [string]$name \n) \n {",
            "TargetFunc",
        ),  # constructor, vertically split
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_powershell_args_valid(payload, expected_name):
    assert_valid_match(POWERSHELL_RULES["args"], payload, expected_name, "powershell.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_powershell_args_invalid(payload):
    assert_invalid_no_match(POWERSHELL_RULES["args"], payload, "powershell.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_powershell_args_pathological(payload, expected_name):
    assert_pathological_match(POWERSHELL_RULES["args"], payload, expected_name, "powershell.args")


def test_powershell_args_nested_paren_default_value_regression():
    """
    Regression test for a real bug (epic #813/#834): both `param(...)` and
    `function NAME(...)` alternatives used the flat `\\([^)]*\\)`,
    truncating at the FIRST `)` -- breaking on a realistic default-value
    expression containing its own parens (`param($Config =
    (Get-DefaultConfig))`, extremely common for computed defaults). Widened
    to the established one-level-nesting idiom.
    """
    args = POWERSHELL_RULES["args"]
    m = args.search("param($Config = (Get-DefaultConfig))")
    assert m and m.group(0) == "param($Config = (Get-DefaultConfig))", "nested-paren default value regressed"


def test_powershell_args_constructor_no_control_flow_collision_regression():
    """Regression test for the same false-positive fix as func_start's own test above."""
    args = POWERSHELL_RULES["args"]
    for stmt in ["if ($a -eq $b) {", "while ($x -lt 10) {", "switch ($x) {", "foreach ($item in $list) {"]:
        assert not args.search(stmt), f"control-flow statement incorrectly matched as constructor args: {stmt!r}"


def test_powershell_args_known_limitation_two_level_paren_nesting_not_supported():
    """
    Documents a known, deliberately-NOT-fixed limitation consistent with the
    doc's established "one-level-nesting" standard (recurring class 1): a
    default-value expression with TWO levels of nested parens (`param($Config
    = (Join-Path (Get-Location) 'x.json'))`) does not match. This mirrors
    every other language's Rule-11 fix in this codebase -- only one level of
    real nesting is checked/supported, not arbitrary depth.
    """
    args = POWERSHELL_RULES["args"]
    two_level = "param($Config = (Join-Path (Get-Location) 'x.json'))"
    assert not args.search(two_level), "documents current (expected, one-level-nesting-only) regex behavior"


def test_powershell_args_redos_immunity():
    """ReDoS sweep for the widened paren nesting and the new constructor alternative."""
    args = POWERSHELL_RULES["args"]
    assert_redos_immune(args, "param(" + "(" * 100000, timeout_sec=3.0)
    assert_redos_immune(args, "Foo(" + "(" * 100000, timeout_sec=3.0)
    assert args.search("param($Config = (Get-DefaultConfig))")


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
# NOTE: test_class_extraction_strict.py had NO powershell entry at all --
# class_start had zero prior test coverage before this file.
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("class TargetEntity {", None),
        ("class TargetEntity : Base {", None),  # inheritance
        ("class TargetEntity : Base, IDisposable {", None),  # inheritance + interface list
        ("enum TargetEntity { A; B }", None),
    ],
    "invalid": [
        "$obj = [TargetEntity]::new()",  # type-accelerator instantiation lookalike
        "New-Object -TypeName TargetEntity",  # instantiation-cmdlet lookalike
        "def classMethod()",  # unrelated-language lookalike (defensive; not real PS syntax either way)
        "# class TargetEntity {",  # commented-out declaration
    ],
    "pathological": [
        (
            "class \n TargetEntity \n : \n Base, \n IDisposable \n {",
            "TargetEntity",
        ),  # vertical inheritance + interface list
        ("enum \n TargetEntity \n {", "TargetEntity"),  # vertical enum
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_powershell_class_start_valid(payload, expected_name):
    assert_valid_match(POWERSHELL_RULES["class_start"], payload, expected_name, "powershell.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_powershell_class_start_invalid(payload):
    assert_invalid_no_match(POWERSHELL_RULES["class_start"], payload, "powershell.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_powershell_class_start_pathological(payload, expected_name):
    assert_pathological_match(POWERSHELL_RULES["class_start"], payload, expected_name, "powershell.class_start")


# ==============================================================================
# DEPENDENCY (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("Import-Module ActiveDirectory", "ActiveDirectory"),
        ("using namespace System.Net", "System.Net"),
        (". .\\script.ps1", ".\\script.ps1"),  # dot-sourcing
        ("Import-Module MyModule -Force", "MyModule"),  # trailing flag must not get swallowed
        (
            "Import-Module 'C:\\Program Files\\MyModule\\MyModule.psd1'",
            "C:\\Program Files\\MyModule\\MyModule.psd1",
        ),  # quoted path with a space -- was a real bug, now fixed
        (
            'using module "C:\\Program Files\\MyModule\\MyModule.psd1"',
            "C:\\Program Files\\MyModule\\MyModule.psd1",
        ),  # double-quoted variant of the same fix
    ],
    "invalid": [
        "Write-Host 'Import-Module'",  # keyword appears only inside an unrelated cmdlet's string argument
        "important = 5",  # substring-of-keyword lookalike
    ],
    "pathological": [
        ("using \n module \n 'MyCustomModule.psm1'", "MyCustomModule.psm1"),  # carried-forward: vertical spacing
        (
            "Import-Module \n 'C:\\Program Files\\Modules\\Foo.psd1'",
            "C:\\Program Files\\Modules\\Foo.psd1",
        ),  # vertical spacing + quoted path with a space
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_powershell_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(
        POWERSHELL_RULES["_dependency_capture"], payload, expected_path, "powershell._dependency_capture"
    )


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_powershell_dependency_capture_invalid(payload):
    assert_invalid_no_match(POWERSHELL_RULES["_dependency_capture"], payload, "powershell._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_powershell_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        POWERSHELL_RULES["_dependency_capture"], payload, expected_path, "powershell._dependency_capture"
    )


def test_powershell_dependency_capture_quoted_path_with_space_regression():
    """
    Regression test for a real bug (epic #813/#834): the quoted-path
    branches used `['\"]?...['\"]?` -- an OPTIONAL quote pair around a
    capture class that excludes `\\s` regardless of whether a quote is
    actually present. So a quoted path containing a space (the extremely
    common Windows `'C:\\Program Files\\...'` shape) silently truncated at
    the first space. Fixed with real per-quote-style alternatives.
    """
    dep = POWERSHELL_RULES["_dependency_capture"]
    m = dep.search("Import-Module 'C:\\Program Files\\MyModule\\MyModule.psd1'")
    captured = next((g for g in m.groups() if g), None) if m else None
    assert captured == "C:\\Program Files\\MyModule\\MyModule.psd1", "quoted-path-with-space capture regressed"


def test_powershell_dependency_capture_redos_immunity():
    """ReDoS sweep for the new quoted-path alternatives."""
    dep = POWERSHELL_RULES["_dependency_capture"]
    assert_redos_immune(dep, "Import-Module '" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(dep, "Import-Module " + "a" * 100000, timeout_sec=3.0)
    assert dep.search("Import-Module 'C:\\Program Files\\MyModule\\MyModule.psd1'")


def test_powershell_dependency_capture_comment_lookalike_structurally_immune_negative_result():
    """
    Documents a confirmed-safe NEGATIVE result (same shape as c's #822
    finding, recurring class 27): unlike most languages,
    `_dependency_capture`'s `^[ \\t]*` anchor requires ONLY whitespace before
    the literal `Import-Module`/`using`/`.` keyword, and PowerShell's `#`
    comment marker is not whitespace -- so a commented-out import
    (`# Import-Module Foo`) does NOT produce a phantom dependency-graph edge
    here, structurally, without needing any shielding fix.
    """
    dep = POWERSHELL_RULES["_dependency_capture"]
    assert not dep.search("# Import-Module Foo"), "comment-lookalike immunity regressed"


def test_powershell_dependency_capture_known_limitation_here_string_lookalike_still_matches_at_regex_level():
    """
    Documents a known, NOT-fixed limitation shared by every language, not
    just powershell (recurring bug class 10 in how_to_harden_extraction.md):
    `_dependency_capture` is matched against raw, unshielded file content for
    every language, unconditionally. Unlike a comment (blocked by the `^[
    \\t]*` anchor, see the confirmed-immune test above), a PowerShell
    here-string's (`@"..."@`) inner content lands at true line start with no
    blocking marker, so import-shaped text inside one still produces a
    phantom dependency-graph edge.
    """
    dep = POWERSHELL_RULES["_dependency_capture"]
    here_string = '$s = @"\nImport-Module Foo\n"@'
    assert dep.search(here_string), "documents current (expected, pipeline-wide, not-yet-fixed) regex behavior"

"""powershell strict structural-signature coverage.

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

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


POWERSHELL_RULES = LANGUAGE_DEFINITIONS["powershell"]["rules"]

# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


_POWERSHELL_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if ($x) {", None),
    ("args", "function foo($x) {", None),
    ("structural_boundaries", "function foo {", None),
    ("func_start", "function Foo {", None),
    ("class_start", "class Foo {", None),
    ("safety", "try { risky() } catch {}", None),
    ("safety_bypasses", "Out-Null", None),
    ("high_risk_execution", "Invoke-Expression $cmd", None),
    ("io", "Get-Content $path", None),
    ("api", "Export-ModuleMember -Function Foo", None),
    ("state_mutation", "$x = 5", None),
    ("dead_code", "# function Foo {}", "# just a note"),
    ("doc", ".SYNOPSIS", None),
    ("test", "Should -Be 5", None),
    ("concurrency", "Start-Job { Get-Process }", None),
    ("ui_framework", "Out-GridView", None),
    ("closures", "{ $_.Name }", None),
    ("globals", "$global:x = 1", None),
    ("decorators", "[Parameter(Mandatory=$true)]", None),
    ("generics", "[List[int]]::new()", None),
    ("comprehensions", "$x | Where-Object { $_ -gt 5 }", None),
    ("scientific", "[Math]::Sqrt(4)", None),
    ("reflection_metaprogramming", "Add-Type -TypeDefinition $src", None),
    ("import", "Import-Module Foo", None),
    ("ownership", "# Author: Jane Doe", None),
    ("planned_debt", "# TODO: refactor", None),
    ("fragile_debt", "# HACK: workaround", None),
    ("spec_exposure", "[SPEC-123]", None),
    ("ssr_boundaries", "New-PodeServer", None),
    ("events", "Register-ObjectEvent $obj EventName", None),
    ("dependency_injection", "Get-Service Foo", None),
    ("pointers", "[IntPtr]::Zero", None),
    ("memory_alloc", "[System.Runtime.InteropServices.Marshal]::AllocHGlobal(10)", None),
    ("telemetry", "Write-Verbose 'msg'", None),
    ("debug_prints", "Write-Host 'msg'", None),
    ("explicit_casts", "[int]$x", None),
    ("panics_and_aborts", "throw 'error'", None),
    ("thread_sleeps", "Start-Sleep 5", None),
    ("bitwise_ops", "$a -band $b", None),
    ("sync_locks", "[System.Threading.Monitor]::Enter($lock)", None),
    ("immutability_locks", "New-Variable Foo -Option Constant", None),
    ("cleanup", "Remove-Item $path", None),
    ("encapsulation", "hidden [int] $x", None),
    ("listeners", "Register-ObjectEvent $obj EventName", None),
    ("test_skip", "It 'test' -Skip", None),
    ("serialization_parsing", "ConvertFrom-Json $str", None),
    ("regex_execution", "$x -match $pattern", None),
    ("time_date_logic", "Get-Date", None),
    ("ipc_rpc_bridges", "Invoke-Command -ScriptBlock {}", None),
]

# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


@pytest.mark.parametrize("signature,positive,negative", _POWERSHELL_SIMPLE_CASES)
def test_powershell_signature_positive_and_negative(signature, positive, negative):
    pattern = POWERSHELL_RULES[signature]
    assert pattern is not None, f"powershell's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"powershell {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"powershell {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


def test_powershell_concurrency_parallel_leading_boundary_regression():
    """
    Regression test: `-Parallel` starts with `-` (non-word), so the
    shared leading \\b could only fire when a word char immediately
    preceded the `-` -- never true for how this ForEach-Object flag is
    actually written (always preceded by whitespace). PS7's parallel
    pipeline feature never matched at all.
    """
    pattern = POWERSHELL_RULES["concurrency"]
    assert pattern.search("1..10 | ForEach-Object -Parallel { $_ }"), "-Parallel still didn't match"
    assert pattern.search("Start-Job { Get-Process }")
    assert pattern.search("[System.Management.Automation.RunspaceFactory]::CreateRunspacePool()")


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


def test_powershell_import_dot_sourcing_leading_boundary_regression():
    """
    Regression test: the dot-sourcing alternative (`. .\\script.ps1`)
    starts with `.` (non-word), so the shared leading \\b could only fire
    when a word char immediately preceded the `.` -- never true for how
    dot-sourcing is actually written (always preceded by whitespace or a
    line start). This common PowerShell module-loading idiom never
    matched at all.
    """
    pattern = POWERSHELL_RULES["import"]
    assert pattern.search(". .\\script.ps1"), "dot-sourcing still didn't match"
    assert pattern.search(". ./lib/helpers.ps1")
    assert pattern.search("Import-Module Foo")


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


def test_powershell_regex_execution_operators_leading_boundary_regression():
    """
    Regression test: `-match`/`-replace`/`-split` all start with `-`
    (non-word), so the shared leading \\b could only fire when a word
    char immediately preceded the `-` -- never true for how these
    operators are actually written (always preceded by whitespace, after
    the left-hand operand). PowerShell's three most common native regex
    operators never matched at all.
    """
    pattern = POWERSHELL_RULES["regex_execution"]
    assert pattern.search("$x -match $pattern"), "-match still didn't match"
    assert pattern.search("$x -replace 'a', 'b'")
    assert pattern.search("$x -split ','")
    assert pattern.search("Select-String -Pattern $p")
    assert pattern.search("[regex]::Match($x, $p)")


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


def test_powershell_func_start_generic_return_type_regression():
    """
    Regression test: the return-type bracket class `[^\\]]+` couldn't
    represent one level of nested brackets, so a PS class method with a
    generic .NET return type never matched at all, unlike the identical
    non-generic form which did.
    """
    pattern = POWERSHELL_RULES["func_start"]
    assert pattern.search("[Dictionary[string,int]] GetMap() {"), "generic return type still didn't match"
    assert pattern.search("[System.Collections.Generic.List[string]] GetItems() {")
    assert pattern.search("[int] GetValue() {"), "non-generic return type regressed"
    assert pattern.search("function Foo() {")


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


def test_powershell_closures_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: the unbounded
    `[^}]*` before the closing `}`, combined with unanchored search, is
    quadratic on payloads with many `{` and no matching `}` (each of the
    n starting positions scans ~n chars before failing). Confirmed
    genuine O(n^2) scaling (~0.002s/0.007s/0.03s/0.11s/0.46s at
    n=2k/4k/8k/16k/32k, ~4x per doubling) before being bounded.
    """
    pattern = POWERSHELL_RULES["closures"]
    poison = "{" * 80000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)

    assert pattern.search("{ $_.Name }")
    assert pattern.search("$sb = { param($x, $y) $x + $y }")
    assert pattern.search("Get-ChildItem | Where-Object { $_.Length -gt 100 }")


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


def test_powershell_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents the automated ambiguity sweep's findings for powershell
    (class_start<->dead_code on 'class', dead_code<->func_start on
    'function', decorators<->doc on 'parameter') -- all confirmed false
    positives via direct empirical verification: dead_code requires an
    immediately-preceding `#`/`<#` comment marker before the keyword,
    which class_start/func_start's line-start anchors (`^[ \\t]*`)
    structurally exclude (a comment marker is never whitespace), so a
    live declaration and its commented-out form never collide. Similarly,
    decorators' `[Parameter(...)]` attribute syntax and doc's
    `.PARAMETER` comment-based help token are structurally distinct (one
    requires a bracket-wrapped call with parens, the other a leading dot)
    and never match the same text.
    """
    class_start = POWERSHELL_RULES["class_start"]
    func_start = POWERSHELL_RULES["func_start"]
    dead_code = POWERSHELL_RULES["dead_code"]
    decorators = POWERSHELL_RULES["decorators"]
    doc = POWERSHELL_RULES["doc"]

    live_class = "class Foo { }"
    assert class_start.search(live_class)
    assert not dead_code.search(live_class)
    commented_class = "# class Foo { }"
    assert dead_code.search(commented_class)
    assert not class_start.search(commented_class)

    live_func = "function Do-Thing { }"
    assert func_start.search(live_func)
    assert not dead_code.search(live_func)
    commented_func = "# function Do-Thing { }"
    assert dead_code.search(commented_func)
    assert not func_start.search(commented_func)

    attribute = "[Parameter(Mandatory=$true)]"
    assert decorators.search(attribute)
    assert not doc.search(attribute)
    comment_help = ".PARAMETER Name"
    assert doc.search(comment_help)
    assert not decorators.search(comment_help)


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


def test_powershell_explicit_casts_and_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (C-style cast syntax
    overlapping pointer-type tokens): powershell's explicit_casts
    (`[int]`/`[string]`/etc.) and pointers (`[IntPtr]`/`[UIntPtr]`/
    `[ref]`) use disjoint bracketed-keyword sets and never match the
    same text.
    """
    casts = POWERSHELL_RULES["explicit_casts"]
    pointers = POWERSHELL_RULES["pointers"]
    assert casts.search("[int]$x")
    assert not casts.search("[IntPtr]::Zero"), "explicit_casts incorrectly matched an IntPtr token"
    assert pointers.search("[IntPtr]::Zero")
    assert not pointers.search("[int]$x"), "pointers incorrectly matched an explicit cast"


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


def test_powershell_test_and_regex_execution_intentional_overlap():
    """
    Known ambiguity pattern from the issue template (test-assertion
    syntax overlapping regex-execution operators): unlike the
    explicit_casts/pointers pair above, this one is a genuine, intentional
    overlap rather than a false collision. Pester's `Should -Match`
    assertion literally performs a regex match under the hood, so a line
    like `Should -Match 'foo'` is correctly classified as both a test
    assertion AND regex execution -- both signatures are expected to fire
    on the same text, and that is not a bug.
    """
    test = POWERSHELL_RULES["test"]
    regex_execution = POWERSHELL_RULES["regex_execution"]
    pester_match_assertion = "Should -Match 'foo'"
    assert test.search(pester_match_assertion)
    assert regex_execution.search(pester_match_assertion)


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


def test_powershell_func_start_and_generics_no_false_collision():
    """
    Known ambiguity pattern from the issue template (function-signature
    type annotations overlapping generic type-parameter syntax):
    func_start's return-type form correctly recognizes non-generic and
    (after the fix above) generic return types on class methods, while
    generics' own signature (which requires a bracket immediately
    followed by another `[...]]`) does not fire on the plain non-generic
    form, so the two only co-fire on text that is genuinely both a
    function start and a generic type usage.
    """
    func_start = POWERSHELL_RULES["func_start"]
    generics = POWERSHELL_RULES["generics"]

    plain_method = "[int] GetValue() {"
    assert func_start.search(plain_method)
    assert not generics.search(plain_method)

    generic_method = "[Dictionary[string,int]] GetMap() {"
    assert func_start.search(generic_method)
    assert generics.search(generic_method)


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


def test_powershell_bitwise_ops_and_closures_no_false_collision():
    """
    Known ambiguity pattern from the issue template (bitwise-operator
    tokens overlapping closure/scriptblock brace syntax): powershell's
    bitwise_ops uses distinct `-band`/`-bor`/`-bxor`/`-bnot`/`-shl`/`-shr`
    operator tokens, structurally unrelated to closures' `{ ... }`
    scriptblock delimiters, so neither fires on text containing only the
    other's construct.
    """
    bitwise_ops = POWERSHELL_RULES["bitwise_ops"]
    closures = POWERSHELL_RULES["closures"]

    assert bitwise_ops.search("$a -band $b")
    assert not closures.search("$a -band $b")

    assert closures.search("{ $_.Name }")
    assert not bitwise_ops.search("{ $_.Name }")

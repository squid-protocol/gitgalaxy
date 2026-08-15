"""
C# extraction hardening (epic #813, issue #820). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for csharp in one file: func_start,
args, class_start, _dependency_capture. Migrated out of the four old
monolithic dict files (test_function_extraction_strict.py,
test_args_extraction_strict.py, test_class_extraction_strict.py,
test_dependency_extraction_strict.py) -- csharp's entries were removed
from those four when this file was added.
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

CSHARP_RULES = LANGUAGE_DEFINITIONS["csharp"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        # Modern idiom (carried forward)
        ("public async Task<List<string>> TargetFunc()", "TargetFunc"),
        ("protected override void TargetFunc(int x)", "TargetFunc"),
        ("internal static readonly Dictionary<int, string> TargetFunc()", "TargetFunc"),
        # Syntax-era / feature coverage
        (
            "public List<T> TargetFunc<T>() where T : IComparable<T> {",
            "TargetFunc",
        ),  # generic method, where-clause constraint after params
        ("public void TargetFunc() => DoWork();", "TargetFunc"),  # expression-bodied method
        # Testing-framework-shaped functions that ARE real functions
        ("[Fact]\npublic void TargetFunc() {", "TargetFunc"),  # xUnit [Fact]
        ("[Theory]\n[InlineData(1, 2)]\npublic void TargetFunc(int a, int b) {", "TargetFunc"),  # xUnit [Theory]
        # #1418: Bodyless interface/abstract method declarations ending in a bare ';'
        ("void TargetFunc(int x);", "TargetFunc"),
        ("public abstract void TargetFunc(int x);", "TargetFunc"),
    ],
    "invalid": [
        "public class TargetFunc {",  # class decl lookalike
        "if (TargetFunc == null)",  # if lookalike
        "new TargetFunc()",  # instantiation
        # #1314: contextual keywords directly preceding a `(` in non-function
        # constructs were captured whole as phantom functions literally named
        # after the keyword (confirmed via real Roslyn corpus source --
        # language-crucible/data/csharp/roslyn/{CSharpCompilation,Workspace}.cs).
        "static (oldSolution, data) => oldSolution.AddDocuments(data.documentInfos),",  # static lambda (C# 9+)
        "var (updated, _) = SetCurrentSolution(oldSolution, newSolution);",  # tuple deconstruction
        "catch (Exception e) when (e is InvalidOperationException)",  # exception filter
        "if (binaryKind is BinaryOperatorKind.Equal or BinaryOperatorKind.NotEqual)",  # pattern combinator
        # #1314: a `foreach`/`for`/`using`/etc. statement header got silently swallowed
        # token-by-token as fake "return type" tokens, letting the walk land on the loop
        # expression's own receiver+method (`changes.GetAddedProjects`) as if it were a
        # real function name -- group 1's dot-permitting identifier (meant for explicit
        # interface implementations like `IFoo.DoWork`) also legalized `receiver.Method`.
        "foreach (var addedProject in changes.GetAddedProjects())",  # loop header, not a function
        # #1418: Multi-line bare call statement ending in ';' with no modifier/return-type prefix
        "                    TargetFunc(\n                        ref explicitInterfaceName, ref separator);",
    ],
    "pathological": [
        (
            '[Obsolete]\n[Route("api/v1")]\npublic\nasync\nTask<Dictionary<string, List<int>>>\nTargetFunc\n(',
            "TargetFunc",
        ),  # carried-forward: attribute stacking, massive nested generics, vertical
        (
            "public static TargetEntity TargetFunc<T>() where T : class, IComparable<T>, IEnumerable<T> {",
            "TargetFunc",
        ),  # generic method w/ multi-constraint where-clause
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_csharp_func_start_valid(payload, expected_name):
    assert_valid_match(CSHARP_RULES["func_start"], payload, expected_name, "csharp.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_csharp_func_start_invalid(payload):
    assert_invalid_no_match(CSHARP_RULES["func_start"], payload, "csharp.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_csharp_func_start_pathological(payload, expected_name):
    assert_pathological_match(CSHARP_RULES["func_start"], payload, expected_name, "csharp.func_start")


def test_csharp_func_start_known_limitation_verbatim_and_raw_string_lookalikes_still_match_at_regex_level():
    """
    Documents a known, NOT-fixed limitation: func_start's own regex has no
    string/comment awareness, so function-shaped text inside a C# verbatim
    string (@-quoted) or C# 11+ raw string literal (triple-quoted) that
    happens to land at true line start still matches -- the same
    architectural class of bug confirmed for javascript/typescript template
    literals, Java text blocks, Go raw strings, and Rust raw strings
    (recurring bug class 3 in how_to_harden_extraction.md), now confirmed
    on a FIFTH language. csharp routes through Mode B (_slice_by_braces,
    lexical_family "standard_block"), which is currently gated to
    javascript/typescript only. Not fixed here -- tracked as its own
    future audited follow-up in the epic.
    """
    func_start = CSHARP_RULES["func_start"]
    verbatim = 'string s = @"\npublic void TargetFunc() {\n";'
    raw = 'string s = """\npublic void TargetFunc() {\n""";'
    assert func_start.search(verbatim), "documents current (expected, pipeline-level-fixed-elsewhere) regex behavior"
    assert func_start.search(raw), "documents current (expected, pipeline-level-fixed-elsewhere) regex behavior"


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("public void TargetFunc(int a, string b)", "TargetFunc"),
        ("protected override Task<int> TargetFunc(CancellationToken token)", "TargetFunc"),
        ("[Fact]\npublic void TargetFunc() {", "TargetFunc"),  # xUnit [Fact] args
    ],
    "invalid": [
        "TargetFunc(a, b);",
        "catch (Exception ex)",
    ],
    "pathological": [
        (
            "public \n async \n Task<IActionResult> \n TargetFunc \n (\n  [FromBody] User user,\n  [FromQuery] string? id,\n  Action<bool, string> callback\n)",
            "TargetFunc",
        ),  # carried-forward: vertical, attribute-decorated params, nested generic callback
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_csharp_args_valid(payload, expected_name):
    assert_valid_match(CSHARP_RULES["args"], payload, expected_name, "csharp.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_csharp_args_invalid(payload):
    assert_invalid_no_match(CSHARP_RULES["args"], payload, "csharp.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_csharp_args_pathological(payload, expected_name):
    assert_pathological_match(CSHARP_RULES["args"], payload, expected_name, "csharp.args")


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("public class TargetEntity", "TargetEntity"),
        ("internal record TargetEntity", "TargetEntity"),
        ("public interface TargetEntity<T>", "TargetEntity"),
        (
            "public class TargetEntity<T> : Base<T> {",
            "TargetEntity",
        ),  # generic class + base -- was a real bug (base silently lost), now fixed
        (
            "public sealed record TargetEntity<T>(T Value) : IComparable<T> {",
            "TargetEntity",
        ),  # primary-constructor record, generic + base -- was a real bug, now fixed
        (
            "public class TargetEntity(int x) : Base(x) {",
            "TargetEntity",
        ),  # C# 12 primary-constructor class (non-generic), base
        (
            "readonly struct TargetEntity",
            "TargetEntity",
        ),  # C# 7.2 readonly struct -- was a total miss before #1708
        (
            "readonly ref struct TargetEntity",
            "TargetEntity",
        ),  # C# 7.2 readonly ref struct
        (
            "ref struct TargetEntity",
            "TargetEntity",
        ),  # C# 7.2 ref struct
        (
            "ref readonly struct TargetEntity<T>",
            "TargetEntity",
        ),  # ref readonly, generic
        (
            "public readonly record struct TargetEntity",
            "TargetEntity",
        ),  # C# 10 readonly record struct
    ],
    "invalid": [
        "var obj = new TargetEntity();",
        "public classList",
        "typeof(TargetEntity)",
        "readonly int MaxValue",  # field/const declaration, not a type
        "private readonly string name;",  # field declaration, not a type
        "ref readonly int GetRef()",  # ref-local return type, not a type decl
    ],
    "pathological": [
        (
            '[Serializable]\n[Route("api/v1")]\npublic \n sealed \n class \n TargetEntity \n : \n IDisposable \n , \n ICloneable',
            "TargetEntity",
        ),  # carried-forward: attribute stacking, modifiers, inheritance interfaces
        (
            "public sealed record TargetEntity<T>(T Value) : IComparable<T>, IEnumerable<T> {",
            "TargetEntity",
        ),  # primary-ctor record w/ generic + multi-interface base, single line (the real bug this fixed)
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_csharp_class_start_valid(payload, expected_name):
    assert_valid_match(CSHARP_RULES["class_start"], payload, expected_name, "csharp.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_csharp_class_start_invalid(payload):
    assert_invalid_no_match(CSHARP_RULES["class_start"], payload, "csharp.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_csharp_class_start_pathological(payload, expected_name):
    assert_pathological_match(CSHARP_RULES["class_start"], payload, expected_name, "csharp.class_start")


def test_csharp_class_start_generic_base_regression():
    """
    Regression test for a real bug (epic #813/#820): there was no
    generic-parameter step-over between the class/interface/etc. name and
    the base-list `:` check, so ANY generic type with a base list
    (`class Foo<T> : Base<T> {`, extremely common) left the class's own
    `<...>` unconsumed right before `:`, silently losing the entire
    base-list capture (group 2) even though the name (group 1) still
    matched fine -- same failure shape as java's #816 class_start bug.
    """
    class_start = CSHARP_RULES["class_start"]
    assert class_start.groups == 2, "sanity: the rule still has both capture groups"
    m = class_start.search("public class Foo<T> : Base<T> {")
    assert m and m.group(1) == "Foo", "class name capture regressed"
    assert m.group(2) and "Base" in m.group(2), "base-list capture still lost behind a generic parameter list"


def test_csharp_class_start_primary_constructor_regression():
    """
    Regression test for a related but distinct real bug (epic #813/#820):
    a primary-constructor's parameter list (`record Foo<T>(T Value) : Base<T>`,
    C# 9+ records / C# 12 primary constructors on classes and structs,
    mainstream and common) was equally unconsumed between the generics and
    the `:` check, independently of the generic-parameter fix above.
    """
    class_start = CSHARP_RULES["class_start"]
    m = class_start.search("public sealed record Foo<T>(T Value) : IComparable<T> {")
    assert m and m.group(1) == "Foo", "class name capture regressed"
    assert m.group(2) and "IComparable" in m.group(2), (
        "base-list capture still lost behind a primary-constructor parameter list"
    )


def test_csharp_class_start_redos_immunity():
    """ReDoS sweep for the new generic-parameter and primary-constructor step-overs."""
    class_start = CSHARP_RULES["class_start"]
    assert_redos_immune(class_start, "public class Foo<" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(class_start, "public class Foo<T>(" + "a" * 100000, timeout_sec=3.0)
    assert class_start.search("public class Foo<T>(T x) : Base<T> {")


# ==============================================================================
# DEPENDENCY (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("using System.Threading.Tasks;", "System.Threading.Tasks"),
        ("global using static System.Math;", "System.Math"),
        (
            "using Alias = Some.Namespace.Target;",
            "Some.Namespace.Target",
        ),  # using alias directive -- was a real bug (no match at all), now fixed
        (
            "global using JsonObj = System.Text.Json.Nodes.JsonObject;",
            "System.Text.Json.Nodes.JsonObject",
        ),  # global using alias directive
        (
            "using StringList = System.Collections.Generic.List<string>;",
            "System.Collections.Generic.List",
        ),  # alias directive with a CLOSED GENERIC target -- the primary real-world reason
        # alias directives exist (shortening long generics) -- was also broken, now fixed
    ],
    "invalid": [
        "using (var stream = new FileStream())",  # using STATEMENT (resource disposal), not a directive
    ],
    "pathological": [
        (
            "global \n using \n static \n Microsoft.AspNetCore.Mvc \n ;",
            "Microsoft.AspNetCore.Mvc",
        ),  # carried-forward: vertical global static using
        (
            "using \n StringList \n = \n System.Collections.Generic.List<string> \n ;",
            "System.Collections.Generic.List",
        ),  # alias directive with generic target, vertical (the real bug this fixed)
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_csharp_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(
        CSHARP_RULES["_dependency_capture"], payload, expected_path, "csharp._dependency_capture"
    )


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_csharp_dependency_capture_invalid(payload):
    assert_invalid_no_match(CSHARP_RULES["_dependency_capture"], payload, "csharp._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_csharp_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        CSHARP_RULES["_dependency_capture"], payload, expected_path, "csharp._dependency_capture"
    )


def test_csharp_dependency_capture_alias_directive_regression():
    """
    Regression test for a real bug (epic #813/#820): a using-alias
    directive (`using Alias = Target.Namespace;`, common for shortening
    long generic types or disambiguating identical type names from
    different namespaces) didn't match AT ALL -- there was no allowance
    for the `IDENT =` prefix before the actual target, so the whole
    statement produced zero dependency-graph edges. Also verifies the
    companion fix: the target itself is very commonly a CLOSED GENERIC
    type (`using StringList = System.Collections.Generic.List<string>;`
    -- the primary real-world motivation for alias directives), which
    needed its own generic-suffix step-over before the required trailing
    `;`.
    """
    pattern = CSHARP_RULES["_dependency_capture"]
    m = pattern.search("using Alias = Some.Namespace.Target;")
    assert m and "Some.Namespace.Target" in m.group(1), "plain alias directive capture regressed"

    m2 = pattern.search("using StringList = System.Collections.Generic.List<string>;")
    assert m2 and "System.Collections.Generic.List" in m2.group(1), "generic-target alias directive capture regressed"

    # Sanity: plain (non-alias) using statements must still work.
    m3 = pattern.search("using System;")
    assert m3 and m3.group(1) == "System"


def test_csharp_dependency_capture_redos_immunity():
    """ReDoS sweep for the new alias-prefix and generic-suffix step-overs."""
    pattern = CSHARP_RULES["_dependency_capture"]
    assert_redos_immune(pattern, "using " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(pattern, "using X = Y<" + "a" * 100000, timeout_sec=3.0)
    assert pattern.search("using X = Y<string>;")


def test_csharp_dependency_capture_known_limitation_verbatim_string_lookalike_still_matches_at_regex_level():
    """
    Companion to func_start's own known-limitation test above:
    _dependency_capture is matched against fully unshielded raw file
    content for every language (see the java pass's #816 finding), so a
    `using ...;`-shaped line inside a C# verbatim string at true line
    start still produces a phantom dependency-graph edge. Documented, not
    fixed here -- see how_to_harden_extraction.md's recurring bug class 10.
    """
    dependency_capture = CSHARP_RULES["_dependency_capture"]
    verbatim = 'string s = @"\nusing System.IO;\n";'
    assert dependency_capture.search(verbatim), "documents current (accepted, unfixed) regex behavior"


def test_csharp_detector_issue_1428_lambda_in_args_shield():
    """
    Ensures that a lambda arrow (=>) inside a multi-line method argument
    does not fool the C# function-start shield into treating the call as
    an expression-bodied member declaration.
    """
    from gitgalaxy.core.detector import StructuralExtractor

    code = """
    class MyClass {
        public void Foo() {
            ReportManifestResourceDuplicates(
                moduleBuilder.ManifestResources,
                SourceAssembly.Modules.Skip(1).Select(m => m.Name),
                AddedModulesResourceNames(resourceDiagnostics),
                resourceDiagnostics);
        }
    }
    """
    detector = StructuralExtractor("csharp", LANGUAGE_DEFINITIONS)
    results = detector.splice(code, "test.cs")
    functions = [f.get("name") for f in results["functions"]]

    assert "Foo" in functions
    assert "SourceAssembly.Modules.Skip" not in functions

"""
Scala extraction hardening (epic #813, issue #825). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for scala in one file: func_start,
args, class_start, _dependency_capture. Migrated out of the four old
monolithic dict files (test_function_extraction_strict.py,
test_args_extraction_strict.py, test_class_extraction_strict.py,
test_dependency_extraction_strict.py) -- scala's entries were removed
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

SCALA_RULES = LANGUAGE_DEFINITIONS["scala"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        # Modern idiom (carried forward)
        ("def TargetFunc()", "TargetFunc"),
        ("override def TargetFunc()", "TargetFunc"),
        ("transparent inline def TargetFunc", "TargetFunc"),
        # Syntax-era / feature coverage
        ("implicit def TargetFunc()", "TargetFunc"),  # Scala 2-era implicit conversion
        ("inline def TargetFunc", "TargetFunc"),  # Scala 3 inline
        (
            "def TargetFunc[T <: Comparable[T]](x: T): T = {",
            "TargetFunc",
        ),  # nested generic bound -- was a real bug, now fixed
        (
            "def TargetFunc(x: Int)(using ctx: Context): Unit = {}",
            "TargetFunc",
        ),  # Scala 3 multiple/using parameter lists
        ("@main def TargetFunc(args: String*): Unit = {}", "TargetFunc"),  # Scala 3 @main entry point
        # Backtick-quoted arbitrary identifiers (doc's Rule 16 identifier-grammar shape)
        ("def `TargetFunc with spaces`()", "TargetFunc with spaces"),
        # Testing-framework-shaped functions that ARE real functions
        (
            "def `should return true`(): Unit = {}",
            "should return true",
        ),  # backtick-named test method, a common ScalaTest/JVM-interop idiom
    ],
    "invalid": [
        "class TargetFunc",  # class decl lookalike
        "val TargetFunc =",  # val decl lookalike
        "trait TargetFunc",  # trait decl lookalike
        'val query = "def TargetFunc() {"',  # string-literal lookalike, not at true line start
        "// def TargetFunc()",  # commented-out def, correctly excluded by the leading-token anchor
    ],
    "pathological": [
        (
            '@deprecated("", "")\noverride \n protected \n inline \n def \n TargetFunc \n (',
            "TargetFunc",
        ),  # carried-forward: deep Scala 3 modifier stacking across lines
        (
            "def TargetFunc[T <: Comparable[T]](\n  x: T\n): T = {",
            "TargetFunc",
        ),  # nested generic bound, params split vertically
        (
            "@deprecated\noverride \n private \n def \n `Target Func` \n (",
            "Target Func",
        ),  # backtick name plus deep vertical modifier stacking
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_scala_func_start_valid(payload, expected_name):
    assert_valid_match(SCALA_RULES["func_start"], payload, expected_name, "scala.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_scala_func_start_invalid(payload):
    assert_invalid_no_match(SCALA_RULES["func_start"], payload, "scala.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_scala_func_start_pathological(payload, expected_name):
    assert_pathological_match(SCALA_RULES["func_start"], payload, expected_name, "scala.func_start")


def test_scala_func_start_nested_generic_bound_regression():
    """
    Regression test for a real bug (epic #813/#825): the args rule's
    generic-parameter step-over was the flat `\\[[^\\]]*\\]`, truncating at
    the FIRST `]` and breaking any nested generic bound (`def foo[T <:
    Comparable[T]](x: T): T = {`, a realistic bounded generic method -- the
    square-bracket variant of the same Rule-11 bug class already fixed for
    java/typescript/python/rust/csharp/kotlin/swift). func_start itself only
    ever used a lookahead here (never consumed the brackets), so it was
    unaffected -- this regression test exists on func_start anyway to pin
    down the fixed shape actually used by the pipeline.
    """
    func_start = SCALA_RULES["func_start"]
    m = func_start.search("def TargetFunc[T <: Comparable[T]](x: T): T = {")
    assert m and m.group(m.lastindex) == "TargetFunc", "nested generic bound detection regressed"


def test_scala_func_start_backtick_identifier_regression():
    """
    Regression test for a real bug (epic #813/#825): the name step-over
    required a plain `[a-zA-Z_]\\w*`, so any backtick-quoted arbitrary
    identifier -- Scala's escape hatch for reserved-word or space-containing
    method names, e.g. Java-interop methods or ScalaTest-style spec names --
    never matched at all (doc's Rule 16 identifier-grammar shape).
    """
    func_start = SCALA_RULES["func_start"]
    m = func_start.search("def `should handle edge cases`(): Unit = {}")
    assert m and m.group(m.lastindex) == "should handle edge cases", "backtick identifier detection regressed"


def test_scala_func_start_redos_immunity():
    """ReDoS sweep for the backtick-identifier alternative."""
    func_start = SCALA_RULES["func_start"]
    assert_redos_immune(func_start, "def `" + "a" * 100000, timeout_sec=3.0)
    assert func_start.search("def `should return true`(): Unit = {}")


def test_scala_func_start_known_limitation_triple_quoted_string_lookalikes_still_match_at_regex_level():
    """
    Documents a known, NOT-fixed limitation: func_start's own regex has no
    string/comment awareness, so function-shaped text inside a Scala
    triple-quoted multi-line string that happens to land at true line start
    still matches -- the same architectural class of bug confirmed for
    javascript/typescript template literals, Java text blocks, Go/Rust raw
    strings, C# verbatim/raw strings, Kotlin raw strings, and Swift
    triple-quoted/raw strings (recurring bug class 3 in
    how_to_harden_extraction.md), now confirmed on a NINTH language. scala
    routes through Mode B (_slice_by_braces), currently gated to
    javascript/typescript only. Not fixed here -- tracked as its own future
    audited follow-up in the epic.
    """
    func_start = SCALA_RULES["func_start"]
    triple_quoted = 'val s = """\ndef TargetFunc(): Unit = {}\n"""'
    assert func_start.search(triple_quoted), (
        "documents current (expected, pipeline-level-fixed-elsewhere) regex behavior"
    )


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("def TargetFunc(a: Int, b: String): Unit =", "TargetFunc"),
        ("def TargetFunc[T](items: List[T])", "TargetFunc"),
        (
            "def TargetFunc[T <: Comparable[T]](x: T): T =",
            "TargetFunc",
        ),  # nested generic bound -- was a real bug, now fixed
        (
            "def TargetFunc(x: Int)(using ctx: Context): Unit = {}",
            "TargetFunc",
        ),  # Scala 3 using clause (second param list not required to be captured)
        ("def `should do something`(x: Int): Int = x", "should do something"),  # backtick identifier
        ("(x: Int, y: Int) => x + y", "x: Int, y: Int"),  # bare lambda param list
    ],
    "invalid": [
        "TargetFunc(a, b)",  # bare call lookalike (known limitation class 7, not this rule's concern)
        "for (i <- 1 to 10) {",  # for-comprehension lookalike
    ],
    "pathological": [
        (
            "inline \n def \n TargetFunc[T] \n (\n  items: List[T],\n  callback: (Int, String) => Unit\n)",
            "TargetFunc",
        ),  # carried-forward: vertical modifiers and complex lambda parameters. NOTE: the
        # name and its generic bracket are kept attached (no vertical split between
        # `TargetFunc` and `[T]`) -- scalafmt never inserts a line break at that exact
        # seam, so testing it would be an unrealistic seam per the doc's "realism
        # triage" guidance (recurring class 17); confirmed empirically that a split
        # there does NOT match (a pre-existing, non-regressed gap, not a new bug).
        (
            "def TargetFunc[T <: Comparable[T]](\n  x: T\n): T =",
            "TargetFunc",
        ),  # nested generic bound, params split vertically
        (
            "def \n `should not break` \n (x: Int): Int = x",
            "should not break",
        ),  # backtick name with vertical spacing around it (not INSIDE the backticks --
        # a literal newline inside a backtick-quoted identifier is not realistic
        # source Scala/scalafmt ever produces, so that seam is deliberately out of
        # scope per the doc's "realism triage" guidance, recurring class 17).
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_scala_args_valid(payload, expected_name):
    assert_valid_match(SCALA_RULES["args"], payload, expected_name, "scala.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_scala_args_invalid(payload):
    assert_invalid_no_match(SCALA_RULES["args"], payload, "scala.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_scala_args_pathological(payload, expected_name):
    assert_pathological_match(SCALA_RULES["args"], payload, expected_name, "scala.args")


def test_scala_args_nested_generic_bound_regression():
    """
    Regression test for a real bug (epic #813/#825): the generic-parameter
    step-over was the flat `\\[[^\\]]*\\]`, truncating at the FIRST `]` and
    breaking any nested generic bound (`def foo[T <: Comparable[T]](x: T): T
    = {`, a realistic bounded generic method -- the square-bracket variant of
    the same Rule-11 bug class already fixed for
    java/typescript/python/rust/csharp/kotlin/swift).
    """
    args = SCALA_RULES["args"]
    assert args.search("def TargetFunc[T <: Comparable[T]](x: T): T = {"), "nested generic bound args detection regressed"


def test_scala_args_backtick_identifier_regression():
    """Regression test for the same root-cause bug as func_start's own regression test above."""
    args = SCALA_RULES["args"]
    assert args.search("def `should handle edge cases`(): Unit = {}"), "backtick identifier args detection regressed"


def test_scala_args_redos_immunity():
    """ReDoS sweep for both the widened generic-parameter step-over and the backtick alternative."""
    args = SCALA_RULES["args"]
    assert_redos_immune(args, "def Foo[T <: " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(args, "def `" + "a" * 100000, timeout_sec=3.0)
    assert args.search("def Foo[T <: Comparable[T]](x: T): T = {")


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("class TargetEntity {", "TargetEntity"),
        ("sealed trait TargetEntity", "TargetEntity"),
        ("case object TargetEntity", "TargetEntity"),
        ("case class TargetEntity(x: Int)", "TargetEntity"),  # canonical Scala idiom
        ("enum TargetEntity { case A, B }", "TargetEntity"),  # Scala 3 enums
        (
            "class TargetEntity[T](x: T) extends Base[T]",
            "TargetEntity",
        ),  # generic class with extends clause -- name capture unaffected by generics
        # (class_start uses a pure lookahead here, not a consuming step-over, so
        # there is no Rule-11 flat-bracket exposure to begin with; verified
        # empirically, see regression test below)
    ],
    "invalid": [
        "val x = new TargetEntity()",  # instantiation lookalike
        "def classMethod()",  # method named "class*" lookalike
        "type TargetEntity = String",  # type-alias lookalike (recurring class 4)
        "opaque type TargetEntity = Int",  # Scala 3 opaque type alias, same exclusion
    ],
    "pathological": [
        (
            "@deprecated\nsealed \n abstract \n class \n TargetEntity \n extends \n Base",
            "TargetEntity",
        ),  # carried-forward: Scala 3 modifiers and vertical spacing
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_scala_class_start_valid(payload, expected_name):
    assert_valid_match(SCALA_RULES["class_start"], payload, expected_name, "scala.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_scala_class_start_invalid(payload):
    assert_invalid_no_match(SCALA_RULES["class_start"], payload, "scala.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_scala_class_start_pathological(payload, expected_name):
    assert_pathological_match(SCALA_RULES["class_start"], payload, expected_name, "scala.class_start")


def test_scala_class_start_generic_with_extends_no_rule11_exposure():
    """
    Unlike java/typescript/csharp's class_start (which capture an
    extends/implements clause in a second group and therefore have real
    Rule-11 exposure -- recurring classes 6/9 in how_to_harden_extraction.md),
    scala's class_start only ever captures the entity NAME via a trailing
    lookahead; it never consumes the generic-parameter list or the
    extends/implements clause into a separate group. So a generic class with
    a subsequent extends clause (`class Foo[T](x: T) extends Base[T]`) has no
    flat-bracket truncation to break, because there's nothing after the name
    for the regex to consume. Verified empirically -- documenting the
    negative result so a future pass doesn't re-investigate this from
    scratch.
    """
    class_start = SCALA_RULES["class_start"]
    m = class_start.search("class TargetEntity[T <: Comparable[T]](x: T) extends Base[T]")
    assert m and m.group(1) == "TargetEntity"


# ==============================================================================
# DEPENDENCY (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("import cats.effect.IO", "cats.effect.IO"),
        ("export scala.collection.mutable.Map", "scala.collection.mutable.Map"),
        ("import scala.util.chaining.*", "scala.util.chaining.*"),  # Scala 3 wildcard -- was truncated, now fixed
        ("import scala.collection.mutable._", "scala.collection.mutable._"),  # Scala 2 wildcard
        (
            "import scala.util.{Try => STry}",
            "scala.util.{Try => STry}",
        ),  # renamed import -- was truncated at `=>`, now fixed
        ("import scala.collection.mutable.{Map, Set}", "scala.collection.mutable.{Map, Set}"),  # block import
        (
            "def foo(): Unit = {\n  import scala.util.Random\n  ()\n}",
            "scala.util.Random",
        ),  # locally-scoped import (the rule's own documented historical fix)
    ],
    "invalid": [
        "val importCount = 0",
        "important = 5",  # substring-of-keyword lookalike, correctly excluded by \b + required \s+
    ],
    "pathological": [
        ("import \n scala.concurrent.Future", "scala.concurrent.Future"),  # carried-forward: vertical import
        (
            "import scala.util.{\n  Try,\n  Success\n}",
            "Try",
        ),  # multi-line braced block import
        (
            "import scala.util.{\n  Try => STry\n}",
            "STry",
        ),  # multi-line braced block import with a rename
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_scala_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(SCALA_RULES["_dependency_capture"], payload, expected_path, "scala._dependency_capture")


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_scala_dependency_capture_invalid(payload):
    assert_invalid_no_match(SCALA_RULES["_dependency_capture"], payload, "scala._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_scala_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        SCALA_RULES["_dependency_capture"], payload, expected_path, "scala._dependency_capture"
    )


def test_scala_dependency_capture_multi_import_no_longer_bleeds_across_statements_regression():
    """
    Regression test for a severe real bug (epic #813/#825): the previous
    capture, `[\\w.{}\\s,]+`, was a single flat character class with no
    statement boundary at all. Since `\\s` matches newlines, it kept
    consuming across subsequent, unrelated lines -- including a SECOND
    import statement -- until it happened to hit some character outside the
    class. On a realistic 2-import file, the first match's capture group
    swallowed the entire second `import` line plus part of the following
    `case class` line, so the second import was never separately detected at
    all. Fixed via a properly bounded segmented-dotted-path grammar that
    cannot bleed past an explicit brace block.
    """
    dep = SCALA_RULES["_dependency_capture"]
    realistic_file = (
        "import scala.util.Try\nimport scala.collection.mutable.{Map, Set}\n\ncase class Foo(x: Int)\n"
    )
    matches = list(dep.finditer(realistic_file))
    captured = [m.group(m.lastindex) for m in matches]
    assert captured == ["scala.util.Try", "scala.collection.mutable.{Map, Set}"], (
        f"expected both imports to be captured separately and cleanly, got {captured!r}"
    )


def test_scala_dependency_capture_redos_immunity():
    """ReDoS sweep for the segmented-dotted-path replacement grammar."""
    dep = SCALA_RULES["_dependency_capture"]
    assert_redos_immune(dep, "import " + "a." * 100000, timeout_sec=3.0)
    assert_redos_immune(dep, "import " + ("a." * 50000) + "{" + "b" * 50000, timeout_sec=3.0)
    assert dep.search("import scala.util.chaining.*")


def test_scala_dependency_capture_known_limitation_commented_import_still_matches_at_regex_level():
    """
    Documents a known, NOT-fixed limitation shared by every language, not
    just scala (recurring bug class 10 in how_to_harden_extraction.md):
    `_dependency_capture` is matched against raw, unshielded file content
    (`content_buffer` in galaxyscope.py) for every language, unconditionally
    -- there is no string/comment shielding gate for this rule at all. A
    commented-out import (`// import scala.util.Try`) at true line start
    still produces a phantom dependency-graph edge. Not fixed here (fixing it
    means shielding `content_buffer` before every language's
    `_dependency_capture.finditer()` call -- a pipeline-wide change, not a
    per-language one).
    """
    dep = SCALA_RULES["_dependency_capture"]
    commented = "// import scala.util.Try"
    m = dep.search(commented)
    assert m, "documents current (expected, pipeline-wide, not-yet-fixed) regex behavior"

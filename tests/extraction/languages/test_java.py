"""
Java extraction hardening (epic #813, issue #816). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for java in one file: func_start, args,
class_start, _dependency_capture. Migrated out of the four old monolithic
dict files (test_function_extraction_strict.py, test_args_extraction_strict.py,
test_class_extraction_strict.py, test_dependency_extraction_strict.py) --
java's entries were removed from those four when this file was added.
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

JAVA_RULES = LANGUAGE_DEFINITIONS["java"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        # Modern idiom (carried forward)
        ("public static void TargetFunc() {", "TargetFunc"),
        ("protected List<String> TargetFunc(int x) {", "TargetFunc"),
        ("protected @Nullable AnnotationAttributes TargetFunc(AnnotationMetadata metadata) {", "TargetFunc"),
        ("protected @Deprecated(since=\"1.0\") Foo TargetFunc(int x) {", "TargetFunc"),
        ("public @NonNull Foo TargetFunc() {", "TargetFunc"),
        ("@Override\npublic void TargetFunc() {", "TargetFunc"),
        # Syntax-era / feature coverage
        ("public void TargetFunc() throws IOException {", "TargetFunc"),  # pre-8, checked exception
        ("default void TargetFunc() {", "TargetFunc"),  # Java 8 interface default method
        ("static void TargetFunc() {", "TargetFunc"),  # Java 8 interface static method
        (
            "public static <T, U extends Comparable<U>> T TargetFunc(T a, U b) {",
            "TargetFunc",
        ),  # one-level-nested generic bound, single line -- was a real bug, now fixed
        ("public <T> Optional<T> TargetFunc(Class<T> type) {", "TargetFunc"),  # bounded generic method
        (
            "public final synchronized <T extends Comparable<T>> T TargetFunc(T... items) {",
            "TargetFunc",
        ),  # varargs + generic bound + modifier stacking
        # Testing-framework-shaped functions that ARE real functions
        ("@Test\npublic void TargetFunc() {", "TargetFunc"),  # JUnit4
        ("@Test\nvoid TargetFunc() {", "TargetFunc"),  # JUnit5, package-private
        (
            '@ParameterizedTest\n@ValueSource(strings = {"a", "b"})\nvoid TargetFunc(String input) {',
            "TargetFunc",
        ),  # JUnit5 parameterized test
        ("public static void main(String[] args) {", "main"),  # main method sanity
    ],
    "invalid": [
        "public class TargetFunc {",  # class decl lookalike
        "new TargetFunc();",  # instantiation
        "return TargetFunc();",  # return call
        "throw TargetFunc();",  # throw call
        'String s = "public void TargetFunc() {";',  # string literal lookalike, not at true line start
        "Map.Entry<String,Integer> TargetFunc = getEntry();",  # generic-typed variable decl lookalike
        "if ((TargetFunc = compute()) != null) {",  # assignment-in-condition lookalike
    ],
    "pathological": [
        (
            '@Override\n@SuppressWarnings("unchecked")\npublic static final <T, U extends Map<String, V>>\nList<T>\nTargetFunc\n() {',
            "TargetFunc",
        ),  # carried-forward: massive generic soup + annotation stacking, multi-line
        (
            "public static <T, U extends Comparable<U>> T \n TargetFunc \n ( \n T a, U b \n ) \n {",
            "TargetFunc",
        ),  # nested generic bound split vertically after the bound itself
        (
            '@Deprecated\n@SafeVarargs\n@SuppressWarnings({"unchecked", "rawtypes"})\npublic final synchronized <T extends Comparable<T>> T TargetFunc(T... items) {',
            "TargetFunc",
        ),  # annotation stacking (3) + varargs + generic bound, single line
        (
            '@Entity\n@Table(name="foo")\n@JsonIgnoreProperties(ignoreUnknown = true)\n@SuppressWarnings("unchecked")\n@Deprecated\npublic void TargetFunc() {',
            "TargetFunc",
        ),  # 5+ stacked annotations with nested-paren arguments
        (
            "public \n static \n final \n synchronized \n <T> \n List<T> \n TargetFunc \n ( \n T \n item \n ) \n {",
            "TargetFunc",
        ),  # modifier stack split at every boundary
        (
            '@Test\n@DisplayName("should do the thing")\n@Timeout(value = 5, unit = TimeUnit.SECONDS)\nvoid TargetFunc() {',
            "TargetFunc",
        ),  # JUnit5 stacked test annotations with args
        (
            "protected \n abstract \n <K, V extends Comparable<V>> \n Map<K, V> \n TargetFunc \n (\n Set<K> keys\n) \n throws \n IOException \n ;",
            "TargetFunc",
        ),  # abstract generic method, vertical, with throws clause
        (
            "public TargetFunc(int x) {",
            "TargetFunc",
        ),  # constructor shape (IDENT() with no return type) -- matches like any bare signature
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_java_func_start_valid(payload, expected_name):
    assert_valid_match(JAVA_RULES["func_start"], payload, expected_name, "java.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_java_func_start_invalid(payload):
    assert_invalid_no_match(JAVA_RULES["func_start"], payload, "java.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_java_func_start_pathological(payload, expected_name):
    assert_pathological_match(JAVA_RULES["func_start"], payload, expected_name, "java.func_start")


def test_java_func_start_nested_generic_bound_regression():
    """
    Regression test for a real bug (epic #813/#816): the generic-bound
    modifier alternative was a flat `<[^>]*>`, truncating at the FIRST `>` --
    a one-level-nested generic bound (`public static <T, U extends
    Comparable<U>> T Foo(T a, U b) {`, a realistic bounded-generic method
    signature) left a stray `>` unconsumed, breaking the match entirely
    (unlike class_start's equivalent bug, this one has no re.M line-restart
    escape hatch when the whole signature is on one line -- the carried-
    forward multi-line pathological case masked this because splitting the
    signature across lines let `^[ \\t]*` re-anchor past the broken modifier
    section instead of needing to cross it).
    """
    func_start = JAVA_RULES["func_start"]
    m = func_start.search("public static <T, U extends Comparable<U>> T TargetFunc(T a, U b) {")
    assert m and m.group(1) == "TargetFunc", "single-line nested generic bound regressed"


def test_java_func_start_redos_immunity():
    """ReDoS sweep for the widened one-level-nesting generic-bound modifier alternative."""
    func_start = JAVA_RULES["func_start"]
    assert_redos_immune(func_start, "public static <T, U extends " + "a" * 100000, timeout_sec=3.0)
    assert func_start.search("public static <T, U extends Comparable<U>> T Foo(T a, U b) {")


def test_java_func_start_known_limitation_text_block_string_lookalike_still_matches_at_regex_level():
    """
    Documents a known, NOT-fixed limitation: func_start's own regex has no
    string/comment awareness, so function-shaped text inside a Java 15+ text
    block (`\"\"\"..\"\"\"`) that happens to land at true line start still
    matches -- the same architectural class of bug confirmed for javascript/
    typescript template literals (recurring bug class #3 in
    how_to_harden_extraction.md), now confirmed on a second, unrelated
    syntax feature (Java text blocks) rather than just js/ts's template
    literals. The real fix (matching against shielded code) lives in
    detector.py's _slice_by_braces and is currently gated to javascript/
    typescript only; broadening it to other Mode B languages (java included)
    is tracked as its own future audited follow-up, not fixed here -- see
    the epic's "Related architectural issue" section for #859's resolution
    that unblocked that follow-up.
    """
    func_start = JAVA_RULES["func_start"]
    text_block = 'String s = """\npublic void TargetFunc() {\n""";'
    assert func_start.search(text_block), "documents current (expected, pipeline-level-fixed-elsewhere) regex behavior"


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("public void TargetFunc(String name, int age) {", "TargetFunc"),
        ("protected List<T> TargetFunc(Predicate<T> filter)", "TargetFunc"),
        (
            "public static <T, U extends Comparable<U>> T TargetFunc(T a, U b) {",
            "TargetFunc",
        ),  # one-level-nested generic bound -- was a real bug, now fixed
        (
            "public <K, V extends Map<K, V>> void TargetFunc(K key, V value) {",
            "TargetFunc",
        ),  # another nested generic bound shape
        ("TargetFunc(items) -> items.size()", None),  # lambda shape
        ("list.forEach(TargetFunc::process)", None),  # method reference
    ],
    "invalid": [
        "TargetFunc(name, age);",
        "for (int i = 0; i < 10; i++)",
    ],
    "pathological": [
        (
            "public \n static \n <T, U extends Comparable<U>> \n void \n TargetFunc \n (\n  @NonNull final List<T> items,\n  @Nullable Function<T, String> mapper\n)",
            "TargetFunc",
        ),  # carried-forward + nested generic bound added, vertical
        (
            'public TargetFunc(\n  @Inject Foo foo,\n  @Named("bar") Bar bar\n) {',
            "TargetFunc",
        ),  # DI-annotated constructor params, vertical
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_java_args_valid(payload, expected_name):
    assert_valid_match(JAVA_RULES["args"], payload, expected_name, "java.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_java_args_invalid(payload):
    assert_invalid_no_match(JAVA_RULES["args"], payload, "java.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_java_args_pathological(payload, expected_name):
    assert_pathological_match(JAVA_RULES["args"], payload, expected_name, "java.args")


def test_java_args_nested_generic_bound_regression():
    """
    Regression test for the same root-cause bug as func_start's own
    regression test above (epic #813/#816): args' Branch 1 shares the exact
    same flat `<[^>]*>` generic-bound modifier alternative, so it broke on
    the identical single-line nested-generic-bound signature.
    """
    args = JAVA_RULES["args"]
    m = args.search("public static <T, U extends Comparable<U>> T TargetFunc(T a, U b) {")
    assert m, "single-line nested generic bound regressed"


def test_java_args_redos_immunity():
    """ReDoS sweep for the widened one-level-nesting generic-bound modifier alternative."""
    args = JAVA_RULES["args"]
    assert_redos_immune(args, "public static <T, U extends " + "a" * 100000, timeout_sec=3.0)
    assert args.search("public static <T, U extends Comparable<U>> T Foo(T a, U b) {")


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("public class TargetEntity {", "TargetEntity"),
        ("protected abstract interface TargetEntity extends Base", "TargetEntity"),
        ("public record TargetEntity(int x) {", "TargetEntity"),  # record, Java 16+
        (
            "public class TargetEntity<T> extends Base<T> {",
            "TargetEntity",
        ),  # generic class + extends -- was a real bug (extends silently lost), now fixed
        (
            "public class TargetEntity<T extends Comparable<T>> implements Serializable {",
            "TargetEntity",
        ),  # generic bound class + implements -- was a real bug, now fixed
        ("sealed interface TargetEntity permits Foo, Bar {", "TargetEntity"),  # Java 17 sealed interface
        (
            "public record TargetEntity(int x, int y) implements Serializable {",
            "TargetEntity",
        ),  # record implementing an interface
    ],
    "invalid": [
        "TargetEntity entity = new TargetEntity();",
        "classyMethod()",
        "return TargetEntity.class;",
    ],
    "pathological": [
        (
            '@Entity\n@Table(name="foo")\n@SuppressWarnings("unchecked")\npublic \n final \n class \n TargetEntity \n implements \n Serializable',
            "TargetEntity",
        ),  # carried-forward: annotation bloat + vertical stacking
        (
            "public \n class \n TargetEntity \n < \n T \n extends \n Comparable<T> \n > \n implements \n Serializable \n , \n Cloneable",
            "TargetEntity",
        ),  # nested generic bound + implements list, vertically split -- the real bug this fixed
        (
            '@Entity\n@Table(name = "targets")\n@JsonIgnoreProperties(ignoreUnknown = true)\n@Deprecated\npublic class TargetEntity<K, V extends Map<K, V>> extends AbstractEntity<K, V> implements Serializable, Cloneable {',
            "TargetEntity",
        ),  # annotation stacking (4) + nested generic bound + multi-interface implements, single line
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_java_class_start_valid(payload, expected_name):
    assert_valid_match(JAVA_RULES["class_start"], payload, expected_name, "java.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_java_class_start_invalid(payload):
    assert_invalid_no_match(JAVA_RULES["class_start"], payload, "java.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_java_class_start_pathological(payload, expected_name):
    assert_pathological_match(JAVA_RULES["class_start"], payload, expected_name, "java.class_start")


def test_java_class_start_generic_extends_regression():
    """
    Regression test for a real bug (epic #813/#816), distinct from the
    func_start/args Rule-11 bug above: class_start had NO generic-parameter
    step-over AT ALL between the class name and the extends/implements
    check (unlike func_start/args, which had a flat-but-present `<[^>]*>`
    that just needed widening). Any generic class declaration followed by
    extends/implements (`class Foo<T> extends Base<T> {`, extremely common
    real Java) left the class's own `<...>` unconsumed right before
    `extends`, silently losing the ENTIRE inheritance capture (group 2) even
    though the class name itself (group 1) still matched fine -- an easy bug
    to miss since the primary capture looked correct.
    """
    class_start = JAVA_RULES["class_start"]
    assert class_start.groups == 2, "sanity: the rule still has both capture groups"

    m = class_start.search("class Foo<T extends Comparable<T>> extends Bar {")
    assert m and m.group(1) == "Foo", "class name capture regressed"
    assert m.group(2) and "Bar" in m.group(2), "extends clause still lost behind a nested generic bound"


def test_java_class_start_redos_immunity():
    """ReDoS sweep for the new generic-parameter step-over before extends/implements."""
    class_start = JAVA_RULES["class_start"]
    assert_redos_immune(class_start, "class Foo<" + "a" * 100000, timeout_sec=3.0)
    assert class_start.search("class Foo<T extends Comparable<T>> extends Bar {")


# ==============================================================================
# DEPENDENCY (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("import java.util.List;", "java.util.List"),
        ("import static org.junit.Assert.*;", "org.junit.Assert.*"),
        ("import java.util.*;", "java.util.*"),  # wildcard package import
        ("import com.example.MyClass;", "com.example.MyClass"),  # single class import
    ],
    "invalid": [
        "String importPath;",
        "requires java.sql;",  # Java 9+ module-info directive -- out of scope for this rule (not an import statement)
    ],
    "pathological": [
        (
            "import \n static \n org.springframework.boot.SpringApplication \n ;",
            "org.springframework.boot.SpringApplication",
        ),  # carried-forward: vertical static import
        (
            "import \n com.example.deeply.nested.package.MyClass \n ;",
            "com.example.deeply.nested.package.MyClass",
        ),  # deeply nested package path, vertical
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_java_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(JAVA_RULES["_dependency_capture"], payload, expected_path, "java._dependency_capture")


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_java_dependency_capture_invalid(payload):
    assert_invalid_no_match(JAVA_RULES["_dependency_capture"], payload, "java._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_java_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        JAVA_RULES["_dependency_capture"], payload, expected_path, "java._dependency_capture"
    )


def test_java_dependency_capture_known_limitation_text_block_string_lookalike_still_matches_at_regex_level():
    """
    Documents a known, NOT-fixed limitation, broader than func_start's own
    text-block finding above: `_dependency_capture` is matched against
    `content_buffer` (the raw, unshielded whole-file content read straight
    off disk in galaxyscope.py) for EVERY language unconditionally -- there
    is no js/ts-style gate here at all, unlike func_start's Mode-B
    `_slice_by_braces` path. An `import ...;`-shaped line inside a Java 15+
    text block at true line start still produces a phantom dependency-graph
    edge. Recorded as a refinement of recurring bug class #3 (the
    "unshielded string/comment content reaching a rule's finditer" class
    extends beyond Mode-B func_start to _dependency_capture's own,
    separately-unshielded call site) rather than fixed here -- fixing it
    would mean shielding `content_buffer` before every language's
    `_dependency_capture.finditer()` call in galaxyscope.py, a pipeline-wide
    architectural change well beyond a single language's extraction pass.
    """
    dependency_capture = JAVA_RULES["_dependency_capture"]
    text_block = 'String s = """\nimport java.util.List;\n""";'
    assert dependency_capture.search(text_block), "documents current (accepted, unfixed) regex behavior"

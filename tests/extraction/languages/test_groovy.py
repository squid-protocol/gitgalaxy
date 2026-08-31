"""
Groovy extraction hardening (epic #813, issue #829). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for groovy in one file: func_start,
args, class_start, _dependency_capture. Migrated out of the old
monolithic dict files.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from typing import Any  # noqa: E402

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_pathological_dependency_match,
    assert_pathological_match,
    assert_redos_immune,
    assert_valid_dependency_match,
    assert_valid_match,
)

GROOVY_RULES = LANGUAGE_DEFINITIONS["groovy"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        ("def foo() {", "foo"),
        ("public static final Map<String, List<String>> getComplexData() {", "getComplexData"),
        ("def \"method with spaces and 'quotes'\"() {", "\"method with spaces and 'quotes'\""),
        ("@Override\nprotected <T extends Comparable<T>> List<T> sort(List<T> list) throws Exception {", "sort"),
        ("java.lang.String[] fullyQualifiedArrayReturn(int a) {", "fullyQualifiedArrayReturn"),
        ("MyClass(String constructorArg) {", "MyClass"),
        # #2530: a bare constructor whose default value is an empty map
        # literal (`[:]`) has a colon, but not adjacent to an identifier
        # the way a named-arg call's `key:` is -- must still match.
        ("MyClass(Map config = [:]) {", "MyClass"),
    ],
    "invalid": [
        "if (condition()) {",
        "catch (Exception e) {",
        "synchronized (lock) {",
        "for (Map.Entry<String, String> entry : map.entrySet()) {",
        "/* def hiddenMethod() { */",
        '"def stringMethod() {"',
        "def myClosure = { -> }",
        # #2530: MarkupBuilder/Jenkins-DSL named-argument-map calls with a
        # trailing closure are syntactically identical to a bare zero-
        # prefix declaration otherwise -- the named-arg `key:` shape is
        # the discriminator (real declarations never contain one).
        'div(class: "empty-state-block") {',
        'button(name: "clear", type: "submit") {',
        "timeout(time: 6, unit: 'HOURS') {",
        "a(href: \"newJob\", class: \"content-block__link\") {",
    ],
    "pathological": [
        ("public \n void \n weirdSpacing \n ( \n ) \n {", "weirdSpacing"),
        ('def \n "pathological string name" \n ( \n ) \n {', '"pathological string name"'),
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_groovy_func_start_valid(payload, expected_name):
    assert_valid_match(GROOVY_RULES["func_start"], payload, expected_name, "groovy.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_groovy_func_start_invalid(payload):
    assert_invalid_no_match(GROOVY_RULES["func_start"], payload, "groovy.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_groovy_func_start_pathological(payload, expected_name):
    assert_pathological_match(GROOVY_RULES["func_start"], payload, expected_name, "groovy.func_start")
    assert_redos_immune(GROOVY_RULES["func_start"], payload)


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("def foo(int a, String b) {", ""),
        ("void bar(Map<String, ? extends List<Object>> complex, int... varargs) {", ""),
        ('def baz(\n  @Inject\n  MyType myVar,\n  @Qualifier("foo") String foo\n) {', ""),
        ("{ a, b ->", ""),
        ("{ String x, def y ->", ""),
        ("{ ->", ""),
    ],
    "invalid": [
        "dependencies {",
        "tasks.register('myTask') {",
        "if (a > b && c < d)",
        "while (matcher.find())",
        "catch (Exception e)",
        "/* (a, b) */",
        '"(String a, int b)"',
        "def foo = (a + b) * c",
    ],
    "pathological": [
        (
            'def \n foo \n ( \n String \n a \n = \n "default), with, commas", \n int \n b \n = \n [1,2,3].size() \n ) \n {',
            "",
        ),
    ],
}


@pytest.mark.parametrize("payload,expected", ARGS_CASES["valid"])
def test_groovy_args_valid(payload, expected):
    assert_valid_match(GROOVY_RULES["args"], payload, expected, "groovy.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_groovy_args_invalid(payload):
    assert_invalid_no_match(GROOVY_RULES["args"], payload, "groovy.args")


@pytest.mark.parametrize("payload,expected", ARGS_CASES["pathological"])
def test_groovy_args_pathological(payload, expected):
    assert_pathological_match(GROOVY_RULES["args"], payload, expected, "groovy.args")
    assert_redos_immune(GROOVY_RULES["args"], payload)


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("class SimpleClass {", "SimpleClass"),
        (
            "public abstract class ComplexClass<T extends Number & Comparable<T>> extends BaseClass<T> implements InterfaceA, InterfaceB {",
            "ComplexClass",
        ),
        ("trait MyTrait {", "MyTrait"),
        ("interface MyInterface extends BaseInterface {", "MyInterface"),
        ("@CompileStatic\n@EqualsAndHashCode(callSuper = true)\nclass AnnotatedClass {", "AnnotatedClass"),
    ],
    "invalid": [
        "def classLoader = new ClassLoader()",
        "String myclass = 'class Foo {'",
        "/* class HiddenClass { */",
        "def myMethod() { classLoader.loadClass('Foo') }",
        "classyMethod()",
    ],
    "pathological": [
        ("class \n Pathological \n <T> \n {", "Pathological"),
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_groovy_class_start_valid(payload, expected_name):
    assert_valid_match(GROOVY_RULES["class_start"], payload, expected_name, "groovy.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_groovy_class_start_invalid(payload):
    assert_invalid_no_match(GROOVY_RULES["class_start"], payload, "groovy.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_groovy_class_start_pathological(payload, expected_name):
    assert_pathological_match(GROOVY_RULES["class_start"], payload, expected_name, "groovy.class_start")
    assert_redos_immune(GROOVY_RULES["class_start"], payload)


# ==============================================================================
# DEPENDENCY (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("import foo.bar.Baz", "foo.bar.Baz"),
        ("import static java.lang.Math.PI", "java.lang.Math.PI"),
        ("import java.util.concurrent.atomic.AtomicInteger as AtomicInt", "java.util.concurrent.atomic.AtomicInteger"),
        ("import java.util.*", "java.util.*"),
        ("import foo.bar.Baz;", "foo.bar.Baz"),
    ],
    "invalid": [
        "def importData() {",
        'String myImport = "import foo.bar"',
        "// import java.util.List",
        'String s = "import java.util.List"',
        "importantVariable = true",
    ],
    "pathological": [
        ("import \\\n  java.util.List", "java.util.List"),
        ("import      java  .  util  .  Map", "java  .  util  .  Map"),
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_groovy_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(
        GROOVY_RULES["_dependency_capture"], payload, expected_path, "groovy._dependency_capture"
    )


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_groovy_dependency_capture_invalid(payload):
    assert_invalid_no_match(GROOVY_RULES["_dependency_capture"], payload, "groovy._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_groovy_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        GROOVY_RULES["_dependency_capture"], payload, expected_path, "groovy._dependency_capture"
    )
    assert_redos_immune(GROOVY_RULES["_dependency_capture"], payload)

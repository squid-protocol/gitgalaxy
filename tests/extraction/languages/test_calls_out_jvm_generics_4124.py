"""
#4124 (calls_out contract C3, docs/calls_out_rule_contract.md): JVM constructor and generic
calls with a type-argument list between the callee and its `(`.

java, kotlin and groovy used `(?<!@)\\b(name)\\s*\\(`, so `new HashMap<K, V>()`, the Java diamond
`new ArrayList<>(xs)`, Kotlin `ArrayDeque<T>()` and `register<Copy>("x")` were missed: all 35
occurrences of the graph-comparison ledger shape
`java/call/object_creation_expression/generic_type+generic/agree[tree_sitter]_vs[gitgalaxy]`.
They now use `CALLS_OUT_C_STYLE_GENERIC_NO_ANNOTATION`. It keeps the `@Name(` annotation guard
(C1) and accepts an empty list.

Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards._shared_patterns import (
    CALLS_OUT_C_STYLE_GENERIC_NO_ANNOTATION,
    QUALIFIED_CALLS_OUT_PATTERNS,
)

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore


def _functions(lang: str, code: str) -> dict[str, dict]:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}


def _callees(text: str) -> list[str]:
    return [m.group(1) for m in CALLS_OUT_C_STYLE_GENERIC_NO_ANNOTATION.finditer(text)]


def test_pattern_is_registered_and_used_by_the_jvm_languages():
    assert CALLS_OUT_C_STYLE_GENERIC_NO_ANNOTATION in QUALIFIED_CALLS_OUT_PATTERNS
    for lang in ("java", "kotlin", "groovy"):
        assert LANGUAGE_DEFINITIONS[lang]["rules"]["calls_out"] is CALLS_OUT_C_STYLE_GENERIC_NO_ANNOTATION


@pytest.mark.parametrize(
    "text, callee",
    [
        ("new HashMap<String, Object>()", "HashMap"),  # DefaultPluginManager.java:355
        ("new ArrayList<>(candidates.length)", "ArrayList"),  # the diamond
        ("new TreeMap<Project, Set<Task>>()", "TreeMap"),  # one nesting level
        ("new Action<Project>() {", "Action"),  # an anonymous class
        ("ArrayDeque<AsyncCall>()", "ArrayDeque"),  # kotlin: no `new`
        ('tasks.register<Copy>("copyKotlinTemplates")', "register"),  # kotlin generic function
        ("plain(x)", "plain"),
    ],
)
def test_generic_call_is_captured(text, callee):
    assert _callees(text) == [callee]


@pytest.mark.parametrize(
    "text",
    [
        "@SuppressWarnings(x)",  # C1: an annotation is a declaration
        "a < b > (c)",  # a comparison with blanks never opens a list
        "x<y || z>(w)",  # `|` never inside a type-argument list
        "a<b\n>(c)",  # one line only
    ],
)
def test_annotation_and_comparison_shapes_are_not_calls(text):
    assert not {"SuppressWarnings", "a", "x"} & set(_callees(text))


def test_generic_declaration_is_not_a_call():
    # The type before a method name is never followed by `(`: `List<T> foo(` calls nothing.
    assert _callees("public <T> List<T> foo(T t) {") == ["foo"]


def test_java_generic_constructors_reach_calls_out():
    code = (
        "class P {\n"
        "    public Object model() {\n"
        "        Map<String, Object> map = new HashMap<String, Object>();\n"
        "        List<String> xs = new ArrayList<>(map.keySet());\n"
        "        Action<Project> action = new Action<Project>() {\n"
        "        };\n"
        "        return wrap(map, xs);\n"
        "    }\n"
        "}\n"
    )
    funcs = _functions("java", code)
    assert set(funcs["model"]["calls_out_to"]) == {"HashMap", "ArrayList", "keySet", "Action", "wrap"}
    # #3835: the arity skips the type arguments, the diamond included.
    assert funcs["model"]["calls_out_arities"]["ArrayList"] == [1]
    assert funcs["model"]["calls_out_arities"]["HashMap"] == [0]


def test_kotlin_generic_calls_reach_calls_out():
    code = "fun start() {\n    val q = ArrayDeque<AsyncCall>()\n    val xs = mutableListOf<AsyncCall>()\n}\n"
    assert set(_functions("kotlin", code)["start"]["calls_out_to"]) == {"ArrayDeque", "mutableListOf"}


@pytest.mark.parametrize(
    "payload",
    [
        "a<" * 50000,
        "a<" + "b" * 100000,
        "a<" + "<b>" * 50000,
        "a<b" + ",c" * 50000 + ">",
        "x<" + " " * 100000 + ">(",
        "f<g<h>" * 20000,
        "a<>" * 50000,
        "@" + "a" * 100000 + "<>(",
    ],
)
def test_redos_immunity(payload):
    assert_redos_immune(CALLS_OUT_C_STYLE_GENERIC_NO_ANNOTATION, payload, timeout_sec=3.0)

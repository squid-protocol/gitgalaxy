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
    CALLS_OUT_KOTLIN,
    QUALIFIED_CALLS_OUT_PATTERNS,
)

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore


def _functions(lang: str, code: str) -> dict[str, dict]:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}


def _callees(text: str, pattern=CALLS_OUT_C_STYLE_GENERIC_NO_ANNOTATION) -> list[str]:
    return [m.group(1) for m in pattern.finditer(text)]


def test_pattern_is_registered_and_used_by_the_jvm_languages():
    assert CALLS_OUT_C_STYLE_GENERIC_NO_ANNOTATION in QUALIFIED_CALLS_OUT_PATTERNS
    for lang in ("java", "groovy"):
        assert LANGUAGE_DEFINITIONS[lang]["rules"]["calls_out"] is CALLS_OUT_C_STYLE_GENERIC_NO_ANNOTATION
    # #6266: kotlin's variant adds the trailing-lambda call
    assert CALLS_OUT_KOTLIN in QUALIFIED_CALLS_OUT_PATTERNS
    assert LANGUAGE_DEFINITIONS["kotlin"]["rules"]["calls_out"] is CALLS_OUT_KOTLIN


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


# --- #6266: Kotlin trailing-lambda calls (`ev.withKey { .. }`, no parentheses) ---


@pytest.mark.parametrize(
    "text, callee",
    [
        ("ev.withKey { sc -> use(sc) }", "withKey"),  # DoomMain.kt
        ("U.pool!!.submit { task() }", "submit"),  # a `!!` receiver
        ("rio.readLines { line: String? ->", "readLines"),
        ("relationMapper.accept{ type, relations ->", "accept"),  # no blank before the brace
        ("ev?.ifKey { sc -> sc }", "ifKey"),  # a safe call
        ("tasks.register<Copy> { it.from(x) }", "register"),  # a type argument before the lambda
        ("ArrayDeque<AsyncCall>()", "ArrayDeque"),  # the #4124 shapes still hold
        ('tasks.register<Copy>("copy")', "register"),
    ],
)
def test_kotlin_trailing_lambda_call_is_captured(text, callee):
    assert callee in _callees(text, CALLS_OUT_KOTLIN)


@pytest.mark.parametrize(
    "text, absent",
    [
        ("else {", "else"),  # a keyword block
        ("init { x() }", "init"),
        ("class Foo {", "Foo"),
        ("foo { x }", "foo"),  # a bare name: a local, a keyword form or a declaration, never read as a call
        ("xs.map { it }", "map"),  # stdlib scope and iteration functions are not resolvable by name
        ("x.let { it }", "let"),
        ("x.apply { y = 1 }", "apply"),
        ("xs.forEach { f(it) }", "forEach"),
        ("val p = a.b\n{", "b"),  # the brace must follow on the same line
    ],
)
def test_kotlin_trailing_lambda_shapes_that_are_not_calls(text, absent):
    assert absent not in _callees(text, CALLS_OUT_KOTLIN)


def test_kotlin_stdlib_name_with_parentheses_is_still_a_call():
    assert _callees("xs.map(f); x.let(g)", CALLS_OUT_KOTLIN) == ["map", "let"]


def test_kotlin_trailing_lambda_reaches_calls_out_with_its_receiver():
    code = (
        "class Menu {\n"
        "    fun Responder(ev: Event): Boolean {\n"
        "        if (ev.ifKey { sc -> keys.notify(sc) }) return true\n"
        "        xs.forEach { show(it) }\n"
        "        return ev.withMouse { m -> m.done() }\n"
        "    }\n"
        "}\n"
    )
    func = _functions("kotlin", code)["Responder"]
    assert {"ifKey", "withMouse", "notify", "done", "show"} <= set(func["calls_out_to"])
    assert "forEach" not in func["calls_out_to"]
    assert func["calls_out_qualifiers"]["ifKey"] == ["ev"]


@pytest.mark.parametrize(
    "payload",
    [
        "a." + "b" * 100000,
        "a." + "b {" * 50000,
        "." + "a." * 50000 + "{",
        "a.b<" + "c" * 100000,
        "a.b<" + "<c>" * 50000,
        "x.y" + " " * 100000 + "{",
        "@" + "a" * 100000 + "{",
    ],
)
def test_kotlin_pattern_redos_immunity(payload):
    assert_redos_immune(CALLS_OUT_KOTLIN, payload, timeout_sec=3.0)

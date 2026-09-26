"""
#3644 (contracts C3, decision 2, docs/calls_out_rule_contract.md): three calls_out shapes in
C++/TypeScript/C#.

1. A type-argument list between the callee and its `(` (`static_cast<int>(`,
   `Object::cast_to<T>(`, `new Array<T>()`) defeated `\\b(name)\\s*\\(`. cpp, typescript and
   csharp now use `CALLS_OUT_C_STYLE_GENERIC`.
2. An out-of-class `Class::method` unit's own header was a call to `method`: recursion was
   compared with the qualified unit name. It is now compared with the leaf.
3. C++ `Type var(args)` took the variable as the callee. The constructor called is the type;
   a built-in type or a pointer/reference declarator calls nothing.

Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards._shared_patterns import (
    CALLS_OUT_C_STYLE,
    CALLS_OUT_C_STYLE_GENERIC,
    QUALIFIED_CALLS_OUT_PATTERNS,
)

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore


def _functions(lang: str, code: str) -> dict[str, dict]:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}


def _calls(lang: str, code: str) -> dict[str, list[str]]:
    return {name: f["calls_out_to"] for name, f in _functions(lang, code).items()}


def _callees(text: str) -> list[str]:
    return [m.group(1) for m in CALLS_OUT_C_STYLE_GENERIC.finditer(text)]


# ----------------------------------------------------------------------------- 1. generics


def test_generic_pattern_is_registered_and_used():
    assert CALLS_OUT_C_STYLE_GENERIC in QUALIFIED_CALLS_OUT_PATTERNS
    for lang in ("cpp", "typescript", "csharp"):
        assert LANGUAGE_DEFINITIONS[lang]["rules"]["calls_out"] is CALLS_OUT_C_STYLE_GENERIC
    for lang in ("c", "javascript", "python"):  # go has its own since #3645
        assert LANGUAGE_DEFINITIONS[lang]["rules"]["calls_out"] is CALLS_OUT_C_STYLE


@pytest.mark.parametrize(
    "text, callee",
    [
        ("static_cast<int>(x)", "static_cast"),
        ("pair<A,int>(a, 1)", "pair"),
        ("back_inserter<vector<wstring> >(out)", "back_inserter"),
        ("new Array<ExpressionRef>()", "Array"),
        ("new Map<string, number[]>()", "Map"),
        ("forward<T&&>(t)", "forward"),
        ("plain(x)", "plain"),
    ],
)
def test_generic_call_is_captured(text, callee):
    assert _callees(text) == [callee]


@pytest.mark.parametrize(
    "text",
    [
        "a < b > (c)",  # a comparison with blanks never opens a list
        "x<y || z>(w)",  # `|` never inside a type-argument list
        "f<a = b>(c)",  # nor `=`
        "a<b\n>(c)",  # one line only
        "g<h(1)>(2)",  # nor a call inside the brackets
    ],
)
def test_comparison_shapes_are_not_generic_calls(text):
    assert not any(name in {"a", "x", "f", "g"} for name in _callees(text))


def test_two_level_nested_type_arguments_are_a_known_gap():
    # One nesting level keeps the pattern bounded; `make<vector<vector<int>>>(` is missed.
    assert _callees("make<vector<vector<int>>>(n)") == []


def test_generic_calls_reach_calls_out():
    cpp = "void run(int a) {\n    auto x = static_cast<int>(a);\n    auto d = Object::cast_to<EditorDock>(w);\n}\n"
    funcs = _functions("cpp", cpp)
    assert funcs["run"]["calls_out_to"] == ["static_cast", "cast_to"]
    assert funcs["run"]["calls_out_qualifiers"]["cast_to"] == ["Object"]
    ts = "function f() {\n  const x = new Array<ExpressionRef>();\n  return helper<number>(1);\n}\n"
    assert _calls("typescript", ts)["f"] == ["Array", "helper"]
    cs = "class C {\n  public int F(int a) {\n    var l = new List<int>();\n    return Go<string>(a);\n  }\n}\n"
    assert _calls("csharp", cs)["F"] == ["List", "Go"]


@pytest.mark.parametrize(
    "payload",
    [
        "a<" * 50000,
        "a<" + "b" * 100000,
        "a<" + "<b>" * 50000,
        "a<b" + ",c" * 50000 + ">",
        "x<" + " " * 100000 + ">(",
        ("f<g<h>" * 20000),
    ],
)
def test_generic_calls_out_redos_immunity(payload):
    assert_redos_immune(CALLS_OUT_C_STYLE_GENERIC, payload, timeout_sec=3.0)


# ----------------------------------------------------------------------------- 2. leaf recursion


def test_same_named_call_on_another_receiver_stays():
    # Only the unit itself (unqualified, `this->`, its own class) is recursion; `child->m(` is
    # a call to another object's method, which tree-sitter's side counts too.
    code = (
        "int Node::getText(int a) {\n    child->getText(a);\n    this->getText(a - 1);\n"
        "    Node::getText(0);\n    return getText(a - 2);\n}\n"
    )
    funcs = _functions("cpp", code)
    (name,) = funcs
    assert funcs[name]["calls_out_to"] == ["getText"]
    assert funcs[name]["calls_out_qualifiers"]["getText"] == ["child"]


def test_out_of_class_header_is_not_a_call_to_itself():
    code = "int Buffer::getLineOffsets(int a) {\n    return compute(a);\n}\n"
    calls = _calls("cpp", code)
    (name,) = calls
    assert name.endswith("getLineOffsets")
    assert calls[name] == ["compute"]


# ----------------------------------------------------------------------------- 3. Type var(args)

_DECLS = (
    "void run(Mutex m) {\n"
    '    EditorProgress progress("x", 3);\n'
    "    MutexLock lock(m);\n"
    "    static std::vector<int> v(10);\n"
    "    int n(5);\n"
    "    Foo* p(q);\n"
    "    Foo& r(s);\n"
    "    return compute(n);\n"
    "}\n"
)


def test_declared_variable_is_not_the_callee_its_type_is():
    calls = _calls("cpp", _DECLS)["run"]
    assert calls == ["EditorProgress", "MutexLock", "vector", "compute"]
    for var in ("progress", "lock", "v", "n", "p", "r"):
        assert var not in calls


def test_keyword_before_a_call_is_not_a_type():
    code = "Foo* make(int a) {\n    if (a) return build(a);\n    throw Error(a);\n    return new Widget(a);\n}\n"
    assert _calls("cpp", code)["make"] == ["build", "Error", "Widget"]


def test_own_header_return_type_is_not_a_call():
    # Only the body is read for declarations: `Status run(` is the unit's own header.
    code = "Status run(int a) {\n    return step(a);\n}\n"
    assert _calls("cpp", code)["run"] == ["step"]


def test_assignment_and_argument_positions_stay_calls():
    code = "void run() {\n    x = make(1);\n    use(a, b(c));\n}\n"
    assert _calls("cpp", code)["run"] == ["make", "use", "b"]


def test_member_call_after_a_comparison_is_not_a_declaration():
    # godot editor_node.cpp:865: the `>` of `->` is not a template close, so `i` is no type.
    code = "void run() {\n    for (int i = 0; i < renderer->get_item_count(); i++) {\n        p->x(i);\n    }\n}\n"
    assert _calls("cpp", code)["run"] == ["get_item_count", "x"]


def test_declarator_rewrite_is_cpp_only():
    # `Type var(` is not a declaration shape in C# or TypeScript.
    assert not LANGUAGE_DEFINITIONS["csharp"].get("calls_out_declarator_constructs")
    assert not LANGUAGE_DEFINITIONS["typescript"].get("calls_out_declarator_constructs")
    assert "calls_out_declarator_constructs" not in LANGUAGE_DEFINITIONS["cpp"]["rules"]

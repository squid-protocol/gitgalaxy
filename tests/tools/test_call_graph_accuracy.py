"""#3332 Level 1: the tree-sitter side of call_graph_accuracy.py names callees the
way the #3327 contract does (rightmost identifier, constructors and macros count)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
pytest.importorskip("tree_sitter_language_pack")

import call_graph_accuracy as cga
import tree_sitter_accuracy_audit as audit


def _calls(lang, src):
    return {name: calls for name, _, calls, _node in cga.ts_functions(src.encode(), lang, audit)}


def test_python_callees_rightmost_and_nested_attribution():
    got = _calls("python", "def run(x):\n    a.b.save(x)\n    Foo()\n    def inner():\n        helper()\n")
    assert got == {"run": {"save", "Foo"}, "inner": {"helper"}}


def test_rust_scoped_constructor_and_macro():
    got = _calls("rust", 'fn run() {\n    let x = ControlFlow::Continue(1);\n    println!("{}", x);\n}\n')
    assert got == {"run": {"Continue", "println"}}


def test_java_constructor_and_method():
    got = _calls("java", "class A {\n  void run() {\n    new Foo().save();\n  }\n}\n")
    assert got == {"run": {"Foo", "save"}}


def test_pairing_drops_recursion_and_needs_nearby_lines():
    gg = [("run", 1, ["run", "save"]), ("far", 50, ["x"])]
    ts = [("run", 2, {"run", "save", "load"}, "run-node"), ("far", 10, {"x"}, "far-node")]
    assert cga._pair(gg, ts) == [("run", {"save"}, {"save", "load"}, "run-node")]


def test_cause_labels_inner_function_calls_and_non_calls():
    """--buckets: a call tree-sitter gives to an inner function, and a name that is no call."""
    src = b"def outer(x):\n    def inner():\n        save(x)\n    return inner\n"
    fns = {n: node for n, _, _, node in cga.ts_functions(src, "python", audit)}
    assert cga._cause("fp", "save", fns["outer"], "python", audit, False)[0] == ("fp:inner-named-function_definition")
    assert cga._cause("fp", "x", fns["outer"], "python", audit, False)[0].startswith("fp:not-a-call-in-ts:")
    assert cga._cause("fp", "nowhere", fns["outer"], "python", audit, False)[0] == "fp:outside-ts-function"


def test_regressions_respect_the_tolerance():
    base = {"c": {"matched_functions": 5, "precision_pct": 90.0, "recall_pct": 80.0}}
    assert cga.regressions({"c": {"precision_pct": 89.6, "recall_pct": 80.0}}, base) == []
    assert cga.regressions({"c": {"precision_pct": 89.0, "recall_pct": 80.0}}, base) == [
        "c: precision_pct 90.0 -> 89.0"
    ]


def test_c8_anonymous_function_calls_belong_to_the_enclosing_unit():
    """C8 (#3641): a callback is no unit of its own; its calls are the enclosing function's."""
    got = _calls(
        "javascript", "function run(xs) {\n  xs.forEach(function (x) { save(x); });\n  xs.map((y) => load(y));\n}\n"
    )
    assert got == {"run": {"forEach", "save", "map", "load"}}


def test_c8_nested_named_function_keeps_its_own_calls():
    got = _calls("python", "def outer(x):\n    def inner():\n        save(x)\n    return inner()\n")
    assert got["outer"] == {"inner"} and got["inner"] == {"save"}


def test_c3_go_conversion_is_a_call():
    got = _calls("go", "package m\nfunc Run(s string) {\n  w([]byte(s))\n}\n")
    assert got == {"Run": {"w", "byte"}}


@pytest.mark.parametrize(
    "lang, src, fn, callee",
    [
        ("rust", "fn run(xs: I) {\n  let v = xs.collect::<Vec<u8>>();\n}\n", "run", "collect"),
        ("csharp", "class A {\n  void Run(object[] xs) {\n    xs.OfType<Location>();\n  }\n}\n", "Run", "OfType"),
        ("java", "class A {\n  void run() {\n    Map m = new HashMap<String, Object>();\n  }\n}\n", "run", "HashMap"),
    ],
)
def test_generic_callee_is_the_function_not_its_type_argument(lang, src, fn, callee):
    assert _calls(lang, src)[fn] == {callee}

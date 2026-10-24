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


def test_cpp_qualified_unit_drops_its_own_leaf_recursion_only():
    # #3644: `Node::walk` calling bare `walk(`, `this->walk(` or `Node::walk(` is recursion;
    # `child->walk(` is another object's method and stays a call.
    src = (
        "int Node::walk(int a) {\n  walk(a - 1);\n  this->walk(a - 2);\n  Node::walk(0);\n"
        "  return other(a);\n}\n"
        "int Node::step(int a) {\n  return child->step(a);\n}\n"
    )
    got = _calls("cpp", src)
    assert got["Node::walk"] == {"other"}
    assert got["Node::step"] == {"step"}


@pytest.mark.parametrize(
    "lang, src, expected",
    [
        (
            "kotlin",
            "class A {\n  fun run(x: Int) {\n    a.b.save(x)\n    Foo(1)\n    xs.map { load(it) }\n  }\n}\n",
            {"save", "Foo", "map", "load"},
        ),
        (
            "scala",
            "object A {\n  def run(x: Int) = {\n    a.b.save(x)\n    new Foo(1)\n    Bar(2)\n    xs.map(y => load(y))\n  }\n}\n",
            {"save", "Foo", "Bar", "map", "load"},
        ),
        (
            "swift",
            "func run(x: Int) {\n  a.b.save(x)\n  Foo(1)\n  xs.map { load($0) }\n}\n",
            {"save", "Foo", "map", "load"},
        ),
        (
            "lua",
            "function run(x)\n  a.b.save(x)\n  obj:meth(1)\n  foo(2)\n  local f = function() load() end\nend\n",
            {"save", "meth", "foo", "load"},
        ),
    ],
)
def test_qualified_bare_constructor_and_callback_callees(lang, src, expected):
    """Step 2 of #3641: kotlin / scala / swift / lua name the rightmost identifier, count a
    constructor, and keep a callback's calls with the enclosing unit (C8)."""
    assert _calls(lang, src)["run"] == expected


@pytest.mark.parametrize("lang", cga.LANGS)
def test_every_measured_language_has_a_function_map_and_a_firing_call_node(lang):
    spec = audit.NODE_MAPS[lang]
    assert spec["func_node_types"] and cga.CALL_NODE_TYPES


def test_kotlin_decoys_in_string_and_comment_are_not_calls():
    got = _calls("kotlin", 'fun run() {\n  val s = "save(1)"\n  // load(2)\n  keep()\n}\n')
    assert got == {"run": {"keep"}}


def test_swift_subscript_is_not_a_call_but_a_call_on_one_is():
    got = _calls("swift", 'func run(r: R) {\n  let h = r.headers["k"]\n  r.items[0].save()\n}\n')
    assert got == {"run": {"save"}}


def test_scala_qualified_generic_constructor_names_the_type():
    got = _calls("scala", "object A {\n  def run() = new util.HashSet[T]()\n}\n")
    assert got == {"run": {"HashSet"}}

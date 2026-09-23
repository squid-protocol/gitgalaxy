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
    return {name: calls for name, _, calls in cga.ts_functions(src.encode(), lang, audit)}


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
    ts = [("run", 2, {"run", "save", "load"}), ("far", 10, {"x"})]
    assert cga._pair(gg, ts) == [("run", {"save"}, {"save", "load"})]


def test_regressions_respect_the_tolerance():
    base = {"c": {"matched_functions": 5, "precision_pct": 90.0, "recall_pct": 80.0}}
    assert cga.regressions({"c": {"precision_pct": 89.6, "recall_pct": 80.0}}, base) == []
    assert cga.regressions({"c": {"precision_pct": 89.0, "recall_pct": 80.0}}, base) == [
        "c: precision_pct 90.0 -> 89.0"
    ]

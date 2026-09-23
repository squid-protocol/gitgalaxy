"""
The `calls_out` contract (#3327, docs/calls_out_rule_contract.md), pinned end to end through
`StructuralExtractor.splice()` -- the same path a scan takes, including the literal shield and
the global/per-language ignore sets, which a bare-regex test would miss.

The corollaries the engine already honours are ordinary tests. The disagreements the audit
filed (#3359-#3361) are strict xfails: each one flips to XPASS, and fails the suite, the day its
fix lands, so the fix PR has to move the pin from here into the passing set.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _calls(lang: str, code: str) -> dict[str, list[str]]:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f["calls_out_to"] for f in functions}


_PY = (
    "def walk(node, xs):\n"
    "    obj.save()\n"
    "    utils.parse(node)\n"
    "    Foo(1)\n"
    "    map(visit, xs)\n"
    '    s = "ghost(1)"\n'
    "    walk(node)\n"
    "    helper()\n"
    "    helper()\n"
    "    if (node): pass\n"
)


def test_bare_name_dedup_no_recursion_and_order():
    # C6: bare names, qualifier dropped; decisions 2+3: deduplicated, self-recursion removed;
    # first-occurrence order is part of the persisted JSON.
    assert _calls("python", _PY)["walk"] == ["save", "parse", "Foo", "helper"]


def test_reference_is_not_a_call():
    # C1: `visit` is passed to map, never invoked.
    assert "visit" not in _calls("python", _PY)["walk"]


def test_keyword_and_string_are_not_calls():
    # C2 keyword `if (`; C7 the literal shield hides `ghost(` inside a string.
    walk = _calls("python", _PY)["walk"]
    assert "if" not in walk
    assert "ghost" not in walk


@pytest.mark.parametrize(
    "lang, code, fn, callee",
    [
        ("javascript", "function run(a) {\n  const f = new Foo(a);\n}\n", "run", "Foo"),
        ("java", "class A {\n  void run(int a) {\n    Foo f = new Foo(a);\n  }\n}\n", "run", "Foo"),
        ("go", "package m\nfunc Run(a int) {\n  x := uint32(a)\n  use(x)\n}\n", "Run", "uint32"),
        ("c", "void run(PyObject *o) {\n  Py_DECREF(o);\n}\n", "run", "Py_DECREF"),
    ],
)
def test_constructors_conversions_and_macros_are_calls(lang, code, fn, callee):
    # C3
    assert callee in _calls(lang, code)[fn]


def test_load_form_is_owned_by_import():
    # C2 / COUNT_CONTRACT corollary 4: `require(` is the import rule's statement.
    assert "require" not in _calls("javascript", 'function run() {\n  const r = require("x");\n  go(r);\n}\n')["run"]


def test_blind_languages_declare_blindness():
    # C7: a blind language carries no calls_out pattern at all, never a guess.
    blind = [
        lang
        for lang, d in LANGUAGE_DEFINITIONS.items()
        if isinstance(d, dict) and d.get("rules", {}).get("calls_out") is None
    ]
    assert "shell" in blind and "yaml" in blind
    for lang in blind:
        assert not hasattr(LANGUAGE_DEFINITIONS[lang]["rules"].get("calls_out"), "finditer")


# --- Filed disagreements: strict xfails that flip when the follow-up lands -------------------


@pytest.mark.xfail(strict=True, reason="#3361: built-ins are calls; _CALLS_OUT_GLOBAL_IGNORE still filters them")
def test_builtins_are_calls():
    code = "def run(xs):\n    print(len(xs))\n"
    assert {"print", "len"} <= set(_calls("python", code)["run"])


@pytest.mark.xfail(strict=True, reason="#3360: a nested declaration header is captured as a call")
def test_nested_declaration_is_not_a_call():
    code = "def outer(x):\n    def inner(y):\n        return y\n    return inner\n"
    assert "inner" not in _calls("python", code)["outer"]


@pytest.mark.xfail(strict=True, reason="#3359: a metadata annotation is captured as a call")
def test_annotation_is_not_a_call():
    code = 'class A {\n  @SuppressWarnings("x")\n  void run(int a) {\n    go(a);\n  }\n}\n'
    assert "SuppressWarnings" not in _calls("java", code)["run"]


@pytest.mark.xfail(strict=True, reason="#3359: go's `func` literal keyword is captured as a call")
def test_func_literal_keyword_is_not_a_call():
    code = "package m\nfunc Run(a int) {\n  go func() { work(a) }()\n}\n"
    assert "func" not in _calls("go", code)["Run"]

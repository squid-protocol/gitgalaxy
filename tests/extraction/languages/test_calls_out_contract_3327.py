"""
The `calls_out` contract (#3327, docs/calls_out_rule_contract.md), pinned end to end through
`StructuralExtractor.splice()` -- the same path a scan takes, including the literal shield and
the global/per-language ignore sets, which a bare-regex test would miss.

The corollaries the engine already honours are ordinary tests. The disagreements the audit
filed (#3359, #3360) are strict xfails: each one flips to XPASS, and fails the suite, the day its
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
    # first-occurrence order is part of the persisted JSON. `map` is a built-in, so a call (C2).
    assert _calls("python", _PY)["walk"] == ["save", "parse", "Foo", "map", "helper"]


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


@pytest.mark.parametrize(
    "lang, code, fn, callees",
    [
        ("python", "def run(xs):\n    print(len(xs))\n", "run", {"print", "len"}),
        ("javascript", "function run(a) {\n  console.log(a);\n}\n", "run", {"log"}),
        ("c", 'int run(int a) {\n  printf("%d", a);\n  return 0;\n}\n', "run", {"printf"}),
        ("lua", "function run(t)\n  for k in pairs(t) do print(k) end\nend\n", "run", {"pairs", "print"}),
    ],
)
def test_builtins_are_calls(lang, code, fn, callees):
    # C2 / decision 1 (#3361): a built-in or stdlib function is a call; the resolver labels it
    # `external`. Only keywords are filtered.
    assert callees <= set(_calls(lang, code)[fn])


@pytest.mark.parametrize(
    "lang, code, fn",
    [
        ("python", "def run(x):\n    assert(x)\n    go(x)\n", "run"),
        ("java", "class A {\n  void run(int x) {\n    assert(x > 0);\n    go(x);\n  }\n}\n", "run"),
        ("dart", "void run(int x) {\n  assert(x > 0);\n  go(x);\n}\n", "run"),
    ],
)
def test_assert_keyword_is_not_a_call(lang, code, fn):
    # C2 (#3361): `assert` left the global set because C's `assert(` is a macro (a call, C3),
    # but where it is a statement keyword the language's own ignore set keeps it out.
    calls = _calls(lang, code)[fn]
    assert "assert" not in calls and "go" in calls


@pytest.mark.parametrize(
    "lang, code, fn",
    [
        ("javascript", "class B extends A {\n  constructor(x) {\n    super(x);\n    go(x);\n  }\n}\n", "constructor"),
        ("java", "class B extends A {\n  B(int x) {\n    super(x);\n    go(x);\n  }\n}\n", "B"),
    ],
)
def test_super_keyword_is_not_a_call(lang, code, fn):
    # C2 (#3361): constructor chaining through the `super` keyword, like java's `this(`.
    calls = _calls(lang, code)[fn]
    assert "super" not in calls and "go" in calls


def test_python_super_builtin_is_a_call():
    assert "super" in _calls("python", "def run(self):\n    super().run()\n")["run"]


def test_c_assert_macro_is_a_call():
    assert "assert" in _calls("c", "void run(int x) {\n  assert(x > 0);\n}\n")["run"]


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

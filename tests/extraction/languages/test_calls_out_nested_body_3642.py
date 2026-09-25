"""
#3642 (contract C8, docs/calls_out_rule_contract.md): a call belongs to the innermost named unit
around it. A call inside a nested *named* function is that function's only, never also the
enclosing one's; a call inside an *anonymous* function stays with the enclosing named unit.

`calls_out` scans a unit's whole block, so every call in a nested named unit used to be listed on
the outer unit too (#3360's C5 fix dropped only the nested header). The detector now blanks each
nested unit the slicer emitted out of the outer block before keeping a callee.

Each case: `outer` declares `inner`, which calls `deep`; `outer` itself calls `top` and then
`inner`. So `outer` lists `top` and `inner`, never `deep`, and `inner` lists `deep`. Driven
through `StructuralExtractor.splice()`, the path a scan takes.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _functions(lang: str, code: str) -> dict[str, dict]:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}


def _calls(lang: str, code: str) -> dict[str, list[str]]:
    return {name: f["calls_out_to"] for name, f in _functions(lang, code).items()}


_PY = "def outer(x):\n    top(x)\n    def inner(y):\n        return deep(y)\n    return inner(x)\n"

CASES = {
    "python": _PY,
    "embedded_python": _PY,
    "javascript": (
        "function outer(a) {\n  top(a);\n  function inner(b) {\n    return deep(b);\n  }\n  return inner(a);\n}\n"
    ),
    "typescript": (
        "function outer(a: number): number {\n  top(a);\n  function inner(b: number): number {\n"
        "    return deep(b);\n  }\n  return inner(a);\n}\n"
    ),
    "rust": (
        "fn outer(a: i32) -> i32 {\n    top(a);\n    fn inner(b: i32) -> i32 {\n        deep(b)\n    }\n"
        "    inner(a)\n}\n"
    ),
    "csharp": (
        "class C\n{\n    public int Outer(int a)\n    {\n        top(a);\n"
        "        int inner(int b)\n        {\n            return deep(b);\n        }\n"
        "        return inner(a);\n    }\n}\n"
    ),
}

_OUTER = {"csharp": "Outer"}


@pytest.mark.parametrize("lang", sorted(CASES))
def test_nested_named_unit_body_calls_are_not_the_outer_units(lang):
    calls = _calls(lang, CASES[lang])
    outer = calls[_OUTER.get(lang, "outer")]
    assert "deep" not in outer
    assert "top" in outer and "inner" in outer


@pytest.mark.parametrize("lang", sorted(CASES))
def test_nested_named_unit_keeps_its_own_calls(lang):
    assert "deep" in _calls(lang, CASES[lang])["inner"]


def test_callee_called_both_outside_and_inside_the_nested_unit_stays():
    code = "def outer(x):\n    log(x)\n    def inner(y):\n        return log(y)\n    return inner(x)\n"
    calls = _calls("python", code)
    assert calls["outer"] == ["log", "inner"]
    assert calls["inner"] == ["log"]


def test_qualifiers_come_only_from_the_outer_units_own_call_sites():
    code = "def outer(x):\n    a.save(x)\n    def inner(y):\n        return b.save(y)\n    return inner(x)\n"
    funcs = _functions("python", code)
    assert funcs["outer"]["calls_out_qualifiers"]["save"] == ["a"]
    assert funcs["inner"]["calls_out_qualifiers"]["save"] == ["b"]


def test_anonymous_function_calls_stay_with_the_enclosing_unit():
    # C8's second bullet: a lambda is not a unit, so its body is the outer body.
    code = "def outer(xs):\n    return sorted(xs, key=lambda x: weigh(x))\n"
    assert set(_calls("python", code)["outer"]) == {"sorted", "weigh"}


def test_doubly_nested_calls_belong_to_the_innermost_unit():
    code = (
        "def outer():\n    a()\n    def mid():\n        b()\n        def leaf():\n"
        "            c()\n        return leaf()\n    return mid()\n"
    )
    calls = _calls("python", code)
    assert calls["outer"] == ["a", "mid"]
    assert calls["mid"] == ["b", "leaf"]
    assert calls["leaf"] == ["c"]

"""#8867: a Java `catch` is a handler, not a decision (branch contract corollary 1); `&&` / `||` are."""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards.languages.java import DEFINITION as JAVA_DEFINITION


def _complexity(body: str) -> int:
    code = f"class A {{\n    int f(boolean a, boolean b) {{\n{body}\n    }}\n}}\n"
    funcs = StructuralExtractor("java", {"java": JAVA_DEFINITION}).splice(code, "")["functions"]
    return next(f for f in funcs if f["name"] == "f")["branch"]


def test_catch_adds_no_complexity():
    body = "try { return 1; } catch (Exception e) { return 2; } finally { a = false; }"
    assert _complexity(body) == _complexity("return 1;")


@pytest.mark.parametrize("op", ["&&", "||"])
def test_short_circuit_operators_count(op):
    assert _complexity(f"return a {op} b ? 1 : 0;") == _complexity("return a ? 1 : 0;") + 1


def test_operator_inside_a_string_literal_does_not_count():
    assert _complexity('String s = "a && b || c"; return 1;') == _complexity("return 1;")

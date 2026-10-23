"""
#5640 slice 2: Scheme calls inside a `lambda` belong to the enclosing named unit.

The DOOM Scheme port's `(melee-or-missile actor #f (lambda () (fx* (p-random) 4)) #f)` lost every call after the
`#f`: the literal shield read `#f` as a `#` line comment and blanked the rest of the line. Scheme's only line comment
is `;`. Owner ruling 2026-10-22: a lambda is never a unit, so its calls are the enclosing unit's.

Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _functions(code: str) -> dict[str, dict]:
    functions = StructuralExtractor("scheme", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}


@pytest.mark.parametrize(
    "literal",
    ["#f", "#t", "#\\a", "#\\space", "#x1F", "#(1 2)", "#u8(1 2)", "#true", "#false", "#;(ignored)"],
)
def test_calls_after_a_hash_literal_on_the_same_line_are_kept(literal):
    code = f"(define (caller a)\n  (run a {literal} (lambda () (inner (deep 1)))))\n"
    assert {"run", "inner", "deep"} <= set(_functions(code)["caller"]["calls_out_to"])


def test_a_lambda_is_not_a_unit_and_its_calls_go_to_the_enclosing_one():
    code = "(define (a-sarg actor)\n  (m actor #f (lambda () (fx* (fx+ (p-random) 10) 4)) #f))\n"
    functions = _functions(code)
    assert list(functions) == ["a-sarg"]
    assert functions["a-sarg"]["calls_out_to"] == ["m", "fx*", "fx+", "p-random"]


def test_a_semicolon_comment_still_hides_a_call():
    code = "(define (caller a)\n  (real a) ; (ghost a)\n  )\n"
    assert _functions(code)["caller"]["calls_out_to"] == ["real"]


@pytest.mark.parametrize("name", ["bytevector-copy/range", "list.tail", "string->number", "a%b", "ns:proc"])
def test_a_callee_name_keeps_its_punctuation(name):
    code = f"(define (caller a)\n  ({name} a 1))\n"
    assert _functions(code)["caller"]["calls_out_to"] == [name]

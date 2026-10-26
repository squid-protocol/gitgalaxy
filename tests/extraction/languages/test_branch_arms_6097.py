"""
#6097: two branch-count disagreements the DOOM study measured against the C original.

* Scheme: a `case` form counted once however many clauses it had (75 clauses read as 6, C reads 93). Each clause
  head `[(d ...) body]` is one arm; a `cond` test (`[(null? x) ...]`, `[(f a b) ...]`) is not a datum list.
* Dart: `break` / `continue` were branch hits; they are unconditional transfers and belong in
  `structural_boundaries` beside `return` (branch_rule_contract.md, #2832), as C has them.

Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _only_function(lang: str, code: str) -> dict:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    assert len(functions) == 1
    return functions[0]


@pytest.mark.parametrize(
    ("clauses", "arms"),
    [
        ("[(1) 0] [(2 3) 1]", 2),
        ("[(a) 0] [(b) 1] [(c) 2]", 3),
        ('[("s") 0] [(#\\a #\\b) 1]', 2),
        ("[(#t) 0] [(-1) 1]", 2),
        ("[(a b) 0]", 0),
        ("[else 0]", 0),
    ],
)
def test_each_scheme_case_clause_is_one_branch(clauses, arms):
    fn = _only_function("scheme", f"(define (f k)\n  (case k {clauses}))\n")
    assert fn["branch_count"] == 1 + arms  # the `case` itself, then one per clause


@pytest.mark.parametrize("test", ["[(null? x) 1]", "[(f a b) 1]", "[(= x 1) 1]", "[(pair? (car x)) 1]"])
def test_a_scheme_cond_call_test_is_not_a_case_clause(test):
    fn = _only_function("scheme", f"(define (g x)\n  (cond {test} [else 2]))\n")
    assert fn["branch_count"] == 1  # only the `cond`


@pytest.mark.parametrize("word", ["break", "continue"])
def test_dart_break_and_continue_are_not_branches(word):
    fn = _only_function(
        "dart", f"void f(int n) {{\n  while (n > 0) {{\n    if (n == 3) {{ {word}; }}\n    n--;\n  }}\n}}\n"
    )
    assert fn["branch_count"] == 2  # `while` and `if`


def test_dart_switch_arms_are_still_counted():
    fn = _only_function(
        "dart", "void f(int k) {\n  switch (k) {\n    case 1:\n      break;\n    default:\n      break;\n  }\n}\n"
    )
    assert fn["branch_count"] == 3  # switch, case, default

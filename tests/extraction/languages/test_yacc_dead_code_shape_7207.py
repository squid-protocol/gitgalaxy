"""#7207 slice 2 (yacc): dead_code counts a keyword-led comment only when it has a statement's shape."""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

POSITIVES = [
    "// if (x) {",
    "// if (ok) return;",
    "// for (i = 0; i < n; i++) {",
    "// while (p) p = p->next;",
    "// return x;",
    "// return foo(a, b)",
    "/* if (a > 1) */",
    "/* return 0; */",
    "// %token NUM",
    "// %token <ival> NUM",
    "// %token PLUS MINUS TIMES",
    "/* %token <sval> IDENT */",
]

NEGATIVES = [
    "// if the parse fails, we retry",
    "// for each rule in the grammar",
    "// while waiting for input",
    "// return value is ignored",
    "// return to the caller",
    "// %token is declared here",
    "// %token names are uppercase by convention",
    "/* if the stack is empty we stop */",
    "/// return value is documented",
]


def _rule():
    return LANGUAGE_DEFINITIONS["yacc"]["rules"]["dead_code"]


@pytest.mark.parametrize("line", POSITIVES)
def test_commented_out_statement_counts(line):
    assert _rule().search(line + "\n")


@pytest.mark.parametrize("line", NEGATIVES)
def test_prose_does_not_count(line):
    assert not _rule().search(line + "\n")


def test_long_line_stays_fast():
    assert not _rule().search("// if " + "(a " * 5000 + "\n")
    assert not _rule().search("// %token " + "A " * 5000 + "x\n")

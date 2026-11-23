"""#8927: Scheme/Racket `closures` counts the Greek-letter lambda; `panics_and_aborts` counts the raise family."""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

RULES = LANGUAGE_DEFINITIONS["scheme"]["rules"]
LAM = chr(0x3BB)


@pytest.mark.parametrize("code", [f"(map ({LAM} (y) y) x)", "(map (lambda (y) y) x)"])
def test_closures_counts_both_spellings(code):
    assert len(RULES["closures"].findall(code)) == 1


@pytest.mark.parametrize("code", [f"(define {LAM}x 1)", f"(m{LAM} 1)", f"({LAM}x 1)"])
def test_closures_rejects_a_longer_symbol(code):
    assert not RULES["closures"].search(code)


@pytest.mark.parametrize(
    "code",
    [
        "(raise 'bad)",
        '(raise-user-error \'x "m")',
        '(raise-argument-error \'f "int" 1)',
        '(raise-arguments-error \'f "m")',
        '(raise-result-error \'f "int" 1)',
        '(raise-range-error \'f "v" "i" 1 v 0 1)',
        '(raise-type-error \'f "int" 1)',
        '(raise-syntax-error \'f "m")',
        "(raise-exception e)",
        "(throw 'key)",
        '(error "x")',
    ],
)
def test_panics_counts_the_raise_family(code):
    assert len(RULES["panics_and_aborts"].findall(code)) == 1


@pytest.mark.parametrize("code", ["(raised x)", "(raise-foo-bar x)", "(my-raise x)", "(thrown x)"])
def test_panics_rejects_a_longer_symbol(code):
    assert not RULES["panics_and_aborts"].search(code)


def test_issue_cases_end_to_end():
    code = f"#lang racket\n(define (lam x) (map ({LAM} (y) y) x))\n(define (rs x) (raise 'bad))\n"
    funcs = StructuralExtractor("scheme", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    assert {"lam", "rs"} <= {f["name"] for f in funcs}
    assert len(RULES["closures"].findall(code)) == 1
    assert len(RULES["panics_and_aborts"].findall(code)) == 1

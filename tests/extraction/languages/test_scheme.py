
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _extraction_harness import (
    assert_invalid_no_match,
    assert_pathological_match,
    assert_valid_match,
)
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

scheme_rules = LANGUAGE_DEFINITIONS["scheme"]["rules"]
FUNC_START = scheme_rules.get("func_start")
ARGS = scheme_rules.get("args")
CLASS_START = scheme_rules.get("class_start")

FUNCTION_CASES = {
    "valid": [
        ("(define (TargetFunc x y)", "TargetFunc"),
        ("(define (TargetFunc)", "TargetFunc"),
        ("(define (string->number str)", "string->number"),
        ("(define (foo* x)", "foo*"),
        ("(define (1+ x)", "1+"),
    ],
    "invalid": [
        "(define-record-type TargetFunc",
        "(if TargetFunc",
        "(let ((TargetFunc 1))",
        "(define TargetFunc 42)",
        '"(define (TargetFunc x y)"',
        '; (define (TargetFunc x y)',
    ],
    "pathological": [
        ("( \n define \n ( \n TargetFunc \n x \n )", "TargetFunc"),
        ("(define \t (TargetFunc\n  x\n  y)", "TargetFunc"),
    ],
}

ARGS_CASES = {
    "valid": [
        ("(define (TargetFunc a b)", "TargetFunc"),
        ("(define (TargetFunc)", "TargetFunc"),
        ("(define (TargetFunc a b . rest)", "TargetFunc"),
        ("(define (TargetFunc a [b 1])", "TargetFunc"),
    ],
    "invalid": [
        "(TargetFunc a b)",
        "(if (> a b)",
        "(define TargetFunc 42)",
        '"(define (TargetFunc a b)"',
        '; (define (TargetFunc a b)',
    ],
    "pathological": [
        ("( \n define \n ( \n TargetFunc \n a \n b \n )", "TargetFunc"),
        ("(define\n\t(TargetFunc\n\ta\n\tb)", "TargetFunc"),
    ],
}

CLASS_CASES = {
    "valid": [
        ("(define-record-type TargetFunc (make-Target) Target?)", "TargetFunc"),
        ("(define-record-type <TargetFunc> (make-target))", "<TargetFunc>"),
        ("(define-record-type (TargetFunc x y)", "TargetFunc"),
    ],
    "invalid": [
        "(define (TargetFunc x y)",
        "(let ((TargetFunc 1))",
        '"(define-record-type TargetFunc"',
        '; (define-record-type TargetFunc',
    ],
    "pathological": [
        ("( \n define-record-type \n TargetFunc \n (", "TargetFunc"),
        ("(define-record-type \n <TargetFunc> \n (", "<TargetFunc>"),
    ],
}

class TestSchemeExtraction:
    @pytest.mark.parametrize("payload, expected_name", FUNCTION_CASES.get("valid", []))
    def test_positive_function_extraction(self, payload, expected_name):
        if not FUNC_START: pytest.skip("No pattern")
        assert_valid_match(FUNC_START, payload, expected_name, "scheme")

    @pytest.mark.parametrize("payload", FUNCTION_CASES.get("invalid", []))
    def test_negative_function_extraction(self, payload):
        if not FUNC_START: pytest.skip("No pattern")
        assert_invalid_no_match(FUNC_START, payload, "scheme")

    @pytest.mark.parametrize("payload, expected_name", FUNCTION_CASES.get("pathological", []))
    def test_pathological_function_extraction(self, payload, expected_name):
        if not FUNC_START: pytest.skip("No pattern")
        assert_pathological_match(FUNC_START, payload, expected_name, "scheme")

    @pytest.mark.parametrize("payload, expected_name", ARGS_CASES.get("valid", []))
    def test_positive_args_extraction(self, payload, expected_name):
        if not ARGS: pytest.skip("No pattern")
        assert_valid_match(ARGS, payload, expected_name, "scheme")

    @pytest.mark.parametrize("payload", ARGS_CASES.get("invalid", []))
    def test_negative_args_extraction(self, payload):
        if not ARGS: pytest.skip("No pattern")
        assert_invalid_no_match(ARGS, payload, "scheme")

    @pytest.mark.parametrize("payload, expected_name", ARGS_CASES.get("pathological", []))
    def test_pathological_args_extraction(self, payload, expected_name):
        if not ARGS: pytest.skip("No pattern")
        assert_pathological_match(ARGS, payload, expected_name, "scheme")

    @pytest.mark.parametrize("payload, expected_name", CLASS_CASES.get("valid", []))
    def test_positive_class_extraction(self, payload, expected_name):
        if not CLASS_START: pytest.skip("No pattern")
        assert_valid_match(CLASS_START, payload, expected_name, "scheme")

    @pytest.mark.parametrize("payload", CLASS_CASES.get("invalid", []))
    def test_negative_class_extraction(self, payload):
        if not CLASS_START: pytest.skip("No pattern")
        assert_invalid_no_match(CLASS_START, payload, "scheme")

    @pytest.mark.parametrize("payload, expected_name", CLASS_CASES.get("pathological", []))
    def test_pathological_class_extraction(self, payload, expected_name):
        if not CLASS_START: pytest.skip("No pattern")
        assert_pathological_match(CLASS_START, payload, expected_name, "scheme")

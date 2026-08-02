"""
m4 extraction hardening. See tests/extraction/how_to_harden_extraction.md.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from typing import Any

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_pathological_match,
    assert_valid_match,
)

M4_RULES = LANGUAGE_DEFINITIONS["m4"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        ("m4_define(`TargetFunc',", "m4_define"),
        ("AC_DEFUN([TargetFunc],", "AC_DEFUN"),
        ("define(`TargetFunc',", "define"),
        ("AC_DEFUN_ONCE([TargetFunc],", "AC_DEFUN_ONCE"),
        ("AU_DEFUN([TargetFunc],", "AU_DEFUN"),
        ("m4_defun([TargetFunc],", "m4_defun"),
    ],
    "invalid": [
        "TargetFunc()",
        "define TargetFunc",
        "dnl m4_define(`TargetFunc',", # commented out
        "# m4_define(`TargetFunc',", # commented out
    ],
    "pathological": [
        ("m4_define \n (`TargetFunc',", "m4_define"),
        ("  \t  AC_DEFUN \n ( \n [TargetFunc]", "AC_DEFUN"),
    ],
}

@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_m4_func_start_valid(payload, expected_name):
    assert_valid_match(M4_RULES["func_start"], payload, expected_name, "m4.func_start")

@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_m4_func_start_invalid(payload):
    assert_invalid_no_match(M4_RULES["func_start"], payload, "m4.func_start")

@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_m4_func_start_pathological(payload, expected_name):
    assert_pathological_match(M4_RULES["func_start"], payload, expected_name, "m4.func_start")

# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("$1", "$1"),
        ("$9", "$9"),
        ("$@", "$@"),
        ("$*", "$*"),
        ("$#", "$#"),
    ],
    "invalid": [
        "$",
        "$a",
        "$ 1",
    ],
    "pathological": [
        ("$10", "$10"), # wait, does $10 match as $1? yes, $10 matches \$[0-9]+ -> $10
    ],
}

@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_m4_args_valid(payload, expected_name):
    assert_valid_match(M4_RULES["args"], payload, expected_name, "m4.args")

@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_m4_args_invalid(payload):
    assert_invalid_no_match(M4_RULES["args"], payload, "m4.args")

@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_m4_args_pathological(payload, expected_name):
    assert_pathological_match(M4_RULES["args"], payload, expected_name, "m4.args")

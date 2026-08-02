import sys
from pathlib import Path

# Add tests/ to sys.path to allow importing _extraction_harness
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from extraction._extraction_harness import (
    assert_invalid_no_match,
    assert_pathological_match,
    assert_valid_match,
)

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

FUNCTION_CASES = {
    "valid": [
        ("TargetFunc:", "TargetFunc"),
        ("TargetFunc :", "TargetFunc"),
        ("TargetFunc\n:", "TargetFunc"),
        ("TargetFunc /* comment */ :", "TargetFunc"),
        ("TargetFunc_1:", "TargetFunc_1"),
    ],
    "invalid": [
        "%token TargetFunc",
        "case TargetFunc:",
        "default:",
        "public:",
        "private:",
        "protected:",
        "// TargetFunc:",
        '"TargetFunc:"',
    ],
    "pathological": [
        ("TargetFunc \t :", "TargetFunc"),
    ],
}

ARGS_CASES = {
    "valid": [
        ("$1", "$1"),
        ("$$", "$$"),
        ("$23", "$23"),
    ],
    "invalid": [
        "var",
        "$$$",
        "$_1",
    ],
    "pathological": [],
}

CLASS_CASES = {"valid": [], "invalid": [], "pathological": []}

DEPENDENCY_CASES = {"valid": [], "invalid": [], "pathological": []}


@pytest.mark.parametrize("case", FUNCTION_CASES["valid"])
def test_valid_function_extraction(case):
    pattern = LANGUAGE_DEFINITIONS["yacc"]["rules"]["func_start"]
    assert_valid_match(pattern, case[0], case[1], "yacc.func_start")


@pytest.mark.parametrize("case", FUNCTION_CASES["invalid"])
def test_invalid_function_extraction(case):
    pattern = LANGUAGE_DEFINITIONS["yacc"]["rules"]["func_start"]
    assert_invalid_no_match(pattern, case, "yacc.func_start")


@pytest.mark.parametrize("case", FUNCTION_CASES["pathological"])
def test_pathological_function_extraction(case):
    pattern = LANGUAGE_DEFINITIONS["yacc"]["rules"]["func_start"]
    assert_pathological_match(pattern, case[0], case[1], "yacc.func_start")


@pytest.mark.parametrize("case", ARGS_CASES["valid"])
def test_valid_args_extraction(case):
    pattern = LANGUAGE_DEFINITIONS["yacc"]["rules"]["args"]
    assert_valid_match(pattern, case[0], case[1], "yacc.args")


@pytest.mark.parametrize("case", ARGS_CASES["invalid"])
def test_invalid_args_extraction(case):
    pattern = LANGUAGE_DEFINITIONS["yacc"]["rules"]["args"]
    assert_invalid_no_match(pattern, case, "yacc.args")


@pytest.mark.parametrize("case", ARGS_CASES["pathological"])
def test_pathological_args_extraction(case):
    pattern = LANGUAGE_DEFINITIONS["yacc"]["rules"]["args"]
    assert_pathological_match(pattern, case[0], case[1], "yacc.args")

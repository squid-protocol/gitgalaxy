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

# #2644: `%union` is a grammar's one real compound-type declaration -- the C
# union spanning every rule's semantic value. The common anonymous form
# captures no name (expected_name None: the payload must match, and
# _resolve_class_start_match resolves it to "Anonymous_Class", the same path
# assembly's no-name class_start takes); bison's rarer named-tag form
# `%union name {` captures the tag in group 1.
CLASS_CASES = {
    "valid": [
        ("%union {", None),
        ("%union\t{", None),
        ("  %union {", None),
        ("%union TargetUnion {", "TargetUnion"),
        ("%union _target_union", "_target_union"),
    ],
    "invalid": [
        # Other `%` directives, including the ones `structural_boundaries` owns.
        "%token TargetUnion",
        "%type <val> expr",
        # \b guards the directive name: `%unionize` is not `%union`.
        "%unionize {",
        # A bare C `union` in embedded action code is not the directive -- this
        # is the whole reason yacc needs its own rule instead of the generic
        # `class|struct|interface|trait|enum` fallback.
        "union TargetUnion {",
        "\tstruct file_list *file;",
        # Only whitespace may precede the directive: mid-line and commented-out
        # occurrences are not declarations.
        "yyval = 0; %union {",
        "/* %union { */",
    ],
    "pathological": [
        ("\t \t%union \t TargetUnion {", "TargetUnion"),
    ],
}

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


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_valid_class_extraction(payload, expected_name):
    pattern = LANGUAGE_DEFINITIONS["yacc"]["rules"]["class_start"]
    assert_valid_match(pattern, payload, expected_name, "yacc.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_invalid_class_extraction(payload):
    pattern = LANGUAGE_DEFINITIONS["yacc"]["rules"]["class_start"]
    assert_invalid_no_match(pattern, payload, "yacc.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_pathological_class_extraction(payload, expected_name):
    pattern = LANGUAGE_DEFINITIONS["yacc"]["rules"]["class_start"]
    assert_pathological_match(pattern, payload, expected_name, "yacc.class_start")

"""
MATLAB extraction hardening (epic #852). See
tests/extraction/how_to_harden_extraction.md for the methodology.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from typing import Any  # noqa: E402

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_pathological_dependency_match,
    assert_pathological_match,
    assert_valid_dependency_match,
    assert_valid_match,
)

MATLAB_RULES = LANGUAGE_DEFINITIONS["matlab"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        # Modern idiom (carried forward)
        ("function [out] = TargetFunc(in)", "TargetFunc"),
        ("function TargetFunc()", "TargetFunc"),
        # Other idioms
        ("function TargetFunc", "TargetFunc"),
        ("function [out1, out2] = TargetFunc(in1, in2)", "TargetFunc"),
        ("function out = TargetFunc(in)", "TargetFunc"),
        ("function  [out]  =  TargetFunc ( in )", "TargetFunc"),  # Spacing
        # Line continuation
        ("function [out] = ...\n    TargetFunc(in)", "TargetFunc"),
        ("function ...\n    TargetFunc(in)", "TargetFunc"),
        # Block comments lookalike
    ],
    "invalid": [
        # Carried forward
        "if TargetFunc()",
        "classdef TargetFunc",
        "TargetFunc = 5",
        # Ghost Prevention
        "disp('function TargetFunc()')",
        "% function TargetFunc()",
        # KNOWN LIMITATION (Class 3): Block comments and string literals are unshielded in Mode D
        # "%{ \n function TargetFunc() \n %}",
        # "x = \"function TargetFunc()\"",
    ],
    "pathological": [
        # Splitting output arrays across newlines (carried forward)
        (
            "function ...\n [ \n out1 \n , \n out2 \n ] ...\n = ...\n TargetFunc ...\n (",
            "TargetFunc",
        ),
        (
            "function...\nout...\n=...\nTargetFunc...\n(",
            "TargetFunc",
        ),
        (
            "function ...\n TargetFunc ...\n (",
            "TargetFunc",
        ),
        (
            "function ...\n [ \n out1 \n , \n out2 \n ] ...\n = ...\n TargetFunc",
            "TargetFunc",
        ),
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_matlab_func_start_valid(payload, expected_name):
    assert_valid_match(MATLAB_RULES["func_start"], payload, expected_name, "matlab.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_matlab_func_start_invalid(payload):
    assert_invalid_no_match(MATLAB_RULES["func_start"], payload, "matlab.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_matlab_func_start_pathological(payload, expected_name):
    assert_pathological_match(MATLAB_RULES["func_start"], payload, expected_name, "matlab.func_start")


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("function [out] = TargetFunc(in1, in2)", None),
        ("function TargetFunc(in1)", None),
        ("function TargetFunc()", None),
        ("@(x, y)", None),  # anonymous function
        ("function [out] = ...\n    TargetFunc(in1, in2)", None),
    ],
    "invalid": [
        "if TargetFunc(in1, in2)",
        "disp(in1, in2)",
    ],
    "pathological": [
        (
            "function ...\n [ \n out1 \n , \n out2 \n ] ...\n = ...\n TargetFunc ...\n (\n in1 \n , \n in2 \n )",
            None,
        ),
        (
            "function...\nout...\n=...\nTargetFunc...\n(\n in1 \n )",
            None,
        ),
        (
            "@...\n(\nx\n,\ny\n)",
            None,
        ),
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_matlab_args_valid(payload, expected_name):
    assert_valid_match(MATLAB_RULES["args"], payload, expected_name, "matlab.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_matlab_args_invalid(payload):
    assert_invalid_no_match(MATLAB_RULES["args"], payload, "matlab.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_matlab_args_pathological(payload, expected_name):
    assert_pathological_match(MATLAB_RULES["args"], payload, expected_name, "matlab.args")


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("classdef TargetClass", "TargetClass"),
        ("classdef (ConstructOnLoad) TargetClass", "TargetClass"),
        ("classdef TargetClass < handle", "TargetClass"),
        ("classdef (Sealed = true, Hidden = false) TargetClass < handle & matlab.mixin.Copyable", "TargetClass"),
        ("classdef TargetClass<handle", "TargetClass"),
        ("classdef ...\n    TargetClass", "TargetClass"),
    ],
    "invalid": [
        "if classdef TargetClass",
        "% classdef TargetClass",
        "disp('classdef TargetClass')",
    ],
    "pathological": [
        (
            "classdef ...\n ( \n ConstructOnLoad \n ) ...\n TargetClass ...\n < ...\n handle",
            "TargetClass",
        ),
        (
            "classdef ...\n TargetClass",
            "TargetClass",
        ),
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_matlab_class_start_valid(payload, expected_name):
    assert_valid_match(MATLAB_RULES["class_start"], payload, expected_name, "matlab.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_matlab_class_start_invalid(payload):
    assert_invalid_no_match(MATLAB_RULES["class_start"], payload, "matlab.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_matlab_class_start_pathological(payload, expected_name):
    assert_pathological_match(MATLAB_RULES["class_start"], payload, expected_name, "matlab.class_start")


# ==============================================================================
# DEPENDENCY (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        # Carried forward
        ("import matlab.unittest.*", "matlab.unittest.*"),
        ("import mypack.myclass", "mypack.myclass"),
        ("import ...\n    mypack.myclass", "mypack.myclass"),
    ],
    "invalid": [
        # Carried forward
        "import_val = 1;",
        "% import matlab.unittest.*",
        "disp('import matlab.unittest.*')",
    ],
    "pathological": [
        # Carried forward
        ("import ...\n parallel.Pool", "parallel.Pool"),
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_matlab_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(
        MATLAB_RULES["_dependency_capture"], payload, expected_path, "matlab._dependency_capture"
    )


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_matlab_dependency_capture_invalid(payload):
    assert_invalid_no_match(MATLAB_RULES["_dependency_capture"], payload, "matlab._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_matlab_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        MATLAB_RULES["_dependency_capture"], payload, expected_path, "matlab._dependency_capture"
    )

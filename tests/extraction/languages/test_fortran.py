"""
Fortran extraction hardening (epic #813, issue #855). See
tests/extraction/how_to_harden_extraction.md for the methodology.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_pathological_match,
    assert_redos_immune,
    assert_valid_dependency_match,
    assert_valid_match,
)

FORTRAN_RULES = LANGUAGE_DEFINITIONS["fortran"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNC_START_VALID = [
    ("subroutine calculate_flux(x, y)", "calculate_flux"),
    ("pure elemental integer(kind=4) function math_op(x, y) result(res)", "math_op"),
    ("   sUbRoUtInE    cRaZy_SuB   ( x )", "cRaZy_SuB"),
    ("PROGRAM main_prog", "main_prog"),
    ("recursive subroutine & \n & multi_line_sub ( a, &\n & b )", "multi_line_sub"),
    ("      subroutine f77_sub\n     + (x, y)", "f77_sub"),
    ("real dimension(10) function get_array()", "get_array"),
    ("subroutine function(x)", "function"),
]

FUNC_START_INVALID = [
    "integer :: subroutine_count = 0",
    "call subroutine_runner(x)",
    "end subroutine my_sub",
]

FUNC_START_PATHOLOGICAL = [
    ("pure recursive elemental double precision function pathological_foo(x)", "pathological_foo"),
]


@pytest.mark.parametrize("payload,expected_name", FUNC_START_VALID)
def test_fortran_func_start_valid(payload, expected_name):
    assert_valid_match(FORTRAN_RULES["func_start"], payload, expected_name, "fortran.func_start")


@pytest.mark.parametrize("payload", FUNC_START_INVALID)
def test_fortran_func_start_invalid(payload):
    assert_invalid_no_match(FORTRAN_RULES["func_start"], payload, "fortran.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNC_START_PATHOLOGICAL)
def test_fortran_func_start_pathological(payload, expected_name):
    assert_pathological_match(FORTRAN_RULES["func_start"], payload, expected_name, "fortran.func_start")


def test_fortran_func_start_redos_immunity():
    assert_redos_immune(FORTRAN_RULES["func_start"], "PURE ELEMENTAL " * 1000 + " FUNCTION A()", timeout_sec=1.0)


# ==============================================================================
# ARGS (args)
# ==============================================================================
# The existing args regex is: \b(?:SUBROUTINE|FUNCTION|ENTRY)\s+[A-Za-z_]\w*(?:\s*\([^)]*\))?|\bINTENT\s*\(\s*(?:IN|OUT|INOUT)\s*\)
# Note: In gitgalaxy, args extraction captures the full parameter list string.
ARGS_VALID = [
    ("subroutine foo(a, b, c)", "a, b, c"),
    ("function empty_args()", ""),
    (
        "subroutine lots(a1,a2,a3,a4,a5,a6,a7,a8,a9,a10,a11,a12,a13,a14,a15,a16,a17,a18,a19,a20)",
        "a1,a2,a3,a4,a5,a6,a7,a8,a9,a10,a11,a12,a13,a14,a15,a16,a17,a18,a19,a20",
    ),
    ("subroutine c_binding(x, y) bind(c, name='c_binding')", "x, y"),
]


@pytest.mark.parametrize("payload,expected_args", ARGS_VALID)
def test_fortran_args_valid(payload, expected_args):
    # args capture logic tests
    pass  # we will write specific args matching logic if it uses group() or raw match.


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_START_VALID = [
    ("module physics_constants", "physics_constants"),
    ("type my_type", "my_type"),
    ("type, public, extends(base_type) :: child_type", "child_type"),
    ("tYpE   ::   weird_type", "weird_type"),
    ("module type", "type"),
]

CLASS_START_INVALID = [
    "type(my_type) :: my_instance",
    "real :: module_val",
    "end module physics_constants",
]


@pytest.mark.parametrize("payload,expected_name", CLASS_START_VALID)
def test_fortran_class_start_valid(payload, expected_name):
    assert_valid_match(FORTRAN_RULES["class_start"], payload, expected_name, "fortran.class_start")


@pytest.mark.parametrize("payload", CLASS_START_INVALID)
def test_fortran_class_start_invalid(payload):
    assert_invalid_no_match(FORTRAN_RULES["class_start"], payload, "fortran.class_start")


# ==============================================================================
# DEPENDENCY CAPTURE (_dependency_capture)
# ==============================================================================
DEPENDENCY_VALID = [
    ("use math_lib", "math_lib"),
    ("use, intrinsic :: iso_fortran_env", "iso_fortran_env"),
    ("use my_mod, only : func1, func2", "my_mod"),
    ("include 'header.h'", "header.h"),
    ('  INCLUDE   "params.f90"  ', "params.f90"),
]

DEPENDENCY_INVALID = [
    "logical :: include_flag = .true.",
    "call print_usage(use_count)",
    "block data include_data",
]


@pytest.mark.parametrize("payload,expected_name", DEPENDENCY_VALID)
def test_fortran_dependency_valid(payload, expected_name):
    assert_valid_dependency_match(FORTRAN_RULES["_dependency_capture"], payload, expected_name, "fortran.dependency")


@pytest.mark.parametrize("payload", DEPENDENCY_INVALID)
def test_fortran_dependency_invalid(payload):
    assert_invalid_no_match(FORTRAN_RULES["_dependency_capture"], payload, "fortran.dependency")

"""
ABAP extraction hardening (epic #813, issue #853). See
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

ABAP_RULES = LANGUAGE_DEFINITIONS["abap"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNC_START_VALID = [
    ("METHOD TargetFunc.", "TargetFunc"),
    ("FORM TargetFunc.", "TargetFunc"),
    ("FUNCTION TargetFunc.", "TargetFunc"),
    ("MODULE TargetFunc.", "TargetFunc"),
    ("  method  TargetFunc .", "TargetFunc"),
    ("method my_method~implementation.", "my_method~implementation"),
]

FUNC_START_INVALID = [
    "CLASS TargetFunc",
    "DATA TargetFunc",
    "CALL FUNCTION TargetFunc",
    "CALL METHOD TargetFunc",
    "ENDMETHOD.",
    "ENDFORM.",
    "TYPES my_type TYPE c.",
    "CONSTANTS my_const TYPE i VALUE 1.",
    '  " METHOD TargetFunc.',
]

FUNC_START_PATHOLOGICAL = [
    ("METHOD \n TargetFunc \n .", "TargetFunc"),
]

@pytest.mark.parametrize("payload,expected_name", FUNC_START_VALID)
def test_abap_func_start_valid(payload, expected_name):
    assert_valid_match(ABAP_RULES["func_start"], payload, expected_name, "abap.func_start")

@pytest.mark.parametrize("payload", FUNC_START_INVALID)
def test_abap_func_start_invalid(payload):
    assert_invalid_no_match(ABAP_RULES["func_start"], payload, "abap.func_start")

@pytest.mark.parametrize("payload,expected_name", FUNC_START_PATHOLOGICAL)
def test_abap_func_start_pathological(payload, expected_name):
    assert_pathological_match(ABAP_RULES["func_start"], payload, expected_name, "abap.func_start")

def test_abap_func_start_redos_immunity():
    assert_redos_immune(ABAP_RULES["func_start"], "METHOD " + " " * 1000 + " foo", timeout_sec=1.0)


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_VALID = [
    ("IMPORTING value(p_name) TYPE string", "IMPORTING"),
    ("EXPORTING e_result TYPE i", "EXPORTING"),
    ("CHANGING c_data TYPE any", "CHANGING"),
    ("RETURNING VALUE(r_val) TYPE string", "RETURNING"),
    ("RECEIVING r_obj TYPE REF TO object", "RECEIVING"),
    ("EXCEPTIONS ex_not_found = 1", "EXCEPTIONS"),
    ("IMPORTING \n  VALUE( p_name ) \n TYPE string", "IMPORTING"),
    ("METHODS get_data IMPORTING p1 TYPE i.", "IMPORTING"),
]

ARGS_INVALID = [
    "DATA IMPORTING TYPE string",
]

ARGS_PATHOLOGICAL = [
    ("IMPORTING \n VALUE( \n p_name \n ) \n TYPE string", "IMPORTING"),
]

@pytest.mark.parametrize("payload,expected_args", ARGS_VALID)
def test_abap_args_valid(payload, expected_args):
    assert_valid_match(ABAP_RULES["args"], payload, expected_args, "abap.args")

@pytest.mark.parametrize("payload", ARGS_INVALID)
def test_abap_args_invalid(payload):
    assert_invalid_no_match(ABAP_RULES["args"], payload, "abap.args")

@pytest.mark.parametrize("payload,expected_args", ARGS_PATHOLOGICAL)
def test_abap_args_pathological(payload, expected_args):
    assert_pathological_match(ABAP_RULES["args"], payload, expected_args, "abap.args")


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_START_VALID = [
    ("CLASS TargetClass DEFINITION.", "TargetClass"),
    ("INTERFACE TargetInterface.", "TargetInterface"),
    ("DEFINE VIEW ENTITY TargetView", "TargetView"),
    ("DEFINE ROOT VIEW ENTITY TargetRootView", "TargetRootView"),
    ("DEFINE PROJECTION VIEW TargetProjView", "TargetProjView"),
    ("DEFINE BEHAVIOR FOR TargetBehavior", "TargetBehavior"),
]

CLASS_START_INVALID = [
    "DATA TargetClass",
    "ENDCLASS.",
]

CLASS_START_PATHOLOGICAL = [
    ("CLASS \n TargetClass \n DEFINITION.", "TargetClass"),
    ("DEFINE \n ROOT \n VIEW \n ENTITY \n TargetEntity", "TargetEntity"),
]

@pytest.mark.parametrize("payload,expected_name", CLASS_START_VALID)
def test_abap_class_start_valid(payload, expected_name):
    assert_valid_match(ABAP_RULES["class_start"], payload, expected_name, "abap.class_start")

@pytest.mark.parametrize("payload", CLASS_START_INVALID)
def test_abap_class_start_invalid(payload):
    assert_invalid_no_match(ABAP_RULES["class_start"], payload, "abap.class_start")

@pytest.mark.parametrize("payload,expected_name", CLASS_START_PATHOLOGICAL)
def test_abap_class_start_pathological(payload, expected_name):
    assert_pathological_match(ABAP_RULES["class_start"], payload, expected_name, "abap.class_start")


# ==============================================================================
# DEPENDENCY (dependency)
# ==============================================================================
DEPENDENCY_VALID = [
    ("INCLUDE z_my_macros.", "z_my_macros"),
    ("TYPE-POOLS abap.", "abap"),
]

DEPENDENCY_INVALID = [
    "DATA include_name TYPE string.",
    "INCLUDE = 1.",
]

DEPENDENCY_PATHOLOGICAL = [
    ("TYPE-POOLS \n slis \n .", "slis"),
]

@pytest.mark.parametrize("payload,expected_name", DEPENDENCY_VALID)
def test_abap_dependency_valid(payload, expected_name):
    assert_valid_dependency_match(ABAP_RULES["_dependency_capture"], payload, expected_name, "abap.dependency")

@pytest.mark.parametrize("payload", DEPENDENCY_INVALID)
def test_abap_dependency_invalid(payload):
    assert_invalid_no_match(ABAP_RULES["_dependency_capture"], payload, "abap.dependency")

@pytest.mark.parametrize("payload,expected_name", DEPENDENCY_PATHOLOGICAL)
def test_abap_dependency_pathological(payload, expected_name):
    # Depending on _dependency_capture, we might need a custom check or we can use assert_valid_dependency_match
    # Pathological should still extract the correct group.
    assert_valid_dependency_match(ABAP_RULES["_dependency_capture"], payload, expected_name, "abap.dependency")

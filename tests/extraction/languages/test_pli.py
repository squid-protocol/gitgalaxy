"""
PL/I extraction gauntlet (#2502, consolidating #1142). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for pli in one file: func_start, args,
class_start, _dependency_capture. Every payload is a real shape from the corpora the
rules were measured on (navikt/DSF, the Zowe PL/I language-support samples, IBM
zopeneditor-sample, IBM Bank-of-Z, Rocket BankDemo); file names are cited where the
shape is unusual.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# tests/ has no __init__.py anywhere in this repo -- see test_ada.py for why the
# harness is imported as a plain top-level module off an inserted sys.path entry.
_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from typing import Any

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_pathological_dependency_match,
    assert_pathological_match,
    assert_redos_immune,
    assert_valid_dependency_match,
    assert_valid_match,
)

PLI_RULES = LANGUAGE_DEFINITIONS["pli"]["rules"]

# ==============================================================================
# FUNC_START -- `label: PROC` / `label: PROCEDURE`; the label adjacent to the keyword.
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        ("MAIN: PROC OPTIONS(MAIN);", "MAIN"),
        ("PSAM1: PROC OPTIONS(MAIN) RETURNS(DEC(12,2));", "PSAM1"),  # zopeneditor PSAM1.pli
        ("PSAM2: PROCEDURE(CUSTFILE_RECORD, CUSTOMER_BALANCE_STATS);", "PSAM2"),
        ("   TRANTOT: PROCEDURE;", "TRANTOT"),  # internal procedure, indented
        ("reform: proc(parm) options(main);", "reform"),  # lowercase (Zowe FORM01.pli)
        ("A: B: PROC;", "B"),  # multiple labels: the adjacent one names the unit
        ("SCAN@#$: PROC;", "SCAN@#$"),  # @ # $ are identifier characters
        ("KONTROLLER_AU_SØKER:\n   PROC(FEIL_FUNNET);", "KONTROLLER_AU_SØKER"),  # national letter
    ],
    "invalid": [
        "%SCOREGET: PROCEDURE(IDX) RETURNS(FIXED);",  # preprocessor procedure (macros')
        "DCL PROC_COUNT FIXED BIN(31);",  # identifier containing the keyword
        "CALL PROCESS_ALL_ACCOUNTS;",  # a call, and PROCESS is not PROC
        "*PROCESS SOURCE RULES(LAXIF);",  # compiler-option directive
        "END PSAM1;",
        "B: ENTRY(X);",  # secondary entry point into an existing procedure (api's)
        "LOOP: DO WHILE (MORE_DATA);",  # labelled group, not a procedure
    ],
    "pathological": [
        # navikt/DSF R0011803.pli: label, 8-digit sequence field in columns 73-80, CRLF,
        # PROC on the next line.
        (
            "KONTROLLER_AU_SØKER:                                               00000480\r\n   PROC(FEIL_FUNNET);",
            "KONTROLLER_AU_SØKER",
        ),
        ("(SUBRG, STRG, SIZE):\n reform: proc(parm) options(main);", "reform"),  # condition prefix
        ("P20_FJERN_DUMMY_ROT:\n\n      PROC;", "P20_FJERN_DUMMY_ROT"),  # blank line between
        ("X" * 64 + ": PROC;", "X" * 64),
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_pli_func_start_valid(payload, expected_name):
    assert_valid_match(PLI_RULES["func_start"], payload, expected_name, "pli.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_pli_func_start_invalid(payload):
    assert_invalid_no_match(PLI_RULES["func_start"], payload, "pli.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_pli_func_start_pathological(payload, expected_name):
    assert_pathological_match(PLI_RULES["func_start"], payload, expected_name, "pli.func_start")


def test_pli_func_start_redos_immunity():
    func_start = PLI_RULES["func_start"]
    assert_redos_immune(func_start, "A:" + " " * 200000, timeout_sec=3.0)
    assert_redos_immune(func_start, ("A:" + " " * 70 + "00000100\n") * 20000, timeout_sec=3.0)
    assert_redos_immune(func_start, "A" * 200000 + ":", timeout_sec=3.0)
    assert func_start.search("MAIN: PROC OPTIONS(MAIN);")


# ==============================================================================
# ARGS -- a PROCEDURE's or ENTRY's own parameter list.
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("PSAM2: PROCEDURE(CUSTFILE_RECORD, CUSTOMER_BALANCE_STATS);", "CUSTFILE_RECORD"),
        ("KONTROLLER: PROC(FEIL_FUNNET);", "FEIL_FUNNET"),
        ("R001D81: PROC(COMMAREA_PEKER) OPTIONS (MAIN);", "COMMAREA_PEKER"),
        ("DDINFO: PROCEDURE (DD);", "DD"),  # Zowe DDINFO.pli: space before the list
        ("B: ENTRY(X, Y);", "X"),  # secondary entry point declares its own parameters
    ],
    "invalid": [
        "CALL PSAM2(CUSTFILE_RECORD, STATS);",  # actuals at a call site
        "DCL BASE64E ENTRY(CHAR(8), FIXED BIN(31)) EXTERNAL;",  # external entry descriptor
        "%DOUBLE: PROCEDURE(N) RETURNS(FIXED);",  # preprocessor procedure
        "MAIN: PROC OPTIONS(MAIN);",  # no parameter list at all
    ],
    "pathological": [
        ("PSAM2: PROCEDURE(CUSTFILE_RECORD,\n                  CUSTOMER_BALANCE_STATS);", "CUSTOMER_BALANCE_STATS"),
        ("X:                                                     00000680\n PROC (IND);", "IND"),
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_pli_args_valid(payload, expected_name):
    assert_valid_match(PLI_RULES["args"], payload, expected_name, "pli.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_pli_args_invalid(payload):
    assert_invalid_no_match(PLI_RULES["args"], payload, "pli.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_pli_args_pathological(payload, expected_name):
    assert_pathological_match(PLI_RULES["args"], payload, expected_name, "pli.args")


def test_pli_args_redos_immunity():
    args = PLI_RULES["args"]
    assert_redos_immune(args, "X: PROC(" + "A," * 100000, timeout_sec=3.0)
    assert_redos_immune(args, "X:" + " " * 200000, timeout_sec=3.0)
    assert args.search("X: PROC(A);")


# ==============================================================================
# CLASS_START -- Enterprise PL/I's named types: DEFINE STRUCTURE and DEFINE ORDINAL.
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("DEFINE ORDINAL COLOR (RED, GREEN, BLUE);", "COLOR"),  # Zowe ORDINALS.pli
        ("define ordinal Color ( Red, Green, Blue );", "Color"),  # Zowe builtins.pli
        ("DEFINE STRUCTURE 1 POINT, 2 X FIXED BIN(31), 2 Y FIXED BIN(31);", "POINT"),
    ],
    "invalid": [
        "DEFINE ALIAS INT FIXED BIN(31);",  # a type alias declares no new type
        "DCL 1 POINT, 2 X FIXED BIN(31);",  # an ordinary structure variable
        "CALL DEFINE_ORDINAL_TABLE;",
    ],
    "pathological": [
        ("DEFINE\n  STRUCTURE\n    1 ACCOUNT_RECORD,", "ACCOUNT_RECORD"),
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_pli_class_start_valid(payload, expected_name):
    assert_valid_match(PLI_RULES["class_start"], payload, expected_name, "pli.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_pli_class_start_invalid(payload):
    assert_invalid_no_match(PLI_RULES["class_start"], payload, "pli.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_pli_class_start_pathological(payload, expected_name):
    assert_pathological_match(PLI_RULES["class_start"], payload, expected_name, "pli.class_start")


def test_pli_class_start_redos_immunity():
    class_start = PLI_RULES["class_start"]
    assert_redos_immune(class_start, "DEFINE STRUCTURE " + " " * 200000, timeout_sec=3.0)
    assert class_start.search("DEFINE ORDINAL COLOR (RED);")


# ==============================================================================
# DEPENDENCY -- the %INCLUDE member (and EXEC SQL INCLUDE's structure).
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("%INCLUDE P0019908;", "P0019908"),  # navikt/DSF: 369 of these
        ("%INCLUDE SYSLIB(CUSTPLI);", "CUSTPLI"),  # ddname(member) binds the member
        ("%INCLUDE MYLIB (REPTTOTL);", "REPTTOTL"),  # zopeneditor MACSAMP.pli
        ("%INCLUDE (SETUPL);", "SETUPL"),  # Zowe
        ('%INCLUDE "INCLUDED.PLI";', "INCLUDED.PLI"),  # Zowe, a quoted file
        ("%INCLUDE 'MYFILE';", "MYFILE"),
        ("EXEC SQL INCLUDE SQLCA;", "SQLCA"),
        ("% INCLUDE DFHBMSCA;", "DFHBMSCA"),
        ("%XINCLUDE CUSTPLI;", "CUSTPLI"),
    ],
    "invalid": [
        "DCL INCLUDE_FLAG BIT(1);",
        "CALL INCLUDE_RECORD(X);",
    ],
    "pathological": [
        ("EXEC SQL\n   INCLUDE SQLCA;", "SQLCA"),
        ("%INCLUDE   SYSLIB  (  CUSTPLI  );", "CUSTPLI"),
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_pli_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(PLI_RULES["_dependency_capture"], payload, expected_path, "pli._dependency_capture")


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_pli_dependency_capture_invalid(payload):
    assert_invalid_no_match(PLI_RULES["_dependency_capture"], payload, "pli._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_pli_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        PLI_RULES["_dependency_capture"], payload, expected_path, "pli._dependency_capture"
    )


def test_pli_dependency_capture_redos_immunity():
    dep = PLI_RULES["_dependency_capture"]
    assert_redos_immune(dep, "%INCLUDE " + "A" * 200000, timeout_sec=3.0)
    assert_redos_immune(dep, "%INCLUDE '" + "A" * 200000, timeout_sec=3.0)
    assert_redos_immune(dep, "%INCLUDE SYSLIB(" + " " * 200000, timeout_sec=3.0)
    assert dep.search("%INCLUDE P0019908;")

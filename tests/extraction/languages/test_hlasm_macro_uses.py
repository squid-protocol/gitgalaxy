# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

"""
HLASM installation / in-file macro uses become call edges to the macro member (#7063, slice 3).

A macro prototype (the line after `MACRO`) opens a unit named for the macro; every operation-field name that is not a
machine instruction, assembler directive or IBM system macro is named as a callee of its unit; the call resolver keeps
the names some unit defines. Driven through `StructuralExtractor.splice()` (the path a scan takes) and `resolve_calls`.
"""

import time

import pytest

from gitgalaxy.core.call_resolver import confident_file_pairs, resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

PAYCALC_MAC = (
    "         MACRO\n"
    "&LAB     PAYCALC &AMT,&RATE=5\n"
    "&LAB     LA    1,&AMT\n"
    "         AIF   ('&RATE' EQ '').DONE\n"
    "         AUDITLOG &AMT\n"
    ".DONE    ANOP\n"
    "         MEND\n"
)
AUDIT_MAC = "         MACRO\n         AUDITLOG &X\n         WTO   'X'\n         MEND\n"


def _units(code: str) -> dict[str, dict]:
    functions = StructuralExtractor("hlasm", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}


def _calls(code: str, unit: str = "MAIN") -> list[str]:
    return _units(code)[unit]["calls_out_to"]


def _program(*lines: str) -> str:
    return "\n".join(["MAIN     CSECT", *lines, "         BR    14", "         END"]) + "\n"


# --- the macro definition is a unit ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source, name",
    [
        (PAYCALC_MAC, "PAYCALC"),
        (AUDIT_MAC, "AUDITLOG"),
        ("         MACRO\n         NOLABEL\n         MEND\n", "NOLABEL"),
        ("    MACRO\r\n    CRLFMAC &VAR\r\n    MEND\r\n", "CRLFMAC"),
        ("         macro\n&lab     lowmac &a\n         mend\n", "lowmac"),
        ("         MACRO\n* banner\n.* more\n&LAB     AFTERCMT &A\n         MEND\n", "AFTERCMT"),
    ],
)
def test_a_macro_prototype_opens_a_unit_named_for_the_macro(source, name):
    assert name in _units(source)


def test_a_macro_unit_ends_at_the_next_section_and_a_section_follows():
    units = _units(PAYCALC_MAC + "MAIN     CSECT\n         PAYCALC 5\n         BR    14\n")
    assert set(units) == {"PAYCALC", "MAIN"}
    assert units["PAYCALC"]["end_line"] < units["MAIN"]["start_line"]


def test_a_macro_keyword_without_a_prototype_opens_no_unit():
    assert _units("         MACRO\n         MEND\nMAIN     CSECT\n         BR    14\n").keys() == {"MAIN"}


# --- a use is a callee --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "         PAYCALC 100",
        "         paycalc 100,RATE=3",
        "LBL      PAYCALC 100",
        "&SYM     PAYCALC 100",
        "         PAYCALC",
    ],
)
def test_an_operation_field_name_is_a_callee(line):
    assert [c.upper() for c in _calls(_program(line))] == ["PAYCALC"]


def test_a_name_is_listed_once_per_unit_and_never_for_the_unit_itself():
    code = _program("         PAYCALC 1", "         PAYCALC 2", "         MAIN")
    assert _calls(code) == ["PAYCALC"]


def test_the_use_belongs_to_the_unit_that_writes_it():
    code = "ONE      CSECT\n         PAYCALC 1\nTWO      CSECT\n         BR 14\n"
    units = _units(code)
    assert units["ONE"]["calls_out_to"] == ["PAYCALC"] and units["TWO"]["calls_out_to"] == []


def test_a_macro_that_invokes_another_macro_calls_it():
    assert _calls(PAYCALC_MAC, "PAYCALC") == ["AUDITLOG"]


def test_the_other_call_forms_are_kept_in_order():
    code = _program("         L     15,=V(SUBA)", "         CALL  SUBB", "         PAYCALC 1")
    assert _calls(code) == ["SUBA", "SUBB", "PAYCALC"]


# --- near misses: no macro name, no edge --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "         LA    1,PAYCALC",  # an operand, not the operation field
        "         MVC   A(8),=C'PAYCALC'",
        "* PAYCALC IN A COMMENT",
        ".* PAYCALC IN A MACRO COMMENT",
        "PAYCALC  DS    0H",  # a label
        "         L     R1,X    PAYCALC REMARK",  # a remark
        "               WAIT=YES",  # a keyword operand on a continuation line
        "               PAYCALC=1",
        "         STM   14,12,12(13)",
        "         DFHEIENT CODEREG=12",
        "         GETMAIN RU,LV=100",
        "         WTO   'HELLO'",
        "         BE    DONE",
        "         AIF   ('&A' EQ '').SKIP",
        "         LHI   1,5",
        "         SLL   1,2",
    ],
)
def test_near_misses_name_no_macro(line):
    assert [c for c in _calls(_program(line)) if c.upper() in {"PAYCALC", "WAIT", "LA", "MVC", "L", "STM"}] == []


@pytest.mark.parametrize(
    "line",
    [
        "         LA    1,0",
        "         ST    1,SAVE",
        "         MVC   A(1),B",
        "         CLC   A,B",
        "         DS    CL8",
    ],
)
def test_machine_instructions_and_directives_are_not_callees(line):
    assert _calls(_program(line)) == []


# --- resolution through the call resolver (the edge) ---------------------------------------------------------------


def _parsed(path: str, source: str) -> dict:
    functions = StructuralExtractor("hlasm", LANGUAGE_DEFINITIONS).splice(source, "")["functions"]
    return {"path": path, "lang_id": "hlasm", "functions": functions, "classes": []}


def _edges(files: list[dict]) -> dict:
    sites, _ = resolve_calls(files)
    return confident_file_pairs(sites)


def test_a_use_in_one_member_is_an_edge_to_the_mac_member_that_defines_it():
    files = [_parsed("maclib/PAYCALC.mac", PAYCALC_MAC), _parsed("src/MAIN.asm", _program("         PAYCALC 100"))]
    assert _edges(files)[("src/MAIN.asm", "maclib/PAYCALC.mac")] == 1


def test_a_macro_calling_a_macro_links_the_two_members():
    files = [_parsed("maclib/PAYCALC.mac", PAYCALC_MAC), _parsed("maclib/AUDITLOG.mac", AUDIT_MAC)]
    assert ("maclib/PAYCALC.mac", "maclib/AUDITLOG.mac") in _edges(files)


def test_an_undefined_name_draws_no_edge():
    files = [_parsed("maclib/AUDITLOG.mac", AUDIT_MAC), _parsed("src/MAIN.asm", _program("         PAYCALC 100"))]
    assert _edges(files) == {}


def test_an_in_file_macro_use_is_not_a_file_edge():
    assert _edges([_parsed("src/MAIN.asm", PAYCALC_MAC + _program("         PAYCALC 1"))]) == {}


def test_the_mac_member_is_the_target_not_the_copy_of_a_name_in_another_language():
    other = {"path": "docs/PAYCALC.py", "lang_id": "python", "functions": [{"name": "PAYCALC", "start_line": 1}]}
    files = [other, _parsed("maclib/PAYCALC.mac", PAYCALC_MAC), _parsed("src/MAIN.asm", _program("         PAYCALC 1"))]
    assert ("src/MAIN.asm", "maclib/PAYCALC.mac") in _edges(files)
    assert ("src/MAIN.asm", "docs/PAYCALC.py") not in _edges(files)


def test_the_assembly_profile_is_untouched():
    assert "_calls_out_file_pass" not in LANGUAGE_DEFINITIONS["assembly"]["rules"]


# --- ReDoS --------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        "         MACRO\n" + " " * 10000 + "\n",
        "         MACRO\n" + "&" * 10000 + " X\n",
        "         MACRO\n" + "A" * 10000 + "\n",
        "         MACRO\n" + "* c\n" * 5000 + "&L " + "A" * 100 + "\n",
        "MAIN     CSECT\n" + "A" * 10000 + "  " + "B" * 10000 + "\n",
        "MAIN     CSECT\n" + ("   " + "X" * 8 + "\n") * 5000,
        "MAIN     CSECT\n" + "&" * 5000 + " " * 5000 + "NAME\n",
    ],
)
def test_macro_use_scans_are_redos_immune(payload):
    start = time.perf_counter()
    _units(payload)
    assert time.perf_counter() - start < 5


def test_a_continuation_line_word_is_an_operand_not_a_use():
    cont = "         EXEC CICS READ DATASET('X')" + " " * 35 + "X\n               NOHANDLE\n"
    assert len(cont.split("\n")[0]) == 72
    src = "MAIN     CSECT\n" + cont + "         END\n"
    assert "NOHANDLE" not in _calls(src)

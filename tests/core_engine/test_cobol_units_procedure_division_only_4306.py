# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4306: COBOL units (paragraphs / sections) come from the PROCEDURE DIVISION only.

CA IDMS programs carry `IDMS-CONTROL SECTION.` / `PROTOCOL. MODE IS ...` in the ENVIRONMENT DIVISION and
`SCHEMA SECTION.` (and `MAP SECTION.` in IDMS-DC) in the DATA DIVISION. No reserved-name list can finish
that set, so the `cobol_sentence_start` scope filter now drops every header candidate between an
IDENTIFICATION / ENVIRONMENT / DATA DIVISION header and the next PROCEDURE DIVISION.
"""

from __future__ import annotations

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _result(code: str) -> dict:
    return StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(code, "")


def _units(code: str) -> list[str]:
    return [f["name"] for f in _result(code)["functions"]]


IDMSSCH = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. IDMSSCH.
       ENVIRONMENT DIVISION.
       IDMS-CONTROL SECTION.
       PROTOCOL.    MODE IS IDMS-DC DEBUG.
       DATA DIVISION.
       SCHEMA SECTION.
       DB LOANSS01 WITHIN LOANSCHM.
       WORKING-STORAGE SECTION.
       01  WS-KEY                 PIC X(12).
       PROCEDURE DIVISION.
       MAIN-PARA.
           BIND RUN-UNIT
           FINISH
           GOBACK.
"""


def test_idms_control_protocol_and_schema_are_not_units():
    assert _units(IDMSSCH) == ["MAIN-PARA"]


def test_idms_dc_map_section_is_not_a_unit():
    code = IDMSSCH.replace("       WORKING-STORAGE SECTION.", "       MAP SECTION.\n       MAP-X.\n       WORKING-STORAGE SECTION.")
    assert _units(code) == ["MAIN-PARA"]


def test_idmssmpl_shape_from_the_lsp_fixtures():
    code = """006500 IDENTIFICATION DIVISION.
006600 PROGRAM-ID. IDMSSMPL.
006700 ENVIRONMENT DIVISION.
006800 IDMS-CONTROL SECTION.
006900 PROTOCOL.    MODE IS IDMS-DC-NONAUTO DEBUG.
007000 DATA DIVISION.
007100 PROCEDURE DIVISION.
007200 MAIN-LINE.
007300     GOBACK.
"""
    assert _units(code) == ["MAIN-LINE"]


def test_the_phantoms_also_leave_the_func_start_count():
    assert _result(IDMSSCH)["equations"].get("func_start", 0) == 1


def test_sections_and_paragraphs_in_the_procedure_division_are_still_units():
    code = IDMSSCH.replace(
        "       MAIN-PARA.\n",
        "       MAIN-PARA.\n           PERFORM SUB-SECT.\n       SUB-SECT SECTION.\n       SUB-PARA.\n",
    )
    assert sorted(_units(code)) == ["MAIN-PARA", "SUB-PARA", "SUB-SECT"]


def test_a_fragment_without_division_headers_keeps_its_units():
    """Near miss: no division header seen -> nothing to exclude (copybook / snippet streams)."""
    assert _units("       MAIN-PARA.\n           GOBACK.\n       NEXT-PARA.\n           GOBACK.\n") == [
        "MAIN-PARA",
        "NEXT-PARA",
    ]


def test_a_nested_program_resets_to_its_own_divisions():
    code = (
        IDMSSCH
        + "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. INNER.\n       ENVIRONMENT DIVISION.\n"
        + "       IDMS-CONTROL SECTION.\n       PROTOCOL.    MODE IS IDMS-DC.\n"
        + "       PROCEDURE DIVISION.\n       INNER-PARA.\n           GOBACK.\n"
    )
    assert _units(code) == ["MAIN-PARA", "INNER-PARA"]

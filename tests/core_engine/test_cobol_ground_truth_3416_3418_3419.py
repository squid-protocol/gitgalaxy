# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Three COBOL shapes the mainframe ground-truth census found the engine missing,
each reproduced from CardDemo (aws-mainframe-modernization-carddemo):

- #3418  `PROGRAM-ID.` alone on its line: the name was read from the next line's
         sequence area (`002600`) or the cols 73-80 identification area (`00220000`).
- #3416  one-line `EXEC SQL INCLUDE <member> END-EXEC` was not a copy.
- #3419  a paragraph header whose separator period is on the next line was not a unit.
"""

from __future__ import annotations

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

RULES = LANGUAGE_DEFINITIONS["cobol"]["rules"]


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("002500 PROGRAM-ID.\n002600     COTRTLIC.\n002700 DATE-WRITTEN.", "COTRTLIC"),
        (
            "002200 PROGRAM-ID." + " " * 54 + "00220000\n002300     COTRTUPC." + " " * 52 + "00230000",
            "COTRTUPC",
        ),
        ("       PROGRAM-ID. SAM1.", "SAM1"),
        ("       PROGRAM-ID.  CBSTM03A IS INITIAL PROGRAM.", "CBSTM03A"),
        ("PROGRAM-ID.\n    MyProgram.", "MyProgram"),  # the greedy-margin guard
    ],
)
def test_program_id_name_is_the_program_not_a_sequence_number(text, name):
    assert RULES["class_start"].search(text).group(1) == name


def test_factory_marker_still_captures_nothing():
    assert RULES["class_start"].search("       FACTORY.\n       IDENTIFICATION DIVISION.") is None


@pytest.mark.parametrize(
    ("text", "members"),
    [
        ("030400     EXEC SQL INCLUDE CSDB2RWY END-EXEC", ["CSDB2RWY"]),
        ("           EXEC SQL INCLUDE DCLTRTYP END-EXEC", ["DCLTRTYP"]),
        ("           EXEC SQL\n                INCLUDE AUTHFRDS\n           END-EXEC.", ["AUTHFRDS"]),
        ("       COPY CUSTCOPY.", ["CUSTCOPY"]),
        ("           MOVE X TO EXEC-SQL-INCLUDE-FLAG", []),
    ],
)
def test_one_line_exec_sql_include_is_a_dependency(text, members):
    assert [m.group(1) for m in RULES["_dependency_capture"].finditer(text)] == members


def test_header_period_on_the_next_line_is_a_unit():
    src = (
        "000100 IDENTIFICATION DIVISION.\n000200 PROGRAM-ID. DEMO.\n000300 PROCEDURE DIVISION.\n"
        "000400 MAIN-PARA.\n000500     PERFORM 2000-SEND-MAP THRU 2000-SEND-MAP-EXIT\n000600     GOBACK.\n"
        "000700 2000-SEND-MAP\n000800      .\n000900     DISPLAY 'S'.\n"
        "001000 2000-SEND-MAP-EXIT.\n001100     EXIT.\n"
    )
    names = [f["name"] for f in StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(src, "")["functions"]]
    assert names == ["MAIN-PARA", "2000-SEND-MAP", "2000-SEND-MAP-EXIT"]


def test_a_statement_line_followed_by_a_period_line_is_not_a_unit():
    """Area B statements are never headers, even with a lone period below them."""
    src = (
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. DEMO.\n       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n           DISPLAY 'A'\n           .\n           GOBACK.\n"
    )
    names = [f["name"] for f in StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(src, "")["functions"]]
    assert names == ["MAIN-PARA"]

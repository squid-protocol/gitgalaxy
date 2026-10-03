# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4203: a free-format data description entry is not a paragraph.

In free-format COBOL (GnuCOBOL `-free`, CobolCraft) `func_start`'s optional
6-char sequence-area slot swallows a 4-space indent plus the level number
(`    01` of `    01 VALUE-BYTES.`), steps past the regex's level-number shield,
and reads the data name as a paragraph header: CobolCraft @ e8c420df had 143
such phantom units (`LK-POSITION` x21, `VALUE-BYTES` x18, ...) and its
`coordinates.cob` / `decode.cob` units were all data items.

A line whose first six columns are not a fixed-format sequence area (six digits
or six blanks, `_COBOL_SEQUENCE_AREA`) is free-format; when its content opens
with a level number or FD / SD / RD / CD it is a data description entry, so the
`cobol_sentence_start` scope filter never lets it start a header.
"""

from __future__ import annotations

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _units(code: str) -> list[str]:
    return [f["name"] for f in StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]]


def _func_start_count(code: str) -> int:
    return StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(code, "")["equations"].get("func_start", 0)


# CobolCraft src/util/coordinates.cob shape: sibling programs, no paragraphs.
SIBLING_PROGRAMS = """IDENTIFICATION DIVISION.
PROGRAM-ID. Facing-GetRelative.

DATA DIVISION.
LINKAGE SECTION.
    01 LK-FACING        BINARY-LONG.
    01 LK-POSITION.
        02 LK-X         BINARY-LONG.
        02 LK-Y         BINARY-LONG.

PROCEDURE DIVISION USING LK-FACING LK-POSITION.
    EVALUATE LK-FACING
        WHEN 0
            COMPUTE LK-Y = LK-Y - 1
    END-EVALUATE
    GOBACK.

END PROGRAM Facing-GetRelative.

IDENTIFICATION DIVISION.
PROGRAM-ID. Decode-Int.

DATA DIVISION.
WORKING-STORAGE SECTION.
    01 VALUE-BYTES.
        02 VALUE-BYTE   BINARY-CHAR UNSIGNED OCCURS 4 TIMES.
    01 BYTE-ALPHA.
        02 BYTE-X       PIC X.
LINKAGE SECTION.
    01 LK-VALUE         BINARY-LONG.

PROCEDURE DIVISION USING LK-VALUE.
    MOVE 0 TO LK-VALUE
    GOBACK.

END PROGRAM Decode-Int.
"""

# Free-format with real paragraphs, a file description and a data copy.
FREE_WITH_PARAGRAPHS = """IDENTIFICATION DIVISION.
PROGRAM-ID. Test-Region.

ENVIRONMENT DIVISION.
INPUT-OUTPUT SECTION.
FILE-CONTROL.
    SELECT IN-FILE ASSIGN TO "in.dat".
DATA DIVISION.
FILE SECTION.
    FD IN-FILE.
    01 IN-REC.
        05 IN-DATA      PIC X(80).
WORKING-STORAGE SECTION.
    01 LOCATION.
        05 LOC-X        BINARY-LONG.
    77 RESULT           BINARY-LONG.

PROCEDURE DIVISION.
AllZero.
    MOVE 0 TO LOC-X
    PERFORM Other-Para.
    GOBACK.

Other-Para.
    DISPLAY "x".
"""

# Fixed format is untouched: a blank or 6-digit sequence area, with a real
# paragraph whose name begins with digits.
FIXED_FORMAT = (
    "000100 IDENTIFICATION DIVISION.\n"
    "000200 PROGRAM-ID. FIXED.\n"
    "000300 DATA DIVISION.\n"
    "000400 WORKING-STORAGE SECTION.\n"
    "000500 01  WS-REC.\n"
    "000600     05 WS-A PIC X.\n"
    "000700 PROCEDURE DIVISION.\n"
    "000800 01-MAIN.\n"
    "000900     DISPLAY 'x'.\n"
    "       10-NEXT.\n"
    "           STOP RUN.\n"
)


@pytest.mark.parametrize(
    ("code", "expected", "why"),
    [
        (SIBLING_PROGRAMS, [], "sibling programs with no paragraphs: no unit is a data item"),
        (FREE_WITH_PARAGRAPHS, ["AllZero", "Other-Para"], "real free-format paragraphs survive, data entries do not"),
        (FIXED_FORMAT, ["01-MAIN", "10-NEXT"], "fixed format: digit-led paragraph names are still units"),
    ],
    ids=["sibling_programs", "free_with_paragraphs", "fixed_format"],
)
def test_free_format_data_entries_are_not_units(code: str, expected: list[str], why: str):
    assert _units(code) == expected, why


@pytest.mark.parametrize(
    "entry",
    ["    01 VALUE-BYTES.", "  05 WS-GROUP.", "    77 WS-COUNTER.", "    FD IN-FILE.", "    sd SORT-FILE."],
)
def test_one_free_format_data_entry_is_not_a_paragraph(entry: str):
    code = f"DATA DIVISION.\nWORKING-STORAGE SECTION.\n{entry}\nPROCEDURE DIVISION.\nMAIN-PARA.\n    GOBACK.\n"
    assert _units(code) == ["MAIN-PARA"]


def test_the_count_and_the_unit_list_agree():
    """The filter is honoured by both the func_start count and the unit list (#2753)."""
    for code in (SIBLING_PROGRAMS, FREE_WITH_PARAGRAPHS, FIXED_FORMAT):
        assert _func_start_count(code) == len(_units(code))

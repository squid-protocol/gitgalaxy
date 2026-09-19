# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#3197: a COBOL paragraph header begins a SENTENCE.

`func_start` accepted any lone `NAME.` whose indentation reached Area B, so the
last line of a multi-line statement or data description became a paragraph: 9
phantom units on IBM/zopeneditor-sample, 26 + 4 on
cics-banking-sample-application-cbsa, each one also splitting the real
paragraph's span. #2538 shielded three LE tokens of that shape and deferred the
structural fix to "file-level fixed/free-format detection".

No such detection is needed, and an Area-A column anchor would be wrong: real
paragraphs sit in Area B in accepted source (measured on language-crucible
v1.3.0 -- `CBL0601v01InOutLineLoop.cbl` puts every paragraph in column 13, which
compilers accept with a warning). What separates a header from a continuation is
the language's own rule: a header can only appear where the previous sentence
has ended. Across the crucible, keyword-rosetta and all three pinned mainframe
corpora, every Area-A header follows a completed sentence, and the captures the
rule rejects are all statement/declaration tails.

The deciding context is the PREVIOUS line, which no lookbehind can span, so this
is a registry-declared scope filter (`_scope_filters: {"func_start": ...}`)
rather than a change to the regex.
"""

from __future__ import annotations

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _units(code: str) -> list[str]:
    return [f["name"] for f in StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]]


def _func_start_count(code: str) -> int:
    return StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(code, "")["equations"].get("func_start", 0)


# Free-format-ish source (Area A at column 8) carrying one phantom of each shape
# the corpora contain.
FREE_FORMAT = """       IDENTIFICATION DIVISION.
       PROGRAM-ID.
           DEMO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TOTALS.
       10  WS-OLD-DATE-PARTS               REDEFINES
           WS-OLD-DATE.
       PROCEDURE DIVISION USING
           TRAN-MSG.
       000-MAIN.
           DISPLAY 'Total: '
              WS-COUNT.
           PERFORM A-PARA.
           STOP RUN.
       A-PARA.
           DISPLAY 'A'.
       B-PARA SECTION.
           EXIT.
"""

# Fixed format: a 6-digit sequence area, a column-7 `-` continuation line, and
# the same phantom shape in Area B.
FIXED_FORMAT = (
    "000100 IDENTIFICATION DIVISION.\n"
    "000200 PROGRAM-ID. FIXED.\n"
    "000300 PROCEDURE DIVISION.\n"
    "000400 000-MAIN.\n"
    "000500     DISPLAY 'x'\n"
    "000600        WS-Y.\n"
    "000700 A-PARA.\n"
    "000800     MOVE 'aaa' TO\n"
    "000900-       'bbb'.\n"
    "001000 B-PARA.\n"
    "001100     EXIT.\n"
)

# A real paragraph indented into Area B, the shape an Area-A anchor would lose.
AREA_B_PARAGRAPHS = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. INDENTED.
       PROCEDURE DIVISION.
            A-PARA.
                DISPLAY 'IN A-PARA'.
                PERFORM C-PARA.
            B-PARA.
                DISPLAY 'IN B-PARA'.
                STOP RUN.
            C-PARA.
                DISPLAY 'IN C-PARA'.
"""


@pytest.mark.parametrize(
    ("code", "expected", "why"),
    [
        (FREE_FORMAT, ["000-MAIN", "A-PARA", "B-PARA"], "free format, one phantom per shape"),
        (FIXED_FORMAT, ["000-MAIN", "A-PARA", "B-PARA"], "sequence area + column-7 continuation"),
        (AREA_B_PARAGRAPHS, ["A-PARA", "B-PARA", "C-PARA"], "real paragraphs indented into Area B"),
    ],
    ids=["free_format", "fixed_format", "area_b_paragraphs"],
)
def test_only_sentence_initial_headers_are_units(code: str, expected: list[str], why: str):
    assert _units(code) == expected, why


@pytest.mark.parametrize(
    ("tail", "phantom"),
    [
        ("           DISPLAY 'Total: '\n              WS-COUNT.\n", "WS-COUNT"),
        ("           OPEN INPUT IN-FILE\n                OUTPUT REPORT-FILE.\n", "REPORT-FILE"),
        ("           MOVE ACCT-ID TO\n                VB2-ACCT-ID.\n", "VB2-ACCT-ID"),
        ("           SELECT SORT-FILE ASSIGN TO\n                XXXXX027.\n", "XXXXX027"),
    ],
    ids=["display", "open", "move", "select_assign"],
)
def test_a_statement_tail_is_not_a_paragraph(tail: str, phantom: str):
    code = "       PROCEDURE DIVISION.\n       000-MAIN.\n" + tail + "           STOP RUN.\n"
    assert phantom not in _units(code)
    assert _units(code) == ["000-MAIN"]


@pytest.mark.parametrize(
    "header",
    ["PROGRAM-ID", "DATE-COMPILED", "AUTHOR", "SOURCE-COMPUTER", "OBJECT-COMPUTER"],
)
def test_a_header_keyword_operand_on_its_own_line_is_not_a_paragraph(header: str):
    """`PROGRAM-ID.` ends a sentence, but the next line is its OPERAND."""
    code = f"       IDENTIFICATION DIVISION.\n       {header}.\n           OPERAND-NAME.\n"
    assert "OPERAND-NAME" not in _units(code)


def test_the_count_and_the_unit_list_agree():
    """coding_analysis counts `func_start`; `_slice_by_labels` builds the units.
    A filter only one of them honoured would make the same file report a
    different number of paragraphs depending on which one you read (#2753)."""
    for code in (FREE_FORMAT, FIXED_FORMAT, AREA_B_PARAGRAPHS):
        assert _func_start_count(code) == len(_units(code))


def test_a_phantom_no_longer_splits_the_real_paragraph_span():
    """The phantom ended the real paragraph's body early (#3197: SAM1's
    `000-MAIN` read 15 lines instead of 44)."""
    functions = StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(FREE_FORMAT, "")["functions"]
    main = next(f for f in functions if f["name"] == "000-MAIN")
    body = FREE_FORMAT[main["start_idx"] : main["end_idx"]]
    assert "PERFORM A-PARA." in body, "the span stopped at the phantom instead of covering the paragraph"

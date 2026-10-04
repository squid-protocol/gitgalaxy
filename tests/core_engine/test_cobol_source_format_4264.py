# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4264: fixed / free reference format, per file and per directive; column 72 only in fixed mode.

A fixed-format line ends at column 72: columns 73-80 are an identification area the compiler
ignores (NIST CCVS `IC1014.2`). A free-format line runs on, and cutting it at column 72 loses
program text. Prism now blanks the identification area of fixed lines only, for every COBOL
rule and reader; the format is detected per file (cobol_source_format.detect_format) and
switched mid-file by `>>SOURCE FORMAT` / `$SET SOURCEFORMAT` directives.
"""

from __future__ import annotations

import pytest

from gitgalaxy.core.cobol_source_format import (
    FIXED,
    FREE,
    VARIABLE,
    blank_identification_area,
    detect_format,
    directive_format,
    line_formats,
)
from gitgalaxy.core.db2_declare_table import _blank_sequence_fields
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _prism() -> Prism:
    return Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)


# NIST CCVS shape: every line carries its identification area in columns 73-80.
FIXED_SRC = (
    "000100 IDENTIFICATION DIVISION.                                         IC1014.2\n"
    "000200 PROGRAM-ID. IC101A.                                              IC1014.2\n"
    "000300* A COMMENT LINE                                                  IC1014.2\n"
    "000400 PROCEDURE DIVISION.                                              IC1014.2\n"
    "000500 MAIN-PARA.                                                       IC1014.2\n"
    "000600     DISPLAY 'HELLO'.                                             IC1014.2\n"
)
LONG = '    DISPLAY "THIS LITERAL RUNS WELL PAST COLUMN SEVENTY-TWO OF THE SOURCE LINE" UPON CONSOLE.'
# GnuCOBOL -free shape: text from column 1, `*>` comments, a statement past column 72.
FREE_SRC = (
    "*> a free-format program\n"
    "IDENTIFICATION DIVISION.\n"
    "PROGRAM-ID. FREEPROG.\n"
    "PROCEDURE DIVISION.\n"
    "MAIN-PARA.\n" + LONG + "\n"
    "NEXT-PARA.\n"
    "    STOP RUN.\n"
)
# Mixed: the file opens free by directive, then switches back to fixed.
MIXED_SRC = (
    "       >>SOURCE FORMAT IS FREE\n"
    "IDENTIFICATION DIVISION.\n"
    "PROGRAM-ID. MIXED.\n" + LONG + "\n"
    ">>SOURCE FIXED\n"
    "       PROCEDURE DIVISION.                                              AB000100\n"
)


@pytest.mark.parametrize(
    "line, fmt",
    [
        ("       >>SOURCE FORMAT IS FREE", FREE),
        (">>SOURCE FREE", FREE),
        (">>source format fixed", FIXED),
        ("      >>FORMAT IS VARIABLE", VARIABLE),
        ('      $SET SOURCEFORMAT"FREE"', FREE),
        ("      $SET SOURCEFORMAT(FIXED)", FIXED),
        ("      $SET ANS85 SOURCEFORMAT 'FREE' NOTRUNC", FREE),  # among other $SET options
        ("       DISPLAY '>>SOURCE FREE'.", None),  # inside a literal, not at the line start
        ("      * >>SOURCE FREE", None),
    ],
)
def test_directive_format(line, fmt):
    assert directive_format(line) == fmt


def test_detection_fixed_free_and_default():
    assert detect_format(FIXED_SRC.split("\n")) == FIXED
    assert detect_format(FREE_SRC.split("\n")) == FREE
    # no evidence either way (Area B text, short lines): the mainframe default
    assert detect_format(["           MOVE A TO B.", "           GOBACK."]) == FIXED


def test_fixed_identification_area_is_blanked_offsets_kept():
    out = blank_identification_area(FIXED_SRC)
    assert "IC1014.2" not in out
    assert [len(x) for x in out.split("\n")] == [len(x) for x in FIXED_SRC.split("\n")]


def test_a_free_line_past_column_72_is_kept():
    assert len(LONG) > 72
    assert blank_identification_area(FREE_SRC) == FREE_SRC
    assert _blank_sequence_fields(FREE_SRC, "cobol") == FREE_SRC


def test_a_directive_switches_mid_file():
    assert line_formats(MIXED_SRC) == [FREE, FREE, FREE, FREE, FREE, FIXED, FIXED]
    out = blank_identification_area(MIXED_SRC)
    assert LONG in out  # free: kept past column 72
    assert "AB000100" not in out  # fixed again after >>SOURCE FIXED


def test_prism_code_stream_drops_only_the_fixed_identification_area():
    prism = _prism()
    assert "IC1014.2" not in prism.split_streams(FIXED_SRC, "cobol")["code_stream"]
    assert "UPON CONSOLE." in prism.split_streams(FREE_SRC, "cobol")["code_stream"]


def test_a_free_sentence_ending_past_column_72_still_ends():
    """The period of LONG sits past column 72; cut there, NEXT-PARA read as the tail of an unended
    sentence and was no paragraph."""
    code = _prism().split_streams(FREE_SRC, "cobol")["code_stream"]
    units = [f["name"] for f in StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]]
    assert "NEXT-PARA" in units

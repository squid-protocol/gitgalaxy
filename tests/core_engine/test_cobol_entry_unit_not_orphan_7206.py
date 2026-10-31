# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#7206: the unit a COBOL PROCEDURE DIVISION falls into is never an orphan or a duplicate.

Control enters at the first paragraph after the header (no main line), or at the
first section and its first paragraph; nothing PERFORMs it by name. A main line
is the entry instead, and the paragraph after it is reached only by fall-through
(out of scope: it stays flagged). Each program, nested or sibling, has its own entry.
"""

from __future__ import annotations

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

HEAD = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. {0}.\n       PROCEDURE DIVISION.\n"


def _status(code: str) -> dict[str, int]:
    out = StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(code, "")
    return {f["name"]: f["usage_status"] for f in out["functions"]}


def test_the_first_paragraph_is_not_an_orphan_and_a_dead_one_still_is():
    code = (
        HEAD.format("P")
        + "       MAIN-PARA.\n           PERFORM WORK-PARA.\n           STOP RUN.\n"
        + "       WORK-PARA.\n           DISPLAY 'X'.\n"
        + "       UNUSED-PARA.\n           DISPLAY 'Y'.\n"
    )
    assert _status(code) == {"MAIN-PARA": 0, "WORK-PARA": 0, "UNUSED-PARA": 1}


def test_a_first_section_and_its_first_paragraph_are_entered():
    code = (
        HEAD.format("P")
        + "       PREMIERE SECTION.\n       A010.\n           PERFORM B010.\n           STOP RUN.\n"
        + "       B010.\n           DISPLAY 'X'.\n"
        + "       SECOND SECTION.\n       C010.\n           DISPLAY 'Z'.\n"
    )
    assert _status(code) == {"PREMIERE": 0, "A010": 0, "B010": 0, "SECOND": 1, "C010": 1}


def test_a_section_with_code_before_its_first_paragraph_does_not_enter_the_paragraph():
    code = (
        HEAD.format("P")
        + "       PREMIERE SECTION.\n           DISPLAY 'S'.\n       A010.\n           DISPLAY 'A'.\n"
    )
    assert _status(code) == {"PREMIERE": 0, "A010": 1}


def test_a_main_line_is_the_entry_so_the_first_paragraph_is_still_flagged():
    code = HEAD.format("P") + "           DISPLAY 'MAIN'.\n       FIRST-PARA.\n           DISPLAY 'F'.\n"
    assert _status(code) == {"FIRST-PARA": 1}


def test_nested_and_sibling_programs_each_have_their_own_entry():
    code = (
        HEAD.format("OUTER")
        + "       OUTER-ENTRY.\n           CALL 'INNER'.\n           STOP RUN.\n"
        + "       OUTER-DEAD.\n           DISPLAY 'D'.\n"
        + HEAD.format("INNER")
        + "       INNER-ENTRY.\n           DISPLAY 'I'.\n"
        + "       INNER-DEAD.\n           DISPLAY 'D'.\n"
        + "       END PROGRAM INNER.\n       END PROGRAM OUTER.\n"
        + HEAD.format("SIB")
        + "       SIB-ENTRY.\n           DISPLAY 'S'.\n       END PROGRAM SIB.\n"
    )
    assert _status(code) == {
        "OUTER-ENTRY": 0,
        "OUTER-DEAD": 1,
        "INNER-ENTRY": 0,
        "INNER-DEAD": 1,
        "SIB-ENTRY": 0,
    }


def test_two_programs_with_the_same_entry_paragraph_are_not_duplicates():
    body = "       ENTRY-PARA.\n           DISPLAY 'S'.\n           STOP RUN.\n"
    code = HEAD.format("A") + body + "       END PROGRAM A.\n" + HEAD.format("B") + body + "       END PROGRAM B.\n"
    out = StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(code, "")
    assert [f["usage_status"] for f in out["functions"]] == [0, 0]
    assert not out["equations"].get("duplicate_logic")
    assert not out["equations"].get("unreferenced_by_name")

# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""COBOL words run through hyphens, and `\\b` fires at every hyphen.

So a keyword rule matched INSIDE names: `io` counted WRITE in `WRITE-LINE`,
`serialization_parsing` counted the `END-STRING` terminator as a STRING,
`ipc_rpc_bridges` counted `END-CALL`, `api` counted `ENTRY-1`. Measured over
language-crucible plus the three pinned mainframe corpora, 8,841 of `io`'s
matches were inside names. On CardDemo, `arch_io` read 1121 where 426 are real.

Earlier fixes guarded rules one at a time (#2537, #2772, #2888, #3359). The
cobol registry now declares `_hyphenated_words`, and the rule loop drops any
match glued to a hyphenated word (detector._glued_to_hyphen_word) for every rule.
"""

from __future__ import annotations

import pytest

from gitgalaxy.core.detector import StructuralExtractor, _glued_to_hyphen_word
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _eq(code: str) -> dict:
    return StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(code, "")["equations"]


def _program(procedure: str, data: str = "") -> str:
    return (
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. DEMO.\n       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n" + data + "       PROCEDURE DIVISION.\n" + procedure
    )


@pytest.mark.parametrize(
    ("text", "start", "end", "glued"),
    [
        ("END-IF", 4, 6, True),  # terminator: an identifier runs into the match
        ("WRITE-LINE", 0, 5, True),  # the match runs on into a name
        ("SQLCODE-DISPLAY", 8, 15, True),
        ("ENTRY-1", 0, 5, True),
        ("A -- IF", 5, 7, False),  # a hyphen with a space beside it is not a word
        ("--TODO", 2, 6, False),  # nor is a double hyphen with nothing alphanumeric before it
        ("MOVE X TO Y", 0, 4, False),
    ],
)
def test_glued_to_hyphen_word(text, start, end, glued):
    assert _glued_to_hyphen_word(text, start, end) is glued


def test_cobol_declares_hyphenated_words():
    assert LANGUAGE_DEFINITIONS["cobol"]["rules"]["_hyphenated_words"] is True


def test_names_containing_keywords_are_not_counted():
    names = _eq(
        _program(
            "       MAIN-PARA.\n"
            "           PERFORM WRITE-LINE\n"
            "           PERFORM OPEN-FILES\n"
            "           MOVE SQLCODE TO SQLCODE-DISPLAY\n"
            "           MOVE 1 TO ENTRY-1\n"
            "           MOVE 1 TO INSPECT-COUNTER\n"
            "           GOBACK.\n"
            "       WRITE-LINE.\n           CONTINUE.\n"
            "       OPEN-FILES.\n           CONTINUE.\n",
            data="       01 SQLCODE-DISPLAY PIC -9(9).\n       01 ENTRY-1 PIC 9.\n       01 INSPECT-COUNTER PIC 9.\n",
        )
    )
    assert names.get("io", 0) == 0
    assert names.get("api", 0) == 0
    assert names.get("regex_execution", 0) == 0


def test_real_keywords_still_count_and_terminators_do_not():
    eq = _eq(
        _program(
            "       MAIN-PARA.\n"
            "           OPEN INPUT IN-FILE\n"
            "           READ IN-FILE\n"
            "               AT END CONTINUE\n"
            "           END-READ\n"
            "           STRING WS-A DELIMITED BY SIZE INTO WS-B\n"
            "           END-STRING\n"
            "           CALL 'SUB' USING WS-A\n"
            "           END-CALL\n"
            "           GOBACK.\n",
            data="       01 WS-A PIC X.\n       01 WS-B PIC X(2).\n",
        )
    )
    assert eq.get("io") == 2  # OPEN, READ -- not END-READ
    assert eq.get("serialization_parsing") == 1  # STRING -- not END-STRING
    assert eq.get("ipc_rpc_bridges") == 1  # CALL -- not END-CALL


def test_accept_from_day_of_week_is_a_time_source():
    """DAY-OF-WEEK is itself hyphenated; the rule names it so the guard keeps it."""
    eq = _eq(
        _program(
            "       MAIN-PARA.\n           ACCEPT WS-D FROM DAY-OF-WEEK\n           GOBACK.\n",
            data="       01 WS-D PIC 9.\n",
        )
    )
    assert eq.get("time_date_logic") == 1

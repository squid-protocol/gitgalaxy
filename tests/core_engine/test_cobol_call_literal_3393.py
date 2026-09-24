# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#3393: in `CALL 'SUBPROG'` the literal is the callee, but the literal shield
blanked it before calls_out ran, so COBOL program-to-program calls never
reached calls_out_to, the call resolver or the file graph. Run through prism
exactly as galaxyscope does, so comments are stripped first."""

from __future__ import annotations

import re

from gitgalaxy.core.detector import StructuralExtractor, _blank_literals_except_callee
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

SRC = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEMO.
       PROCEDURE DIVISION.
       MAIN-PARA.
      *    CALL 'COMMENTED' USING X
           DISPLAY 'CALL NOTME NOW'
           CALL 'PROG2' USING WS-X
           CALL "PROG3"
           CALL WS-PGM USING WS-X
           PERFORM SUB-PARA
           GOBACK.
       SUB-PARA.
           DISPLAY 'S'.
"""


def _calls(src: str) -> dict[str, list[str]]:
    ref = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS).split_streams(src, "cobol")
    r = StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(
        code_stream=ref["code_stream"], comment_stream=ref["comment_stream"], raw_content=src
    )
    return {f["name"]: f["calls_out_to"] for f in r["functions"]}


def test_call_literal_is_a_callee_in_source_order():
    assert _calls(SRC)["MAIN-PARA"] == ["PROG2", "PROG3", "WS-PGM", "SUB-PARA"]


def test_only_the_literal_after_the_verb_is_kept():
    verb = re.compile(r"(?i)(?<![\w-])CALL\s+$")
    text = "DISPLAY 'CALL X' CALL 'PROG2' MOVE 'Y' TO Z"
    assert _blank_literals_except_callee(text, verb) == "DISPLAY '      ' CALL 'PROG2' MOVE ' ' TO Z"
    assert len(_blank_literals_except_callee(text, verb)) == len(text)


def test_cobol_declares_the_literal_callee_verb():
    assert "_calls_out_literal_callee" in LANGUAGE_DEFINITIONS["cobol"]["rules"]

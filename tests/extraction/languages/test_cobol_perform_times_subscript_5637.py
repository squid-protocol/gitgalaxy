"""#5637: `PERFORM x(i) TIMES` counts an inline loop with a subscripted data item; it names no paragraph.
Same for reference-modified and qualified counts. Out-of-line `PERFORM PARA-X n TIMES` still calls PARA-X."""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

P = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)

BODY = [
    "PERFORM WS-COUNT(WS-SLOT) TIMES",
    "   ADD 1 TO WS-TOTAL",
    "END-PERFORM",
    "PERFORM WS-COUNT (WS-SLOT) TIMES",
    "   ADD 1 TO WS-TOTAL",
    "END-PERFORM",
    "PERFORM WS-COUNT(WS-A + 1, 2) TIMES",
    "   ADD 1 TO WS-TOTAL",
    "END-PERFORM",
    "PERFORM WS-COUNT(WS-ROW(1)) TIMES",
    "   ADD 1 TO WS-TOTAL",
    "END-PERFORM",
    "PERFORM WS-COUNT(1:2) TIMES",
    "   ADD 1 TO WS-TOTAL",
    "END-PERFORM",
    "PERFORM WS-COUNT OF WS-REC(2) TIMES",
    "   ADD 1 TO WS-TOTAL",
    "END-PERFORM",
    "PERFORM WS-COUNT(WS-SLOT)",
    "        TIMES",
    "   ADD 1 TO WS-TOTAL",
    "END-PERFORM",
    "PERFORM 7 TIMES",
    "   ADD 1 TO WS-TOTAL",
    "END-PERFORM",
    "PERFORM VARYING WS-SLOT FROM 1 BY 1 UNTIL WS-SLOT > 3",
    "   ADD 1 TO WS-TOTAL",
    "END-PERFORM",
    "PERFORM UNTIL WS-TOTAL > 99",
    "   ADD 1 TO WS-TOTAL",
    "END-PERFORM",
    "PERFORM WORK-PARA WS-COUNT(WS-SLOT) TIMES",
    "PERFORM WORK-PARA",
    "STOP RUN.",
]
TAIL = ["WORK-PARA.", "    ADD 1 TO WS-TOTAL."]
HEAD = [
    "IDENTIFICATION DIVISION.",
    "PROGRAM-ID. REPRO5.",
    "DATA DIVISION.",
    "WORKING-STORAGE SECTION.",
    "01  WS-SLOT PIC 9(4) COMP VALUE 1.",
    "01  WS-TOTAL PIC 9(4) COMP VALUE 0.",
    "01  WS-COUNT PIC 9(4) COMP OCCURS 4.",
    "PROCEDURE DIVISION.",
    "MAIN-PARA.",
]


def _src(fixed: bool) -> str:
    def lay(lines, indent):
        return [" " * indent + ln for ln in lines]

    if fixed:
        # Area A (col 8) for headers, area B (col 12) for statements.
        out = [f"       {h}" for h in HEAD[:-1]] + [f"       {HEAD[-1]}"]
        out += lay(BODY, 11)
        out += [f"       {TAIL[0]}", f"           {TAIL[1]}"]
    else:
        out = list(HEAD) + BODY + TAIL
    return "\n".join(out) + "\n"


@pytest.mark.parametrize("fixed", [True, False], ids=["fixed", "free"])
def test_subscripted_times_count_is_not_a_paragraph_call(fixed):
    src = _src(fixed)
    st = P.split_streams(src, "cobol")
    out = StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(
        code_stream=st["code_stream"],
        comment_stream=st["comment_stream"],
        raw_content=src,
        positional_comment_stream=P.split_positional_comment_stream(src, "cobol"),
    )
    calls = {f["name"]: f["calls_out_to"] for f in out["functions"]}
    assert calls["MAIN-PARA"] == ["WORK-PARA"]

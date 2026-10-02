"""statement_inventory: statements split at verbs (literals and EXEC blocks whole, conditional phrases not statements,
procedure copybooks expanded) and bucketed by what translating them needs."""

from __future__ import annotations  # `dict | None` in a signature, on Python 3.9

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import statement_inventory as si


def _src(*body: str) -> str:
    return "".join(
        f"       {b}\n" for b in ("IDENTIFICATION DIVISION.", "PROGRAM-ID. P.", "PROCEDURE DIVISION.", *body)
    )


def _sts(text: str, index: dict | None = None) -> list[dict]:
    return si.statements(si.tokens(si.procedure_division(si.expand(si.code_lines(text), index or {}))))


def test_statements_split_at_verbs_and_keep_literals_and_exec_blocks_whole():
    sts = _sts(_src("MAIN-PARA.", "    MOVE 'READ IT' TO A", "    READ F AT END MOVE 'Y' TO EOF END-READ",
                    "    EXEC CICS RETURN TRANSID('T') END-EXEC", "    GOBACK."))  # fmt: skip
    assert [s["verb"] for s in sts] == ["MOVE", "READ", "MOVE", "EXEC", "GOBACK"]
    assert sts[0]["text"] == "MOVE 'READ IT' TO A" and sts[0]["paragraph"] == "MAIN-PARA"
    assert sts[3]["text"].startswith("EXEC:CICS RETURN")


def test_a_procedure_copybook_is_expanded_with_its_replacing(tmp_path):
    (tmp_path / "SETATT.cpy").write_text("           MOVE DFHBMPRF TO (TESTVAR1)A OF X\n")
    sts = _sts(_src("A.", "    COPY SETATT REPLACING ==(TESTVAR1)== BY ==NAME==."), {"SETATT": tmp_path / "SETATT.cpy"})
    assert [s["text"] for s in sts] == ["MOVE DFHBMPRF TO NAMEA OF X"]


def test_buckets():
    estate = {"SUBPGM"}

    def b(text: str) -> tuple[str, str]:
        (st,) = _sts(_src("A.", "    " + text))
        return si.classify(st, estate)

    assert b("MOVE A TO B")[0] == "S" and b("COMPUTE X = Y * 2")[0] == "S" and b("EVALUATE TRUE END-EVALUATE")[0] == "S"
    assert b("PERFORM P1")[0] == "R" and b("PERFORM P1 THRU P1-EXIT") == ("F", "PERFORM THRU")
    assert b("GO TO P2") == ("F", "GO TO") and b("STRING A DELIMITED BY SIZE INTO B") == ("L", "STRING")
    assert b("MOVE FUNCTION UPPER-CASE(A) TO B") == ("L", "intrinsic FUNCTION UPPER-CASE")
    assert b("CALL 'SUBPGM' USING A") == ("R", "CALL of an estate program")
    assert b("CALL 'CEEDAYS' USING A") == ("R", "CALL CEEDAYS (modelled)")
    assert b("CALL 'COBDATFT' USING A") == ("H", "CALL COBDATFT (no program, no model)")
    assert b("CALL WS-PGM USING A") == ("H", "dynamic CALL (identifier)")
    assert b("SET ADDRESS OF LK TO PTR") == ("H", "pointer (SET ADDRESS OF)")
    assert b("ACCEPT WS-D FROM DATE YYYYMMDD")[0] == "R" and b("ACCEPT WS-PARM")[0] == "H"
    assert b("EXEC SQL SELECT 1 INTO :X FROM T END-EXEC") == ("H", "EXEC SQL")
    assert b("EXEC CICS RETURN END-EXEC")[0] == "R"
    assert (
        b("EXEC CICS DELAY FOR SECONDS(1) END-EXEC")[0] == "R" and b("EXEC CICS WEB RECEIVE INTO(X) END-EXEC")[0] == "H"
    )

"""#8121: a SQLCA declared COMP (IBM's own SQLCA copybook, as example-health-apis ships it) is held big-endian, so
`EVALUATE SQLCODE WHEN 100` matches after a no-row SELECT. DetSql wrote every SQLCA field in the COMP-5 order
(little-endian), so +100 read back as 1677721600 and took the OTHER arm. The COMP-5 stand-in (`det/copy/SQLCA.cpy`) is
untouched: its ports carry no registration call and keep the little-endian read."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
STUB = "public class SqlcService {\n    public int handleCall(CobolRef<byte[]> a) {\n        return 0;\n    }\n}\n"
DETSQL = ROOT / "gitgalaxy/tools/cobol_to_java/det/cobolrt/sql/DetSql.java"
COMP_SQLCA = """       01  SQLCA.
           05  SQLCAID     PIC X(8).
           05  SQLCABC     PIC S9(9) COMP.
           05  SQLCODE     PIC S9(9) COMP.
           05  SQLERRM.
               49  SQLERRML PIC S9(4) COMP.
               49  SQLERRMC PIC X(70).
           05  SQLERRP     PIC X(8).
           05  SQLERRD     OCCURS 6 TIMES PIC S9(9) COMP.
           05  SQLWARN.
               10  SQLWARN0 PIC X.
               10  SQLWARN1 PIC X.
               10  SQLWARN2 PIC X.
               10  SQLWARN3 PIC X.
               10  SQLWARN4 PIC X.
               10  SQLWARN5 PIC X.
               10  SQLWARN6 PIC X.
               10  SQLWARN7 PIC X.
           05  SQLSTATE    PIC X(5).
"""
# every statement whose no-row outcome is SQLCODE +100 reads SQLCODE the same way, whichever one set it
STATEMENTS = [
    "SELECT 1 INTO :N FROM T WHERE K = :K",
    "FETCH C1 INTO :N",
    "UPDATE T SET V = 1 WHERE K = :K",
    "DELETE FROM T WHERE K = :K",
]
PROC = [
    "EXEC SQL DECLARE C1 CURSOR FOR SELECT V FROM T END-EXEC",
    "EXEC SQL OPEN C1 END-EXEC",
]


def _program(stmt: str) -> str:
    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. SQLC.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
             "01 N PIC S9(9) COMP-5.", "01 K PIC S9(4) COMP-5.", "01 R PIC X(2).",
             "    EXEC SQL INCLUDE SQLCA END-EXEC.", "PROCEDURE DIVISION.", *[f"    {p}" for p in PROC],
             f"    EXEC SQL {stmt} END-EXEC", "    EVALUATE SQLCODE", "        WHEN 0 MOVE '00' TO R",
             "        WHEN 100 MOVE 'NF' TO R", "        WHEN -811 MOVE 'ME' TO R", "        WHEN OTHER MOVE '90' TO R",
             "    END-EVALUATE", "    GOBACK."]  # fmt: skip
    return "\n".join(f"       {x}" for x in lines) + "\n"


def _translate(tmp_path: Path, stmt: str, comp: bool):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    copy = tmp_path / ("copy_comp" if comp else "copy_none")
    copy.mkdir(exist_ok=True)
    if comp:
        (copy / "SQLCA.cpy").write_text(COMP_SQLCA)
    (tmp_path / "SQLC.cbl").write_text(_program(stmt))
    (tmp_path / "project").mkdir(exist_ok=True)
    return P.translate(tmp_path / "SQLC.cbl", [copy], STUB, "p", None, tmp_path / "project")


@pytest.mark.parametrize("stmt", STATEMENTS)
def test_a_comp_sqlca_is_registered_and_the_comp5_standin_is_not(stmt, tmp_path):
    assert "DetSql.sqlcaBigEndian(s_SQLCA);" in _translate(tmp_path, stmt, comp=True).java
    assert "sqlcaBigEndian" not in _translate(tmp_path, stmt, comp=False).java


class _Gen:
    cics = None
    para_index = {"NF-PARA": 4}

    def __init__(self, comp_sqlca):
        if comp_sqlca is not None:
            self.comp_sqlca = comp_sqlca

    def field_expr(self, ref):
        return "ca"

    def jump(self, target):
        return f"return GOTO | {target};"


@pytest.mark.parametrize(("comp", "order"), [(True, "BIG_ENDIAN"), (False, "LITTLE_ENDIAN"), (None, "LITTLE_ENDIAN")])
def test_the_whenever_sqlcode_read_follows_the_sqlca_declaration(comp, order):
    from types import SimpleNamespace

    from gitgalaxy.tools.cobol_to_java.det.sql import Sql

    stmts = [
        SimpleNamespace(text="EXEC SQL WHENEVER NOT FOUND GO TO NF-PARA END-EXEC", line=1),
        SimpleNamespace(text="EXEC SQL COMMIT END-EXEC", line=2),
    ]
    s = Sql(_Gen(comp), "P", None)
    s.scan_whenever(stmts)
    out = s.command(stmts[1].text, stmts[1].line, "")
    other = "LITTLE_ENDIAN" if order == "BIG_ENDIAN" else "BIG_ENDIAN"
    assert any(f"ByteOrder.{order}" in x for x in out) and not any(other in x for x in out)


def test_every_sqlca_write_goes_through_the_order_aware_putint():
    src = DETSQL.read_text()
    assert "BIG_ENDIAN_SQLCA.contains(ca.storage())" in src
    body = src.split("private static void putInt", 1)[1].split("}", 2)[0]
    assert "big ? bytes - 1 - i : i" in body
    # no SQLCA number is written around putInt (a direct bytes[] store of a code would skip the order)
    assert "SQLCODE] =" not in src and "SQLCODE + " not in src.replace("ca.offset() + SQLCODE", "")

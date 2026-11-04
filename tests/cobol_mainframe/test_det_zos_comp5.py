"""#7646 slice 2 (register C7): the translator holds COMP-5 big-endian, as z/OS does, only when asked
(`translate(zos_comp5=True)`), and lifts the refusals of a COMP-5 item's bytes only then. Synthetic programs only."""

from __future__ import annotations

import pytest

PKG = "p"
# a stub with a CALL entry, the one Cobol.swapZosComp5 is wrapped around
STUB = "public class Zc5Service {\n    public int handleCall(CobolRef<byte[]> a) {\n        return 0;\n    }\n}\n"
BYTE_USES = [
    (["01 G.", "   05 A PIC S9(4) COMP-5 VALUE 1.", "   05 B PIC X(2)."], ["MOVE G TO T"]),
    (["01 A PIC S9(9) COMP-5 VALUE 1.", "01 X REDEFINES A PIC X(4)."], ["MOVE X TO T"]),
    (["01 A PIC S9(18) COMP-5 VALUE 1.", "01 X REDEFINES A PIC X(8)."], ["MOVE X TO T"]),
    (["01 A PIC S9(9) COMP-5 VALUE 1."], ["MOVE A(1:2) TO T"]),
    (["01 G.", "   05 A PIC S9(4) COMP-5 OCCURS 3.", "01 X REDEFINES G PIC X(6)."], ["MOVE X TO T"]),
    (["01 A PIC S9(4) COMP-5 VALUE 1.", "01 X REDEFINES A PIC S9(4) COMP."], ["MOVE X TO N"]),
]


def _program(data: list[str], proc: list[str]) -> str:
    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. ZC5.", "DATA DIVISION.", "WORKING-STORAGE SECTION.", *data]
    lines += ["01 T PIC X(8).", "01 N PIC S9(4).", "PROCEDURE DIVISION.", *[f"    {x}" for x in proc], "    GOBACK."]
    return "\n".join(f"       {x}" for x in lines) + "\n"


def _translate(tmp_path, data, proc, zos_comp5):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "ZC5.cbl").write_text(_program(data, proc))
    (tmp_path / "project").mkdir(exist_ok=True)
    return P.translate(tmp_path / "ZC5.cbl", [], STUB, PKG, None, tmp_path / "project",
                       zos_comp5=zos_comp5)  # fmt: skip


@pytest.mark.parametrize(("data", "proc"), BYTE_USES)
def test_byte_uses_are_refused_by_default_and_translated_under_the_declared_difference(data, proc, tmp_path):
    off = _translate(tmp_path, data, proc, False)
    assert any("oracle_assumptions.md C7" in h for h in off.stats["holes"]), off.stats["holes"]
    assert "swapZosComp5" not in off.java  # the default port is unchanged
    on = _translate(tmp_path, data, proc, True)
    assert not any("C7" in h for h in on.stats["holes"]), on.stats["holes"]
    assert "Cobol.swapZosComp5(true)" in on.java and "Cobol.swapZosComp5(comp5Before)" in on.java


def test_the_value_image_follows_the_order(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import layout as L

    (tmp_path / "ZC5.cbl").write_text(
        _program(["01 A PIC S9(4) COMP-5 VALUE 258.", "01 B PIC S9(9) COMP-5 VALUE -2."], [])
    )
    recs = L.records(tmp_path / "ZC5.cbl", [])
    a, b = (r for r in recs if r.name in ("A", "B"))
    assert (L.image(a), L.image(b)) == (b"\x02\x01", b"\xfe\xff\xff\xff")
    token = L.COMP5_BIG.set(True)
    try:
        assert (L.image(a), L.image(b)) == (b"\x01\x02", b"\xff\xff\xff\xfe")
    finally:
        L.COMP5_BIG.reset(token)
    assert L.image(a) == b"\x02\x01"  # restored


@pytest.mark.parametrize(
    ("proc", "why"),
    [
        (["EXEC SQL COMMIT END-EXEC"], "EXEC SQL"),
        (["CALL 'CEEDAYS' USING N"], "CEEDAYS"),
        (["CALL 'DSNTIAC' USING N"], "DSNTIAC"),
        (["CALL 'OTHERPGM' USING N"], "OTHERPGM"),
    ],
)
def test_sql_le_and_foreign_calls_stay_refused_under_the_switch(proc, why, tmp_path):
    data = ["01 A PIC S9(4) COMP-5 VALUE 1."]
    with pytest.raises(ValueError, match=why):
        _translate(tmp_path, data, proc, True)

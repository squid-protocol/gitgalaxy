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


# ---- slice 4: IMS DL/I (CALL 'CBLTDLI') is not a foreign program ------------------------------------------------
def _dli_source(call: str, entry: bool = True) -> str:
    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. DLIT.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
             "01  FN PIC X(4) VALUE 'GU  '.", "01  IOA.", "    05 IO-KEY PIC X(4).", "    05 IO-CNT PIC S9(9) COMP-5 VALUE 7.",
             "01  IOX REDEFINES IOA PIC X(8).", "LINKAGE SECTION.", "01  PCB1.", "    05 P-DBD PIC X(8).",
             "    05 P-REST PIC X(38).", "PROCEDURE DIVISION.", "MAIN-PARA.",
             *(["    ENTRY 'DLITCBL' USING PCB1."] if entry else []), f"    {call}", "    MOVE IOX TO IOX", "    GOBACK."]  # fmt: skip
    return "\n".join(" " * 7 + ln for ln in lines) + "\n"


def _dli_translate(tmp_path, src, zos_comp5):
    pytest.importorskip("tree_sitter_language_pack")
    import sys
    from pathlib import Path

    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    import test_det_programs as tdp

    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "DLIT.cbl").write_text(src)
    project = tmp_path / "project"
    tdp._batch_package(project / "src/main/java")
    return P.translate(tmp_path / "DLIT.cbl", [], "public class DlitService {\n}\n", PKG, None, project,
                       zos_comp5=zos_comp5)  # fmt: skip


@pytest.mark.parametrize("name", ["CBLTDLI", "CEETDLI"])
def test_a_dl_i_call_translates_under_the_switch_with_its_io_area_big_endian(name, tmp_path):
    """The DL/I I/O area holds a COMP-5 item and a REDEFINES over its bytes: under the switch the area is IBM's
    big-endian image, and the CALL is DetDli's, not a program outside the source."""
    src = _dli_source(f"CALL '{name}' USING FN PCB1 IOA")
    off = _dli_translate(tmp_path, src, False)
    assert any("C7" in h for h in off.stats["holes"]), off.stats["holes"]  # default: bytes refused, as before
    on = _dli_translate(tmp_path, src, True)
    assert not on.stats["holes"], on.stats["holes"]
    assert "DetDli.call(" in on.java and "Cobol.swapZosComp5(true)" in on.java


def test_the_other_dl_i_interfaces_stay_refused_under_the_switch(tmp_path):
    with pytest.raises(ValueError, match="AIBTDLI"):  # outside the DL/I calls dli.CALLS names: a foreign CALL
        _dli_translate(tmp_path, _dli_source("CALL 'AIBTDLI' USING FN PCB1 IOA"), True)
    # a program IMS does not enter at DLITCBL: dli.call's own refusal, not a COMP-5 one
    on = _dli_translate(tmp_path, _dli_source("CALL 'CBLTDLI' USING FN PCB1 IOA", entry=False), True)
    assert any("DLITCBL" in h for h in on.stats["holes"]), on.stats["holes"]


def test_the_burned_carddemo_ims_programs_translate_under_the_switch(tmp_path):
    """PAUDBLOD, PAUDBUNL and DBUNLDGS CALL 'CBLTDLI' and declare COMP-5 only in IMSFUNCS (#7646 ruling B)."""
    pytest.importorskip("tree_sitter_language_pack")
    import os
    from pathlib import Path

    root = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    app = Path(root or "/nonexistent") / "aws-mainframe-modernization-carddemo/app/app-authorization-ims-db2-mq"
    if not app.is_dir():
        pytest.skip("the CardDemo corpus is not checked out")
    from gitgalaxy.tools.cobol_to_java.det import program as P
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import test_det_programs as tdp

    for prog in ("PAUDBLOD", "PAUDBUNL", "DBUNLDGS"):
        project = tmp_path / prog
        tdp._batch_package(project / "src/main/java")
        r = P.translate(app / "cbl" / f"{prog}.CBL", [app / "cpy"], f"public class {prog.title()}Service {{\n}}\n", PKG,
                        None, project, zos_comp5=True)  # fmt: skip
        assert not r.stats["holes"], (prog, r.stats["holes"])
        assert "Cobol.swapZosComp5(true)" in r.java

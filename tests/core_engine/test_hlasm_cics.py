"""#3495: command-level EXEC CICS in HLASM, read by the COBOL command walkers
through core/hlasm_cics.py's END-EXEC rewrite. The shapes are walmartlabs/zECS's
(crucible data/hlasm/zecs)."""

from gitgalaxy.core.hlasm_cics import cics_stream, dc_values
from gitgalaxy.core.mainframe_boundary import extract_boundary


def _line(text: str, mark: str = " ") -> str:
    """One assembler source line: text in columns 1-71, `mark` in column 72."""
    return text.ljust(71) + mark


SOURCE = "\n".join(
    [
        "*        EXEC CICS LINK PROGRAM('COMMENT')",
        "ZECSNC   DFHEIENT CODEREG=(R12),DATAREG=R10,EIBREG=R11",
        _line("         EXEC CICS START TRANSID(Z_EXP) FROM (Z_TRAN)", "X"),
        "               LENGTH (4) NOHANDLE",
        "         EXEC CICS ABEND ABCODE(AB_001) NOHANDLE",
        _line("         EXEC CICS VERIFY USERID(USERID) PASSWORD(PASSWORD)", "X"),
        "              NOHANDLE",  # column 15: real source drifts a column
        "         OC    EIBRESP,EIBRESP         Normal response?",
        "         BC    B'0111',ER_0001",
        "         EXEC CICS WRITEQ TD QUEUE('@tdq@') FROM(TD_DATA) NOHANDLE",
        "         EXEC CICS LINK PROGRAM(PGMNAME) COMMAREA(CA)",
        "         EXEC CICS RETURN",
        "AB_001   DC    CL04'Z001'",
        "PGMNAME  DC    CL8'ZECS003 '",
        "         CALL  SUBPGM,(PARM)",
    ]
)


def test_stream_is_line_aligned_and_closes_each_command():
    stream = cics_stream(SOURCE)
    lines = stream.split("\n")
    assert len(lines) == len(SOURCE.split("\n"))
    assert "COMMENT" not in stream  # a column-1 `*` comment is blanked
    assert lines[3].endswith("NOHANDLE END-EXEC")  # after the continuation, not the X line
    assert "X" not in lines[2][60:]  # the column-72 mark is gone
    assert lines[6].rstrip().endswith("NOHANDLE END-EXEC")  # column-15 continuation kept
    assert stream.count("END-EXEC") == 6


def test_dc_values_read_character_constants_with_hlasm_symbols():
    assert dc_values(SOURCE) == {"AB_001": "Z001", "PGMNAME": "ZECS003"}  # pad stripped


def test_boundary_carries_every_cics_channel():
    b = extract_boundary("hlasm", SOURCE)
    calls = {(c["verb"], c["operand"], c["target"]) for c in b["calls"]}
    assert ("START TRANSID", "Z_EXP", None) in calls  # an HLASM symbol, not cut at `_`
    assert ("LINK", "PGMNAME", "ZECS003") in calls  # resolved through its DC
    assert not any(c["verb"] == "CALL" for c in b["calls"])  # the CALL macro is not COBOL's CALL
    (queue,) = b["cics_resources"]
    assert (queue["verb"], queue["kind"], queue["name"], queue["line"]) == ("WRITEQ", "QUEUE", "@tdq@", 10)
    (task,) = b["cics_tasks"]
    assert (task["verb"], task["operand"], task["line"]) == ("START", "Z_EXP", 3)
    uow = {(r["verb"], r["line"]): r for r in b["uow_handlers"]}
    assert uow[("ABEND", 5)]["condition"] == "Z001"
    assert uow[("VERIFY", 6)]["condition"] == "NORMAL"  # `OC EIBRESP,EIBRESP` tests for zero


def test_a_source_without_cics_is_untouched():
    plain = "PROG     CSECT\n         BR    14\n"
    assert cics_stream(plain) == plain
    b = extract_boundary("hlasm", plain)
    assert b["calls"] == b["cics_resources"] == b["cics_tasks"] == b["uow_handlers"] == []

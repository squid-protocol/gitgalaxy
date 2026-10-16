"""#5126 (register X64): a file control command sets EIBDS -- "the symbolic identifier of the last data set referred to
in a file control request" (IBM, EXEC interface block fields) -- on both translators. The stub's driver moves the FILE
operand in front of every file command; the det port does it in a program that reads EIBDS, and nowhere else."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "tools"))
import equivalence_cics as ec  # noqa: E402
from test_det_translate import _LenCics  # noqa: E402

from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402

# every file control form of a verb, FILE and its obsolete DATASET spelling
FORMS = [
    "READ {f}('KSDS') INTO(REC) RIDFLD(KEY) RESP(R)",
    "READ {f}(WS-FILE) INTO(REC) RIDFLD(KEY) UPDATE RESP(R)",
    "READNEXT {f}('KSDS') INTO(REC) RIDFLD(KEY) RESP(R)",
    "READPREV {f}('KSDS') INTO(REC) RIDFLD(KEY) RESP(R)",
    "STARTBR {f}('KSDS') RIDFLD(KEY) RESP(R)",
    "RESETBR {f}('KSDS') RIDFLD(KEY) RESP(R)",
    "ENDBR {f}('KSDS') RESP(R)",
    "WRITE {f}('KSDS') FROM(REC) RIDFLD(KEY) RESP(R)",
    "REWRITE {f}('KSDS') FROM(REC) RESP(R)",
    "DELETE {f}('KSDS') RIDFLD(KEY) RESP(R)",
    "UNLOCK {f}('KSDS') RESP(R)",
]


# the port does not translate these (refused by name, as before): no EIBDS statement is invented for them
REFUSED_BY_THE_PORT = ("RESETBR",)


def _first(text: str) -> str | None:
    """The stub's leading statement for a command, when it is the EIBDS move."""
    try:
        st = ec.translate_command(text, eibds=True)
    except ec.Unsupported:
        return None
    return st[0] if st and st[0].endswith(" TO EIBDS") else None


@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("spelling", ["FILE", "DATASET"])
def test_the_stub_names_the_file_before_every_file_control_command(form, spelling):
    text = form.format(f=spelling)
    operand = "WS-FILE" if "WS-FILE" in text else "'KSDS'"
    # (a form the stub refuses whole, e.g. RESETBR, is refused as before: no EIBDS statement is invented for it)
    first = _first(text)
    try:
        ec.translate_command(text)
    except ec.Unsupported:
        assert first is None
        return
    assert first == f"MOVE {operand} TO EIBDS"
    assert not any("EIBDS" in x for x in ec.translate_command(text))  # a program that never reads it keeps its text


@pytest.mark.parametrize(
    "text",
    [
        "WRITEQ TS QUEUE('QQ') FROM(REC)",
        "READQ TD QUEUE('QQQQ') INTO(REC)",
        "DELETE CONTAINER('C') CHANNEL('CH')",
        "ASSIGN USERID(WS-U)",
        "RETURN",
    ],
)
def test_no_other_command_touches_eibds(text):
    try:
        st = ec.translate_command(text, eibds=True)
    except ec.Unsupported:
        return
    assert not any("EIBDS" in s for s in st)


class _EibdsCics(_LenCics):
    def __init__(self, reads: bool):
        super().__init__()
        self.eibds_read = reads
        self.g.eib = lambda name: f"EIB({name})"
        self.text = lambda t: f"TEXT({t})"


@pytest.mark.parametrize("form", FORMS)
def test_the_det_port_names_the_file_in_a_program_that_reads_eibds(form):
    text = form.format(f="FILE")
    if form.startswith(REFUSED_BY_THE_PORT):
        with pytest.raises(C.CicsError):
            _EibdsCics(True).command(text, "")
        return
    out = _EibdsCics(True).command(text, "")
    operand = "WS-FILE" if "WS-FILE" in text else "'KSDS'"
    assert out[0] == f"Cobol.move(TEXT({operand}), EIB(EIBDS), CS);"


@pytest.mark.parametrize("form", FORMS)
def test_a_program_that_never_reads_eibds_keeps_its_port_text(form):
    text = form.format(f="FILE")
    if form.startswith(REFUSED_BY_THE_PORT):
        return
    quiet = _EibdsCics(False).command(text, "")
    assert not any("EIBDS" in x for x in quiet)
    assert _EibdsCics(True).command(text, "")[1:] == quiet


@pytest.mark.parametrize(
    ("text", "reads"),
    [
        ("MOVE EIBDS TO WS-DS", True),
        ("MOVE EIBDS(1:8) TO WS-DS", True),
        ("IF EIBDS = 'ACCT' DISPLAY 'X'", True),
        ("MOVE EIBDS-NICE TO WS-DS", False),
        ("MOVE WS-EIBDS TO WS-DS", False),
        ("DISPLAY 'EIBDS: '", False),
        ('DISPLAY "EIBDS"', False),
    ],
)
def test_the_program_scan_reads_whole_words_outside_literals(text, reads):
    assert C.reads_eibds([text]) is reads
    assert C.reads_eibds(["MOVE A TO B", text]) is reads


def test_a_stub_program_that_reads_eibds_is_translated_whole():
    prog = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DSREAD.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-RESP                PIC S9(8) COMP.
       01  WS-REC                 PIC X(20).
       01  WS-KEY                 PIC X(5).
       01  WS-DS                  PIC X(8).
       PROCEDURE DIVISION.
       MAIN-PARA.
           EXEC CICS READ FILE('ACCT') RIDFLD(WS-KEY)
                INTO(WS-REC) RESP(WS-RESP)
           END-EXEC.
           MOVE EIBDS TO WS-DS
           EXEC CICS RETURN END-EXEC.
"""
    text, _ = ec.translate(prog)
    lines = text.splitlines()
    at = next(i for i, ln in enumerate(lines) if ln.strip() == "MOVE 'ACCT' TO EIBDS")
    assert any("GGCREAD" in ln for ln in lines[at + 1 :])  # the file is named before the request runs
    assert all(len(ln) <= 72 for ln in lines)
    quiet, _ = ec.translate(prog.replace("MOVE EIBDS TO WS-DS", "MOVE SPACES TO WS-DS"))
    assert "EIBDS" not in quiet  # a program that never reads EIBDS keeps its driver text


@pytest.mark.parametrize(
    ("line", "reads"),
    [
        ("           MOVE EIBDS TO WS-DS", True),
        ("           MOVE EIBDS(1:8) TO WS-DS", True),
        ("           MOVE EIBDS-NICE TO WS-DS", False),
        ("           MOVE WS-EIBDS TO WS-DS", False),
        ("           DISPLAY 'EIBDS: '", False),
        ("      *    MOVE EIBDS TO WS-DS", False),
    ],
)
def test_the_stub_scan_reads_whole_words_outside_comments_and_literals(line, reads):
    assert ec.reads_eibds(["       PROCEDURE DIVISION.", line]) is reads


@pytest.mark.parametrize("reads", [True, False])
def test_the_translated_port_sets_eibds_only_in_a_program_that_reads_it(tmp_path, monkeypatch, reads):
    """program._translate sets the gate from the statements: the READ's own port needs repositories this program does
    not have, so its body is replaced by a comment while the wrapper (Cics.command) is the real one."""
    from gitgalaxy.tools.cobol_to_java.det import program as P

    monkeypatch.setattr(C.Cics, "_command", lambda self, text, ind: [f"{ind}// the command"])
    (tmp_path / "T1.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. T1.\n       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n       01  WS-DS                 PIC X(8) VALUE SPACES.\n"
        "       01  WS-F                  PIC X(8) VALUE 'ACCT'.\n       PROCEDURE DIVISION.\n"
        "           EXEC CICS READ FILE(WS-F) END-EXEC\n"
        + ("           MOVE EIBDS TO WS-DS\n" if reads else "           MOVE WS-F TO WS-DS\n")
        + "           EXEC CICS RETURN END-EXEC.\n",
        encoding="utf-8",
    )
    vsam = tmp_path / "proj/src/main/java/com/x/entity/vsam"
    vsam.mkdir(parents=True)
    (vsam / "CobolRecords.java").write_text("package com.x.entity.vsam; public class CobolRecords {}\n")
    stub = "package com.x.service;\nimport com.x.cics.CicsTask;\npublic class T1Service {\n" \
           "    public void runTask(CicsTask task) {}\n}\n"  # fmt: skip
    r = P.translate(tmp_path / "T1.cbl", [], stub, "com.x", {}, tmp_path / "proj")
    moves = [x for x in r.java.splitlines() if "Cobol.move(" in x and "EIBDS" in x]
    assert len(moves) == (2 if reads else 0), r.java  # the program's own MOVE EIBDS and the READ's
    assert ("// the command" in r.java) is True

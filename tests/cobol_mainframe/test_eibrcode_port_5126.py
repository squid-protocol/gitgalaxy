"""#5126 (register X64), slice 2 -- the port half of EIBRCODE: in a program that reads EIBRCODE, a file control command's
outcome puts the 6 bytes a planned condition states (faults.cfg's sixth column) into EIBRCODE, before a condition's jump,
as the stub's GGCRCOD does; unstated, the field is left as it was. The forge's CicsTask carries the column."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_det_translate import _LenCics  # noqa: E402

from gitgalaxy.tools.cobol_to_java.cics_task_faults import FAULTS_JAVA  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402

PUT = "if (RESP != 0 && task.rcode() != null) EIB(EIBRCODE).putRaw(task.rcode());"
FORMS = [
    "READ {f}('KSDS') INTO(REC) RIDFLD(KEY) RESP(R)",
    "READ {f}(WS-FILE) INTO(REC) RIDFLD(KEY) UPDATE RESP(R)",
    "READNEXT {f}('KSDS') INTO(REC) RIDFLD(KEY) RESP(R)",
    "READPREV {f}('KSDS') INTO(REC) RIDFLD(KEY) RESP(R)",
    "STARTBR {f}('KSDS') RIDFLD(KEY) RESP(R)",
    "ENDBR {f}('KSDS') RESP(R)",
    "WRITE {f}('KSDS') FROM(REC) RIDFLD(KEY) RESP(R)",
    "REWRITE {f}('KSDS') FROM(REC) RESP(R)",
    "DELETE {f}('KSDS') RIDFLD(KEY) RESP(R)",
    "DELETE {f}('KSDS') RESP(R)",
    "UNLOCK {f}('KSDS') RESP(R)",
]


class _RcodeCics(_LenCics):
    def __init__(self, reads: bool):
        super().__init__()
        self.eibrcode_read = reads
        self.g.eib = lambda name: f"EIB({name})"
        self.g.jump = lambda to: f"JUMP({to});"
        self.text = lambda t: f"TEXT({t})"

    outcome = C.Cics.outcome  # the real one: the test stubs above it only print OUTCOME(...)


def _puts(out: list[str]) -> list[str]:
    return [x for x in out if "putRaw(task.rcode())" in x]


@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("spelling", ["FILE", "DATASET"])
def test_a_reader_sets_eibrcode_right_after_the_eib_resp_fields(form, spelling):
    out = _RcodeCics(True).command(form.format(f=spelling), "")
    (put,) = _puts(out)
    at = out.index(put)
    assert "EIBRESP2" in out[at - 1]  # after the EIB's own fields, before RESP / a condition's jump
    assert put.startswith("if (") and put.endswith(".putRaw(task.rcode());") and "EIB(EIBRCODE)" in put
    assert [x for x in out if x != put] == _RcodeCics(False).command(form.format(f=spelling), "")


@pytest.mark.parametrize("form", FORMS)
def test_a_non_reader_keeps_its_port_text(form):
    assert not any("rcode" in x for x in _RcodeCics(False).command(form.format(f="FILE"), ""))


def test_a_condition_jump_comes_after_the_rcode():
    out = _RcodeCics(True).command("READ FILE('KSDS') INTO(REC) RIDFLD(KEY)", "")
    assert out.index(_puts(out)[0]) < next(i for i, x in enumerate(out) if "condition(" in x)


@pytest.mark.parametrize("text", ["RETURN", "SYNCPOINT", "GETMAIN SET(P) LENGTH(10)"])
def test_no_other_command_sets_it(text):
    try:
        out = _RcodeCics(True).command(text, "")
    except C.CicsError:
        return
    assert not _puts(out)
    assert not _RcodeCics(True).rcode_cmd


@pytest.mark.parametrize(
    ("text", "reads"),
    [
        ("MOVE EIBRCODE TO FE-RCODE", True),
        ("MOVE EIBRCODE(1:1) TO C", True),
        ("MOVE EIBRCODE-NICE TO C", False),
        ("MOVE WS-EIBRCODE TO C", False),
        ("DISPLAY 'EIBRCODE: '", False),
        ("MOVE EIBDS TO C", False),
    ],
)
def test_the_program_scan_reads_whole_words_outside_literals(text, reads):
    assert C.reads_eibrcode([text]) is reads
    assert C.reads_eibds([text]) is (text == "MOVE EIBDS TO C")


def test_the_forge_task_reads_the_sixth_column_only_for_a_condition():
    assert "private byte[] rcode;" in FAULTS_JAVA and "public byte[] rcode()" in FAULTS_JAVA
    assert "[0-9A-Fa-f]{12}" in FAULTS_JAVA  # a malformed column (or an ABEND code) is no rcode
    inj = FAULTS_JAVA[FAULTS_JAVA.index("private int[] injected(") :]
    assert inj.index("rcode = null;") < inj.index("faultPlan.isEmpty()")  # cleared by every lookup, as the stub's
    abend = inj.index("resp == -1 && f.length > 5")
    assert abend < inj.index("rcode = rcodeOf(f);") < inj.index("if (resp == 15)")  # set past the ABEND branch

"""#5079 (register X57): the cics-crucible runner's cobol-stub leg compares transient data.

The stub's WRITEQ-TD / READQ-TD / DELETEQ-TD event lines parse to SPEC 6.2 events, a scenario's `initial.td_queues` is laid
out as the stub's `td-<hex>/NNNNNN.bin`, the `final` state reads back the records not yet read (a deleted queue is
empty), and the CSD's `DEFINE TDQUEUE` lines reach the stub's tdqueues.cfg. The stub's own DELETEQ-TD line is checked
where a C compiler exists (test_cics_runtimes)."""

import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402
from test_cics_runtimes import _run_stub, _stub, needs_cc  # noqa: E402

_CSD = """* a comment
DEFINE PROGRAM(HCRQTD) GROUP(G) LANGUAGE(COBOL)
DEFINE TDQUEUE(HCQ1) GROUP(G) TYPE(INTRA) RECOVSTATUS(NO)
DEFINE TDQUEUE(HCX1) GROUP(G) TYPE(EXTRA) TYPEFILE(OUTPUT)
"""


def test_the_csd_parser_keeps_each_tdqueue_as_the_stub_reads_it():
    assert cc.parse_csd(_CSD)["tdqueues"] == {"HCQ1": "INTRA RECOVSTATUS=NO", "HCX1": "EXTRA TYPEFILE=OUTPUT"}
    assert "tdqueues" not in cc.parse_csd(
        "DEFINE PROGRAM(P) GROUP(G)\n"
    )  # none defined: the stub takes every queue as defined


def test_seeded_records_are_laid_out_and_read_back_first_in_first_out(tmp_path):
    runner.seed_td(tmp_path, {"HCQ1": ["SEEDED1", "TWO"]})
    d = tmp_path / ("td-" + b"HCQ1".hex().upper())
    assert sorted(p.name for p in d.iterdir()) == ["000001.bin", "000002.bin"]
    assert [bytes(x) for x in runner.read_td(tmp_path)["HCQ1"]] == [
        "SEEDED1".encode("cp037"),
        "TWO".encode("cp037"),
    ]
    assert runner.read_ts(tmp_path) == {}  # a TD directory is not a TS queue


def test_a_read_record_is_gone_and_a_deleted_queue_is_empty(tmp_path):
    runner.seed_td(tmp_path, {"HCQ1": ["ONE", "TWO"]})
    d = tmp_path / ("td-" + b"HCQ1".hex().upper())
    (d / "000001.bin").unlink()  # the stub's READQ TD removes the record and moves `head` on
    (d / "head").write_text("2\n", encoding="ascii")
    assert [bytes(x) for x in runner.read_td(tmp_path)["HCQ1"]] == ["TWO".encode("cp037")]
    (d / "000002.bin").unlink()
    (d / "head").write_text("3\n", encoding="ascii")
    assert runner.read_td(tmp_path) == {"HCQ1": []}
    assert runner.read_td(tmp_path / "missing") == {}


def test_the_stub_event_lines_parse_to_td_events(tmp_path):
    (tmp_path / "002.bin").write_bytes(b"ALPHA")
    (tmp_path / "003.bin").write_bytes(b"LONG")
    (tmp_path / "events.txt").write_text(
        "001 WRITEQ-TD pgm=HCRQTD queue=HCQ1 len=5 resp=0\n"
        "002 WRITEQ-TD pgm=HCRQTD queue=HCNQ len=5 resp=44\n"
        "003 READQ-TD pgm=HCRQTD queue=48435131 resp=22 len=8 copied=4\n"
        "004 READQ-TD pgm=HCRQTD queue=48435131 resp=23 len=-1 copied=0\n"
        "005 DELETEQ-TD pgm=HCRQTD queue=HCNQ resp=44\n",
        encoding="latin-1",
    )
    (tmp_path / "001.bin").write_bytes(b"ALPHA")
    ev = runner._cobol_events(tmp_path, "HCRQTD")
    assert [e["event"] for e in ev] == ["WRITEQ-TD", "WRITEQ-TD", "READQ-TD", "READQ-TD", "DELETEQ-TD"]
    assert (ev[0]["queue"], ev[0]["resp"], ev[0]["data"].data) == ("HCQ1", "NORMAL", b"ALPHA")
    assert (ev[1]["resp"], ev[1]["data"].data) == ("QIDERR", b"ALPHA")  # the record is logged whatever the answer
    assert (ev[2]["queue"], ev[2]["resp"], ev[2]["length"], ev[2]["data"].data) == ("HCQ1", "LENGERR", 8, b"LONG")
    assert (ev[3]["resp"], ev[3]["length"], ev[3]["data"]) == ("QZERO", None, None)
    assert (ev[4]["queue"], ev[4]["resp"]) == ("HCNQ", "QIDERR")


def test_a_side_without_td_support_is_unsupported_not_passing():
    log = {"tasks": [{"trigger": {"kind": "terminal"}, "events": [{"event": "DELETEQ-TD", "queue": "Q", "resp": "NORMAL"}]}],
           "final": {"td_queues": {"Q": []}}}  # fmt: skip
    java = runner.JAVA_CAPS
    assert not java.td_queues
    got = cc.blockers(log, java, {"initial": {"td_queues": {"Q": ["A"]}}})
    assert "CicsTask: TD queue seeding" in got and "CicsTask: TD queue final state" in got
    assert "stub: TD queue seeding" not in cc.blockers(log, runner.COBOL_CAPS, {"initial": {"td_queues": {"Q": ["A"]}}})
    assert not [b for b in cc.blockers(log, runner.COBOL_CAPS) if "TD" in b]


_CFG = "AAAA INTRA\nXXXX EXTRA\n"


@needs_cc
def test_the_stub_records_deleteq_td(tmp_path):
    from test_td_queue_5079 import _MAIN as main  # noqa: PLC0415

    (tmp_path / "tdqueues.cfg").write_text(_CFG, encoding="ascii")
    _run_stub(_stub(tmp_path, main), tmp_path, "W:AAAA:abc", "D:AAAA", "D:CCCC", "D:XXXX", "W:CCCC:zz")
    lines = (tmp_path / "out" / "events.txt").read_text().splitlines()
    assert lines == ["001 WRITEQ-TD pgm= queue=AAAA len=3 resp=0",
                     "002 DELETEQ-TD pgm= queue=AAAA resp=0",
                     "003 DELETEQ-TD pgm= queue=CCCC resp=44",
                     "004 DELETEQ-TD pgm= queue=XXXX resp=16",
                     "005 WRITEQ-TD pgm= queue=CCCC len=2 resp=44"]  # fmt: skip
    assert (tmp_path / "out" / "005.bin").read_bytes() == b"zz"  # a refused WRITEQ TD logs its record too

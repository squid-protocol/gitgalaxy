"""#5168 round 3 (register X61): SET / INQUIRE TDQUEUE OPENSTATUS and TYPE, translated by the stub's harness
(equivalence_cics.translate_command) and the det port (Cics.command); every other option is refused by name. The runtimes'
answers are tests/cics_crucible/test_td_queue_5168.py's."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "tools"))
import equivalence_cics as ec  # noqa: E402
from test_det_translate import _LenCics  # noqa: E402

from gitgalaxy.standards.cics.commands import COMMANDS as SPEC  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402


def test_the_commands_are_in_the_spec_and_keyed_by_their_form_word():
    assert SPEC["SET TDQUEUE"].status == "modelled" and SPEC["INQUIRE TDQUEUE"].status == "modelled"
    assert C.command_key(["SET"], {"TDQUEUE": "Q", "OPENSTATUS": "X"}) == "SET TDQUEUE"
    assert C.command_key(["INQUIRE"], {"TDQUEUE": "Q", "TYPE": "X"}) == "INQUIRE TDQUEUE"
    assert (
        C.command_key(["SET"], {"TERMINAL": "T", "UCTRANST": "X"}) == "SET TERMINAL"
    )  # the other forms keep their keys
    assert C.command_key(["INQUIRE"], {"PROGRAM": "P"}) == "INQUIRE PROGRAM"


def test_the_stub_translates_set_and_inquire():
    st = ec.translate_command("SET TDQUEUE(WS-Q) OPENSTATUS(DFHVALUE(CLOSED)) RESP(R) RESP2(R2)")
    assert st[:3] == ["MOVE WS-Q TO GG-QNAME", "MOVE DFHVALUE(CLOSED) TO GG-NUM", "CALL 'GGCSTDQ' USING GG-CICS"]
    both = ec.translate_command("INQUIRE TDQUEUE('AAAA') OPENSTATUS(WS-O) TYPE(WS-T) RESP(R)")
    assert "MOVE 'OPENSTATUS TYPE' TO GG-FLAGS" in both and "CALL 'GGCITDQ' USING GG-CICS" in both
    assert "    MOVE GG-NUM TO WS-O" in both and "    MOVE GG-LEN TO WS-T" in both
    only = ec.translate_command("INQUIRE TDQUEUE(WS-Q) TYPE(WS-T)")
    assert "MOVE 'TYPE' TO GG-FLAGS" in only and not any("GG-NUM TO" in x for x in only)


@pytest.mark.parametrize(
    ("text", "why"),
    [
        (
            "SET TDQUEUE(WS-Q) OPENSTATUS(DFHVALUE(OPEN)) ATITERMID(WS-T)",
            "only an extrapartition queue's open state and a queue's availability",
        ),
        (
            "SET TDQUEUE(WS-Q) ATIFACILITY(DFHVALUE(TERMINAL))",
            "only an extrapartition queue's open state and a queue's availability",
        ),
        (
            "INQUIRE TDQUEUE(WS-Q) ATIFACILITY(WS-L) OPENSTATUS(WS-O)",
            "only an extrapartition queue's open state and a queue's availability",
        ),
        ("INQUIRE TDQUEUE START", "only an extrapartition queue's open state and a queue's availability"),
        ("SET TDQUEUE(WS-Q)", "SET TDQUEUE without OPENSTATUS, ENABLESTATUS or TRIGGERLEVEL"),
        (
            "INQUIRE TDQUEUE(WS-Q) RESP(R)",
            "INQUIRE TDQUEUE without OPENSTATUS, TYPE, ENABLESTATUS, TRIGGERLEVEL, RECOVSTATUS or TRANSID",
        ),
    ],
)
def test_every_other_form_is_refused_by_name_on_both_translators(text, why):
    with pytest.raises(ec.Unsupported, match=why):
        ec.translate_command(text)
    with pytest.raises(C.CicsError, match=why):
        _LenCics().command(text, "")


def test_the_det_port_calls_the_task_and_stores_the_answers():
    st = _LenCics().command("SET TDQUEUE(WS-Q) OPENSTATUS(DFHVALUE(OPEN)) RESP(R)", "")
    assert st[0].startswith("int[] tdq") and ".setTdQueueOpenStatus(" in st[0] and "INT(DFHVALUE(OPEN))" in st[0]
    assert st[-1].startswith("OUTCOME(tdq") and "[0]" in st[-1] and "[1]" in st[-1]
    inq = _LenCics().command("INQUIRE TDQUEUE(WS-Q) OPENSTATUS(WS-O) TYPE(WS-T) RESP(R)", "")
    assert ".inquireTdQueue(" in inq[0] and inq[0].endswith("true, true);") and inq[1].endswith("[0] == 0) {")
    assert any("STORE(WS-O, BigDecimal.valueOf(tdq" in x and "[2])" in x for x in inq)
    assert any("STORE(WS-T, BigDecimal.valueOf(tdq" in x and "[3])" in x for x in inq)
    only = _LenCics().command("INQUIRE TDQUEUE(WS-Q) OPENSTATUS(WS-O)", "")
    assert only[0].endswith("true, false);") and not any("WS-T" in x for x in only)

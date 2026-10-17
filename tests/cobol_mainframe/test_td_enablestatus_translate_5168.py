"""#5168 round 5 (register X66): SET / INQUIRE TDQUEUE ENABLESTATUS, translated by the stub's harness
(equivalence_cics.translate_command) and the det port (Cics.command). The runtimes' answers are
tests/cics_crucible/test_td_queue_5168.py's."""

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


def test_the_spec_models_enablestatus():
    assert "ENABLESTATUS" in SPEC["SET TDQUEUE"].options and "ENABLESTATUS" in SPEC["INQUIRE TDQUEUE"].options
    assert C.command_key(["SET"], {"TDQUEUE": "Q", "ENABLESTATUS": "X"}) == "SET TDQUEUE"
    for key in ("READQ TD", "WRITEQ TD", "DELETEQ TD"):
        assert any(o.condition == "DISABLED" for o in SPEC[key].outcomes), key


def test_the_stub_translates_set_and_inquire():
    st = ec.translate_command("SET TDQUEUE(WS-Q) ENABLESTATUS(DFHVALUE(DISABLED)) RESP(R) RESP2(R2)")
    assert st[:3] == ["MOVE WS-Q TO GG-QNAME", "MOVE DFHVALUE(DISABLED) TO GG-NUM", "CALL 'GGCSTDE' USING GG-CICS"]
    inq = ec.translate_command("INQUIRE TDQUEUE('AAAA') ENABLESTATUS(WS-E) RESP(R)")
    assert "MOVE 'ENABLESTATUS' TO GG-FLAGS" in inq and "CALL 'GGCITDQ' USING GG-CICS" in inq
    assert any("GG-ITEM TO WS-E" in x for x in inq)


def test_both_options_together_are_refused_by_name_on_both_translators():
    text = "SET TDQUEUE(WS-Q) OPENSTATUS(DFHVALUE(OPEN)) ENABLESTATUS(DFHVALUE(ENABLED))"
    with pytest.raises(ec.Unsupported, match="OPENSTATUS and ENABLESTATUS together"):
        ec.translate_command(text)
    with pytest.raises(C.CicsError, match="OPENSTATUS and ENABLESTATUS together"):
        _LenCics().command(text, "")


def test_the_det_port_calls_the_task_and_stores_the_answers():
    st = _LenCics().command("SET TDQUEUE(WS-Q) ENABLESTATUS(DFHVALUE(DISABLED)) RESP(R)", "")
    assert ".setTdQueueEnableStatus(" in st[0] and "INT(DFHVALUE(DISABLED))" in st[0]
    inq = _LenCics().command("INQUIRE TDQUEUE(WS-Q) ENABLESTATUS(WS-E) RESP(R)", "")
    assert ".inquireTdQueue(" in inq[0] and any("STORE(WS-E, BigDecimal.valueOf(tdq" in x and "[4])" in x for x in inq)

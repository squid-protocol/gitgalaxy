"""#6271 (register X71): RESP faults on SEND MAP, RECEIVE MAP, RETURN, SYNCPOINT and SYNCPOINT ROLLBACK. A scenario plans
`{"cmd", "map", "nth", "resp", "resp2"}`; both runtimes answer that condition and do nothing else. The end-to-end proof is
CBSA BNKMENU's `option-*-return-invreq` / `first-entry-send-map-invmpsz` and DBCRFUN's
`proctran-insert-fails-rollback-invreq` (det_port.py run); these are the unit pieces: the plan's accept / refuse table, and
the stub, the Java task and the translator all naming the same hook.

IBM (CICS TS 6.x, the Conditions of SEND MAP, RECEIVE MAP, RETURN, SYNCPOINT, SYNCPOINT ROLLBACK)."""

import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
import equivalence_cics as ec  # noqa: E402

REPO = TESTS.parent


def _lines(**f):
    return ec.fault_lines({"name": "s", "faults": [f]})


ACCEPTED = [
    ({"cmd": "SEND-MAP", "map": "M1", "resp": "INVMPSZ"}, "SEND-MAP M1 1 38 0"),
    ({"cmd": "SEND-MAP", "map": "M1", "resp": "TSIOERR", "nth": 2}, "SEND-MAP M1 2 35 0"),
    ({"cmd": "SEND-MAP", "map": "M1", "resp": "INVREQ"}, "SEND-MAP M1 1 16 200"),
    ({"cmd": "RECEIVE-MAP", "map": "M1", "resp": "INVMPSZ"}, "RECEIVE-MAP M1 1 38 0"),
    ({"cmd": "RECEIVE-MAP", "map": "M1", "resp": "INVREQ"}, "RECEIVE-MAP M1 1 16 0"),
    ({"cmd": "RETURN", "resp": "INVREQ", "resp2": 4}, "RETURN - 1 16 4"),
    ({"cmd": "RETURN", "resp": "LENGERR", "resp2": 26}, "RETURN - 1 22 26"),
    ({"cmd": "SYNCPOINT", "resp": "INVREQ"}, "SYNCPOINT - 1 16 200"),
    ({"cmd": "ROLLBACK", "resp": "INVREQ", "resp2": 200}, "ROLLBACK - 1 16 200"),
    # #6271 (X72): DELAY -- EXPIRED (no RESP2) and INVREQ RESP2 4 / 5 / 6 / 22
    ({"cmd": "DELAY", "resp": "EXPIRED"}, "DELAY - 1 31 0"),
    ({"cmd": "DELAY", "resp": "INVREQ", "resp2": 4}, "DELAY - 1 16 4"),
    ({"cmd": "DELAY", "resp": "INVREQ", "resp2": 5}, "DELAY - 1 16 5"),
    ({"cmd": "DELAY", "resp": "INVREQ", "resp2": 6, "nth": 2}, "DELAY - 2 16 6"),
    ({"cmd": "DELAY", "resp": "INVREQ", "resp2": 22, "nth": "*"}, "DELAY - * 16 22"),
]


@pytest.mark.parametrize(("fault", "line"), ACCEPTED)
def test_a_documented_condition_is_planned_with_ibms_resp2(fault, line):
    assert _lines(**fault) == [line]


REFUSED = [
    {"cmd": "SEND-MAP", "map": "M1", "resp": "INVMPSZ", "resp2": 1},  # IBM states no RESP2
    {"cmd": "SEND-MAP", "map": "M1", "resp": "INVREQ", "resp2": 5},  # not IBM's 200
    {"cmd": "SEND-MAP", "map": "M1", "resp": "OVERFLOW"},
    {"cmd": "SEND-MAP", "map": "M1", "resp": "WRBRK"},
    {"cmd": "RECEIVE-MAP", "map": "M1", "resp": "MAPFAIL"},  # natural, not planned
    {"cmd": "RECEIVE-MAP", "map": "M1", "resp": "EOC"},
    {"cmd": "RECEIVE-MAP", "map": "M1", "resp": "INVREQ", "resp2": 1},
    {"cmd": "RETURN", "resp": "INVREQ"},  # four RESP2 values: the plan names one
    {"cmd": "RETURN", "resp": "INVREQ", "resp2": 8},
    {"cmd": "RETURN", "resp": "LENGERR", "resp2": 12},
    {"cmd": "RETURN", "resp": "CHANNELERR", "resp2": 1},
    {"cmd": "SYNCPOINT", "resp": "ROLLEDBACK"},
    {"cmd": "SYNCPOINT", "resp": "INVREQ", "resp2": 1},
    {"cmd": "ROLLBACK", "resp": "LENGERR"},
    {"cmd": "DELAY", "resp": "INVREQ"},  # four RESP2 values: the plan names one
    {"cmd": "DELAY", "resp": "INVREQ", "resp2": 7},
    {"cmd": "DELAY", "resp": "EXPIRED", "resp2": 1},  # IBM states no RESP2
    {"cmd": "DELAY", "resp": "NORMAL", "resp2": 23},  # cancelled by another task: needs a second task, refused
    {"cmd": "DELAY", "resp": "SYSIDERR"},
    {"cmd": "DELAY", "resp": "ISCINVREQ"},
]


@pytest.mark.parametrize("fault", REFUSED)
def test_every_other_condition_is_refused(fault):
    with pytest.raises(ec.Unsupported):
        _lines(**fault)


def test_the_refusal_names_register_x71():
    with pytest.raises(ec.Unsupported, match="X71"):
        _lines(cmd="SYNCPOINT", resp="INVREQ", resp2=1)
    with pytest.raises(ec.Unsupported, match="X71"):
        _lines(cmd="RETURN", resp="INVREQ")
    with pytest.raises(ec.Unsupported, match="X72"):
        _lines(cmd="DELAY", resp="INVREQ", resp2=7)


def test_plans_sit_beside_the_file_command_plans():
    sc = {
        "name": "s",
        "faults": [{"cmd": "READ", "file": "F", "resp": "NOTFND"}, {"cmd": "ROLLBACK", "resp": "INVREQ"}],
    }
    assert ec.fault_lines(sc) == ["READ F 1 13 80", "ROLLBACK - 1 16 200"]


def test_a_command_key_fits_the_stubs_parse_buffer():
    # the stub reads the command with %15s into char[16]: a longer key never matches
    assert all(len(c) <= 15 for c in ec.UI_FAULT_CONDITIONS)


def test_the_stub_the_task_and_the_translator_read_the_same_plan():
    stub = (REPO / "tests/equivalence/cics/ggcics.c").read_text(encoding="utf-8")
    task = (REPO / "gitgalaxy/tools/cobol_to_java/cobol_to_java_transaction_forge.py").read_text(encoding="utf-8")
    faults = (REPO / "gitgalaxy/tools/cobol_to_java/cics_task_faults.py").read_text(encoding="utf-8")  # #5274
    cics = (REPO / "gitgalaxy/tools/cobol_to_java/det/cics.py").read_text(encoding="utf-8")
    for cmd in ("SEND-MAP", "RECEIVE-MAP", "RETURN", "SYNCPOINT", "ROLLBACK"):
        assert f'"{cmd}"' in stub or cmd in ("SYNCPOINT", "ROLLBACK"), cmd
    assert 'rollback ? "ROLLBACK" : "SYNCPOINT"' in stub
    assert "public int[] planned(String cmd, String name)" in faults
    assert 'root().injected("RETURN", "-")' in task
    for cmd in ("SEND-MAP", "RECEIVE-MAP"):
        assert f'task.planned("{cmd}", {{G_jstr(m)}})' in cics.replace('\\"', '"')
    assert 'task.planned({G_jstr("ROLLBACK" if back else "SYNCPOINT")}' in cics


def test_the_delay_stub_and_translator_read_the_same_plan():
    stub = (REPO / "tests/equivalence/cics/ggcics_taskcontrol.c").read_text(encoding="utf-8")
    det = (REPO / "gitgalaxy/tools/cobol_to_java/det/cics_taskcontrol.py").read_text(encoding="utf-8")
    body = stub[stub.index("int GGCDLAY") :]
    # planned before the POST is released and before any child is dispatched: a failed DELAY does nothing else
    assert body.index('injected("DELAY", "-"') < body.index("post_release()") < body.index("dispatch_children()")
    assert 'task.planned("DELAY", "-")' in det
    assert "if ({pl}[0] == 0) task.delay(" in det

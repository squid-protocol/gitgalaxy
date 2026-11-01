"""#6271 (register X71): RESP faults on SEND MAP, RECEIVE MAP, RETURN, SYNCPOINT and SYNCPOINT ROLLBACK. A scenario plans
`{"cmd", "map", "nth", "resp", "resp2"}`; both runtimes answer that condition and do nothing else. The end-to-end proof is
CBSA BNKMENU's `option-*-return-invreq` / `first-entry-send-map-invmpsz` and DBCRFUN's
`proctran-insert-fails-rollback-invreq` (det_port.py run); these are the unit pieces: the plan's accept / refuse table, and
the stub, the Java task and the translator all naming the same hook.

IBM (CICS TS 6.x, the Conditions of SEND MAP, RECEIVE MAP, RETURN, SYNCPOINT, SYNCPOINT ROLLBACK)."""

import json
import os
import re
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
import equivalence_cics as ec  # noqa: E402
import ggcics_source  # noqa: E402
from gitgalaxy.core.source_text import read_source  # noqa: E402

REPO = TESTS.parent


def _det_cics_source() -> str:
    """det/cics.py and its command families (#5274)."""
    return "\n".join(
        p.read_text(encoding="utf-8") for p in sorted((REPO / "gitgalaxy/tools/cobol_to_java/det").glob("cics*.py"))
    )


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
    # #6882 (X26): SET / INQUIRE TERMINAL
    ({"cmd": "SET-TERMINAL", "resp": "INVREQ"}, "SET-TERMINAL - 1 16 43"),
    ({"cmd": "SET-TERMINAL", "resp": "TERMIDERR", "resp2": 23, "nth": 2}, "SET-TERMINAL - 2 11 23"),
    ({"cmd": "INQ-TERMINAL", "resp": "TERMIDERR"}, "INQ-TERMINAL - 1 11 1"),
    # #6882 slice 2: RUN TRANSID / FETCH ANY
    ({"cmd": "RUN-TRANSID", "resp": "TRANSIDERR"}, "RUN-TRANSID - 1 28 1"),
    ({"cmd": "FETCH-ANY", "resp": "NOTFINISHED", "resp2": 52}, "FETCH-ANY - 1 113 52"),
    ({"cmd": "FETCH-ANY", "resp": "NOTFINISHED", "resp2": 53, "nth": 2}, "FETCH-ANY - 2 113 53"),
    ({"cmd": "FETCH-ANY", "resp": "NOTFND"}, "FETCH-ANY - 1 13 1"),
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
    {"cmd": "SET-TERMINAL", "resp": "INVREQ", "resp2": 44},  # IBM's INVREQ RESP2 is 43
    {"cmd": "SET-TERMINAL", "resp": "NOTAUTH"},
    {"cmd": "SET-TERMINAL", "resp": "TERMIDERR", "resp2": 1},  # 1 is INQUIRE's
    {"cmd": "INQ-TERMINAL", "resp": "INVREQ"},
    {"cmd": "RUN-TRANSID", "resp": "INVREQ"},
    {"cmd": "RUN-TRANSID", "resp": "TRANSIDERR", "resp2": 2},
    {"cmd": "FETCH-ANY", "resp": "NOTFINISHED", "resp2": 54},
    {"cmd": "FETCH-ANY", "resp": "NOTFND", "resp2": 2},
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
    stub = ggcics_source.stub_source()
    task = (REPO / "gitgalaxy/tools/cobol_to_java/cobol_to_java_transaction_forge.py").read_text(encoding="utf-8")
    faults = (REPO / "gitgalaxy/tools/cobol_to_java/cics_task_faults.py").read_text(encoding="utf-8")  # #5274
    cics = _det_cics_source()
    for cmd in ("SEND-MAP", "RECEIVE-MAP", "RETURN", "SYNCPOINT", "ROLLBACK"):
        assert f'"{cmd}"' in stub or cmd in ("SYNCPOINT", "ROLLBACK"), cmd
    assert 'rollback ? "ROLLBACK" : "SYNCPOINT"' in stub
    assert "public int[] planned(String cmd, String name)" in faults
    assert 'root().injected("RETURN", "-")' in task
    for cmd in ("SEND-MAP", "RECEIVE-MAP"):
        assert f'task.planned("{cmd}", {{jstr(m)}})' in cics.replace('\\"', '"')
    assert 'task.planned({jstr("ROLLBACK" if back else "SYNCPOINT")}' in cics


def test_the_delay_stub_and_translator_read_the_same_plan():
    stub = (REPO / "tests/equivalence/cics/ggcics_taskcontrol.c").read_text(encoding="utf-8")
    det = (REPO / "gitgalaxy/tools/cobol_to_java/det/cics_taskcontrol.py").read_text(encoding="utf-8")
    body = stub[stub.index("int GGCDLAY") :]
    # planned before the POST is released and before any child is dispatched: a failed DELAY does nothing else
    assert body.index('injected("DELAY", "-"') < body.index("post_release()") < body.index("dispatch_children()")
    assert 'task.planned("DELAY", "-")' in det
    assert "if ({pl}[0] == 0) task.delay(" in det


@pytest.mark.parametrize(
    "command",
    [
        "DELAY INTERVAL(5)",
        "DELAY FOR SECONDS(3)",
        "DELAY TIME(120000)",
        "DELAY",
        "SEND TEXT FROM(WS-T) LENGTH(10)",
        "SEND TEXT FROM(WS-T) LENGTH(10) ERASE",
    ],
)
def test_an_unhandled_planned_fault_takes_the_default_action(command):
    # #5862 (P121): a DELAY / SEND TEXT that codes no RESP hands its condition to GGCCOND (HANDLE CONDITION, ERROR, else the
    # AEIx abend, as the det port does); one that codes RESP or NOHANDLE tests its own
    plain = ec.translate_command(command)
    assert "    CALL 'GGCCOND' USING GG-CICS" in plain
    assert not any("GGCCOND" in x for x in ec.translate_command(command + " RESP(R) RESP2(R2)"))
    assert not any("GGCCOND" in x for x in ec.translate_command(command + " NOHANDLE"))


def test_expired_is_ignored_by_default_in_the_stub_and_the_det_runtime():
    # #5862 (X72): "EXPIRED's default action when unhandled is to ignore it", as EOC's: GGCCOND and DetCics agree
    cond = (REPO / "tests/equivalence/cics/ggcics_conditions.c").read_text(encoding="utf-8")
    body = cond[cond.index("int GGCCOND") :]
    assert "cond == EOC || cond == DFHRESP_EXPIRED" in body[: body.index("abend(c,")]
    rt = (REPO / "gitgalaxy/tools/cobol_to_java/det/cobolrt/cics/DetCics.java").read_text(encoding="utf-8")
    ign = rt[rt.index("ignoredByDefault") :]
    assert '"EXPIRED".equals(condition)' in ign[: ign.index("}")]


def test_a_plain_return_transid_that_codes_resp_reads_the_return_plan():
    # #6271 (X71): the stub, the Java task and the translator all let a planned RETURN fail the plain form -- only when
    # the program codes RESP (GG-ITEM 2); a plain RETURN with no RESP never consults the plan
    stub = ggcics_source.stub_source()
    task = (REPO / "gitgalaxy/tools/cobol_to_java/cobol_to_java_transaction_forge.py").read_text(encoding="utf-8")
    cics = _det_cics_source()
    body = stub[stub.index("int GGCRETN") : stub.index("int GGCRETI")]
    assert 'c->item == 2 && lvl == 0 && injected("RETURN", "-"' in body
    assert body.index("injected(") < body.index("return_event(transid")
    assert "public int[] returnTransidResp(String transid, Object commarea, Integer length)" in task
    assert 'level == 1 ? root().injected("RETURN", "-") : null' in task
    assert 'self._return_call("returnTransidResp"' in cics


def test_the_driver_lets_only_a_resp_coded_plain_return_fail():
    body = "RETURN TRANSID('OMEN') COMMAREA(CA) LENGTH(1)"
    plain = ec.translate_command(body)
    tested = ec.translate_command(body + " RESP(R) RESP2(R2)")
    assert plain[-1] == "GOBACK" and "MOVE 2 TO GG-ITEM" not in plain
    assert "MOVE 2 TO GG-ITEM" in tested and "MOVE GG-RESP TO R" in tested and tested[-1] != "GOBACK"
    assert "IF GG-RESP = 0" in tested


# #6271 (X71): SEND TEXT (IBM, the Conditions of -send-text): TSIOERR 35; INVREQ 16 (RESP2 200, the only RESP2 it lists); LENGERR 22
# (no RESP2). Nameless (`-`), like RETURN.
TEXT_ACCEPTED = [
    ({"cmd": "SEND-TEXT", "resp": "TSIOERR"}, "SEND-TEXT - 1 35 0"),
    ({"cmd": "SEND-TEXT", "resp": "INVREQ"}, "SEND-TEXT - 1 16 200"),
    ({"cmd": "SEND-TEXT", "resp": "INVREQ", "resp2": 200, "nth": 2}, "SEND-TEXT - 2 16 200"),
    ({"cmd": "SEND-TEXT", "resp": "LENGERR", "nth": "*"}, "SEND-TEXT - * 22 0"),
]


@pytest.mark.parametrize(("fault", "line"), TEXT_ACCEPTED)
def test_send_text_conditions_are_planned(fault, line):
    assert _lines(**fault) == [line]


TEXT_REFUSED = [
    {"cmd": "SEND-TEXT", "resp": "TSIOERR", "resp2": 1},  # IBM states no RESP2
    {"cmd": "SEND-TEXT", "resp": "INVREQ", "resp2": 5},  # not IBM's 200
    {"cmd": "SEND-TEXT", "resp": "LENGERR", "resp2": 1},
    *({"cmd": "SEND-TEXT", "resp": r} for r in ("IGREQCD", "IGREQID", "INVLDC", "INVPARTN", "RETPAGE", "WRBRK")),
    {"cmd": "SEND-CONTROL", "resp": "TSIOERR"},  # a sibling gap: not planned yet
]


@pytest.mark.parametrize("fault", TEXT_REFUSED)
def test_every_other_send_text_condition_is_refused(fault):
    with pytest.raises(ec.Unsupported):
        _lines(**fault)


def test_the_send_text_refusal_names_register_x71():
    with pytest.raises(ec.Unsupported, match="X71"):
        _lines(cmd="SEND-TEXT", resp="TSIOERR", resp2=1)


def test_the_send_text_stub_and_translator_read_the_same_plan():
    stub = ggcics_source.stub_source()
    cics = _det_cics_source()
    assert 'injected("SEND-TEXT", "-"' in stub
    assert 'task.planned("SEND-TEXT", "-")' in cics
    assert "if ({pl}[0] == 0) task.sendText(" in cics
    # CONVERSE writes its data without consulting a SEND TEXT plan
    assert "send_text_event(c, from, fromlen)" in stub


# the CBSA terminal programs whose SEND TEXT (STM010, PF12) and plain RETURN TRANSID (A010) failure arms a committed
# scenario reaches by a planned fault, not a stated "no fault can be injected" (#6271); BNKMENU's plain RETURN was first
_CBSA_SEND_TEXT = ("bnkmenu", "bnk1cac", "bnk1cca", "bnk1ccs", "bnk1cra", "bnk1dac", "bnk1tfn", "bnk1uac")
_CBSA_PLAIN_RETURN = ("bnkmenu", *_CBSA_SEND_TEXT[1:])


def _case_plans(prog, cmd):
    case = json.loads((REPO / f"tests/equivalence/cbsa-{prog}/case.json").read_text(encoding="utf-8"))
    return [s for s in case["scenarios"] if any(f.get("cmd") == cmd for f in s.get("faults", []))]


@pytest.mark.parametrize("prog", _CBSA_SEND_TEXT)
def test_a_committed_scenario_fails_the_termination_send_text(prog):
    (sc,) = _case_plans(prog, "SEND-TEXT")
    assert sc["aid"] == "DFHPF12"
    assert ec.fault_lines({"name": sc["name"], "faults": sc["faults"]}) == ["SEND-TEXT - 1 35 0"]


@pytest.mark.parametrize("prog", _CBSA_PLAIN_RETURN[1:])
def test_a_committed_scenario_fails_the_plain_return_transid(prog):
    (sc,) = _case_plans(prog, "RETURN")
    assert ec.fault_lines({"name": sc["name"], "faults": sc["faults"]}) == ["RETURN - 1 16 4"]


@pytest.mark.parametrize("prog", _CBSA_SEND_TEXT)
def test_no_stale_cannot_inject_entry_remains_for_the_reached_arms(prog):
    path = REPO / f"tests/equivalence/infeasible_outcomes/cbsa-{prog}.json"
    for e in json.loads(path.read_text(encoding="utf-8"))["entries"]:
        text = e["reason"]
        if e["unit"] == "STM010":
            assert "SEND TEXT" not in text, e
        if e["unit"] == "A010" and prog != "bnkmenu":
            # only the arm a successful RETURN would take stays stated infeasible
            assert e["outcome"] == "false" or "RETURN" not in text, e


def test_send_control_is_refused_by_name():
    with pytest.raises(ec.Unsupported, match="X71"):
        _lines(cmd="SEND-CONTROL", resp="TSIOERR")


def test_no_burned_cbsa_send_control_codes_resp():
    # the refusal's premise: a failure of a RESP-less SEND CONTROL would abend, which IBM does not describe
    src = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    cobol = Path(src) / "cics-banking-sample-application-cbsa/src/base/cobol_src" if src else None
    if cobol is None or not cobol.is_dir():
        pytest.skip("CBSA corpus not available")
    found = 0
    for f in sorted(cobol.glob("*.cbl")):
        text = read_source(f).text
        for m in re.finditer(r"EXEC\s+CICS\s+SEND\s+CONTROL(.*?)END-EXEC", text, re.S | re.I):
            found += 1
            assert "RESP" not in m.group(1).upper(), f.name
    assert found


def test_the_terminal_stub_and_translator_read_the_same_plan():
    stub = ggcics_source.stub_source()
    det = _det_cics_source()
    for cmd, fn in (("SET-TERMINAL", "int GGCSETT"), ("INQ-TERMINAL", "int GGCINQT")):
        body = stub[stub.index(fn) :]
        # planned before the terminal is looked up: a failed command changes nothing
        assert body.index(f'injected("{cmd}", "-"') < body.index("uctranst_terminal(c")
        assert f'task.planned(\\"{cmd}\\", \\"-\\"); if ({{r}}[0] == 0)' in det
    with pytest.raises(ec.Unsupported, match="X26"):
        _lines(cmd="SET-TERMINAL", resp="INVREQ", resp2=44)


def test_the_run_and_fetch_stub_and_translator_read_the_same_plan():
    stub = (REPO / "tests/equivalence/cics/ggcics_taskcontrol.c").read_text(encoding="utf-8")
    det = (REPO / "gitgalaxy/tools/cobol_to_java/cics_task_taskcontrol.py").read_text(encoding="utf-8")
    for cmd in ("RUN-TRANSID", "FETCH-ANY"):
        assert f'injected("{cmd}", "-"' in stub.replace('("', '("')
        assert f'task.injected("{cmd}", "-")' in det

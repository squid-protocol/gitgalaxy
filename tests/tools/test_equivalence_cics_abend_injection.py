"""#6271 (register X70): abend injection on a file control command. A scenario plans `{"cmd", "file", "nth", "resp":
"ABEND", "abcode": "AFCR|AFCS|AFCT"}`; both runtimes abend the task at that command (cause system), the nearest HANDLE
ABEND exit gets control, and the command answers NORMAL. The end-to-end proof is carddemo-cardupdate's
`search-card-read-rls-abend-afcr` / `pf5-rewrite-rls-abend-afct` (det_port.py run); these are the unit pieces:
the plan's accept / refuse table, the COBOL driver's exit check and the det translator's post-command check.

IBM (CICS TS 6.x, transaction abend codes AFCR / AFCS / AFCT): the VSAM RLS file control abends; no RESP condition."""

import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(TESTS / "cobol_mainframe"))
import equivalence_cics as ec  # noqa: E402
from test_det_translate import _RbaCics  # noqa: E402

_PLAN = {"cmd": "READ", "file": "ACCTDAT", "resp": "ABEND", "abcode": "AFCR"}


def _faults(**kw):
    return {"name": "s", "faults": [{**_PLAN, **kw}]}


@pytest.mark.parametrize("cmd", ["READ", "READNEXT", "READPREV", "STARTBR", "ENDBR", "WRITE", "REWRITE", "DELETE"])
@pytest.mark.parametrize("code", ["AFCR", "AFCS", "AFCT", "AFCC"])
def test_an_rls_abend_is_planned_on_a_file_command(cmd, code):
    assert ec.fault_lines(_faults(cmd=cmd, abcode=code)) == [f"{cmd} ACCTDAT 1 -1 0 {code}"]


def test_nth_defaults_to_the_first_and_may_be_every_one():
    assert ec.fault_lines(_faults(nth=2)) == ["READ ACCTDAT 2 -1 0 AFCR"]
    assert ec.fault_lines(_faults(nth="*")) == ["READ ACCTDAT * -1 0 AFCR"]


def test_an_abend_plan_sits_beside_a_condition_plan():
    sc = {"name": "s", "faults": [{"cmd": "READ", "file": "CUSTDAT", "resp": "NOTFND"}, _PLAN]}
    assert ec.fault_lines(sc) == ["READ CUSTDAT 1 13 80", "READ ACCTDAT 1 -1 0 AFCR"]


@pytest.mark.parametrize(
    "bad",
    [
        {"abcode": "ASRA"},  # a code no source gives for a file command
        {"abcode": None},
        {"abcode": "afcr"},
        {"cmd": "SEND"},  # not a file control command
        {"resp2": 100},  # IBM states none
        {"file": None},  # names nothing
    ],
)
def test_every_other_abend_plan_is_refused(bad):
    with pytest.raises(ec.Unsupported):
        ec.fault_lines(_faults(**bad))


def test_the_driver_takes_the_exit_after_a_file_command_only_when_the_program_has_labels():
    plain = ec.translate_command("READ FILE('ACCTDAT') INTO(REC) RIDFLD(K) RESP(R)")
    assert "IF GG-GOTO < 0" not in plain
    lines = ec.translate_command("READ FILE('ACCTDAT') INTO(REC) RIDFLD(K) RESP(R)", labels=["ABEND-ROUTINE"])
    assert lines[0] == "MOVE 0 TO GG-GOTO"  # a stale exit from an earlier command is spent
    assert lines[-6:] == [
        "GO TO",
        "    ABEND-ROUTINE",
        "    DEPENDING ON GG-GOTO",
        "IF GG-GOTO < 0",
        "    GOBACK",
        "END-IF",
    ]


def test_the_driver_leaves_an_unlock_alone():
    lines = ec.translate_command("UNLOCK FILE('ACCTDAT')", labels=["ABEND-ROUTINE"])
    assert "IF GG-GOTO < 0" not in lines


class _AbendCics(_RbaCics):
    SIZES = {**_RbaCics.SIZES}

    def __init__(self, handle_abend):
        super().__init__()
        self.handle_abend = handle_abend
        self.g.jump = lambda target: f"return GOTO | {target};"
        self.g.tmpname = lambda p: f"{p}7"


def test_a_det_port_checks_for_the_exit_after_a_file_command_in_a_handle_abend_program():
    cmd = "STARTBR DATASET('EPSMORTF') RIDFLD(RID) RBA EQUAL RESP(R)"
    plain = _AbendCics(False).command(cmd, "")
    assert not any("abendExit" in ln for ln in plain)
    lines = _AbendCics(True).command(cmd, "")
    assert lines[-3:] == [
        "String exit7 = task.abendExit();",
        "if (exit7 != null) return GOTO | paragraph(exit7);",
        "if (task.ended()) throw abended();",
    ]
    assert lines[: len(plain)] == plain  # the command itself is as before


def test_a_det_port_checks_only_file_commands():
    lines = _AbendCics(True).command("ASKTIME", "")
    assert not any("abendExit" in ln for ln in lines)


@pytest.mark.parametrize("code", ["AFCR", "AFCS", "AFCT", "AFCC"])
def test_a_link_abend_is_planned_on_the_program_it_names(code):
    plan = {"cmd": "LINK", "program": "INQCUST", "resp": "ABEND", "abcode": code}
    assert ec.fault_lines({"name": "s", "faults": [plan]}) == [f"LINK INQCUST 1 -1 0 {code}"]


@pytest.mark.parametrize(
    "plan",
    [
        {"cmd": "LINK", "program": "INQCUST", "abcode": "ASRA"},
        {"cmd": "LINK", "program": "INQCUST", "abcode": "AFCR", "resp2": 4},
        {"cmd": "LINK", "abcode": "AFCR"},
        {"cmd": "ASKTIME", "file": "X", "abcode": "AFCR"},
    ],
)
def test_a_link_abend_refuses_other_codes_a_resp2_no_name_and_other_commands(plan):
    with pytest.raises(ec.Unsupported):
        ec.fault_lines({"name": "s", "faults": [{"resp": "ABEND", **plan}]})


def test_a_link_with_an_abend_exit_goes_to_it_before_the_callee_runs():
    lines = ec.translate_command("LINK PROGRAM('INQCUST') COMMAREA(DFHCOMMAREA) LENGTH(10)", labels=["ABEND-ROUTINE"])
    text = "\n".join(lines)
    assert text.index("GGCLINK") < text.index("DEPENDING ON GG-GOTO") < text.index("GGCRUN")


def test_a_browse_that_abended_delivers_no_record_to_the_port():
    """The injected abend answers a READNEXT / READPREV with RESP 0 and no key: `normal()` must be false, or the port reads
    `key()` (null) before it checks the abend exit (an NPE on INQCUST's READPREV, #6271)."""
    from gitgalaxy.tools.cobol_to_java.cics_task_filecontrol import FILECONTROL_JAVA  # noqa: PLC0415

    assert "return key != null && (resp == 0 || resp == 15);" in FILECONTROL_JAVA
    assert "return record != null && (resp == 0 || resp == 15);" in FILECONTROL_JAVA


def test_inqcust_plans_an_rls_abend_on_the_read_the_startbr_and_the_readprev():
    import json  # noqa: PLC0415

    case = json.loads((TESTS / "equivalence" / "cbsa-inqcust" / "case.json").read_text(encoding="utf-8"))
    planned = {
        (f["cmd"], f["abcode"]) for sc in case["scenarios"] for f in sc.get("faults", []) if f.get("resp") == "ABEND"
    }
    assert planned == {("READ", "AFCR"), ("STARTBR", "AFCS"), ("READPREV", "AFCT"), ("READ", "AFCC")}


def test_zecs000_plans_an_rls_abend_on_the_control_read():
    """#6271: 9100-ABEND (the HANDLE ABEND label of 1000-RETRIEVE) is reached by a file abend, so no non-file command abend is needed."""
    import json

    case = json.loads((TESTS / "equivalence" / "zecs-zecs000" / "case.json").read_text(encoding="utf-8"))
    planned = {
        f["abcode"]
        for sc in case["scenarios"]
        for f in sc.get("faults", [])
        if f.get("resp") == "ABEND" and f["cmd"] == "READ" and f["file"] == "ZCEXPIRE"
    }
    assert planned == {"AFCR", "AFCS", "AFCT"}

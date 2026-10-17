"""#5044: the file faults the equivalence harness plans, one test per command x IBM condition x RESP2 (register X49).

The table below is typed from IBM CICS TS 6.x's per-command "Conditions" (READ, READNEXT, READPREV, WRITE, REWRITE, DELETE,
STARTBR, ENDBR; the syntax line's condition list and each RESP2 checked against the raw pages), kept apart from the
harness's own table so the two cannot agree by being the same object. Sibling of test_file_fault_forms.py (#4623).
"""

import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_cics as ec  # noqa: E402
import test_cics_runtimes as rt  # noqa: E402  (its compile helper)

FILE_COMMANDS = ("READ", "READNEXT", "READPREV", "STARTBR", "ENDBR", "WRITE", "REWRITE", "DELETE")
ALL = FILE_COMMANDS
# IBM, per condition: the commands that list it -> the RESP2 a local VSAM file reaches
IBM = {
    "FILENOTFOUND": dict.fromkeys(ALL, (1,)),
    "NOTAUTH": dict.fromkeys(ALL, (101,)),
    "IOERR": dict.fromkeys(ALL, (120,)),
    "SYSIDERR": dict.fromkeys(ALL, (130,)),
    "ISCINVREQ": dict.fromkeys(ALL, (70,)),
    "ILLOGIC": dict.fromkeys(("READ", "STARTBR", "ENDBR", "WRITE", "DELETE"), (110,)),
    "NOTFND": dict.fromkeys(("READ", "READNEXT", "READPREV", "STARTBR", "DELETE"), (80,)),
    "ENDFILE": dict.fromkeys(("READNEXT", "READPREV"), (90,)),
    "DISABLED": dict.fromkeys(("READ", "WRITE", "DELETE", "STARTBR"), (50,)),
    "NOTOPEN": dict.fromkeys(("READ", "WRITE", "DELETE", "STARTBR"), (60,)),
    "NOSPACE": dict.fromkeys(("WRITE", "REWRITE"), (100,)),
    "LOCKED": dict.fromkeys(("READ", "READNEXT", "READPREV", "WRITE", "REWRITE", "DELETE"), (106,)),
    "DUPKEY": dict.fromkeys(("READ", "READNEXT", "READPREV"), (140,)),
    "DUPREC": dict.fromkeys(("WRITE", "REWRITE"), (150,)),
    "LENGERR": {
        "READ": (10, 11, 13),
        "READNEXT": (10, 11, 13),
        "READPREV": (10, 11, 13),
        "WRITE": (10, 12, 14),
        "REWRITE": (10, 12, 14),
    },  # fmt: skip
    "INVREQ": {
        "READ": (20, 25, 26, 28, 42),
        "READNEXT": (20, 25, 26, 34, 37, 42),
        "READPREV": (20, 24, 26, 37, 41),
        "STARTBR": (20, 25, 26, 33, 42),
        "ENDBR": (35,),
        "WRITE": (20, 23, 26),
        "REWRITE": (30, 47),
        "DELETE": (20, 21, 22, 25, 26, 31, 42, 47),
    },
}
# listed by IBM for the command, refused here: data-table / RLS conditions no case defines
REFUSED_BY_NAME = ("LOADING", "RECORDBUSY", "CHANGED", "SUPPRESSED")
BROWSE_ENDING = {("READNEXT", "ILLOGIC"), ("READPREV", "ILLOGIC"), ("REWRITE", "ILLOGIC")}  # IBM: ends the browse


def _plan(cmd, resp, **extra):
    return {"name": "s", "faults": [{"cmd": cmd, "file": "XREF", "resp": resp, **extra}]}


CASES = [(cmd, resp) for resp in IBM for cmd in FILE_COMMANDS]


@pytest.mark.parametrize(("cmd", "resp"), CASES)
def test_a_file_fault_is_planned_only_where_ibm_lists_it_with_ibms_resp2(cmd, resp):
    n = ec.CICS_RESP[resp]
    ibm = IBM[resp].get(cmd)
    if (cmd, resp) in BROWSE_ENDING:
        with pytest.raises(ec.Unsupported, match="terminates the browse"):
            ec.fault_lines(_plan(cmd, resp, resp2=110))
    elif ibm is None:
        with pytest.raises(ec.Unsupported, match="IBM documents|register X49|register X48"):
            ec.fault_lines(_plan(cmd, resp))
        with pytest.raises(ec.Unsupported):
            ec.fault_lines(_plan(cmd, resp, resp2=7))
    else:
        for r2 in ibm:
            assert ec.fault_lines(_plan(cmd, resp, resp2=r2)) == [f"{cmd} XREF 1 {n} {r2}"]
            assert ec.fault_lines(_plan(cmd, resp, resp2=r2, nth="*")) == [f"{cmd} XREF * {n} {r2}"]
        if len(ibm) == 1:  # one RESP2: the default
            assert ec.fault_lines(_plan(cmd, resp)) == [f"{cmd} XREF 1 {n} {ibm[0]}"]
        else:  # several: the scenario names one
            with pytest.raises(ec.Unsupported, match="name one"):
                ec.fault_lines(_plan(cmd, resp))
        wrong = max(ibm) + 1
        with pytest.raises(ec.Unsupported, match=f"RESP2 {'/'.join(map(str, ibm))}"):
            ec.fault_lines(_plan(cmd, resp, resp2=wrong))


@pytest.mark.parametrize("cmd", FILE_COMMANDS)
@pytest.mark.parametrize("resp", REFUSED_BY_NAME)
def test_the_conditions_the_region_cannot_raise_are_refused_by_name(cmd, resp):
    with pytest.raises(ec.Unsupported, match="register X49"):
        ec.fault_lines(_plan(cmd, resp, resp2=104))


@pytest.mark.parametrize("cmd", FILE_COMMANDS)
def test_a_condition_no_file_command_lists_is_refused(cmd):
    for resp in ("NORMAL", "PGMIDERR", "QIDERR", "ITEMERR", "TRANSIDERR", "TERMIDERR"):
        with pytest.raises(ec.Unsupported, match="IBM"):
            ec.fault_lines(_plan(cmd, resp))


def test_every_condition_the_harness_accepts_on_a_file_command_is_in_the_ibm_table():
    assert {r: dict(c) for r, c in ec.FILE_FAULT_CONDITIONS.items() if r not in ("ILLOGIC",)} == {
        r: dict(c) for r, c in IBM.items() if r not in ("ILLOGIC",)
    }
    assert dict(ec.FILE_FAULT_CONDITIONS["ILLOGIC"]) == IBM["ILLOGIC"]


def test_dupkey_on_delete_stays_refused_and_rewrite_has_no_notopen_or_disabled():
    with pytest.raises(ec.Unsupported, match="X48"):
        ec.fault_lines(_plan("DELETE", "DUPKEY"))
    for resp in ("NOTOPEN", "DISABLED"):  # IBM's REWRITE Conditions list has neither (raw page, 2026-10-13)
        with pytest.raises(ec.Unsupported, match="IBM documents"):
            ec.fault_lines(_plan("REWRITE", resp))


@pytest.mark.parametrize("cond", ("DUPKEY", "DUPREC"))
def test_the_spec_states_each_duplicate_key_outcome_with_ibms_resp2(cond):
    """#4623: the spec's outcomes carry DUPKEY / DUPREC on exactly the commands IBM lists, with IBM's RESP2."""
    from gitgalaxy.standards.cics.commands import files

    for cmd in FILE_COMMANDS:
        got = [o for o in getattr(files, cmd).outcomes if o.condition == cond]
        want = IBM[cond].get(cmd)
        assert [o.resp2 for o in got] == (list(want) if want else []), (cmd, cond)
        if cond == "DUPKEY" and got:  # the record is delivered: DUPKEY writes what NORMAL writes
            (normal,) = [o for o in getattr(files, cmd).outcomes if o.condition == "NORMAL"]
            assert got[0].writes == normal.writes


def test_a_non_file_command_is_not_read_by_the_file_rule():
    assert ec.fault_lines({"name": "s", "faults": [{"cmd": "WRITEQ-TS", "queue": "Q", "resp": "NOSPACE"}]}) == [
        "WRITEQ-TS Q 1 18 0"
    ]
    assert ec.fault_lines(
        {"name": "s", "faults": [{"cmd": "START", "transid": "T", "resp": "SYSIDERR", "resp2": 1}]}
    ) == ["START T 1 53 1"]


@rt.needs_javac
def test_cics_task_answers_the_planned_resp2_after_write_rewrite_and_delete(tmp_path):
    """The model ports and det ports read EIBRESP2 as CicsTask.resp2() after these commands (as the stub's c->resp2)."""
    plan = ec.fault_lines({"name": "s", "faults": [
        {"cmd": "WRITE", "file": "F", "resp": "NOSPACE"},
        {"cmd": "REWRITE", "file": "F", "resp": "IOERR"},
        {"cmd": "DELETE", "file": "F", "resp": "LOCKED"},
        {"cmd": "REWRITE", "file": "F", "nth": 2, "resp": "INVREQ", "resp2": 47}]})  # fmt: skip
    lines = ", ".join(f'"{ln}"' for ln in plan)
    out = rt._cics_task(
        tmp_path,
        f"""
        CicsTask t = new CicsTask("HC01", "ENTER", null, null).withFaults(java.util.List.of({lines}), null);
        System.out.println("write " + t.write("F", false, () -> {{}}) + " " + t.resp2());
        System.out.println("rewrite " + t.rewrite("F", () -> {{}}) + " " + t.resp2());
        System.out.println("rewrite2 " + t.rewrite("F", () -> {{}}) + " " + t.resp2());
        System.out.println("delete " + t.deleteHeld("F", () -> {{}}) + " " + t.resp2());
        System.out.println("unplanned " + t.write("F", true, () -> {{}}) + " " + t.resp2());""",
    )
    assert out.splitlines() == ["write 18 100", "rewrite 17 120", "rewrite2 16 47", "delete 100 106", "unplanned 14 0"]

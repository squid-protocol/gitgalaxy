"""#5089 (register X60): ENQ fault injection. A scenario plans ENQBUSY for an ENQ by its RESOURCE operand; the stub
(GGCENQ) and CicsTask.enq answer alike, and a planned-busy ENQ without NOSUSPEND is refused by both.

IBM (CICS TS 6.x, EXEC CICS ENQ): ENQBUSY "occurs when an ENQ command specifies a resource that is unavailable and the
NOSUSPEND option is specified"; without NOSUSPEND "the application program is suspended and the ENQBUSY condition is not
raised". IBM states no RESP2 for it, so a plan names none (0). INVREQ / LENGERR come from the program's own operands."""

import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_cics as ec  # noqa: E402
from test_cics_runtimes import _cics_task, _stub, _stub_base_env, needs_cc, needs_javac  # noqa: E402

_PLAN = {"cmd": "ENQ", "resource": "WS-RES", "resp": "ENQBUSY"}


def _faults(**kw):
    return {"name": "s", "faults": [{**_PLAN, **kw}]}


def test_enqbusy_is_planned_for_an_enq_by_its_resource_as_written():
    assert ec.fault_lines(_faults()) == ["ENQ WS-RES 1 55 0"]
    assert ec.fault_lines(_faults(nth=2)) == ["ENQ WS-RES 2 55 0"]
    assert ec.fault_lines(_faults(nth="*", resource="ws-res ")) == [
        "ENQ WS-RES * 55 0"
    ]  # case and blanks are no part of it


@pytest.mark.parametrize("resp", ["INVREQ", "LENGERR", "NOTFND", "NORMAL", "IOERR"])
def test_no_other_condition_is_planned_for_an_enq(resp):
    with pytest.raises(ec.Unsupported, match="register X60"):
        ec.fault_lines(_faults(resp=resp))


@pytest.mark.parametrize("cmd", ["READ", "WRITEQ-TS", "START", "CANCEL", "LINK"])
def test_enqbusy_is_no_other_commands_condition(cmd):
    with pytest.raises(ec.Unsupported, match="register X60|register X49"):  # (a file command's own rule says X49)
        ec.fault_lines({"name": "s", "faults": [{"cmd": cmd, "file": "F", "queue": "Q", "transid": "T", "reqid": "R",
                                                 "program": "P", "resp": "ENQBUSY"}]})  # fmt: skip


@pytest.mark.parametrize("bad", [None, "", "A" * 17, "A'B"])
def test_a_resource_that_is_no_short_data_name_is_refused(bad):
    with pytest.raises(ec.Unsupported, match="RESOURCE"):
        ec.fault_lines(_faults(resource=bad))


def test_ibm_states_no_resp2_for_enqbusy_so_a_plan_names_none():
    with pytest.raises(ec.Unsupported, match="no RESP2"):
        ec.fault_lines(_faults(resp2=100))


def test_the_enq_statement_calls_the_stub_with_its_resource_and_nosuspend():
    text = "\n".join(ec.translate_command("ENQ RESOURCE(ws-res) NOSUSPEND RESP(WS-R)"))
    assert "MOVE 'WS-RES' TO GG-FLAGS" in text and "MOVE 'NOSUSPEND' TO GG-NAME1" in text and "'GGCENQ'" in text
    plain = "\n".join(ec.translate_command("ENQ RESOURCE(WS-RES) LENGTH(6) NOHANDLE"))
    assert "MOVE SPACES TO GG-NAME1" in plain and "'GGCENQ'" in plain


_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len; } gg_cics;
int GGCENQ(gg_cics *c);
int main(int argc, char **argv) {
    gg_cics c;
    for (int i = 1; i + 1 < argc; i += 2) {
        memset(&c, ' ', sizeof c);
        c.resp = -1; c.resp2 = -1;
        memcpy(c.flags, argv[i], strlen(argv[i]));
        if (strcmp(argv[i + 1], "NS") == 0) memcpy(c.name1, "NOSUSPEN", 8);
        GGCENQ(&c);
        printf("%d/%d\n", c.resp, c.resp2);
    }
    return 0;
}
"""

# one ENQ sequence on both runtimes, the plan: WS-RES its 2nd and 3rd, OTHER every one
_PLAN_LINES = ["ENQ WS-RES 2 55 0", "ENQ WS-RES 3 55 0", "ENQ OTHER * 55 0"]
_STEPS = ["WS-RES", "WS-RES", "WS-RES", "WS-RES", "OTHER", "OTHER", "X"]
_ANSWERS = ["0/0", "55/0", "55/0", "0/0", "55/0", "55/0", "0/0"]


@needs_cc
def test_the_stub_plans_enqbusy_and_refuses_it_without_nosuspend(tmp_path):
    exe = _stub(tmp_path, _MAIN)
    (tmp_path / "out").mkdir()
    (tmp_path / "faults.cfg").write_text("\n".join(_PLAN_LINES) + "\n", encoding="ascii")
    env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out")}
    argv = [a for res in _STEPS for a in (res, "NS")]
    run = subprocess.run([str(exe), *argv], env=env, capture_output=True, text=True, check=True)  # noqa: S603
    assert run.stdout.split() == _ANSWERS
    assert (tmp_path / "out" / "faults.txt").read_text(encoding="ascii").splitlines() == [
        "ENQ WS-RES 2 55 0", "ENQ WS-RES 3 55 0", "ENQ OTHER 1 55 0", "ENQ OTHER 2 55 0"]  # fmt: skip
    (tmp_path / "faults.cfg").write_text(
        "ENQ WS-RES * 55 0\n", encoding="ascii"
    )  # busy, no NOSUSPEND: the task would wait
    bad = subprocess.run([str(exe), "WS-RES", "-"], env=env, capture_output=True, text=True, check=False)  # noqa: S603
    assert bad.returncode == 98 and "ENQ on a planned-busy resource without NOSUSPEND" in bad.stdout
    (tmp_path / "faults.cfg").write_text("ENQ OTHER * 55 0\n", encoding="ascii")  # not planned: no NOSUSPEND needed
    fine = subprocess.run([str(exe), "WS-RES", "-"], env=env, capture_output=True, text=True, check=True)  # noqa: S603
    assert fine.stdout.split() == ["0/0"]


@needs_javac
def test_cics_task_answers_as_the_stub_does(tmp_path):
    def task(lines):
        plan = ", ".join(f'"{ln}"' for ln in lines)
        return f'new CicsTask("HC01", "ENTER", null, null).withFaults(java.util.List.of({plan}), null)'

    body = [f"CicsTask t = {task(_PLAN_LINES)};"]
    body += [f'System.out.println(t.enq("{res}", true));' for res in _STEPS]
    body += [f"CicsTask u = {task(['ENQ WS-RES * 55 0'])};"]
    body += [
        'try { u.enq("WS-RES", false); } catch (UnsupportedOperationException e) { System.out.println(e.getMessage()); }'
    ]
    body += ['System.out.println(u.enq("OTHER", false));']
    out = _cics_task(tmp_path, "\n".join(body)).splitlines()
    names = {"0/0": "NORMAL", "55/0": "ENQBUSY"}
    assert out[: len(_ANSWERS)] == [names[a] for a in _ANSWERS]
    assert "ENQ on a planned-busy resource without NOSUSPEND" in out[len(_ANSWERS)]
    assert out[-1] == "NORMAL"


# ---- ENQ's own operands (X60): LENGTH outside 1-255 is LENGERR RESP2 1, a MAXLIFETIME CVDA that is neither UOW (246) nor
# TASK (233) is INVREQ RESP2 2; both at once is refused; an absent option is no condition ---------------------------------
_UOW, _TASK = 246, 233
# (LENGTH or None, MAXLIFETIME or None) -> "RESP/RESP2"
_OPERANDS = {
    (None, None): "0/0", (1, None): "0/0", (255, None): "0/0", (0, None): "22/1", (256, None): "22/1", (-1, None): "22/1",
    (32767, None): "22/1", (None, _UOW): "0/0", (None, _TASK): "0/0", (None, 0): "16/2", (None, 1): "16/2",
    (None, 247): "16/2", (8, _UOW): "0/0", (8, 7): "16/2", (0, _TASK): "22/1",
}  # fmt: skip

_OPERANDS_MAIN = r"""
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len; char qname[16]; int item;
                 int num; } gg_cics;
int GGCENQ(gg_cics *c);
int main(int argc, char **argv) {
    gg_cics c;
    for (int i = 1; i + 1 < argc; i += 2) {
        memset(&c, ' ', sizeof c);
        c.resp = -1; c.resp2 = -1; c.len = 0; c.num = 0;
        memcpy(c.flags, "WS-RES", 6);
        if (strcmp(argv[i], "-") != 0) { c.len = atoi(argv[i]); c.name2[0] = 'L'; }
        if (strcmp(argv[i + 1], "-") != 0) { c.num = atoi(argv[i + 1]); c.name2[c.name2[0] == 'L' ? 1 : 0] = 'M'; }
        GGCENQ(&c);
        printf("%d/%d\n", c.resp, c.resp2);
    }
    return 0;
}
"""


@needs_cc
def test_the_stub_checks_enq_length_and_maxlifetime(tmp_path):
    exe = _stub(tmp_path, _OPERANDS_MAIN)
    (tmp_path / "out").mkdir()
    env = {**_stub_base_env(), "GGCICS_DIR": str(tmp_path), "GGCICS_OUT": str(tmp_path / "out")}
    argv = [str(v) if v is not None else "-" for k in _OPERANDS for v in k]
    run = subprocess.run([str(exe), *argv], env=env, capture_output=True, text=True, check=True)  # noqa: S603
    assert run.stdout.split() == list(_OPERANDS.values())
    bad = subprocess.run([str(exe), "0", "7"], env=env, capture_output=True, text=True, check=False)  # noqa: S603
    assert bad.returncode == 98 and "IBM states no order" in bad.stdout


@needs_javac
def test_cics_task_checks_enq_length_and_maxlifetime_as_the_stub_does(tmp_path):
    def arg(v):
        return "null" if v is None else f"Integer.valueOf({v})"

    body = ['CicsTask t = new CicsTask("HC01", "ENTER", null, null);']
    body += [
        f'{{ int[] r = t.enqChecked("WS-RES", false, {arg(a)}, {arg(b)}); System.out.println(r[0] + "/" + r[1]); }}'
        for a, b in _OPERANDS
    ]
    body += ['try { t.enqChecked("WS-RES", false, 0, 7); } catch (UnsupportedOperationException e) '
             '{ System.out.println("refused"); }']  # fmt: skip
    out = _cics_task(tmp_path, "\n".join(body)).splitlines()
    assert out == [*_OPERANDS.values(), "refused"]


def test_the_enq_statement_passes_length_and_maxlifetime_to_the_stub():
    text = "\n".join(ec.translate_command("ENQ RESOURCE(WS-RES) LENGTH(300) MAXLIFETIME(DFHVALUE(TASK)) NOHANDLE"))
    assert (
        "MOVE 300 TO GG-LEN" in text and "MOVE DFHVALUE(TASK) TO GG-NUM" in text
    )  # (the CVDA number is spliced in at the end) and "MOVE 'LM' TO GG-NAME2" in text
    only = "\n".join(ec.translate_command("ENQ RESOURCE(WS-RES) LENGTH(8) NOHANDLE"))
    assert "MOVE 8 TO GG-LEN" in only and "MOVE 'L' TO GG-NAME2" in only and "GG-NUM" not in only
    neither = "\n".join(ec.translate_command("ENQ RESOURCE(WS-RES) NOHANDLE"))
    assert "MOVE SPACES TO GG-NAME2" in neither and "GG-LEN" not in neither


# ---- ENQ / DEQ in a RUN TRANSID child (#5089, X18): only on a data area the child's own WORKING-STORAGE declares ----------------
def _program(cmd: str, *, ws: str = "01 WS-RES PIC X(8).", linkage: str = "") -> str:
    pad = "       "
    return "\n".join(
        [pad + "IDENTIFICATION DIVISION.", pad + "PROGRAM-ID. KID.", pad + "DATA DIVISION.",
         pad + "WORKING-STORAGE SECTION.", pad + ws, pad + "LINKAGE SECTION.", pad + linkage,
         pad + "PROCEDURE DIVISION.", pad + f"EXEC CICS {cmd} END-EXEC.", pad + "EXEC CICS RETURN END-EXEC."]
    )  # fmt: skip


@pytest.mark.parametrize("cmd", ["ENQ RESOURCE(WS-RES)", "DEQ RESOURCE(WS-RES)", "ENQ RESOURCE(WS-RES) NOSUSPEND TASK"])
def test_an_enq_on_the_childs_own_working_storage_is_task_private(cmd):
    assert ec.child_region_resource(_program(cmd)) is None


@pytest.mark.parametrize(
    ("cmd", "kw"),
    [
        ("ENQ RESOURCE(WS-RES) LENGTH(8)", {}),  # the contents name the resource: another task's may hold the same
        ("DEQ RESOURCE(WS-RES) LENGTH(8)", {}),
        (
            "ENQ RESOURCE(LK-RES)",
            {"linkage": "01 LK-RES PIC X(8)."},
        ),  # LINKAGE storage can be shared (a COMMAREA, the CWA)
        (
            "ENQ RESOURCE(NOT-HERE)",
            {},
        ),  # not declared in this source (a copybook's item is not seen: refused, not guessed)
        ("ENQ RESOURCE(WS-OTHER)", {"ws": "01 WS-RES PIC X(8).\n       01 WS-OTHER-X PIC X."}),
        ("ENQ", {}),
        ("GET COUNTER(WS-RES) VALUE(WS-RES)", {}),  # a counter is region state: stays refused
    ],
)
def test_every_other_region_resource_in_a_child_stays_refused(cmd, kw):
    assert ec.child_region_resource(_program(cmd, **kw)) is not None


def test_one_shared_enq_refuses_the_program_whatever_else_it_holds():
    text = _program("ENQ RESOURCE(WS-RES)").replace(
        "EXEC CICS RETURN", "EXEC CICS ENQ RESOURCE(WS-RES) LENGTH(8) END-EXEC.\n       EXEC CICS RETURN"
    )
    assert ec.child_region_resource(_program("ENQ RESOURCE(WS-RES)")) is None  # (the private one alone passes)
    assert ec.child_region_resource(text) == "EXEC CICS ENQ"  # the shared one is not masked by it
    assert ec.child_region_resource("EXEC SQL SELECT 1 END-EXEC") is not None

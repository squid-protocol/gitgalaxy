"""#4952: the CBSA CRECUST equivalence case (Db2 seed, five RUN children) is committed and its holes are named.

The case is never proven while a hole stands: L1 (CEEDAYS picture 10 over 8 bytes, refused by name) and X18 (the child
schedule is ASSUMED). These checks pin that state without running Docker, so a later change that quietly drops a hole,
a child, the Db2 seed or the sweep-baseline entry fails here instead of reading as a proof.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CASE_DIR = ROOT / "tests/equivalence/cbsa-crecust"
REGISTER = ROOT / "docs/language_status/register"
CHILDREN = {f"OCR{n}": f"CRDTAGY{n}" for n in range(1, 6)}
sys.path.insert(0, str(ROOT / "tests" / "tools"))
sys.path.insert(0, str(ROOT / "tests" / "cics_crucible"))
import equivalence_cics as ec  # noqa: E402
import equivalence_cics_faults as ecf  # noqa: E402
from test_cics_runtimes import _cics_task, needs_javac  # noqa: E402


def _case() -> dict:
    return json.loads((CASE_DIR / "case.json").read_text(encoding="utf-8"))


def test_case_runs_the_five_children_and_has_a_db2_seed():
    case = _case()
    assert case["kind"] == "cics" and case["program"] == "CRECUST"
    assert case["child_programs"] == CHILDREN
    assert sorted(case["transactions"]) == sorted(CHILDREN)
    # every child is a program of the case, so RUN TRANSID has something to run
    assert {p["program"] for p in case["programs"]} >= set(CHILDREN.values())
    seed = CASE_DIR / "seed.sql"
    assert case["db2"]["seed"] == "@case/seed.sql" and seed.is_file()
    assert "IBMUSER.PROCTRAN" in case["db2"]["compare"]
    assert re.search(r"INSERT\s+INTO", seed.read_text(encoding="utf-8"), re.I)


def test_scenarios_cover_the_credit_check_and_the_paths_around_the_ceedays_hole():
    names = [s["name"] for s in _case()["scenarios"]]
    # create-customer, born-in-the-future, born-30-feb and born-over-150 reach CEEDAYS (L1); born-before-1601 ends before it
    assert names[:5] == ["create-customer", "born-before-1601", "born-in-the-future", "born-30-feb", "born-over-150"]
    # #6072: the CUSTOMER control-record and new-record fault scenarios (the SYSIDERR retries and the other RESPs)
    assert names[5:] == [
        "control-read-sysiderr-retried",
        "control-read-io-error",
        "control-rewrite-sysiderr-retried",
        "control-rewrite-io-error",
        "write-sysiderr-retried",
        "write-sysiderr-exhausted",
        # #6882: RUN TRANSID and FETCH ANY faults
        "run-transid-first-transiderr",
        "fetch-any-notfinished-nothing-retrieved",
        "fetch-any-notfinished-after-a-reply",
        "fetch-any-notfnd-nothing-retrieved",
        "fetch-any-notfnd-after-a-reply",
        # #6882: PUT CONTAINER and GET CONTAINER faults
        "put-container-first-containererr",
        "get-container-first-containererr",
        # #6882: CEELOCT feedback-code failure
        "ceeloct-local-time-unavailable",
        # #6967: a fault planned in a RUN child -- the child abends, FETCH ANY answers COMPSTATUS ABEND (853)
        "fetch-any-first-child-abends",
        # #6967: FETCH ANY returns a child with COMPSTATUS SECERROR (951)
        "fetch-any-first-child-secerror",
        # #6967: ... after two NORMAL children; the SECERROR child's reply is empty (owner, X18)
        "fetch-any-third-child-secerror",
    ]


def test_notes_name_the_assumptions_and_forbid_reading_the_level_from_them():
    notes = _case()["notes"]
    for word in ("L1", "X18", "ASSUMED", "Not recorded as evidence"):
        assert word in notes
    assert "NOT PROVABLE" not in notes


def test_sweep_baseline_no_longer_carries_the_case():
    # #5089: the slack is ruled blank (L1), so the det proof holds and the baseline is a two-way ratchet
    det = json.loads((ROOT / "tests/equivalence/det_sweep_baseline.json").read_text(encoding="utf-8"))["det"]
    assert "cbsa-crecust" not in det and "cbsa-bnk1ccs-create" not in det


def test_register_entries_agree_the_case_is_refused_not_proven():
    l1 = (REGISTER / "L1.md").read_text(encoding="utf-8")
    x18 = (REGISTER / "X18.md").read_text(encoding="utf-8")
    assert "cbsa-crecust" in l1 and "REFUSED" in l1
    assert "tests/equivalence/cbsa-crecust" in x18 and "BNK1CCS" in x18


# ---- #6967 (register X18): a fault scoped to a RUN TRANSID child task ---------------------------------------------
# A fault with "child": "<TRANSID>" is planned in the child the parent dispatches for that transaction: fault_lines writes
# it `@TRANSID ` first, both stubs hand the child its lines with the prefix off (it counts its commands as a task of its
# own), and what fires in the child comes back into the parent's fired log, `@TRANSID ` first.


def _sc(*faults):
    return {"name": "s", "faults": list(faults)}


def test_a_child_fault_is_the_root_fault_line_with_its_transid_first():
    forms = [
        {"cmd": "DELAY", "resp": "INVREQ", "resp2": 6, "nth": 1},
        {"cmd": "LINK", "program": "ABNDPROC", "resp": "PGMIDERR", "resp2": 3, "nth": 1},
        {"cmd": "READ", "file": "CUSTOMER", "resp": "NOTFND", "nth": 2},
        {"cmd": "READ", "file": "CUSTOMER", "resp": "ABEND", "abcode": "AFCR", "nth": 1},
    ]
    for f in forms:
        root = ecf.fault_lines(_sc(f))
        assert ecf.fault_lines(_sc({**f, "child": "OCR1"})) == ["@OCR1 " + line for line in root], f


def test_the_child_abend_scenario_plans_its_faults_in_a_child_of_the_case():
    """CRDTAGYn abends only by DELAY RESP != NORMAL -> LINK ABNDPROC (no RESP) -> ABEND; ABNDPROC writes ABNDFILE, a
    region resource a child may not touch (R1), so its LINK fails PGMIDERR and the child abends on that condition."""
    (sc,) = [s for s in _case()["scenarios"] if s["name"] == "fetch-any-first-child-abends"]
    assert {f["child"] for f in sc["faults"]} <= set(CHILDREN)  # fault_lines has no case to check it against
    assert ecf.fault_lines(sc) == ["@OCR1 DELAY - 1 16 6", "@OCR1 LINK ABNDPROC 1 27 3"]


@pytest.mark.parametrize("child", ["", "OCR12", "ocr1", 7, None, "OC R"])
def test_a_child_that_is_not_a_transaction_id_is_refused(child):
    with pytest.raises(ec.Unsupported, match="child"):
        ecf.fault_lines(_sc({"cmd": "DELAY", "child": child, "resp": "INVREQ", "resp2": 6}))


@needs_javac
@pytest.mark.slow(reason="first in its CI split part it pays the cold javac of the shared CicsTask build (#6018)")
def test_a_child_fault_fires_only_in_the_child_and_fetch_any_reports_its_abend(tmp_path):
    log = tmp_path / "fired.txt"
    out = _cics_task(
        tmp_path,
        """
        CicsTask t = new CicsTask("GTPA", "ENTER", null, null).withTaskNumber(100).withPrograms(new CicsTask.Programs() {
            public boolean defined(String p) {
                return true;
            }

            public String program(String tr) {
                return "KIDPROG";
            }

            public boolean transaction(String tr) {
                return tr.equals("KC");
            }

            public void run(String p, CicsTask s) {
                int[] d = s.planned("DELAY", "-");
                System.out.println("child DELAY " + d[0] + "/" + d[1]);
                if (d[0] != 0) {
                    s.abend("KIDA");
                    return;
                }
                s.returnTransid(null, null);
            }
        }).withFaults(java.util.List.of("@KC DELAY - 1 16 6"), java.nio.file.Path.of("%LOG%"));
        int[] d = t.planned("DELAY", "-");
        System.out.println("parent DELAY " + d[0] + "/" + d[1]);
        t.runTransid("KC");
        CicsTask.FetchResult f = t.fetch(null, "WAIT", 0, false);
        System.out.println(f.resp() + " " + f.compstatus() + " " + f.abcode());""".replace("%LOG%", log.as_posix()),
    )
    assert out.splitlines() == ["parent DELAY 0/0", "child DELAY 16/6", "NORMAL 900 KIDA"]
    assert log.read_text(encoding="utf-8").splitlines() == ["@KC DELAY - 1 16 6"]


def _faulted(child):
    return {"name": "s", "faults": [{"cmd": "DELAY", "child": child, "resp": "INVREQ", "resp2": 6}]}


@pytest.mark.parametrize("child", sorted(CHILDREN))
def test_a_fault_in_a_child_the_case_runs_is_accepted(child):  # #6967
    ecf.check_child_faults(_case(), _faulted(child))


@pytest.mark.parametrize(
    "case", [_case(), {"kind": "cics", "programs": []}], ids=["other-transid", "no-child-programs"]
)
def test_a_fault_in_a_child_no_child_programs_entry_runs_is_refused(case):
    with pytest.raises(ec.Unsupported, match="never fires"):
        ecf.check_child_faults(case, _faulted("ZZZ9"))


def test_a_fault_without_child_needs_no_child_programs():
    ecf.check_child_faults(
        {"kind": "cics", "programs": []}, {"name": "s", "faults": [{"cmd": "DELAY", "resp": "EXPIRED"}]}
    )


def test_every_committed_child_fault_names_a_child_of_its_case():
    seen = 0
    for path in sorted((ROOT / "tests/equivalence").glob("*/case.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        for sc in case.get("scenarios", []):
            if any("child" in f for f in sc.get("faults") or []):
                ecf.check_child_faults(case, sc)
                seen += 1
    assert seen >= 1


def test_every_terminal_verb_of_the_burned_cbsa_screens_has_a_fault_command_or_a_refusal():
    """#6967: SEND MAP / SEND TEXT / RECEIVE MAP are planned (X71); SEND CONTROL is refused by name; no screen uses a
    bare RECEIVE, CONVERSE or SEND PAGE, so no terminal outcome lacks a command."""
    import os

    base = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    src = Path(base or "") / "cics-banking-sample-application-cbsa/src/base/cobol_src"
    if not base or not src.is_dir():
        pytest.skip("the CBSA corpus is not fetched")
    verbs = set()
    for f in src.glob("BNK1*.cbl"):
        text = f.read_text(encoding="latin-1")
        for m in re.finditer(r"(?is)\bEXEC\s+CICS\s+(SEND|RECEIVE|CONVERSE)\s+(\w+)", text):
            verbs.add(f"{m.group(1).upper()} {m.group(2).upper()}")
    assert verbs <= {"SEND MAP", "SEND TEXT", "RECEIVE MAP", "SEND CONTROL"}, verbs
    for v in ("SEND MAP", "SEND TEXT", "RECEIVE MAP"):
        assert v.replace(" ", "-") in ecf.FAULT_COMMANDS


# ---- #6967 (register X18): a FETCH whose child reports COMPSTATUS SECERROR -----------------------------------------


def test_the_secerror_scenario_plans_the_compstatus_of_the_first_child_fetched():
    (sc,) = [s for s in _case()["scenarios"] if s["name"] == "fetch-any-first-child-secerror"]
    assert ecf.fault_lines(sc) == ["FETCH-STATUS - 1 1214 0"]
    (third,) = [s for s in _case()["scenarios"] if s["name"] == "fetch-any-third-child-secerror"]
    assert ecf.fault_lines(third) == ["FETCH-STATUS - 3 1214 0"]


@pytest.mark.parametrize(
    "fault",
    [
        {"cmd": "FETCH-STATUS", "resp": "ABEND"},
        {"cmd": "FETCH-STATUS", "resp": "NORMAL"},
        {"cmd": "FETCH-STATUS", "resp": "NOTFND", "resp2": 1},
        {"cmd": "FETCH-STATUS", "resp": "SECERROR", "resp2": 3},
        {"cmd": "FETCH-ANY", "resp": "SECERROR"},
    ],
    ids=["abend", "normal", "other-condition", "resp2", "not-a-fetch-any-condition"],
)
def test_only_secerror_is_planned_as_a_compstatus_and_it_states_no_resp2(fault):
    with pytest.raises(ec.Unsupported):
        ecf.fault_lines(_sc(fault))


@needs_javac
@pytest.mark.slow(reason="first in its CI split part it pays the cold javac of the shared CicsTask build (#6018)")
def test_the_planned_child_fetched_is_secerror_and_the_next_is_not(tmp_path):
    log = tmp_path / "fired.txt"
    out = _cics_task(
        tmp_path,
        """
        CicsTask t = new CicsTask("GTPB", "ENTER", null, null).withTaskNumber(100).withPrograms(new CicsTask.Programs() {
            public boolean defined(String p) {
                return true;
            }

            public String program(String tr) {
                return "KIDPROG";
            }

            public boolean transaction(String tr) {
                return true;
            }

            public void run(String p, CicsTask s) {
                s.returnTransid(null, null);
            }
        }).withFaults(java.util.List.of("FETCH-STATUS - 1 1214 0"), java.nio.file.Path.of("%LOG%"));
        t.runTransid("KA");
        t.runTransid("KB");
        for (int i = 0; i < 2; i++) {
            CicsTask.FetchResult f = t.fetch(null, "WAIT", 0, false);
            System.out.println(f.resp() + " " + f.compstatus() + " " + f.abcode());
        }""".replace("%LOG%", log.as_posix()),
    )
    assert out.splitlines() == ["NORMAL 1214 null", "NORMAL 1016 null"]
    assert log.read_text(encoding="utf-8").splitlines() == ["FETCH-STATUS - 1 1214 0"]


@needs_javac
@pytest.mark.slow(reason="first in its CI split part it pays the cold javac of the shared CicsTask build (#6018)")
def test_a_secerror_child_replies_with_an_empty_channel_and_the_next_child_with_its_own(tmp_path):
    """#6967 (X18, owner 2026-10-29): IBM says nothing about the reply of a child that failed its security check; the
    reply is assumed EMPTY (a channel of the harness's name with no container). Both children left container R."""
    log = tmp_path / "fired.txt"
    out = _cics_task(
        tmp_path,
        """
        CicsTask t = new CicsTask("GTPB", "ENTER", null, null).withTaskNumber(100).withPrograms(new CicsTask.Programs() {
            public boolean defined(String p) {
                return true;
            }

            public String program(String tr) {
                return "KIDPROG";
            }

            public boolean transaction(String tr) {
                return true;
            }

            public void run(String p, CicsTask s) {
                s.putContainer(null, "R", "kid".getBytes(), 3, null, false);
                s.returnTransid(null, null);
            }
        }).withFaults(java.util.List.of("FETCH-STATUS - 1 1214 0"), java.nio.file.Path.of("%LOG%"));
        t.putContainer("CH", "X", "p".getBytes(), 1, null, false);
        t.runTransid("KA", "CH");
        t.runTransid("KB", "CH");
        for (int i = 0; i < 2; i++) {
            CicsTask.FetchResult f = t.fetch(null, "WAIT", 0, true);
            CicsTask.ContainerResult g = t.getContainer(f.channel(), "R", 60);
            System.out.println(f.resp() + " " + f.compstatus() + " " + f.abcode() + " " + g.resp() + " "
                    + (g.data() == null ? "-" : new String(g.data())));
        }
        CicsTask.FetchResult n = t.fetch(null, "NOSUSPEND", 0, false);
        System.out.println(n.resp() + " " + n.channel());""".replace("%LOG%", log.as_posix()),
    )
    first, second, none = out.splitlines()
    assert first.startswith("NORMAL 1214 null ") and not first.endswith(" kid")
    assert first.split()[3] != "NORMAL"  # GET CONTAINER on the empty reply fails
    assert second == "NORMAL 1016 null NORMAL kid"
    assert none.startswith("NOTFND")

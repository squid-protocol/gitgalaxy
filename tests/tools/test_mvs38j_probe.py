"""MVS 3.8J probe (#8414): deck generation and the three-way comparison, offline; plus the committed probe results' shape."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools" / "box" / "mvs38j"))
import probe  # noqa: E402
import runner  # noqa: E402

from gitgalaxy.core import job_flow  # noqa: E402

FIXTURE = ROOT / "tests" / "equivalence" / "jcl" / "fixture"
ROWS = job_flow.jcl_job_flow((FIXTURE / "FLOW.jcl").read_text(encoding="utf-8"))
DOC = json.loads((FIXTURE / "scenarios.json").read_text(encoding="utf-8"))


def test_the_deck_keeps_each_cond_as_written_and_sets_the_return_code_through_idcams():
    deck = probe.build_deck(ROWS, "CONDJOB", {"S1": {"rc": 6}, "S3": {"rc": 0}, "S5": {"rc": 0}})
    lines = deck.splitlines()
    assert lines[0].startswith("//CONDJOB  JOB ")
    assert "//S2       EXEC PGM=IDCAMS,COND=(4,LT,S1)" in lines
    assert "//S3       EXEC PGM=IDCAMS,COND=((8,LE,S1),(0,NE,S2))" in lines
    assert "//S5       EXEC PGM=IDCAMS,COND=EVEN" in lines
    assert lines[lines.index("//S1       EXEC PGM=IDCAMS") + 3] == " SET MAXCC=6"
    assert all(len(ln) <= 72 for ln in lines)


def test_an_abend_runs_a_program_the_system_cannot_find_and_a_step_without_input_gets_return_code_0():
    deck = probe.build_deck(ROWS, "EVNJOB", {"T1": {"abend": "S0C7"}})
    assert f"//T1       EXEC PGM={probe.ABEND_PGM}" in deck
    assert deck.count("SET MAXCC=0") == 2  # T2, T3 have no `given`: started if the box starts them
    assert "COND=((4,LT,T1),ONLY)" in deck


def test_every_cond_scenario_builds_a_deck_for_exactly_its_jobs_steps():
    for sc in DOC["scenarios"]:
        if sc["job"] in probe.COND_JOBS:
            deck = probe.build_deck(ROWS, sc["job"], sc["given"])
            assert [ln[2:10].strip() for ln in deck.splitlines() if " EXEC " in ln] == list(sc["expect"])


LOG = """\
 IEF403I J1 - STARTED - TIME=12.00.01
 IEF142I J1 A - STEP WAS EXECUTED - COND CODE 0006
 IEF202I J1 B - STEP WAS NOT RUN BECAUSE OF CONDITION CODES
 IEF272I J1 B - STEP WAS NOT EXECUTED.
 IEF450I J1 C - ABEND S806 U0000 SYSTEM=806 USER=0000
 $HASP395 J1  ENDED
"""


def test_a_step_is_run_when_it_ended_with_a_code_or_abended_and_bypass_otherwise():
    assert probe.observed(runner.parse_log(LOG), "J1", ["A", "B", "C", "D"]) == {
        "A": "run",
        "B": "bypass",
        "C": "run",
        "D": "bypass",
    }
    assert probe.observed(runner.parse_log(LOG), "OTHER", ["A"]) is None


def test_the_verdict_names_which_column_differs_from_the_manual_answer():
    e = {"S1": "run", "S2": "bypass"}
    other = {"S1": "run", "S2": "run"}
    assert probe.verdict(e, e, e) == "agree"
    assert probe.verdict(e, e, other) == "differ:box"
    assert probe.verdict(e, other, e) == "differ:engine"
    assert probe.verdict(e, other, other) == "differ:engine+box"
    assert probe.verdict(e, e, None) == "no-box-answer"


def test_the_committed_results_cover_every_cond_scenario_and_repeat_the_manual_and_engine_answers():
    from gitgalaxy.core.jcl_flow import JclFlow

    got = json.loads((FIXTURE / "mvs38j_probe.json").read_text(encoding="utf-8"))
    assert got["provenance"] == "mvs38j-run" and "Q16" in got["internal_only"]
    flow = JclFlow(ROWS)
    want = [s for s in DOC["scenarios"] if s["job"] in probe.COND_JOBS]
    assert [r["id"] for r in got["results"]] == [s["id"] for s in want]
    for r, sc in zip(got["results"], want, strict=True):
        assert r["expect"] == sc["expect"], r["id"]
        assert r["engine"] == flow.run(sc["job"], sc["given"]).actions, r["id"]
        assert r["verdict"] == probe.verdict(r["expect"], r["engine"], r["box"]), r["id"]
        assert r["unparsed_ief"] == 0, r["id"]


PROC_DOC = json.loads((probe.PROC_CASE / "scenarios.json").read_text(encoding="utf-8"))


def test_the_proc_deck_keeps_one_call_its_overrides_and_makes_each_dd_a_named_new_dataset():
    deck, sym = probe.proc_deck(PROC_DOC["flow_jcl"], "OVRJOB", "O3")
    lines = deck.splitlines()
    assert lines[0].startswith("//OVRJOB   JOB ") and "MSGLEVEL=(1,1)" in lines[0]
    assert "//A1       EXEC PGM=IEFBR14,PARM='X1'" in lines
    assert "//A2.EXTRA DD DSN=EXTRA.DD,UNIT=SYSDA,SPACE=(TRK,1)" in lines
    assert not any(ln.startswith(("//O1", "//O2")) for ln in lines) and "//O3       EXEC BASE" in lines
    assert sym == [] and all(len(ln) <= 72 for ln in lines)
    deck, sym = probe.proc_deck(PROC_DOC["flow_jcl"], "SYMJOB", "S2")
    assert sym == ["P1"] and deck.splitlines()[-1] == "//S2       EXEC CATP,HLQ=TEST,PRM=TWO"
    assert "SET" not in deck


PROC_LOG = """\
IEF236I ALLOC. FOR J A1 O3
IEF237I 251  ALLOCATED TO SYSUT1
IEF285I   NEW.IN                                       DELETED       *--------0
IEF285I   VOL SER NOS= WORK00.
IEF236I ALLOC. FOR J A2 O3
IEF237I 252  ALLOCATED TO SYSUT1
IEF237I 251  ALLOCATED TO EXTRA
IEF653I SUBSTITUTION JCL - PGM=IEFBR14,PARM='TWO'
IEF285I   BASE.IN2                                     DELETED       *--------0
IEF285I   EXTRA.DD                                     DELETED       *--------0
IEF236I ALLOC. FOR OTHER X1 Y
"""


def test_the_proc_log_reader_pairs_each_steps_ddnames_with_its_dsns_in_order():
    steps, subst = probe.observe_proc(PROC_LOG, "J")
    assert steps == {
        "O3.A1": {"dd": {"SYSUT1": "NEW.IN"}},
        "O3.A2": {"dd": {"SYSUT1": "BASE.IN2", "EXTRA": "EXTRA.DD"}},
    }
    assert subst == ["TWO"]
    shown = probe.proc_projection(steps, {"O3.A2"}, {"O3.A2": "TWO"})
    assert shown["O3.A2"] == {"dd": [("SYSUT1", "BASE.IN2"), ("EXTRA", "EXTRA.DD")], "parm": "TWO"}
    assert "parm" not in shown["O3.A1"]


def test_the_committed_proc_results_repeat_the_manual_answers_and_the_engine_and_name_what_is_unobserved():
    got = json.loads((probe.PROC_RESULTS).read_text(encoding="utf-8"))
    assert got["provenance"] == "mvs38j-run" and "Q16" in got["internal_only"]
    _, text, libs, scs = probe.proc_scenarios()
    assert [r["id"] for r in got["results"]] == [s["id"] for s in scs] and len(scs) == 8
    for r, sc in zip(got["results"], scs, strict=True):
        assert list(r["expect"]) == list(sc["expect"]), r["id"]
        assert r["verdict"] == probe.verdict(r["expect"], r["engine"], r["box"]), r["id"]
        assert r["unobserved"] == probe.PROC_UNOBSERVED and r["jcl_error"] is False, r["id"]
        assert [s["procstep"] for s in r["box_steps"]] == [k.split(".")[1] for k in sc["expect"]], r["id"]


def _flow():
    return probe.flow_scenarios()


def test_the_flow_deck_runs_iefbr14_and_puts_each_permanent_dataset_under_the_user_catalog_alias():
    doc, _ = _flow()
    deck = probe.flow_deck(doc["flow_jcl"], "CATJOB", {})
    lines = deck.splitlines()
    assert "PGM=IEFBR14" in deck and "PGM=MERGE" not in deck
    assert "//         DD DSN=PUB001.A.SECOND,DISP=SHR" in lines
    assert "//         DD DSN=PUB001.PAY.GDG.GSTAND,DISP=SHR" in lines  # BASE(0) probed as a plain dataset
    out = lines.index("//OUT      DD DSN=PUB001.A.OUT,DISP=(NEW,CATLG),")
    assert lines[out + 1] == "//            UNIT=SYSDA,SPACE=(TRK,1)"  # 3.8J wants a UNIT
    assert all(len(ln) <= 71 for ln in lines)  # past column 71 is IEF618I


def test_a_temporary_keeps_its_name_in_the_deck_and_a_given_return_code_runs_idcams():
    doc, _ = _flow()
    deck = probe.flow_deck(doc["flow_jcl"], "BYPJOB", {"B1": {"rc": 8}})
    assert "DSN=&&LOST" in deck and "PUB001.&&" not in deck
    assert "//B1       EXEC PGM=IDCAMS" in deck and " SET MAXCC=8" in deck


def test_the_support_decks_create_what_is_read_and_delete_it_with_idcams_so_a_missing_one_is_not_a_jcl_error():
    doc, _ = _flow()
    pre, post = probe.flow_support_decks(doc["flow_jcl"], "CATJOB")
    assert "DSN=PUB001.B.ONE,DISP=(MOD,CATLG)," in pre and "PUB001.A.OUT" not in pre
    assert " DELETE PUB001.A.OUT" in post and " SET MAXCC=0" in post and "OLD,DELETE" not in post
    assert all(len(ln) <= 71 for ln in (pre + post).splitlines())
    assert probe.flow_support_decks(doc["flow_jcl"], "TMPJOB") == ("", "")


def test_a_system_named_temporary_prints_as_its_ampersand_name_and_the_catalog_and_gdg_standin_are_normalised():
    assert probe.flow_dsn("SYS26324.T204022.RA000.DFLJOB.KEPT", "DFLJOB") == "&&KEPT"
    assert probe.flow_dsn("SYS26324.T204022.RA000.DFLJOB.R0000001", "DFLJOB") == "&&(system-named)"
    assert probe.flow_dsn("SYS26324.T204022.RA000.OTHER.KEPT", "DFLJOB").startswith("SYS26324")
    assert probe.flow_dsn("PUB001.PAY.CTL", "DUMJOB") == "PAY.CTL"
    assert probe.flow_dsn("PUB001.PAY.GDG.GSTAND", "CATJOB") == "PAY.GDG(0)"


FLOW_LOG = """IEF236I ALLOC. FOR DFLJOB T1
IEF237I DMY  ALLOCATED TO NUL
IEF142I DFLJOB T1 - STEP WAS EXECUTED - COND CODE 0000
IEF285I   SYS26324.T204022.RA000.DFLJOB.KEPT           PASSED        *--------0
IEF285I   VOL SER NOS= WORK01.
IEF285I   UCPUB001                                     KEPT          *--------0
IEF374I STEP /T1      / STOP  26324.2040 CPU    0MIN 00.00SEC
IEF237I 252  ALLOCATED TO SYS00001
IEF285I   SYS26324.T204022.RA000.DFLJOB.KEPT           DELETED
"""


def test_the_log_reader_gives_each_step_its_datasets_and_keeps_what_follows_the_last_step_apart():
    seen = probe.observe_flow(FLOW_LOG, "DFLJOB")
    assert seen["T1"] == {"dsn": ["&&KEPT"], "disp": ["PASSED"], "dummy": ["NUL"]}  # the catalog line is not a dataset
    assert seen[probe.JOB_END]["disp"] == ["DELETED"]
    temps = probe.flow_box_temps({k: v for k, v in seen.items() if k != probe.JOB_END})
    assert temps == {"&&KEPT": {"created": "T1", "received": [], "deleted_after": "JOB"}}


def test_the_committed_flow_results_cover_every_flow_scenario_and_agree_three_ways():
    got = json.loads(probe.FLOW_RESULTS.read_text(encoding="utf-8"))
    assert got["provenance"] == "mvs38j-run" and "Q16" in got["internal_only"]
    _, scs = _flow()
    assert [r["id"] for r in got["results"]] == [s["id"] for s in scs] and len(scs) == 6
    for r in got["results"]:
        assert r["verdict"] == probe.verdict(r["expect"], r["engine"], r["box"]), r["id"]
        assert r["unobserved"] == probe.FLOW_UNOBSERVED, r["id"]
    assert [r["id"] for r in got["results"] if r.get("substituted")] == ["concat-read-order"]


def test_the_restart_deck_keeps_restart_and_cond_and_overrides_each_procedure_steps_sysin():
    doc, _ = probe.restart_scenarios()
    deck = probe.restart_deck(doc["flow_jcl"], "RSTJOB3", {"CALL1.P2": {"rc": 8}})
    lines = deck.splitlines()
    assert lines[0] == "//RSTJOB3  JOB (ACCT),'PROC STEP',CLASS=A,MSGCLASS=A,RESTART=CALL1.P2"
    assert "//P3       EXEC PGM=IDCAMS,COND=(4,LT,P2)" in lines
    assert (
        lines.index("//P2.SYSIN DD *") + 1 < len(lines) and lines[lines.index("//P2.SYSIN DD *") + 1] == " SET MAXCC=8"
    )
    assert lines[lines.index("//P1.SYSIN DD *") + 1] == " SET MAXCC=0"
    plain = probe.restart_deck(doc["flow_jcl"], "RSTJOB7", {})
    assert "//M3       EXEC PGM=IDCAMS,COND=((0,NE,M1),(4,LT,M2))" in plain.splitlines()
    assert all(len(ln) <= 72 for ln in lines + plain.splitlines())


def test_a_restart_step_with_no_record_is_skipped_an_executed_one_run_and_a_cond_bypass_bypass():
    log = """\
 IEF142I J1 B - STEP WAS EXECUTED - COND CODE 0008
 IEF202I J1 C - STEP WAS NOT RUN BECAUSE OF CONDITION CODES
 IEF272I J1 C - STEP WAS NOT EXECUTED.
 IEF142I J1 P2 CALL - STEP WAS EXECUTED - COND CODE 0000
 $HASP395 J1  ENDED
"""
    got = probe.observed_restart(runner.parse_log(log), "J1", ["A", "B", "C", "CALL.P2", "CALL.P1"])
    assert got == {"A": "skipped", "B": "run", "C": "bypass", "CALL.P2": "run", "CALL.P1": "skipped"}


def test_the_committed_restart_results_cover_every_step_restart_scenario_and_agree_three_ways():
    got = json.loads((probe.RESTART_RESULTS).read_text(encoding="utf-8"))
    assert got["provenance"] == "mvs38j-run" and "Q16" in got["internal_only"]
    doc, scs = probe.restart_scenarios()
    assert [r["id"] for r in got["results"]] == [s["id"] for s in scs] and len(scs) == 11
    assert set(got["skipped"]) == {s["id"] for s in doc["scenarios"]} - {s["id"] for s in scs}
    for r in got["results"]:
        assert r["verdict"] == probe.verdict(r["expect"], r["engine"], r["box"]) == "agree", r["id"]


def _dsutil():
    return json.loads(probe.DSUTIL_SCENARIOS.read_text(encoding="utf-8"))


def test_the_dsutil_decks_run_the_real_utilities_and_re_root_every_dataset_under_the_user_catalog():
    doc = _dsutil()
    for sc in doc["scenarios"]:
        deck = probe.dsutil_deck(doc["flow_jcl"], sc["job"])
        assert deck.splitlines()[0].split()[:2] == [f"//{sc['job']}", "JOB"], sc["id"]
        assert "PRB." not in deck, sc["id"]
    cleanup = probe.dsutil_cleanup_deck(doc["cleanup_dsns"])
    assert cleanup.count("DISP=(MOD,DELETE)") == len(doc["cleanup_dsns"]) and "PRB." not in cleanup
    assert "PGM=IEBGENER" in probe.dsutil_deck(doc["flow_jcl"], "GENCPY") and "PGM=IEBCOPY" in probe.dsutil_deck(
        doc["flow_jcl"], "CPYSEL"
    )


def test_the_dsutil_events_collapse_kept_cataloged_and_deleted_uncataloged_and_map_the_root_back():
    disp = [
        {"dsn": "JES2.JOB00012.SO0101", "disposition": "SYSOUT"},
        {"dsn": "PUB001.UTIL.EMPTY", "disposition": "CATALOGED"},
        {"dsn": "UCPUB001", "disposition": "KEPT"},
        {"dsn": "PUB001.UTIL.EMPTY", "disposition": "UNCATALOGED"},
        {"dsn": "PUB001.UTIL.EMPTY", "disposition": "DELETED"},
    ]
    assert probe.dsutil_events(disp, ["PRB.UTIL.EMPTY"]) == [
        ["PRB.UTIL.EMPTY", "cataloged"],
        ["PRB.UTIL.EMPTY", "deleted"],
    ]


def test_the_committed_dsutil_results_cover_every_scenario_and_name_the_one_disagreement():
    got = json.loads(probe.DSUTIL_RESULTS.read_text(encoding="utf-8"))
    assert got["provenance"] == "mvs38j-run" and "Q16" in got["internal_only"]
    assert [r["id"] for r in got["results"]] == [s["id"] for s in _dsutil()["scenarios"]]
    assert all(r["engine"] is None and not r["jcl_error"] for r in got["results"])
    # IEF453I / IEF212I (a missing OLD dataset is "JOB FAILED - JCL ERROR" on the box) are the only lines the log reader does not know
    assert {r["id"]: r["unparsed_ief"] for r in got["results"] if r["unparsed_ief"]} == {
        "iefbr14-old-dataset-not-cataloged": 2
    }
    differ = {r["id"]: r["verdict"] for r in got["results"] if r["verdict"] != "agree"}
    assert differ == {"iebgener-dummy-input-empty-output": "differ:box"}
    row = next(r for r in got["results"] if r["id"] in differ)
    assert row["expect"]["steps"]["S1"]["rc"] == 0 and row["box"]["steps"]["S1"]["rc"] == 12

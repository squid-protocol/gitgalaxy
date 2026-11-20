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

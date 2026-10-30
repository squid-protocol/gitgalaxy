"""#5126 (register X64 / X19): ASSIGN USERID, FACILITY / TERMCHK and SCRNHT / SCRNWD are facts an equivalence case states
("userid", "termid", "screen"). No burned program reads them (only STARTCODE is read, by four programs whose cases state
it), so nothing is executed-equivalent; this pins that reading, that each option is a named gap until a case states it,
and that the harness really emits each stated fact on both sides. Burned estates only."""

import os
import sys
from pathlib import Path

import pytest

from gitgalaxy.core.source_text import read_source

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "tools"))
sys.path.insert(0, str(HERE))
import proof_blockers as pb  # noqa: E402

BURNED_DIRS = (
    "aws-mainframe-modernization-carddemo",
    "cics-async-api-credit-card-application-example",
    "cics-banking-sample-application-cbsa",
    "cics-genapp",
    "dbb-mortgage-application",
    "zecs",
)
# program -> the ASSIGN task facts it reads; each has an equivalence case that states STARTCODE (X64)
KNOWN_READERS = {
    "ASYNCPNT": {"STARTCODE"},
    "SEQPNT": {"STARTCODE"},
    "LGICVS01": {"STARTCODE"},
    "LGIPVS01": {"STARTCODE"},
}
GAP = "fact: ASSIGN {} (no equivalence case states it)"


def _readers() -> dict[str, set[str]]:
    root = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    if not root or not Path(root).is_dir():
        pytest.skip("GITGALAXY_MAINFRAME_CORPORA is not set")
    found: dict[str, set[str]] = {}
    for name in BURNED_DIRS:
        base = Path(root) / name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.suffix.lower() not in {".cbl", ".cob", ".cobol"} or not path.is_file():
                continue
            text = read_source(path).text
            if "ASSIGN" not in text.upper():
                continue
            names = set(pb.facts_needed(text)["assign_task"])
            if names:
                found.setdefault(path.stem.upper(), set()).update(names)
    return found


def test_only_startcode_is_read_by_a_burned_program():
    assert _readers() == KNOWN_READERS, (
        "a burned program reads ASSIGN USERID / FACILITY / TERMCHK / SCRNHT / SCRNWD: prove it with a case that states "
        "the fact, then update KNOWN_READERS and the X64 entry"
    )


@pytest.mark.parametrize("option", ["USERID", "FACILITY", "TERMCHK", "SCRNHT", "SCRNWD"])
def test_each_option_is_found_by_the_fact_scan(option):
    assert pb.facts_needed(f"           EXEC CICS ASSIGN {option}(X) END-EXEC.\n")["assign_task"] == {
        pb.ASSIGN_TASK_FACTS[option]
    }


def test_each_option_is_a_named_gap_until_a_case_states_it():
    for fact in ("USERID", "FACILITY", "SCRNHT/SCRNWD"):
        facts = {"eib": set(), "assign_task": {fact}, "assign_region": set()}
        assert pb.fact_gaps(facts, pb.Run("equivalence", "c")) == {GAP.format(fact)}
        assert pb.fact_gaps(facts, None) == {GAP.format(fact)}
        assert pb.fact_gaps(facts, pb.Run("crucible", "k")) == set()  # the crucible runner states them


def test_a_stated_fact_drops_only_its_own_gap():
    facts = {"eib": set(), "assign_task": {"USERID", "FACILITY", "SCRNHT/SCRNWD"}, "assign_region": set()}
    u, f, s = (GAP.format(x) for x in ("USERID", "FACILITY", "SCRNHT/SCRNWD"))
    assert pb.fact_gaps(facts, pb.Run("equivalence", "c", userid=True)) == {f, s}
    assert pb.fact_gaps(facts, pb.Run("equivalence", "c", termid=True)) == {u, s}
    assert pb.fact_gaps(facts, pb.Run("equivalence", "c", screen=True)) == {u, f}
    assert pb.fact_gaps(facts, pb.Run("equivalence", "c", termid=True, userid=True, screen=True)) == set()


def test_the_scenario_rules_hold_for_a_whole_case(tmp_path):
    """Every scenario must state the fact (the case's value is the default); an empty value or a screen with no termid
    states nothing."""
    cases = tmp_path / "cases"
    sc = [{"name": "a"}, {"name": "b"}]
    _case = _case_writer(cases)
    _case("top", "t", termid="T1", userid="U", screen=[24, 80], scenarios=sc)
    _case("each", "e", scenarios=[{**x, "termid": "T1", "userid": "U", "screen": [24, 80]} for x in sc])
    _case("part", "p", termid="T1", scenarios=[{"name": "a", "userid": "U", "screen": [1, 2]}, {"name": "b"}])
    _case("noterm", "n", userid="U", screen=[24, 80], scenarios=sc)
    _case("empty", "m", termid="", userid="", screen=[], scenarios=sc)
    runs = pb.equivalence_runs(cases)
    got = {}
    for c, f in (("top", "t"), ("each", "e"), ("part", "p"), ("noterm", "n"), ("empty", "m")):
        r = runs[("k", f"src/{f}.cbl")][0]
        got[c] = (bool(r.termid), r.userid, r.screen)
    assert got == {
        "top": (True, True, True),
        "each": (True, True, True),
        "part": (True, False, False),
        "noterm": (False, True, False),
        "empty": (False, False, False),
    }


def _case_writer(cases: Path):
    import json

    def write(name: str, stem: str, **fields) -> None:
        path = cases / name / "case.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        body = {"corpus": "k", "program": stem.upper(), "program_source": f"src/{stem}.cbl", **fields}
        path.write_text(json.dumps(body), encoding="utf-8")

    return write


def test_the_harness_emits_each_stated_fact_on_both_sides():
    src = read_source(HERE.parents[0] / "tools" / "equivalence_cics.py").text
    for needle in (
        "GGCICS_FACILITY=",  # stub: termid
        "GGCICS_USERID=",
        "GGCICS_SCREEN=",
        "withTermidIfStated(",  # det port
        "task.withUserid(",
        "task.withScreen(",
    ):
        assert needle in src, needle


def test_case_states_is_the_flag_set_the_runs_carry(tmp_path):
    case = {"termid": "T1", "scenarios": [{"name": "a", "userid": "U", "startcode": "TD"}, {"name": "b"}]}
    assert pb.case_states(case) == {
        "startcode": False, "termid": True, "userid": False, "screen": False, "rcode": False,
    }  # fmt: skip
    assert not any(pb.case_states({}).values())


def test_unstated_facts_drops_each_stated_fact_for_every_option():
    """The evidence report's list and the gap list are one rule (whole class: each option, each stating flag)."""
    every = {"eib": {"EIBRCODE", "EIBCPOSN"}, "assign_task": {"STARTCODE", "USERID", "FACILITY", "SCRNHT/SCRNWD"}}
    every["assign_region"] = set()
    allflags = pb.Run("equivalence", "c", startcode=True, termid=True, userid=True, screen=True, rcode=True)
    assert pb.unstated_facts(every, allflags) == {"eib": ["EIBCPOSN"], "assign_task": []}
    assert pb.unstated_facts(every, pb.Run("equivalence", "c")) == {
        "eib": ["EIBCPOSN", "EIBRCODE"],
        "assign_task": ["FACILITY", "SCRNHT/SCRNWD", "STARTCODE", "USERID"],
    }
    assert pb.unstated_facts(every, None)["assign_task"] == ["FACILITY", "SCRNHT/SCRNWD", "STARTCODE", "USERID"]
    for flag, fact in (
        ("startcode", "STARTCODE"),
        ("termid", "FACILITY"),
        ("userid", "USERID"),
        ("screen", "SCRNHT/SCRNWD"),
    ):
        left = pb.unstated_facts(every, pb.Run("equivalence", "c", **{flag: True}))["assign_task"]
        assert fact not in left and len(left) == 3, flag
    assert pb.fact_gaps(every, allflags) == {"fact: EIBCPOSN (no harness states it)"}


def test_the_evidence_report_drops_what_the_chosen_case_states(monkeypatch):
    import evidence_report as er

    src = read_source(HERE.parents[0] / "tools" / "evidence_report.py").text
    assert "pb.unstated_facts(" in src and "pb.case_states(" in src
    assert er.pb is pb

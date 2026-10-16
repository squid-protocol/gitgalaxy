"""#4725 readiness report: the ranking is cics_census.blockers' ranking, the render is deterministic, the ladder counts
add up, and a callee with holes keeps a whole-translated caller out of the whole count."""

import copy
import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import cics_census as cc  # tests/tools/cics_census.py
import readiness_report as rr  # tests/tools/readiness_report.py

FIXTURE_REPORTS = Path(__file__).resolve().parents[1] / "fixtures" / "evidence_report"


@pytest.fixture(autouse=True)
def _snapshot_reports(monkeypatch):
    """#5206: the evidence report is published on `generated`, not committed; these tests read a frozen snapshot."""
    monkeypatch.setattr(rr, "REPORTS", FIXTURE_REPORTS)


def prog(name, level="L0", gaps=(), whole=None, refused=None, nxt=()):
    whole = (not gaps) if whole is None else whole
    return {
        "program": name,
        "level": level,
        "next": list(nxt),
        "assumptions": {"named_by_commands": [{"id": "X1", "status": "ASSUMED", "area": "CICS"}]},
        "translation": {"whole": whole, "refused": refused, "gap_classes": list(gaps)},
    }


def test_every_burned_estate_builds_and_ladder_adds_up():
    rep = rr.build()
    assert rep["estates"]
    for m in rep["estates"].values():
        lad = m["ladder"]
        assert sum(lad["levels"].values()) == lad["programs"]
        assert lad["translated_whole"] + lad["with_holes"] + lad["refused"] == lad["programs"]
        assert sum(m["eras"].values()) == lad["programs"]


def test_ranking_equals_the_blockers_tool():
    for name in rr.estates():
        report = json.loads((FIXTURE_REPORTS / name / "report.json").read_text(encoding="utf-8"))
        rows = {(name, p["program"]): {"gap_classes": p["translation"]["gap_classes"]} for p in report["programs"]}
        want = [(g["gap"], g["only"], g["one_away"], g["touched"]) for g in cc.blockers(rows)["gaps"]]
        got = rr.rules_to_land(report["programs"], name, {}, top=0)["ranked"]
        assert [(g["gap"], g["only"], g["one_away"], g["touched"]) for g in got] == want


def test_render_is_deterministic():
    assert rr.render() == rr.render()
    assert json.dumps(rr.build(), sort_keys=True) == json.dumps(rr.build(), sort_keys=True)


def test_ladder_counts_whole_holes_refused_and_callee_holes():
    progs = [
        prog("A", "L2"),
        prog("B", "L1", nxt=["its det port equal on every scenario of c: B CALLs C, which has holes"]),
        prog("C", "L0", gaps=["CALL X", "EXEC CICS GETMAIN"]),
        prog("D", "L0", gaps=["missing copybook Q"], refused="missing copybook Q"),
    ]
    lad = rr.ladder(progs)
    assert (lad["translated_whole"], lad["with_holes"], lad["refused"]) == (2, 1, 1)
    assert lad["whole_with_callee_holes"] == 1
    assert lad["executed_equivalent_or_above"] == 1
    assert lad["refusal_reasons"] == {"missing copybook Q": 1}


def test_rules_rank_by_programs_made_whole_with_era_mix():
    progs = [prog("A", gaps=["g1"]), prog("B", gaps=["g1"]), prog("C", gaps=["g2"]), prog("D", gaps=["g1", "g2"])]
    r = rr.rules_to_land(progs, "e", {"A": "2", "B": "3"})
    assert [g["gap"] for g in r["ranked"]] == ["g1", "g2"]
    assert r["ranked"][0]["only"] == 2 and r["ranked"][0]["only_by_era"] == {"2": 1, "3": 1}
    assert r["ranked"][1]["only"] == 1 and r["ranked"][1]["one_away"] == 1  # D is one rule away
    assert r["ranked"][1]["only_by_era"] == {"none": 1}


def test_an_estate_with_no_gaps_and_no_eras():
    m = rr.rules_to_land([prog("A", "L3")], "e", {})
    assert m["ranked"] == [] and m["classes"] == 0
    assert rr.era_of({}) == {}


def test_previous_run_delta():
    old = rr.build()
    new = copy.deepcopy(old)
    name = next(iter(new["estates"]))
    new["estates"][name]["ladder"]["translated_whole"] += 1
    ranked = new["estates"][name]["rules_to_land"]["ranked"]
    if ranked:
        ranked[0]["only"] += 5
    d = rr.delta(old, new)
    assert d[name]["ladder"]["translated_whole"][1] == d[name]["ladder"]["translated_whole"][0] + 1
    assert all(not v["ladder"] and not v["rules"] for k, v in d.items() if k != name)
    assert "Since the previous run" in rr.render(new, old)
    other = {"estates": {}}
    assert rr.delta(other, new)[name] == {"new_estate": True}


def test_unknown_estate_is_refused():
    with pytest.raises(SystemExit):
        rr.main(["no-such-estate"])


def test_main_json_round_trips(tmp_path):
    out = tmp_path / "r.json"
    assert rr.main(["--json", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == json.loads(json.dumps(rr.build(), sort_keys=True))

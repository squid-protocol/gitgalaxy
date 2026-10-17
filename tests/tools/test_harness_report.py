"""harness_report (#4493): coverage, run status, input generation and blockers-as-fixes, from proof_blockers' result.
Fixture cases / corpora under tmp_path; no corpus, translator or sweep needed."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness_report as hr
import proof_blockers as pb
import test_proof_blockers as tpb


def burned(res):
    """The fixture corpus is not a burned name: mark its programs burned, as proof_blockers does for a real one."""
    for p in res["programs"]:
        p["burned"] = True
    return res


def fixture(tmp_path):
    cases, corpora, cru, det_baseline, rows = tpb.setup(tmp_path)
    for c, n in (("c-known", 4), ("c-cov", 2), ("c-taskn", 5), ("c-assign", 3), ("c-proven", 6)):
        f = cases / c / "case.json"
        d = json.loads(f.read_text())
        d["scenarios"] = [{"name": f"s{i}"} for i in range(n)]
        f.write_text(json.dumps(d))
    tpb.evidence(cases, "c-known", 1, 1)  # so that leaving the baseline proves it, as in a real fix
    return cases, corpora, cru, det_baseline, rows


def proof(cases, corpora, cru, det_baseline, rows):
    return burned(pb.proof_blockers(rows, [corpora], cases_dir=cases, crucible_dir=cru, det_baseline=det_baseline))


def test_coverage_and_status_counts(tmp_path):
    cases, *rest = fixture(tmp_path)
    rep = hr.build(proof(cases, *rest), "x", cases)
    c = rep["coverage"]
    assert (c["programs"], c["proven"]) == (9, 1)
    assert c["with_case"] == 8 and c["with_case_pct"] == 88.9  # NOCASE has none
    assert sum(rep["status_counts"].values()) == 9
    by = {Path(r["program"]).stem: r for r in rep["programs"]}
    assert by["PROVEN"]["status"] == "proven" and by["NOCASE"]["status"] == hr.NOT_ATTEMPTED
    assert by["KNOWN"]["status"] == hr.COULDNT_RUN and by["COV"]["status"] == hr.COVERAGE_OPEN
    assert c["paragraphs"]["live"] > 0 and c["cases_measured"] >= 1


def test_each_non_proven_program_is_under_exactly_one_blocker(tmp_path):
    cases, *rest = fixture(tmp_path)
    rep = hr.build(proof(cases, *rest), "x", cases)
    listed = [p for b in rep["blockers"] for p in b["programs"]]
    assert len(listed) == len(set(listed))
    assert sorted(listed) == sorted(r["program"] for r in rep["programs"] if r["gaps"])
    top = rep["blockers"][0]
    assert top["tests_unlocked"] == max(b["tests_unlocked"] for b in rep["blockers"])
    assert all(b["fix"] and b["programs"] for b in rep["blockers"])


def test_unlock_prediction_matches_a_rerun_after_the_fix(tmp_path):
    cases, corpora, cru, det_baseline, rows = fixture(tmp_path)
    before = hr.build(proof(cases, corpora, cru, det_baseline, rows), "x", cases)
    known = next(b for b in before["blockers"] if b["gap"].startswith("known unproven"))
    assert known["tests_unlocked"] == 4 and known["programs_unlocked"] == 1

    def proven_tests(rep):
        return sum(r["tests"] for r in rep["programs"] if r["status"] == hr.PROVEN)

    # fix the blocker: the case leaves det_sweep_baseline.json
    after = hr.build(proof(cases, corpora, cru, {}, rows), "x", cases)
    gained = proven_tests(after) - proven_tests(before)
    assert gained >= known["tests_unlocked"]
    newly = {r["program"] for r in after["programs"] if r["status"] == hr.PROVEN} - {
        r["program"] for r in before["programs"] if r["status"] == hr.PROVEN
    }
    assert newly == set(known["programs"]) and gained == known["tests_unlocked"]
    assert all(b["gap"] != known["gap"] for b in after["blockers"])


def test_a_program_with_two_gaps_unlocks_nothing_until_both_go(tmp_path):
    cases, *rest = fixture(tmp_path)
    rep = hr.build(proof(cases, *rest), "x", cases)
    assign = next(r for r in rep["programs"] if r["program"].endswith("ASSIGN.cbl"))
    assert len(assign["gaps"]) == 2
    mine = next(b for b in rep["blockers"] if assign["program"] in b["programs"])
    assert mine["tests_unlocked"] == 0 and mine["programs_unlocked"] == 0
    assert mine["then_needs"][assign["program"]] == [g for g in assign["gaps"] if g != mine["gap"]]
    assert "also needs" in hr.markdown(rep)


def test_input_generation_classes():
    case = {"datasets": {"A": {"input": "@generate", "generate": {"copybook": "a.cpy", "record": "R", "records": 5}},
                         "B": {"input": "data/b.dat"}, "C": {}},
            "scenario_generate": {"count": 24}}  # fmt: skip
    i = hr.input_generation(case)
    assert [g["dataset"] for g in i["generated"]] == ["A"] and i["shipped"] == ["B"] and i["skipped"] == ["C"]
    assert i["scenarios_generated"] and hr.scenario_count(case) == 24
    assert hr.input_generation({}) == {"generated": [], "shipped": [], "skipped": [], "scenarios_generated": False}


def test_non_burned_programs_are_counted_never_named(tmp_path):
    cases, *rest = fixture(tmp_path)
    res = proof(cases, *rest)
    for p in res["programs"][:2]:
        p["burned"] = False
    names = [p["program"] for p in res["programs"][:2]]
    rep = hr.build(res, "x", cases)
    assert rep["not_listed"]["non_burned_programs"] == 2
    text = json.dumps(rep) + hr.markdown(rep)
    assert not any(n in text for n in names)


def test_empty_estate_and_write(tmp_path):
    rep = hr.build({"programs": [], "gaps": []}, "none", tmp_path)
    assert rep["coverage"]["programs"] == 0 and rep["coverage"]["proven_pct"] is None
    assert "None: every program is proven." in hr.markdown(rep)
    cases, *rest = fixture(tmp_path / "f")
    paths = hr.write_report(proof(cases, *rest), tmp_path / "out", "est", cases)
    assert json.loads(paths["json"].read_text())["schema_version"] == hr.SCHEMA_VERSION
    assert "## Blockers (highest value first)" in paths["md"].read_text()

"""proof_blockers: the proof-level ranking over the programs a survey translates WHOLE -- which proof subject runs
each, the verdict sources (sweep, det_sweep_baseline, CI's ratchet, Db2), coverage, runtime facts, and the ranking.
Fixture cases / crucible / corpora under tmp_path; no corpus, translator or sweep needed."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proof_blockers as pb


def fixed(*code: str) -> str:
    return "\n".join(f"{i * 100:06d} {c}" for i, c in enumerate(code, 1)) + "\n"


CICS = fixed("PROCEDURE DIVISION.", "    EXEC CICS RETURN END-EXEC.")
TASKN = fixed("PROCEDURE DIVISION.", "    MOVE EIBTASKN TO WS-T", "    EXEC CICS RETURN END-EXEC.")
ASSIGN = fixed("PROCEDURE DIVISION.", "    EXEC CICS ASSIGN APPLID(A) USERID(U) END-EXEC.")
BATCH = fixed("PROCEDURE DIVISION.", "    DISPLAY 'HI'", "    STOP RUN.")


def write(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data))
    return path


def case(cases: Path, name: str, corpus: str, prog: str, **extra) -> None:
    write(cases / name / "case.json", {"corpus": corpus, "program": Path(prog).stem.upper(), "program_source": prog,
                                       **extra})  # fmt: skip


def evidence(cases: Path, name: str, covered: int, live: int, bc: int = 1, bt: int = 1) -> None:
    write(cases / name / "evidence.json", {"coverage": {"paragraphs": {"covered": covered, "live": live},
                                                        "branches": {"covered": bc, "total": bt}}})  # fmt: skip


def whole(prog: str) -> dict:
    return {"program": prog, "statements": 5, "translated": 5, "holes": []}


def setup(tmp_path: Path):
    cases, corpora, cru = tmp_path / "cases", tmp_path / "corpora", tmp_path / "crucible"
    files = {"a/PROVEN.cbl": CICS, "a/NOCASE.cbl": CICS, "a/DB2.cbl": CICS, "a/KNOWN.cbl": CICS, "a/COV.cbl": CICS,
             "a/TASKN.cbl": TASKN, "a/ASSIGN.cbl": ASSIGN, "a/BATCH.cbl": BATCH, "a/HOLEY.cbl": CICS,
             "a/LINKED.cbl": CICS, "a/DIFF.cbl": CICS}  # fmt: skip
    for rel, text in files.items():
        write(corpora / "estate" / rel, text)
    case(
        cases, "c-proven", "estate", "a/PROVEN.cbl", programs=[{"program": "LINKED", "program_source": "a/LINKED.cbl"}]
    )
    evidence(cases, "c-proven", 3, 3)
    case(cases, "c-db2", "estate", "a/DB2.cbl", db2={})
    case(cases, "c-known", "estate", "a/KNOWN.cbl")
    case(cases, "c-cov", "estate", "a/COV.cbl")
    evidence(cases, "c-cov", 2, 3, 1, 4)
    case(cases, "c-taskn", "estate", "a/TASKN.cbl")
    evidence(cases, "c-taskn", 1, 1)
    case(cases, "c-assign", "estate", "a/ASSIGN.cbl")
    evidence(cases, "c-assign", 1, 1)
    case(cases, "c-diff", "estate", "a/DIFF.cbl")
    det_baseline = {"c-known": {"issue": "#1", "why": "a known cause"}}
    rows = {("estate", p): whole(p) for p in files}
    rows[("estate", "a/HOLEY.cbl")] = {"program": "a/HOLEY.cbl", "statements": 5, "translated": 4, "holes": ["x"]}
    return cases, corpora, cru, det_baseline, rows


def run(tmp_path, **kw):
    cases, corpora, cru, det_baseline, rows = setup(tmp_path)
    return pb.proof_blockers(rows, [corpora], cases_dir=cases, crucible_dir=cru, det_baseline=det_baseline, **kw)


def gaps_of(res, stem):
    return next(p["gaps"] for p in res["programs"] if Path(p["program"]).stem == stem)


def test_each_gap_class_from_its_source(tmp_path):
    res = run(tmp_path)
    assert gaps_of(res, "PROVEN") == [] and gaps_of(res, "LINKED") == []  # a LINKed program is run by the case
    assert gaps_of(res, "NOCASE") == ["no case"]
    assert gaps_of(res, "DB2") == ["not proven in CI: Db2 case (det-sweep runs --skip-db2)"]
    assert gaps_of(res, "KNOWN") == ["known unproven: #1"]
    assert gaps_of(res, "COV") == ["coverage: live paragraphs no scenario runs"]
    assert gaps_of(res, "TASKN") == ["fact: EIBTASKN (no harness states it)"]
    assert gaps_of(res, "ASSIGN") == ["fact: ASSIGN APPLID/SYSID (the case states no region)",
                                      "fact: ASSIGN USERID (no equivalence case states it)"]  # fmt: skip
    assert gaps_of(res, "DIFF") == ["coverage: unknown (no sweep, no evidence record)"]
    stems = {Path(p["program"]).stem for p in res["programs"]}
    assert "BATCH" not in stems and "HOLEY" not in stems  # not CICS / not whole
    assert res["not_cics"] == 1
    assert (res["whole"], res["proven"]) == (9, 2)


def test_branches_and_all_programs(tmp_path):
    res = run(tmp_path, branches=True, only_cics=False)
    assert "coverage: branch outcomes no scenario runs" in gaps_of(res, "COV")
    assert gaps_of(res, "BATCH") == ["no case"]


def test_a_sweep_overrides_the_ratchet_and_names_the_diff(tmp_path):
    sweep = tmp_path / "sweep"
    write(sweep / "sweep.json", {"det": {
        "c-diff": {"proved": False, "coverage": "not proven; 3 scenarios cover 3/3 paragraphs and 1/2 branches"},
        "c-db2": {"proved": True, "coverage": "proven on 3 scenarios, covering 3/3 paragraphs and 2/2 branches",
                  "translated": "5/5"},
        "c-known": {"proved": False, "coverage": ""},
    }})  # fmt: skip
    write(sweep / "det" / "c-diff" / "proof" / "report.json", {"outputs": {"s1": {"diffs": [
        {"event": 3, "kind": "RETURN", "fields": [{"field": "commarea.X-Y", "cobol": 1, "java": 2}]}]}}})  # fmt: skip
    res = run(tmp_path, sweeps=pb.load_sweeps([sweep]))
    assert gaps_of(res, "DIFF") == ["scenario differs: RETURN commarea"]
    assert gaps_of(res, "DB2") == []
    assert gaps_of(res, "KNOWN") == ["known unproven: #1"]
    known = next(p for p in res["programs"] if p["program"].endswith("KNOWN.cbl"))
    assert "a known cause" in known["detail"]["known unproven: #1"]


def test_the_case_with_fewest_gaps_speaks_for_a_program(tmp_path):
    cases, corpora, cru, det_baseline, rows = setup(tmp_path)
    case(cases, "c-cov-2", "estate", "a/COV.cbl")
    evidence(cases, "c-cov-2", 3, 3)
    res = pb.proof_blockers(rows, [corpora], cases_dir=cases, crucible_dir=cru, det_baseline=det_baseline)
    cov = next(p for p in res["programs"] if p["program"].endswith("COV.cbl"))
    assert cov["gaps"] == [] and cov["case"] == "c-cov-2"


def test_crucible_programs_rank_apart(tmp_path):
    cases, corpora, cru, det_baseline, rows = setup(tmp_path)
    write(cru / "baseline.json", {"cells": {
        "k-fail/s1/java-ported": {"status": "fail", "reason": "task 1 (T1) event 2: WRITEQ-TS expected, got RETURN"},
        "k-noport/s1/java-ported": {"status": "fail", "reason": "no port of any of its programs"}}})  # fmt: skip
    write(cru / "coverage.json", {"programs": {
        "k-ok/OKP": {"live": 1, "scenarios": {"s1": {"units": ["MAIN"]}}},
        "k-fail/FAILP": {"live": 1, "scenarios": {"s1": {"units": ["MAIN"]}}},
        "k-noport/NOP": {"live": 1, "scenarios": {}}}})  # fmt: skip
    for c, p in (("k-ok", "OKP"), ("k-fail", "FAILP")):
        (cru / "ports" / c / p).mkdir(parents=True)
    for c, p in (("k-ok", "OKP"), ("k-fail", "FAILP"), ("k-noport", "NOP")):
        rel = f"cases/trap/{c}/src/{p}.cbl"
        write(corpora / "cics-crucible" / rel, CICS)
        rows[("cics-crucible", rel)] = whole(rel)
    res = pb.proof_blockers(rows, [corpora], cases_dir=cases, crucible_dir=cru, det_baseline=det_baseline)
    assert res["whole"] == 9  # the estates' count is unchanged
    assert (res["crucible"]["whole"], res["crucible"]["proven"]) == (3, 1)
    assert gaps_of(res, "NOP") == ["no det port (crucible)"]
    assert gaps_of(res, "FAILP")[0].startswith("scenario differs: WRITEQ-TS expected")


def test_rank_counts_only_and_one_away_split_burned():
    progs = {("CardDemo", "A"): (True, {"g1"}), ("x", "B"): (False, {"g1"}), ("x", "C"): (False, {"g1", "g2"}),
             ("x", "D"): (False, set())}  # fmt: skip
    r = pb.rank(progs)
    g1 = next(g for g in r["gaps"] if g["gap"] == "g1")
    assert (g1["only"], g1["only_burned"], g1["only_non_burned"], g1["one_away"], g1["touched"]) == (2, 1, 1, 1, 3)
    assert (r["whole"], r["proven"], r["proven_non_burned"]) == (4, 1, 1)


def test_facts_are_names_only():
    f = pb.facts_needed(fixed("    MOVE EIBTASKN TO A", "    MOVE EIBCALEN TO B",
                              "    EXEC CICS ASSIGN SYSID(S) SCRNHT(H) END-EXEC."))  # fmt: skip
    assert f == {"eib": {"EIBTASKN"}, "assign_task": {"SCRNHT/SCRNWD"}, "assign_region": {"SYSID"}}


def test_cli_prints_the_totals(tmp_path, capsys, monkeypatch):
    cases, corpora, cru, det_baseline, rows = setup(tmp_path)
    survey = tmp_path / "s" / "main-b" / "survey.json"
    write(survey, {"estate": [r for (c, _), r in rows.items()]})
    monkeypatch.setattr(pb, "CASES", cases)
    monkeypatch.setattr(pb, "CRUCIBLE", cru)
    monkeypatch.setattr(pb, "DET_BASELINE", write(tmp_path / "det_sweep_baseline.json", {"det": det_baseline}))
    assert pb.main([str(tmp_path / "s"), "--label", "main", "--corpora", str(corpora), "--no-census"]) == 0
    out = capsys.readouterr().out
    assert "estates: translated whole 9 (non-burned 9); proven 2 (non-burned 2)" in out
    assert "no case" in out

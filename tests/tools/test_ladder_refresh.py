"""ladder_refresh: case validation, pin-test discovery, the table, and the chain's order (fake runner, no sweep)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ladder_refresh as lr


def test_unknown_and_non_burned_cases_are_refused(tmp_path, monkeypatch):
    fake = tmp_path / "eq"
    (fake / "census-x").mkdir(parents=True)
    (fake / "census-x" / "case.json").write_text(json.dumps({"corpus": "some-census-repo", "program": "X"}))
    (fake / "burned-y").mkdir()
    (fake / "burned-y" / "case.json").write_text(json.dumps({"corpus": "ZECS", "program": "Y"}))
    monkeypatch.setattr(lr, "EQUIVALENCE", fake)
    out = lr.case_problems(["nope", "census-x", "burned-y"])
    assert len(out) == 2
    assert "no such case" in out[0] and "not a burned estate" in out[1]


def test_real_burned_case_is_accepted():
    assert lr.case_problems(["cbsa-crdtagy1", "carddemo-cbpaup0c"]) == []


def test_pin_tests_match_case_and_program_whole_words(tmp_path, monkeypatch):
    root = tmp_path
    (root / "tests" / "equivalence").mkdir(parents=True)
    (root / "tests" / "equivalence" / "t.py").write_text("CRDTAGY1")
    (root / "tests" / "a.py").write_text("x = 'cbsa-crdtagy1'")
    (root / "tests" / "b.py").write_text("y = 'crdtagy1'")  # the program, any case
    (root / "tests" / "c.py").write_text("z = 'CRDTAGY10'")  # a different program
    (root / "tests" / "d.py").write_text("w = 'cbsa-crdtagy1-extra'")  # a different case
    monkeypatch.setattr(lr, "program_of", lambda case: "CRDTAGY1")
    assert lr.pin_tests(["cbsa-crdtagy1"], root) == ["tests/a.py", "tests/b.py"]


def test_table_rows_improved_equal_new_unproven():
    t = lr.table([
        ("a", (9, 10, 4, 5), (10, 10, 5, 5), "proven"),
        ("b", (1, 2, 1, 2), (1, 2, 1, 2), "proven"),
        ("c", None, (3, 4, 0, 0), "proven"),
        ("d", (1, 2, 1, 2), None, "NOT PROVEN"),
    ])  # fmt: skip
    lines = t.splitlines()
    assert len(lines) == 6
    assert "| a | 90.0 (9/10) | 100.0 (10/10) | 80.0 (4/5) | 100.0 (5/5) | proven |" in lines
    assert "| c | - | 75.0 (3/4) | - | n/a (0/0) | proven |" in lines
    assert "| d | 50.0 (1/2) | - | 50.0 (1/2) | - | NOT PROVEN |" in lines


def _sweep(work: Path, proved: bool) -> None:
    work.mkdir(parents=True, exist_ok=True)
    cov = "proven on 3 scenarios, covering 5/5 paragraphs and 2/3 branches"
    row = {"proved": proved, "coverage": cov if proved else ""}
    (work / "sweep.json").write_text(json.dumps({"det": {"cbsa-crdtagy1": row}}))


def test_chain_order_and_evidence_only_with_record(tmp_path, monkeypatch):
    calls = []

    def runner(argv):
        calls.append(argv)
        if "proof_sweep.py" in " ".join(argv):
            _sweep(tmp_path, True)
        return 0

    monkeypatch.setattr(lr, "has_record", lambda c: True)
    rc, rows = lr.chain(["cbsa-crdtagy1"], tmp_path, runner=runner, python="py")
    assert rc == 0
    joined = [" ".join(c) for c in calls]
    assert "proof_sweep.py" in joined[0] and "--faults all" in joined[0] and "--det-only" in joined[0]
    assert "det_coverage_ledger.py update" in joined[1]
    assert "evidence.py prove cbsa-crdtagy1" in joined[2]
    assert "pytest" in joined[3] and "test_harness_report.py" in joined[3]
    assert rows[0][2] == (5, 5, 2, 3) and rows[0][3] == "proven"

    calls.clear()
    monkeypatch.setattr(lr, "has_record", lambda c: False)
    lr.chain(["cbsa-crdtagy1"], tmp_path, runner=runner, python="py", skip_tests=True)
    assert not any("evidence.py" in " ".join(c) for c in calls)


def test_unproven_case_stops_the_chain(tmp_path):
    calls = []

    def runner(argv):
        calls.append(argv)
        _sweep(tmp_path, False)
        return 0

    rc, rows = lr.chain(["cbsa-crdtagy1"], tmp_path, runner=runner, python="py")
    assert rc == 1 and len(calls) == 1 and rows[0][3] == "NOT PROVEN"

"""#5133: the CI critical path -- the ground-truth job in 2 parts and the advisory evidence deltas in their own job.

`ground-truth` and `full-suite` are required checks (the ruleset names them), so each stays one job that aggregates its
parts. The parts must together cover everything the single job ran, and nothing advisory may hold the required check back.
"""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _jobs(name):
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))["jobs"]


def _steps(job):
    return {s.get("name"): s for s in job["steps"]}


def test_ground_truth_is_the_aggregate_of_its_parts():
    jobs = _jobs("mainframe-ground-truth.yml")
    assert "ground-truth" in jobs and "ground-truth-part" in jobs
    assert "ground-truth-part" in jobs["ground-truth"]["needs"]
    assert "ground-truth" in jobs["publish-history"]["needs"] or jobs["publish-history"]["needs"] == "ground-truth"
    publish = jobs["publish-history"]
    assert "ground-truth-part" in publish["needs"]  # #5176: a tested-tree skip uploads no history artifact
    assert "needs.ground-truth-part.result == 'success'" in publish["if"]
    assert "name" not in jobs["ground-truth"]  # the check is named by its key: `ground-truth`


def test_the_parts_partition_tests_cobol_mainframe():
    part = _jobs("mainframe-ground-truth.yml")["ground-truth-part"]
    include = part["strategy"]["matrix"]["include"]
    assert [i["group"] for i in include] == [1, 2]
    assert part["strategy"]["fail-fast"] is False
    carved = [
        "tests/cobol_mainframe/test_evidence_components.py",
        "tests/cobol_mainframe/test_det_nondigit_zoned.py",
    ]
    assert all((ROOT / f).is_file() for f in carved)
    rest, only = (i["tests"].split() for i in include)
    assert rest == ["tests/cobol_mainframe/", *(f"--ignore={f}" for f in carved)]
    assert only == carved
    run = _steps(part)["Full-corpus differential and answer-key tests"]["run"]
    pytest_line = next(ln for ln in run.splitlines() if "-m pytest" in ln)
    assert "${{ matrix.tests }}" in pytest_line and "tests/cobol_mainframe" not in pytest_line


def test_ledger_gate_and_history_stay_in_part_1_only():
    steps = _steps(_jobs("mainframe-ground-truth.yml")["ground-truth-part"])
    for name in (
        "Gate against the ground-truth ledger",
        "Restore the published history from the generated branch",
        "Keep the history for the publish job",
    ):
        assert "matrix.group == 1" in steps[name]["if"], name


def test_evidence_deltas_is_advisory_and_off_the_required_check():
    jobs = _jobs("smoke-test.yml")
    deltas = jobs["evidence-deltas"]
    assert deltas["continue-on-error"] is True
    assert "evidence-deltas" not in jobs["full-suite"]["needs"]
    assert not any("evidence_report" in str(s.get("run")) for s in jobs["full-suite-part"]["steps"])
    assert any("evidence_report.py --deltas" in str(s.get("run")) for s in deltas["steps"])


def test_every_artifact_download_waits_on_a_job_that_can_upload_it():
    """#5176: a download job gated only on an aggregate that passes when the uploader was skipped fails on a green run."""
    for path in sorted(WORKFLOWS.glob("*.yml")):
        jobs = yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"]
        text = path.read_text(encoding="utf-8")
        if "skip_tested_tree" not in text:
            continue
        for name, job in jobs.items():
            if not any("download-artifact" in str(s.get("uses", "")) for s in job.get("steps", [])):
                continue
            needs = job.get("needs", [])
            needs = [needs] if isinstance(needs, str) else needs
            uploaders = [
                n for n in jobs if any("upload-artifact" in str(s.get("uses", "")) for s in jobs[n].get("steps", []))
            ]
            gate = str(job.get("if", ""))
            assert any(
                n in needs and (f"needs.{n}.result == 'success'" in gate or "success()" in gate) for n in uploaders
            ), f"{path.name}:{name} downloads an artifact without requiring its uploader to have succeeded"

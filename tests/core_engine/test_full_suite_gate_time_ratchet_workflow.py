"""#5257: full-suite-gate.yml runs the per-test time ratchet on its Linux legs, as smoke-test.yml's parts do (#5166).

Windows and macOS legs are not held to it: the baseline's seconds are Linux CI times.
"""

from fnmatch import fnmatch
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
JOB = "full-suite-matrix"
SMOKE_TIMES_GLOB = "test-times-part-*"  # the nightly suite budget merges these (smoke-test.yml)


def _steps():
    doc = yaml.safe_load((WORKFLOWS / "full-suite-gate.yml").read_text(encoding="utf-8"))
    return doc["jobs"][JOB]["steps"]


def _step(prefix):
    hits = [s for s in _steps() if str(s.get("name", "")).startswith(prefix)]
    assert len(hits) == 1, f"expected one step named {prefix!r}, found {len(hits)}"
    return hits[0]


def test_pytest_step_writes_a_times_file_per_leg():
    times = _step("Full Suite")["env"]["GITGALAXY_TEST_TIMES"]
    for key in ("runner.temp", "matrix.os", "matrix.python-version", "matrix.part"):
        assert key in times, f"{key} missing: legs would overwrite each other or land inside the checkout"


def test_ratchet_reads_the_file_the_pytest_step_writes():
    written = _step("Full Suite")["env"]["GITGALAXY_TEST_TIMES"].split("/")[-1].split("  #")[0]
    run = _step("Per-test time ratchet")["run"]
    assert "tests/tools/time_ratchet.py check --times" in run
    assert ".test_durations" not in run  # it carries no slow marks
    assert written in run.replace("$RUNNER_TEMP/", "")


def test_ratchet_runs_after_pytest_on_linux_only():
    names = [str(s.get("name", "")) for s in _steps()]
    pytest_at = next(i for i, n in enumerate(names) if n.startswith("Full Suite"))
    ratchet_at = next(i for i, n in enumerate(names) if n.startswith("Per-test time ratchet"))
    assert ratchet_at > pytest_at
    assert _step("Per-test time ratchet")["if"] == "runner.os == 'Linux'"


def test_times_artifact_is_linux_only_and_stays_out_of_the_budget_merge():
    up = _step("Upload this leg's test times")
    assert "always()" in up["if"] and "Linux" in up["if"]
    assert not fnmatch(up["with"]["name"], SMOKE_TIMES_GLOB)
    assert "matrix.part" in up["with"]["name"]

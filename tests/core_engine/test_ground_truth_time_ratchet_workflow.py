"""#5166: mainframe-ground-truth.yml runs the per-test time ratchet, as smoke-test.yml's full-suite parts do.

smoke-test.yml ignores tests/cobol_mainframe on a pull request, so the ground-truth parts are the only PR run that times
those tests; without the ratchet an unmarked slow one reached main (#5240, #5248).
"""

from fnmatch import fnmatch
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
JOB = "ground-truth-part"
SMOKE_TIMES_GLOB = "test-times-part-*"  # the nightly suite budget merges these (smoke-test.yml, full-suite-durations)


def _steps():
    doc = yaml.safe_load((WORKFLOWS / "mainframe-ground-truth.yml").read_text(encoding="utf-8"))
    return doc["jobs"][JOB]["steps"]


def _step(prefix):
    hits = [s for s in _steps() if str(s.get("name", "")).startswith(prefix)]
    assert len(hits) == 1, f"expected one step named {prefix!r}, found {len(hits)}"
    return hits[0]


def test_pytest_step_writes_the_times_file():
    step = _step("Full-corpus differential")
    times = step["env"]["GITGALAXY_TEST_TIMES"]
    assert "matrix.group" in times, "each part writes its own times file"
    assert "runner.temp" in times, "outside the checkout, so a scan never sees it"


def test_ratchet_reads_the_file_the_pytest_step_writes():
    written = _step("Full-corpus differential")["env"]["GITGALAXY_TEST_TIMES"]
    run = _step("Per-test time ratchet")["run"]
    assert "tests/tools/time_ratchet.py check --times" in run
    # the CI times file, never the committed .test_durations (it carries no slow marks; #5166)
    assert ".test_durations" not in run
    assert written.split("/")[-1] in run, "the ratchet checks the file the pytest step wrote"


def test_ratchet_runs_after_pytest_in_a_part_the_required_check_aggregates():
    names = [str(s.get("name", "")) for s in _steps()]
    pytest_at = next(i for i, n in enumerate(names) if n.startswith("Full-corpus differential"))
    ratchet_at = next(i for i, n in enumerate(names) if n.startswith("Per-test time ratchet"))
    assert ratchet_at > pytest_at
    doc = yaml.safe_load((WORKFLOWS / "mainframe-ground-truth.yml").read_text(encoding="utf-8"))
    assert JOB in doc["jobs"]["ground-truth"]["needs"], "the required check aggregates the parts"


def test_times_artifact_stays_out_of_the_nightly_budget_merge():
    up = _step("Upload this part's test times")
    assert up.get("if") == "always()"
    assert not fnmatch(up["with"]["name"], SMOKE_TIMES_GLOB)

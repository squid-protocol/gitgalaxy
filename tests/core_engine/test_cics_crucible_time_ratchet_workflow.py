"""#5257: cics-crucible.yml runs the per-test time ratchet over the runner-tests job (sibling of #5166).

The e2e tests under tests/cics_crucible are skipped everywhere else, so this job is the only run that times them.
"""

from fnmatch import fnmatch
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
JOB = "runner-tests"
SMOKE_TIMES_GLOB = "test-times-part-*"  # the nightly suite budget merges these (smoke-test.yml)


def _doc():
    return yaml.safe_load((WORKFLOWS / "cics-crucible.yml").read_text(encoding="utf-8"))


def _steps():
    return _doc()["jobs"][JOB]["steps"]


def _index(prefix):
    hits = [i for i, s in enumerate(_steps()) if str(s.get("name", "")).startswith(prefix)]
    assert len(hits) == 1, f"expected one step named {prefix!r}, found {len(hits)}"
    return hits[0]


PYTEST_STEPS = ("The runner's own tests", "The tests that read the crucible checkout")


def test_each_pytest_step_writes_its_own_times_file_outside_the_checkout():
    files = []
    for prefix in PYTEST_STEPS:
        times = _steps()[_index(prefix)]["env"]["GITGALAXY_TEST_TIMES"]
        assert "runner.temp" in times
        files.append(times.split("/")[-1])
    assert len(set(files)) == len(files), "one file per pytest step, or the second overwrites the first"


def test_ratchet_reads_every_file_after_both_pytest_steps():
    steps = _steps()
    at = _index("Per-test time ratchet")
    assert at > max(_index(p) for p in PYTEST_STEPS)
    run = steps[at]["run"]
    assert "tests/tools/time_ratchet.py check --times" in run
    assert ".test_durations" not in run  # it carries no slow marks
    for prefix in PYTEST_STEPS:
        assert steps[_index(prefix)]["env"]["GITGALAXY_TEST_TIMES"].split("/")[-1] in run


def test_times_artifact_is_uploaded_always_and_stays_out_of_the_nightly_budget_merge():
    up = _steps()[_index("Upload this job's test times")]
    assert up.get("if") == "always()"
    assert not fnmatch(up["with"]["name"], SMOKE_TIMES_GLOB)


def test_required_check_still_aggregates_runner_tests():
    assert JOB in _doc()["jobs"]["crucible"]["needs"]

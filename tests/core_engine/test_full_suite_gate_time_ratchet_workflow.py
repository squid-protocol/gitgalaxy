# ruff: noqa: S101
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


# #5764: slowest minutes seen per (os, python) part on the gate's runs of 2026-10-14..20; a cap needs 1.3x headroom.
# windows 3.11 was 25 min as 2 parts; as 3 parts it is an estimate (~4 min setup + 2/3 of the tests): re-measure.
SLOWEST_SEEN_MIN = {
    ("windows-latest", "3.11"): 18,
    ("windows-latest", "3.12"): 19,
    ("macos-latest", "3.11"): 16,
    ("macos-latest", "3.12"): 17,
}


def _legs():
    import json
    import re

    text = (WORKFLOWS / "full-suite-gate.yml").read_text(encoding="utf-8")
    return [json.loads(m) for m in re.findall(r"\{\"os\":[^{}]*\}", text)]


def test_the_pytest_step_times_out_before_its_job_so_a_stall_keeps_its_log():
    assert _step("Full Suite")["timeout-minutes"] == "${{ matrix.step_timeout }}"
    legs = _legs()
    assert legs
    for leg in legs:
        assert leg["step_timeout"] == leg["timeout"] - 3, leg


def test_no_workflow_expression_uses_arithmetic():
    """#5764: `${{ (matrix.timeout || 30) - 3 }}` is not valid; the workflow failed to start and no job ran."""
    import re

    for path in sorted(WORKFLOWS.glob("*.yml")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith("#"):
                continue
            for expr in re.findall(r"\$\{\{(.*?)\}\}", line):
                bare = re.sub(r"'[^']*'|\"[^\"]*\"", "", expr)
                assert not re.search(r"[\w)\]]\s+[-+*/]\s+[\w(]", bare), f"{path.name}: {line.strip()}"


def test_every_leg_cap_has_headroom_over_the_slowest_seen_time():
    legs = _legs()
    assert legs
    for leg in legs:
        seen = SLOWEST_SEEN_MIN.get((leg["os"], leg["python-version"]))
        if seen:
            assert leg["timeout"] >= seen * 1.3, leg

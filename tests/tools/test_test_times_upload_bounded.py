"""#8328: a `test-times-*` artifact upload is timing telemetry. When the artifact service is down, upload-artifact retries
until the job timeout and cancels a job whose tests passed, so each such step must be non-fatal and bounded."""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
# Remaining slice (5-file cap of the #8328 PR): the same step in this workflow.
PENDING = {"mainframe-ground-truth.yml"}


def _steps():
    for path in sorted(WORKFLOWS.glob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in (doc.get("jobs") or {}).items():
            for step in job.get("steps") or []:
                uses = str(step.get("uses", ""))
                name = str((step.get("with") or {}).get("name", ""))
                if uses.startswith("actions/upload-artifact@") and name.startswith("test-times"):
                    yield path.name, job_name, step


def test_the_scan_finds_the_known_uploads():
    assert len({w for w, _, _ in _steps()}) >= 5


@pytest.mark.parametrize(
    ("workflow", "step"),
    [pytest.param(w, s, id=f"{w}:{j}") for w, j, s in _steps()],
)
def test_a_test_times_upload_is_nonfatal_and_bounded(workflow, step):
    if workflow in PENDING:
        pytest.skip("pending slice (#8328)")
    assert step.get("continue-on-error") is True
    assert 0 < int(step.get("timeout-minutes", 0)) <= 5

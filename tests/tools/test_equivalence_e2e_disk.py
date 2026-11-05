"""#7701: the Equivalence E2E db2 job frees runner disk before it loads the Db2 and oracle images (a full runner disk
killed a main run with "No space left on device")."""

from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "equivalence-e2e.yml"
STEP = "Free runner disk (#7701)"


def _job_text(job: str) -> str:
    """The text of one top-level job: from its `  name:` line to the next job."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = lines.index(f"  {job}:")
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if lines[i].startswith("  ")
            and not lines[i].startswith("   ")
            and lines[i].rstrip().endswith(":")
            and not lines[i].lstrip().startswith("#")
        ),
        len(lines),
    )
    return "\n".join(lines[start:end])


def test_db2_job_frees_disk_before_any_image_work():
    text = _job_text("db2")
    assert STEP in text
    free = text.index(STEP)
    for later in (
        "Restore the pinned Db2 image",
        "Load or pull the pinned Db2 image",
        "Load or build the oracle image",
    ):
        assert free < text.index(later), later


@pytest.mark.parametrize("path", ["/usr/share/dotnet", "/usr/local/lib/android", "/opt/ghc"])
def test_free_step_removes_unused_toolchains(path):
    text = _job_text("db2")
    step = text[text.index(STEP) :].split("\n      - name:", 1)[0]
    assert path in step
    assert "df -h" in step


@pytest.mark.parametrize("job", ["tested-tree", "plan", "shard", "equivalence-e2e"])
def test_other_jobs_do_not_pay_for_it(job):
    assert STEP not in _job_text(job)

# ruff: noqa: S101
"""#8215: an upload whose artifact is one-per-shard and is read back by a `pattern:` download carries `overwrite: true`.
After `gh run rerun --failed` a shard that failed early uploads a stub; without `overwrite` the run holds two artifacts of
the name and the download can take the stub (det sweep: 273-byte timing.json, "no result" for a shard that had passed)."""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WF = Path(__file__).resolve().parents[2] / ".github" / "workflows"
SHARDED = {
    "evidence-refresh.yml": ("db2-part-", "refresh-sweep-shard-", "refresh-records-", "refresh-detmut-"),
    "cics-crucible.yml": ("cics-crucible-shard-",),
    "det-sweep.yml": ("det-sweep-db2-", "det-sweep-"),
}


def _uploads(workflow):
    jobs = yaml.safe_load((WF / workflow).read_text(encoding="utf-8"))["jobs"]
    for job in jobs.values():
        for step in job.get("steps", []):
            if str(step.get("uses", "")).startswith("actions/upload-artifact@"):
                yield step["with"]


@pytest.mark.parametrize("workflow", sorted(SHARDED))
def test_per_shard_uploads_overwrite(workflow):
    prefixes = SHARDED[workflow]
    seen = [w for w in _uploads(workflow) if str(w["name"]).startswith(prefixes) and "${{" in str(w["name"])]
    assert seen, f"no per-shard upload found in {workflow}"
    missing = [w["name"] for w in seen if w.get("overwrite") is not True]
    assert not missing, f"{workflow}: per-shard uploads without overwrite: {missing}"

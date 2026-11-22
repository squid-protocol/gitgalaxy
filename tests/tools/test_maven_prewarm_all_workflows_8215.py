# ruff: noqa: S101
"""#8215: every job in the det sweep, CICS crucible and ports-compile workflows that restores the Maven cache fetches the
Spring Boot parent POM, retried, after the restore and before any step that runs tests. A restore-key hit may lack the
pinned parent, and each shard would then ask Central for it on its own (det sweep run 42721961353: 30 of 30 cases lost).
Equivalence E2E has its own pin test (`test_equivalence_e2e_maven_prewarm.py`)."""

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ("det-sweep.yml", "cics-crucible.yml", "ports-compile.yml")
RUNS_PYTEST = re.compile(r"(?m)^\s*(?:python3? -m )?pytest\b")
EXPECTED_JOBS = {"det-sweep.yml": 2, "cics-crucible.yml": 2, "ports-compile.yml": 1}


def _jobs_restoring_maven(name: str) -> dict[str, list[dict]]:
    jobs = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))["jobs"]
    return {
        job_name: job["steps"]
        for job_name, job in jobs.items()
        if any(s.get("id") == "maven_dependencies" for s in job.get("steps", []))
    }


@pytest.mark.parametrize("workflow", WORKFLOWS)
def test_each_maven_cache_job_prefetches_the_parent_pom_with_retry(workflow):
    jobs = _jobs_restoring_maven(workflow)
    assert len(jobs) == EXPECTED_JOBS[workflow], sorted(jobs)
    for name, steps in jobs.items():
        label = f"{workflow}:{name}"
        cache_at = [s.get("id") for s in steps].index("maven_dependencies")
        fetch = [
            (i, s)
            for i, s in enumerate(steps)
            if "spring-boot-starter-parent" in s.get("run", "") and "dependency:get" in s["run"]
        ]
        assert len(fetch) == 1, label
        at, step = fetch[0]
        assert at > cache_at, f"{label}: the fetch must follow the cache restore"
        run = step["run"]
        assert "ci_retry.sh" in run, label
        assert "cache-hit != 'true'" in step.get("if", ""), label
        assert "SpringBoot().version" in run, f"{label}: the version comes from the generated pom's pin"
        assert "*.lastUpdated" in run, f"{label}: a restored 'not found' marker must go before the fetch"
        # the checkout is a `gitgalaxy/` subdirectory in these workflows
        assert run.lstrip().startswith("cd gitgalaxy"), label
        for later in steps[:at]:
            assert not RUNS_PYTEST.search(later.get("run", "")), label  # installing pytest is not running it

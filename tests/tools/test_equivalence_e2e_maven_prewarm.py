# ruff: noqa: S101
"""#8723, #8746: every job that restores the Maven cache fetches the Spring Boot parent POM, retried, before any case
runs, so a throttled Central cannot fail a whole shard past the in-test -U retry (#8375)."""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = [
    "equivalence-e2e.yml",
    "evidence-refresh.yml",
    "det-sweep.yml",
    "cics-crucible.yml",
]


def _jobs_restoring_maven(workflow: str) -> dict[str, list[dict]]:
    path = ROOT / ".github" / "workflows" / workflow
    jobs = yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"]
    return {
        name: job["steps"]
        for name, job in jobs.items()
        if any(s.get("name", "").startswith("Cache Maven dependencies") for s in job.get("steps", []))
    }


@pytest.mark.parametrize("workflow", WORKFLOWS)
def test_there_are_maven_cache_jobs(workflow):
    assert _jobs_restoring_maven(workflow)


@pytest.mark.parametrize("workflow", WORKFLOWS)
def test_each_maven_cache_job_prefetches_the_parent_pom_with_retry(workflow):
    for name, steps in _jobs_restoring_maven(workflow).items():
        where = f"{workflow}:{name}"
        ids = [s.get("id") for s in steps]
        assert "maven_dependencies" in ids, f"{where}: the cache step needs id maven_dependencies"
        cache_at = ids.index("maven_dependencies")
        fetch = [
            (i, s)
            for i, s in enumerate(steps)
            if "spring-boot-starter-parent" in s.get("run", "") and "dependency:get" in s["run"]
        ]
        assert len(fetch) == 1, where
        at, step = fetch[0]
        assert at > cache_at, f"{where}: the fetch must follow the cache restore"
        assert "ci_retry.sh" in step["run"], where
        assert "cache-hit != 'true'" in step.get("if", ""), where
        # the version comes from the pin the generated pom uses, not a copy
        assert "SpringBoot().version" in step["run"], where
        # and it runs before the first step that runs tests
        for later in steps[:at]:
            assert "-m pytest" not in later.get("run", ""), where


def test_the_pin_the_step_reads_exists():
    from gitgalaxy.tools.cobol_to_java.java_target import SpringBoot

    assert SpringBoot().version.count(".") == 2

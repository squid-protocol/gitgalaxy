# ruff: noqa: S101
"""#8723: every Equivalence E2E job that restores the Maven cache fetches the Spring Boot parent POM, retried, before any
test runs, so a throttled Central cannot fail a whole shard past the in-test -U retry (#8375)."""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "equivalence-e2e.yml"


def _jobs_restoring_maven() -> dict[str, list[dict]]:
    jobs = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]
    return {
        name: job["steps"]
        for name, job in jobs.items()
        if any(s.get("id") == "maven_dependencies" for s in job.get("steps", []))
    }


def test_there_are_maven_cache_jobs():
    assert len(_jobs_restoring_maven()) >= 2


def test_each_maven_cache_job_prefetches_the_parent_pom_with_retry():
    for name, steps in _jobs_restoring_maven().items():
        ids = [s.get("id") for s in steps]
        cache_at = ids.index("maven_dependencies")
        fetch = [
            (i, s)
            for i, s in enumerate(steps)
            if "spring-boot-starter-parent" in s.get("run", "") and "dependency:get" in s["run"]
        ]
        assert len(fetch) == 1, name
        at, step = fetch[0]
        assert at > cache_at, f"{name}: the fetch must follow the cache restore"
        assert "ci_retry.sh" in step["run"], name
        assert "cache-hit != 'true'" in step.get("if", ""), name
        # the version comes from the pin the generated pom uses, not a copy
        assert "SpringBoot().version" in step["run"], name
        # and it runs before the first step that runs tests
        for later in steps[:at]:
            assert "pytest" not in later.get("run", ""), name


def test_the_pin_the_step_reads_exists():
    from gitgalaxy.tools.cobol_to_java.java_target import SpringBoot

    assert SpringBoot().version.count(".") == 2

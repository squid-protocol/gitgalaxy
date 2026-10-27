# ruff: noqa: S101, ARG001, E402, I001
"""#4904: unit tests for subprocess timeouts, Db2 pool deadline, and workflow timeout-minutes."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = REPO_ROOT / "tests" / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO_ROOT / "tests"))
sys.path.insert(0, str(REPO_ROOT))

import cics_crucible
import det_survey
import equivalence_common
import equivalence_db2
import equivalence_java
import mutation
import porting_loop


# --------------------------------------------------------------------------------------------------
# (1) Db2 pool wait raises by name after its deadline
# --------------------------------------------------------------------------------------------------
def test_db2_pool_deadline_raises_by_name(monkeypatch):
    """Waiting for a free Db2 database in the pool raises Db2PoolTimeoutError by name after deadline."""
    pytest.importorskip("fcntl")
    monkeypatch.setattr(equivalence_db2, "_LOCK", None)
    monkeypatch.setattr(equivalence_db2, "pool", lambda: ["GGDB_TEST"])

    # Simulate all slot locks failing with BlockingIOError
    class DummyLock:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def close(self):
            pass

    fcntl = pytest.importorskip("fcntl")  # the Db2 pool's slot locks are flock: Linux-only (no Db2 on Windows)

    def fake_flock(fh, flags):
        raise BlockingIOError("Resource temporarily unavailable")

    monkeypatch.setattr(fcntl, "flock", fake_flock)

    # Fast-forward time so we don't actually sleep 20 min in unit tests
    current_time = [1000.0]

    def fake_monotonic():
        return current_time[0]

    def fake_sleep(seconds):
        current_time[0] += 300.0  # jump forward 5 min each sleep

    monkeypatch.setattr(equivalence_db2.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(equivalence_db2.time, "sleep", fake_sleep)

    with pytest.raises(equivalence_db2.Db2PoolTimeoutError) as exc_info:
        equivalence_db2.hold_lock(timeout=600)

    assert "timed out after 600" in str(exc_info.value)
    assert "GGDB_TEST" in str(exc_info.value)


# --------------------------------------------------------------------------------------------------
# (2) Representative subprocess timeouts are turned into the tool's named failure
# --------------------------------------------------------------------------------------------------
def test_cics_crucible_container_sh_timeout(monkeypatch, tmp_path):
    """cics_crucible.Container.sh turns TimeoutExpired into RuntimeError and cleans up container."""
    removed = []

    def fake_run(cmd, *args, **kwargs):
        if "docker" in cmd and "run" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="test-container-id\n", stderr="")
        if "docker" in cmd and "exec" in cmd:
            raise subprocess.TimeoutExpired(cmd, timeout=kwargs.get("timeout", 120))
        if "docker" in cmd and "rm" in cmd:
            removed.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    box = cics_crucible.Container(tmp_path)
    assert box.id == "test-container-id"

    with pytest.raises(RuntimeError) as exc_info:
        box.sh("infinite loop task")

    assert "docker exec timed out after" in str(exc_info.value)
    # verify docker rm -f was called to remove the container
    assert any("rm" in cmd and "test-container-id" in cmd for cmd in removed)


def test_equivalence_common_docker_run_timeout(monkeypatch, tmp_path):
    """equivalence_common._docker_run turns TimeoutExpired into returncode 124 and cleans up container."""
    removed = []

    def fake_run(cmd, *args, **kwargs):
        if "docker" in cmd and "run" in cmd:
            raise subprocess.TimeoutExpired(cmd, timeout=kwargs.get("timeout", 180))
        if "docker" in cmd and "rm" in cmd:
            removed.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    proc = equivalence_common._docker_run(tmp_path, "test-image", ())
    assert proc.returncode == 124
    assert "docker run timed out after" in proc.stderr
    assert "GnuCOBOL pass" in proc.stderr
    # verify docker rm -f was called
    assert len(removed) >= 1
    assert "rm" in removed[0] and "-f" in removed[0]


def test_equivalence_java_run_direct_timeout(monkeypatch, tmp_path):
    """equivalence_java._run_direct turns TimeoutExpired into returncode 124."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "target").mkdir(parents=True, exist_ok=True)
    (project / equivalence_java.PRECOMPILED).write_text("")
    (project / equivalence_java.TEST_CLASSPATH).write_text(f"{project}/target/classes")
    (project / equivalence_java.TEST_FILE).parent.mkdir(parents=True, exist_ok=True)
    (project / equivalence_java.TEST_FILE).write_text("test")
    (project / equivalence_java.TEST_SOURCE).write_text("test")

    monkeypatch.setattr(equivalence_java, "_launcher", lambda _cp: Path("/fake/launcher.jar"))
    monkeypatch.setattr(equivalence_java, "_runner", lambda _l, _j, _cp, _s: Path("/fake/runner"))

    def fake_run(cmd, *args, **kwargs):
        raise subprocess.TimeoutExpired(cmd, timeout=kwargs.get("timeout", 180))

    monkeypatch.setattr(subprocess, "run", fake_run)

    shell = {"JAVA_HOME": "/usr/lib/jvm/java-17-openjdk-amd64", "PATH": ""}
    proc = equivalence_java._run_direct(project, "", shell)
    assert proc is not None
    assert proc.returncode == 124
    assert "java EquivalenceMain timed out after" in proc.stderr


def test_det_survey_compile_port_timeout(monkeypatch, tmp_path):
    """det_survey.compile_port turns TimeoutExpired into compiles=False with timeout error."""
    row = {"program": "TEST1"}

    def fake_run(cmd, *args, **kwargs):
        raise subprocess.TimeoutExpired(cmd, timeout=kwargs.get("timeout", 60))

    monkeypatch.setattr(subprocess, "run", fake_run)

    det_survey.compile_port(row, tmp_path, tmp_path, "fake-cp")
    assert row["compiles"] is False
    assert any("javac timed out after" in err for err in row.get("compile_errors", []))


def test_mutation_compiles_timeout(monkeypatch, tmp_path):
    """mutation.compiles turns TimeoutExpired into (False, 'javac timed out...')."""

    def fake_run(cmd, *args, **kwargs):
        raise subprocess.TimeoutExpired(cmd, timeout=kwargs.get("timeout", 60))

    monkeypatch.setattr(subprocess, "run", fake_run)

    ok, why = mutation.compiles(tmp_path, "cp", tmp_path / "out")
    assert ok is False
    assert "javac timed out after" in why


def test_porting_loop_run_timeout(monkeypatch, tmp_path):
    """porting_loop._run turns TimeoutExpired into returncode 124 and logs timeout."""
    log = tmp_path / "loop.log"

    def fake_run(cmd, *args, **kwargs):
        raise subprocess.TimeoutExpired(cmd, timeout=kwargs.get("timeout", 900))

    monkeypatch.setattr(subprocess, "run", fake_run)

    proc = porting_loop._run(["fake", "cmd"], log, timeout=10)
    assert proc.returncode == 124
    assert "command timed out after 10s: fake cmd" in proc.stderr
    assert "command timed out after 10s: fake cmd" in log.read_text(encoding="utf-8")


# --------------------------------------------------------------------------------------------------
# (3) YAML check: every job in publish.yml, mirror-tag-sync.yml, cics-crucible.yml has timeout-minutes
# --------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "rel_path",
    [
        ".github/workflows/publish.yml",
        ".github/workflows/mirror-tag-sync.yml",
        ".github/workflows/cics-crucible.yml",
    ],
)
def test_workflow_jobs_have_timeout_minutes(rel_path: str):
    """Every job in publish.yml, mirror-tag-sync.yml, and cics-crucible.yml specifies timeout-minutes."""
    workflow_file = REPO_ROOT / rel_path
    assert workflow_file.is_file(), f"workflow file {workflow_file} does not exist"
    data = yaml.safe_load(workflow_file.read_text(encoding="utf-8"))
    jobs = data.get("jobs", {})
    assert jobs, f"no jobs found in {rel_path}"

    for job_name, job_spec in jobs.items():
        assert "timeout-minutes" in job_spec, f"job {job_name!r} in {rel_path} lacks timeout-minutes"
        t = job_spec["timeout-minutes"]
        if isinstance(t, str) and t.startswith("${{ fromJSON(needs.plan.outputs.timeout)"):
            continue  # #5919: a shard job's timeout is emitted by the plan job (bounded by the planner's ceiling)
        assert isinstance(t, int), f"job {job_name!r} in {rel_path} timeout-minutes is not an integer: {t}"
        assert t > 0, f"job {job_name!r} in {rel_path} timeout-minutes must be positive: {t}"


def test_evidence_refresh_refresh_cap():
    """evidence-refresh.yml refresh job is capped at ~60 min (issue #4904)."""
    workflow_file = REPO_ROOT / ".github/workflows/evidence-refresh.yml"
    data = yaml.safe_load(workflow_file.read_text(encoding="utf-8"))
    refresh_job = data["jobs"]["refresh"]
    assert refresh_job["timeout-minutes"] == 60


def test_cics_crucible_has_image_cache():
    """cics-crucible.yml contains the GnuCOBOL image cache step from det-sweep.yml."""
    workflow_file = REPO_ROOT / ".github/workflows/cics-crucible.yml"
    content = workflow_file.read_text(encoding="utf-8")
    assert "Cache the GnuCOBOL oracle image" in content
    assert "gnucobol-image.tar" in content
    assert "gnucobol-image-${{ hashFiles('gitgalaxy/tests/equivalence/gnucobol.Dockerfile') }}" in content


# --------------------------------------------------------------------------------------------------
# (5) #5156: full-suite-gate shards are complete, and both grids agree
# --------------------------------------------------------------------------------------------------
def _full_suite_gate_text() -> str:
    return (REPO_ROOT / ".github/workflows/full-suite-gate.yml").read_text(encoding="utf-8")


def test_full_suite_gate_legs_are_planned_not_typed():
    """#5919: no hand-set leg JSON is left in the gate; the plan job emits every leg."""
    text = _full_suite_gate_text()
    assert "include='[" not in text
    assert '"splits"' not in text and '"timeout"' not in text and '"step_timeout"' not in text
    assert "suite_shard_plan.py --gate" in text


def test_full_suite_gate_planned_parts_are_complete_and_in_plan_range():
    """#5156: each (os, python) leg lists parts 1..splits once, no 3.10 leg (#3322), every cap inside the plan's range."""
    import suite_shard_plan

    legs: dict[tuple, list[int]] = {}
    for entry in suite_shard_plan.gate_plan(suite_shard_plan.load_durations())["matrix"]:
        assert entry["python-version"] != "3.10"
        assert suite_shard_plan.GATE_TIMEOUT_FLOOR <= entry["timeout"] <= suite_shard_plan.GATE_TIMEOUT_CEILING, entry
        legs.setdefault((entry["os"], entry["python-version"], entry["splits"]), []).append(entry["part"])
    assert legs
    for key, parts in legs.items():
        assert sorted(parts) == list(range(1, key[2] + 1)), key

"""#4438 item 4: referee-panel.yml is a nightly / manual run, never a PR gate, and leaks nothing it does not need to.

JVM start-up, a Maven build and the 5-minute grammar generation make the panel a poor gate; the scorecard names other
tools and its publication is on hold (owner, #4438), so the only output is a short-retention artifact.
"""

import re
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools" / "referees"))

import run_panel as R  # noqa: E402

WORKFLOW = ROOT / ".github" / "workflows" / "referee-panel.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")
DOC = yaml.safe_load(TEXT)
JOB = DOC["jobs"]["panel"]
STEPS = JOB["steps"]


def _step(name_part):
    return next(s for s in STEPS if name_part in s.get("name", ""))


def test_only_a_schedule_and_a_manual_trigger():
    on = DOC.get(True) or DOC.get("on")  # PyYAML reads the bare key `on` as True
    assert set(on) == {"schedule", "workflow_dispatch"}


def test_the_token_is_read_only():
    assert DOC["permissions"] == {"contents": "read"}
    assert "permissions" not in JOB


def test_every_action_is_pinned_to_a_sha():
    uses = [s["uses"] for s in STEPS if "uses" in s]
    assert uses
    assert all(re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", u) for u in uses), uses


def test_the_job_has_a_timeout_and_a_serial_queue():
    assert 0 < JOB["timeout-minutes"] <= 360
    assert DOC["concurrency"]["cancel-in-progress"] is False


def test_the_artifact_is_short_lived():
    up = _step("Upload the scorecard")
    assert up["uses"].startswith("actions/upload-artifact@")
    assert 1 <= up["with"]["retention-days"] <= 7
    assert up["if"] == "always()"


def test_installs_are_cached_by_hash_and_saved_before_the_run():
    restore = _step("Restore the referee installs")
    save = _step("Save the referee installs")
    assert restore["with"]["key"] == save["with"]["key"]
    assert re.fullmatch(r"referee-panel-installs-\$\{\{ hashFiles\('[^']+'\) \}\}", save["with"]["key"])
    names = [s.get("name", "") for s in STEPS]
    assert names.index(save["name"]) < names.index("Run the panel")
    installs = [s for s in STEPS if s.get("name", "").startswith("Install ") and s["name"] != "Install GitGalaxy"]
    assert len(installs) == 4
    assert all(s["if"] == "steps.referees.outputs.cache-hit != 'true'" for s in installs)


def test_no_cache_key_carries_a_run_ref_or_date():
    for s in STEPS:
        if s.get("uses", "").startswith("actions/cache"):
            assert not re.search(r"github\.(sha|run_id|run_number|ref|head_ref)|\bdate\b|\bnow\b", s["with"]["key"])


def test_referees_live_outside_the_checkout():
    assert 'echo "REFEREES_DIR=$RUNNER_TEMP/' in _step("Locate the referees")["run"]


def test_every_referee_variable_run_panel_preflights_is_exported():
    block = _step("Point the panel at the referees")["run"]
    for var in R.REFEREE_ENV.values():
        assert re.search(rf"echo \"{var}=", block), var


def test_the_run_step_runs_the_panel_outside_the_checkout():
    run = _step("Run the panel")["run"]
    assert "tests/tools/referees/run_panel.py" in run
    assert '--out "$RUNNER_TEMP/' in run  # run_panel refuses an --out inside the checkout


def test_the_upstream_refs_are_pinned():
    env = JOB["env"]
    for key in ("REFEREE_COBRIX_SHA", "REFEREE_TREESITTER_SHA", "REFEREE_MAPA_SHA"):
        assert re.fullmatch(r"[0-9a-f]{40}", env[key]), key
    assert re.fullmatch(r"\d+\.\d+\.\d+", env["REFEREE_CHE4Z_TAG"])
    assert re.fullmatch(r"\d+\.\d+\.\d+", env["REFEREE_TREESITTER_CLI"])
    assert not re.search(r"git (clone|pull)\b|--branch", TEXT), "install by fetching the pinned sha, not a moving ref"


@pytest.mark.skipif(
    sys.platform != "linux", reason="the Install Cobrix step is bash for the ubuntu runner; on Windows `bash` is WSL"
)
def test_cobrix_classpath_jars_are_copied_into_the_referee_cache(tmp_path):
    import os
    import subprocess

    run = _step("Install Cobrix")["run"]
    assert '-Dmdep.outputFile="$REFEREES_DIR/cobrix.m2.cp"' in run
    assert 'mkdir -p "$REFEREES_DIR/cobrix-lib"' in run
    assert 'cobrix-lib/*.jar | paste -sd: - > "$REFEREES_DIR/cobrix.cp"' in run
    # the copy fragment, run on a Maven-style classpath file (no trailing newline: the last jar must still be copied)
    lines = run.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.lstrip().startswith("mkdir -p") and "cobrix-lib" in ln)
    fragment = "\n".join(lines[start:])
    # relative POSIX paths: an absolute Windows path (C:\\...) holds the ':' the fragment splits on
    m2 = tmp_path / "m2"
    m2.mkdir()
    jars = [m2 / f"dep{i}.jar" for i in range(3)]
    for j in jars:
        j.write_text("")
    refs = tmp_path / "refs"
    refs.mkdir()
    (refs / "cobrix.m2.cp").write_text(":".join(f"m2/{j.name}" for j in jars))
    subprocess.run(
        ["bash", "-euo", "pipefail", "-c", fragment],
        check=True,
        cwd=tmp_path,
        env={**os.environ, "REFEREES_DIR": "refs"},
    )
    assert sorted(p.name for p in (refs / "cobrix-lib").glob("*.jar")) == [j.name for j in jars]
    cp = (refs / "cobrix.cp").read_text().strip().split(":")
    assert cp == [f"refs/cobrix-lib/{j.name}" for j in jars]

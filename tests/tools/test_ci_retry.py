"""#5048: tests/tools/ci_retry.sh and the workflow steps that use it."""

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "tests" / "tools" / "ci_retry.sh"
WORKFLOWS = REPO / ".github" / "workflows"


def _run(tmp_path, attempts, fail_times, *, cmd=None, backoff=3):
    """Run ci_retry.sh around a command that fails `fail_times` times; sleeps are logged, not slept."""
    counter, sleeps = tmp_path / "count", tmp_path / "sleeps"
    sleeper = tmp_path / "fake-sleep"
    sleeper.write_text(f'#!/bin/sh\necho "$1" >> "{sleeps}"\n')
    sleeper.chmod(0o755)
    flaky = tmp_path / "flaky"
    flaky.write_text(
        f'#!/bin/sh\necho x >> "{counter}"\n[ "$(wc -l < "{counter}")" -gt {fail_times} ] && exit 0\nexit 7\n'
    )
    flaky.chmod(0o755)
    argv = cmd or [str(flaky)]
    proc = subprocess.run(
        ["bash", str(SCRIPT), str(attempts), str(backoff), "--", *argv],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "CI_RETRY_SLEEP": str(sleeper)},
    )
    tries = len(counter.read_text().split()) if counter.exists() else 0
    slept = sleeps.read_text().split() if sleeps.exists() else []
    return proc, tries, slept


def test_first_try_success_does_not_sleep(tmp_path):
    proc, tries, slept = _run(tmp_path, 4, 0)
    assert (proc.returncode, tries, slept) == (0, 1, [])


def test_fail_then_succeed_retries_with_doubling_backoff(tmp_path):
    proc, tries, slept = _run(tmp_path, 4, 2)
    assert (proc.returncode, tries, slept) == (0, 3, ["3", "6"])
    assert "INFRASTRUCTURE" not in proc.stdout


def test_never_working_stops_at_the_bound_with_the_infrastructure_marker(tmp_path):
    proc, tries, slept = _run(tmp_path, 3, 99)
    assert proc.returncode == 7
    assert tries == 3 and slept == ["3", "6"]
    assert "::error::INFRASTRUCTURE (not a code defect)" in proc.stdout


def test_missing_command_is_infrastructure_too_and_args_with_spaces_survive(tmp_path):
    proc, tries, _ = _run(tmp_path, 2, 0, cmd=["/nonexistent/docker", "pull", "a b"])
    assert proc.returncode != 0 and "INFRASTRUCTURE" in proc.stdout and "a b" in proc.stdout
    ok = subprocess.run(["bash", str(SCRIPT), "2", "0", "--", "test", "a b", "=", "a b"], capture_output=True)
    assert ok.returncode == 0


def test_bad_usage_is_refused():
    assert subprocess.run(["bash", str(SCRIPT), "3"], capture_output=True).returncode == 2


# (workflow, a line that must go through ci_retry.sh, the pin that must survive)
SITES = [
    ("tri-comparison-audit.yml", "apt-get", "universal-ctags"),
    ("tri-comparison-history.yml", "apt-get", "universal-ctags"),
    ("graph-accuracy-audit.yml", "npm install", "typescript@6.0.2"),
    ("evidence-refresh.yml", "docker pull", '"$image"'),
    ("det-sweep.yml", "docker pull", "$image"),
]


@pytest.mark.parametrize(("name", "needle", "pin"), SITES)
def test_flaky_steps_go_through_ci_retry(name, needle, pin):
    lines = [
        ln
        for ln in (WORKFLOWS / name).read_text(encoding="utf-8").splitlines()
        if needle in ln and not ln.lstrip().startswith("#")
    ]
    assert lines, f"{name}: no {needle} step left"
    for ln in lines:
        assert "ci_retry.sh" in ln, ln
    assert any(pin in ln for ln in lines)

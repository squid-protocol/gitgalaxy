"""#5048: tests/tools/ci_retry.sh and the workflow steps that use it."""

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "tests" / "tools" / "ci_retry.sh"
WORKFLOWS = REPO / ".github" / "workflows"

# ci_retry.sh runs only on the ubuntu workflow runners; on a Windows runner `bash` is the WSL launcher (UTF-16 output,
# no /usr/bin), so the behaviour tests are Linux-only like the other bash-script tools (test_box_tools.py).
needs_linux_bash = pytest.mark.skipif(
    sys.platform != "linux", reason="ci_retry.sh is a bash script for the Linux runners"
)


def _run(tmp_path, attempts, fail_times, *, cmd=None, backoff=3, extra_env=None):
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
        env={"PATH": "/usr/bin:/bin", "CI_RETRY_SLEEP": str(sleeper), **(extra_env or {})},
    )
    tries = len(counter.read_text().split()) if counter.exists() else 0
    slept = sleeps.read_text().split() if sleeps.exists() else []
    return proc, tries, slept


@needs_linux_bash
def test_first_try_success_does_not_sleep(tmp_path):
    proc, tries, slept = _run(tmp_path, 4, 0)
    assert (proc.returncode, tries, slept) == (0, 1, [])


@needs_linux_bash
def test_fail_then_succeed_retries_with_doubling_backoff(tmp_path):
    proc, tries, slept = _run(tmp_path, 4, 2)
    assert (proc.returncode, tries, slept) == (0, 3, ["3", "6"])
    assert "INFRASTRUCTURE" not in proc.stdout


@needs_linux_bash
def test_never_working_stops_at_the_bound_with_the_infrastructure_marker(tmp_path):
    proc, tries, slept = _run(tmp_path, 3, 99)
    assert proc.returncode == 7
    assert tries == 3 and slept == ["3", "6"]
    assert "::error::INFRASTRUCTURE (not a code defect)" in proc.stdout


@needs_linux_bash
def test_missing_command_is_infrastructure_too_and_args_with_spaces_survive(tmp_path):
    proc, tries, _ = _run(tmp_path, 2, 0, cmd=["/nonexistent/docker", "pull", "a b"])
    assert proc.returncode != 0 and "INFRASTRUCTURE" in proc.stdout and "a b" in proc.stdout
    ok = subprocess.run(["bash", str(SCRIPT), "2", "0", "--", "test", "a b", "=", "a b"], capture_output=True)
    assert ok.returncode == 0


@needs_linux_bash
def test_bad_usage_is_refused():
    assert subprocess.run(["bash", str(SCRIPT), "3"], capture_output=True).returncode == 2


@needs_linux_bash
def test_a_cache_hit_skips_the_fetch(tmp_path):
    proc, tries, slept = _run(tmp_path, 4, 0, extra_env={"CI_RETRY_CACHED": "true"})
    assert (proc.returncode, tries, slept) == (0, 0, [])
    assert "cache hit" in proc.stderr


@needs_linux_bash
def test_a_cache_miss_falls_through_to_the_retries(tmp_path):
    proc, tries, slept = _run(tmp_path, 4, 1, extra_env={"CI_RETRY_CACHED": "false"})
    assert (proc.returncode, tries, slept) == (0, 2, ["3"])


@needs_linux_bash
def test_the_final_failure_prints_the_cause_line(tmp_path):
    cmd = ["sh", "-c", "echo first; echo 'E: Failed to fetch http://x  Temporary failure resolving'; echo; exit 9"]
    proc, _, _ = _run(tmp_path, 2, 0, cmd=cmd)
    assert proc.returncode == 9
    assert "ci_retry: cause: E: Failed to fetch http://x  Temporary failure resolving" in proc.stdout
    assert proc.stdout.index("cause:") < proc.stdout.index("::error::INFRASTRUCTURE")


@needs_linux_bash
def test_a_missing_command_still_has_a_cause(tmp_path):
    proc, _, _ = _run(tmp_path, 1, 0, cmd=["/nonexistent/docker", "pull"])
    assert "ci_retry: cause:" in proc.stdout and "nonexistent" in proc.stdout


CAPTURE = {"CI_RETRY_CAPTURE": "1"}


@needs_linux_bash
def test_capture_mode_stdout_is_only_the_command_stdout(tmp_path):
    cmd = ["sh", "-c", "echo data; echo warn >&2"]
    proc, _, _ = _run(tmp_path, 3, 0, cmd=cmd, extra_env=CAPTURE)
    assert (proc.returncode, proc.stdout, proc.stderr) == (0, "data\n", "warn\n")


@needs_linux_bash
def test_capture_mode_a_failed_attempt_never_leaks_stdout(tmp_path):
    flaky = tmp_path / "flaky2"
    counter = tmp_path / "n"
    flaky.write_text(
        f'#!/bin/sh\necho x >> "{counter}"\necho "out$(wc -l < "{counter}")"\necho err >&2\n[ "$(wc -l < "{counter}")" -ge 3 ] && exit 0\nexit 5\n'
    )
    flaky.chmod(0o755)
    proc, _, slept = _run(tmp_path, 4, 0, cmd=[str(flaky)], extra_env=CAPTURE)
    assert proc.returncode == 0 and proc.stdout.strip() == "out3" and slept == ["3", "6"]
    assert proc.stderr.count("attempt") == 2 and "INFRASTRUCTURE" not in proc.stderr


@needs_linux_bash
def test_capture_mode_final_failure_is_all_stderr_and_stdout_is_empty(tmp_path):
    cmd = ["sh", "-c", "echo partial; echo 'HTTP 502 bad gateway' >&2; exit 9"]
    proc, tries, slept = _run(tmp_path, 2, 0, cmd=cmd, extra_env=CAPTURE)
    assert proc.returncode == 9 and proc.stdout == "" and slept == ["3"]
    assert "ci_retry: cause: HTTP 502 bad gateway" in proc.stderr
    assert "::error::INFRASTRUCTURE (not a code defect)" in proc.stderr


@needs_linux_bash
def test_capture_mode_cause_falls_back_to_stdout_and_missing_command(tmp_path):
    proc, _, _ = _run(tmp_path, 1, 0, cmd=["sh", "-c", "echo only-out; exit 4"], extra_env=CAPTURE)
    assert proc.stdout == "" and "cause: only-out" in proc.stderr
    proc, _, _ = _run(tmp_path, 1, 0, cmd=["/nonexistent/gh", "api"], extra_env=CAPTURE)
    assert proc.stdout == "" and "nonexistent" in proc.stderr


@needs_linux_bash
def test_capture_mode_cache_hit_keeps_stdout_empty(tmp_path):
    proc, tries, _ = _run(tmp_path, 4, 0, extra_env={**CAPTURE, "CI_RETRY_CACHED": "true"})
    assert (proc.returncode, proc.stdout, tries) == (0, "", 0)


@needs_linux_bash
def test_default_mode_still_merges_stderr_into_stdout(tmp_path):
    proc, _, _ = _run(tmp_path, 1, 0, cmd=["sh", "-c", "echo data; echo warn >&2"])
    assert sorted(proc.stdout.split()) == ["data", "warn"]


# (workflow, a line that must go through ci_retry.sh, the pin that must survive)
SITES = [
    ("tri-comparison-audit.yml", "apt-get", "universal-ctags"),
    ("tri-comparison-history.yml", "apt-get", "universal-ctags"),
    ("graph-accuracy-audit.yml", "npm install", "typescript@6.0.2"),
    ("graph-accuracy-audit.yml", "rustup toolchain install", "1.90.0"),
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


# The corpus clone: 13 workflows fetch language-crucible at the pin from tests/crucible_pins.toml.
CLONE_WORKFLOWS = sorted(
    p.name for p in WORKFLOWS.glob("*.yml") if "language-crucible.git" in p.read_text(encoding="utf-8")
)


def test_the_clone_site_list_is_not_empty():
    assert len(CLONE_WORKFLOWS) >= 13


@pytest.mark.parametrize("name", CLONE_WORKFLOWS)
def test_corpus_clone_goes_through_ci_retry_and_keeps_the_pin(name):
    lines = [
        ln.strip()
        for ln in (WORKFLOWS / name).read_text(encoding="utf-8").splitlines()
        if "git clone" in ln and "language-crucible.git" in ln and not ln.lstrip().startswith("#")
    ]
    assert lines, f"{name}: no language-crucible clone left"
    for ln in lines:
        assert "tests/tools/ci_retry.sh" in ln, ln
        # a retry starts from a clean directory (a partial clone would fail every later try) and clones the pin
        assert ln.index("rm -rf language-crucible") < ln.index("git clone"), ln
        assert '--branch "$1"' in ln and ln.endswith('_ "$ref"'), ln


# #5048: hash-pinned pip installs. pip's own --retries covers only connection resets, so the wrapper is the fix.
PIP_RETRIED = [
    "archetype-validation.yml",
    "blocker-baseline.yml",
    "call-graph-accuracy-audit.yml",
    "call-resolution-history.yml",
    "dependabot-relock.yml",
    "det-sweep.yml",
    "full-suite-gate.yml",
    "java-base-generation.yml",
    "java-compile.yml",
    "mainframe-ground-truth.yml",
    "unicode-gauntlet.yml",
]
PIP_LINE = "pip install --require-hashes"


@pytest.mark.parametrize("name", PIP_RETRIED)
def test_hash_pinned_pip_installs_go_through_ci_retry_and_keep_the_hashes(name):
    lines = [
        ln.strip()
        for ln in (WORKFLOWS / name).read_text(encoding="utf-8").splitlines()
        if PIP_LINE in ln and not ln.lstrip().startswith("#")
    ]
    assert lines, f"{name}: no hash-pinned pip install left"
    for ln in lines:
        assert ln.startswith(("tests/tools/ci_retry.sh 4 10 -- ", "gitgalaxy/tests/tools/ci_retry.sh 4 10 -- ")), ln
        assert "-r " in ln and "ci/requirements/" in ln, ln


def test_workflows_with_an_unretried_hash_pinned_pip_install_do_not_grow():
    """The class can only shrink: wrap a workflow's installs, then delete it from this list."""
    unwrapped = sorted(
        p.name
        for p in WORKFLOWS.glob("*.yml")
        if any(
            PIP_LINE in ln and "ci_retry.sh" not in ln and not ln.lstrip().startswith("#")
            for ln in p.read_text(encoding="utf-8").splitlines()
        )
    )
    assert not set(PIP_RETRIED) & set(unwrapped)
    assert len(unwrapped) <= 26, f"a new workflow has an unretried pip install: {unwrapped}"


DIGEST = "icr.io/x/db2@sha256:" + "a" * 64


def _fake_docker(tmp_path, present):
    """A `docker` that logs its calls; `image inspect` succeeds only when `present`."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "docker.log"
    exe = bindir / "docker"
    exe.write_text(
        f'#!/bin/sh\necho "$@" >> "{log}"\n[ "$1 $2" = "image inspect" ] && exit {0 if present else 1}\nexit 0\n'
    )
    exe.chmod(0o755)
    return {"PATH": f"{bindir}:/usr/bin:/bin"}, log


@needs_linux_bash
@pytest.mark.parametrize("flags", [[], ["-q"]])
def test_a_digest_pinned_docker_pull_is_skipped_when_the_image_is_local(tmp_path, flags):
    env, log = _fake_docker(tmp_path, present=True)
    proc, _, _ = _run(tmp_path, 3, 0, cmd=["docker", "pull", *flags, DIGEST], extra_env=env)
    assert proc.returncode == 0 and "cache hit" in proc.stderr
    assert log.read_text().splitlines() == [f"image inspect {DIGEST}"]


@needs_linux_bash
def test_a_digest_pinned_docker_pull_fetches_when_the_image_is_absent(tmp_path):
    env, log = _fake_docker(tmp_path, present=False)
    proc, _, _ = _run(tmp_path, 3, 0, cmd=["docker", "pull", "-q", DIGEST], extra_env=env)
    assert proc.returncode == 0 and "cache hit" not in proc.stderr
    assert log.read_text().splitlines() == [f"image inspect {DIGEST}", f"pull -q {DIGEST}"]


@needs_linux_bash
def test_a_tag_only_docker_pull_never_infers_a_probe(tmp_path):
    env, log = _fake_docker(tmp_path, present=True)
    proc, _, _ = _run(tmp_path, 3, 0, cmd=["docker", "pull", "alpine:3"], extra_env=env)
    assert proc.returncode == 0 and "cache hit" not in proc.stderr
    assert log.read_text().splitlines() == ["pull alpine:3"]


@needs_linux_bash
def test_an_explicit_probe_beats_the_inferred_one(tmp_path):
    env, log = _fake_docker(tmp_path, present=True)
    proc, _, _ = _run(tmp_path, 3, 0, cmd=["docker", "pull", DIGEST], extra_env={**env, "CI_RETRY_CACHED": "false"})
    assert proc.returncode == 0 and "cache hit" not in proc.stderr
    assert log.read_text().splitlines() == [f"pull {DIGEST}"]


# #8424: a `gh api` read captured into a variable / process substitution is wrapped in capture mode, so a failed try never
# leaks into the captured value. The planner workflows (ruff-audit.yml is the next slice) carry the same three-call step.
GH_API_PLAN_WORKFLOWS = ["gitgalaxy.yml", "small-audits.yml", "mypy-audit.yml"]


def _gh_api_lines(name):
    return [
        ln
        for ln in (WORKFLOWS / name).read_text(encoding="utf-8").splitlines()
        if "gh api" in ln and not ln.lstrip().startswith("#")
    ]


def test_every_wrapped_gh_api_capture_uses_capture_mode():
    for path in sorted(WORKFLOWS.glob("*.yml")):
        for ln in _gh_api_lines(path.name):
            if "ci_retry.sh" in ln:
                assert "CI_RETRY_CAPTURE=1" in ln, f"{path.name}: {ln.strip()}"


@pytest.mark.parametrize("name", GH_API_PLAN_WORKFLOWS)
def test_the_planner_gh_api_calls_are_wrapped_in_capture_mode(name):
    lines = _gh_api_lines(name)
    assert len(lines) == 3, f"{name}: expected the labels / files / count calls"
    for ln in lines:
        assert "CI_RETRY_CAPTURE=1 tests/tools/ci_retry.sh 4 10 -- gh api" in ln, ln
        assert "||" in ln, f"{name}: the planner must still fail open: {ln.strip()}"

"""#9031: a GitHub API rate limit (HTTP 403) in the `lane` job's cosmetic "close the push lane's bot PR" step failed a whole
Evidence Refresh. The class: a best-effort or read-only `gh` call in the lane job with no retry. These tests run the
workflow's own shell over a stub `gh`."""

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "evidence-refresh.yml"
CLOSE = "Full lane - close the push lane's open bot PR (superseded)"
GATES = (
    "Full lane - stand down while the open bot PR's checks are running (#6693)",
    "Push lane - stand down while a full run is queued or running",
)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("bash") is None, reason="runs the workflow's bash"
)


def _block(name):
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == f"- name: {name}")
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].strip() and len(lines[i]) - len(lines[i].lstrip()) <= 6),
        len(lines),
    )
    return lines[start:end]


def _script(name):
    block = _block(name)
    i = next(i for i, ln in enumerate(block) if ln.strip() == "run: |")
    return "\n".join(ln[10:] for ln in block[i + 1 :])


def _run(tmp_path, list_rc, prs, close_rc=0):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.txt"
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$@" >> "{calls}"\n'
        'if [ "$1" = api ]; then\n'
        f'  [ {list_rc} -ne 0 ] && {{ echo "gh: API rate limit exceeded (HTTP 403)" >&2; exit 1; }}\n'
        f'  printf "{prs}"; exit 0\n'
        "fi\n"
        f"exit {close_rc}\n"
    )
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    tools = tmp_path / "tests" / "tools"
    tools.mkdir(parents=True)
    shutil.copy(ROOT / "tests" / "tools" / "ci_retry.sh", tools / "ci_retry.sh")
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", REPO="o/r", EVENT="schedule", CI_RETRY_SLEEP="true")
    r = subprocess.run(
        ["bash", "-e", "-c", _script(CLOSE)], cwd=tmp_path, env=env, capture_output=True, text=True, check=False
    )
    return r, calls.read_text().splitlines() if calls.exists() else []


def test_a_rate_limited_listing_warns_and_the_step_passes(tmp_path):
    r, calls = _run(tmp_path, list_rc=1, prs="")
    assert r.returncode == 0, r.stderr
    assert "::warning" in r.stdout
    assert len(calls) == 3  # three attempts, never a close


def test_a_rate_limited_close_warns_and_the_step_passes(tmp_path):
    r, calls = _run(tmp_path, list_rc=0, prs="7\\n9\\n", close_rc=1)
    assert r.returncode == 0, r.stderr
    assert r.stdout.count("::warning") == 2
    assert sum(c.startswith("pr close") for c in calls) == 6


def test_each_open_bot_pr_is_closed_once(tmp_path):
    r, calls = _run(tmp_path, list_rc=0, prs="7\\n9\\n")
    assert r.returncode == 0, r.stderr
    closes = [c for c in calls if c.startswith("pr close")]
    assert [c.split()[2] for c in closes] == ["7", "9"]


def test_no_open_bot_pr_closes_nothing(tmp_path):
    r, calls = _run(tmp_path, list_rc=0, prs="")
    assert r.returncode == 0, r.stderr
    assert not [c for c in calls if c.startswith("pr close")]


@pytest.mark.parametrize("name", GATES)
def test_the_gate_reads_go_through_ci_retry(name):
    script = _script(name)
    assert "gh api" in script
    for line in script.splitlines():
        if "gh api" in line:
            assert "ci_retry.sh" in line, line


def test_the_lane_checkout_carries_ci_retry():
    text = WORKFLOW.read_text(encoding="utf-8")
    lane = text[text.index("\n  lane:") : text.index("\n  db2-part:")]
    assert "            tests/tools/ci_retry.sh\n" in lane


PIN = "Pin the commit of main this run is of"
LATE = "Push lane - hold the PR back if a full run has started meanwhile (#4743)"


def _stub_gh(tmp_path, fail_first, out):
    """A `gh` that prints `out` after `fail_first` rate-limited (HTTP 403) attempts."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    count = tmp_path / "count.txt"
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/usr/bin/env bash\n"
        f'echo x >> "{count}"\n'
        f'if [ "$(wc -l < "{count}")" -le {fail_first} ]; then\n'
        '  echo "gh: API rate limit exceeded (HTTP 403)" >&2; exit 1\n'
        "fi\n"
        f'printf "%s\\n" "{out}"\n'
    )
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    tools = tmp_path / "gitgalaxy" / "tests" / "tools"
    tools.mkdir(parents=True)
    shutil.copy(ROOT / "tests" / "tools" / "ci_retry.sh", tools / "ci_retry.sh")
    return bin_dir, count


def _run_step(tmp_path, name, fail_first, out):
    bin_dir, count = _stub_gh(tmp_path, fail_first, out)
    gh_out = tmp_path / "gh_output.txt"
    summary = tmp_path / "summary.txt"
    env = dict(
        os.environ,
        PATH=f"{bin_dir}:{os.environ['PATH']}",
        REPO="o/r",
        GITHUB_OUTPUT=str(gh_out),
        GITHUB_STEP_SUMMARY=str(summary),
        CI_RETRY_SLEEP="true",
    )
    # the inline pin loop sleeps through the PATH: a no-op `sleep` keeps the test instant
    sleep = bin_dir / "sleep"
    sleep.write_text("#!/usr/bin/env bash\nexit 0\n")
    sleep.chmod(sleep.stat().st_mode | stat.S_IEXEC)
    r = subprocess.run(
        ["bash", "-e", "-c", _script(name)], cwd=tmp_path, env=env, capture_output=True, text=True, check=False
    )
    return r, (gh_out.read_text() if gh_out.exists() else ""), len(count.read_text().splitlines())


def test_the_pin_read_survives_a_transient_rate_limit(tmp_path):
    r, out, calls = _run_step(tmp_path, PIN, fail_first=2, out="abc123")
    assert r.returncode == 0, r.stderr
    assert out.strip() == "sha=abc123"
    assert calls == 3


def test_the_pin_read_fails_the_job_when_every_try_is_rate_limited(tmp_path):
    r, out, calls = _run_step(tmp_path, PIN, fail_first=99, out="abc123")
    assert r.returncode != 0
    assert "INFRASTRUCTURE" in r.stderr  # ci_digest reruns it instead of calling it a code defect
    assert not out
    assert calls == 3


def test_the_late_gate_survives_a_transient_rate_limit(tmp_path):
    r, out, calls = _run_step(tmp_path, LATE, fail_first=1, out="1")
    assert r.returncode == 0, r.stderr
    assert out.strip() == "publish=false"
    assert calls == 2


def test_the_late_gate_publishes_when_every_try_is_rate_limited(tmp_path):
    r, out, calls = _run_step(tmp_path, LATE, fail_first=99, out="1")
    assert r.returncode == 0, r.stderr
    assert "::warning" in r.stdout
    assert out.strip() == "publish=true"
    assert calls == 3


def test_the_late_gate_publishes_when_no_full_run_is_active(tmp_path):
    r, out, _ = _run_step(tmp_path, LATE, fail_first=0, out="0")
    assert r.returncode == 0, r.stderr
    assert out.strip() == "publish=true"


# A `gh api` / `gh run` read left bare fails the whole refresh on a rate limit. Every one is retried (ci_retry.sh, or
# the inline loop in the pin step, which runs before any checkout) or listed here with its reason.
BARE_GH_ALLOWED = {
    # the auto-merge loop retries by itself and treats a non-"clean status" error as fatal on purpose (#6693)
    "gh pr merge",
}


def test_no_gh_read_in_the_workflow_is_left_without_a_retry():
    offenders = []
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    for n, ln in enumerate(lines, 1):
        code = ln.split("#", 1)[0] if ln.lstrip().startswith("#") else ln
        if not any(tok in code for tok in ("gh api ", "gh run ", "gh pr ", "gh issue ")):
            continue
        if "ci_retry.sh" in code or any(a in code for a in BARE_GH_ALLOWED) or code.lstrip().startswith("#"):
            continue
        if "--comment" in code or code.lstrip().startswith("echo"):
            continue
        if 'gh api "repos/$REPO/commits/main"' in code:  # the pin step's inline retry loop
            continue
        offenders.append(f"{n}: {ln.strip()}")
    assert not offenders, "\n".join(offenders)

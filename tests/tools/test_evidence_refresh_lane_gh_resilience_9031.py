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

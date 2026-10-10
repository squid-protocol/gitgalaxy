"""Box tools (tests/tools/box/*.sh): slot limit, kill-by-cwd safety, dry-run listing."""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

# Linux only: the scripts need flock(1) and /proc. On macOS heavy-run.sh never got a slot and the suite hung to the
# job timeout (#4840: every macOS shard-3 leg cancelled at 45 min).
pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="the box tools are bash scripts (flock, /proc, kill) for the Linux box"
)

BOX = Path(__file__).resolve().parent / "box"


def _env(tmp_path, slots=2):
    return dict(os.environ, GG_LOCK_DIR=str(tmp_path / "locks"), GG_HEAVY_SLOTS=str(slots), GG_HEAVY_POLL="0.2")


def test_heavy_run_respects_slot_limit(tmp_path):
    slots = 2
    log = tmp_path / "log"
    job = f"echo S $$ >> {log}; sleep 1; echo E $$ >> {log}"
    procs = [
        subprocess.Popen([str(BOX / "heavy-run.sh"), "bash", "-c", job], env=_env(tmp_path, slots))  # noqa: S603
        for _ in range(slots + 1)
    ]
    for p in procs:
        assert p.wait(timeout=30) == 0
    running = peak = 0
    for line in log.read_text().splitlines():
        running += 1 if line.startswith("S") else -1
        peak = max(peak, running)
    assert peak == slots


def test_heavy_run_propagates_exit_status(tmp_path):
    rc = subprocess.run(  # noqa: S603
        [str(BOX / "heavy-run.sh"), "bash", "-c", "exit 7"], env=_env(tmp_path), timeout=30, check=False
    ).returncode
    assert rc == 7


def test_heavy_run_fails_fast_without_flock(tmp_path):
    env = _env(tmp_path)
    env["PATH"] = str(tmp_path / "empty-bin")  # no flock (nor anything else) on PATH; bash itself is found by path
    res = subprocess.run(  # noqa: S603
        ["/bin/bash", str(BOX / "heavy-run.sh"), "true"], env=env, capture_output=True, text=True, timeout=30, check=False
    )
    assert res.returncode == 127
    assert "flock" in res.stderr


def test_golden_lock_is_exclusive(tmp_path):
    log = tmp_path / "log"
    job = f"echo S >> {log}; sleep 0.5; echo E >> {log}"
    procs = [subprocess.Popen([str(BOX / "golden-lock.sh"), "bash", "-c", job], env=_env(tmp_path)) for _ in range(2)]  # noqa: S603
    for p in procs:
        p.wait(timeout=30)
    assert log.read_text().split() == ["S", "E", "S", "E"]


@pytest.fixture
def sleeper(tmp_path):
    d = tmp_path / "wt"
    d.mkdir()
    p = subprocess.Popen(["sleep", "60"], cwd=d)  # noqa: S603, S607
    time.sleep(0.2)
    yield d, p
    p.kill()
    p.wait()


def test_kill_by_cwd_dry_run_lists_without_killing(sleeper):
    d, p = sleeper
    out = subprocess.run(
        [str(BOX / "kill-by-cwd.sh"), str(d), "--dry-run"], capture_output=True, text=True, check=False
    )  # noqa: S603
    assert out.returncode == 0 and str(p.pid) in out.stdout
    assert p.poll() is None


def test_kill_by_cwd_kills_target_but_never_itself_or_parent(sleeper):
    d, p = sleeper
    # The caller's own shell also runs with cwd inside <d>: it must survive and finish.
    out = subprocess.run(  # noqa: S603
        ["bash", "-c", f"{BOX}/kill-by-cwd.sh {d}; echo caller-alive"],
        cwd=d,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "caller-alive" in out.stdout
    assert p.wait(timeout=10) != 0  # killed by signal


def test_wait_pids_reports_status():
    p = subprocess.Popen(["sleep", "0.3"])  # noqa: S603, S607
    out = subprocess.run(
        [str(BOX / "wait-pids.sh"), str(p.pid)], capture_output=True, text=True, timeout=20, check=False
    )  # noqa: S603
    assert f"{p.pid} exit=" in out.stdout
    p.wait()


def test_sync_pins_dry_run_changes_nothing():
    out = subprocess.run([str(BOX / "sync-pins.sh"), "--dry-run"], capture_output=True, text=True, check=False)  # noqa: S603
    assert out.returncode == 0, out.stderr
    for name in ("language-crucible", "cics-crucible", "estate-crucible"):
        assert name in out.stdout
    assert subprocess.run([str(BOX / "sync-pins.sh"), "--bogus"], capture_output=True, check=False).returncode == 2  # noqa: S603

"""#5604: the workflow's waits on the background Db2 start must outlast what they wait for."""

import re
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_db2 as d  # noqa: E402

PULL_TIMEOUT_S = 1800  # equivalence_db2.pull_image's per-attempt docker pull timeout
START_ATTEMPTS = 2  # _ensure_container: one start, one replace


def _steps():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "det-sweep.yml").read_text(encoding="utf-8"))
    return [s for job in wf["jobs"].values() for s in job.get("steps", [])]


def _first_db_wait_s(run: str) -> int:
    loop = re.search(r"seq 1 (\d+)\)", run)
    nap = re.search(r"^\s*sleep (\d+)\s*$", run, re.M)
    assert loop and nap, "wait loop not found"
    return int(loop.group(1)) * int(nap.group(1))


def _prewarm_pull_wait_s(run: str) -> int:
    m = re.search(r"pulled = .*?for _ in range\((\d+)\):.*?time\.sleep\((\d+)\)", run, re.S)
    assert m, "prewarm pull-done wait not found"
    return int(m.group(1)) * int(m.group(2))


def _run_of(marker: str) -> str:
    found = [s["run"] for s in _steps() if marker in s.get("run", "") or marker in s.get("name", "")]
    assert len(found) == 1
    return found[0]


def test_first_db_wait_outlasts_both_start_attempts():
    run = _run_of("Wait for the first Db2 database")
    assert _first_db_wait_s(run) >= START_ATTEMPTS * d.READY_POLLS * 10


def test_prewarm_pull_wait_covers_one_pull_attempt():
    assert _prewarm_pull_wait_s(_run_of("db2_prewarm.py")) >= PULL_TIMEOUT_S


@pytest.mark.parametrize(("polls", "ok"), [(120, False), (539, False), (540, True)])
def test_parser_sees_the_old_bound(polls, ok):
    run = f"for _ in $(seq 1 {polls}); do\n  sleep 5\ndone"
    assert (_first_db_wait_s(run) >= START_ATTEMPTS * d.READY_POLLS * 10 + 300) is ok

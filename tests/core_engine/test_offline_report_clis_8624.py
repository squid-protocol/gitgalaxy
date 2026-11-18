"""#8624 slice 2: the report / recorder CLIs take the same `--offline` flag as galaxyscope, through one shared helper."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# After the CLI has run with --offline, a deliberate network call must be refused.
_ATTEMPT = (
    "import socket\n"
    "from gitgalaxy.tools.readiness.offline import OfflineViolation\n"
    "try:\n"
    "    socket.create_connection(('127.0.0.1', 9), timeout=1)\n"
    "    print('allowed')\n"
    "except OfflineViolation:\n"
    "    print('refused')\n"
    "except OSError:\n"
    "    print('allowed')\n"
)

_RUN_COMPLETENESS = (
    "import sys\n"
    "from gitgalaxy.tools.cobol_to_cobol.completeness_report import main\n"
    "rc = main(sys.argv[1:])\n"
    "print('RC', rc)\n"
)
_RUN_RECORDER = (
    "import runpy, sys\n"
    "sys.argv = ['audit_recorder'] + sys.argv[1:]\n"
    "runpy.run_module('gitgalaxy.recorders.audit_recorder', run_name='__main__')\n"
    "print('RC 0')\n"
)

CLIS = {
    "completeness_report": _RUN_COMPLETENESS,
    "audit_recorder": _RUN_RECORDER,
}


def _env(**extra):
    env = dict(os.environ, PYTHONPATH=str(REPO), GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER")
    env.pop("GITGALAXY_OFFLINE", None)
    env.pop("GITGALAXY_ASSESS_OFFLINE", None)
    env.update(extra)
    return env


def _run(code, args, **extra):
    return subprocess.run(  # noqa: S603 -- this interpreter with a fixed driver
        [sys.executable, "-c", code, *map(str, args)],
        capture_output=True,
        text=True,
        env=_env(**extra),
        check=False,
        timeout=300,
    )


@pytest.fixture(scope="module")
def planted(tmp_path_factory):
    """A planted repo, scanned offline to a master DB, and a stand-in galaxy.json for the recorder."""
    base = tmp_path_factory.mktemp("offline_clis")
    repo = base / "planted"
    repo.mkdir()
    (repo / "a.py").write_text("import os\n\ndef f(x):\n    if x:\n        return os.getcwd()\n    return None\n")
    out = base / "out"
    res = subprocess.run(  # noqa: S603 -- this interpreter running galaxyscope on a temp repo
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(repo), "--db-only", "--offline", "--output", str(out)],
        capture_output=True,
        text=True,
        env=_env(GITGALAXY_DISABLE_GIT_HISTORY="1"),
        check=False,
        timeout=300,
    )
    assert res.returncode == 0, (res.stdout + res.stderr)[-3000:]
    db = next(out.glob("*_galaxy_master.db"))
    galaxy = base / "galaxy.json"
    galaxy.write_text("{}")
    return {"completeness_report": [db, "--md", base / "report.md"], "audit_recorder": [galaxy]}


@pytest.mark.parametrize("cli", sorted(CLIS))
def test_a_planted_repo_completes_under_the_guard(cli, planted):
    res = _run(CLIS[cli] + _ATTEMPT, [*planted[cli], "--offline"])
    assert "RC 0" in res.stdout, (res.stdout + res.stderr)[-3000:]


@pytest.mark.parametrize("cli", sorted(CLIS))
def test_a_deliberate_network_call_raises_offline_violation(cli, planted):
    res = _run(CLIS[cli] + _ATTEMPT, [*planted[cli], "--offline"])
    assert res.stdout.split()[-1] == "refused", (res.stdout + res.stderr)[-3000:]


@pytest.mark.parametrize("cli", sorted(CLIS))
def test_the_env_var_alone_installs_the_guard_and_without_it_nothing_is_guarded(cli, planted):
    guarded = _run(CLIS[cli] + _ATTEMPT, planted[cli], GITGALAXY_OFFLINE="1")
    open_ = _run(CLIS[cli] + _ATTEMPT, planted[cli])
    assert guarded.stdout.split()[-1] == "refused", (guarded.stdout + guarded.stderr)[-3000:]
    assert open_.stdout.split()[-1] == "allowed", (open_.stdout + open_.stderr)[-3000:]

"""#8624 slice 5: the two log-scanner CLIs take the shared `--offline` flag."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

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

_DRIVER = (
    "import runpy, sys\n"
    "mod = sys.argv.pop(1)\n"
    "sys.argv[0] = mod\n"
    "try:\n"
    "    runpy.run_module('gitgalaxy.tools.terabyte_log_scanning.' + mod, run_name='__main__')\n"
    "    print('RC 0')\n"
    "except SystemExit as e:\n"
    "    print('RC', e.code or 0)\n"
)


def _env(**extra):
    env = dict(os.environ, PYTHONPATH=str(REPO), GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER")
    env.pop("GITGALAXY_OFFLINE", None)
    env.pop("GITGALAXY_ASSESS_OFFLINE", None)
    env.update(extra)
    return env


def _run(mod, args, **extra):
    return subprocess.run(  # noqa: S603 -- this interpreter with a fixed driver
        [sys.executable, "-c", _DRIVER + _ATTEMPT, mod, *map(str, args)],
        capture_output=True,
        text=True,
        env=_env(**extra),
        check=False,
        timeout=120,
    )


@pytest.fixture(scope="module")
def planted(tmp_path_factory):
    d = tmp_path_factory.mktemp("logs")
    log = d / "app.log"
    log.write_text("2026-11-18 10:00:00 PGM1 ran\n2026-11-18 10:01:00 card 4111111111111111\n")
    return {
        "pii_leak_hunter": [log, "--out", d / "o1"],
        "terabyte_log_scanner": [log, "-k", "PGM1", "--out", d / "o2"],
    }


MODS = ["pii_leak_hunter", "terabyte_log_scanner"]


@pytest.mark.parametrize("mod", MODS)
def test_it_runs_and_refuses_a_network_call_with_the_flag(mod, planted):
    res = _run(mod, [*planted[mod], "--offline"])
    assert "RC" in res.stdout, (res.stdout + res.stderr)[-3000:]
    assert res.stdout.split()[-1] == "refused", (res.stdout + res.stderr)[-3000:]


@pytest.mark.parametrize("mod", MODS)
def test_the_env_var_alone_guards_and_without_it_nothing_is_guarded(mod, planted):
    guarded = _run(mod, planted[mod], GITGALAXY_OFFLINE="1")
    open_ = _run(mod, planted[mod])
    assert guarded.stdout.split()[-1] == "refused", (guarded.stdout + guarded.stderr)[-3000:]
    assert open_.stdout.split()[-1] == "allowed", (open_.stdout + open_.stderr)[-3000:]

"""#8624 slice 3: the three cobol_to_cobol reporters take the shared `--offline` flag."""

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
    "    runpy.run_module('gitgalaxy.tools.cobol_to_cobol.' + mod, run_name='__main__')\n"
    "    print('RC 0')\n"
    "except SystemExit as e:\n"
    "    print('RC', e.code or 0)\n"
)

COBOL = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. DEMO.\n       PROCEDURE DIVISION.\n           STOP RUN.\n"


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
    d = tmp_path_factory.mktemp("cobol_reporters")
    (d / "demo.cbl").write_text(COBOL)
    return {
        "cobol_system_limits_reporter": [d],
        "cobol_graveyard_finder": [d],
        "cobol_jcl_auditor": [d, d],
    }


MODS = ["cobol_system_limits_reporter", "cobol_jcl_auditor", "cobol_graveyard_finder"]


@pytest.mark.parametrize("mod", MODS)
def test_it_completes_and_refuses_a_network_call_with_the_flag(mod, planted):
    res = _run(mod, [*planted[mod], "--offline"])
    assert "RC 0" in res.stdout, (res.stdout + res.stderr)[-3000:]
    assert res.stdout.split()[-1] == "refused", (res.stdout + res.stderr)[-3000:]


@pytest.mark.parametrize("mod", MODS)
def test_the_env_var_alone_guards_and_without_it_nothing_is_guarded(mod, planted):
    guarded = _run(mod, planted[mod], GITGALAXY_OFFLINE="1")
    open_ = _run(mod, planted[mod])
    assert guarded.stdout.split()[-1] == "refused", (guarded.stdout + guarded.stderr)[-3000:]
    assert open_.stdout.split()[-1] == "allowed", (open_.stdout + open_.stderr)[-3000:]

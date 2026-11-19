"""#8624 slice 15: the two root-level COBOL controllers take the shared `--offline` flag (audit_recorder already did)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

_DRIVER = (
    "import runpy, sys\n"
    "mod = sys.argv.pop(1)\n"
    "sys.argv[0] = mod\n"
    "try:\n"
    "    runpy.run_module('gitgalaxy.' + mod, run_name='__main__')\n"
    "except SystemExit:\n"
    "    pass\n"
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


def _run(mod, args, **extra):
    env = dict(os.environ, PYTHONPATH=str(REPO), GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER")
    env.pop("GITGALAXY_OFFLINE", None)
    env.pop("GITGALAXY_ASSESS_OFFLINE", None)
    env.update(extra)
    return subprocess.run(  # noqa: S603 -- this interpreter with a fixed driver
        [sys.executable, "-c", _DRIVER, mod, *map(str, args)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=120,
    )


@pytest.fixture
def cases(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    return {
        "cobol_to_java_controller": [["--init-config", tmp_path / "cfg.yaml"]],
        "cobol_refractor_controller": [[empty]],
    }


MODS = ["cobol_to_java_controller", "cobol_refractor_controller"]


@pytest.mark.parametrize("mod", MODS)
def test_the_flag_guards_the_controller_process(mod, cases):
    args = cases[mod][0]
    res = _run(mod, [*args, "--offline"])
    assert res.stdout.split()[-1] == "refused", (res.stdout + res.stderr)[-3000:]


@pytest.mark.parametrize("mod", MODS)
def test_the_env_var_alone_guards_and_without_it_nothing_is_guarded(mod, cases):
    args = cases[mod][0]
    assert _run(mod, args, GITGALAXY_OFFLINE="1").stdout.split()[-1] == "refused"
    assert _run(mod, args).stdout.split()[-1] == "allowed"

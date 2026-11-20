"""#8624 slice 7: four cobol_to_cobol forges (compiler, schema, JCL, DAG architect) take the shared `--offline` flag."""

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
    "    runpy.run_module(mod, run_name='__main__')\n"
    "    print('RC 0')\n"
    "except SystemExit as e:\n"
    "    print('RC', e.code or 0)\n"
)

PKG = "gitgalaxy.tools.cobol_to_cobol."
COBOL = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. HELLO.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01  WS-A PIC X(4).\n"
    "       PROCEDURE DIVISION.\n"
    "           MOVE 'ABCD' TO WS-A.\n"
    "           STOP RUN.\n"
)


def _env(**extra):
    env = dict(os.environ, PYTHONPATH=str(REPO), GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER")
    env.pop("GITGALAXY_OFFLINE", None)
    env.pop("GITGALAXY_ASSESS_OFFLINE", None)
    env.update(extra)
    return env


def _run(mod, args, **extra):
    return subprocess.run(  # noqa: S603 -- this interpreter with a fixed driver
        [sys.executable, "-c", _DRIVER + _ATTEMPT, PKG + mod, *map(str, args)],
        capture_output=True,
        text=True,
        env=_env(**extra),
        check=False,
        timeout=120,
    )


@pytest.fixture(scope="module")
def planted(tmp_path_factory):
    d = tmp_path_factory.mktemp("forges")
    src = d / "src"
    src.mkdir()
    (src / "hello.cbl").write_text(COBOL)
    return {
        "compiler": ("cobol_compiler_forge", [src, d / "out_c"]),
        "schema": ("cobol_schema_forge", [src / "hello.cbl"]),
        "jcl": ("cobol_jcl_forge", [src, "--out", d / "out_j"]),
        "dag": ("cobol_dag_architect", [src]),
    }


KEYS = ["compiler", "schema", "jcl", "dag"]


@pytest.mark.parametrize("key", KEYS)
def test_it_runs_and_refuses_a_network_call_with_the_flag(key, planted):
    mod, args = planted[key]
    res = _run(mod, [*args, "--offline"])
    assert "RC 0" in res.stdout, (res.stdout + res.stderr)[-3000:]
    assert res.stdout.split()[-1] == "refused", (res.stdout + res.stderr)[-3000:]


@pytest.mark.parametrize("key", KEYS)
def test_the_env_var_alone_guards_and_without_it_nothing_is_guarded(key, planted):
    mod, args = planted[key]
    guarded = _run(mod, args, GITGALAXY_OFFLINE="1")
    open_ = _run(mod, args)
    assert guarded.stdout.split()[-1] == "refused", (guarded.stdout + guarded.stderr)[-3000:]
    assert open_.stdout.split()[-1] == "allowed", (open_.stdout + open_.stderr)[-3000:]

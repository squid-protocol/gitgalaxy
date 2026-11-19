"""#8624 slice 8: cobol_etl_unpacker and cobol_microservice_slicer take the shared `--offline` flag."""

import json
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

COBOL = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. DEMO.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01 WS-A PIC 9(4).\n"
    "       PROCEDURE DIVISION.\n"
    "       MAIN-PARA.\n"
    "           MOVE 5 TO WS-A.\n"
    "           STOP RUN.\n"
)

SCHEMA = {"properties": {"NAME": {"description": "Legacy PIC: X(4)"}}}


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
    d = tmp_path_factory.mktemp("unpacker_slicer")
    (d / "demo.cbl").write_text(COBOL)
    (d / "data.bin").write_bytes("ABCDEFGH".encode("cp037"))  # two 4-byte records
    (d / "schema.json").write_text(json.dumps(SCHEMA))
    return {
        "cobol_etl_unpacker": [d / "data.bin", d / "schema.json", "--out", d / "out.csv"],
        "cobol_microservice_slicer": [d / "demo.cbl", "--var", "WS-A"],
    }


MODS = ["cobol_etl_unpacker", "cobol_microservice_slicer"]


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

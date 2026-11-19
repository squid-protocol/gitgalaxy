"""#8624 slice 10: the test forge, batch harness, proof_reach (and slice 9: the forges and guardrail) take the shared `--offline` flag."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from gitgalaxy.tools.cobol_to_java.cobol_to_java_guardrail import write_baseline  # noqa: E402

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
    "    runpy.run_module('gitgalaxy.tools.cobol_to_java.' + mod, run_name='__main__')\n"
    "    print('RC 0')\n"
    "except SystemExit as e:\n"
    "    print('RC', e.code or 0)\n"
)

JAVA = (
    "package demo;\npublic class DemoService {\n    private int count;\n    public int total() { return count; }\n}\n"
)

MODS = [
    "cobol_to_java_api_contract_forge",
    "cobol_to_java_spring_forge",
    "cobol_to_java_service_forge",
    "cobol_to_java_guardrail",
    "cobol_to_java_test_forge",
    "batch_test_harness",
    "proof_reach",
]


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
    d = tmp_path_factory.mktemp("cobol_to_java_offline")
    (d / "demo_ir.json").write_text(json.dumps({"program_id": "DEMO", "paragraphs": {}}))
    (d / "demo_schema.json").write_text(json.dumps({"properties": {"NAME": {"description": "Legacy PIC: X(4)"}}}))
    proj = d / "proj"
    (proj / "src").mkdir(parents=True)
    (proj / "src" / "DemoService.java").write_text(JAVA)
    write_baseline(proj)
    corpus = d / "corpus" / "x"
    corpus.mkdir(parents=True)
    (d / "Demo.java").write_text(JAVA)
    return {
        "cobol_to_java_test_forge": [d / "demo_ir.json"],
        "batch_test_harness": [corpus],
        "proof_reach": [d / "Demo.java"],
        "cobol_to_java_api_contract_forge": [d / "demo_ir.json"],
        "cobol_to_java_spring_forge": [d / "demo_schema.json"],
        "cobol_to_java_service_forge": [d / "demo_ir.json"],
        "cobol_to_java_guardrail": [proj],
    }


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

"""#8624: `galaxyscope --offline` / GITGALAXY_OFFLINE=1 installs the no-network guard on a direct scan."""

import os
import subprocess
import sys
from pathlib import Path

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


def _env(**extra):
    env = dict(os.environ, PYTHONPATH=str(REPO), GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER", **extra)
    env.pop("GITGALAXY_OFFLINE", None)
    env.pop("GITGALAXY_ASSESS_OFFLINE", None)
    env.update(extra)
    return env


def _run(code, args=(), **extra):
    return subprocess.run(  # noqa: S603 -- this interpreter with a fixed probe
        [sys.executable, "-c", code, *args], capture_output=True, text=True, env=_env(**extra), check=False
    )


def test_importing_the_engine_with_the_env_var_installs_the_guard():
    res = _run("import gitgalaxy.galaxyscope\n" + _ATTEMPT, GITGALAXY_OFFLINE="1")
    assert res.stdout.split()[-1] == "refused", res.stderr[-2000:]


def test_the_flag_on_argv_installs_the_guard():
    res = _run("import gitgalaxy.galaxyscope\n" + _ATTEMPT, ["--offline"])
    assert res.stdout.split()[-1] == "refused", res.stderr[-2000:]


def test_without_the_opt_in_nothing_is_guarded():
    res = _run("import gitgalaxy.galaxyscope\n" + _ATTEMPT)
    assert res.stdout.split()[-1] == "allowed", res.stderr[-2000:]


def test_a_scan_of_a_planted_repo_completes_offline(tmp_path):
    repo = tmp_path / "planted"
    repo.mkdir()
    (repo / "a.py").write_text("import os\n\ndef f(x):\n    if x:\n        return os.getcwd()\n    return None\n")
    (repo / "b.c").write_text("int main(void) { return 0; }\n")
    out = tmp_path / "out"
    res = subprocess.run(  # noqa: S603 -- this interpreter running galaxyscope on a temp repo
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(repo), "--db-only", "--offline", "--output", str(out)],
        capture_output=True,
        text=True,
        env=_env(GITGALAXY_DISABLE_GIT_HISTORY="1"),
        check=False,
        timeout=300,
    )
    assert res.returncode == 0, (res.stdout + res.stderr)[-3000:]
    assert any(out.glob("*_galaxy_master.db")), res.stdout[-2000:]
    assert "OfflineViolation" not in res.stdout + res.stderr


def test_offline_refuses_the_tiktoken_download_by_name():
    """An installed tiktoken with no cached encoding must not die obscurely: the warning names the refusal."""
    code = (
        "import logging, sys, types\n"
        "class Boom:\n"
        "    @staticmethod\n"
        "    def get_encoding(name):\n"
        "        import socket\n"
        "        socket.getaddrinfo('openaipublic.blob.core.windows.net', 443)\n"
        "sys.modules['tiktoken'] = Boom\n"
        "logging.basicConfig(level=logging.WARNING)\n"
        "import gitgalaxy.core.detector as d\n"
        "print('HAS', d.HAS_TIKTOKEN)\n"
    )
    res = _run(code, GITGALAXY_OFFLINE="1")
    assert "HAS False" in res.stdout, res.stderr[-2000:]
    assert "offline mode refuses the tiktoken cl100k_base download" in res.stderr

"""#8624 slice 6: the four `gitgalaxy` sensor subcommands and the API network map take the shared `--offline` flag."""

import os
import sqlite3
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

CLI = "gitgalaxy.cli"
MAP = "gitgalaxy.tools.network_auditing.full_api_network_map"


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


def _git(tmp, *args):
    subprocess.run(["git", *args], cwd=tmp, check=True, capture_output=True)  # noqa: S603, S607


@pytest.fixture(scope="module")
def planted(tmp_path_factory):
    d = tmp_path_factory.mktemp("sensors")
    db = d / "s_galaxy_master.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE file_data(id INTEGER PRIMARY KEY, file_path TEXT, language TEXT, function_count INTEGER,
            raw_imports TEXT, total_loc INTEGER, repo_name TEXT);
        CREATE TABLE function_data(id INTEGER PRIMARY KEY, file_id INTEGER, func_name TEXT, is_public INTEGER DEFAULT 0, loc INTEGER);
        CREATE TABLE fcall_data(id INTEGER PRIMARY KEY, src_file_id INTEGER, src_func_id INTEGER, src_func_name TEXT, callee TEXT,
            step TEXT, kind TEXT DEFAULT 'call', candidates INTEGER, dst_file_id INTEGER, dst_func_id INTEGER, dst_class_id INTEGER);
        CREATE TABLE fcall_candidates(id INTEGER PRIMARY KEY, src_file_id INTEGER, src_func_id INTEGER, callee TEXT, dst_file_id INTEGER, dst_func_id INTEGER, platform TEXT);
        CREATE TABLE fcall_external(id INTEGER PRIMARY KEY, src_file_id INTEGER, callee TEXT, callers INTEGER);
        INSERT INTO file_data VALUES (1,'a.c','c',1,'[]',10,'r'),(2,'b.c','c',1,'["a.h"]',10,'r');
        INSERT INTO function_data VALUES (10,1,'f',1,2),(11,2,'g',1,2);
        INSERT INTO fcall_data(src_file_id,src_func_id,kind,candidates,dst_file_id,dst_func_id) VALUES (2,11,'call',1,1,10);
        """
    )
    con.commit()
    con.close()
    repo = d / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "a.c").write_text("void f(void) { old(p); }\n")
    _git(repo, "add", "a.c")
    _git(repo, "commit", "-qm", "one")
    (repo / "a.c").write_text("void f(void) { new(p); }\n/* TODO */\n")
    _git(repo, "commit", "-qam", "two")
    app = d / "app"
    app.mkdir()
    (app / "swagger.json").write_text('{"swagger": "2.0", "paths": {"/a": {"get": {}}}}')
    (app / "svc.py").write_text("@app.route('/a')\ndef a():\n    return 1\n")
    return {
        "reach": (CLI, ["reach", db, "--src", d]),
        "libsurface": (CLI, ["libsurface", db]),
        "activity": (CLI, ["activity", repo]),
        "change": (CLI, ["change", repo]),
        "api_map": (MAP, [app]),
    }


KEYS = ["reach", "libsurface", "activity", "change", "api_map"]


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

# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""#4108 slice 19: System Config Mutation (`arch_sys_config`) in the mainstream languages, through a real scan.

`test_system_config_mutation_live_rules.py` pins the 8 languages that carry a rule (elixir is not in it). The
mainstream languages carry a stated absence (`None`, e.g. python's contract note), so every environment write,
`chmod`, `chdir` or registry write in python, js, go, ruby, java and rust must read 0. This plants them and
pins that; elixir is added to the firing set. Writing a rule for one of them is a contract decision (sibling gap),
so the absence is a strict xfail the day someone adds one without updating this file.
"""

import os
import sqlite3
import subprocess
import sys

import pytest

pytestmark = pytest.mark.slow(
    reason="two real scans of planted files; the fixture's cost lands on whichever test runs first in a CI split part"
)

# elixir carries a rule the live-rules test does not cover
ELIXIR_FIRE = {
    "put_env": "System.put_env(\"A\", \"b\")\n",
    "app_put_env": "Application.put_env(:app, :k, 1)\n",
    "chmod": "File.chmod(\"a\", 0o644)\n",
}
ELIXIR_QUIET = {
    "get_env": "x = System.get_env(\"A\")\n",
    "app_get_env": "x = Application.get_env(:app, :k)\n",
    "file_read": "x = File.read(\"a\")\n",
}
# mainstream languages: a stated absence, planted with the mutation each one would hold
ABSENT = {
    "py": "import os\nos.environ['A'] = 'b'\nos.chmod('a', 0o644)\nos.chdir('/tmp')\n",
    "js": "process.env.A = 'b';\nfs.chmodSync('a', 0o644);\nprocess.chdir('/tmp');\n",
    "go": 'package main\nfunc f() {\n\tos.Setenv("A", "b")\n\tos.Chmod("a", 0644)\n\tos.Chdir("/tmp")\n}\n',
    "rb": "ENV['A'] = 'b'\nFile.chmod(0644, 'a')\nDir.chdir('/tmp')\n",
    "java": 'class A { void f() { System.setProperty("a", "b"); new File("a").setReadable(true); } }\n',
    "rs": 'fn f() { std::env::set_var("A", "b"); std::env::set_current_dir("/tmp").unwrap(); }\n',
}


def _scan(tmp_path, files: dict) -> dict:
    src = tmp_path / "src"
    src.mkdir()
    for name, text in files.items():
        (src / name).write_text(text, encoding="utf-8")
    out = tmp_path / "out"
    env = dict(os.environ, GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER", GITGALAXY_DISABLE_GIT_HISTORY="1")
    subprocess.run(
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(src), "--db-only", "--output", str(out)],
        env=env,
        check=True,
        capture_output=True,
        timeout=180,
    )
    (db,) = out.glob("*_galaxy_master.db")
    con = sqlite3.connect(db)
    try:
        return {p: n for p, n in con.execute("select file_path, arch_sys_config from file_data")}
    finally:
        con.close()


@pytest.fixture(scope="module")
def scans(tmp_path_factory):
    elixir = {f"{k}.ex": t for k, t in ELIXIR_FIRE.items()} | {f"q_{k}.ex": t for k, t in ELIXIR_QUIET.items()}
    absent = {f"m.{ext}": t for ext, t in ABSENT.items()}
    return _scan(tmp_path_factory.mktemp("ex"), elixir), _scan(tmp_path_factory.mktemp("abs"), absent)


@pytest.mark.parametrize("name", sorted(ELIXIR_FIRE))
def test_elixir_mutation_fires(scans, name):
    assert scans[0][f"{name}.ex"] >= 1


@pytest.mark.xfail(
    strict=True,
    reason="sibling gap: the rule's leading \\b sits before the colon of `:os.putenv`, so an Erlang-module call never matches",
)
def test_elixir_erlang_module_putenv_fires(tmp_path):
    got = _scan(tmp_path, {"e.ex": ":os.putenv('A', 'b')\n"})
    assert got["e.ex"] >= 1


@pytest.mark.parametrize("name", sorted(ELIXIR_QUIET))
def test_elixir_reads_stay_zero(scans, name):
    assert scans[0][f"q_{name}.ex"] == 0


@pytest.mark.parametrize("ext", sorted(ABSENT))
def test_mainstream_language_is_a_stated_absence(scans, ext):
    assert scans[1][f"m.{ext}"] == 0

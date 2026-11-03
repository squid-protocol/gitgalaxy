"""
System Config Mutation (#4108 slice 13): thin-signal probe, kept as a regression guard.

The committed golden fixture fires `system_config_mutation` only for csd and jcl: language-crucible has no
crystal / fsharp / acs / zscript directory and its sql files hold no `ALTER SYSTEM`-shaped statement, so the other
live rules are a corpus gap, not broken detection. A rule regressing there would pass the golden check, so this pins
each live language end to end: a real scan of a planted file must put a count in `file_data.arch_sys_config`, and
a file with only look-alike text must put none.
"""

import os
import sqlite3
import subprocess
import sys

import pytest

# language -> (file name, text that must fire, minimum count, text that must not fire)
LIVE = {
    "crystal": (
        "a.cr",
        'ENV["FOO"] = "x"\nDir.cd("/tmp")\nFile.chmod(0o644, "a")\n',
        3,
        'x = ENV["FOO"]\nputs x\n',
    ),
    "fsharp": (
        "a.fs",
        'open System\nlet f () =\n    Environment.SetEnvironmentVariable("A", "b")\n    Registry.SetValue("k", "n", "v")\n',
        2,
        'open System\nlet f () = Environment.GetEnvironmentVariable("A")\n',
    ),
    "postgresql": (
        "a.sql",
        "ALTER SYSTEM SET work_mem = 64;\nSELECT set_config('a', 'b', false);\nALTER ROLE bob SET search_path = x;\n",
        3,
        "SELECT current_setting('work_mem');\nCREATE FUNCTION f() RETURNS int AS $$ BEGIN RETURN 1; END $$ LANGUAGE plpgsql;\n",
    ),
    "acs": (
        "a.acs",
        'script 1 (void)\n{\n    SetCVar("x", 1);\n    ConsoleCommand("y");\n}\n',
        2,
        "script 1 (void)\n{\n    int a = GetCVar(1);\n}\n",
    ),
    "zscript": (
        "a.zs",
        'class A : Actor\n{\n    void Tick()\n    {\n        CVar c = CVar.GetCVar("x");\n        c.SetInt(1);\n        c.SetString("y");\n    }\n}\n',
        2,
        "class A : Actor\n{\n    void Tick()\n    {\n        int v = c.GetInt();\n    }\n}\n",
    ),
    "jcl": (
        "a.jcl",
        "//CSDJOB JOB 1\n//S1 EXEC PGM=DFHCSDUP\n//SYSIN DD *\n DEFINE TRANSACTION(ABCD) GROUP(G1)\n/*\n",
        1,
        "//J JOB 1\n//S1 EXEC PGM=IEFBR14\n",
    ),
    "csd": (
        "a.csd",
        "DEFINE TRANSACTION(ABCD) GROUP(G1)\n       PROGRAM(PROG1)\nDEFINE PROGRAM(PROG1) GROUP(G1)\n",
        2,
        "* a comment about DEFINE TRANSACTION\n",
    ),
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
        timeout=120,
    )
    (db,) = out.glob("*_galaxy_master.db")
    con = sqlite3.connect(db)
    try:
        return {
            p: (lang, n) for p, lang, n in con.execute("select file_path, language, arch_sys_config from file_data")
        }
    finally:
        con.close()


@pytest.fixture(scope="module")
def scans(tmp_path_factory):
    fire = {name: text for name, text, _, _ in LIVE.values()}
    quiet = {"quiet_" + name: text for name, _, _, text in LIVE.values()}
    return _scan(tmp_path_factory.mktemp("fire"), fire), _scan(tmp_path_factory.mktemp("quiet"), quiet)


@pytest.mark.parametrize("language", sorted(LIVE))
def test_planted_mutation_fires_through_a_real_scan(scans, language):
    name, _, minimum, _ = LIVE[language]
    lang, count = scans[0][name]
    assert lang == language
    assert count >= minimum


@pytest.mark.parametrize("language", sorted(LIVE))
def test_lookalike_text_does_not_fire(scans, language):
    name = "quiet_" + LIVE[language][0]
    lang, count = scans[1][name]
    assert lang == language
    assert count == 0


@pytest.mark.xfail(
    strict=True,
    reason="sibling gap (#2899 string-literal shape): crystal's rule matches `Dir.cd` / `ENV[..] =` inside a string literal",
)
def test_mutation_text_inside_a_string_literal_does_not_fire(tmp_path):
    got = _scan(tmp_path, {"s.cr": 'puts "Dir.cd is not called"\n'})
    assert got["s.cr"][1] == 0

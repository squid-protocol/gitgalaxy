"""DOOM per-subsystem complexity distributions (#6097): grouping by file prefix, ratios, skips and outputs.

Synthetic scan DBs only (no DOOM code); the tool dir goes on sys.path and the module is imported as a bare name
(tests/ has no __init__.py).
"""

import csv
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "doom_speedrun"))

import subsystem_distribution as sd  # noqa: E402

SHA = "abc123def"


def make_scan(work, name, funcs):
    """funcs: [(file_path, language, complexity)]."""
    scan = work / "scans" / SHA / name
    scan.mkdir(parents=True)
    con = sqlite3.connect(scan / f"{name}_galaxy_master.db")
    con.execute("create table file_data (id integer primary key, file_path text, language text)")
    con.execute("create table function_data (file_id integer, complexity integer)")
    ids = {}
    for path, lang, cx in funcs:
        fid = ids.setdefault(
            path, con.execute("insert into file_data (file_path, language) values (?, ?)", (path, lang)).lastrowid
        )
        con.execute("insert into function_data values (?, ?)", (fid, cx))
    con.commit()
    con.close()


def many(path, lang, values):
    return [(path, lang, v) for v in values]


@pytest.fixture
def work(tmp_path):
    make_scan(
        tmp_path,
        "linuxdoom",
        many("linuxdoom/r_main.c", "c", range(1, 21)) + many("linuxdoom/p_map.c", "c", range(1, 21)),
    )
    make_scan(
        tmp_path,
        "gore",
        many("src/r_main.go", "go", range(2, 42, 2))  # twice linuxdoom's renderer
        + many("src/Game.go", "go", [1] * 20)  # renamed: lands in other
        + many("README.md", "markdown", [99] * 5),
    )
    make_scan(tmp_path, "tiny", many("r_a.c", "c", [1, 2]))
    return tmp_path


ROWS = [{"name": n, "class": "engine-port"} for n in ("linuxdoom", "gore", "tiny", "doom-wasm")] + [
    {"name": "freedoom", "class": "assets"}
]


def test_load_groups_code_functions_by_subsystem_and_drops_other_languages(work):
    got = sd.load_by_subsystem(next((work / "scans" / SHA / "gore").glob("*_master.db")))
    assert set(got) == {"renderer", "other"}  # README.md (markdown) dropped
    assert len(got["renderer"]) == 20 and got["other"] == [1.0] * 20


def test_summarise_gives_ratio_to_linuxdoom_and_the_other_share(work):
    result, skipped = sd.run(ROWS, work, SHA)
    assert sorted(skipped) == ["doom-wasm", "tiny"]  # freedoom (assets) skipped silently
    rows, other = result["gore"]
    by = {r["subsystem"]: r for r in rows}
    assert other == 50 and by["other"]["share"] == 50
    assert by["renderer"]["med_vs_linuxdoom"] == pytest.approx(2.0)
    assert "med_vs_linuxdoom" not in by["other"]  # linuxdoom has no 'other' functions here
    assert all("med_vs_linuxdoom" not in r for r in result["linuxdoom"][0])  # the baseline is not compared to itself
    assert by["renderer"]["cx10"] == 100 * 16 / 20


def test_a_run_needs_the_baseline(tmp_path):
    make_scan(tmp_path, "gore", many("r_x.go", "go", range(40)))
    with pytest.raises(SystemExit, match="linuxdoom"):
        sd.run(ROWS, tmp_path, SHA)


def test_main_refuses_unlicensed_ports_and_writes_results(work):
    with pytest.raises(SystemExit, match="not-a-port"):
        sd.main(["--only", "not-a-port", "--work", str(work), "--sha", SHA])
    manifest = work / "manifest.csv"
    with open(manifest, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["name", "class"])
        w.writeheader()
        w.writerows(ROWS)
    assert sd.main(["--only", "gore", "--work", str(work), "--sha", SHA, "--manifest", str(manifest)]) == 0
    dest = work / "results" / SHA / "distribution"
    with open(dest / "subsystem_distribution.csv", newline="") as fh:
        recs = list(csv.DictReader(fh))
    assert {r["port"] for r in recs} == {"linuxdoom", "gore"}
    assert "| gore | 50 | renderer | 20 |" in (dest / "subsystem_distribution.md").read_text()

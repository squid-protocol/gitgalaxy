"""DOOM per-subsystem metric distributions (#6097): grouping by file prefix, every metric, vendored drop, skips and outputs.

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


def make_scan(work, name, funcs, names=None):
    """funcs: [(file_path, language, complexity)] or with (loc, fan_out, token_mass, args) appended."""
    scan = work / "scans" / SHA / name
    scan.mkdir(parents=True)
    (work / "repos" / name).mkdir(parents=True)
    con = sqlite3.connect(scan / f"{name}_galaxy_master.db")
    con.execute("create table file_data (id integer primary key, file_path text, language text)")
    con.execute(
        "create table function_data (file_id integer, func_name text, complexity integer, loc integer, func_fan_out integer, "
        "token_mass integer, args integer)"
    )
    ids, names = {}, names or {}
    for i, (path, lang, cx, *rest) in enumerate(funcs):
        fid = ids.setdefault(
            path, con.execute("insert into file_data (file_path, language) values (?, ?)", (path, lang)).lastrowid
        )
        con.execute(
            "insert into function_data values (?, ?, ?, ?, ?, ?, ?)", (fid, names.get(i), cx, *(rest or (cx, 0, 0, 0)))
        )
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
    assert len(got["renderer"]["complexity"]) == 20 and got["other"]["complexity"] == [1.0] * 20


def test_summarise_gives_ratio_to_linuxdoom_and_the_other_share(work):
    result, skipped = sd.run(ROWS, work, SHA)
    assert sorted(skipped) == ["doom-wasm", "tiny"]  # freedoom (assets) skipped silently
    rows, other = result["gore"]
    by = {r["subsystem"]: r for r in rows}
    assert other == 50 and by["other"]["share"] == 50
    assert by["renderer"]["complexity_vs_linuxdoom"] == pytest.approx(2.0)
    assert "complexity_vs_linuxdoom" not in by["other"]  # linuxdoom has no 'other' functions here
    assert all(
        "complexity_vs_linuxdoom" not in r for r in result["linuxdoom"][0]
    )  # the baseline is not compared to itself
    assert by["renderer"]["cx10"] == 100 * 16 / 20


def test_every_metric_is_summarised_per_subsystem(tmp_path):
    make_scan(tmp_path, "linuxdoom", [("p_map.c", "c", 1, 10, 1, 100, 2)] * 30)
    make_scan(tmp_path, "gore", [("p_map.go", "go", 1, 30, 3, 50, "a, b, c")] * 30)  # args as old-style text
    rows, _ = sd.run(ROWS, tmp_path, SHA)[0]["gore"]
    (row,) = rows
    assert row["loc_med"] == 30 and row["func_fan_out_med"] == 3 and row["args_med"] == 3
    assert row["loc_vs_linuxdoom"] == pytest.approx(3.0)
    assert row["token_mass_vs_linuxdoom"] == pytest.approx(0.5)
    assert row["func_fan_out_vs_linuxdoom"] == pytest.approx(3.0) and row["args_vs_linuxdoom"] == pytest.approx(1.5)


def test_vendored_code_is_dropped(tmp_path):
    make_scan(tmp_path, "linuxdoom", many("r_main.c", "c", range(1, 31)))
    make_scan(tmp_path, "gore", many("r_main.go", "go", range(1, 31)) + many("zlib/r_inflate.c", "c", [99] * 40))
    (tmp_path / "repos" / "gore" / "zlib").mkdir()  # the engine detector reads the clone's directories
    rows, _ = sd.run(ROWS, tmp_path, SHA)[0]["gore"]
    assert [(r["subsystem"], r["n"]) for r in rows] == [("renderer", 30)]


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


def test_lineage_places_a_renamed_file_by_the_namesake_and_prefix_fallback_keeps_the_rest(tmp_path):
    base = [("r_draw.c", "c", 1), ("p_map.c", "c", 1), ("m_misc.c", "c", 1), ("i_main.c", "c", 1)]
    make_scan(tmp_path, "linuxdoom", base, {0: "R_DrawColumn", 1: "P_UseSpecialLine", 2: "M_Init", 3: "main"})
    port = [("Game.go", "go", 1)] * 3 + [("p_map.go", "go", 1), ("Util.go", "go", 1), ("Util2.go", "go", 1)]
    names = {0: "r_draw_column", 1: "UseSpecialLine", 2: "main", 3: "Helper", 4: "Init", 5: "DrawColumnX"}
    make_scan(tmp_path, "gore", port, names)
    rows = [{"name": "linuxdoom"}, {"name": "gore"}]
    got, _ = sd.run(rows, tmp_path, SHA, min_functions=1)
    counts = {r["subsystem"]: r["n"] for r in got["gore"][0]}
    # r_draw_column -> renderer, UseSpecialLine (bare) -> playsim, Helper in p_map.go -> playsim by prefix;
    # main / Init / DrawColumnX have no prefixed namesake, so they stay in "other"
    assert counts == {"renderer": 1, "playsim": 2, "other": 3}
    prefix, _ = sd.run(rows, tmp_path, SHA, min_functions=1, assign="prefix")
    assert {r["subsystem"]: r["n"] for r in prefix["gore"][0]} == {"playsim": 1, "other": 5}


def test_name_index_drops_ambiguous_and_unprefixed_names():
    import lineage

    full, bare = lineage.name_index(
        [("R_Init", "r_main.c"), ("P_Init", "p_setup.c"), ("main", "i_main.c"), ("P_Ticker", "p_tick.c"),
         ("P_Ticker", "r_main.c"), ("P_SpawnMapThing", "p_mobj.c")]
    )  # fmt: skip
    assert full == {"rinit": "renderer", "pinit": "playsim", "pspawnmapthing": "playsim"}
    assert bare == {"spawnmapthing": "playsim"}  # "Init" too short; "Ticker" ambiguous; "main" has no prefix

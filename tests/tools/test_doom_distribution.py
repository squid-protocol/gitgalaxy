"""DOOM study distributions (#5620): quantiles, distance, per-port profile, skips and outputs.

Synthetic scan DBs only (no DOOM code); the tool dir goes on sys.path and the module is imported as a bare name
(tests/ has no __init__.py).
"""

import csv
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "doom_speedrun"))

import distribution  # noqa: E402

SHA = "abc123def"


def make_scan(work, name, funcs, vendor_dir=None, vendor_lang=None):
    """funcs: [(language, complexity, loc, fan_out, token_mass, args)]; ``vendor_lang`` files live under ``vendor_dir``."""
    scan = work / "scans" / SHA / name
    scan.mkdir(parents=True)
    con = sqlite3.connect(scan / f"{name}_galaxy_master.db")
    con.execute("create table file_data (id integer primary key, language text, file_path text)")
    con.execute(
        "create table function_data (file_id integer, complexity integer, loc integer, func_fan_out integer, "
        "token_mass integer, args)"
    )
    langs = {}
    (work / "repos" / name).mkdir(parents=True, exist_ok=True)
    for lang, *rest in funcs:
        path = f"{vendor_dir}/x.{lang}" if vendor_dir and lang == vendor_lang else f"src/x.{lang}"
        fid = langs.setdefault(
            lang, con.execute("insert into file_data (language, file_path) values (?, ?)", (lang, path)).lastrowid
        )
        con.execute("insert into function_data values (?, ?, ?, ?, ?, ?)", (fid, *rest))
    con.commit()
    con.close()


def ramp(n, scale=1, lang="c"):
    return [(lang, i * scale, 10 + i, i % 5, 100 + i, i % 3) for i in range(1, n + 1)]


@pytest.fixture
def work(tmp_path):
    make_scan(tmp_path, "linuxdoom", ramp(40))
    make_scan(tmp_path, "chocolate-doom", ramp(40))  # identical shape: distance 0
    make_scan(tmp_path, "gore", ramp(40, scale=3, lang="go") + [("markdown", 999, 1, 0, 0, 0)])
    make_scan(tmp_path, "freedoom", ramp(40))  # an assets project
    make_scan(tmp_path, "doomretro", ramp(5))  # under the minimum
    return tmp_path


ROWS = [{"name": n, "class": "engine-port"} for n in ("linuxdoom", "chocolate-doom", "gore", "doomretro")] + [
    {"name": "freedoom", "class": "assets"},
    {"name": "doom-wasm", "class": "engine-port"},  # no scan at all
]


def test_quantile_matches_the_linear_definition():
    assert distribution.quantile([4, 1, 3, 2], 0.0) == 1
    assert distribution.quantile([4, 1, 3, 2], 1.0) == 4
    assert distribution.quantile([4, 1, 3, 2], 0.5) == 2.5
    assert distribution.quantile([7], 0.9) == 7
    assert distribution.quantile([1, 2, 3, 4, 5], 0.9) == pytest.approx(4.6)


def test_wasserstein_is_zero_for_equal_and_the_shift_for_a_shifted_copy():
    a = [float(i) for i in range(50)]
    assert distribution.wasserstein(a, a) == 0
    assert distribution.wasserstein(a, [x + 7 for x in a]) == pytest.approx(7)


def test_args_count_accepts_an_int_or_the_old_text_list():
    assert distribution._count(3) == 3 and distribution._count(None) == 0
    assert distribution._count("a, b,, c") == 3


def test_load_metrics_keeps_code_languages_and_names_the_majority(work):
    lang, values = distribution.load_metrics(next((work / "scans" / SHA / "gore").glob("*_master.db")))
    assert lang == "go"
    assert len(values["complexity"]) == 40 and 999.0 not in values["complexity"]  # markdown dropped
    assert set(values) == set(distribution.FIELDS)


@pytest.mark.parametrize(
    "vendor_dir", ["third_party_sdl", "3rdparty-png", "zlib", "jpeg-6", "src/lzma", "src/nlohmann"]
)
def test_vendored_code_is_dropped_from_a_distribution(tmp_path, vendor_dir):
    """Every vendor rule of the engine detector (third-party prefix, known library name, versioned name), the whole input class, not one name."""
    (tmp_path / "repos" / "gore" / vendor_dir).mkdir(parents=True, exist_ok=True)
    make_scan(tmp_path, "gore", ramp(40, lang="go") + ramp(60, scale=50, lang="c"), vendor_dir, "c")
    db = next((tmp_path / "scans" / SHA / "gore").glob("*_master.db"))
    vendored = distribution.doom_scorer._engine_vendor_test(tmp_path / "repos" / "gore")
    assert len(distribution.load_metrics(db)[1]["complexity"]) == 100  # no test: nothing dropped
    lang, values = distribution.load_metrics(db, vendored)
    assert lang == "go" and len(values["complexity"]) == 40


def test_run_profiles_ports_against_the_baseline_and_skips_the_rest(work):
    summary, skipped = distribution.run(ROWS, work, SHA)
    assert set(summary) == {"linuxdoom", "chocolate-doom", "gore"}
    assert sorted(skipped) == ["doom-wasm", "doomretro"]  # freedoom is assets: skipped silently, not reported
    assert summary["linuxdoom"]["dist"] == 0 and summary["chocolate-doom"]["dist"] == 0
    gore = summary["gore"]
    assert gore["lang"] == "go" and gore["n"] == 40
    assert gore["complexity_med"] == 61.5  # 3 * median(1..40)
    assert gore["dist"] > 0.5
    assert gore["cx10"] == 100 * sum(3 * i >= 10 for i in range(1, 41)) / 40


def test_a_run_needs_the_baseline(tmp_path):
    make_scan(tmp_path, "gore", ramp(40, lang="go"))
    with pytest.raises(SystemExit, match="linuxdoom"):
        distribution.run(ROWS, tmp_path, SHA)


def test_baseline_percentile_counts_ties_half():
    summary = {
        p: {f + "_med": m for f in distribution.FIELDS} for p, m in (("linuxdoom", 5), ("a", 5), ("b", 9), ("c", 1))
    }
    pct = distribution.base_percentiles(summary)["complexity"]
    assert pct["linuxdoom_percentile"] == 50 and pct["population_median"] == 5


def test_main_refuses_unlicensed_ports_and_writes_results(work, capsys):
    with pytest.raises(SystemExit, match="not-a-licensed-port"):
        distribution.main(["--only", "not-a-licensed-port", "--work", str(work), "--sha", SHA])
    manifest = work / "manifest.csv"
    with open(manifest, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["name", "class"])
        w.writeheader()
        w.writerows(ROWS)
    assert distribution.main(["--only", "gore", "--work", str(work), "--sha", SHA, "--manifest", str(manifest)]) == 0
    dest = work / "results" / SHA / "distribution"
    with open(dest / "distribution.csv", newline="") as fh:
        assert [r["port"] for r in csv.DictReader(fh)] == ["linuxdoom", "gore"]  # baseline always added
    assert set(json.loads((dest / "distribution.json").read_text())) == {"linuxdoom", "gore"}
    md = (dest / "distribution.md").read_text()
    assert "| gore | go | 40 |" in md and "linuxdoom percentile" in md
    assert "gore" in capsys.readouterr().out

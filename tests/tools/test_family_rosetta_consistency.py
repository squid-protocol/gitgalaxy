# ruff: noqa: S101
"""#8863: the keyword-rosetta consistency report is a pure function of the manifests, the registry's defined rules and the ledger; each case builds a tiny corpus."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import family_rosetta_consistency as frc

LANGS = ["a", "b", "c", "d"]


def _defined(fams, langs=LANGS):
    return {lang: set(fams) for lang in langs}


def _manifests(fam, counts):
    return {lang: {fam: n} for lang, n in zip(LANGS, counts, strict=False)}


def _write_corpus(root: Path, folders: dict, ledger=None):
    for name, files in folders.items():
        d = root / "data" / name
        d.mkdir(parents=True)
        (d / "expected_signals.json").write_text(json.dumps({"language": name, "files": files}))
    if ledger is not None:
        (root / "deviation_ledger.json").write_text(json.dumps({"entries": ledger}))


def test_a_family_that_fires_everywhere_with_one_count_is_clean():
    r = frc.analyze(_manifests("io", [3, 3, 3, 3]), ["io"], _defined(["io"]))
    assert set(r["families"]["io"]["verdicts"].values()) == {"agrees"}
    assert frc.silent_cells(r) == []


def test_a_language_with_a_rule_that_reads_zero_is_silent():
    r = frc.analyze(_manifests("io", [3, 3, 3, 0]), ["io"], _defined(["io"]))
    assert frc.silent_cells(r) == [("io", "d")]


def test_over_and_under_the_target_are_told_apart():
    r = frc.analyze(_manifests("io", [3, 3, 5, 1]), ["io"], _defined(["io"]))
    assert r["families"]["io"]["verdicts"] == {"a": "agrees", "b": "agrees", "c": "over", "d": "under"}


def test_a_language_without_a_rule_is_not_applicable_not_a_gap():
    defined = _defined(["io"])
    defined["d"] = set()
    r = frc.analyze(_manifests("io", [3, 3, 3, 0]), ["io"], defined)
    d = r["families"]["io"]
    assert d["not_applicable"] == ["d"]
    assert "d" not in d["verdicts"]
    assert d["defined"] == 3


def test_a_ledgered_deviation_is_not_called_a_gap_but_an_agreeing_cell_stays_agreeing():
    r = frc.analyze(_manifests("io", [3, 3, 0, 3]), ["io"], _defined(["io"]), {("io", "c"), ("io", "a")})
    assert r["families"]["io"]["verdicts"] == {"a": "agrees", "b": "agrees", "c": "ledgered", "d": "agrees"}
    assert frc.silent_cells(r) == []


def test_a_family_the_corpus_does_not_plant_is_listed_not_dropped():
    r = frc.analyze(_manifests("io", [3, 3, 3, 3]), ["io", "regex_execution"], _defined(["io"]))
    assert r["not_testable"] == ["regex_execution"]
    assert "regex_execution" not in r["families"]


def test_a_folder_that_is_not_a_registry_language_is_skipped_and_named():
    m = _manifests("io", [3, 3, 3, 3])
    m["markdown"] = {"io": 0}
    r = frc.analyze(m, ["io"], _defined(["io"]))
    assert r["unmapped_folders"] == ["markdown"]
    assert r["languages"] == 4


@pytest.mark.parametrize(
    ("counts", "consensus"),
    [([3, 3, 0, 0], True), ([3, 0, 0, 0], False), ([3, 3, 3, 0], True)],
)
def test_the_majority_threshold_is_inclusive_at_the_exact_boundary(counts, consensus):
    r = frc.analyze(_manifests("io", counts), ["io"], _defined(["io"]), min_fire_share=0.5)
    assert r["families"]["io"]["consensus"] is consensus
    if not consensus:
        assert r["families"]["io"]["verdicts"] == {}


def test_target_is_the_most_frequent_nonzero_count_and_ties_take_the_smaller():
    assert frc.target_count([0, 0, 0]) == 0
    assert frc.target_count([2, 2, 3, 0]) == 2
    assert frc.target_count([3, 2, 3, 2]) == 2


def test_the_result_is_deterministic_whatever_the_input_order():
    m = _manifests("io", [3, 3, 0, 5])
    a = frc.analyze(m, ["io"], _defined(["io"]))
    b = frc.analyze(dict(reversed(list(m.items()))), ["io"], _defined(["io"]))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_counts_are_summed_over_every_file_of_a_folder(tmp_path):
    _write_corpus(tmp_path, {"a": {"main.py": {"io": 1, "x": "text"}, "b.py": {"io": 2, "flag": True}}})
    manifests, bad = frc.load_corpus(tmp_path)
    assert manifests == {"a": {"io": 3}}
    assert bad == []


def test_a_malformed_manifest_is_reported_not_fatal(tmp_path):
    _write_corpus(tmp_path, {"a": {"main.py": {"io": 1}}})
    broken = tmp_path / "data" / "z"
    broken.mkdir()
    (broken / "expected_signals.json").write_text("{not json")
    manifests, bad = frc.load_corpus(tmp_path)
    assert list(manifests) == ["a"]
    assert bad == ["z"]


def test_the_ledger_splits_joined_signals_and_tolerates_a_missing_file(tmp_path):
    assert frc.load_ledger(tmp_path) == set()
    (tmp_path / "deviation_ledger.json").write_text(
        json.dumps({"entries": [{"signal": "globals|io", "languages_seen": ["go"]}, {"signal": "x"}]})
    )
    assert frc.load_ledger(tmp_path) == {("globals", "go"), ("io", "go")}


def test_a_missing_corpus_exits_2_and_says_nothing_was_checked(tmp_path, capsys):
    assert frc.main(["--corpus", str(tmp_path / "nope")]) == 2
    assert "nothing was checked" in capsys.readouterr().err


def test_a_corpus_with_no_manifests_exits_2(tmp_path, capsys):
    (tmp_path / "data").mkdir()
    assert frc.main(["--corpus", str(tmp_path)]) == 2
    assert "nothing was checked" in capsys.readouterr().err


def test_a_threshold_outside_zero_one_exits_2(tmp_path):
    assert frc.main(["--corpus", str(tmp_path), "--min-fire-share", "0"]) == 2


def test_the_cli_reports_a_silent_cell_and_check_floor_fails_on_it(tmp_path, capsys):
    pytest.importorskip("gitgalaxy")
    from family_validity_chart import engine_grid

    _fams, _langs, defined = engine_grid()
    langs = sorted(lang for lang, rules in defined.items() if "branch" in rules)[:4]
    assert len(langs) == 4
    folders = {lang: {"main.x": {"branch": 3}} for lang in langs[:3]}
    folders[langs[3]] = {"main.x": {"branch": 0}}
    _write_corpus(tmp_path, folders, ledger=[])
    out_json = tmp_path / "out.json"
    assert frc.main(["--corpus", str(tmp_path), "--json", str(out_json)]) == 0
    assert f"`branch` (target 3, fires in 3 of 4): {langs[3]}" in capsys.readouterr().out
    assert json.loads(out_json.read_text())["families"]["branch"]["verdicts"][langs[3]] == "silent"
    assert frc.main(["--corpus", str(tmp_path), "--check-floor"]) == 1


def test_the_real_corpus_lists_every_contracted_planted_family_when_checked_out(capsys):
    corpus = frc.default_corpus()
    if not (corpus / "data").is_dir():
        pytest.skip("keyword-rosetta corpus not checked out (set KEYWORD_ROSETTA_PATH)")
    from family_validity_chart import engine_grid

    families, _langs, defined = engine_grid()
    manifests, _bad = frc.load_corpus(corpus)
    result = frc.analyze(manifests, [f.key for f in families], defined, frc.load_ledger(corpus))
    planted = {k for m in manifests.values() for k in m}
    contracted = {f.key for f in families}
    assert set(result["families"]) == contracted & planted
    assert set(result["not_testable"]) == contracted - planted


def test_drift_names_only_a_family_both_sources_read_differently():
    manifests = {"a": {"io": 3, "args": 2}, "b": {"io": 3}}
    live = {"a": {"io": 3, "args": 9, "branch": 4}, "b": {"io": 0}}
    assert frc.drift(manifests, live) == {"a": {"args": (2, 9)}, "b": {"io": (3, 0)}}


def test_drift_report_says_when_nothing_drifted():
    assert "same live" in frc.render_drift({})
    assert "`a`: args=2/9" in frc.render_drift({"a": {"args": (2, 9)}})


def _python_corpus(tmp_path: Path) -> Path:
    d = tmp_path / "data" / "python"
    d.mkdir(parents=True)
    (d / "main.py").write_text("import os\n\n\ndef f(a, b):\n    if a:\n        return b\n    return a\n")
    (d / "expected_signals.json").write_text(json.dumps({"files": {"main.py": {"import": 1}}}))
    return tmp_path


def test_live_counts_reach_every_defined_family_of_a_folder(tmp_path):
    from family_validity_chart import engine_grid

    _fams, _langs, defined = engine_grid()
    live = frc.live_manifests(_python_corpus(tmp_path), ["python", "markdown"], defined)
    assert set(live) == {"python"}  # a folder that is not a registry language is skipped
    assert set(live["python"]) == defined["python"]
    assert live["python"]["import"] >= 1
    assert live["python"]["branch"] >= 1


def test_live_cli_reads_the_sources_and_reports_drift(tmp_path, capsys):
    corpus = _python_corpus(tmp_path)
    assert frc.main(["--corpus", str(corpus), "--live"]) == 0
    out = capsys.readouterr().out
    assert "| import |" in out
    assert "Live vs manifest" in out


def test_merge_live_keeps_the_manifest_count_for_a_planted_family_and_marks_the_rest_as_readings():
    manifests = {"a": {"io": 3}, "b": {"io": 3}}
    live = {"a": {"io": 1, "regex_execution": 0}, "b": {"io": 3, "regex_execution": 2}}
    merged, readings = frc.merge_live(manifests, live)
    assert merged == {"a": {"io": 3, "regex_execution": 0}, "b": {"io": 3, "regex_execution": 2}}
    assert readings == {("regex_execution", "a"), ("regex_execution", "b")}


def test_a_silent_reading_is_tagged_and_does_not_trip_the_floor():
    fam = "regex_execution"
    manifests = _manifests(fam, [2, 2, 2, 0])
    result = frc.analyze(manifests, [fam], _defined([fam]), None, 0.5, {(fam, "d")})
    assert result["families"][fam]["reading_cells"] == ["d"]
    assert frc.silent_cells(result) == [(fam, "d")]
    assert frc.silent_cells(result, include_readings=False) == []
    assert "d (reading)" in frc.render_markdown(result)


def test_a_planted_cell_has_no_reading_cells_key():
    fam = "io"
    result = frc.analyze(_manifests(fam, [1, 1, 1, 0]), [fam], _defined([fam]))
    assert "reading_cells" not in result["families"][fam]
    assert frc.silent_cells(result, include_readings=False) == [(fam, "d")]


def test_the_committed_report_is_a_snapshot_of_both_runs_with_its_sibling_gaps():
    """docs/family_rosetta_consistency.md carries both commands, both tables and the gap list (it is a dated reading, rerun to refresh)."""
    doc = (frc.REPO_ROOT / "docs" / "family_rosetta_consistency.md").read_text(encoding="utf-8")
    assert "family_rosetta_consistency.py" in doc and "--live" in doc
    assert doc.count("## Silent cells") == 2  # one per run
    assert "## Run 1: manifests" in doc and "## Run 2: `--live`" in doc
    assert "## Sibling gaps" in doc
    assert "- `dead_code` (target 1, fires in 4 of 5): python" in doc
    rows = [ln.split("|")[1].strip() for ln in doc.splitlines() if ln.startswith("| ") and ln.count("|") == 10]
    assert "branch" in rows and "family" in rows

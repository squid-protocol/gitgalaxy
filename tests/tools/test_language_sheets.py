"""The per-language evidence sheets: independent stats, a fixed method vocabulary, no overall score.
The loaders read committed baselines, so these cases pin the rules (bins, the Rosetta pass/fail
rule, the vocabulary check) and one end-to-end build over the real baselines."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import language_sheets as ls


def test_chip_bins_follow_the_keyword_quality_chart():
    assert [ls.chip_bin(p) for p in (0, 49.9, 50, 79.9, 80, 89.9, 90, 97.9, 98, 100)] == [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]


def test_keyword_bins_run_high_to_low_and_lower_edge_is_inclusive():
    assert [ls.kw_bin(s) for s in (1.0, 0.90, 0.899, 0.75, 0.749, 0.50, 0.499, 0.0)] == [0, 0, 1, 1, 2, 2, 3, 3]
    assert ls.KW_LABELS == (">90", "90-75", "75-50", "<50")


def test_rosetta_snapshot_counts_open_defects_and_variations(tmp_path):
    data = {
        "engine_commit": "abc1234567890",
        "languages": ["x", "y"],
        "ungated_metrics": ["loc"],
        "metrics": {
            "branch": {"x": 3, "y": 4},
            "io": {"x": 1, "y": None},  # y is n/a here: not comparable
            "loc": {"x": 9, "y": 9},  # ungated: not counted
            "doc": {"x": 2, "y": 2},
        },
        "cell_categories": {
            "branch/x": "extraction",  # open defect
            "doc/x": "inherency",  # validated variation, counts as passed
            "doc/y": "unexplained",  # open defect
        },
    }
    src, out = tmp_path / "bias_data.json", tmp_path / "snap.json"
    src.write_text(json.dumps(data))
    ls.refresh_rosetta(src, out)
    snap = json.loads(out.read_text())
    assert snap["engine_commit"] == "abc1234567890"
    assert snap["languages"]["x"] == {"comparable": 3, "open": 1, "variation": 1}
    assert snap["languages"]["y"] == {"comparable": 2, "open": 1, "variation": 0}


def test_validate_rejects_unknown_methods_and_unexplained_ensembles():
    stats = {
        "functions": {
            "a": ls.Stat(method="magic"),
            "b": ls.Stat(method="ensemble"),
            "c": ls.Stat(method="ensemble"),
        },
    }
    notes = {"c": {"stat_notes": {"functions": "tree-sitter plus ctags; count a function only if both agree"}}}
    problems = ls.validate(stats, notes)
    assert any(p.startswith("a/functions") and "vocabulary" in p for p in problems)
    assert any(p.startswith("b/functions") and "note" in p for p in problems)
    assert not any(p.startswith("c/") for p in problems)


def test_validate_rejects_a_note_for_an_unknown_stat():
    problems = ls.validate({}, {"c": {"stat_notes": {"speed": "fast"}}})
    assert problems == ["notes/c.toml: unknown stat 'speed'"]


def test_every_loader_method_is_in_the_vocabulary():
    """A loader emitting a method outside METHODS would fail validate() at build time; catch it here."""
    _langs, stats = ls.load_all()
    used = {s.method for by_lang in stats.values() for s in by_lang.values()}
    assert used <= ls.METHODS, used - ls.METHODS


def test_build_covers_every_code_language_without_an_overall_score():
    files, problems = ls.build()
    assert problems == []
    langs, _stats = ls.load_all()
    assert {f"{lang}.md" for lang in langs} <= set(files)
    assert {"README.md", "matrix.svg"} <= set(files)
    for text in files.values():
        assert "overall score:" not in text.lower() or "no overall score" in text.lower()
    # the contrast the design exists for: a language with no reference tooling is not scored against one that has it
    assert "libclang" in files["c.md"]
    assert "not measured" in files["easytrieve.md"]


def test_build_is_deterministic():
    first, _ = ls.build()
    second, _ = ls.build()
    assert first == second


def _stat(**extra):
    return ls.Stat(extra=extra) if extra else ls.Stat()


def test_coverage_counts_measured_stats_and_ignores_decoy_only_keywords():
    stats = {name: {} for name in ls.STATS}
    stats["detection"]["a"] = ls.Stat()
    stats["functions"]["a"] = ls.Stat()
    stats["keywords"]["a"] = _stat(scored=0, decoy_only=9, defined=20, bins=[0, 0, 0, 0])  # decoy only: not counted
    stats["keywords"]["b"] = _stat(scored=3, decoy_only=0, defined=20, bins=[3, 0, 0, 0])
    assert ls.coverage("a", stats) == 2
    assert ls.coverage("b", stats) == 1
    assert ls.coverage("none", stats) == 0


def test_split_by_coverage_puts_well_measured_first_and_sorts_each_group_a_to_z():
    stats = {name: {} for name in ls.STATS}
    for lang in ("zig", "ada", "mid"):  # zig and ada reach the cutoff, mid does not
        for name in ls.STATS[: ls.COVERAGE_MIN] if lang != "mid" else ls.STATS[:1]:
            if name != "keywords":
                stats[name][lang] = ls.Stat()
    stats["keywords"]["zig"] = _stat(scored=1, decoy_only=0, defined=5, bins=[1, 0, 0, 0])
    stats["keywords"]["ada"] = _stat(scored=1, decoy_only=0, defined=5, bins=[1, 0, 0, 0])
    well, sparse = ls.split_by_coverage(["zig", "mid", "ada", "unmeasured"], stats)
    assert well == ["ada", "zig"]
    assert sparse == ["mid", "unmeasured"]


def test_build_writes_three_matrices_each_language_in_exactly_one():
    files, _problems = ls.build()
    langs, stats = ls.load_all()
    notes = ls.load_notes()
    well, legacy, sparse = ls.split_groups(langs, stats, notes)
    assert well and legacy and sparse
    assert set(well).isdisjoint(legacy) and set(well).isdisjoint(sparse) and set(legacy).isdisjoint(sparse)
    assert {"matrix.svg", "matrix_legacy.svg", "matrix_sparse.svg"} <= set(files)
    for group, name in ((well, "matrix.svg"), (legacy, "matrix_legacy.svg"), (sparse, "matrix_sparse.svg")):
        for lang in group:
            assert f">{lang}</text>" in files[name]
        for other in (g for g in (well, legacy, sparse) if g is not group):
            assert all(f">{lang}</text>" not in files[name] for lang in other)


def _ledger(tmp_path, boards):
    """boards: {corpus: {field: (got, tp, truth, tier)}}"""
    corpora = {}
    for name, fields in boards.items():
        corpora[name] = {
            "scoreboard": {
                f: {"engine": {"got": g, "tp": tp, "truth": t}, "forge": None, "truth": tier}
                for f, (g, tp, t, tier) in fields.items()
            },
            "mismatches": {},
        }
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps({"corpora": corpora}))
    return path


def test_ground_truth_sums_corpora_and_reports_the_weakest_tier(tmp_path):
    ledger = _ledger(
        tmp_path,
        {
            "a": {
                "program_id": (3, 3, 3, "cross_verified"),
                "units": (10, 10, 10, "cross_verified"),
                "intra-program edges": (8, 8, 10, "cross_verified"),
            },
            "b": {
                "program_id": (2, 2, 2, "cross_verified"),
                "units": (5, 5, 5, "cross_verified"),
                "intra-program edges": (4, 4, 5, "draft"),
            },
        },
    )
    out = ls.ground_truth_stats(ledger)
    fn = out["functions"]["cobol"]
    assert dict(fn.metrics) == {"precision": 100.0, "recall": 100.0}
    assert fn.n == 15 and fn.method == "answer-key"
    assert "2 corpora, 5 programs" in fn.reference and "weakest tier cross_verified" in fn.reference
    calls = out["calls"]["cobol"]
    assert dict(calls.metrics) == {"precision": 100.0, "recall": 80.0}  # 12 of 15 edges
    assert "weakest tier draft" in calls.reference
    assert "imports" not in out  # no copybook paths in this ledger: no stat, not a zero


def test_ground_truth_never_replaces_an_independent_measurement(monkeypatch):
    real = ls.Stat(metrics=[("recall", 90.0)], method="tree-sitter")
    fake = {"functions": {"cobol": ls.Stat(metrics=[("recall", 100.0)], method="answer-key")}}
    monkeypatch.setattr(ls, "ground_truth_stats", lambda: fake)
    monkeypatch.setitem(ls.LOADERS, "functions", lambda: {"cobol": real})
    _langs, stats = ls.load_all()
    assert stats["functions"]["cobol"] is real


def test_ground_truth_missing_ledger_is_no_stats(tmp_path):
    assert ls.ground_truth_stats(tmp_path / "absent.json") == {}


def test_split_groups_keeps_legacy_together_whatever_its_coverage():
    stats = {name: {} for name in ls.STATS}
    for name in ls.STATS[: ls.COVERAGE_MIN]:
        for lang in ("modern", "oldie"):
            stats[name][lang] = ls.Stat()
    stats["keywords"].pop("modern", None)
    stats["keywords"].pop("oldie", None)
    for lang in ("modern", "oldie"):
        stats["answer_key"][lang] = ls.Stat()
    notes = {"oldie": {"context": ls.LEGACY}}
    well, legacy, sparse = ls.split_groups(["oldie", "modern", "tiny"], stats, notes)
    assert (well, legacy, sparse) == (["modern"], ["oldie"], ["tiny"])


def test_answer_key_maps_fields_to_languages_and_leaves_out_the_by_design_fields(tmp_path):
    ledger = _ledger(
        tmp_path,
        {
            "k1": {
                "JCL job flow": (10, 10, 10, "cross_verified"),
                "JCL runner programs": (4, 4, 5, "draft"),
                "units": (20, 20, 20, "cross_verified"),
                "dead": (9, 3, 6, "cross_verified"),  # by design: the engine flags something else
                "PL/I call sites": (7, 7, 7, "sample_verified"),
            },
            "k2": {"JCL job flow": (6, 6, 6, "cross_verified"), "BMS screen fields": (3, 3, 3, "draft")},
        },
    )
    out = ls.answer_key_stats(ledger)
    assert set(out) == {"jcl", "cobol", "pli", "bms"}  # every other field is cobol's
    jcl = out["jcl"]
    assert jcl.n == 21 and jcl.method == "answer-key"
    assert dict(jcl.metrics) == {"precision": 100.0, "recall": 95.2}  # 20 matched of 20 reported, of 21 true
    assert jcl.extra["tiers"] == {"cross_verified": 16, "draft": 5}
    assert jcl.extra["weakest"] == "draft" and jcl.extra["corpora"] == 2
    cobol = out["cobol"]
    assert cobol.n == 20  # `dead` is listed on the sheet but not counted
    assert [r["field"] for r in cobol.extra["fields"]] == ["units", "dead"]
    assert cobol.extra["fields"][1]["by_design"] is True
    assert out["pli"].extra["weakest"] == "sample_verified"


def test_answer_key_cell_text_states_how_much_is_cross_verified(tmp_path):
    ledger = _ledger(
        tmp_path, {"k": {"JCL job flow": (10, 10, 10, "cross_verified"), "DD names": (10, 10, 10, "draft")}}
    )
    jcl = ls.answer_key_stats(ledger)["jcl"]
    text = ls.cell_text("answer_key", jcl)
    assert "50% of 20 facts cross-verified" in text and "weakest tier draft" in text


def test_answer_key_missing_ledger_is_no_stats(tmp_path):
    assert ls.answer_key_stats(tmp_path / "absent.json") == {}


def test_upper_bound_matches_the_cross_verify_formula():
    assert ls.upper_bound_95(0, 0) == 1.0
    assert ls.upper_bound_95(0, 100) == pytest.approx(1 - 0.05 ** (1 / 100))
    assert round(ls.upper_bound_95(2, 315), 3) == 0.019  # the figure dsf.json records for its PL/I calls sample
    assert ls.upper_bound_95(5, 5) <= 1.0


def _keys(tmp_path, census_by_key):
    d = tmp_path / "keys"
    d.mkdir()
    for name, census in census_by_key.items():
        (d / f"{name}.json").write_text(json.dumps({"sample_census": census}))
    return d


def test_sample_review_pools_each_languages_sections_and_skips_nested_or_unknown_ones(tmp_path):
    keys = _keys(
        tmp_path,
        {
            "a": {
                "pli_calls": {"asked": 100, "key_errors": 1},
                "pli_moves": {"asked": 50, "key_errors": 0},
                "dsns": {"asked": 20, "key_errors": 0},
                "layouts": {"sampled": {"ridfld": {"asked": 10, "key_errors": 0}}},  # nested: skipped
                "mystery": {"asked": 5, "key_errors": 0},  # no language owns it
            },
            "b": {
                "pli_layouts": {"sampled": {"asked": 30, "key_errors": 0}},
                "pli_calls": {"asked": 20, "key_errors": 1},
            },
        },
    )
    out = ls.sample_review(keys)
    assert set(out) == {"pli", "jcl"}
    assert out["pli"]["asked"] == 200 and out["pli"]["key_errors"] == 2
    assert out["pli"]["sections"]["pli_calls"] == {
        "asked": 120,
        "key_errors": 2,
        "upper_bound_95": out["pli"]["sections"]["pli_calls"]["upper_bound_95"],
    }
    assert out["jcl"]["upper_bound_95"] == round(ls.upper_bound_95(0, 20), 5)


def test_sample_review_missing_directory_is_empty(tmp_path):
    assert ls.sample_review(tmp_path / "absent") == {}


def test_answer_key_carries_the_sample_and_its_cell_text_says_what_it_does_not_prove(tmp_path):
    ledger = _ledger(tmp_path, {"k": {"PL/I call sites": (10, 10, 10, "sample_verified")}})
    keys = _keys(tmp_path, {"k": {"pli_calls": {"asked": 300, "key_errors": 2}}})
    pli = ls.answer_key_stats(ledger, keys)["pli"]
    assert pli.extra["sample"]["asked"] == 300
    text = ls.cell_text("answer_key", pli)
    assert "blind review of 300 sampled items found 2 key errors" in text and "at most" in text and "95%" in text


def test_the_sheet_explains_the_sample_and_that_counts_are_for_the_key_as_first_drafted():
    files, _ = ls.build()
    assert "### How much of the key was re-read" in files["pli.md"]
    assert "as first drafted" in files["pli.md"]
    assert "sample: key error" in files["matrix_legacy.svg"]

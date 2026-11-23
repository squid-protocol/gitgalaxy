"""The per-language evidence sheets: independent stats, a fixed method vocabulary, no overall score.
The loaders read committed baselines, so these cases pin the rules (bins, the Rosetta pass/fail
rule, the vocabulary check) and one end-to-end build over the real baselines."""

import json
import sys
from pathlib import Path

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


def test_build_writes_two_matrices_and_every_well_measured_language_is_in_the_first():
    files, _problems = ls.build()
    langs, stats = ls.load_all()
    well, sparse = ls.split_by_coverage(langs, stats)
    assert well and sparse and set(well).isdisjoint(sparse)
    assert {"matrix.svg", "matrix_sparse.svg"} <= set(files)
    assert all(f">{lang}</text>" in files["matrix.svg"] for lang in well)
    assert all(f">{lang}</text>" in files["matrix_sparse.svg"] for lang in sparse)
    assert all(f">{lang}</text>" not in files["matrix.svg"] for lang in sparse)

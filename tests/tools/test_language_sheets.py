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

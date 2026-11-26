"""family_red_cells ranks the grid's red cells and writes the epic's launchable lines (#8863)."""

import family_red_cells as frc

BASE = {
    "cells": {
        "go": {
            "closures": {
                "functions": 100,
                "recall": 1.0,
                "precision": 0.36,
                "n_family": 500,
                "n_oracle": 180,
                "pinned": True,
            },
            "branch": {"functions": 100, "recall": 1.0, "precision": 0.96, "pinned": True},
            "io": {"functions": 100, "recall": 0.5, "precision": 0.9, "pinned": False},
        },
        "rust": {
            "closures": {"functions": 9, "recall": 0.1, "precision": 0.1, "pinned": True},  # thin: untested, not red
            "short_circuit": {"functions": 50, "recall": 0.9, "precision": 0.12, "pinned": True},
            "panics_and_aborts": {"functions": 50, "recall": None, "precision": None},  # no instances
        },
    }
}


def test_red_cells_are_ranked_worst_first_and_skip_thin_and_empty():
    cells = frc.red_cells(BASE)
    assert [(c["lang"], c["family"]) for c in cells] == [("rust", "short_circuit"), ("go", "closures"), ("go", "io")]


def test_direction_names_what_is_wrong():
    by = {(c["lang"], c["family"]): c["direction"] for c in frc.red_cells(BASE)}
    assert by[("go", "closures")] == "over-counts" and by[("go", "io")] == "misses"


def test_language_with_most_red_cells_comes_first():
    assert list(frc.by_language(frc.red_cells(BASE))) == ["go", "rust"]


def test_slice_line_is_a_launchable_checklist_item():
    line = frc.slice_line("go", [c for c in frc.red_cells(BASE) if c["lang"] == "go"])
    assert line.startswith("- [ ] **go**: 2 red cells")
    assert "closures 1.00/0.36" in line and frc.SKILL in line and "one PR for this language only" in line


def test_hatched_cells_are_marked_in_the_report(capsys, tmp_path):
    import json

    p = tmp_path / "b.json"
    p.write_text(json.dumps(BASE))
    frc.main(["--baseline", str(p)])
    out = capsys.readouterr().out
    assert "3 red cells in 2 languages" in out and "hatched" in out

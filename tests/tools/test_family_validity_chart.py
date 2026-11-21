# ruff: noqa: S101
"""#8863: the keyword-family validity grid is a pure function of the baseline and the engine's registry; every case here builds a small one."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import family_validity_chart as fvc

FAMILIES = [
    fvc.Family("branch", "structure", "stated"),
    fvc.Family("io", "safety", "stated"),
    fvc.Family("telemetry", "resources", "draft"),
]
LANGUAGES = ["c", "go", "zig"]
# go defines all three, c defines branch and io, zig defines only branch
DEFINED = {"c": {"branch", "io"}, "go": {"branch", "io", "telemetry"}, "zig": {"branch"}}


def _cell(recall, precision, status="ok", n_oracle=50, n_family=50, pinned=True, corpus="crucible v1"):
    return {
        "recall": recall,
        "precision": precision,
        "status": status,
        "n_oracle": n_oracle,
        "n_family": n_family,
        "functions": 100,
        "corpus": corpus,
        "pinned": pinned,
    }


CELLS = {
    "go": {
        "branch": _cell(0.99, 0.98),
        "io": _cell(0.33, 0.62, "both", pinned=False, corpus="prometheus"),
        "telemetry": _cell(None, None, "no-instances", n_oracle=0, n_family=0),
    },
    "c": {"branch": _cell(1.0, 0.03, "over-counts", n_oracle=4)},
}


def test_score_is_the_weaker_side_and_nothing_scores_when_the_oracle_sees_nothing():
    assert fvc.cell_score(_cell(1.0, 0.03)) == 0.03  # finds everything, fires on strings: not a good family
    assert fvc.cell_score(_cell(0.4, 0.9)) == 0.4
    assert fvc.cell_score(_cell(0.0, None, "dead")) == 0.0  # never fires where the oracle sees the construct
    assert fvc.cell_score(_cell(None, 0.0, "over-counts")) == 0.0  # fires where the oracle sees nothing
    assert fvc.cell_score(_cell(None, None, "no-instances")) is None


def test_lut_runs_red_to_blue_and_stretches_the_top():
    assert fvc.lut(0.0) == "#f22222"[:0] + fvc.lut(0.0)  # a hex colour
    red, blue = fvc.lut(0.0), fvc.lut(1.0)
    assert red != blue
    assert red.startswith("#f") and blue.endswith(("f2", "f1", "f3"))  # red-dominant at 0, blue-dominant at 1
    assert fvc.lut(-1) == fvc.lut(0) and fvc.lut(2) == fvc.lut(1)  # clamped
    assert (
        len({fvc.lut(x / 100) for x in (80, 85, 90, 95, 100)}) == 5
    )  # the 80-100% range, where most cells sit, stays distinguishable


def test_cell_states():
    assert fvc.cell_state("go", "branch", DEFINED, CELLS)[0] == "scored"
    assert fvc.cell_state("go", "telemetry", DEFINED, CELLS)[0] == "empty"
    assert fvc.cell_state("c", "io", DEFINED, CELLS)[0] == "untested"  # defined, not yet scored
    assert fvc.cell_state("zig", "io", DEFINED, CELLS)[0] == "na"  # the language has no rule for it


def test_summary_counts_every_cell_once():
    s = fvc.summary(FAMILIES, LANGUAGES, DEFINED, CELLS)
    assert s["scored"] == 3 and s["empty"] == 1 and s["untested"] == 2 and s["na"] == 3
    assert s["scored"] + s["empty"] + s["untested"] + s["na"] == len(FAMILIES) * len(LANGUAGES)
    assert s["defined"] == 6
    assert (s["scored_languages"], s["scored_families"]) == (2, 2)


def test_svg_is_deterministic_and_says_what_it_shows():
    a = fvc.render_svg(FAMILIES, LANGUAGES, DEFINED, CELLS)
    assert a == fvc.render_svg(FAMILIES, LANGUAGES, DEFINED, CELLS)
    assert a.startswith("<svg") and a.rstrip().endswith("</svg>")
    assert "3 of 6 defined cells scored" in a
    assert (
        "go / io: recall 0.33, precision 0.62" in a and "prometheus (not pinned)" in a
    )  # the tooltip names the corpus and says it is exploratory
    assert "fewer than 10 functions" in a
    assert (
        a.count('class="u"') == 2
    )  # one shared-definition element per untested cell (plus the style rule); N/A cells draw nothing
    assert "<title>c / branch" in a  # the faded (n < 10) cell is still scored and explained


def test_columns_put_scored_languages_first():
    assert fvc._order(LANGUAGES, FAMILIES, DEFINED, CELLS) == ["go", "c", "zig"]


def test_no_baseline_means_every_defined_cell_is_untested(tmp_path):
    assert fvc.load_baseline(tmp_path / "missing.json") == {}
    s = fvc.summary(FAMILIES, LANGUAGES, DEFINED, {})
    assert s["scored"] == 0 and s["untested"] == 6 and s["na"] == 3


def test_markdown_lists_only_scored_languages_with_their_weakest_family():
    md = fvc.render_markdown(FAMILIES, LANGUAGES, DEFINED, CELLS)
    assert "3 of 6 defined cells scored" in md
    assert "| go | 2 | io (0.33 / 0.62) |" in md
    assert "| c | 1 | branch (1.0 / 0.03) |" in md
    assert "zig" not in md


def test_history_appends_only_a_changed_snapshot(tmp_path):
    path = tmp_path / "h.csv"
    rows = fvc.history_rows(FAMILIES, LANGUAGES, DEFINED, CELLS, "abc", "2026-11-21T00:00:00Z")
    assert fvc.append_history(path, rows) is True
    again = fvc.history_rows(FAMILIES, LANGUAGES, DEFINED, CELLS, "def", "2026-11-22T00:00:00Z")
    assert fvc.append_history(path, again) is False  # same numbers on another day: no new rows
    more = {**CELLS, "zig": {"branch": _cell(1.0, 1.0)}}
    assert (
        fvc.append_history(path, fvc.history_rows(FAMILIES, LANGUAGES, DEFINED, more, "ghi", "2026-11-23T00:00:00Z"))
        is True
    )


def test_engine_grid_matches_the_contracts_and_registry():
    families, languages, defined = fvc.engine_grid()
    assert len(families) >= 71 and len(languages) >= 70
    assert set(defined) == set(languages)
    assert "bitwise_ops" in {f.key for f in families}
    assert all(lang not in languages for lang in fvc.NOT_CODE)


def test_committed_baseline_cells_name_real_families_and_languages():
    families, languages, _ = fvc.engine_grid()
    keys, langs = {f.key for f in families}, set(languages)
    cells = fvc.load_baseline()
    assert cells, "tests/family_validity_baseline.json is empty"
    for lang, rows in cells.items():
        assert lang in langs, lang
        for rule, cell in rows.items():
            assert rule in keys, (lang, rule)
            assert cell["status"] in {"ok", "misses", "over-counts", "both", "dead", "no-instances"}
            assert isinstance(cell["pinned"], bool) and cell["corpus"]


def test_committed_svg_is_current():
    assert fvc.main(["--check"]) == 0


def test_check_fails_on_a_stale_svg(request, monkeypatch, capsys):
    stale = fvc.REPO_ROOT / "docs" / "self_scan" / "_stale_test_chart.svg"
    stale.write_text("<svg/>", encoding="utf-8")
    monkeypatch.setattr(fvc, "CHART_PATH", stale)
    request.addfinalizer(lambda: stale.unlink(missing_ok=True))
    assert fvc.main(["--check"]) == 1
    assert "is stale" in capsys.readouterr().out


@pytest.mark.parametrize("bad", [0.0, 1.0])
def test_lut_is_a_valid_hex_colour(bad):
    c = fvc.lut(bad)
    assert len(c) == 7 and c[0] == "#"
    int(c[1:], 16)
    json.dumps(c)

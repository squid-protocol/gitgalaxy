# ruff: noqa: S101
"""#8863: the keyword-family validity charts are a pure function of the baseline and the engine's registry; every case here builds a small one."""

import json
import sys
from pathlib import Path

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
DECOYS = {
    "c": {"io": {"comment": "pass", "string_counts": True, "keyword": "fopen", "corpus": "keyword-rosetta"}},
    "zig": {"branch": {"comment": "leak", "string_counts": None, "keyword": "if", "corpus": "keyword-rosetta"}},
    "go": {"telemetry": {"comment": "pass", "string_counts": False, "keyword": "log", "corpus": "keyword-rosetta"}},
}


def test_score_is_the_weaker_side_and_nothing_scores_when_the_oracle_sees_nothing():
    assert fvc.cell_score(_cell(1.0, 0.03)) == 0.03  # finds everything, fires on strings: not a good family
    assert fvc.cell_score(_cell(0.4, 0.9)) == 0.4
    assert fvc.cell_score(_cell(0.0, None, "dead")) == 0.0  # never fires where the oracle sees the construct
    assert fvc.cell_score(_cell(None, 0.0, "over-counts")) == 0.0  # fires where the oracle sees nothing
    assert fvc.cell_score(_cell(None, None, "no-instances")) is None


def test_which_side_is_weaker():
    assert fvc.cell_side(_cell(0.4, 0.9)) == "R"
    assert fvc.cell_side(_cell(0.9, 0.4)) == "P"
    assert fvc.cell_side(_cell(0.0, None)) == "R"  # never fires: it misses
    assert fvc.cell_side(_cell(None, 0.0)) == "P"  # fires on nothing: it over-counts


def test_bins_are_fixed_and_ordered():
    assert fvc.BIN_EDGES == (0.50, 0.80, 0.90, 0.98)  # fixed in advance, not tuned to the data
    assert [fvc.score_bin(x) for x in (0.0, 0.49, 0.5, 0.79, 0.8, 0.89, 0.9, 0.97, 0.98, 1.0)] == [
        0,
        0,
        1,
        1,
        2,
        2,
        3,
        3,
        4,
        4,
    ]
    assert len(fvc.BIN_FILLS) == len(fvc.BIN_LABELS) == len(fvc.BIN_EDGES) + 1
    assert len(set(fvc.BIN_FILLS)) == 5  # five distinguishable fills
    assert "green" not in "".join(fvc.BIN_FILLS)  # one blue hue plus a dark red for failure: no red/green pair


def test_cell_states():
    assert fvc.cell_state("go", "branch", DEFINED, CELLS, DECOYS)[0] == "scored"
    assert fvc.cell_state("go", "telemetry", DEFINED, CELLS, DECOYS)[0] == "empty"  # scored, nothing to see
    assert fvc.cell_state("c", "io", DEFINED, CELLS, DECOYS)[0] == "decoy"  # no parser result, a decoy result
    assert fvc.cell_state("c", "io", DEFINED, CELLS)[0] == "untested"  # without the decoy section it is untested
    assert fvc.cell_state("zig", "io", DEFINED, CELLS, DECOYS)[0] == "na"  # the language has no rule for it


def test_summary_counts_every_cell_once_and_separates_the_evidence():
    s = fvc.summary(FAMILIES, LANGUAGES, DEFINED, CELLS, DECOYS)
    assert (s["scored"], s["empty"], s["decoy"], s["untested"], s["na"]) == (3, 1, 2, 0, 3)
    assert s["scored"] + s["empty"] + s["decoy"] + s["untested"] + s["na"] == len(FAMILIES) * len(LANGUAGES)
    assert s["defined"] == 6
    assert s["decoy_only"] == 3  # c/io and zig/branch, plus go/telemetry (parser saw nothing, the decoy test ran)
    assert s["scored"] + s["decoy_only"] + s["untested_any"] == s["defined"]
    assert (s["scored_languages"], s["scored_families"]) == (2, 2)
    plain = fvc.summary(FAMILIES, LANGUAGES, DEFINED, CELLS)
    assert plain["decoy_only"] == 0 and plain["untested_any"] == plain["defined"] - plain["scored"]


def test_decoy_totals():
    t = fvc.decoy_totals(DECOYS)
    assert t == {"comment_total": 3, "comment_ignored": 2, "string_total": 2, "string_counted": 1}


def test_summary_figure_says_how_much_and_how_well_in_numbers():
    svg = fvc.render_summary_svg(FAMILIES, LANGUAGES, DEFINED, CELLS, DECOYS)
    assert svg == fvc.render_summary_svg(FAMILIES, LANGUAGES, DEFINED, CELLS, DECOYS)  # deterministic
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert "Keyword families: how much is checked, and how well" in svg
    assert (
        "6 language-by-family rules are defined. 3 are measured against a parser (2 languages), 3 more only by a decoy test, 0 not tested yet."
        in svg
    )
    assert (
        "In a comment: ignored" not in svg and "Decoy tiers: grey now" in svg
    )  # decoy rates left the README figure (2026-11-27)
    assert "In a string literal: counted" not in svg and "Grey = a decoy test only" in svg
    assert "family_validity_matrix.svg" in svg  # points at the maintainer matrix
    assert "hover" not in svg.lower()  # a README figure cannot depend on tooltips
    assert "<title>" not in svg


def test_summary_table_prints_the_score_marks_the_weaker_side_and_the_failures():
    svg = fvc.render_summary_svg(FAMILIES, LANGUAGES, DEFINED, CELLS, DECOYS)
    assert ">98<" in svg  # go/branch: min(0.99, 0.98), printed
    assert ">33†<" in svg  # go/io: 0.33, and the dagger marks an unpinned corpus
    assert ">3<" in svg  # c/branch: 0.03 from only 4 functions, so shown thin and without fill
    assert svg.count(f'stroke="{fvc.FAIL}"') >= 2  # the failing cell(s) are outlined (and the score key swatch)
    assert 'class="side"' in svg or 'class="sided"' in svg  # R / P marks
    assert 'stroke-dasharray="3 2"' in svg  # the under-10-function cell is dashed, not filled


def test_summary_rows_are_best_first():
    svg = fvc.render_summary_svg(FAMILIES, LANGUAGES, DEFINED, CELLS, DECOYS)
    # median(branch) = median(0.98, 0.03) = 0.505; median(io) = 0.33: what holds up is at the top, the problems at the bottom
    assert svg.index(">branch<") < svg.index(">io<")
    assert "Rows best first." in svg


def test_draft_contracts_are_marked_in_words_not_italics():
    cells = {"go": {"telemetry": _cell(0.5, 0.5, "ok")}}
    svg = fvc.render_summary_svg(FAMILIES, LANGUAGES, DEFINED, cells, {})
    assert "telemetry (draft)" in svg


def test_matrix_has_no_dots_no_rainbow_and_names_every_state():
    svg = fvc.render_matrix_svg(FAMILIES, LANGUAGES, DEFINED, CELLS, DECOYS)
    assert svg == fvc.render_matrix_svg(FAMILIES, LANGUAGES, DEFINED, CELLS, DECOYS)
    assert "Keyword-family matrix (maintainers)" in svg
    for label in (
        "not tested yet",
        "decoy test only (SOP-001 first-pass, SOP-002 spec-grade): grey",
        "parser: construct never seen",
        "N/A: no rule",
        "Decoy tiers: grey now (SOP-001, SOP-002). Stricter tiers (SOP-003 and later) take more colour",
    ):
        assert label in svg
    assert 'class="dg"' not in svg and "green dot" not in svg
    assert "go / io: recall 0.33, precision 0.62" in svg and "prometheus (not pinned)" in svg
    assert (
        "c / io: decoy test (untiered) with &#x27;fopen&#x27;: in a comment ignored (pass); in a string literal counts"
        in svg
    )
    assert "in a comment LEAKS" in svg  # the detail is in the hover, not in the colour
    assert all(fill in svg for fill in fvc.BIN_FILLS[:2])


def test_columns_put_scored_languages_first():
    assert fvc._order(LANGUAGES, FAMILIES, DEFINED, CELLS) == ["go", "c", "zig"]


def test_no_baseline_means_every_defined_cell_is_untested(tmp_path):
    assert fvc.load_baseline(tmp_path / "missing.json") == {}
    assert fvc.load_decoys(tmp_path / "missing.json") == {}
    s = fvc.summary(FAMILIES, LANGUAGES, DEFINED, {})
    assert s["scored"] == 0 and s["untested"] == 6 and s["na"] == 3


def test_load_decoys_reads_the_baseline_section(tmp_path):
    path = tmp_path / "b.json"
    path.write_text(json.dumps({"cells": {}, "decoys": DECOYS}), encoding="utf-8")
    assert fvc.load_decoys(path) == DECOYS


def test_markdown_lists_only_scored_languages_and_the_decoy_result():
    md = fvc.render_markdown(FAMILIES, LANGUAGES, DEFINED, CELLS, DECOYS)
    assert "3 measured against a parser" in md and "3 more by a decoy test only" in md
    assert "| go | 2 | io (0.33 / 0.62) |" in md
    assert "| c | 1 | branch (1.0 / 0.03) |" in md
    assert "zig" not in md
    assert "a keyword in a comment is ignored in 2 of 3 cells" in md and "counted in 1 of 2" in md


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


def test_committed_baseline_names_real_families_and_languages():
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
    for lang, rows in fvc.load_decoys().items():
        assert lang in langs, lang
        for rule, dec in rows.items():
            assert rule in keys, (lang, rule)
            assert dec["comment"] in {"pass", "leak"} and dec["keyword"]


def test_the_charts_are_published_pages_not_committed_files():
    """They are rendered by generated_docs.py from the committed baseline, so a PR commits no SVG and cannot collide on one."""
    import generated_docs

    pages = {rel: fn for rel, fn in generated_docs.PAGES.items() if "family_validity" in rel}
    assert set(pages) == {"docs/self_scan/family_validity_chart.svg", "docs/self_scan/family_validity_matrix.svg"}
    for rel, fn in pages.items():
        svg = fn()
        assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>"), rel


def test_every_decoy_tier_is_the_one_grey_and_only_the_hover_tells_them_apart():
    """Owner ruling 2026-11-27: only a parser carries score colours. First-pass (SOP-001) and spec-grade (SOP-002) decoys are both grade 0."""
    clean = {"comment": "pass", "string_counts": False, "keyword": "k", "corpus": "r", "protocol": "SOP-001-v1"}
    strings = {**clean, "string_counts": True, "protocol": "SOP-002-v1"}
    leak = {**clean, "comment": "leak", "ident_boundary": "leak"}
    assert {fvc.decoy_fill(d) for d in (clean, strings, leak, {})} == {
        fvc.DECOY_GREY
    }  # a leak is not red, an unknown protocol is grey
    assert (
        len({fvc.MATRIX_COLOR[k] for k in ("untested", "decoy", "empty", "na")}) == 4
    )  # still apart from the other states
    decoys = {"c": {"io": clean}, "go": {"io": strings}, "zig": {"branch": leak}}
    svg = fvc.render_matrix_svg(FAMILIES, LANGUAGES, DEFINED, {}, decoys)
    assert f'fill="{fvc.DECOY_GREY}"><title>' in svg  # the decoy cells carry the grey
    assert "decoy test (first-pass)" in svg and "decoy test (spec-grade)" in svg
    assert "gates run: comment leak; word boundary leak" in svg


def test_a_stricter_tier_tints_toward_the_parser_blue_in_proportion_to_its_grade(monkeypatch):
    assert fvc.decoy_tier({"protocol": "SOP-002-v1"}) == ("spec-grade", 0.0)
    assert fvc.decoy_tier({"protocol": "nope"}) == ("untiered", 0.0)
    monkeypatch.setitem(fvc.DECOY_TIERS, "SOP-003-v1", ("rule-grade", 1.0))
    monkeypatch.setitem(fvc.DECOY_TIERS, "SOP-9-v1", ("half", 0.5))
    assert fvc.decoy_fill({"protocol": "SOP-003-v1"}) == fvc.PARSER_BLUE  # as thorough as a parser: the parser colour
    half = fvc.decoy_fill({"protocol": "SOP-9-v1"})
    assert half not in (fvc.DECOY_GREY, fvc.PARSER_BLUE)
    assert fvc._blend("#000000", "#ffffff", 0.5) == "#808080" and fvc._blend("#102030", "#102030", 0.7) == "#102030"
    assert fvc._blend("#000000", "#ffffff", 2.0) == "#ffffff" and fvc._blend("#000000", "#ffffff", -1.0) == "#000000"


def test_the_readme_figure_shows_no_decoy_rates_only_the_ladder_key():
    decoys = {
        "c": {"io": {"comment": "pass", "string_counts": True, "keyword": "k", "corpus": "r", "protocol": "SOP-001-v1"}}
    }
    svg = fvc.render_summary_svg(FAMILIES, LANGUAGES, DEFINED, CELLS, decoys)
    assert "In a comment: ignored" not in svg and "In a string literal: counted" not in svg
    assert "Decoy tiers: grey now (SOP-001, SOP-002)" in svg
    assert "Grey = a decoy test only" in svg

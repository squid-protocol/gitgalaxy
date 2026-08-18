#!/usr/bin/env python3
"""
tri_comparison_chart.py

The unified entry point: runs the tri-comparison pipeline (gather -> reconcile -> ledger merge)
across GitGalaxy's languages and renders ONE SVG -- docs/self_scan/tri_comparison_chart.svg --
covering all three tools (GitGalaxy, tree-sitter, ctags), unlike tree_sitter_accuracy_audit.py's
chart which only ever had two bars to draw.

USAGE
    python tests/tools/tri_comparison_chart.py --languages python,rust,csharp --write
    python tests/tools/tri_comparison_chart.py --all --write   # every language with a corpus

PANELS: FIVE, MATCHING THE OLD CHART'S SHAPE
    Function Recall, Function Precision, Class Recall, Class Precision, Args Exact-Match. An
    earlier version of this chart collapsed recall and precision into one "existence" panel,
    reasoning that there's no privileged ground truth here to measure false positives against
    the way tree_sitter_accuracy_audit.py's bi-comparison could. That reasoning doesn't actually
    require dropping precision, just redefining it without a privileged ground truth --
    tri_comparison_reconcile.py now computes both from the exact same underlying per-slot
    agreement data:
      - recall_t = (slots tool t reported) / (every slot ANY available tool reported).
      - precision_t = (slots tool t reported that at least one OTHER tool corroborated) /
        (slots tool t reported, period).
    This produces real, differentiated signal, not just more panels for their own sake --
    confirmed on rust: GitGalaxy sits at 100% recall (it's the strict superset -- tree-sitter and
    ctags both independently miss the same 152 real occurrences) but only ~92% precision (some of
    what only GitGalaxy reports isn't corroborated), while tree-sitter/ctags sit at ~92% recall
    but ~100% precision. That's a genuine recall/precision tradeoff, not an artifact of the
    formula.

CSS/HTML CLASS PANELS: OUT OF SCOPE, NOT JUST LOW-SCORING
    GitGalaxy's own `class_start` for css/html targets selector/tag-shaped entities (`.foo {`),
    not OOP-shaped classes -- the bi-comparison chart already treats this as permanently out of
    scope by design (epic #1295), not an unmeasured gap. This chart matches that: css and html
    are excluded from class_recall/class_precision reconciliation entirely (see
    _CLASS_SCOPE_EXCLUDED_LANGS below), not scored and hidden, so a discrepancy ledger entry
    never gets manufactured for a comparison that was never a fair one to begin with.

BAR GROUPS: VARIABLE, NOT ALWAYS THREE
    Every language with real data gets a GitGalaxy bar. Only 24 of GitGalaxy's 45 languages get
    all three (both tree-sitter and ctags available); 7 more get GitGalaxy+tree-sitter only
    (ctags has no parser for them); 9 get GitGalaxy+ctags only (tree-sitter has no grammar for
    them -- ada, agc_assembly, assembly, cobol, embedded_python, m4, scheme, sqlite, yacc); the
    rest render GitGalaxy alone. Bars are drawn compactly -- a 2-bar group is never padded with
    an empty slot for the missing tool -- but ALWAYS in the fixed order GitGalaxy, tree-sitter,
    ctags, so a given vertical position in the stack means the same tool in every row.

    "Real data" is stricter than "the corpus directory exists", in two distinct ways, each
    confirmed by hand rather than assumed:
      - lua and groovy have a language-crucible directory with files in it, but GitGalaxy's own
        language routing finds ZERO files that are actually lua/groovy source (Redis's C
        Lua-embedding code; Groovy tooling written in Java) -- gather_language() returns an empty
        result list, treated identically to a missing corpus directory (embedded_python, sqlite,
        ada): an "awaiting language-crucible corpus" row.
      - jcl and livecode have real, CORRECTLY-routed files (3 real .jcl files; 2 real livecode
        files) but every tool finds zero functions/classes in all of them -- every score is an
        undefined 0/0, not a low one. Same visual "awaiting" treatment, honest wording
        (`LanguageChartData.awaiting_note`) since the corpus genuinely isn't missing here, just
        empty of anything comparable in this small a sample.

GITGALAXY'S BAR: ALWAYS BLUE, ASTERISK FOR AN UNAUDITED LOSS
    An earlier version of this chart turned GitGalaxy's bar gray when it lost to another
    available tool and that gap hadn't been investigated. Recoloring an entire bar species read
    as more alarming than intended and made the chart harder to scan at a glance for a value that
    hasn't actually changed meaning -- GitGalaxy's bar is now ALWAYS its normal categorical blue.
    The same "beaten and not yet investigated" signal instead appends `*` to GitGalaxy's OWN
    value label for that cell (e.g. `126/259*`) -- still visible, far less visually loud. See
    docs/self_scan/how_to_investigate_a_discrepancy.md for what an asterisk is asking for.

    Recall and precision fail in OPPOSITE shapes, and the asterisk check has to know which one
    it's looking at -- confirmed the hard way: GitGalaxy's rust func PRECISION (92.1%, genuinely
    beaten by both tree-sitter and ctags at 100%) first shipped with no `*` at all, because the
    check only looked for GitGalaxy on recall's failure side (`dissenting_tools`, "GitGalaxy
    missed something real"), and precision's failure side is the opposite one (`agreeing_tools`
    == just GitGalaxy alone, "GitGalaxy claims something nobody corroborates"). Each panel below
    passes its own `aspect` ("recall" or "precision") to `is_language_metric_clean()` -- see that
    function's own docstring in tri_comparison_ledger.py for the full reasoning.

VALUE LABELS: CENTERED ON EACH BAR, NOT STACKED TO THE SIDE
    Each bar carries its own `matched/total` label centered horizontally within the bar-track
    (the fixed-width background, not the variable-length fill -- so a short bar's label doesn't
    end up crammed against its own left edge), in white for contrast against the saturated fill.

WINNER BADGE
    The space a stacked column of raw numbers used to occupy (to the right of each panel) now
    holds ONE badge per (language, panel): a colored letter -- G/T/C -- naming whichever
    available tool scored strictly highest there, in that tool's own categorical color. No badge
    at all when there's a tie for the top score (including a 1-bar group, which can't have a
    "winner" over nothing) -- a badge only ever appears when there's an actual winner to name.

COLOR SOURCE
    Categorical slots 1-3 of the validated reference palette (see the `dataviz` skill's
    references/palette.md) -- GitGalaxy=blue, tree-sitter=orange, ctags=aqua. Those three slots
    are the ones documented as clearing the ALL-PAIRS CVD/contrast gates in both light and dark
    mode, the relevant gate for a small-multiples chart with this many rows.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ctags_reader  # noqa: E402
import tri_comparison_ledger as ledger_mod  # noqa: E402
from tri_comparison_reconcile import ALL_TOOLS, MetricScore, reconcile_symbols  # noqa: E402

CHART_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "self_scan" / "tri_comparison_chart.svg"

# The 45 languages with real structural signatures (see docs/language_status/README.md) --
# NODE_MAPS's 31 tree-sitter-baselined languages plus the 14 GitGalaxy extracts from but
# tree-sitter has no grammar for.
_GG_ONLY_LANGS = (
    "abap", "ada", "agc_assembly", "assembly", "cobol", "dockerfile", "embedded_python",
    "jcl", "livecode", "m4", "scheme", "sqlite", "yacc", "yaml",
)

# See module docstring's CSS/HTML CLASS PANELS section -- class_start there targets
# selector/tag-shaped entities, not OOP classes; excluded from class reconciliation entirely
# (epic #1295 precedent), not scored and hidden.
_CLASS_SCOPE_EXCLUDED_LANGS = frozenset({"css", "html"})

_TOOL_LABEL = {"gitgalaxy": "GitGalaxy", "tree_sitter": "tree-sitter", "ctags": "ctags"}
_TOOL_BADGE_LETTER = {"gitgalaxy": "G", "tree_sitter": "T", "ctags": "C"}

# Categorical palette slots 1-3 (validated all-pairs, both modes -- see dataviz skill's
# references/palette.md). Light-mode values; this is a static, light-surface-only SVG, matching
# tree_sitter_accuracy_chart.svg's own precedent.
_COLOR_GITGALAXY = "#2a78d6"
_COLOR_TREE_SITTER = "#eb6834"
_COLOR_CTAGS = "#1baf7a"
_COLOR_TOOL = {"gitgalaxy": _COLOR_GITGALAXY, "tree_sitter": _COLOR_TREE_SITTER, "ctags": _COLOR_CTAGS}


def all_languages() -> list[str]:
    import tree_sitter_accuracy_audit as tsaa

    return sorted(set(tsaa.NODE_MAPS.keys()) | set(_GG_ONLY_LANGS))


def _available_tools(lang: str) -> tuple[str, ...]:
    import tree_sitter_accuracy_audit as tsaa

    tools = ["gitgalaxy"]
    if lang in tsaa.NODE_MAPS:
        tools.append("tree_sitter")
    if ctags_reader.ctags_available(lang):
        tools.append("ctags")
    return tuple(tools)


def _corpus_exists(lang: str) -> bool:
    import os

    root = Path(os.environ.get("LANGUAGE_CRUCIBLE_PATH", Path(__file__).resolve().parent.parent.parent.parent / "language-crucible"))
    return (root / "data" / lang).exists()


class LanguageChartData:
    def __init__(self, lang: str):
        self.lang = lang
        self.available_tools = _available_tools(lang)
        self.has_data = _corpus_exists(lang)  # refined in run_pipeline once gather actually runs
        self.awaiting_note = "awaiting language-crucible corpus"
        self.func_recall: dict[str, MetricScore] = {}
        self.func_precision: dict[str, MetricScore] = {}
        self.class_recall: dict[str, MetricScore] = {}
        self.class_precision: dict[str, MetricScore] = {}
        self.args: dict[str, MetricScore] = {}


def run_pipeline(languages: list[str], verbose: bool = True) -> dict[str, LanguageChartData]:
    from tri_comparison_gatherer import gather_language

    out: dict[str, LanguageChartData] = {}
    for lang in languages:
        data = LanguageChartData(lang)
        out[lang] = data
        if not data.has_data:
            if verbose:
                print(f"tri_comparison_chart: {lang} -- no language-crucible corpus, skipping (awaiting data)")
            continue
        if verbose:
            print(f"tri_comparison_chart: {lang} -- gathering ({', '.join(data.available_tools)})...")
        try:
            results = gather_language(lang)
        except SystemExit as e:
            if verbose:
                print(f"tri_comparison_chart: {lang} -- gather failed ({e}), skipping")
            data.has_data = False
            continue

        if not results:
            # Corpus directory exists but GitGalaxy's own language routing found zero files
            # actually written in this language (confirmed cases: lua, groovy -- see module
            # docstring). Functionally identical to no corpus at all for chart purposes.
            if verbose:
                print(f"tri_comparison_chart: {lang} -- corpus has no real {lang} files, treating as awaiting data")
            data.has_data = False
            continue

        func_recall, func_precision, args_scores, func_groups = reconcile_symbols(
            results, "function", data.available_tools
        )
        data.func_recall = func_recall
        data.func_precision = func_precision
        data.args = args_scores

        class_groups: list = []
        if lang not in _CLASS_SCOPE_EXCLUDED_LANGS:
            class_recall, class_precision, _, class_groups = reconcile_symbols(
                results, "class", data.available_tools
            )
            data.class_recall = class_recall
            data.class_precision = class_precision

        # Different case from the empty-results one above: real, correctly-routed files exist
        # (confirmed cases: jcl -- 3 real .jcl files; livecode -- 2 real files) but EVERY tool
        # found zero functions/classes in all of them, so every score is an undefined 0/0
        # (MetricScore.rate_pct is None). Rendering three empty bar-tracks with no bars at all
        # reads as a broken row, not a "nothing to compare" one -- same visual "awaiting" note,
        # honest wording since the corpus genuinely isn't missing here.
        any_real_score = any(
            s.rate_pct is not None
            for d in (data.func_recall, data.class_recall, data.args)
            for s in d.values()
        )
        if not any_real_score:
            if verbose:
                print(f"tri_comparison_chart: {lang} -- {len(results)} real file(s) but 0 functions/classes found by any tool")
            data.has_data = False
            data.awaiting_note = "no functions/classes found in this corpus by any tool"

        ledger_mod.merge_and_save(lang, func_groups + class_groups, path=ledger_mod.LEDGER_PATH)
    return out


def _gg_needs_asterisk(lang: str, symbol_type: str, ledger_metric: str, aspect: str) -> bool:
    return not ledger_mod.is_language_metric_clean(
        lang, symbol_type, ledger_metric, path=ledger_mod.LEDGER_PATH, aspect=aspect
    )


def _winner_or_tie(scores: dict[str, MetricScore], available_tools: tuple[str, ...]) -> str | None:
    """Tool name with the strictly-highest score among available tools with real data; the
    literal string "tie" if 2+ tools share the top score; None if fewer than 2 tools have real
    data at all (a 1-bar group, or an empty panel) -- that last case isn't a comparison, so it's
    kept distinct from a real tie rather than folded into it. The badge renderer only cares about
    the winner case (see _winner below); the bottom-of-chart tally (render_chart's summary
    block) needs all three states to count "how many of the 5x45 possible comparisons actually
    happened, and how did each one resolve" without silently inflating the tie count with cells
    that were never a real comparison to begin with."""
    vals = [(t, scores[t].rate_pct) for t in available_tools if t in scores and scores[t].rate_pct is not None]
    if len(vals) < 2:
        return None
    vals.sort(key=lambda tv: -tv[1])
    if vals[0][1] == vals[1][1]:
        return "tie"
    return vals[0][0]


def _winner(scores: dict[str, MetricScore], available_tools: tuple[str, ...]) -> str | None:
    """Tool name with the strictly-highest score, or None on a tie OR no real comparison --
    the coarser two-way split the badge renderer actually needs (draw a badge, or don't)."""
    result = _winner_or_tie(scores, available_tools)
    return result if result != "tie" else None


_CHART_STYLE = """<style>
  .surface { fill: #fcfcfb; }
  .title { font-size: 15px; font-weight: 600; fill: #0b0b0b; }
  .subtitle { font-size: 11px; fill: #52514e; }
  .scope-note { font-size: 10px; fill: #706f6a; }
  .panel-title { font-size: 10.5px; font-weight: 600; fill: #0b0b0b; text-anchor: middle; }
  .summary-title { font-size: 10.5px; font-weight: 600; fill: #0b0b0b; text-anchor: start; }
  .lang-label { font-size: 13px; font-weight: 700; fill: #0b0b0b; }
  .bar-value-label { font-size: 8px; fill: #ffffff; text-anchor: middle; font-weight: 600; }
  .legend-label { font-size: 10px; fill: #0b0b0b; }
  .stripe { fill: #f0efec; }
  .awaiting { font-size: 9.5px; fill: #9a9a95; font-style: italic; }
  .bar-track { fill: #eeede9; }
  .badge-label { font-size: 8.5px; font-weight: 700; fill: #ffffff; text-anchor: middle; }
</style>"""


def render_chart(data_by_lang: dict[str, LanguageChartData]) -> str:
    from datetime import datetime, timezone

    langs = sorted(data_by_lang.keys())
    n = len(langs)

    label_col_w = 138  # room for "embedded_python" (longest name) bold at 13px
    bar_max_w = 88
    badge_col_w = 20
    inner_gap = 6
    panel_w = bar_max_w + inner_gap + badge_col_w
    panel_gap = 18
    left_margin, right_margin = 16, 16
    top_margin = 128
    header_h = 20
    bottom_margin = 44
    bar_h = 10
    sub_gap = 2
    row_pad = 5
    row_h = row_pad * 2 + 3 * bar_h + 2 * sub_gap  # room for up to 3 stacked bars, always

    # (data attr, symbol_type, ledger metric, panel title, asterisk aspect -- see
    # ledger_mod.is_language_metric_clean's own docstring for why recall and precision need
    # different aspects, not just different data)
    panels = [
        ("func_recall", "function", "existence", "Func Recall", "recall"),
        ("func_precision", "function", "existence", "Func Precision", "precision"),
        ("class_recall", "class", "existence", "Class Recall", "recall"),
        ("class_precision", "class", "existence", "Class Precision", "precision"),
        ("args", "function", "args", "Args Match", "recall"),
    ]

    panels_x_start = left_margin + label_col_w
    width = panels_x_start + len(panels) * panel_w + (len(panels) - 1) * panel_gap + right_margin

    # Tally: one vote per (language, panel) cell that's an actual comparison (2+ tools with real
    # data) -- 5 panels x up to 45 languages, but a 1-bar group or an empty panel (css/html class,
    # a blank args column) contributes no vote at all, per _winner_or_tie's own docstring on why
    # "no comparison happened" has to stay distinct from "it was a tie".
    tally: Counter[str] = Counter()
    for data in data_by_lang.values():
        if not data.has_data:
            continue
        for attr, _, _, _, _ in panels:
            scores = getattr(data, attr)
            if not scores:
                continue
            result = _winner_or_tie(scores, data.available_tools)
            if result is not None:
                tally[result] += 1
    total_votes = sum(tally.values())

    summary_h = 76
    height = top_margin + header_h + n * row_h + bottom_margin + summary_h
    rows_top = top_margin + header_h

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        + f'width="{width}" height="{height}" font-family="system-ui, -apple-system, Segoe UI, sans-serif">',
        _CHART_STYLE,
        f'<rect class="surface" x="0" y="0" width="{width}" height="{height}"/>',
        f'<text class="title" x="{left_margin}" y="20">GitGalaxy Structural Extraction: Tri-Comparison '
        + f"vs. Tree-sitter and ctags</text>",
        f'<text class="subtitle" x="{left_margin}" y="36">{datetime.now(timezone.utc).strftime("%Y-%m-%d")} '
        + f"&#183; source: tests/tools/tri_comparison_chart.py &#183; "
        + f"ledger: docs/self_scan/tri_comparison_ledger.json</text>",
        f'<text class="scope-note" x="{left_margin}" y="52">No tool is ground truth -- recall is vs. '
        + f"everything anyone found, precision is vs. what each tool itself claimed.</text>",
        f'<text class="scope-note" x="{left_margin}" y="64">Bar groups vary 1-3 by language\'s tool coverage '
        + f"-- order is always GitGalaxy, tree-sitter, ctags. css/html class panels are out of "
        + f"scope by design (selectors, not OOP classes).</text>",
        f'<text class="scope-note" x="{left_margin}" y="76">GitGalaxy\'s bar is always blue; `*` marks an '
        + f"unaudited loss to another tool, not a verdict. Badge = the tool that scored strictly "
        + f"highest (blank on a tie).</text>",
        f'<text class="scope-note" x="{left_margin}" y="88">See docs/self_scan/how_to_investigate_a_discrepancy.md '
        + f"for what `*` is asking for.</text>",
    ]

    legend_y = 108
    lx = left_margin
    for tool in ALL_TOOLS:
        parts.append(f'<rect x="{lx}" y="{legend_y - 8}" width="14" height="8" rx="2" fill="{_COLOR_TOOL[tool]}"/>')
        parts.append(f'<text class="legend-label" x="{lx + 18}" y="{legend_y}">{_TOOL_LABEL[tool]}</text>')
        lx += 18 + 9 * len(_TOOL_LABEL[tool]) + 20
    parts.append(f'<text class="legend-label" x="{lx}" y="{legend_y}">* = GitGalaxy, unaudited loss</text>')

    for i, (_, _, _, title, _) in enumerate(panels):
        px = panels_x_start + i * (panel_w + panel_gap)
        parts.append(
            f'<text class="panel-title" x="{px + (bar_max_w + inner_gap + badge_col_w) / 2}" '
            f'y="{top_margin + header_h - 4}">{title}</text>'
        )

    for row_i, lang in enumerate(langs):
        y = rows_top + row_i * row_h
        data = data_by_lang[lang]
        if row_i % 2 == 0:
            parts.append(f'<rect class="stripe" x="{left_margin}" y="{y}" width="{width - left_margin - right_margin}" height="{row_h}"/>')
        parts.append(f'<text class="lang-label" x="{left_margin + 4}" y="{y + row_h / 2 + 3.5}">{lang}</text>')

        if not data.has_data:
            parts.append(f'<text class="awaiting" x="{panels_x_start}" y="{y + row_h / 2 + 3.5}">{data.awaiting_note}</text>')
            continue

        for panel_i, (attr, symbol_type, ledger_metric, _, aspect) in enumerate(panels):
            px = panels_x_start + panel_i * (panel_w + panel_gap)
            scores: dict[str, MetricScore] = getattr(data, attr)
            if not scores:
                continue  # class panel on a css/html row, or a metric with no comparable data
            bar_y = y + row_pad
            track_h = 3 * bar_h + 2 * sub_gap
            parts.append(f'<rect class="bar-track" x="{px}" y="{bar_y}" width="{bar_max_w}" height="{track_h}" rx="2"/>')
            for tool in data.available_tools:
                if tool not in scores or scores[tool].rate_pct is None:
                    continue
                score = scores[tool]
                w = max(2, bar_max_w * score.rate_pct / 100.0)
                color = _COLOR_TOOL[tool]
                parts.append(f'<rect x="{px}" y="{bar_y}" width="{w:.1f}" height="{bar_h}" rx="2" fill="{color}"/>')
                label = f"{score.matched_consensus}/{score.total_slots}"
                if tool == "gitgalaxy" and _gg_needs_asterisk(lang, symbol_type, ledger_metric, aspect):
                    label += "*"
                parts.append(
                    f'<text class="bar-value-label" x="{px + bar_max_w / 2}" y="{bar_y + bar_h - 2}">{label}</text>'
                )
                bar_y += bar_h + sub_gap

            winner = _winner(scores, data.available_tools)
            if winner:
                bx = px + bar_max_w + inner_gap + badge_col_w / 2
                by = y + row_h / 2
                parts.append(f'<circle cx="{bx}" cy="{by}" r="8" fill="{_COLOR_TOOL[winner]}"/>')
                parts.append(f'<text class="badge-label" x="{bx}" y="{by + 3}">{_TOOL_BADGE_LETTER[winner]}</text>')

    summary_top = rows_top + n * row_h + 20
    parts.append(f'<line x1="{left_margin}" y1="{summary_top - 10}" x2="{width - right_margin}" y2="{summary_top - 10}" stroke="#dedcd6" stroke-width="1"/>')
    parts.append(
        f'<text class="summary-title" x="{left_margin}" y="{summary_top + 4}">'
        f"Summary -- best tool per (language, metric), {total_votes} real comparisons "
        f'(1-bar groups and empty panels don\'t count)</text>'
    )
    stat_y = summary_top + 26
    sx = left_margin
    for tool in ALL_TOOLS:
        count = tally.get(tool, 0)
        pct = 100.0 * count / total_votes if total_votes else 0.0
        parts.append(f'<circle cx="{sx + 7}" cy="{stat_y - 4}" r="7" fill="{_COLOR_TOOL[tool]}"/>')
        parts.append(f'<text class="badge-label" x="{sx + 7}" y="{stat_y - 1}">{_TOOL_BADGE_LETTER[tool]}</text>')
        stat_text = f"{_TOOL_LABEL[tool]} best: {count} ({pct:.0f}%)"
        parts.append(f'<text class="legend-label" x="{sx + 20}" y="{stat_y}">{stat_text}</text>')
        sx += 20 + 6.2 * len(stat_text) + 24
    tie_count = tally.get("tie", 0)
    tie_pct = 100.0 * tie_count / total_votes if total_votes else 0.0
    parts.append(f'<circle cx="{sx + 7}" cy="{stat_y - 4}" r="7" fill="#9a9a95"/>')
    parts.append(f'<text class="legend-label" x="{sx + 20}" y="{stat_y}">Ties: {tie_count} ({tie_pct:.0f}%)</text>')

    footer_y = summary_top + 46
    parts.append(
        f'<text class="scope-note" x="{left_margin}" y="{footer_y}">Value labels are raw counts '
        f"(matched/total). Regenerate: tri_comparison_chart.py --all --write</text>"
    )
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--languages", help="Comma-separated language list.")
    group.add_argument("--all", action="store_true", help="Every language with a corpus available.")
    parser.add_argument("--write", action="store_true", help=f"Write SVG to {CHART_PATH}.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    languages = all_languages() if args.all else [s.strip() for s in args.languages.split(",")]
    data = run_pipeline(languages, verbose=not args.quiet)
    svg = render_chart(data)

    if args.write:
        CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
        CHART_PATH.write_text(svg)
        print(f"tri_comparison_chart: wrote {CHART_PATH}")
    else:
        print(svg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

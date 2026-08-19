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

PANELS: FIVE, BUT ONLY TWO ARE RANKED
    Functions Found, Function Precision, Classes Found, Class Precision, Args Found.

    RECALL AND ARGS-MATCH WERE REMOVED AS RATIOS -- THEIR DENOMINATORS AREN'T TRUSTWORTHY
    ENOUGH TO RANK ON YET
        An earlier version of this chart rendered "Func/Class Recall" as matched/union (every
        slot ANY available tool reported) and "Args Match" as matched-the-cross-tool-majority /
        comparable. Both sounded principled but share the same flaw: BOTH require trusting an
        unverified cross-tool agreement as if it were correctness, and both are exactly as
        unreliable as any one tool's own noise -- confirmed twice on real data, not
        theoretically: ctags' Haskell parser double/triple-tags multi-clause functions (one tag
        per pattern-match equation), and tree-sitter's own raw walk had the identical bug for the
        same language before it was fixed earlier in this effort. Either bug inflates a SHARED
        denominator (recall's union) or corrupts a "majority" (args' 2-vs-1 credit), silently
        distorting every OTHER tool's score too -- a ranking built on unverified cross-tool
        agreement isn't a ranking worth showing yet. Reporting the bare found-count instead (no
        ratio, no implied "of how many" or "how many matched") sidesteps the problem entirely:
        it's just what each tool actually claimed, full stop, not scored against anything
        uncertain. Once a language/metric's ledger shapes are validated (see
        docs/self_scan/how_to_investigate_a_discrepancy.md), a real denominator can come back for
        that language specifically -- this is a deliberate, temporary state, not a permanent
        downgrade.
    PRECISION SURVIVES BECAUSE ITS DENOMINATOR IS DIFFERENT IN KIND, NOT DEGREE
        precision_t = (slots tool t reported that at least one OTHER tool corroborated) / (slots
        tool t reported, period) -- the denominator is that SAME tool's own claim count, never a
        cross-tool union or majority vote. A tool can't inflate its own precision denominator by
        being noisy elsewhere the way it can inflate everyone's shared recall denominator or skew
        an args majority. This is exactly the "of what we found, how many are real" framing --
        confirmed differentiated on rust: GitGalaxy's ~92% precision there (some GitGalaxy-only
        claims uncorroborated) is a genuine signal a bare found-count alone wouldn't show.

    Found-count panels never render a winner badge and never enter the bottom summary tally --
    "found more" isn't a claim that tool is more correct (more found is what a hallucinating
    tool does too), so there's no ranking to declare. Only the two genuinely ranked panels
    (Func/Class Precision) produce a badge and count toward the summary.

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

EVERY TOOL'S BAR IS ALWAYS ITS OWN COLOR; ASTERISK MEANS "NOT YET VERIFIED", NOT "LOST"
    An earlier version of this chart turned GitGalaxy's bar gray when it lost to another
    available tool and that gap hadn't been investigated, then later moved to asterisking only
    GitGalaxy's own label. Both versions singled GitGalaxy out, which was backwards: the open
    question in a disputed cell is "has anyone actually read the source and confirmed who's
    right", and that question applies to EVERY tool shown there, not just GitGalaxy. Every
    tool's bar is always its normal categorical color; `*` now appends to EVERY tool's value
    label in a cell with any currently-reproducing, unvalidated ledger entry for that
    (language, symbol_type, metric) -- see `ledger_mod.has_open_question()` and
    docs/self_scan/how_to_investigate_a_discrepancy.md for what an asterisk is asking for.

VALUE LABELS: CENTERED ON EACH BAR, NOT STACKED TO THE SIDE
    Each bar carries its own value label (a ranked panel's `matched/total`, or a found-count
    panel's bare count) centered horizontally within the bar-track (the fixed-width background,
    not the variable-length fill -- so a short bar's label doesn't end up crammed against its own
    left edge), in white for contrast against the saturated fill.

WINNER BADGE: REQUIRES VERIFICATION, NOT JUST THE HIGHER NUMBER
    A badge implies "we know who's actually right" -- a raw percentage comparison alone isn't
    enough to earn that claim. Confirmed necessary by a real case, not a hypothetical: under a
    pure highest-rate_pct rule, a 2-sample cell at 100% (2/2) outranked an 80-sample cell at
    98.75% (79/80) with a badge exactly as confident-looking as any other, an artifact of sample
    size nobody had verified, not evidence that tool was more correct there. A cell only gets a
    badge now if `has_open_question()` is False for it (no ledger entry currently reproduces
    unvalidated) AND one available tool scored strictly highest -- a colored letter (G/T/C) in
    that tool's own categorical color, in the space a stacked column of raw numbers used to
    occupy. No badge on a disputed cell (regardless of how lopsided the raw numbers look), a
    tie, or a 1-bar group (which can't have a "winner" over nothing).

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
    "abap",
    "ada",
    "agc_assembly",
    "assembly",
    "cobol",
    "dockerfile",
    "embedded_python",
    "jcl",
    "livecode",
    "m4",
    "scheme",
    "sqlite",
    "yacc",
    "yaml",
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

    root = Path(
        os.environ.get(
            "LANGUAGE_CRUCIBLE_PATH", Path(__file__).resolve().parent.parent.parent.parent / "language-crucible"
        )
    )
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
            class_recall, class_precision, _, class_groups = reconcile_symbols(results, "class", data.available_tools)
            data.class_recall = class_recall
            data.class_precision = class_precision

        # Different case from the empty-results one above: real, correctly-routed files exist
        # (confirmed cases: jcl -- 3 real .jcl files; livecode -- 2 real files) but EVERY tool
        # found zero functions/classes in all of them, so every score is an undefined 0/0
        # (MetricScore.rate_pct is None). Rendering three empty bar-tracks with no bars at all
        # reads as a broken row, not a "nothing to compare" one -- same visual "awaiting" note,
        # honest wording since the corpus genuinely isn't missing here.
        any_real_score = any(
            s.rate_pct is not None for d in (data.func_recall, data.class_recall, data.args) for s in d.values()
        )
        if not any_real_score:
            if verbose:
                print(
                    f"tri_comparison_chart: {lang} -- {len(results)} real file(s) but 0 functions/classes found by any tool"
                )
            data.has_data = False
            data.awaiting_note = "no functions/classes found in this corpus by any tool"

        ledger_mod.merge_and_save(lang, func_groups + class_groups, path=ledger_mod.LEDGER_PATH)
    return out


def _disputed(lang: str, symbol_type: str, ledger_metric: str) -> bool:
    return ledger_mod.has_open_question(lang, symbol_type, ledger_metric, path=ledger_mod.LEDGER_PATH)


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

    # (data attr, symbol_type, ledger metric, panel title, ranked, found_field -- see
    # ledger_mod.has_open_question's own docstring for the asterisk/badge gating this drives,
    # symmetric across all three tools now regardless of panel. `ranked` False means "found
    # count, no bar-width ratio, no winner badge, doesn't enter the summary tally" -- see module
    # docstring's PANELS section for why the two existence panels AND args dropped their ratio.
    # `found_field` is which MetricScore attribute IS the found-count on an unranked panel:
    # func/class use matched_consensus (this tool's own raw claim count, gate-free); args uses
    # total_slots instead, since args_scores' matched_consensus already means "matched the
    # cross-tool majority" -- exactly the pre-verification correctness claim this panel is
    # deliberately NOT making yet, so it can't be reused as a neutral "found" count the way
    # func/class's can.)
    panels = [
        ("func_recall", "function", "existence", "Functions Found", False, "matched_consensus"),
        ("func_precision", "function", "existence", "Func Precision", True, None),
        ("class_recall", "class", "existence", "Classes Found", False, "matched_consensus"),
        ("class_precision", "class", "existence", "Class Precision", True, None),
        ("args", "function", "args", "Args Found", False, "total_slots"),
    ]

    panels_x_start = left_margin + label_col_w
    width = panels_x_start + len(panels) * panel_w + (len(panels) - 1) * panel_gap + right_margin

    # Tally: one vote per (language, panel) cell that's an actual comparison (2+ tools with real
    # data) AND not disputed (see WINNER BADGE module docstring -- a badge/vote requires
    # has_open_question() to be False, not just a highest score) -- up to 2 ranked panels x 45
    # languages, but a 1-bar group, an empty panel (css/html class), or a still-disputed cell
    # contributes no vote at all, per _winner_or_tie's own docstring on why "no comparison
    # happened" has to stay distinct from "it was a tie".
    tally: Counter[str] = Counter()
    for lang, data in data_by_lang.items():
        if not data.has_data:
            continue
        for attr, symbol_type, ledger_metric, _, ranked, _ in panels:
            if not ranked:
                continue
            scores = getattr(data, attr)
            if not scores:
                continue
            if _disputed(lang, symbol_type, ledger_metric):
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
        f'<text class="scope-note" x="{left_margin}" y="52">No tool is ground truth. Found-count panels '
        + f'are unranked raw counts (no badge) -- a shared "how many are real" denominator turned out '
        + f"as corruptible as any one tool's own noise. Precision is each tool's own claims vs. what "
        + f"another tool corroborated.</text>",
        f'<text class="scope-note" x="{left_margin}" y="64">Bar groups vary 1-3 by language\'s tool coverage '
        + f"-- order is always GitGalaxy, tree-sitter, ctags. css/html class panels are out of "
        + f"scope by design (selectors, not OOP classes).</text>",
        f'<text class="scope-note" x="{left_margin}" y="76">`*` marks EVERY tool\'s label in a cell with '
        + f"any unvalidated disagreement, not just GitGalaxy's -- not a verdict either way. Badge = "
        + f"the tool that scored strictly highest on a RANKED, UN-disputed panel (blank on a tie, a "
        + f"disputed cell, or a found-count panel).</text>",
        f'<text class="scope-note" x="{left_margin}" y="88">See docs/self_scan/how_to_investigate_a_discrepancy.md '
        + f"for what `*` is asking for.</text>",
    ]

    legend_y = 108
    lx = left_margin
    for tool in ALL_TOOLS:
        parts.append(f'<rect x="{lx}" y="{legend_y - 8}" width="14" height="8" rx="2" fill="{_COLOR_TOOL[tool]}"/>')
        parts.append(f'<text class="legend-label" x="{lx + 18}" y="{legend_y}">{_TOOL_LABEL[tool]}</text>')
        lx += 18 + 9 * len(_TOOL_LABEL[tool]) + 20
    parts.append(f'<text class="legend-label" x="{lx}" y="{legend_y}">* = unvalidated disagreement here</text>')

    for i, (_, _, _, title, _, _) in enumerate(panels):
        px = panels_x_start + i * (panel_w + panel_gap)
        parts.append(
            f'<text class="panel-title" x="{px + (bar_max_w + inner_gap + badge_col_w) / 2}" '
            f'y="{top_margin + header_h - 4}">{title}</text>'
        )

    for row_i, lang in enumerate(langs):
        y = rows_top + row_i * row_h
        data = data_by_lang[lang]
        if row_i % 2 == 0:
            parts.append(
                f'<rect class="stripe" x="{left_margin}" y="{y}" width="{width - left_margin - right_margin}" height="{row_h}"/>'
            )
        parts.append(f'<text class="lang-label" x="{left_margin + 4}" y="{y + row_h / 2 + 3.5}">{lang}</text>')

        if not data.has_data:
            parts.append(
                f'<text class="awaiting" x="{panels_x_start}" y="{y + row_h / 2 + 3.5}">{data.awaiting_note}</text>'
            )
            continue

        for panel_i, (attr, symbol_type, ledger_metric, _, ranked, found_field) in enumerate(panels):
            px = panels_x_start + panel_i * (panel_w + panel_gap)
            scores: dict[str, MetricScore] = getattr(data, attr)
            if not scores:
                continue  # class panel on a css/html row, or a metric with no comparable data
            bar_y = y + row_pad
            track_h = 3 * bar_h + 2 * sub_gap
            parts.append(
                f'<rect class="bar-track" x="{px}" y="{bar_y}" width="{bar_max_w}" height="{track_h}" rx="2"/>'
            )

            # Symmetric across all three tools now -- see EVERY TOOL'S BAR / WINNER BADGE module
            # docstring sections. Computed once per panel, not per tool: it's a property of the
            # (language, symbol_type, metric) cell, not of any one tool's reading within it.
            disputed = _disputed(lang, symbol_type, ledger_metric)

            # Found-count panels have no privileged denominator to scale against (see module
            # docstring) -- bar width is relative to this ROW's own highest found-count instead,
            # purely a visual "who claimed more" cue, never a percentage of anything.
            row_max_found = (
                max(
                    (
                        getattr(scores[t], found_field)
                        for t in data.available_tools
                        if t in scores and scores[t].rate_pct is not None
                    ),
                    default=0,
                )
                if not ranked
                else 0
            )
            for tool in data.available_tools:
                if tool not in scores or scores[tool].rate_pct is None:
                    continue
                score = scores[tool]
                color = _COLOR_TOOL[tool]
                if ranked:
                    w = max(2, bar_max_w * score.rate_pct / 100.0)
                    label = f"{score.matched_consensus}/{score.total_slots}"
                else:
                    found = getattr(score, found_field)
                    w = max(2, bar_max_w * found / row_max_found) if row_max_found else 2
                    label = f"{found}"
                parts.append(f'<rect x="{px}" y="{bar_y}" width="{w:.1f}" height="{bar_h}" rx="2" fill="{color}"/>')
                if disputed:
                    label += "*"
                parts.append(
                    f'<text class="bar-value-label" x="{px + bar_max_w / 2}" y="{bar_y + bar_h - 2}">{label}</text>'
                )
                bar_y += bar_h + sub_gap

            if ranked and not disputed:
                winner = _winner(scores, data.available_tools)
                if winner:
                    bx = px + bar_max_w + inner_gap + badge_col_w / 2
                    by = y + row_h / 2
                    parts.append(f'<circle cx="{bx}" cy="{by}" r="8" fill="{_COLOR_TOOL[winner]}"/>')
                    parts.append(f'<text class="badge-label" x="{bx}" y="{by + 3}">{_TOOL_BADGE_LETTER[winner]}</text>')

    summary_top = rows_top + n * row_h + 20
    parts.append(
        f'<line x1="{left_margin}" y1="{summary_top - 10}" x2="{width - right_margin}" y2="{summary_top - 10}" stroke="#dedcd6" stroke-width="1"/>'
    )
    parts.append(
        f'<text class="summary-title" x="{left_margin}" y="{summary_top + 4}">'
        f"Summary -- best tool per (language, metric), ranked panels only "
        f"(Func/Class Precision), {total_votes} real comparisons "
        f"(1-bar groups and empty panels don't count)</text>"
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
        f'<text class="scope-note" x="{left_margin}" y="{footer_y}">Ranked-panel labels are '
        f"matched/total; found-count panels are a single raw count, no denominator. "
        f"Regenerate: tri_comparison_chart.py --all --write</text>"
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

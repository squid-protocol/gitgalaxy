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

PANELS
    Three, not five: Function Existence, Class Existence, Args Exact-Match. Deliberately not the
    old chart's five (func recall, func precision, class recall, class precision, args) --
    tree_sitter_accuracy_audit.py could split recall from precision because it had a privileged
    ground truth to measure false positives against (an "extra" -- something a tool reported that
    ground truth says isn't real). This tool has no privileged ground truth (see
    tri_comparison_reconcile.py's own module docstring for why), so "existence" here is a
    single recall-shaped number: of everything ANY available tool reported, how much did this
    ONE tool also report. A true precision-style "corroboration rate" metric (of what THIS tool
    reported, how much did at least one other tool confirm) is a real, useful, and currently
    MISSING second metric -- noted here rather than silently treated as equivalent to what this
    chart actually shows, and left as a clearly-scoped follow-up rather than guessed at under
    time pressure.

BAR GROUPS: VARIABLE, NOT ALWAYS THREE
    Every language gets a GitGalaxy bar. Only 24 of GitGalaxy's 45 languages get all three (both
    tree-sitter and ctags available); 7 more get GitGalaxy+tree-sitter only (ctags has no parser
    for them); 9 get GitGalaxy+ctags only (tree-sitter has no grammar for them -- ada,
    agc_assembly, assembly, cobol, embedded_python, m4, scheme, sqlite, yacc); the rest render
    GitGalaxy alone. Bars are drawn compactly -- a 2-bar group is never padded with an empty slot
    for the missing tool -- but ALWAYS in the fixed order GitGalaxy, tree-sitter, ctags, so a
    given vertical position in the stack means the same tool in every row that includes it.

GITGALAXY'S BAR: GRAY VS. COLORED
    The one piece of this chart that's a genuine design decision, not just a rendering choice:
    GitGalaxy's bar renders its normal categorical color when it TIES the other available tool(s)
    for a given (language, symbol_type, metric), or when tri_comparison_ledger.py's
    is_language_metric_clean() says every discrepancy where GitGalaxy is on the losing
    (dissenting) side has a validated verdict. It renders GRAY when GitGalaxy's score is lower
    than at least one other available tool's AND at least one of the discrepancies behind that
    gap hasn't been investigated yet (see docs/self_scan/how_to_investigate_a_discrepancy.md).
    Gray means "unaudited," not "wrong" -- tree-sitter and ctags bars never render gray; only
    GitGalaxy's does, because this whole tool exists to audit GitGalaxy specifically, not to
    grade the other two.

COLOR SOURCE
    Categorical slots 1-3 of the validated reference palette (see the `dataviz` skill's
    references/palette.md) -- GitGalaxy=blue, tree-sitter=orange, ctags=aqua. Those three slots
    are the ones documented as clearing the ALL-PAIRS CVD/contrast gates in both light and dark
    mode, the relevant gate for a small-multiples chart with this many rows. The gray override on
    GitGalaxy is a status-like "unaudited" signal, not a fourth series -- reserved, not reused for
    series identity, per the same skill's rule.
"""

from __future__ import annotations

import argparse
import sys
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

_TOOL_LABEL = {"gitgalaxy": "GitGalaxy", "tree_sitter": "tree-sitter", "ctags": "ctags"}
# Fixed tool order everywhere in this chart -- reuses reconcile.py's ALL_TOOLS rather than a
# second, easy-to-drift copy of the same three-tuple.

# Categorical palette slots 1-3 (validated all-pairs, both modes -- see dataviz skill's
# references/palette.md). Light-mode values; this is a static, light-surface-only SVG, matching
# tree_sitter_accuracy_chart.svg's own precedent.
_COLOR_GITGALAXY = "#2a78d6"
_COLOR_TREE_SITTER = "#eb6834"
_COLOR_CTAGS = "#1baf7a"
_COLOR_GRAY = "#9a9a95"  # status-like "unaudited" override on GitGalaxy's bar only
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
        self.corpus_available = _corpus_exists(lang)
        self.func_existence: dict[str, MetricScore] = {}
        self.class_existence: dict[str, MetricScore] = {}
        self.args: dict[str, MetricScore] = {}


def run_pipeline(languages: list[str], verbose: bool = True) -> dict[str, LanguageChartData]:
    from tri_comparison_gatherer import gather_language

    out: dict[str, LanguageChartData] = {}
    for lang in languages:
        data = LanguageChartData(lang)
        out[lang] = data
        if not data.corpus_available:
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
            data.corpus_available = False
            continue

        func_existence, args_scores, func_groups = reconcile_symbols(results, "function", data.available_tools)
        class_existence, _, class_groups = reconcile_symbols(results, "class", data.available_tools)
        data.func_existence = func_existence
        data.class_existence = class_existence
        data.args = args_scores

        ledger_mod.merge_and_save(lang, func_groups + class_groups, path=ledger_mod.LEDGER_PATH)
    return out


def _gg_bar_color(lang: str, symbol_type: str, metric: str) -> str:
    if ledger_mod.is_language_metric_clean(lang, symbol_type, metric, path=ledger_mod.LEDGER_PATH):
        return _COLOR_GITGALAXY
    return _COLOR_GRAY


_CHART_STYLE = """<style>
  .surface { fill: #fcfcfb; }
  .title { font-size: 15px; font-weight: 600; fill: #0b0b0b; }
  .subtitle { font-size: 11px; fill: #52514e; }
  .scope-note { font-size: 10px; fill: #706f6a; }
  .panel-title { font-size: 11px; font-weight: 600; fill: #0b0b0b; text-anchor: middle; }
  .lang-label { font-size: 10.5px; fill: #0b0b0b; }
  .value-label { font-size: 8.5px; fill: #52514e; }
  .legend-label { font-size: 10px; fill: #0b0b0b; }
  .stripe { fill: #f0efec; }
  .awaiting { font-size: 9.5px; fill: #9a9a95; font-style: italic; }
  .bar-track { fill: #eeede9; }
</style>"""


def render_chart(data_by_lang: dict[str, LanguageChartData]) -> str:
    from datetime import datetime, timezone

    langs = sorted(data_by_lang.keys())
    n = len(langs)

    label_col_w = 118
    bar_max_w = 92
    value_label_w = 56
    panel_w = bar_max_w + value_label_w + 10
    panel_gap = 22
    left_margin, right_margin = 16, 16
    top_margin = 128
    header_h = 20
    bottom_margin = 44
    bar_h = 6
    sub_gap = 2
    row_pad = 5
    row_h = row_pad * 2 + 3 * bar_h + 2 * sub_gap  # room for up to 3 stacked bars, always

    panels = [("func_existence", "function", "existence", "Function Existence"),
              ("class_existence", "class", "existence", "Class Existence"),
              ("args", "function", "args", "Args Exact-Match")]

    panels_x_start = left_margin + label_col_w
    width = panels_x_start + len(panels) * panel_w + (len(panels) - 1) * panel_gap + right_margin
    height = top_margin + header_h + n * row_h + bottom_margin
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
        f'<text class="scope-note" x="{left_margin}" y="52">No tool is ground truth -- each bar is that '
        + f"tool's own agreement rate vs. everything anyone found.</text>",
        f'<text class="scope-note" x="{left_margin}" y="64">Bar groups vary 1-3 by language\'s tool coverage '
        + f"-- order is always GitGalaxy, tree-sitter, ctags.</text>",
        f'<text class="scope-note" x="{left_margin}" y="76">GitGalaxy\'s bar is GRAY when beaten and '
        + f"unaudited, colored when tied or validated.</text>",
        f'<text class="scope-note" x="{left_margin}" y="88">See docs/self_scan/how_to_investigate_a_discrepancy.md '
        + f"for what an unaudited gap means.</text>",
    ]

    legend_y = 108
    lx = left_margin
    for tool in ALL_TOOLS:
        parts.append(f'<rect x="{lx}" y="{legend_y - 8}" width="14" height="8" rx="2" fill="{_COLOR_TOOL[tool]}"/>')
        parts.append(f'<text class="legend-label" x="{lx + 18}" y="{legend_y}">{_TOOL_LABEL[tool]}</text>')
        lx += 18 + 9 * len(_TOOL_LABEL[tool]) + 20
    parts.append(f'<rect x="{lx}" y="{legend_y - 8}" width="14" height="8" rx="2" fill="{_COLOR_GRAY}"/>')
    parts.append(f'<text class="legend-label" x="{lx + 18}" y="{legend_y}">GitGalaxy, unaudited gap</text>')

    for i, (_, _, _, title) in enumerate(panels):
        px = panels_x_start + i * (panel_w + panel_gap)
        parts.append(f'<text class="panel-title" x="{px + panel_w / 2}" y="{top_margin + header_h - 4}">{title}</text>')

    for row_i, lang in enumerate(langs):
        y = rows_top + row_i * row_h
        data = data_by_lang[lang]
        if row_i % 2 == 0:
            parts.append(f'<rect class="stripe" x="{left_margin}" y="{y}" width="{width - left_margin - right_margin}" height="{row_h}"/>')
        parts.append(f'<text class="lang-label" x="{left_margin + 4}" y="{y + row_h / 2 + 3.5}">{lang}</text>')

        if not data.corpus_available:
            parts.append(f'<text class="awaiting" x="{panels_x_start}" y="{y + row_h / 2 + 3.5}">awaiting language-crucible corpus</text>')
            continue

        for panel_i, (attr, symbol_type, metric, _) in enumerate(panels):
            px = panels_x_start + panel_i * (panel_w + panel_gap)
            scores: dict[str, MetricScore] = getattr(data, attr)
            bar_y = y + row_pad
            parts.append(f'<rect class="bar-track" x="{px}" y="{bar_y}" width="{bar_max_w}" height="{3 * bar_h + 2 * sub_gap}" rx="2"/>')
            for tool in data.available_tools:
                if tool not in scores:
                    continue
                score = scores[tool]
                if score.rate_pct is None:
                    continue
                w = max(2, bar_max_w * score.rate_pct / 100.0)
                color = _gg_bar_color(lang, symbol_type, metric) if tool == "gitgalaxy" else _COLOR_TOOL[tool]
                parts.append(f'<rect x="{px}" y="{bar_y}" width="{w:.1f}" height="{bar_h}" rx="2" fill="{color}"/>')
                parts.append(
                    f'<text class="value-label" x="{px + bar_max_w + 4}" y="{bar_y + bar_h - 0.5}">'
                    f"{score.matched_consensus}/{score.total_slots}</text>"
                )
                bar_y += bar_h + sub_gap

    footer_y = height - bottom_margin + 16
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

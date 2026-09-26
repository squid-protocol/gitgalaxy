#!/usr/bin/env python3
"""
graph_coverage_chart.py -- which languages' graphs are measured, how well, and on how much (#3796).

The counterpart of tri_comparison_chart.svg for the two graphs. One row per measured language,
three panels, and every language GitGalaxy parses but does not measure listed by name, so the
chart discloses coverage rather than implying it:

    Imports              import_graph_accuracy.py      vs each language's import statements
                                                       (tree-sitter / ast), resolved by the
                                                       language's own rule; pinned real repos
    Callee names         call_graph_accuracy.py        vs tree-sitter call nodes (Level 1: which
                                                       names a function calls); language-crucible
    Call resolution      call_graph_resolution.py      vs a compiler or analyser reference
                                                       (Level 2: which definition a call reaches)

It is a pure function of committed files -- the three baselines plus
docs/self_scan/graph_comparison_ledger.json -- so it needs no scan, and the history workflow
regenerates it after refreshing the ledger.

WHAT A CELL SAYS
    Imports and callee names show the VALIDATED numbers (graph_ledger.validated): a ledger
    verdict moves a disagreement; an unvalidated one counts as it does raw. A `*` means at
    least one shape behind the number has no verdict yet, so the number is not a claim
    (graph_comparison_README.md). Call resolution has no per-shape ledger: its numbers are
    "vs <tool> <version>", the reference's view, never ground truth.
    A panel whose n is below SMALL_N is drawn faded: too few to quote.

USAGE
    python tests/tools/graph_coverage_chart.py                 # markdown table to stdout
    python tests/tools/graph_coverage_chart.py --write         # docs/self_scan/graph_coverage_chart.svg
    python tests/tools/graph_coverage_chart.py --check         # fail if the committed SVG is stale
    python tests/tools/graph_coverage_chart.py --history PATH  # append this state to a history CSV
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Optional

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import graph_ledger as gl  # noqa: E402

CHART_PATH = REPO_ROOT / "docs" / "self_scan" / "graph_coverage_chart.svg"
HISTORY_PATH = REPO_ROOT / "docs" / "self_scan" / "graph_coverage_history.csv"
IMPORT_BASELINE = REPO_ROOT / "tests" / "import_graph_accuracy_baseline.json"
CALL_BASELINE = REPO_ROOT / "tests" / "call_graph_accuracy_baseline.json"
# A panel measured on fewer items than this is drawn faded: too few to quote.
SMALL_N = 100

PANELS = ("imports", "calls", "resolution")
PANEL_TITLE = {"imports": "Imports", "calls": "Callee names", "resolution": "Call resolution"}
PANEL_SUB = {
    "imports": "file -> file, vs import statements",
    "calls": "names called, vs tree-sitter",
    "resolution": "call -> definition, vs a compiler",
}


@dataclass
class Cell:
    precision: Optional[float]
    recall: Optional[float]
    n_precision: int  # what precision is out of (engine edges / calls / judged links)
    n_recall: int  # what recall is out of (import statements / calls / reference edges)
    open_shapes: int = 0
    open_precision: int = 0  # shapes without a verdict on the precision (GitGalaxy-only) side
    open_recall: int = 0  # ... and on the recall (reference-only) side
    raw_precision: Optional[float] = None
    raw_recall: Optional[float] = None
    reference: str = ""  # call resolution: "tsc 6.0.2"
    corpus: str = ""  # the repos, for the tooltip
    unit: str = ""  # what n counts: imports / calls / edges
    repos: int = 0
    files: int = 0
    functions: int = 0

    @property
    def detail(self) -> str:
        """The second line under n: where the number was measured."""
        if self.reference:
            return f"vs {self.reference}"
        if self.repos:
            return f"repos {self.repos} \u00b7 files {self.files:,}"
        return f"functions {self.functions:,}" if self.functions else ""

    @property
    def n(self) -> int:
        """What recall is out of: the reference's import statements, calls or edges."""
        return self.n_recall

    @property
    def small(self) -> bool:
        return self.n < SMALL_N


# Registry entries that are data or prose, with no dependency or call graph to measure.
NOT_CODE = frozenset({"csv", "json", "markdown", "pbtxt", "plaintext", "xml"})


def all_languages() -> list[str]:
    """The denominator: every language the engine's registry parses, bar pure data/prose formats.
    Read from the registry itself (not tri_comparison_chart's list, which needs tree-sitter), so the
    chart is the same on every machine."""
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    return sorted(set(LANGUAGE_DEFINITIONS) - NOT_CODE)


def _ledger_results(results: dict[str, dict[str, Any]], symbol_type: str, ledger_path: Path) -> dict[str, list[int]]:
    """Attach `top_causes` from the ledger's live shapes, so graph_ledger.validated can apply the
    verdicts without a re-run (the ledger holds each shape's last measured count). Returns the
    open shapes per language as [precision side, recall side]."""
    import tri_comparison_ledger as tl

    entries = tl.load_ledger(ledger_path).get("entries", {})
    open_by_side: dict[str, list[int]] = {lang: [0, 0] for lang in results}
    for e in entries.values():
        if e.get("symbol_type") != symbol_type or e.get("language") not in results or not e.get("still_reproduces"):
            continue
        fp = e.get("agreeing_tools") == ["gitgalaxy"]
        results[e["language"]].setdefault("top_causes", []).append(
            {
                "cause": ("fp:" if fp else "fn:") + e["metric"],
                "count": int(e.get("last_seen_count") or 0),
                "examples": [],
            }
        )
        if e.get("status") != "validated":
            open_by_side[e["language"]][0 if fp else 1] += 1
    return open_by_side


def _validated_cells(
    results: dict[str, dict[str, Any]],
    symbol_type: str,
    counts: tuple[str, str, str, str],
    ledger_path: Path,
    corpus_key: Optional[str] = None,
) -> dict[str, Cell]:
    open_by_side = _ledger_results(results, symbol_type, ledger_path)
    v = gl.validated(results, symbol_type, counts, ledger_path)
    out = {}
    for lang, r in results.items():
        x = v.get(lang, {})
        p_ok, p_bad, r_ok, r_bad = (int(r[k]) for k in counts)
        out[lang] = Cell(
            precision=x.get("precision_pct", r.get("precision_pct")),
            recall=x.get("recall_pct", r.get("recall_pct")),
            n_precision=p_ok + p_bad,
            n_recall=r_ok + r_bad,
            open_shapes=int(x.get("open_shapes") or 0),
            open_precision=open_by_side[lang][0],
            open_recall=open_by_side[lang][1],
            raw_precision=r.get("precision_pct"),
            raw_recall=r.get("recall_pct"),
            corpus=str(r.get(corpus_key, "")) if corpus_key else "",
        )
    return out


def import_cells(baseline: Path = IMPORT_BASELINE, ledger_path: Path = gl.LEDGER) -> dict[str, Cell]:
    results = json.loads(baseline.read_text())
    for r in results.values():  # the baseline stores totals and misses; the ledger maths wants hits
        r["correct"] = r["engine_edges"] - r["fp"]
        r["found"] = r["imports"] - r["fn"]
    cells = _validated_cells(results, "import", ("correct", "fp", "found", "fn"), ledger_path, "repos")
    for lang, c in cells.items():
        c.unit, c.files = "imports", int(results[lang].get("files") or 0)
        c.repos = len([r for r in str(results[lang].get("repos", "")).split(",") if r.strip()])
    return cells


def call_cells(baseline: Path = CALL_BASELINE, ledger_path: Path = gl.LEDGER) -> dict[str, Cell]:
    results = json.loads(baseline.read_text())
    cells = _validated_cells(results, "call", ("tp", "fp", "tp", "fn"), ledger_path)
    for lang, c in cells.items():
        c.unit, c.functions = "calls", int(results[lang].get("matched_functions") or 0)
    return cells


def resolution_cells(tests_dir: Path = REPO_ROOT / "tests") -> dict[str, Cell]:
    """One cell per registered reference with a committed baseline (python's file has no
    language suffix: it came first)."""
    from callgraph_refs import REFERENCES

    out = {}
    for lang, ref in sorted(REFERENCES.items()):
        name = (
            "call_graph_resolution_baseline.json" if lang == "python" else f"call_graph_resolution_{lang}_baseline.json"
        )
        path = tests_dir / name
        if not path.exists():
            continue
        b = json.loads(path.read_text())
        out[lang] = Cell(
            precision=b.get("confident_precision_pct"),
            recall=b.get("recall_pct"),
            n_precision=int(b.get("confident_judged") or 0),
            n_recall=int(b.get("pyan_edges") or 0),  # the reference's edge count, whatever the tool
            raw_precision=b.get("confident_precision_pct"),
            raw_recall=b.get("recall_pct"),
            reference=f"{ref.tool} {b.get('reference_version') or ref.version}",
            corpus=ref.corpus,
            unit="edges",
        )
    return out


def load(ledger_path: Path = gl.LEDGER) -> dict[str, dict[str, Cell]]:
    """{panel: {language: Cell}} from the committed baselines and ledger."""
    return {
        "imports": import_cells(ledger_path=ledger_path),
        "calls": call_cells(ledger_path=ledger_path),
        "resolution": resolution_cells(),
    }


# ----------------------------------------------------------------------------- rendering


def _pct(x: Optional[float]) -> str:
    return "-" if x is None else f"{x:.1f}%"


def _star(c: Cell, side: str) -> str:
    return "*" if (c.open_precision if side == "P" else c.open_recall) else ""


def render_markdown(data: dict[str, dict[str, Cell]], languages: list[str]) -> str:
    measured = [lang for lang in languages if any(lang in data[p] for p in PANELS)]
    head = "| language | " + " | ".join(PANEL_TITLE[p] + " P / R (n)" for p in PANELS) + " |"
    lines = [head, "|---" * (len(PANELS) + 1) + "|"]
    for lang in measured:
        row = [lang]
        for p in PANELS:
            c = data[p].get(lang)
            if not c:
                row.append("not measured")
                continue
            small = ", small n" if c.small else ""
            row.append(
                f"{_pct(c.precision)}{_star(c, 'P')} / {_pct(c.recall)}{_star(c, 'R')} "
                f"(n={c.n:,} {c.unit}; {c.detail}{small})"
            )
        lines.append("| " + " | ".join(row) + " |")
    rest = [lang for lang in languages if lang not in measured]
    lines.append(f"\nNot measured in any panel ({len(rest)} of {len(languages)}): {', '.join(rest)}.")
    lines.append(
        f"\n`*` = a disagreement shape behind this number has no verdict yet, so it is not a claim. "
        f"small n = fewer than {SMALL_N} items."
    )
    return "\n".join(lines)


# Precision and recall get their own pair, distinct from the tool colours of the charts above it
# (blue / orange / aqua): the dataviz palette's violet and yellow slots, validated as a pair
# (CVD dE 41). Yellow is under 3:1 on the surface, so every bar carries its value as text.
_COLOR = {"P": "#4a3aa7", "R": "#eda100"}
_SIDE_LABEL = {"P": "Precision", "R": "Recall"}
_SMALL_OPACITY = 0.35
_STYLE = """<style>
  .surface { fill: #fcfcfb; }
  .title { font-size: 15px; font-weight: 600; fill: #0b0b0b; }
  .subtitle { font-size: 11px; fill: #52514e; }
  .panel-title { font-size: 11px; font-weight: 600; fill: #0b0b0b; }
  .panel-sub { font-size: 9.5px; fill: #706f6a; }
  .lang { font-size: 12px; font-weight: 700; fill: #0b0b0b; }
  .pr { font-size: 9px; fill: #52514e; }
  .legend { font-size: 10px; fill: #0b0b0b; }
  .val { font-size: 9.5px; fill: #0b0b0b; }
  .n { font-size: 9px; fill: #706f6a; }
  .none { font-size: 9.5px; fill: #9a9a95; font-style: italic; }
  .note { font-size: 10px; fill: #52514e; }
  .stripe { fill: #f0efec; }
  .track { fill: #eeede9; }
</style>"""


def render_svg(data: dict[str, dict[str, Cell]], languages: list[str], stamp: str = "") -> str:
    measured = [lang for lang in languages if any(lang in data[p] for p in PANELS)]
    rest = [lang for lang in languages if lang not in measured]
    left, right, top = 16, 16, 106
    label_w, panel_w, row_h = 104, 306, 34
    track_x, track_w = 46, 110  # inside a panel: "Precision"/"Recall", then the 0-100% track
    n_x = track_x + track_w + 48  # then the value, then n and where it was measured
    width = left + label_w + panel_w * len(PANELS) + right

    # the unmeasured list, wrapped to the chart width
    words, wrapped, line = list(rest), [], ""
    for w in words:
        cand = f"{line}, {w}" if line else w
        if len(cand) * 5.6 > width - left - right and line:
            wrapped.append(line + ",")
            line = w
        else:
            line = cand
    if line:
        wrapped.append(line)
    body_h = row_h * len(measured)
    height = top + body_h + 28 + 16 * len(wrapped) + 62

    counts = {p: len(data[p]) for p in PANELS}
    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
        f'height="{height}" font-family="system-ui, -apple-system, Segoe UI, sans-serif">',
        _STYLE,
        f'<rect class="surface" x="0" y="0" width="{width}" height="{height}"/>',
        f'<text class="title" x="{left}" y="24">Graph accuracy coverage: imports and calls, per language</text>',
        f'<text class="subtitle" x="{left}" y="42">Measured: imports {counts["imports"]}, callee names '
        f"{counts['calls']}, call resolution {counts['resolution']} of {len(languages)} languages. "
        "Bars are GitGalaxy's score.</text>",
    ]
    lx = left
    for side in ("P", "R"):
        p.append(f'<rect x="{lx}" y="53" width="14" height="8" rx="2" fill="{_COLOR[side]}"/>')
        p.append(f'<text class="legend" x="{lx + 19}" y="61">{_SIDE_LABEL[side]}</text>')
        lx += 90
    p.append(
        f'<rect x="{lx}" y="53" width="14" height="8" rx="2" fill="{_COLOR["P"]}" opacity="{_SMALL_OPACITY}"/>'
        f'<text class="legend" x="{lx + 19}" y="61">faded: n below {SMALL_N}, too few to quote</text>'
    )
    for i, panel in enumerate(PANELS):
        x = left + label_w + i * panel_w
        p.append(f'<text class="panel-title" x="{x}" y="84">{PANEL_TITLE[panel]}</text>')
        p.append(f'<text class="panel-sub" x="{x}" y="97">{escape(PANEL_SUB[panel])}</text>')

    for r, lang in enumerate(measured):
        y = top + r * row_h
        if r % 2 == 0:
            p.append(f'<rect class="stripe" x="{left}" y="{y}" width="{width - left - right}" height="{row_h}"/>')
        p.append(f'<text class="lang" x="{left + 6}" y="{y + row_h / 2 + 4}">{escape(lang)}</text>')
        for i, panel in enumerate(PANELS):
            x = left + label_w + i * panel_w
            c = data[panel].get(lang)
            if not c:
                p.append(f'<text class="none" x="{x}" y="{y + row_h / 2 + 3}">not measured</text>')
                continue
            fade = f' opacity="{_SMALL_OPACITY}"' if c.small else ""
            tip = (
                f"{lang} {PANEL_TITLE[panel].lower()}: precision {_pct(c.precision)} of {c.n_precision:,}, "
                f"recall {_pct(c.recall)} of {c.n_recall:,}"
                + (
                    f" (raw {_pct(c.raw_precision)} / {_pct(c.raw_recall)}; {c.open_shapes} shapes without a verdict)"
                    if c.open_shapes
                    else ""
                )
                + (f"; vs {c.reference}" if c.reference else "")
                + (f"; corpus {c.corpus}" if c.corpus else "")
                + ("; small n" if c.small else "")
            )
            p.append(f"<g><title>{escape(tip)}</title>")
            for j, (side, val) in enumerate((("P", c.precision), ("R", c.recall))):
                by = y + 7 + j * 12
                p.append(f'<text class="pr" x="{x}" y="{by + 7.5}">{_SIDE_LABEL[side]}</text>')
                p.append(f'<rect class="track" x="{x + track_x}" y="{by}" width="{track_w}" height="8" rx="2"/>')
                if val is not None:
                    w = max(track_w * val / 100.0, 2.0)
                    p.append(
                        f'<rect x="{x + track_x}" y="{by}" width="{w:.1f}" height="8" rx="2" '
                        f'fill="{_COLOR[side]}"{fade}/>'
                    )
                p.append(
                    f'<text class="val" x="{x + track_x + track_w + 5}" y="{by + 8}">{_pct(val)}{_star(c, side)}</text>'
                )
            n_line = f"n={c.n:,} {c.unit}"  # small n is the fade, the legend and the tooltip
            p.append(f'<text class="n" x="{x + n_x}" y="{y + 15}">{escape(n_line)}</text>')
            if c.detail:
                p.append(f'<text class="n" x="{x + n_x}" y="{y + 27}">{escape(c.detail)}</text>')
            p.append("</g>")

    y = top + body_h + 24
    p.append(
        f'<text class="panel-title" x="{left}" y="{y}">Not measured in any panel ({len(rest)} of {len(languages)})</text>'
    )
    for k, text in enumerate(wrapped):
        p.append(f'<text class="none" x="{left}" y="{y + 16 + 16 * k}">{escape(text)}</text>')
    y += 16 * len(wrapped) + 28
    p.append(
        f'<text class="note" x="{left}" y="{y}">* a disagreement shape behind the number has no verdict yet '
        "(docs/self_scan/graph_comparison_ledger.json): not a claim. n counts what recall is out of "
        "(import statements, calls, reference edges).</text>"
    )
    p.append(
        f'<text class="note" x="{left}" y="{y + 15}">Call resolution is scored against the reference tool, '
        "not ground truth. Generated by tests/tools/graph_coverage_chart.py"
        + (f" at {escape(stamp)}" if stamp else "")
        + ".</text>"
    )
    p.append("</svg>")
    return "\n".join(p) + "\n"


# ----------------------------------------------------------------------------- history

HISTORY_FIELDS = (
    "timestamp_utc",
    "commit_sha",
    "panel",
    "language",
    "precision_pct",
    "recall_pct",
    "raw_precision_pct",
    "raw_recall_pct",
    "n_precision",
    "n_recall",
    "open_shapes",
    "reference",
)


def history_rows(data: dict[str, dict[str, Cell]], sha: str, when: str) -> list[dict[str, Any]]:
    return [
        {
            "timestamp_utc": when,
            "commit_sha": sha,
            "panel": panel,
            "language": lang,
            "precision_pct": c.precision,
            "recall_pct": c.recall,
            "raw_precision_pct": c.raw_precision,
            "raw_recall_pct": c.raw_recall,
            "n_precision": c.n_precision,
            "n_recall": c.n_recall,
            "open_shapes": c.open_shapes,
            "reference": c.reference,
        }
        for panel in PANELS
        for lang, c in sorted(data[panel].items())
    ]


_STATE_FIELDS = HISTORY_FIELDS[2:]  # everything but when and at which commit


def _last_snapshot(path: Path) -> list[tuple[str, ...]]:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return []
    last = rows[-1]["timestamp_utc"]
    return [tuple(r[k] for k in _STATE_FIELDS) for r in rows if r["timestamp_utc"] == last]


def append_history(path: Path, rows: list[dict[str, Any]]) -> bool:
    """Append a snapshot unless it measures exactly what the last one did, so a push that moved
    nothing leaves the file (and the history workflow's diff) untouched. Returns whether it wrote."""
    new = not path.exists()
    state = [tuple("" if r[k] is None else str(r[k]) for k in _STATE_FIELDS) for r in rows]
    if not new and _last_snapshot(path) == state:
        return False
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=HISTORY_FIELDS, lineterminator="\n")
        if new:
            w.writeheader()
        w.writerows(rows)
    return True


def _head_sha() -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help=f"write {CHART_PATH.relative_to(REPO_ROOT)}")
    ap.add_argument("--check", action="store_true", help="fail if the committed SVG differs from a fresh render")
    ap.add_argument("--history", metavar="PATH", help="append this state to a history CSV")
    ap.add_argument("--summary", metavar="PATH", help="append the markdown table here (e.g. $GITHUB_STEP_SUMMARY)")
    a = ap.parse_args(argv)

    data, languages = load(), all_languages()
    svg = render_svg(data, languages)
    table = render_markdown(data, languages)
    if a.summary:
        with open(a.summary, "a", encoding="utf-8") as fh:
            fh.write("## Graph accuracy coverage\n\n" + table + "\n")
    if a.history:
        when = os.environ.get("GRAPH_COVERAGE_TIMESTAMP") or dt.datetime.now(dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        wrote = append_history(Path(a.history), history_rows(data, _head_sha(), when))
        print(f"graph_coverage_chart: history {'appended' if wrote else 'unchanged'}")
    if a.check:
        current = CHART_PATH.read_text(encoding="utf-8") if CHART_PATH.exists() else ""
        if current != svg:
            print(
                f"graph_coverage_chart: {CHART_PATH.relative_to(REPO_ROOT)} is stale -- "
                "run `python tests/tools/graph_coverage_chart.py --write` and commit it"
            )
            return 1
        print("graph_coverage_chart: chart is current")
        return 0
    if a.write:
        CHART_PATH.write_text(svg, encoding="utf-8")
        print(f"graph_coverage_chart: wrote {CHART_PATH.relative_to(REPO_ROOT)}")
    if not (a.write or a.history or a.summary):
        print(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

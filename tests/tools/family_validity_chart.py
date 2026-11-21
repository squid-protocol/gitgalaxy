#!/usr/bin/env python3
"""
family_validity_chart.py -- how much of the keyword-family signals is checked, and how well (#8863).

The counterpart of tri_comparison_chart.svg (function finding) and graph_coverage_chart.svg (call graph) for the keyword families. Two figures
from one baseline, because one picture cannot honestly carry both "how much is checked" and "how well":

  docs/self_scan/family_validity_chart.svg    the README figure: a coverage bar, a table of every parser-measured cell with the score PRINTED in it,
                                              and the decoy-test result. Few numbers, readable at README width, no hover needed.
  docs/self_scan/family_validity_matrix.svg   the maintainer matrix: every language the engine parses against every family with a written contract
                                              (signal_contracts.py), 73 x 71 cells, with hover tooltips. The detail behind the summary.

WHAT THE NUMBERS ARE
    Parser-measured cell: the family's count in each function against a parser's reading of the same functions (family_oracle.py, family_oracle_ts.py).
    Recall = of the functions where the parser sees the construct, the share where the family fired. Precision = of the functions where the family fired,
    the share where the parser sees the construct. The cell shows the LOWER of the two, in per cent, and a letter says which: R (it misses constructs) or
    P (it fires where there is none). A one-sided cell (the family never fires, or the parser never sees the construct) counts as 0.
    The parser's reading is our interpretation of the family's written contract: a measured agreement on one corpus, not ground truth.

    Decoy test (no parser): the family's keyword planted in a comment and in a string literal, in each language's own syntax, only where the bare keyword
    fires as code (a positive control). Comments should be ignored (they are); strings are counted by design (#2535), which conflicts with the contracts.

    Score bins are fixed here, before the data is read again, and are not tuned to it: under 50%, 50-79%, 80-89%, 90-97%, 98-100%.

USAGE
    python tests/tools/family_validity_chart.py                 # markdown summary to stdout
    python tests/tools/family_validity_chart.py --write         # both SVGs
    python tests/tools/family_validity_chart.py --check         # fail if a committed SVG is stale
    python tests/tools/family_validity_chart.py --history PATH  # append per-language rows to a history CSV
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import shutil
import statistics
import subprocess
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

BASELINE = REPO_ROOT / "tests" / "family_validity_baseline.json"
CHART_PATH = REPO_ROOT / "docs" / "self_scan" / "family_validity_chart.svg"
MATRIX_PATH = REPO_ROOT / "docs" / "self_scan" / "family_validity_matrix.svg"
NOT_CODE = frozenset(
    {"csv", "json", "markdown", "pbtxt", "plaintext", "xml"}
)  # data or prose: no keyword families to measure
SMALL_N = 10  # fewer oracle functions than this: a cell is too thin to quote

# Score bins, fixed in advance: (upper edge, fill). One blue hue, dark to bright on the dark surface; the only accent colour is the red that flags failure.
BIN_EDGES = (0.50, 0.80, 0.90, 0.98)
BIN_FILLS = ("#3b1d1d", "#1f3b5c", "#2f6aa8", "#4f9be8", "#a9d1ff")
BIN_LABELS = ("under 50%", "50-79%", "80-89%", "90-97%", "98-100%")
FAIL = "#e5534b"
NEUTRAL = "#8b949e"
TRACK = "#30363d"
PARSER_BLUE = "#4f9be8"

CELL, GAP = 11, 1
PITCH = CELL + GAP
MATRIX_COLOR = {"na": "#12141a", "untested": "#3b3f4a", "decoy": "#566074", "empty": "#4d5260"}


@dataclass(frozen=True)
class Family:
    key: str
    phase: str
    status: str  # the contract's own status: stated / declared / draft


def engine_grid() -> tuple[list[Family], list[str], dict[str, set[str]]]:
    """(families by phase, languages, {language: families it has a rule for}) read from the engine's own registry."""
    from gitgalaxy.standards import signal_contracts as sc
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    families = [Family(k, c.phase, c.status) for ph in sc.PHASE_ORDER for k, c in sc.CONTRACTS.items() if c.phase == ph]
    languages = sorted(set(LANGUAGE_DEFINITIONS) - NOT_CODE)
    defined: dict[str, set[str]] = {}
    for lang in languages:
        rules = LANGUAGE_DEFINITIONS[lang].get("rules", {}) or {}
        defined[lang] = {k for k, v in rules.items() if v is not None and getattr(v, "pattern", "x") != ""}
    return families, languages, defined


def load_baseline(path: Path = BASELINE) -> dict[str, dict[str, dict]]:
    return json.loads(path.read_text(encoding="utf-8")).get("cells", {}) if path.exists() else {}


def load_decoys(path: Path = BASELINE) -> dict[str, dict[str, dict]]:
    """{language: {family: {comment: pass|leak, string_counts: bool|None, keyword, corpus}}} from the baseline's `decoys` section."""
    return json.loads(path.read_text(encoding="utf-8")).get("decoys", {}) if path.exists() else {}


def cell_score(cell: dict) -> float | None:
    """The lower of recall and precision; None when the oracle saw nothing to score. A family that never fires where the oracle sees the
    construct scores 0, and one that fires where the oracle sees nothing scores 0."""
    if cell["status"] == "no-instances":
        return None
    r, p = cell.get("recall"), cell.get("precision")
    if r is None and p is None:
        return None
    return min(r, p) if r is not None and p is not None else 0.0


def cell_side(cell: dict) -> str:
    """Which side is the weaker: R (recall: it misses constructs) or P (precision: it fires where there is none)."""
    r, p = cell.get("recall"), cell.get("precision")
    if r is None:
        return "P"
    if p is None:
        return "R"
    return "R" if r < p else "P"


def score_bin(score: float) -> int:
    """0..4 into BIN_FILLS: under 50%, 50-79%, 80-89%, 90-97%, 98-100%."""
    return sum(score >= edge for edge in BIN_EDGES)


def cell_state(
    lang: str, rule: str, defined: dict[str, set[str]], cells: dict, decoys: dict | None = None
) -> tuple[str, dict | None]:
    """("scored", cell) / ("empty", cell) / ("decoy", None) / ("untested", None) / ("na", None): a decoy-only cell has no parser result but a decoy test."""
    cell = cells.get(lang, {}).get(rule)
    if cell is not None:
        return ("empty" if cell_score(cell) is None else "scored"), cell
    if rule in (decoys or {}).get(lang, {}):
        return "decoy", None
    return ("untested" if rule in defined.get(lang, set()) else "na"), None


def summary(
    families: list[Family], languages: list[str], defined: dict[str, set[str]], cells: dict, decoys: dict | None = None
) -> dict:
    decoys = decoys or {}
    counts = {"scored": 0, "empty": 0, "untested": 0, "na": 0, "decoy": 0}
    scored_langs: set[str] = set()
    scored_fams: set[str] = set()
    empty_with_decoy = 0
    for lang in languages:
        for fam in families:
            state = cell_state(lang, fam.key, defined, cells, decoys)[0]
            counts[state] += 1
            if state == "scored":
                scored_langs.add(lang)
                scored_fams.add(fam.key)
            elif state == "empty" and fam.key in decoys.get(lang, {}):
                empty_with_decoy += 1  # parser saw nothing to score, but the decoy test did run there
    decoy_only = counts["decoy"] + empty_with_decoy
    defined_n = counts["scored"] + counts["empty"] + counts["untested"] + counts["decoy"]
    return {
        **counts,
        "defined": defined_n,
        "decoy_only": decoy_only,
        "tested": counts["scored"] + decoy_only,
        "untested_any": defined_n - counts["scored"] - decoy_only,
        "languages": len(languages),
        "families": len(families),
        "scored_languages": len(scored_langs),
        "scored_families": len(scored_fams),
    }


def decoy_totals(decoys: dict) -> dict:
    cells = [d for fams in decoys.values() for d in fams.values()]
    strings = [d for d in cells if d["string_counts"] is not None]
    return {
        "comment_total": len(cells),
        "comment_ignored": sum(d["comment"] == "pass" for d in cells),
        "string_total": len(strings),
        "string_counted": sum(bool(d["string_counts"]) for d in strings),
    }


def _order(
    languages: list[str], families: list[Family], defined: dict[str, set[str]], cells: dict, decoys: dict | None = None
) -> list[str]:
    """Parser-scored languages first (most scored cells first), then the rest alphabetically."""
    n = {
        lang: sum(cell_state(lang, f.key, defined, cells, decoys)[0] == "scored" for f in families)
        for lang in languages
    }
    return sorted(languages, key=lambda lang: (-n[lang], lang))


_STYLE = """<style>
  .surface { fill: #0f1117; }  /* house style: dark, matching the other charts */
  .title { font-size: 16px; font-weight: 600; fill: #f0efec; }
  .subtitle { font-size: 12px; fill: #c3c2b7; }
  .h { font-size: 12px; font-weight: 700; fill: #f0efec; }
  .legend { font-size: 10.5px; fill: #f0efec; }
  .lang { font-size: 11px; font-weight: 600; fill: #f0efec; }
  .fam { font-size: 10.5px; fill: #c3c2b7; }
  .num { font-size: 11px; font-weight: 700; fill: #f0efec; text-anchor: middle; }
  .numd { font-size: 11px; font-weight: 700; fill: #0f1117; text-anchor: middle; }
  .thin { font-size: 11px; font-style: italic; fill: #8b949e; text-anchor: middle; }
  .side { font-size: 7px; font-weight: 700; fill: #c9d1d9; opacity: 0.85; }
  .sided { font-size: 7px; font-weight: 700; fill: #0f1117; opacity: 0.8; }
  .dim { font-size: 11px; fill: #56606f; text-anchor: middle; }
  .note { font-size: 10px; fill: #c3c2b7; }
  .big { font-size: 11px; font-weight: 600; fill: #f0efec; }
  .phase { font-size: 10px; font-weight: 700; fill: #f0efec; }
  .lang9 { font-size: 9px; fill: #c3c2b7; }
  .u { fill: #3b3f4a; }
</style>"""


def _svg_open(width: int, height: int) -> list[str]:
    return [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            'font-family="system-ui, -apple-system, Segoe UI, sans-serif">'
        ),
        _STYLE,
        f'<rect class="surface" x="0" y="0" width="{width}" height="{height}"/>',
    ]


def _fmt_int(n: int) -> str:
    return f"{n:,}"


def render_summary_svg(
    families: list[Family], languages: list[str], defined: dict[str, set[str]], cells: dict, decoys: dict | None = None
) -> str:
    """The README figure: coverage bar, the table of parser-measured cells with scores printed in them, and the decoy-test bars."""
    decoys = decoys or {}
    s = summary(families, languages, defined, cells, decoys)
    dt_ = decoy_totals(decoys)
    langs = [
        lang
        for lang in _order(languages, families, defined, cells)
        if any(cell_state(lang, f.key, defined, cells)[0] == "scored" for f in families)
    ]
    rows = []
    for fam in families:
        got = {lang: cell_state(lang, fam.key, defined, cells, decoys) for lang in langs}
        scored = {lang: c for lang, (st, c) in got.items() if st == "scored" and c is not None}
        if scored:
            med = statistics.median(cell_score(c) or 0.0 for c in scored.values())
            rows.append((med, fam, got))
    rows.sort(key=lambda r: (r[0], r[1].key))  # worst first: the reader sees the problems first

    left, label_w, cw, ch, cgap = 16, 188, 60, 18, 2
    gx = left + label_w
    table_w = len(langs) * (cw + cgap)
    right_x = gx + table_w + 40
    width = max(right_x + 340, 1060)
    top_a = 150
    height = top_a + (ch + cgap) * len(rows) + 130
    p = _svg_open(width, height)
    p.append(f'<text class="title" x="{left}" y="24">Keyword families: how much is checked, and how well</text>')
    p.append(
        f'<text class="subtitle" x="{left}" y="43">{_fmt_int(s["defined"])} language-by-family rules are defined. {s["scored"]} are measured against a parser '
        f"({s['scored_languages']} languages), {_fmt_int(s['decoy_only'])} more only by a decoy test, {_fmt_int(s['untested_any'])} not tested yet.</text>"
    )
    # coverage bar
    bar_x, bar_y, bar_w, bar_h = left, 56, width - left * 2, 16
    parts = (
        (s["scored"], PARSER_BLUE, "measured against a parser"),
        (s["decoy_only"], NEUTRAL, "decoy test only"),
        (s["untested_any"], TRACK, "not tested yet"),
    )
    total = max(sum(n for n, _, _ in parts), 1)
    x = float(bar_x)
    lx = bar_x
    for n, color, label in parts:
        w = bar_w * n / total
        p.append(f'<rect x="{x:.1f}" y="{bar_y}" width="{w:.1f}" height="{bar_h}" fill="{color}"/>')
        x += w
        p.append(f'<rect x="{lx}" y="{bar_y + 24}" width="9" height="9" fill="{color}"/>')
        text = f"{_fmt_int(n)} {label}"
        p.append(f'<text class="legend" x="{lx + 14}" y="{bar_y + 32}">{escape(text)}</text>')
        lx += 22 + int(len(text) * 5.6)
    # panel A: parser table
    p.append(
        f'<text class="h" x="{left}" y="{top_a - 34}">Measured against a parser: the lower of recall and precision, in %</text>'
    )
    for i, lang in enumerate(langs):
        cx = gx + i * (cw + cgap) + cw / 2
        p.append(f'<text class="lang" x="{cx:.0f}" y="{top_a - 8}" text-anchor="middle">{escape(lang)}</text>')
    y = top_a
    for _med, fam, got in rows:
        label = fam.key + (" (draft)" if fam.status == "draft" else "")
        p.append(f'<text class="fam" x="{left}" y="{y + 13}">{escape(label)}</text>')
        for i, lang in enumerate(langs):
            x0 = gx + i * (cw + cgap)
            state, cell = got[lang]
            if state == "scored" and cell is not None:
                sc_ = cell_score(cell) or 0.0
                pct = round(sc_ * 100)
                if cell["n_oracle"] < SMALL_N:
                    p.append(
                        f'<rect x="{x0}" y="{y}" width="{cw}" height="{ch}" fill="none" stroke="{NEUTRAL}" stroke-width="1" stroke-dasharray="3 2"/>'
                    )
                    p.append(f'<text class="thin" x="{x0 + cw / 2}" y="{y + 13}">{pct}</text>')
                    continue
                b = score_bin(sc_)
                stroke = f' stroke="{FAIL}" stroke-width="1.6"' if b == 0 else ""
                p.append(f'<rect x="{x0}" y="{y}" width="{cw}" height="{ch}" fill="{BIN_FILLS[b]}"{stroke}/>')
                bright = b == 4
                dagger = "" if cell["pinned"] else "†"
                p.append(
                    f'<text class="{"numd" if bright else "num"}" x="{x0 + cw / 2}" y="{y + 13}">{pct}{dagger}</text>'
                )
                p.append(
                    f'<text class="{"sided" if bright else "side"}" x="{x0 + 3}" y="{y + 8}">{cell_side(cell)}</text>'
                )
            elif state == "empty":
                p.append(f'<text class="dim" x="{x0 + cw / 2}" y="{y + 13}">\N{EN DASH}</text>')
            elif state in ("untested", "decoy"):
                p.append(f'<text class="dim" x="{x0 + cw / 2}" y="{y + 13}">·</text>')
        y += ch + cgap
    ya = y + 12
    p.append(
        f'<text class="note" x="{left}" y="{ya}">R = the family misses constructs the parser sees; P = it fires where the parser sees none. † corpus not pinned (exploratory).</text>'
    )
    p.append(
        f'<text class="note" x="{left}" y="{ya + 14}">Dashed grey italic: under {SMALL_N} functions. · not tested yet. \N{EN DASH} tested, the construct never occurs. Rows worst first. Draft = the contract is a draft.</text>'
    )
    kx = float(left)
    for i, label in enumerate(BIN_LABELS):
        stroke = f' stroke="{FAIL}" stroke-width="1.4"' if i == 0 else ""
        p.append(f'<rect x="{kx:.0f}" y="{ya + 24}" width="12" height="9" fill="{BIN_FILLS[i]}"{stroke}/>')
        p.append(f'<text class="legend" x="{kx + 16:.0f}" y="{ya + 32}">{label}</text>')
        kx += 28 + len(label) * 5.6
    # panel B: decoy test
    bx, bw = right_x, width - right_x - left
    p.append(f'<text class="h" x="{bx}" y="{top_a - 34}">Decoy test (no parser needed)</text>')
    p.append(
        f'<text class="note" x="{bx}" y="{top_a - 20}">Each family keyword planted in a comment and in a string</text>'
    )
    p.append(f'<text class="note" x="{bx}" y="{top_a - 7}">literal, in {len(decoys)} languages.</text>')
    by = top_a + 4
    for label, n, tot, accent in (
        ("In a comment: ignored", dt_["comment_ignored"], dt_["comment_total"], False),
        ("In a string literal: counted", dt_["string_counted"], dt_["string_total"], True),
    ):
        p.append(f'<text class="big" x="{bx}" y="{by + 10}">{label}</text>')
        w = bw * (n / tot if tot else 0)
        p.append(f'<rect x="{bx}" y="{by + 18}" width="{bw}" height="14" fill="{TRACK}"/>')
        p.append(f'<rect x="{bx}" y="{by + 18}" width="{w:.1f}" height="14" fill="{FAIL if accent else NEUTRAL}"/>')
        p.append(f'<text class="legend" x="{bx}" y="{by + 46}">{_fmt_int(n)} of {_fmt_int(tot)} cells</text>')
        by += 70
    notes = (
        "Comments are stripped before any family is counted, as designed.",
        "Strings are not: a keyword inside a string counts like code. That is",
        "documented behaviour (issue #2535), but it conflicts with the families'",
        "written contracts, so it is a decision for the maintainers, not a fix.",
    )
    for i, line in enumerate(notes):
        p.append(f'<text class="note" x="{bx}" y="{by + 4 + i * 13}">{escape(line)}</text>')
    by += 70
    for i, line in enumerate(
        (
            "One repository per language; the parser's reading is our interpretation",
            "of each family's contract, not ground truth. Cells are measurements on",
            "one corpus, not proof a family is right everywhere.",
            "Full 73 x 71 matrix: docs/self_scan/family_validity_matrix.svg",
        )
    ):
        p.append(f'<text class="note" x="{bx}" y="{by + i * 13}">{escape(line)}</text>')
    p.append("</svg>")
    return "\n".join(p) + "\n"


def _decoy_tip(lang: str, rule: str, dec: dict) -> str:
    strings = {True: "counts", False: "does not count", None: "not tested"}[dec["string_counts"]]
    comment = "ignored (pass)" if dec["comment"] == "pass" else "LEAKS"
    return f"{lang} / {rule}: decoy test with '{dec['keyword']}': in a comment {comment}; in a string literal {strings}; no parser result yet"


def render_matrix_svg(
    families: list[Family], languages: list[str], defined: dict[str, set[str]], cells: dict, decoys: dict | None = None
) -> str:
    """The maintainer matrix: every language against every contracted family, with tooltips."""
    decoys = decoys or {}
    order = _order(languages, families, defined, cells)
    s = summary(families, languages, defined, cells, decoys)
    left, label_w, top = 16, 176, 172
    grid_x = left + label_w
    rows: list[tuple[str, Family | str]] = []
    last = None
    for f0 in families:
        if f0.phase != last:
            rows.append(("phase", f0.phase))
            last = f0.phase
        rows.append(("fam", f0))
    width = grid_x + PITCH * len(order) + 16
    height = top + PITCH * len(rows) + 84
    p = _svg_open(width, height)
    p.insert(
        2,
        f'<defs><rect id="c" width="{CELL}" height="{CELL}"/><pattern id="hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
        '<line x1="0" y1="0" x2="0" y2="4" stroke="#0f1117" stroke-width="1.4"/></pattern></defs>',
    )
    p.append(
        f'<text class="title" x="{left}" y="24">Keyword-family matrix (maintainers): every language against every family</text>'
    )
    p.append(
        f'<text class="subtitle" x="{left}" y="42">{_fmt_int(s["defined"])} cells have a rule: {s["scored"]} measured against a parser, {_fmt_int(s["decoy_only"])} decoy test only, '
        f"{_fmt_int(s['untested_any'])} not tested; {_fmt_int(s['na'])} cells are N/A. Hover a cell for numbers. The README figure is the summary of this.</text>"
    )
    lx, ly = left, 56
    for i, fill in enumerate(BIN_FILLS):
        stroke = f' stroke="{FAIL}" stroke-width="1.2"' if i == 0 else ""
        p.append(f'<rect x="{lx + i * 70}" y="{ly}" width="12" height="10" fill="{fill}"{stroke}/>')
        p.append(f'<text class="legend" x="{lx + i * 70 + 16}" y="{ly + 9}">{BIN_LABELS[i]}</text>')
    sx = float(lx + 5 * 70 + 10)
    for color, label in (
        (MATRIX_COLOR["decoy"], "decoy test only"),
        (MATRIX_COLOR["untested"], "not tested yet"),
        (MATRIX_COLOR["empty"], "tested, construct never seen"),
        (MATRIX_COLOR["na"], "N/A: no rule"),
    ):
        p.append(
            f'<rect x="{sx:.0f}" y="{ly}" width="{CELL}" height="{CELL}" fill="{color}" stroke="#4a4f5c" stroke-width="0.6"/>'
        )
        p.append(f'<text class="legend" x="{sx + 16:.0f}" y="{ly + 9}">{label}</text>')
        sx += 30 + len(label) * 5.6
    p.append(
        f'<text class="legend" x="{lx}" y="{ly + 26}">Cell colour = the lower of recall and precision. Faded: under {SMALL_N} functions. Hatched: corpus not pinned (exploratory).</text>'
    )
    for i, lang in enumerate(order):
        cx = grid_x + i * PITCH + CELL / 2
        p.append(f'<text class="lang9" transform="translate({cx:.1f},{top - 6}) rotate(-90)">{escape(lang)}</text>')
    p.append(
        f'<rect x="{grid_x - 1}" y="{top - 1}" width="{PITCH * len(order) + 1}" height="{PITCH * len(rows) + 1}" fill="{MATRIX_COLOR["na"]}" stroke="#2a2d36" stroke-width="1"/>'
    )
    y = top
    for kind, item in rows:
        if kind == "phase":
            p.append(f'<text class="phase" x="{left}" y="{y + 9}">{escape(str(item)).upper()}</text>')
            y += PITCH
            continue
        fam = item if isinstance(item, Family) else None
        if fam is None:
            continue
        p.append(
            f'<text class="fam" x="{left + 8}" y="{y + 9}">{escape(fam.key)}{" (draft)" if fam.status == "draft" else ""}</text>'
        )
        for i, lang in enumerate(order):
            state, cell = cell_state(lang, fam.key, defined, cells, decoys)
            x = grid_x + i * PITCH
            if state == "na":
                continue
            if state == "untested":
                p.append(f'<use href="#c" x="{x}" y="{y}" class="u"/>')
            elif state == "decoy":
                tip = _decoy_tip(lang, fam.key, decoys[lang][fam.key])
                p.append(
                    f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="{MATRIX_COLOR["decoy"]}"><title>{escape(tip)}</title></rect>'
                )
            elif cell is not None:
                where = f"{cell['corpus']}{'' if cell['pinned'] else ' (not pinned)'}"
                if state == "empty":
                    tip = f"{lang} / {fam.key}: scored, but the oracle sees no instance in {where}"
                    p.append(
                        f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="{MATRIX_COLOR["empty"]}"><title>{escape(tip)}</title></rect>'
                    )
                else:
                    sc_ = cell_score(cell) or 0.0
                    b = score_bin(sc_)
                    fade = ' opacity="0.5"' if cell["n_oracle"] < SMALL_N else ""
                    stroke = f' stroke="{FAIL}" stroke-width="1.2"' if b == 0 else ""
                    r = "-" if cell["recall"] is None else f"{cell['recall']:.2f}"
                    pr = "-" if cell["precision"] is None else f"{cell['precision']:.2f}"
                    tip = f"{lang} / {fam.key}: recall {r}, precision {pr} ({cell['n_oracle']} oracle, {cell['n_family']} family functions; {where})"
                    p.append(
                        f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="{BIN_FILLS[b]}"{fade}{stroke}><title>{escape(tip)}</title></rect>'
                    )
                    if not cell["pinned"]:
                        p.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="url(#hatch)"/>')
        y += PITCH
    ny = y + 18
    p.append(
        f'<text class="note" x="{left}" y="{ny}">A cell is agreement with the oracle\'s reading of the family\'s contract on one corpus, not proof the family is right everywhere. '
        "Oracles: Python ast and tree-sitter (tests/tools/family_oracle.py).</text>"
    )
    p.append(
        f'<text class="note" x="{left}" y="{ny + 14}">Languages without a tree-sitter grammar (COBOL, JCL, assembler, ...) need another oracle. (draft) = the family\'s contract is a draft.</text>'
    )
    p.append("</svg>")
    return "\n".join(p) + "\n"


def render_markdown(
    families: list[Family], languages: list[str], defined: dict[str, set[str]], cells: dict, decoys: dict | None = None
) -> str:
    s = summary(families, languages, defined, cells, decoys)
    out = [
        (
            f"Keyword-family validity: {_fmt_int(s['defined'])} defined cells; {s['scored']} measured against a parser "
            f"({s['scored_languages']} of {s['languages']} languages, {s['scored_families']} of {s['families']} families), {s['decoy_only']} more by a decoy test only, "
            f"{_fmt_int(s['untested_any'])} not tested; {_fmt_int(s['na'])} N/A."
        ),
        "",
        "| language | scored | weakest family (recall / precision) |",
        "|---|---:|---|",
    ]
    for lang in _order(languages, families, defined, cells):
        scored = [
            (cell_score(c), f.key, c)
            for f in families
            for st, c in [cell_state(lang, f.key, defined, cells)]
            if st == "scored" and c is not None
        ]
        if not scored:
            continue
        low = min(scored, key=lambda t: (t[0] or 0.0, t[1]))
        out.append(f"| {lang} | {len(scored)} | {low[1]} ({low[2]['recall']} / {low[2]['precision']}) |")
    if decoys:
        d = decoy_totals(decoys)
        out += [
            "",
            (
                f"Decoy test: a keyword in a comment is ignored in {d['comment_ignored']} of {d['comment_total']} cells; "
                f"a keyword in a string literal is counted in {d['string_counted']} of {d['string_total']}."
            ),
        ]
    return "\n".join(out)


def history_rows(
    families: list[Family], languages: list[str], defined: dict[str, set[str]], cells: dict, sha: str, when: str
) -> list[dict]:
    rows = []
    for lang in languages:
        vals = [
            v
            for f in families
            for st, c in [cell_state(lang, f.key, defined, cells)]
            if st == "scored" and c is not None
            for v in [cell_score(c)]
            if v is not None
        ]
        rows.append(
            {
                "when": when,
                "sha": sha,
                "language": lang,
                "defined": sum(cell_state(lang, f.key, defined, cells)[0] != "na" for f in families),
                "scored": len(vals),
                "mean_weaker_side": round(sum(vals) / len(vals), 3) if vals else "",
            }
        )
    return rows


def _last_snapshot(path: Path) -> list[tuple[str, ...]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        data = list(csv.DictReader(fh))
    if not data:
        return []
    last = data[-1]["when"]
    return sorted((r["language"], r["defined"], r["scored"], r["mean_weaker_side"]) for r in data if r["when"] == last)


def append_history(path: Path, rows: list[dict]) -> bool:
    """Append one snapshot, unless it is identical to the last (so a no-change run adds no rows)."""
    fresh = sorted((r["language"], str(r["defined"]), str(r["scored"]), str(r["mean_weaker_side"])) for r in rows)
    if _last_snapshot(path) == fresh:
        return False
    new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        if new:
            w.writeheader()
        w.writerows(rows)
    return True


def _head_sha() -> str:
    git = shutil.which("git")
    if git is None:
        return ""
    try:
        return subprocess.run(  # noqa: S603  (git resolved by shutil.which, fixed arguments)
            [git, "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--write",
        action="store_true",
        help=f"write {CHART_PATH.relative_to(REPO_ROOT)} and {MATRIX_PATH.relative_to(REPO_ROOT)}",
    )
    ap.add_argument("--check", action="store_true", help="fail if a committed SVG differs from a fresh render")
    ap.add_argument("--history", metavar="PATH", help="append per-language rows to a history CSV")
    ap.add_argument(
        "--baseline", default=str(BASELINE), help="the baseline JSON (default tests/family_validity_baseline.json)"
    )
    a = ap.parse_args(argv)

    families, languages, defined = engine_grid()
    cells = load_baseline(Path(a.baseline))
    decoys = load_decoys(Path(a.baseline))
    outputs = {
        CHART_PATH: render_summary_svg(families, languages, defined, cells, decoys),
        MATRIX_PATH: render_matrix_svg(families, languages, defined, cells, decoys),
    }
    if a.history:
        when = os.environ.get("FAMILY_VALIDITY_TIMESTAMP") or dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        wrote = append_history(Path(a.history), history_rows(families, languages, defined, cells, _head_sha(), when))
        print(f"family_validity_chart: history {'appended' if wrote else 'unchanged'}")
    if a.check:
        stale = [
            path for path, svg in outputs.items() if (path.read_text(encoding="utf-8") if path.exists() else "") != svg
        ]
        for path in stale:
            print(
                f"family_validity_chart: {path.relative_to(REPO_ROOT)} is stale -- "
                "run `python tests/tools/family_validity_chart.py --write` and commit it"
            )
        if stale:
            return 1
        print("family_validity_chart: charts are current")
        return 0
    if a.write:
        for path, svg in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(svg, encoding="utf-8")
            print(f"family_validity_chart: wrote {path.relative_to(REPO_ROOT)}")
    if not (a.write or a.history):
        print(render_markdown(families, languages, defined, cells, decoys))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

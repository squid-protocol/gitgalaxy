#!/usr/bin/env python3
"""
family_validity_chart.py -- which keyword families are measured, in which language, and how well (#8863).

The counterpart of tri_comparison_chart.svg (function finding) and graph_coverage_chart.svg (call graph) for
the keyword families. One column per language the engine parses, one row per family that has a written
contract (gitgalaxy/standards/signal_contracts.py), grouped by the contract's phase. A cell says one of:

    black      N/A       the language defines no rule for the family (nothing to measure)
    gray       untested  the language has a rule; no oracle has scored it yet
    dotted     empty     scored, but the oracle never sees the construct in the corpus, so nothing can be said
    rainbow    scored    the WEAKER of recall and precision against a parser's reading of the same functions:
                         red 0%, orange 50%, green 80%, cyan 90%, blue 100%

A cell drawn faded has fewer than SMALL_N oracle functions behind it (too few to quote); a cell with diagonal
hatching comes from a corpus that is not a pinned crucible release, so it is exploratory and not reproducible.

It is a pure function of committed files: tests/family_validity_baseline.json (written by
`tests/tools/family_oracle.py --update-baseline`) and the engine's own registry, so it needs no scan.

WHAT A CELL IS AND IS NOT
    Recall is the share of functions where a parser sees the construct and the family fired; precision is the
    share of functions where the family fired and the parser sees the construct. The parser's reading is the
    family's CONTRACT as the oracle interprets it (family_oracle.py, family_oracle_ts.py): a cell is a measured
    agreement with that reading on one corpus, not proof the family is right everywhere. Taking the weaker side
    keeps a family that finds everything but also fires on strings (recall 1.00, precision 0.03) from looking good.

USAGE
    python tests/tools/family_validity_chart.py                 # markdown summary to stdout
    python tests/tools/family_validity_chart.py --write         # docs/self_scan/family_validity_chart.svg
    python tests/tools/family_validity_chart.py --check         # fail if the committed SVG is stale
    python tests/tools/family_validity_chart.py --history PATH  # append per-language rows to a history CSV
"""

from __future__ import annotations

import argparse
import colorsys
import csv
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

BASELINE = REPO_ROOT / "tests" / "family_validity_baseline.json"
CHART_PATH = REPO_ROOT / "docs" / "self_scan" / "family_validity_chart.svg"
NOT_CODE = frozenset(
    {"csv", "json", "markdown", "pbtxt", "plaintext", "xml"}
)  # data or prose: no keyword families to measure
SMALL_N = 10  # fewer oracle functions than this: the cell is drawn faded

CELL, GAP = 11, 1
PITCH = CELL + GAP
STATE_COLOR = {"na": "#12141a", "untested": "#3b3f4a", "empty": "#4d5260"}


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


def cell_score(cell: dict) -> float | None:
    """The weaker of recall and precision; None when the oracle saw nothing to score. A family that never fires where the oracle sees the
    construct scores 0, and one that fires where the oracle sees nothing scores 0."""
    if cell["status"] == "no-instances":
        return None
    r, p = cell.get("recall"), cell.get("precision")
    if r is None and p is None:
        return None
    return min(x for x in (r, p) if x is not None) if r is not None and p is not None else 0.0


def lut(score: float) -> str:
    """Rainbow lookup table, red (0) through orange, green, cyan to blue (1). Scores cluster near 1, so the hue is stretched at the top:
    0.5 is orange, 0.8 green, 0.9 cyan, 0.95 light blue."""
    s = max(0.0, min(1.0, score))
    hue = (240 * s**3) / 360
    r, g, b = colorsys.hsv_to_rgb(hue, 0.82, 0.95)
    return f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"


def cell_state(lang: str, rule: str, defined: dict[str, set[str]], cells: dict) -> tuple[str, dict | None]:
    """("scored", cell) / ("empty", cell) / ("untested", None) / ("na", None)."""
    cell = cells.get(lang, {}).get(rule)
    if cell is not None:
        return ("empty" if cell_score(cell) is None else "scored"), cell
    return ("untested" if rule in defined.get(lang, set()) else "na"), None


def summary(families: list[Family], languages: list[str], defined: dict[str, set[str]], cells: dict) -> dict:
    counts = {"scored": 0, "empty": 0, "untested": 0, "na": 0}
    for lang in languages:
        for fam in families:
            counts[cell_state(lang, fam.key, defined, cells)[0]] += 1
    scored_langs = {
        lang for lang in languages for fam in families if cell_state(lang, fam.key, defined, cells)[0] == "scored"
    }
    scored_fams = {
        fam.key for lang in languages for fam in families if cell_state(lang, fam.key, defined, cells)[0] == "scored"
    }
    return {
        **counts,
        "defined": counts["scored"] + counts["empty"] + counts["untested"],
        "languages": len(languages),
        "families": len(families),
        "scored_languages": len(scored_langs),
        "scored_families": len(scored_fams),
    }


def _order(languages: list[str], families: list[Family], defined: dict[str, set[str]], cells: dict) -> list[str]:
    """Scored languages first (most scored cells first), then the rest alphabetically."""
    n = {lang: sum(cell_state(lang, f.key, defined, cells)[0] == "scored" for f in families) for lang in languages}
    return sorted(languages, key=lambda lang: (-n[lang], lang))


_STYLE = """<style>
  .surface { fill: #0f1117; }  /* house style: dark, matching the other charts */
  .u { fill: #3b3f4a; }
  .title { font-size: 15px; font-weight: 600; fill: #f0efec; }
  .subtitle { font-size: 11px; fill: #c3c2b7; }
  .legend { font-size: 10px; fill: #f0efec; }
  .phase { font-size: 10px; font-weight: 700; fill: #f0efec; }
  .fam { font-size: 9px; fill: #c3c2b7; }
  .famd { font-size: 9px; fill: #77766f; font-style: italic; }
  .lang { font-size: 9px; fill: #c3c2b7; }
  .note { font-size: 10px; fill: #c3c2b7; }
</style>"""


def render_svg(families: list[Family], languages: list[str], defined: dict[str, set[str]], cells: dict) -> str:
    order = _order(languages, families, defined, cells)
    s = summary(families, languages, defined, cells)
    left, label_w, top = 16, 176, 150
    grid_x = left + label_w
    # rows: a header line per phase, then its families
    rows: list[tuple[str, Family | str]] = []
    last = None
    for f0 in families:
        if f0.phase != last:
            rows.append(("phase", f0.phase))
            last = f0.phase
        rows.append(("fam", f0))
    row_h = PITCH
    width = grid_x + PITCH * len(order) + 16
    height = top + row_h * len(rows) + 84
    p = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            'font-family="system-ui, -apple-system, Segoe UI, sans-serif">'
        ),
        _STYLE,
        (
            f'<defs><rect id="c" width="{CELL}" height="{CELL}"/>'
            '<pattern id="hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            '<line x1="0" y1="0" x2="0" y2="4" stroke="#0f1117" stroke-width="1.4"/></pattern>'
            '<pattern id="dots" width="4" height="4" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="0.7" fill="#8f8e86"/></pattern></defs>'
        ),
        f'<rect class="surface" x="0" y="0" width="{width}" height="{height}"/>',
        f'<text class="title" x="{left}" y="24">Keyword families: measured agreement with a parser, per language</text>',
        (
            f'<text class="subtitle" x="{left}" y="42">{s["scored"]} of {s["defined"]} defined cells scored '
            f"({s['scored_languages']} of {s['languages']} languages, {s['scored_families']} of {s['families']} families); "
            f"{s['na']} cells are N/A (no rule in that language). Colour is the weaker of recall and precision.</text>"
        ),
    ]
    # legend
    lx, ly = left, 54
    p.extend(f'<rect x="{lx + i * 5}" y="{ly}" width="5" height="9" fill="{lut(i / 40)}"/>' for i in range(41))
    for frac, txt in ((0, "0%"), (0.5, "50%"), (0.8, "80%"), (1, "100%")):
        p.append(f'<text class="legend" x="{lx + frac * 200:.0f}" y="{ly + 21}" text-anchor="middle">{txt}</text>')
    sx = float(lx + 250)
    for color, label, extra in (
        (STATE_COLOR["untested"], "not yet tested", ""),
        (STATE_COLOR["empty"], "scored, construct never seen", "dots"),
        (STATE_COLOR["na"], "N/A: no rule", ""),
    ):
        p.append(
            f'<rect x="{sx}" y="{ly}" width="{CELL}" height="{CELL}" fill="{color}" stroke="#2a2d36" stroke-width="0.5"/>'
        )
        if extra:
            p.append(f'<rect x="{sx}" y="{ly}" width="{CELL}" height="{CELL}" fill="url(#dots)"/>')
        p.append(f'<text class="legend" x="{sx + 16}" y="{ly + 9}">{label}</text>')
        sx += 22 + len(label) * 5.4
    p.append(f'<rect x="{sx}" y="{ly}" width="{CELL}" height="{CELL}" fill="{lut(0.9)}" opacity="0.5"/>')
    p.append(f'<text class="legend" x="{sx + 16}" y="{ly + 9}">faded: fewer than {SMALL_N} functions</text>')
    sx += 40 + 30 * 5.4
    p.append(f'<rect x="{sx}" y="{ly}" width="{CELL}" height="{CELL}" fill="{lut(0.9)}"/>')
    p.append(f'<rect x="{sx}" y="{ly}" width="{CELL}" height="{CELL}" fill="url(#hatch)"/>')
    p.append(f'<text class="legend" x="{sx + 16}" y="{ly + 9}">hatched: unpinned corpus (exploratory)</text>')
    gh = row_h * len(rows)
    p.append(f'<rect x="{grid_x}" y="{top}" width="{PITCH * len(order)}" height="{gh}" fill="{STATE_COLOR["na"]}"/>')
    # column labels, rotated
    for i, lang in enumerate(order):
        cx = grid_x + i * PITCH + CELL / 2
        p.append(f'<text class="lang" transform="translate({cx:.1f},{top - 6}) rotate(-90)">{escape(lang)}</text>')
    # rows
    y = top
    for kind, item in rows:
        if kind == "phase":
            p.append(f'<text class="phase" x="{left}" y="{y + 9}">{escape(str(item)).upper()}</text>')
            y += row_h
            continue
        fam = item if isinstance(item, Family) else None
        if fam is None:
            continue
        cls = "famd" if fam.status == "draft" else "fam"
        p.append(f'<text class="{cls}" x="{left + 8}" y="{y + 9}">{escape(fam.key)}</text>')
        for i, lang in enumerate(order):
            state, cell = cell_state(lang, fam.key, defined, cells)
            x = grid_x + i * PITCH
            if state == "na":
                continue  # the grid background is the N/A colour: 2,000+ cells need no element
            if state == "untested":
                p.append(f'<use href="#c" x="{x}" y="{y}" class="u"/>')
                continue
            if cell is None:
                continue
            where = f"{cell['corpus']}{'' if cell['pinned'] else ' (not pinned)'}"
            if state == "empty":
                tip = f"{lang} / {fam.key}: scored, but the oracle sees no instance in {where}"
                p.append(
                    f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="{STATE_COLOR["empty"]}"><title>{escape(tip)}</title></rect>'
                )
                p.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="url(#dots)"/>')
                continue
            sc_ = cell_score(cell)
            if sc_ is None:
                continue
            fade = ' opacity="0.5"' if cell["n_oracle"] < SMALL_N else ""
            r = "-" if cell["recall"] is None else f"{cell['recall']:.2f}"
            pr = "-" if cell["precision"] is None else f"{cell['precision']:.2f}"
            tip = f"{lang} / {fam.key}: recall {r}, precision {pr} ({cell['n_oracle']} oracle, {cell['n_family']} family functions; {where})"
            p.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="{lut(sc_)}"{fade}><title>{escape(tip)}</title></rect>'
            )
            if not cell["pinned"]:
                p.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="url(#hatch)"/>')
        y += row_h
    ny = y + 18
    p.append(
        f'<text class="note" x="{left}" y="{ny}">Hover a cell for recall, precision, the number of functions and the corpus. A cell is agreement with the '
        "oracle's reading of the family's contract on one corpus, not proof the family is right everywhere.</text>"
    )
    p.append(
        f'<text class="note" x="{left}" y="{ny + 16}">Oracles: Python ast and tree-sitter (tests/tools/family_oracle.py, family_oracle_ts.py). '
        "Families in italics have a draft contract. Languages without a tree-sitter grammar (COBOL, JCL, assembler, ...) need another oracle.</text>"
    )
    p.append("</svg>")
    return "\n".join(p) + "\n"


def render_markdown(families: list[Family], languages: list[str], defined: dict[str, set[str]], cells: dict) -> str:
    s = summary(families, languages, defined, cells)
    out = [
        (
            f"Keyword-family validity grid: {s['scored']} of {s['defined']} defined cells scored "
            f"({s['scored_languages']} of {s['languages']} languages, {s['scored_families']} of {s['families']} families); "
            f"{s['untested']} untested, {s['empty']} scored with no instance, {s['na']} N/A."
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
        low = min(scored, key=lambda t: (t[0], t[1]))
        out.append(f"| {lang} | {len(scored)} | {low[1]} ({low[2]['recall']} / {low[2]['precision']}) |")
    return "\n".join(out)


def history_rows(
    families: list[Family], languages: list[str], defined: dict[str, set[str]], cells: dict, sha: str, when: str
) -> list[dict]:
    rows = []
    for lang in languages:
        sc_ = [
            cell_score(c)
            for f in families
            for st, c in [cell_state(lang, f.key, defined, cells)]
            if st == "scored" and c is not None
        ]
        vals = [x for x in sc_ if x is not None]
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
    ap.add_argument("--write", action="store_true", help=f"write {CHART_PATH.relative_to(REPO_ROOT)}")
    ap.add_argument("--check", action="store_true", help="fail if the committed SVG differs from a fresh render")
    ap.add_argument("--history", metavar="PATH", help="append per-language rows to a history CSV")
    ap.add_argument(
        "--baseline", default=str(BASELINE), help="the baseline JSON (default tests/family_validity_baseline.json)"
    )
    a = ap.parse_args(argv)

    families, languages, defined = engine_grid()
    cells = load_baseline(Path(a.baseline))
    svg = render_svg(families, languages, defined, cells)
    if a.history:
        when = os.environ.get("FAMILY_VALIDITY_TIMESTAMP") or dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        wrote = append_history(Path(a.history), history_rows(families, languages, defined, cells, _head_sha(), when))
        print(f"family_validity_chart: history {'appended' if wrote else 'unchanged'}")
    if a.check:
        current = CHART_PATH.read_text(encoding="utf-8") if CHART_PATH.exists() else ""
        if current != svg:
            print(
                f"family_validity_chart: {CHART_PATH.relative_to(REPO_ROOT)} is stale -- "
                "run `python tests/tools/family_validity_chart.py --write` and commit it"
            )
            return 1
        print("family_validity_chart: chart is current")
        return 0
    if a.write:
        CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
        CHART_PATH.write_text(svg, encoding="utf-8")
        print(f"family_validity_chart: wrote {CHART_PATH.relative_to(REPO_ROOT)}")
    if not (a.write or a.history):
        print(render_markdown(families, languages, defined, cells))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

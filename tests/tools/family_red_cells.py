#!/usr/bin/env python3
"""Rank the red cells of the keyword-family validity grid and print the work as ready-to-paste epic lines (#8863).

    python tests/tools/family_red_cells.py                       # every language: red cells, worst first
    python tests/tools/family_red_cells.py --lang go             # one language, with the contract sentence for each cell
    python tests/tools/family_red_cells.py --slices              # one `- [ ]` line per language, for the #8863 checklist
    python tests/tools/family_red_cells.py --json                # machine readable

A cell is RED when the weaker of recall and precision is under the bar (0.8, the oracle's own bar) on at least 10 oracle
functions. Thin cells (under 10 functions) are never red: they are untested, not wrong. Hatched cells (a corpus that is not a
pinned crucible) are listed but marked, because their number cannot be quoted.

The tool only reads `tests/family_validity_baseline.json` and the contracts; it measures nothing. Refresh the baseline first
(`python tests/tools/family_oracle_sweep.py --write`, see .claude/skills/family-validity-remeasure), or the list is last
sweep's. What each direction means:
  misses      recall under the bar: the family misses what the oracle sees. Candidate missing keywords, or an oracle that reads
              the contract too broadly (Go `time.After`, C `close`): CHECK THE CONTRACT FIRST.
  over-counts precision under the bar: the family fires where the oracle sees nothing. Trace what the rule matches (method
              declarations as closures, `||` closures as booleans, bare words as io) before touching a list.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
BASELINE = REPO / "tests" / "family_validity_baseline.json"
BAR = 0.8
MIN_FUNCTIONS = 10
SKILL = ".claude/skills/family-validity-fix/SKILL.md"


def _weakest(cell: dict) -> float | None:
    vals = [v for v in (cell.get("recall"), cell.get("precision")) if v is not None]
    return min(vals) if vals else None


def direction(cell: dict) -> str:
    low_r = cell.get("recall") is not None and cell["recall"] < BAR
    low_p = cell.get("precision") is not None and cell["precision"] < BAR
    if low_r and low_p:
        return "both"
    return "misses" if low_r else "over-counts"


def red_cells(baseline: dict, bar: float = BAR, min_functions: int = MIN_FUNCTIONS) -> list[dict]:
    """Every red cell, worst first: [{lang, family, recall, precision, weakest, direction, pinned, n_family, n_oracle, corpus}]."""
    out = []
    for lang, fams in baseline.get("cells", {}).items():
        for fam, cell in fams.items():
            weakest = _weakest(cell)
            if weakest is None or weakest >= bar or cell.get("functions", 0) < min_functions:
                continue
            out.append(
                {
                    "lang": lang,
                    "family": fam,
                    "recall": cell.get("recall"),
                    "precision": cell.get("precision"),
                    "weakest": weakest,
                    "direction": direction(cell),
                    "pinned": bool(cell.get("pinned")),
                    "n_family": cell.get("n_family"),
                    "n_oracle": cell.get("n_oracle"),
                    "corpus": cell.get("corpus", ""),
                }
            )
    return sorted(out, key=lambda c: (c["weakest"], c["lang"], c["family"]))


def by_language(cells: list[dict]) -> dict[str, list[dict]]:
    langs: dict[str, list[dict]] = {}
    for c in cells:
        langs.setdefault(c["lang"], []).append(c)
    return dict(sorted(langs.items(), key=lambda kv: (-len(kv[1]), kv[0])))


def _fmt(v: float | None) -> str:
    return "-" if v is None else f"{v:.2f}"


def cell_text(c: dict) -> str:
    return f"{c['family']} {_fmt(c['recall'])}/{_fmt(c['precision'])}"


def slice_line(lang: str, cells: list[dict]) -> str:
    """One launchable checklist line for the epic: a language, its red cells, the skill, and a finish line a worker can check."""
    listing = ", ".join(cell_text(c) for c in cells)
    return (
        f"- [ ] **{lang}**: {len(cells)} red cell{'s' if len(cells) != 1 else ''} (recall/precision: {listing}). "
        f"Follow `{SKILL}`. Done when every cell is 0.8 or better on the pinned crucible, or the contract is silent and a "
        f"question is filed; one PR for this language only."
    )


def contract_sentence(family: str) -> str:
    try:
        from gitgalaxy.standards.signal_contracts import CONTRACTS
    except Exception:  # the tool still ranks without the engine importable
        return ""
    row = CONTRACTS.get(family)
    return row.contract if row else ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--lang", help="only this language, with each cell's contract sentence")
    ap.add_argument("--slices", action="store_true", help="print one `- [ ]` epic line per language")
    ap.add_argument("--json", action="store_true", help="machine-readable list")
    ap.add_argument("--baseline", default=str(BASELINE))
    args = ap.parse_args(argv)
    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    cells = red_cells(baseline)
    if args.lang:
        cells = [c for c in cells if c["lang"] == args.lang]
    if args.json:
        print(json.dumps(cells, indent=2))
        return 0
    langs = by_language(cells)
    if args.slices:
        for lang, cs in langs.items():
            print(slice_line(lang, cs))
        return 0
    print(
        f"{len(cells)} red cells in {len(langs)} languages (weaker of recall and precision under {BAR}, at least {MIN_FUNCTIONS} oracle functions)"
    )
    for lang, cs in langs.items():
        print(f"\n{lang}: {len(cs)}")
        for c in cs:
            hatch = "" if c["pinned"] else "  [hatched: not a pinned crucible]"
            print(
                f"  {c['family']:24s} recall {_fmt(c['recall'])}  precision {_fmt(c['precision'])}  "
                f"({c['n_family']} fire vs {c['n_oracle']} oracle)  {c['direction']}{hatch}"
            )
            if args.lang:
                print(f"      contract: {contract_sentence(c['family'])[:220]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
tri_comparison_report.py

Renders docs/self_scan/tri_comparison_ledger.json as a human-scannable Markdown report --
docs/self_scan/tri_comparison_points_of_interest.md -- so debugging a real GitGalaxy defect (or
a tree-sitter/ctags one) starts with "open this file and read down it," not "query a JSON blob."

The ledger is the source of truth (merge-safe, what the chart's gray/colored logic reads); this
report is a pure, stateless rendering of it -- regenerate anytime with `--write`, no re-running
the (slow) gather+reconcile pipeline needed, and this script never itself writes to the ledger.

RANKING: WHY 2-vs-1 BEFORE A 3-WAY SPLIT
    Existence disagreements are always a 2-vs-1 split when all three tools are available for a
    language -- "found" is binary per tool, so three tools can't produce a genuine three-way
    split on whether a symbol exists at all. Args values aren't binary (a real int), so args CAN
    3-way split (three tools, three different counts, no majority). A 2-vs-1 split isolates
    exactly one tool as the outlier against two that independently agree -- the strongest, most
    actionable signal this tool produces (it's what surfaced the real bevy_ecs_table.rs::
    initialize() GitGalaxy args-undercount during development). A 3-way split has no majority to
    lean on and is inherently a weaker starting point for guessing who's right, so it's ranked
    below every 2-vs-1 entry, not omitted -- still worth a look, just not first.
    Within each tier, unvalidated entries sort before validated ones (validated is a closed
    question, unvalidated is the open one this report exists to surface), then by occurrence
    count descending (a pattern repeating hundreds of times is worth checking before one that
    only showed up once).

COLUMN ORDER
    Every reading table renders gitgalaxy / tree_sitter / ctags in that fixed left-to-right
    order, regardless of which tool(s) are in the agreeing vs. dissenting set for a given row --
    same "order preserved" rule the chart itself follows.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tri_comparison_ledger import LEDGER_PATH, load_ledger

REPORT_PATH = LEDGER_PATH.parent / "tri_comparison_points_of_interest.md"

_TOOL_ORDER = ("gitgalaxy", "tree_sitter", "ctags")
_TOOL_LABEL = {"gitgalaxy": "GitGalaxy", "tree_sitter": "tree-sitter", "ctags": "ctags"}


def _shape_rank(entry: dict) -> tuple:
    is_two_vs_one = min(len(entry["agreeing_tools"]), len(entry["dissenting_tools"])) == 1
    return (
        0 if is_two_vs_one else 1,
        0 if entry["status"] != "validated" else 1,
        -entry["last_seen_count"],
    )


def _format_reading(value) -> str:
    if value is None:
        return "*(n/a)*"
    return str(value)


def _render_entry(key: str, entry: dict) -> str:
    # Ledger entries store agreeing_tools/dissenting_tools alphabetically-sorted (an implementation
    # detail of JSON persistence, see tri_comparison_ledger.py). Re-sort by the fixed _TOOL_ORDER
    # here so the prose matches the table columns below -- same "order preserved" rule throughout.
    agree = ", ".join(_TOOL_LABEL[t] for t in _TOOL_ORDER if t in entry["agreeing_tools"]) or "none"
    dissent = ", ".join(_TOOL_LABEL[t] for t in _TOOL_ORDER if t in entry["dissenting_tools"]) or "none"
    status_glyph = "✅" if entry["status"] == "validated" else "❓"
    shape_kind = "2-vs-1" if min(len(entry["agreeing_tools"]), len(entry["dissenting_tools"])) == 1 else "3-way split"

    lines = [
        f"### {status_glyph} `{entry['language']}` {entry['symbol_type']} {entry['metric']}: "
        f"{agree} agree, {dissent} differ",
        "",
        f"*{shape_kind} -- {entry['last_seen_count']} occurrence"
        f"{'s' if entry['last_seen_count'] != 1 else ''} as of {entry['last_reconciled_at']}"
        f"{'' if entry['still_reproduces'] else ' (no longer reproduces on the most recent run)'}*",
        "",
    ]

    if entry["status"] == "validated":
        lines += [
            f"**Verdict** (by {entry['investigated_by']}, {entry['investigated_at']}):",
            f"> {entry['verdict']}",
            "",
        ]
    else:
        lines += [
            "**Not yet investigated.** See `docs/self_scan/how_to_investigate_a_discrepancy.md` "
            "for the process -- read the source at a few examples below, then hand-edit this "
            "entry (`" + key + "`) in `tri_comparison_ledger.json`.",
            "",
        ]

    lines.append("| file | name | " + " | ".join(_TOOL_LABEL[t] for t in _TOOL_ORDER) + " |")
    lines.append("|---" * (2 + len(_TOOL_ORDER)) + "|")
    for ex in entry["last_seen_examples"]:
        readings = ex["readings"]
        row = [ex["file_path"], f"`{ex['name']}`"]
        row += [_format_reading(readings.get(t)) for t in _TOOL_ORDER]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    return "\n".join(lines)


def generate_report(ledger_path: Path = LEDGER_PATH) -> str:
    ledger = load_ledger(ledger_path)
    entries = ledger.get("entries", {})

    header = [
        "# Tri-Comparison Points of Interest",
        "",
        "Generated from `tri_comparison_ledger.json` by `tests/tools/tri_comparison_report.py "
        + "--write` -- do not hand-edit this file, edit the ledger and regenerate. See "
        + "`docs/self_scan/how_to_investigate_a_discrepancy.md` for what ❓ entries are asking for.",
        "",
        "Sorted 2-vs-1 splits before 3-way splits, unvalidated before validated, biggest "
        + "occurrence count first within each tier -- see this script's own module docstring for "
        + "why that order.",
        "",
    ]

    reproducing = {k: e for k, e in entries.items() if e["still_reproduces"]}
    by_lang: dict[str, list[tuple[str, dict]]] = {}
    for key, entry in reproducing.items():
        by_lang.setdefault(entry["language"], []).append((key, entry))

    if not by_lang:
        header.append("*No discrepancies currently on record.*")
        return "\n".join(header) + "\n"

    body = []
    for lang in sorted(by_lang):
        body.append(f"## {lang}")
        body.append("")
        ranked = sorted(by_lang[lang], key=lambda kv: _shape_rank(kv[1]))
        for key, entry in ranked:
            body.append(_render_entry(key, entry))

    return "\n".join(header + body)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write", action="store_true", help=f"Write to {REPORT_PATH} instead of stdout."
    )
    args = parser.parse_args()

    report = generate_report()
    if args.write:
        REPORT_PATH.write_text(report)
        print(f"tri_comparison_report: wrote {REPORT_PATH}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

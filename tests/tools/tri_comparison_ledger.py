#!/usr/bin/env python3
"""
tri_comparison_ledger.py

Persists tri_comparison_reconcile.py's DiscrepancyGroups across runs, tracks which ones a human
has actually investigated (and what they found), and answers the one question the chart needs:
for this (language, symbol_type, metric), is there any unvalidated discrepancy at all right now
-- regardless of which tool(s) are on which side of it?

WHY A LEDGER AT ALL, AND WHY PER-SHAPE NOT PER-INSTANCE
    See tri_comparison_reconcile.py's own module docstring for why discrepancies are grouped by
    SHAPE (language/symbol_type/metric/which-tools-agreed) rather than logged per individual
    occurrence -- csharp alone has 271 individual occurrences behind ONE shape
    (agree[ctags,gitgalaxy]_vs[tree_sitter]), almost certainly one systematic tree-sitter C#
    recall gap, not 271 separate findings. The ledger persists one entry per shape, not per
    occurrence, so a human's investigation of a handful of examples produces one verdict that
    covers everything matching that shape -- both what's been seen already and whatever new
    occurrences of the same shape turn up on a later run.

FILE
    docs/self_scan/tri_comparison_ledger.json -- committed, hand-editable (it's small, one entry
    per discrepancy SHAPE, not per instance -- expect low tens of entries per language at most,
    not thousands), reviewed like any other source file in a PR. Never regenerated from scratch;
    always MERGED (see merge_and_save below) so a validated verdict survives a fresh reconcile
    run untouched.

ENTRY LIFECYCLE
    1. reconcile_symbols() finds a discrepancy shape that doesn't exist in the ledger yet ->
       merge_and_save() adds it with status="unvalidated", verdict=None.
    2. A human (see docs/self_scan/how_to_investigate_a_discrepancy.md for the actual process)
       reads the source at a handful of the recorded examples, determines what's actually true,
       and hand-edits the entry: status="validated", verdict=<free text explaining what was
       found and which tool(s) were right>, investigated_by, investigated_at.
    3. Every later merge_and_save() call updates last_seen_count/last_seen_examples/
       last_seen_at for that shape (the raw numbers can drift as the corpus or engines change)
       but NEVER touches status/verdict/investigated_by/investigated_at once a human has set
       them -- re-running the tri-comparison tool must never silently revert a validated entry
       back to looking unvalidated, and must never let fresh examples quietly overwrite the
       ones a human actually read.
    4. If a previously-seen shape doesn't reproduce on a fresh run (the underlying cause got
       fixed, or corpus content moved), its entry is kept, not deleted -- `still_reproduces` is
       set to false and `last_reconciled_at` still updates. Keeping a historical record of what
       used to disagree and was resolved is worth more than silently losing it; an entry that
       stops reproducing is also, trivially, no longer capable of blocking a chart badge (see
       has_open_question below), so keeping it costs nothing at read time.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Type-hint only -- importing this eagerly would drag in tri_comparison_gatherer's
    # tree_sitter_accuracy_audit/tree_sitter_language_pack dependency chain just to read a JSON
    # file, which tri_comparison_report.py (this module's only other caller besides the tool
    # itself) has no other reason to need. `from __future__ import annotations` above already
    # makes every annotation in this file a lazy string, so this import never has to run.
    from tri_comparison_reconcile import DiscrepancyGroup

LEDGER_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "self_scan" / "tri_comparison_ledger.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_ledger(path: Path = LEDGER_PATH) -> dict:
    if not path.exists():
        return {"entries": {}}
    return json.loads(path.read_text())


def save_ledger(ledger: dict, path: Path = LEDGER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")


def merge_and_save(language: str, groups: list[DiscrepancyGroup], path: Path = LEDGER_PATH) -> dict:
    """Merges a fresh reconcile_symbols() run's discrepancy groups for one language into the
    persistent ledger, preserving any existing validation. Sets `language` on each group first
    (reconcile_symbols itself doesn't know its own language -- the caller does)."""
    ledger = load_ledger(path)
    entries = ledger.setdefault("entries", {})
    now = _now()

    seen_keys_this_run = set()
    for g in groups:
        g.language = language
        key = g.shape_key
        seen_keys_this_run.add(key)
        examples = [{"file_path": ex.file_path, "name": ex.name, "readings": ex.readings} for ex in g.examples]
        if key in entries:
            entry = entries[key]
            entry["last_seen_count"] = g.total_occurrences
            entry["last_seen_examples"] = examples
            entry["last_reconciled_at"] = now
            entry["still_reproduces"] = True
        else:
            entries[key] = {
                "language": language,
                "symbol_type": g.symbol_type,
                "metric": g.metric,
                "agreeing_tools": sorted(g.agreeing_tools),
                "dissenting_tools": sorted(g.dissenting_tools),
                "status": "unvalidated",
                "verdict": None,
                "investigated_by": None,
                "investigated_at": None,
                "first_seen_at": now,
                "last_reconciled_at": now,
                "still_reproduces": True,
                "last_seen_count": g.total_occurrences,
                "last_seen_examples": examples,
            }

    # Shapes that existed for this language before this run but didn't reproduce now -- keep the
    # record, mark it stale, never delete (see module docstring, lifecycle step 4).
    for key, entry in entries.items():
        if entry["language"] == language and key not in seen_keys_this_run:
            entry["still_reproduces"] = False
            entry["last_reconciled_at"] = now

    save_ledger(ledger, path)
    return ledger


def has_open_question(language: str, symbol_type: str, metric: str, path: Path = LEDGER_PATH) -> bool:
    """The one question the chart actually needs answered: is there ANY currently-reproducing,
    unvalidated discrepancy for this (language, symbol_type, metric) triple -- regardless of
    which tool(s) are on which side? Symmetric across all three tools on purpose (an earlier,
    GitGalaxy-only version of this check -- `is_language_metric_clean`, only ever asterisked
    GitGalaxy's own label and only gated GitGalaxy's own recall/precision failure shapes)
    drives two chart behaviors:
      - EVERY tool's value label in a disputed cell gets a `*`, not just GitGalaxy's -- the
        question is "has anyone actually verified this", not "did GitGalaxy specifically lose".
      - No winner badge is drawn on a disputed cell at all, for any panel. A badge implies "we
        know who's actually right"; that's only true once a human (or a dispatched agent
        standing in for one -- see docs/self_scan/how_to_investigate_a_discrepancy.md) has read
        real source and recorded a verdict. A raw percentage comparison alone isn't enough to
        earn one -- confirmed necessary by a real case the strictly-highest-rate_pct rule
        produced on its own: a 2-sample cell at 100% (2/2) outranking an 80-sample cell at
        98.75% (79/80), an artifact of sample size nobody had verified, not evidence either
        tool is more correct there.
    """
    ledger = load_ledger(path)
    return any(
        entry["language"] == language
        and entry["symbol_type"] == symbol_type
        and entry["metric"] == metric
        and entry["still_reproduces"]
        and entry["status"] != "validated"
        for entry in ledger.get("entries", {}).values()
    )

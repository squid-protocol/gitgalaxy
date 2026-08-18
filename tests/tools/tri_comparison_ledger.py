#!/usr/bin/env python3
"""
tri_comparison_ledger.py

Persists tri_comparison_reconcile.py's DiscrepancyGroups across runs, tracks which ones a human
has actually investigated (and what they found), and answers the one question the chart needs:
for this (language, symbol_type, metric), is there any unvalidated discrepancy touching
GitGalaxy's reading right now?

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
       stops reproducing is also, trivially, no longer capable of graying out a chart bar (see
       is_language_metric_clean below), so keeping it costs nothing at read time.
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


def merge_and_save(
    language: str, groups: list[DiscrepancyGroup], path: Path = LEDGER_PATH
) -> dict:
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
        examples = [
            {"file_path": ex.file_path, "name": ex.name, "readings": ex.readings} for ex in g.examples
        ]
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


def is_language_metric_clean(
    language: str, symbol_type: str, metric: str, path: Path = LEDGER_PATH, aspect: str = "recall"
) -> bool:
    """The one question the chart actually needs answered: does GitGalaxy's value label for this
    (language, symbol_type, metric) get a `*` (an unaudited loss) or not? True means either no
    discrepancy currently reproduces here, or every one that does has a validated verdict.

    `aspect` matters because recall and precision fail in OPPOSITE shapes, and checking the wrong
    one silently misses real cases -- confirmed on rust: GitGalaxy's func precision (92.1%,
    genuinely beaten by both tree-sitter and ctags at 100%) rendered with no `*` at all under the
    recall-only check this function used to be, because GitGalaxy was never in `dissenting_tools`
    for the shape actually causing that gap.
      - "recall" (default; also correct for the "args" metric, whose discrepancy groups are
        already majority/minority-shaped, not agree/disagree-shaped): GitGalaxy MISSED something
        real -- flagged when GitGalaxy is in `dissenting_tools` (recall's actual failure mode).
      - "precision": GitGalaxy is the LONE, uncorroborated claimant of something -- flagged only
        when GitGalaxy is in `agreeing_tools` AND is the ONLY tool in that set (present but
        nobody else backs it up). A shape like csharp's agree[ctags,gitgalaxy]_vs[tree_sitter]
        does NOT flag precision -- ctags corroborates GitGalaxy there, precision is fine; only
        agree[gitgalaxy]_vs[...] (GitGalaxy truly alone) does.
    """
    ledger = load_ledger(path)
    for entry in ledger.get("entries", {}).values():
        if not (
            entry["language"] == language
            and entry["symbol_type"] == symbol_type
            and entry["metric"] == metric
            and entry["still_reproduces"]
            and entry["status"] != "validated"
        ):
            continue
        if aspect == "precision":
            flagged = entry["agreeing_tools"] == ["gitgalaxy"]
        else:
            flagged = "gitgalaxy" in entry["dissenting_tools"]
        if flagged:
            return False
    return True

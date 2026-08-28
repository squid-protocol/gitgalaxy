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
       found and which tool(s) were right>, investigated_by, investigated_at, and (2026-08-20,
       see VERIFIED ADJUSTMENTS below) credit_tools/debit_tools if the verdict cleanly resolves
       to one or more tools confirmed correct or confirmed wrong on this shape.
    3. Every later merge_and_save() call updates last_seen_count/last_seen_examples/
       last_seen_at for that shape (the raw numbers can drift as the corpus or engines change)
       but NEVER touches status/verdict/investigated_by/investigated_at/credit_tools/debit_tools
       once a human has set them -- re-running the tri-comparison tool must never silently revert
       a validated entry back to looking unvalidated, and must never let fresh examples quietly
       overwrite the ones a human actually read.
    4. If a previously-seen shape doesn't reproduce on a fresh run (the underlying cause got
       fixed, or corpus content moved), its entry is kept, not deleted -- `still_reproduces` is
       set to false and `last_reconciled_at` still updates. Keeping a historical record of what
       used to disagree and was resolved is worth more than silently losing it; an entry that
       stops reproducing is also, trivially, no longer capable of blocking a chart badge (see
       has_open_question below) or being credited/debited (see apply_verified_adjustments below),
       so keeping it costs nothing at read time.

VERIFIED ADJUSTMENTS (credit_tools / debit_tools) -- LETTING A VERDICT MOVE THE NUMBER, NOT JUST ANNOTATE IT
    Validating an entry (step 2 above) used to change only how the chart is READ (the `*`/badge
    gating `has_open_question()` drives) -- the raw precision percentage itself stayed defined
    purely by tool agreement, forever, even after a human read the source and confirmed a specific
    tool's "uncorroborated" claim was actually real, or confirmed a "corroborated" claim was
    actually a shared mistake. Confirmed as a genuine gap, not a deliberate design choice
    (2026-08-20): GitGalaxy's C func precision sat at 99.77% (1726/1730) with the remaining 4
    being the exact functions a ledger entry had already validated as real (both other tools
    locally lose the one function right after a bare SLOT-macro invocation line, Claim 3 in
    docs/why_gitgalaxy_beats_ast_here.md) -- confirmed-correct, manually-verified, and the score
    never reflected it.
    Both fields are lists of tool names, empty by default, set DELIBERATELY alongside `verdict`
    when validating -- NEVER inferred from the verdict's prose, since most validated shapes don't
    resolve to "one tool is simply right/wrong" at all (a structural ambiguity, a genuinely mixed
    multi-cause shape) and leaving either field empty is the correct, common case, not an
    oversight to fix later.
      - `credit_tools`: set when the verdict cleanly confirms THIS tool's claim, on this shape, is
        real, and the reason the other tool(s) don't corroborate it is a confirmed limitation in
        THEM, not an open question about the credited tool. `apply_verified_adjustments()` (below)
        ADDS the shape's occurrence count into the credited tool's `matched_consensus` for
        precision -- the credited tool already claimed these occurrences (that's why it's in
        `agreeing_tools` for this shape to begin with); crediting converts already-claimed-but-
        unconfirmed into claimed-and-confirmed, `total_slots` is untouched.
      - `debit_tools`: the symmetric case -- set when the verdict confirms this tool's agreement
        with another tool on this shape is a SHARED MISTAKE, not real corroboration. Real example:
        C's `agree[ctags,tree_sitter]_vs[gitgalaxy]` shape -- `EXPORT_FUN`/
        `MICROPY_WRAP_MP_EXECUTE_BYTECODE` are both already-known macro hallucinations that ctags
        AND tree-sitter independently mis-tag the same way, so their mutual "agreement" was never
        real corroboration, just two different regex/grammar engines getting fooled by the same
        macro-definition text. `apply_verified_adjustments()` SUBTRACTS the shape's occurrence
        count from each debited tool's `matched_consensus` -- again `total_slots` is untouched
        (both tools genuinely did claim these occurrences; that fact doesn't change, only whether
        the claim should count as corroborated). Debiting BOTH agreeing tools on a shape is normal
        and expected when they're independently wrong for the same underlying reason (the C
        example above); debit only one of two agreeing tools when the verdict specifically
        distinguishes them (rare -- most 2-tool-agree shapes that turn out wrong are wrong for a
        shared reason, per every case actually seen so far).
    Scope discipline carries over from every other part of this module: set these two fields with
    the same rigor as `verdict` itself -- a rubber-stamped credit/debit is worse than leaving both
    empty, since it moves a number based on a conclusion nobody actually checked.
      - GEOMETRY GUARD: a credit is only meaningful on a shape's SOLE agreeing tool (the one
        reconcile_symbols left uncorroborated), and a debit is only meaningful on a tool that was
        part of a 2+-tool agreement (the corroboration a debit revokes). `apply_verified_adjustments`
        skips -- with a stderr warning, never a silent no-op -- any credit/debit whose named tool
        doesn't fit that geometry (a debit on a lone claimant or a dissenting-side tool used to
        drive the numerator negative: m4/scheme's `-73/79` and `-42/92` on the chart, and zig's
        impossible 100.27% class precision from the mirror-image bad credit). The guard doesn't
        rewrite the ledger; the warning is there so a human fixes the entry.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Type-hint only -- importing this eagerly would drag in tri_comparison_gatherer's
    # tree_sitter_accuracy_audit/tree_sitter_language_pack dependency chain just to read a JSON
    # file, which tri_comparison_report.py (this module's only other caller besides the tool
    # itself) has no other reason to need. `from __future__ import annotations` above already
    # makes every annotation in this file a lazy string, so this import never has to run.
    from tri_comparison_reconcile import DiscrepancyGroup, MetricScore

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
                "credit_tools": [],
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


def _credit_is_well_formed(tool: str, g: DiscrepancyGroup) -> bool:
    """A credit only has a defined meaning when `tool` is the SOLE agreeing tool on this shape.
    reconcile_symbols() adds an occurrence to a tool's precision `matched_consensus` iff at least
    one OTHER tool corroborated it at that slot (`len(present) >= 2`); a lone claimant therefore
    starts with those occurrences in `total_slots` but NOT `matched_consensus`, which is exactly
    the gap a `credit` closes once a human confirms the uncorroborated claim was real. Crediting a
    tool that already shares a 2+-tool agreement double-counts (it's already in `matched_consensus`);
    crediting a tool that isn't in `agreeing_tools` at all invents a claim it never made."""
    return tool in g.agreeing_tools and len(g.agreeing_tools) == 1


def _debit_is_well_formed(tool: str, g: DiscrepancyGroup) -> bool:
    """The mirror of `_credit_is_well_formed`: a debit only has a defined meaning when `tool` was
    part of a 2+-tool agreement (so reconcile_symbols() already counted these occurrences as
    corroborated in its `matched_consensus`) and the verdict now revokes that corroboration as a
    shared mistake -- the C `agree[ctags,tree_sitter]_vs[gitgalaxy]` case in this module's own
    docstring. Debiting a lone claimant, or a tool on the dissenting (absent) side, subtracts
    occurrences that were never in `matched_consensus` to begin with and drives the numerator
    negative (m4/scheme, real ledger entries that produced `-73/79` / `-42/92` on the chart)."""
    return tool in g.agreeing_tools and len(g.agreeing_tools) >= 2


def _warn_malformed(tool: str, g: DiscrepancyGroup, kind: str) -> None:
    print(
        f"tri_comparison_ledger: ignoring malformed {kind}_tools=[{tool}] on {g.shape_key} "
        f"(agreeing_tools={sorted(g.agreeing_tools)}) -- a {kind} on this shape has no defined "
        f"effect on precision; clean the ledger entry (see apply_verified_adjustments docstring).",
        file=sys.stderr,
    )


def apply_verified_adjustments(
    precision_scores: dict[str, MetricScore], groups: list[DiscrepancyGroup], path: Path = LEDGER_PATH
) -> None:
    """Mutates `precision_scores` in place -- see this module's own VERIFIED ADJUSTMENTS docstring
    section for the full reasoning. For every group whose ledger entry is `status == "validated"`,
    adds that group's CURRENT `total_occurrences` (not the ledger's possibly-stale
    `last_seen_count` -- `groups` is this run's fresh reconciliation, the ledger only supplies the
    human's credit/debit decision) to each `credit_tools` entry's `matched_consensus`, and
    SUBTRACTS the same amount from each `debit_tools` entry's `matched_consensus`. A no-op for any
    group with no ledger entry, an unvalidated one, or both fields empty/absent -- the
    overwhelmingly common case, since most validated shapes don't resolve to "one or more specific
    tools are simply right/wrong" at all. Only ever touches precision -- `total_slots` (what a
    tool itself claimed) is untouched either direction, and recall/found-count panels don't call
    this at all since "found more" was never a ranked claim to begin with (see
    tri_comparison_chart.py's own PANELS docstring).

    A credit/debit that names a tool the shape's geometry can't support -- a credit on a tool
    that already shares a 2+-tool agreement (or isn't in `agreeing_tools` at all), or a debit on
    a lone claimant / a dissenting-side tool -- is malformed: it has no defined effect on
    `matched_consensus` (and a bad debit drives the numerator negative, the m4/scheme `-73/79` /
    `-42/92` bug). Those are skipped with a stderr warning rather than applied; see
    `_credit_is_well_formed` / `_debit_is_well_formed`. The ledger JSON isn't rewritten here --
    the warning is the signal to clean the offending entry by hand."""
    ledger = load_ledger(path)
    entries = ledger.get("entries", {})
    for g in groups:
        if g.metric != "existence":
            # `groups` (from reconcile_symbols) mixes existence- and args-shaped groups for
            # symbol_type=="function" -- precision is inherently existence-shaped (it's a
            # question about whether a claimed occurrence is real), so an args-metric group here
            # is never eligible, regardless of what its own ledger entry says.
            continue
        entry = entries.get(g.shape_key)
        if not entry or entry["status"] != "validated":
            continue
        for tool in entry.get("credit_tools", []):
            if tool not in precision_scores:
                continue
            if not _credit_is_well_formed(tool, g):
                _warn_malformed(tool, g, "credit")
                continue
            precision_scores[tool].matched_consensus += g.total_occurrences
        for tool in entry.get("debit_tools", []):
            if tool not in precision_scores:
                continue
            if not _debit_is_well_formed(tool, g):
                _warn_malformed(tool, g, "debit")
                continue
            precision_scores[tool].matched_consensus -= g.total_occurrences

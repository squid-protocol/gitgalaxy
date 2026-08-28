# How to Investigate a Tri-Comparison Discrepancy

This is the workflow behind the tri-comparison tool's gray-vs-colored bars: how a raw
disagreement between GitGalaxy, tree-sitter, and ctags becomes either "confirmed and colored" or
stays "flagged and gray." See `tests/tools/tri_comparison_reconcile.py` and
`tests/tools/tri_comparison_ledger.py`'s own module docstrings for the mechanics this doc is the
human-facing procedure for.

## Why this exists

None of the three tools is ground truth here. GitGalaxy can be right when tree-sitter is wrong
(see `docs/self_scan/README.md`'s "tree-sitter as a baseline, not as infallible ground truth"
section for confirmed cases), and the same is now true three ways: ctags can side with either
one, or be the odd one out itself. A raw disagreement is a *question*, not an automatic loss for
whichever tool is outvoted — the only way to turn a question into an answer is to read the actual
source at the point of disagreement, the same instinct already used to confirm every case in that
README section, just made a repeatable process instead of ad hoc.

## The lifecycle

1. **Gather + reconcile.** `tri_comparison_gatherer.py` runs all three tools independently over
   `language-crucible`; `tri_comparison_reconcile.py` matches their readings by name (rank-paired
   by line when a name repeats) and groups every disagreement by **shape** — which tools agreed,
   which didn't, for a given language/symbol-type/metric. A shape is NOT one instance; csharp's
   `agree[ctags,gitgalaxy]_vs[tree_sitter]` shape alone covers 271 individual functions, almost
   certainly one systematic tree-sitter recall gap, not 271 separate things to check.
2. **Merge into the ledger.** `tri_comparison_ledger.py`'s `merge_and_save()` writes any new
   shape into `docs/self_scan/tri_comparison_ledger.json` as `status: "unvalidated"`, and updates
   the occurrence count/example list on shapes it's already seen — without ever touching
   `status`/`verdict` on one a human has already validated. Nothing here decides who's right;
   it's bookkeeping.
3. **Investigate.** For each `unvalidated` entry where `"gitgalaxy"` appears in
   `dissenting_tools` (the only kind that grays out a chart cell — see step 5), open a handful of
   the entry's `last_seen_examples` (`file_path` + `name`, capped at 10, not exhaustive — a
   representative sample of the shape, chosen so a human doesn't have to read hundreds of
   near-identical cases) and **read the actual source** at that location. Concretely:
   - Open `{corpus_dir}/{file_path}` at the reported name/line for each example.
   - Work out the real answer by hand: does this function/class actually exist, and with how
     many parameters, by the same definition a person would use?
   - Check whether the pattern generalizes across the sampled examples (a shared cause — a
     specific syntax shape, a specific tree-sitter grammar gap, a ctags kind-mapping edge case)
     or whether the examples are actually unrelated and the shape needs splitting into more than
     one real question (rare, but possible — the ledger has no problem holding a
     revised/re-added entry for that case).
4. **Record the verdict.** Hand-edit the entry in `tri_comparison_ledger.json`:
   ```json
   "status": "validated",
   "verdict": "<what you found, which tool(s) were actually right, and why — enough for someone
                else to trust the conclusion without re-doing the investigation>",
   "investigated_by": "<name>",
   "investigated_at": "<YYYY-MM-DD>"
   ```
   A verdict isn't required to mean "GitGalaxy was right" — recording "confirmed GitGalaxy
   under-counts args on multi-line `pub(crate) unsafe fn` signatures in Rust; ctags and
   tree-sitter both correctly report 5 params where GitGalaxy reports 3" is just as valid a
   verdict, and belongs in a GitHub issue against GitGalaxy's own engine, same as any other
   confirmed defect — the ledger records the finding, it doesn't fix the engine.
5. **The chart reads the ledger, not the raw numbers.** `is_language_metric_clean()` renders a
   `(language, symbol_type, metric)` cell colored only if every currently-reproducing shape
   where GitGalaxy is in `dissenting_tools` has `status: "validated"`. A shape where GitGalaxy is
   on the *agreeing* side (like csharp's 271-occurrence one above) never grays anything out on
   its own — GitGalaxy isn't the one being questioned there.

## When a validated shape's count changes a lot

`merge_and_save()` refreshes `last_seen_count`/`last_seen_examples` on a validated shape without
ever touching `status`/`verdict` (step 2 above) — deliberately, so a routine re-run doesn't need a
human to re-bless every shape every time. That's the right default when the corpus is stable. It
stops being safe to trust blindly the moment the corpus itself changes substantially for that
language (a new repo added, an existing one expanded) — a shape key only names *which tools
agreed/disagreed on which metric*, not *why*, and nothing stops a genuinely new mechanism from
hiding inside a count increase on an already-`validated` shape, indistinguishable from more of the
same, until someone actually looks.

**Concrete case this happened (2026-08-28):** cobol's corpus grew from 53 to 308 files across six
new/expanded repos. `cobol/function/existence/agree[ctags]_vs[gitgalaxy]` — already `validated`,
`still_reproduces: true` — went from 133 occurrences to 773 without any status change, which is
exactly the "looks fine, nobody has to look again" state the merge step is designed to produce. A
full re-check (`tri_comparison_gatherer.gather_language()`, name-diffed across every file, not
just the capped sample) confirmed it really was the same single already-documented ctags
limitation (`ctags_reader.py`'s "tags ANY period-terminated word" note) generalizing to new
syntax shapes the smaller corpus never exercised — division/section headers
(`WORKING-STORAGE`/`CONFIGURATION`/`LINKAGE`/etc.) and embedded-SQL qualified-column periods
(`COMMERCIAL.POLICYNUMBER`), not just the scope-terminators (`END-IF.`) the note originally
evidenced — zero unexplained residual, zero remaining GitGalaxy defect. But a *sibling* shape for
the same language, `cobol/class/existence/agree[gitgalaxy]_vs[ctags]`, was sitting `unvalidated`
with all 6 of its occurrences newly introduced by the same corpus expansion (5 from a program
that splits `PROGRAM-ID.` and its name across two lines, ctags' Cobol parser doesn't handle at
all; 1 from an underscore-containing program name ctags truncates) — a completely different,
previously undiscovered mechanism. Trusting "cobol already has validated shapes, this language is
probably fine" without checking BOTH shapes individually would have missed it.

**The rule:** after adding or substantially expanding a language's corpus content, don't just look
at which shapes are `unvalidated` — for that language's shapes that are already `validated` too,
compare the new `last_seen_count` against what it was before the corpus change. A count that grew
roughly proportionally to the file-count increase is consistent with (not proof of) "same
mechanism, more instances" and still deserves the re-sampling above before trusting it; a count
that grew disproportionately, or a shape whose `last_seen_examples` now cite files that didn't
exist in the corpus before, is a specific signal to re-verify rather than assume. Either way,
re-running step 2.5's full gather-and-diff (from the `tri-comparison-ledger-sweep` skill) costs
one script run and settles it with evidence instead of trust. If the mechanism still fully and
exclusively accounts for the new count, update the verdict text's cited occurrence number (and any
cross-referenced note in `ctags_reader.py`/`tree_sitter_accuracy_audit.py`) so it doesn't read as
stale to the next person, without changing `status`. If it doesn't, treat it as a fresh
investigation — same lifecycle as an `unvalidated` entry, even though the JSON's `status` field
still says `validated` until you change it.

## What NOT to do

- Don't mark an entry `validated` without actually reading source — a rubber-stamped verdict is
  worse than an honest gray bar, since it actively hides a question that hasn't been answered.
- Don't delete an entry that stops reproducing (`still_reproduces: false`). It's a record of a
  question that was once open; keep it, don't erase the history.
- Don't invent a per-instance ledger entry. If a shape's examples turn out to span more than one
  real cause, split it into more than one shape-level entry (re-run reconciliation after the
  underlying grouping logic, if needed, reflects the real distinction) — never track individual
  occurrences one at a time.

## Example (worked, from building this tool)

`rust/function/args/agree[ctags,tree_sitter]_vs[gitgalaxy]` flagged
`bevy/bevy_ecs_table.rs::initialize` as one example. Reading the source: the real signature is
`(&mut self, row: TableRow, data: OwningPtr<'_>, tick: Tick, caller: MaybeLocation)` — 5 real
parameters. ctags and tree-sitter both report 5; GitGalaxy reports 3. That's a genuine GitGalaxy
under-count on a multi-line signature, not a ground-truth artifact — the verdict for that shape
(once the rest of its sample is read, not just this one case) should say so plainly, and the
underlying engine defect belongs in its own GitHub issue, separate from the ledger entry itself.

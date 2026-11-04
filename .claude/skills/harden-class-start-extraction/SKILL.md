---
name: harden-class-start-extraction
description: Extend #1264's per-language class_start named-entity extraction (gitgalaxy/core/detector.py's _CLASS_START_NAMED_EXTRACTION_LANGS allowlist) to more languages, using the epic #1295 methodology. Use when the user asks to "add X to the class_start allowlist", "harden class detection for X", "fix class recall for X", or references epic #1295 / issue #1264's follow-up. Distinct from harden-language-extraction (func_start/args/class_start's own regex correctness) and harden-strict-signatures (branch/io/safety signature coverage) -- this is specifically about whether class_start's matches get reused as NAMED entities (class_data/class_count) versus the legacy hardcoded fallback regex.
---

Source of truth is `tests/extraction/how_to_extend_class_start_named_extraction.md` -- read it
directly, it has the full per-language diagnosis table (how each of the epic's 13 languages
turned out: a real regex problem vs. a ground-truth measurement gap vs. a conceptual mismatch),
the recurring-cause checklist, and the shared-file collision warning for parallelizing. Don't
re-derive any of that from scratch or from memory of a past pass.

**Status (2026-11):** epic #1295 is closed. 11 of its 13 languages are on the allowlist; css and
html are permanently out of scope (the doc's "Decided: not extending" section, enforced in code
since #2798). The allowlist now holds 44 languages, many added with their language. Languages
with a `class_start` rule still on the legacy fallback: ada, assembly, crystal, fsharp, scheme,
yaml, zscript. Recompute before you start: compare `_CLASS_START_NAMED_EXTRACTION_LANGS` with the
languages in `LANGUAGE_DEFINITIONS` whose `rules` carry `class_start`.

## The one thing to check before anything else

Run `python tests/tools/class_start_diff.py --lang <x>` before touching any regex. If
`real_classes` reads 0 or implausibly low, the blocker is `tree_sitter_accuracy_audit.py`'s own
ground-truth extraction (`_get_node_name` missing a branch for that language's node type), not
the language's `rules` in `gitgalaxy/standards/language_standards/languages/<lang>.py`. The
how-to doc's table has the confirmed root causes and fixes for the epic's languages (go/kotlin/
objective-c/zig were fixable field-name gaps; dart/ruby/haskell/perl were pure ground-truth fixes)
and the css/html reasoning for when the comparison is not even meaningful.

## Process

1. **Scope the request.** One language, or a batch of ground-truth-gap fixes (these touch
   `tree_sitter_accuracy_audit.py`, not the language's rules file, so they're a distinct unit of
   work from regex hardening), or a "is this even a class" judgment call like css/html's.
   Epic #1295 is closed: file new work via `issue-generation` once scope for a batch is clear,
   mirroring epic #813/#1069's structure.
2. **Get the diff before reading the language's rules file cold.**
   `python tests/tools/class_start_diff.py --lang <x>` -- prints per-file extra/missing names with
   source-line context, using the *exact* name-resolution algorithm the live pipeline uses
   (imports `_resolve_class_start_match` from `detector.py` directly, so it can't drift). Its own
   docstring has a caveat: it matches raw file text, not `prism.py`-shielded `code_stream`, so
   treat its numbers as triage, not a final verdict.
3. **Classify each `extra`/`missing` name** against the how-to doc's recurring-cause list (no
   capture group / declaration-vs-usage ambiguity / compound modifiers / ground-truth scope
   mismatch / ground-truth measurement gap). This is the judgment step -- keep it in the main
   conversation or a Sonnet-tier agent, not a scout.
4. **Fix real regex bugs with the full discipline**: ReDoS scaling check on any quantifier
   change, follow `gitgalaxy/standards/how_to_add_a_language.md`'s numbered engine rules (19 as of 2026-11).
5. **Flip the allowlist and verify for real** -- the how-to doc's step 6 has the exact command
   sequence (`tree_sitter_accuracy_audit.py --lang <x> --ci` then `--regenerate` -- which now also
   refreshes the summary table itself, no separate `--summary-table` step needed --
   `crucible_check.py` both modes, `audit_check.py --regenerate` for pure line-shifts, the relevant
   pytest suites). The raw-text triage in step 2 is not a substitute for this.
6. **Close the loop**: comment on the tracking issue (closed epic #1295 for history) with the result, append any newly-confirmed recurring-cause
   class to the how-to doc itself (not just the PR description).

## Parallelizing across languages -- read the how-to doc's warning first

Unlike epic #1069's strict-signature sweep (each language owns its own test file, fully
parallelizable), this work shares three touchpoints across every language's PR: the
`_CLASS_START_NAMED_EXTRACTION_LANGS` frozenset itself, the summary table in
`gitgalaxy/standards/language_standards/__init__.py`, and the golden master fixtures. Prefer one
language (or a tiny single-digit-extra batch) per PR, merged before starting the next, over concurrent worktree
agents editing the same shared files. If splitting concurrently anyway, keep the ground-truth-gap
fixes (touch `tree_sitter_accuracy_audit.py` only) in separate PRs from the regex-hardening
languages (touch `language_standards/languages/<lang>.py`/`detector.py`) so the two kinds of work don't collide.

Keep the actual regex engineering (step 4) and the allowlist/baseline verification (step 5) in
the main conversation -- same reasoning `harden-language-extraction`'s skill gives for its own
step 5: tight iteration against real tooling and judgment about ambiguous cases, not mechanical
script execution a cheaper subagent could do instead.

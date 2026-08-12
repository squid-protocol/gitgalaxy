---
name: harden-class-start-extraction
description: Extend #1264's per-language class_start named-entity extraction (gitgalaxy/core/detector.py's _CLASS_START_NAMED_EXTRACTION_LANGS allowlist) to more languages, using the epic #1295 methodology. Use when the user asks to "add X to the class_start allowlist", "harden class detection for X", "fix class recall for X", or references epic #1295 / issue #1264's follow-up. Distinct from harden-language-extraction (func_start/args/class_start's own regex correctness) and harden-strict-signatures (branch/io/safety signature coverage) -- this is specifically about whether class_start's matches get reused as NAMED entities (class_data/class_count) versus the legacy hardcoded fallback regex.
---

Source of truth is `tests/extraction/how_to_extend_class_start_named_extraction.md` -- read it
directly, it has the full per-language diagnosis table (which of the 13 remaining languages have
a real regex problem vs. a ground-truth measurement gap vs. a conceptual mismatch, confirmed
during the epic's scaffolding pass), the recurring-cause checklist, and the shared-file collision
warning for parallelizing. Don't re-derive any of that from scratch or from memory of a past pass.

## The one thing to check before anything else

Run `python tests/tools/class_start_diff.py --lang <x>` before touching any regex. If
`real_classes` reads 0 or implausibly low, the blocker is `tree_sitter_accuracy_audit.py`'s own
ground-truth extraction (`_get_node_name` missing a branch for that language's node type), not
`language_standards.py`. The how-to doc's table already has confirmed root causes and fixes for
go/kotlin/objective-c/zig (fixable field-name gaps), and flags perl/css/html as needing a judgment
call about whether the comparison is even meaningful. Only c/swift/rust/dart/ruby/haskell
currently have trustworthy ground truth to test a `class_start` regex against.

## Process

1. **Scope the request.** One language, the small "ground-truth-gap" batch (go/kotlin/
   objective-c/zig -- these touch `tree_sitter_accuracy_audit.py`, not `language_standards.py`,
   so they're a distinct unit of work from regex hardening), or the css/html/perl judgment calls.
   Don't default to "just do #1295" -- it's not a single issue with sub-issues yet; file them via
   `issue-generation` once scope for a batch is clear, mirroring epic #813/#1069's structure.
2. **Get the diff before reading `language_standards.py` cold.**
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
   change, follow `gitgalaxy/standards/how_to_add_a_language.md`'s 12 engine rules.
5. **Flip the allowlist and verify for real** -- the how-to doc's step 6 has the exact command
   sequence (`tree_sitter_accuracy_audit.py --lang <x> --ci` then `--regenerate`, `--summary-table`,
   `crucible_check.py` both modes, `audit_check.py --regenerate` for pure line-shifts, the relevant
   pytest suites). The raw-text triage in step 2 is not a substitute for this.
6. **Close the loop**: comment on #1295 with the result, append any newly-confirmed recurring-cause
   class to the how-to doc itself (not just the PR description).

## Parallelizing across languages -- read the how-to doc's warning first

Unlike epic #1069's strict-signature sweep (each language owns its own test file, fully
parallelizable), this work shares three touchpoints across every language's PR: the
`_CLASS_START_NAMED_EXTRACTION_LANGS` frozenset itself, `language_standards.py`'s summary table,
and the golden master JSON fixtures. Prefer one language (or the tiny single-digit-extra batch:
html/objective-c/kotlin/ruby) per PR, merged before starting the next, over concurrent worktree
agents editing the same shared files. If splitting concurrently anyway, keep the ground-truth-gap
fixes (touch `tree_sitter_accuracy_audit.py` only) in separate PRs from the regex-hardening
languages (touch `language_standards.py`/`detector.py`) so the two kinds of work don't collide.

Keep the actual regex engineering (step 4) and the allowlist/baseline verification (step 5) in
the main conversation -- same reasoning `harden-language-extraction`'s skill gives for its own
step 5: tight iteration against real tooling and judgment about ambiguous cases, not mechanical
script execution a cheaper subagent could do instead.

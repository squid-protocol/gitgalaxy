---
name: harden-language-extraction
description: Deepen or fix a language's structural-extraction accuracy in gitgalaxy/standards/language_standards.py (func_start/args/class_start/_dependency_capture regexes) using the epic #813 methodology. Use when the user asks to "harden extraction for X", "add strict tests for language X", "find bugs in X's parsing", or similar per-language regex-correctness work -- not for adding a brand-new language from scratch (that's how_to_add_a_language.md's LLM generation prompt) and not for the broader ReDoS/boundary-correctness rules covered there either.
---

Source of truth is `tests/extraction/how_to_harden_extraction.md` -- read it directly, don't work
from a summary here or from memory of a past pass; it has the full checklist, a 43+-entry (and
growing) recurring-bug-class list, and the verification discipline. It's the companion to
`gitgalaxy/standards/how_to_add_a_language.md` (the 12 engine rules for ReDoS/boundary
correctness) -- read that one too if the work is likely to touch a shared regex idiom rather than
a language-specific quirk.

## Process (translating that doc's 5-stage pipeline to this tool's Agent tool)

1. **Load the target.** Read the language's full `rules` dict from `language_standards.py` and its
   existing cases in `tests/extraction/languages/test_<lang>.py` (or the old monolithic
   `test_*_extraction_strict.py` files if it hasn't migrated yet). Work one language, all four
   gauntlets, in one sitting -- not gauntlet-by-gauntlet across languages.
2. **Research real-world syntax** (the "Linguist" stage) if the language's modern idioms, legacy
   eras, or edge cases aren't already well understood in this conversation -- spawn an `Explore` or
   `general-purpose` Agent for this rather than guessing; it's read-heavy and benefits from a fresh
   pass over official docs/spec examples.
3. **Generate adversarial cases** (the "Red Teamer" stage) covering the three tiers (valid/
   invalid/pathological) per the doc's per-language checklist. For a language with real suspected
   bugs, consider spawning this as an isolated Agent call kept blind from the current
   implementation, so it's testing the rule's real-world scope, not confirming the existing regex.
4. **Empirically verify every candidate** against the real compiled regex with
   `tests/extraction/tools/verify_candidates.py` before adding it to a test file -- never guess
   whether a payload matches. A failing verification is a finding to triage (real bug vs.
   unrealistic payload), not an automatic fix.
5. **Fix real bugs with the full discipline**: ReDoS scaling check on any quantifier change,
   `python tests/tools/audit_check.py` (add `--regenerate` for pure line-shifts), then
   `pytest tests/extraction/languages/test_<lang>.py`. If the fix touches `language_standards.py`,
   `detector.py`, or `prism.py`: `python tests/tools/crucible_check.py` -- confirm any real diff is
   confined to the language(s) actually changed (check `_dependency_capture` fixes for legitimate
   cross-language DAG ripple, per the doc's note) before `--update --yes`.
6. **Close the loop**: migrate the language's cases into `tests/extraction/languages/test_<lang>.py`
   if not already done, append any newly-confirmed recurring-bug-class or lesson to
   `how_to_harden_extraction.md` itself (not just the PR description), and use the
   `issue-generation` skill for epic/sub-issue bookkeeping if this is tracked work rather than an
   ad hoc fix.

Keep the actual regex engineering (step 5) in the main conversation -- it needs tight iteration
against `verify_candidates.py` and real judgment about ambiguous cases, which is exactly the kind
of work this project's model-tiering guidance (CLAUDE.md) reserves for the main session rather than
a cheaper subagent.

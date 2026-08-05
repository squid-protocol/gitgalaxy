---
name: harden-strict-signatures
description: Deepen the non-extraction-pillar structural-signature test coverage in tests/extraction/languages/test_<lang>_strict.py (branch/io/safety_bypasses/ReDoS/etc. -- NOT func_start/args/class_start/_dependency_capture, that's harden-language-extraction's job) using the epic #1069 methodology. Use when the user asks to "harden strict signature tests for X", "close the ReDoS gap for X", "add missing signature cases for X", or references epic #1069 / issues #1070-1074.
---

Source of truth is `tests/extraction/how_to_harden_strict_signatures.md` — read it directly, it
has the corrected ReDoS methodology (don't assume `_best_of_timing` mechanically replaces
`assert_redos_immune`; the doc explains why) and the section-by-section checklist mapped onto
issues #1070–#1074. It's the sibling to `tests/extraction/how_to_harden_extraction.md`
(`harden-language-extraction` skill) — read that one too if you're unsure which suite a rule
belongs to.

## Process

1. **Scope the request.** One language across all applicable sections (A–D from the doc), one
   section across a batch of languages, or a specific issue number (#1070–#1074). Sub-issues are
   grouped by problem type, not per-language — don't default to "just do #1070" if the user asked
   for a language.
2. **Get the gap report before reading anything else.** Either run
   `python tests/extraction/tools/audit_strict_coverage.py --lang <X> --json` yourself, or delegate
   it to the `strict-signature-scout` subagent (Haiku-pinned — this step is pure script execution,
   no judgment, exactly what that agent is for). Don't open `language_standards.py` cold to figure
   out what's missing; the script already slices it.
3. **Draft candidate cases** (the judgment step — keep this in the main conversation or a
   Sonnet-tier agent, not the scout). For each gap the report surfaced:
   - a realistic positive snippet (real code shape, not a synthetic string engineered to match)
   - a realistic negative/lookalike snippet where the doc's section D applies
   - for ReDoS work, an adversarial "never closes" payload per the doc's diagnose-first sequence
4. **Verify every candidate before writing it in** — either run `verify_candidates.py`'s
   `check_case`/`check_many` yourself, or hand the drafted tuples to `strict-signature-scout` for
   batch verification (mechanical execution + reporting, same reasoning as step 2). A failing
   verification is a finding to triage, not something to quietly drop or auto-fix.
5. **Write the survivors into `test_<lang>_strict.py`**, then run
   `pytest tests/extraction/languages/test_<lang>_strict.py` and
   `python tests/tools/audit_check.py` before considering the language done.
6. **If a real regex bug surfaced**, fix it with the full discipline the doc describes (ReDoS
   scaling proof, `crucible_check.py` if `language_standards.py`/`detector.py`/`prism.py` changed)
   — keep this part in the main conversation; it needs the same tight iteration and judgment
   `harden-language-extraction` reserves for step 5 of its own process, not a subagent.

## Parallelizing across languages

Each language owns its own `test_<lang>_strict.py` file with zero cross-file overlap, so batches
of languages can run as concurrent subagents once step 3's case-drafting judgment is understood
for that batch (e.g. one agent per ~5 languages for issue #1073's 17-language ghost-prevention
sweep). Two-tier split:

- **`strict-signature-scout` (Haiku)**: gap reports and candidate verification — mechanical,
  well-defined output, no realism judgment. Cheap to run per-language or per-batch.
- **Case-drafting agent (Sonnet, e.g. `general-purpose` or the main session)**: the actual
  "is this snippet realistic" and "does this failing verification mean a real bug" judgment calls.

If running truly in parallel (multiple case-drafting agents editing different `_strict.py` files
at once), consider `isolation: "worktree"` per batch so concurrent edits don't collide on commit —
or have each agent report its diff back for serial application instead.

## Closing the loop

Use the `issue-generation` skill to close out #1070–#1074 (or comment progress) as batches
complete, and update `how_to_harden_strict_signatures.md` itself if a genuinely new recurring-bug
class turns up — this suite is getting adversarial attention for the first time, so a new class is
plausible, not just a repeat of `how_to_add_a_language.md`'s existing 16 rules.

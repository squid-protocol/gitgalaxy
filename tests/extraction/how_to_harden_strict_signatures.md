# How to Harden the Strict Structural-Signature Test Suite

This is the companion doc to `how_to_harden_extraction.md`, scoped to the *other* test concern
that lives alongside it in `tests/extraction/languages/`: `test_<lang>_strict.py`, one file per
language, proving `language_standards.py`'s ~43-key structural-signature rules (`branch`, `io`,
`safety_bypasses`, ReDoS immunity, etc.) — **not** the four extraction pillars (`func_start`,
`args`, `class_start`, `_dependency_capture`), which stay `how_to_harden_extraction.md`'s job.
If you're not sure which concern a rule belongs to: the four pillars extract an *exact identifier*
via a capture group; everything else here just proves *presence/absence* of a construct.

Tracked by epic [#1069](https://github.com/squid-protocol/gitgalaxy/issues/1069), which is the
`#518`-lineage follow-on applying epic `#813`'s harder-won rigor standard (born from auditing the
sibling extraction-pillar suite and finding it "dangerously sparse") to this suite, which never
got the same re-audit. Sub-issues #1070–#1074 map onto the five sections below.

## Why this doc exists

A 2026-08-05 audit (`tests/extraction/tools/audit_strict_coverage.py` — run it yourself, don't
trust a stale snapshot) found this suite thinner than what #813's founding audit already rejected
for the sibling one: roughly one positive/negative pair per signature, no pathological-tier depth
at all, 6 languages with zero per-language ReDoS regression coverage, and — most concretely —
python's and javascript's entire AI/ML extension pack (`llm_api`, `cryptography`, `rce_funnel`,
etc.) completely untested despite being a real detection-capability claim, not just a nice-to-have.

## Tooling — use these, don't rebuild them

- **`tests/extraction/tools/audit_strict_coverage.py`** — the gap detector. Run
  `--lang <x> --json` before touching any language to get its exact missing-signature list,
  ghost-prevention gaps, and current ReDoS-assertion count, instead of reading
  `language_standards.py` cold to figure out what's missing.
- **`tests/extraction/tools/verify_candidates.py`** — `check_case`/`check_many` (empirically
  verify a candidate `(rule, payload, expect_match)` against the real compiled regex before
  writing it into a test file) and `check_redos_scaling` (geometric-sweep diagnostic, see below).
  This module started as epic #813's tool but its checker functions were never extraction-pillar-
  specific — reuse it rather than writing a second copy for this suite.
- **`tests/extraction/languages/_strict_harness.py`** — the two helpers that actually get compiled
  into permanent pytest assertions: `assert_redos_immune` (single payload, single timeout — proves
  a *specific* pattern survives a *specific* adversarial payload) and `_best_of_timing` (min-of-N
  timing at one size — see the ReDoS section below for how the two combine in a real regression
  test, not as interchangeable alternatives).

## Work language-by-language, not category-by-category

Same reasoning as the extraction-pillar doc: load one language's full `rules` dict once
(`audit_strict_coverage.py --lang X --json` gives you the sliced, relevant subset — you don't need
the whole multi-thousand-line `LANGUAGE_DEFINITIONS` file in context), close as many of that
language's gaps across sections A–D below as apply in one sitting, then move on.

### A/B — ReDoS coverage (issues #1070, #1071)

**Read the actual mechanics before writing anything** — `assert_redos_immune` and `_best_of_timing`
are not interchangeable, and #1071's framing of "migrate to the scaling-ratio method" needs this
correction: they serve two different moments in the workflow, both visible in
`test_css_strict.py`'s `test_css_class_start_redos_regression` (the reference example):

1. **Diagnose first, with `check_redos_scaling`** (from `verify_candidates.py`, or `_best_of_timing`
   called directly) — sweep a rule's pattern against a "never closes" adversarial payload at
   several geometrically increasing sizes (start at n=2000, not n=32000 — some shapes, like the
   Rule 14 adjacent-quantifier bug, blow up dramatically faster than the usual nested-delimiter
   case). A ~2x-per-doubling ratio is linear and fine — **stop here, no permanent test needed
   beyond what's already there.** A ~4x-per-doubling ratio is real O(n²) backtracking and is a bug.
2. **If it's clean:** for the 6 zero-coverage languages (#1070: haskell, kotlin, lua, ruby, scala,
   swift), add a straightforward `assert_redos_immune(pattern, adversarial_payload, timeout_sec=...)`
   call per rule with an unbounded-looking quantifier, proving the *current* pattern survives a
   large payload within a generous timeout. This alone closes #1070 — it does not require
   `_best_of_timing` if there's no bug to document.
3. **If you find a real bug:** fix the regex (bound the quantifier), then write the two-part
   regression pattern `test_css_strict.py` already uses: `_best_of_timing` proving the *old, buggy*
   pattern's quadratic signature (reconstruct it inline as a comparison, exactly like the CSS
   example's `old_pattern`), paired with `assert_redos_immune` proving the *new* pattern is immune
   at an even larger payload. This is what #1071 is actually asking for in the 37
   `assert_redos_immune`-only languages: **run the diagnostic sweep to check for an undiscovered
   bug a single generous timeout might be masking** — not a mechanical rewrite of every passing
   test. Most of those 37 will come back clean; only the ones that don't need the two-part pattern.

### C — Missing signature-case coverage (issue #1072)

`audit_strict_coverage.py --lang X --json`'s `missing_case_entirely` list is the exact punch list
— no need to diff `LANGUAGE_DEFINITIONS.keys()` against the test file by hand. For each missing
key, add one realistic positive snippet (real code you'd find in an actual file of that language,
not a synthetic string engineered to match — same bar as the extraction gauntlets' `valid` tier)
plus a realistic negative/lookalike snippet, verify both with `verify_candidates.py`'s `check_case`
before writing them in, then add to the language's `_XXX_SIMPLE_CASES` list.

Prioritize **python's and javascript's AI/ML extension pack** first (`llm_api`,
`llm_orchestrator`, `llm_vector_store`, `ml_traditional`, `dl_frameworks`, `cryptography`,
`rce_funnel`, `hardware_bridge`, `exfiltration_camouflage`, `lazy_evaluation`, `vectorized_math`)
— see `gitgalaxy/standards/how_to_add_a_language.md`'s "AI/ML Extension Pack" section for what
each key is supposed to detect. This is a real blind spot in a supply-chain-risk detection
feature, not a test-depth nit.

### D — Ghost-prevention / negative-case coverage (issue #1073)

`audit_strict_coverage.py`'s `no_negative_case` list per language is every signature currently
paired with `None` in the negative slot. For each, add a realistic lookalike that should **not**
match — same discipline as the extraction gauntlets' `invalid` tier (Ghost Prevention): a different
keyword entirely is a weak test; a structural lookalike (a string literal containing the keyword,
a comment, an unrelated construct that shares surface tokens) is a real one. Verify with
`check_case` before writing it in — a negative case that turns out to actually match is a bug
finding, not a test to quietly drop.

Sequence the 17 flagged languages by real-world scan frequency if you need to prioritize (python,
javascript, java, go, ruby, php, typescript, c/cpp/csharp before less common ones) — the doc
doesn't mandate a fixed order.

### E — Case depth beyond the ~1-pair floor (issue #1074, stretch)

Deliberately last. Once A–D close the correctness/security gaps, revisit whichever signatures
turned out to be highest-ambiguity while working through them (multiple false-positive shapes
found, or the rule covers a construct with real historical syntax variation) and add multiple case
variants — different syntax eras, modifier stacking — approaching (not necessarily matching) the
extraction gauntlets' pathological-tier depth. Don't force depth onto a signature that's already
unambiguous just to hit a number.

## Verification discipline (same as the extraction-pillar doc, not repeated in full)

1. Empirically verify every candidate with `verify_candidates.py` before adding it — never guess.
2. A failing verification is a finding to triage (real engine bug vs. unrealistic payload), not an
   automatic fix.
3. Real bugs get the full discipline: ReDoS scaling check on any quantifier change,
   `python tests/tools/audit_check.py`, `pytest tests/extraction/languages/test_<lang>_strict.py`,
   and `python tests/tools/crucible_check.py` if `language_standards.py`/`detector.py`/`prism.py`
   changed (see `CLAUDE.md`'s Differential Scan section — never point a shared/stale venv at this).
4. This suite is almost entirely test-writing, not regex-fixing — expect far fewer real bugs than
   epic #813 found, since these rules were never claiming to isolate an *exact* identifier, only to
   detect presence. Don't manufacture a "finding" to justify a regex change that isn't needed.

## Closing the loop

Once a language's gaps in A–D are closed, update its entry in `audit_strict_coverage.py`'s output
implicitly (rerun the script, don't hand-track), and note any newly-confirmed recurring-bug-class
in `gitgalaxy/standards/how_to_add_a_language.md` itself if you find one that isn't already listed
there (Rules 1–16) — this suite is exactly where a new boundary/ReDoS bug class is most likely to
surface next, since it's getting adversarial attention for the first time.

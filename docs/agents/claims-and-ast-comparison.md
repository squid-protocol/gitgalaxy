---
description: "Logging cases where GitGalaxy beats tree-sitter, and the full rule that comparative-correctness claims need verified source reading, incl. ctags and tie-break."
---
# Comparative-correctness claims and AST comparison

Moved verbatim from CLAUDE.md (kept out of the always-loaded context). CLAUDE.md links here.

The general rule, stated plainly in `README.md`'s "One Graph, Not Five Separate Tools" section, is
that tree-sitter/AST parsing is *more precise per file* than GitGalaxy's regex-based structural
signatures — that's the trade GitGalaxy makes for one comparable signal set across every language
without a per-language toolchain. It doesn't hold universally, though: any time work in this repo
turns up a specific, evidenced case where GitGalaxy's output is *more* accurate than tree-sitter's
own parse (not just "different" — genuinely more correct, with a concrete before/after), log it as
its own dated Claim N in `docs/why_gitgalaxy_beats_ast_here.md` rather than leaving it as a PR
description or code comment only. Two examples already there: `args` counting in languages with no
formal parameter-list syntax at all (bash/traditional Perl, #1518/#1519), and function recall
inside dialect/extension syntax a base grammar has no concept of (Cython's `cdef class` inside
plain tree-sitter-python, #1526). Keep each claim narrow and evidence-backed (a measured
before/after, not "heuristics are sometimes better") — this doc's whole value is that it doesn't
overstate the exception into "GitGalaxy is more accurate than tree-sitter" in general, which isn't
true.

## Comparative-correctness claims require verification, not just the higher number

This generalizes a rule first proven necessary on the tri-comparison chart (`tests/tools/
tri_comparison_chart.py`, `tri_comparison_ledger.py`) but applicable anywhere in this repo a claim
gets made that one measurement is "more correct" than another — a badge, a README claim, a PR
description, a chart, a doc. **Never treat a raw number comparison alone as settling who's right.**
A strictly-highest-percentage rule doesn't know or care about sample size or whether anyone has
actually checked the disagreement against real source: a 2-sample cell at 100% (2/2) can outrank an
80-sample cell at 98.75% (79/80) with equal visual confidence, which is an artifact of an unverified
comparison, not evidence either side is more correct. The fix isn't "always trust the bigger sample"
either — it's requiring that a claim of correctness be backed by someone (human or a dispatched
agent standing in for one) actually reading the real disputed source and recording *why*, before it
drives a badge, a chart, or a claim in prose.

**The concrete mechanism this models on:** `tri_comparison_ledger.py`'s `has_open_question()` — a
cell only earns a badge/claim once every ledger entry touching it is `status == "validated"` (a
human or agent read real source and recorded a verdict), regardless of how lopsided the raw numbers
look before that. See the tri-comparison-ledger-sweep skill for the full investigate-and-verify
workflow this drives.

**Regenerating the chart/ledger itself is a separate, operational concern from the verification
rule above — read `docs/self_scan/tri_comparison_README.md` before running
`tri_comparison_chart.py` or hand-editing `tri_comparison_ledger.json`.** It's the canonical
regen doc both agents point to (this file for Claude, `ANTIGRAVITY.md` for Gemini/Antigravity), not
something to re-derive or duplicate. A real incident (PR #2111, 2026-08-22) shows why it matters:
that regen ran with no genuine `universal-ctags` binary on PATH — Ubuntu's `arduino-ctags` package
shadows the `ctags` binary name and silently degrades every language to a 2-tool comparison instead
of erroring — which reverted cobol's already-validated full-precision badge, degraded fortran's,
and dropped ctags data repo-wide, all without a single error message. Before trusting any regen's
output: confirm `ctags --version` in your own terminal prints "Universal Ctags", not an Arduino
banner or a not-found error; always regenerate with `--all --write`, never a partial `--languages`
list with `--write` (it overwrites the whole file with only those languages); and never hand-set
`status`/`verdict`/`still_reproduces` on a ledger entry — those come from a live gather or a human
(or agent-standing-in-for-one) reading real source, never a guess about whether a shape "should"
still reproduce.

**Once verified, a rate-only TIE needs its own tie-break — don't leave it badge-less by default
either.** Found via a real case: GitGalaxy, tree-sitter, and ctags can each land on 100% precision
for the same language/metric (each is simply never wrong about what it itself claims, at very
different claim counts) once GitGalaxy's extra claims are ledger-validated — a rate-only comparison
ties 3 ways and awards nobody, even though GitGalaxy demonstrably found more of the validated-real
total (`_winner_or_tie()` in `tri_comparison_chart.py`: a rate tie is broken by each tied party's
*absolute count of validated-correct occurrences*, not the raw claim count). This is the same
"more evidence should count for something" principle as the sample-size fix above, pointing the
opposite direction — a smaller sample's identical rate shouldn't get an unearned edge, but neither
should a much larger *validated* sample lose one just for tying instead of leading outright. Only
apply a count-based tie-break to values that already cleared the verification bar above; breaking
a tie with unverified counts is exactly the anti-pattern this rule exists to prevent.

# The rosetta-audit check (keyword-rosetta, no pins)

`rosetta-audit` (`.github/workflows/rosetta-audit.yml`, #2557, redesigned in #2682) runs the
[keyword-rosetta](https://github.com/squid-protocol/keyword-rosetta) control corpus's verifier
across every language folder against your PR's engine build. It is the cross-language
*consistency* twin of the tri-comparison check, and it is built the same way: **it only ever
measures, it is baseline-gated, and it is advisory.** Neither repo requires a status check to
merge, and there is no pin to bump on either side.

## What the corpus is

One identical 12-probe program written in all 46 signature-bearing languages, with the exact
planted count of every signal keyword recorded in `data/<lang>/expected_signals.json`. Identical
intent everywhere means any divergence in what the engine extracts is measured language bias.
Those manifests are the corpus's human-blessed baselines: every number in them has a
`status: "validated"` entry in its `deviation_ledger.json` (its `docs/GATING.md`), the same bar
`tests/tri_comparison_baseline_*.json` and the tri-comparison ledger hold here.

## The three outcomes

`tests/tools/rosetta_audit.py` runs every language against your build, then re-runs anything
that failed against a second build of the branch you are targeting, and classifies each
language:

| verdict | meaning | job result |
|---|---|---|
| **clean** | manifest matches your build | pass |
| **pre-existing** | fails against your build **and** against main: the corpus has not caught up with an engine change that already merged. Not your PR's doing. | notice, pass |
| **regression** | fails against your build, passes against main: **your change moves the corpus** | fail, unless labelled (below) |
| **broken** | a verifier run crashed instead of reporting PASS/FAIL (no `galaxyscope`, scan error) | fail, exit 2 |

The step summary lists the moved languages with the verifier's own diff lines. A run that
checked zero languages is exit 2, never "all OK" (#2682 — that false green happened).

## When your PR moves the corpus

Decide which of these you are in:

1. **Unintentional regression.** Fix the engine change.
2. **Intentional, corpus-visible improvement** (a rule fix or addition, a stripper change).
   The expected values live in the corpus repo, so:
   - add the **`rosetta:rebless-owed`** label to this PR — the audit reports the regressions
     as warnings and goes green, with the languages still listed in the summary. Adding the
     label re-runs the audit (the workflow listens for `labeled`), so an already-red run
     turns green on its own; you do not need to push an empty commit. Note that
     `gh pr create --label` attaches the label *after* the `opened` payload is built, so the
     very first run of a new PR reads no labels and goes red — the `labeled` event that
     follows is the one that counts;
   - merge;
   - open the re-bless PR in keyword-rosetta **against engine main** (manifests + ledger
     per its `docs/GATING.md`). Its `verify.yml` checks out engine main, so it is green by
     construction once the numbers are right. Nothing to set beforehand, nothing to reset
     after.
   - Note the companion PR in this PR's **Cross-repo** section (`docs/ecosystem.md`).
3. **A new rule absence** (you nulled/removed a rule): the separate `n/a review audit` step
   fails until the corpus ships a validated ledger entry naming the language and signal.
   Absence is either real morphology (ledger it) or a gap (don't ship it). Never regenerate
   the corpus's `docs/na_baseline.json` to absorb an unreviewed cell.

Adding a rule that was `None` is corpus-visible even though every manifest still says 0 —
see the corpus's `AGENTS.md` rule 8: pair it with a corpus plant or it manufactures a red cell
in the bias report.

## What happens after you merge

keyword-rosetta's `bias-history.yml` (the twin of `tri-comparison-history.yml` here) runs on
every corpus push and daily: it verifies the corpus against engine main, regenerates the bias
report and chart, commits them, and keeps one issue — *"corpus owes a re-bless against engine
main"* — open with the failing languages until the re-bless lands. That issue, not a red check
on someone else's PR, is where drift shows up.

## Reproducing locally

```sh
# from this repo, with the main .venv active (it has galaxyscope) and ../keyword-rosetta checked out
python tests/tools/rosetta_audit.py
# classify against a second build, e.g. the full-precision crucible venv built from main
python tests/tools/rosetta_audit.py --baseline-bin .crucible_venvs/full_precision/bin/galaxyscope
# one language, with the corpus's own verifier
GITGALAXY_PATH=$PWD python ../keyword-rosetta/tools/verify_language.py go --report
```

`GALAXYSCOPE_BIN` selects the engine build under test; `--baseline-bin` the one to classify
against. Exit codes: 0 clean or pre-existing only, 1 regression, 2 the audit did not run.

## Invariants

- The audit checks out keyword-rosetta at `main`; keyword-rosetta's CI checks out this repo
  at `main`. Both are advisory. There is no `KEYWORD_ROSETTA_REF` and no `ENGINE_REF`.
- Merge order for a count-changing engine change is engine first, corpus second. The corpus
  never needs to verify against an unmerged engine PR in CI; if you want that anyway,
  dispatch its `verify.yml` with `engine_ref=pull/<N>/head` — a run parameter, not a file.
- The corpus repo's independence is the point: expected values and their audit trail live
  there, under its gating rules. This repo only reports what its build does to them.

---
name: score-contract-audit
description: Run one SCORE-layer contract (epic #2812 Phase 4 / #2908 shape) end to end -- decompose a gated risk_<metric> into its recorded inputs, state its equation contract with D-decisions and an acceptance table, edit the formula, re-price, and land the engine + corpus PR pair. The score-layer twin of rule-contract-audit; same tier table and never-delegate list.
---

# Score-contract audit (one `risk_<metric>` family)

The score-layer twin of `rule-contract-audit` (read its "Run it cheap" section first --
**the tier table and never-delegate list there apply verbatim**: fable orchestrates and owns
every sentence/decision/go-no-go, the `contract-audit-scout` (haiku) runs the megabyte legs
and returns digests, a sonnet build agent applies exact specs, `gemini-analyzer` adversary-
reviews the draft equation and the final diff). The differences are the phases and the
evidence artifacts, which are score-shaped: a formula and its recorded inputs, not a regex
and its matched lines.

The worked precedent is `docs/risk_documentation_contract.md` (#2908) -- your contract doc
follows `docs/_score_contract_template.md`, which mirrors its sections.

## Session shape (exact commands; background every slow leg, delegate every heavy read)

```sh
# 0. environment -- one command, never the primary checkout (#2916)
tests/tools/worktree_env.sh score-<N> --corpus     # prints the five exports; eval them
```

### Phase 0 -- decomposition before opinion (scout runs, orchestrator reads digests)
```sh
$PY tests/tools/audit_score_inputs.py <metric> --corpus $KEYWORD_ROSETTA_PATH/data --summary
```
- Exit 1 (a residual) means the recorded inputs no longer explain the recorded score --
  STOP and find out why before any design work; the epic's method rests on this equality.
  (`verification` warns instead: its per-function `impact` is not persisted -- a known
  recording gap, not your bug.)
- Hold four things from the digest: the CLUSTER table's dominant input, the SENSITIVITY
  points-per-unit, the open-defect cells the bias report pins on this metric, and the
  formula's consumers (`grep -n "risk_<metric>\|_calc_<metric>" gitgalaxy/ -r`).
- A distribution/inequality metric (gini and kin) that is the lone red cell while its
  underlying count TOTAL sits on the median is a wrong per-unit DISTRIBUTION, not a slicing
  or inherency question -- one probe planted in the wrong unit, or double-counted across two
  contracts, skews the per-unit spread behind a correct total. Read the per-file values
  before reclassifying the cell (makefile `func_complexity_gini`, #2918 -> keyword-rosetta#123:
  a correct branch total of 3 hid a per-unit gini of 0.667 through three mis-diagnoses).

### Phase 1 -- the equation contract (orchestrator only; the irreducible reasoning)
Write, in the template's sections: the equation sentence (what the score MEANS, one
sentence, language-independent); each input's kind/unit and why adding them is adding like
to like (the commensurability question Phase 4 exists for); the **D-decisions** -- every
judgment the new equation forces (denominators, floors, clamps, multiplier semantics) as
D1/D2/... with the recommendation and the alternative, for maintainer sign-off BEFORE
implementation; and the **acceptance table** -- expected values on named corpus files,
computed by hand from the contract, so the implementation has a target that is not itself.
Adversary-review the draft equation with `gemini-analyzer` before locking it.

### Phase 2 -- edit, then re-price; do not eyeball
- Build agent applies the formula edit from your exact spec (one `_calc_*`, one layer).
- Scout re-runs `audit_score_inputs.py <metric>` (must be 0 residuals against the NEW
  formula) and the acceptance table's named files (must match your hand-computed values).
- Scout runs the corpus regen (`bias_report.py` under the engine worktree paths) and
  returns the headline: open-defect share, this metric's cause table.

### Phase 3 -- engine PR
```sh
PATH=$PRIMARY/.venv/bin:$PATH $PY tests/tools/contract_pr_check.py --score --corpus $KEYWORD_ROSETTA_PATH
```
One command; paste its PR-body block (Measured / Corpus / Golden masters / Tests) into the
PR. The bless it certifies re-prices a GATED score -- verify the `bless_scope --summary`
leaf keys are exactly this metric and its declared consumers, nothing else. Label
`rosetta:rebless-owed` if corpus cells move; merge order engine-first (ROSETTA_AUDIT.md).

### Phase 4 -- corpus PR (keyword-rosetta)
`tools/rebless.py <lang> --engine <worktree> --note "<dated sentence> (gitgalaxy#N): ..."`
per moved language + ledger entries per its GATING.md; retire any ledgered cell the new
equation resolves (`--retire <id> --resolved-by gitgalaxy#N --verdict "..."`).

## Done criterion
The metric's row in the score sheet carries the equation sentence and doc; the bias
report's cause table shows no unledgered cell for it; `audit_score_inputs.py <metric>`
exits 0 on the corpus; the acceptance table's values are asserted in a
`tests/metrics/test_<metric>_contract.py` the build agent wrote from your table.

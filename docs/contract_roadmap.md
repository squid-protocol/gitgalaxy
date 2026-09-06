# Contract Roadmap

> Why the cross-language bias work stalled at 88%, what the remaining red cells actually are,
> and the plan to give the engine a stated contract at each of its three layers — stream,
> count, score. Measured 2026-09-06 against engine `15d7af44` / keyword-rosetta `555604e`,
> gate at 0 unexplained. Approved 2026-09-06; the handoff surface is the epic this document
> is linked from. Companion artifact (same content, formatted):
> https://claude.ai/code/artifact/debf7286-7958-48d6-91e5-48b1bbc4abc0

## In five sentences

1. The headline consistency score paints every out-of-band cell red, including the ones the
   ledger already validated as "this language cannot express that" — so the scoreboard could
   not tell an extraction defect from a language fact, which is why the work kept looking
   like an extraction problem.
2. Of the 267 gated red cells, 38% are echoes of another cell, 17% are language inherency,
   and only about 19% are rules matching the wrong construct.
3. The largest engine-side finding is a layer leak, not a regex: `core/spatial_correlation.py`
   edits recorded signal counts in place (the ×3 cascading flux, the silencer dampeners, the
   ×5 / ×100 amplifiers), so the count the corpus reads is never the raw count.
4. "Contract" means one English sentence per signal saying what one hit is, plus its unit —
   that is what lets a formula be checked for adding like to like.
5. Plan: fix the scoreboard first, state the contracts as a sheet, move the scoring weights
   out of the counts, then audit rules and formulas in batches; close the 40 per-language
   tracking issues, which were on the wrong axis.

## 1. Where the red actually comes from

Every out-of-band cell in keyword-rosetta's `docs/bias_data.json` already carries a verdict
from `explain_out_of_band`, and every ledgered verdict carries a `disposition`. Rolling those
up by cause — which nothing in the report did before Phase 0 — gives this picture of the 267
gated cells:

| cause | cells | largest entries | right response |
|---|---|---|---|
| echo | 102 | `derived` — 50 in `risk_*`, 52 in signal/structure rows | Nothing. Stop counting them in any headline. |
| inherency | ~45 | `args-no-parameter-surface-morphology` (14), `encapsulation-is-language-idiom` (9), `no-async-construct-concurrency`, `no-lock-construct-sync-locks`, 10 `undefined` | Declare it: a contract-level absence becomes `n/a`, not red. |
| extraction | ~50 | `batch4-dual-keyword-overlaps` (23), `orphan-detection-is-name-recurrence` (13), `api-double-count-inflates-scored-api` (4), 18 `upstream-bug` entries | Rule contracts, audited per family. Most already have issues. |
| correlation | 38 | `string-literal-selective-shielding` (38) — per #2535's close: no shielding exists, strings count uniformly; the residual is the silencer dampener + ×3 flux editing `counts` | Move the adjustments out of the recorded count (Phase 2). |
| scoring | ~32 | `path-and-extension-modifiers` (23), `state-flux-branch-weighting` (11), `control-flow-ratio-denominator…`, `composite-nonlinearity…` | Formula contracts + a commensurability audit (Phase 4). |

Shares are approximate: a cell can carry more than one ledger entry, and the split of
`engine-semantic` into correlation vs scoring is by entry, not by cell. The gate's own count
(155 ledgered · 102 derived · 10 undefined) is exact.

Two consequences. First, the number worth tracking is not "share in band" but **open-defect
share**: cells whose only explanation is an open engine finding. Second, the goal was never
"every language scores the same risk" — `LANGUAGE_STRICTNESS` strata are design, and the report
already bands within them. The achievable goal is **equal counts for equal constructs**, with
every remaining difference coming from one of three declared sources: a stratum, an `n/a`, or
a filed defect. After that, a red dot is a defect by construction.

## 2. Root cause: three layers, no contract at any boundary

| layer | question | fact today |
|---|---|---|
| **0 · stream** | what text a rule sees | comments stripped by lexical family (`prism.py`); string literals never masked, for any rule, any language (#2535). Uniform, correct, and written down nowhere a rule author would read it — the corpus discovered it by decoy migration (rosetta #17, #71, #73). |
| **1 · count** | what one hit means | 2 of ~56 signals have a contract (`api`, `args`). Six proximity pairs in `spatial_correlation.py` add to `counts[...]` in place — recorded `state_mutation` is raw + 2 × cascading hits. A weighted count cannot be held equal by a corpus that plants two mutations; the ledger's `state-flux-branch-weighting` (11 cells) is this. |
| **2 · score** | how counts combine | `_calc_state_flux` subtracts declarations from writes; `control_flow_ratio` divides by an unplanted vocabulary tally; `raw_arch_api` bands per-file against per-function. Five open issues (#2705, #2770, #2771, #2772, #2655's residue) are the same defect: no stated unit per input. |

The leak, concretely:

```python
# gitgalaxy/core/spatial_correlation.py, Block 6 (documented + pinned by #2631)
counts["state_mutation"] += cascading_flux * 2   # +2 on top of the raw hit = x3 net
mitigations["amplified_cascading_flux"] = ... + cascading_flux

# gitgalaxy/metrics/signal_processor.py:1786
net_volatility = max(0.0, raw_flux - (freeze_hits * 0.5))   # writes minus declarations
```

#2631 documented the ×3 and made the raw count recoverable (`raw = recorded − 2 × amplified`),
which was the right first move. The remaining question is not *whether* the weight is right but
*which layer owns it*. While it sits in `counts`, `state_mutation` in every recorder, golden
master and corpus manifest is a score, not a count — and #2765 is trying to write a contract for
a number that already has a weight baked in.

### What a contract is

One English sentence per signal, written without reference to any language, stating what one
hit is: the sentence you would hand to whoever writes the rule for language 47 so their count
means what the other 46 mean. Its corollaries are the tie-breakers people would otherwise
resolve differently (a reference is not a declaration; a modifier counts only where it modifies
a declaration; where the language makes the property the default, the declaration is the
marker). The mathematical part is a consequence: a stated meaning has a stated **unit** — per
file, per function, per declaration, per write — and a formula can then be checked mechanically
for combining like with like. `docs/api_rule_contract.md` is the worked example; it took 46
audit rows to find the seven languages whose own idiom the rule could not see.

## 3. Decisions (approved 2026-09-06)

**D1 · Layer ownership — recorded signal counts become raw counts; correlation weights move to
the formulas that read them.** The six proximity pairs keep their semantics and their pinned
tests but stop writing into `counts`. They already write to `mitigations`; a helper in
`signal_processor.py` reads `raw + adjustment` for every consumer, so every risk score is
unchanged by construction. What changes: the `state_mutation` / `high_risk_execution` /
`concurrency` columns in `file_data`, recorders, golden masters and corpus manifests become
counts; ~21 languages' `state_mutation` drop to the planted 2; the `state-flux-branch-weighting`
entry retires. Recorders carry the weighted figure under its own key so user-facing SARIF/SBOM
numbers do not silently change meaning. Costs one golden-master bless and one corpus re-bless;
precondition for #2765.

**D2 · The per-language issues — close #2561–#2607 (40 open) and #2560; one handoff surface.**
They were organised on the wrong axis. Every cell they listed is explained (gate 0) and tracked
by cause in the ledger; #2669 had already declared them "not the work queue" and built
`issue_status.py` plus a Batch F.6 reopen loop solely to keep them current. The E.3 capstone rule
decouples: a capstone is written when the language reads clean by `language_deviations.py`,
whenever that happens.

**D3 · Where the contract sheet lives — `gitgalaxy/standards/signal_contracts.py`,
machine-readable, rendered to `docs/signal_contracts.md`, checked against
`how_to_add_a_language.md`.** One entry per signal: `kind`, `unit`, the one-sentence contract,
its status (`stated` after a corpus-wide audit, `draft` when transcribed from the schema
comment), the full-doc link, and whether the corpus plants it. `how_to_add_a_language.md` keeps
its one-liners — it is the LLM prompt for new languages — but a baseline-gated audit
(`tests/signal_contract_audit.py`, the `dead_key_audit.py` pattern) fails when a registry key
has no entry or a comment drifts from its sentence. The corpus's `_registry.py` can import the
module the way it already imports `LANGUAGE_DEFINITIONS`. Full `docs/<rule>_rule_contract.md`
files stay for rules that earn a 46-row audit.

**D4 · Headline metric — add "open-defect share" now; switch the chart badge after the README
embed is updated.** Phase 0 adds the cause roll-up and a second headline line to
`bias_report.md` and a `cell_categories` block to `bias_data.json`, leaving the chart badges as
they are.

## 4. Phases

Ordered by dependency: 0 first so progress is measured honestly; 1 and 2 before 3 because
contracts written against weighted counts would be wrong; 4 last because it needs units, and
units come from the sheet.

### Phase 0 — Scoreboard: say what each red cell is

- **repo** keyword-rosetta, one PR, no engine change
- **change** `tools/bias_report.py`: `categorize_out_of_band(verdicts, ledger)` → echo /
  inherency / extraction / correlation / scoring / unexplained by disposition (most severe wins
  on mixed cells); new report section "What the red cells are"; open-defect share;
  `bias_data.json["cell_categories"]` + `["open_defect_share"]`. `docs/GATING.md`: the category
  semantics. Entries that explain no out-of-band cell are listed (rosetta #75's decay check,
  made standing).
- **done when** the report states the open-defect share; `--gate` unchanged.
- **closes** rosetta #75 (as a standing check)

### Phase 1 — The sheet: every signal has a contract line, a kind and a unit

- **repo** gitgalaxy, one PR, no behaviour change
- **change** `gitgalaxy/standards/signal_contracts.py` (new): the stream contract and the
  count contract as module constants; one `SignalContract` per registry key, sentences
  transcribed from the schema comments as `draft`, `api`/`args` as `stated`.
  `tests/signal_contract_audit.py` (new, baseline-gated, its own workflow beside
  `dead-key-audit.yml`). `docs/signal_contracts.md` rendered from the module.
  `how_to_add_a_language.md`: the stream contract as CRITICAL ENGINE RULE 18, pointer above the
  schema. `.claude/skills/rule-contract-audit/SKILL.md`: the #2730/#2743 method as a repeatable
  workflow. `docs/ecosystem.md` skills table and the rosetta workflow row.
- **done when** the audit exits 0 with a baseline of the `draft` rows; the corpus can import
  the module.

### Phase 2 — Raw counts are counts (D1)

- **repo** gitgalaxy engine PR (label `rosetta:rebless-owed`) → golden-master bless → corpus
  re-bless PR
- **change** `spatial_correlation.py`: the pairs write to `mitigations` only.
  `signal_processor.py`: one `_weighted(raw_signals, mitigations, key)` helper; every consumer
  of the affected signals reads it. Recorders: weighted figure under its own key.
  `test_spatial_correlation.py` pins move from `counts` to `mitigations`. `core/README.md`
  proximity table updated.
- **proof** every `risk_*` column in both golden masters byte-identical before and after (the
  bless diff must be signal-column-only); corpus: `state_mutation` lands on 2 where planted,
  `state-flux-branch-weighting` flips `still_reproduces`.
- **unblocks** #2765

### Phase 3 — Count contracts, audited by family

- **repo** gitgalaxy engine PR + corpus plant/ledger PR per family (the #2743 / rosetta #53
  choreography; `rule-contract-audit` skill)
- **order** by consistency: `state_mutation` #2765 → `encapsulation` #2766 →
  `immutability_locks` #2772 (rule half: narrow swift `static|Sendable`, solidity `view|pure`,
  c `alignas|restrict`, makefile `override`; the contract states it is annotation-relative and
  default-immutable languages ledger an absence) → cobol `args`/`globals` #2804 #2805 → the rest
  by the mechanical audit. The eight unplanted risk inputs get a plant or a contract-level
  absence.
- **done when** every row in the sheet is `stated`; inherency cells are `n/a` by contract, not
  by ledger prose.

### Phase 4 — Score contracts + the commensurability audit

- **repo** gitgalaxy: one tooling PR, then one PR per formula
- **change** `tests/tools/audit_commensurability.py`: walks each `_calc_*` AST (the corpus's
  `_SignalUses` approach in `_registry.py`), reads units from the sheet, flags `+`/`−` between
  unlike units, any input the corpus does not gate, and any denominator of kind `tally`. Sits
  beside `audit_length_invariance.py` and `audit_risk_equations.py` as the third leg.
- **closes** #2770, #2771, #2772 (formula half: drop the subtraction; a normalised credit
  returns only if #2765 produces a declaration count), #2705's residue

### Phase 5 — Closure

- chart badge → open-defect share (D4 step 2) with the README copy; capstones written per
  language as each reads clean.
- **done when** open-defect share is 0 and the sheet has no `draft` rows — the epic's close
  criterion, replacing "nothing unexplained".

## 5. Tooling and skills

| artifact | repo | phase | what it does |
|---|---|---|---|
| `bias_report.py` cause roll-up | keyword-rosetta | 0 | Category per red cell; open-defect share; decayed-entry list. Reuses `explain_out_of_band`, changes no verdict. |
| `standards/signal_contracts.py` | gitgalaxy | 1 | The sheet. Importable by engine tests and the corpus. |
| `tests/signal_contract_audit.py` | gitgalaxy | 1 | Baseline-gated: every registry key has an entry; kind + unit set; schema comment contains the sentence. `--render` writes the table. |
| `docs/signal_contracts.md` | gitgalaxy | 1 | Rendered table. |
| skill `rule-contract-audit` | gitgalaxy | 1 | The repeatable method: sentence → corollaries → 46-language audit via `screen_plant.py` + crucible incidence → engine PR + corpus plant → sheet row `stated`. |
| skill `rosetta-language-sweep` | keyword-rosetta | 1 | Re-scoped to the per-language *classification instrument* a family audit calls; no longer a work queue. |
| `tools/issue_status.py` | keyword-rosetta | 1 | Kept as a generator for ad hoc standing; `--post` retired with the issues. |
| `tests/tools/audit_commensurability.py` | gitgalaxy | 4 | Unit check over the risk formulas; the third invariant beside length and tier parity. |

## 6. Issue disposition

| issues | action | goes to |
|---|---|---|
| #2561–#2607 (40 open) | close, scripted comment | epic; live standing via `language_deviations.py <lang>` |
| #2560 | close as superseded | epic |
| #2669 | final status; close | F.4 → Phase 3 families (`encapsulation` #2766, api census #2806); F.5 → the six STRUCTURE COUNTS issues; F.6 retired |
| #2765 #2766 #2772 #2804 #2805 | keep | Phase 3, in that order |
| #2770 #2771 | keep | Phase 4 |
| #2795 #2796 #2798 | keep | Phase 0/3 — structure rows get the same inherency → `n/a` treatment |
| #2792 #2801 #2803 #2806 | keep | engine defects, unchanged |
| rosetta #75 | close via Phase 0 | decayed-entry check becomes standing |
| rosetta #68 | keep | unrelated (menu tooling) |

## 7. Corrections to the first assessment

Two claims in the earlier assessment were wrong. **"Uniform string shielding" is not a phase**:
#2535 established there is no shielding to make uniform — strings are already uniform input to
every rule, and the observed per-language differences were the silencer dampener. **The ×3 is
not "in the detector"**: it is in `spatial_correlation.py`'s amplifier block, applied within a
150-character radius per function, documented and pinned by #2631. Both corrections point the
same way — at the count layer carrying score-layer adjustments — which is why D1 replaced the
shielding item.

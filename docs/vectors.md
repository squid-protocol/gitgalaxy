# The 13 per-file vectors: names, meaning, and the validation record

**Status: current.** [gitgalaxy#2991](https://github.com/squid-protocol/gitgalaxy/issues/2991)
resolved via **Option A**: the 13 per-file vectors are renamed to the descriptive
vocabulary below; the legacy `risk_*` names are kept as **deprecated aliases** for
schema compatibility (see [Deprecation](#deprecation) below). This document describes
what each vector measures, cites the evidence behind that description, and gives the
old-name -> new-name mapping. It is the reference `README.md` links to for vector-level
detail. [gitgalaxy#2994](https://github.com/squid-protocol/gitgalaxy/issues/2994) adds a
second, additive measurement system on top of these 13 vectors — see
[The tier model](#the-tier-model) below.

## Why this document exists

The engine persists 13 per-file vectors. Until this rename they were each named
`risk_<metric>` (`risk_concurrency`, `risk_cognitive_load`, `risk_api_exposure`, …). The
`risk_` prefix asserted something specific: that a higher value means a higher
probability of a defect or vulnerability in that file. The temporal-crucible validation
program — epic [gitgalaxy#2982](https://github.com/squid-protocol/gitgalaxy/issues/2982),
~3,550 scanned snapshots across two repositories (curl, nDPI) and three label families,
every test pre-registered before the data was looked at — tested that claim to
exhaustion. The disposition is recorded in
[gitgalaxy#2991](https://github.com/squid-protocol/gitgalaxy/issues/2991) and its
[per-vector disposition table](https://github.com/squid-protocol/gitgalaxy/issues/2991#issuecomment-5653971650),
which this document follows vector by vector. The rename itself was driven by the
disposition table; the mechanical audit of every calculator's formula is in
[`vector_formulas.md`](vector_formulas.md) (sibling document).

**The one-paragraph honest summary.** Across two repositories and three label families, two
predictors survived: recidivism (the file that had the last fix gets the next one — the
strongest, most replicated result of the program, p<1e-4 on both repos) and change entropy /
Hassan HCM (`HCM1_LD_30`, validated on fresh bug labels after being selected on CVE labels:
AUC 0.868 vs a line count's 0.830). Both are **history** metrics. Everything structural —
keyword counts, danger vocabulary, complexity, per-file totals, pooled, density-normalized,
length-matched, or banded — reduced to file size; the nulls are equivalence-confirmed, not
just non-significant, on two independent repositories
(temporal-crucible `docs/HYPOTHESES.md`, "the plain-language summary" and point 2). What
*did* validate is that the vectors reliably characterize **what a change did**: the fix-shaped
composite tracks a security-fix → ordinary-fix → control → revert gradient cleanly, and
per-vector deltas correspond to real code events (guard code added, threading introduced,
debt markers diluted). That is a real, useful, differentiated capability. It measures activity
and surface, not defect probability — hence the rename below.

## The name table

| new name | legacy alias (`risk_*`) | disposition |
|---|---|---|
| `complexity_load` | `risk_cognitive_load` | KEEP-DESCRIPTIVE |
| `guard_balance` | `risk_safety_score` | KEEP-DESCRIPTIVE |
| `debt_markers` | `risk_tech_debt` | REWORK-flagged (formula artifact, #2984) |
| `test_surface` | `risk_verification` | KEEP-DESCRIPTIVE |
| `connectivity` | `risk_api_exposure` | KEEP-DESCRIPTIVE (conditional PROMOTE candidate) |
| `concurrency_surface` | `risk_concurrency` | KEEP-DESCRIPTIVE |
| `mutation_surface` | `risk_state_flux` | KEEP-DESCRIPTIVE (size-proxy caveat) |
| `dead_code_surface` | `risk_dead_code` | KEEP-DESCRIPTIVE |
| `spec_alignment` | `risk_spec_match` | KEEP-DESCRIPTIVE |
| `hist_stability` | `risk_stability` | PROMOTE (predictive layer, pending) |
| `hist_churn` | `risk_churn` | PROMOTE (predictive layer, pending) |
| `doc_surface` | `risk_documentation` | KEEP-DESCRIPTIVE |
| `credential_material` | `risk_secrets_risk` | REWORK-flagged (formula artifact, #2979) |

Umbrella term: "Risk Exposure" is now **"Structural Surface Profile"** in report/brief
headings and UI labels (with "(formerly Risk Exposure)" noted on first use per surface).
This document, `README.md`, `gitgalaxy/metrics/README.md`, and the visualizer at
`site/` have been updated to the new vocabulary; the underlying DB columns and JSON keys
remain `risk_*` unconditionally — see [Deprecation](#deprecation).

## The descriptive / predictive split

The validation record supports splitting the product's claim into two layers with different
epistemic status:

- **The descriptive layer** (this document, 11 of the 13 vectors below): per-file
  *structural surface and content* meters — how much of a given vocabulary or construct is
  present in the file as it currently stands. These are an x-ray: they tell you what is
  there. The record shows they do **not** tell you where a defect is more likely to be. They
  remain useful for what they actually do — annotation, retrieval, review routing by kind of
  content, and characterizing what a change did to a file.

- **The predictive layer** (2 of the 13 vectors, `hist_stability` and `hist_churn` — plus
  recidivism and change-entropy features not yet exposed as scored vectors at all): the
  **history** family. This is the layer the record actually validated as carrying defect-lift
  beyond size. It is presently inert: every scan runs with `GITGALAXY_DISABLE_GIT_HISTORY`
  set, so `hist_stability` and `hist_churn` are ablated to zero in every recorded scan today
  ([temporal-crucible#29](https://github.com/squid-protocol/temporal-crucible/issues/29),
  "Engine gap: process features are ablated to zero in every scan"). The `hist_` prefix
  marks this family as **promoted pending** temporal-crucible#29's history-enabled mode
  shipping, and then passing the defect-lift gate defined in
  [gitgalaxy#2987](https://github.com/squid-protocol/gitgalaxy/issues/2987) ("a signal earns
  entry to a gated formula by demonstrated defect-lift beyond size"). Until both land, treat
  a currently-recorded `hist_stability`/`hist_churn` (or `risk_stability`/`risk_churn`) value
  as carrying no signal at all, in either direction.

The 13 vectors below are grouped by their disposition-table verdict: **KEEP-DESCRIPTIVE**
(11 vectors — this is the bulk of the schema, described here as activity/surface
meters under their new names), and **PROMOTE** (`hist_stability`, `hist_churn` — flagged
here for completeness, but they are explicitly *not* descriptive; they are the history
family awaiting the predictive-layer path above). None of the 13 is deleted or hidden by
this document; `debt_markers` and `credential_material` carry a REWORK flag noted in their
sections below — known formula artifacts, not yet fixed. The rename does not imply the
formula artifact is fixed.

---

## `complexity_load` (formerly `risk_cognitive_load`)

**(1) What it measures.** Complexity- and size-adjacent structure: how much branching,
nesting, and declaration surface a file's extracted units carry, as a share the engine reads
as "load" on a reader.

**(2) What the record established.** `complexity_load` tracks file size in every setting it
was tested in (disposition table). It appears together with `dead_code_surface` in the
event-class delta tables as a vector that *rises* after a fix because guard code added by a
repair reads as added complexity, not because complexity marks a vulnerability
(`exposure_history_report.md`: "guard code added by a fix reads as complexity (dead_code,
cognitive_load)"). It is one of the signals inside the 26/27-feature structural vector whose
temporal-split, out-of-selection AUC (0.479) came in *below* net-LOC alone (0.531) — both at
chance (`class_signals.md`, "Collapsed binary: fix-like vs control").

**(3) Explicit non-claims.** This value is not a defect-probability estimate. Per-file
standing levels of the structural family this vector belongs to were shown to track file
size, with the corresponding nulls equivalence-confirmed on a second, independent repository
(nDPI Stage-2 TOST: effect 0.000, CI ⊂ ±0.10 — `docs/HYPOTHESES.md`, "Stage-2 … equivalence
CIs"). A rise in `complexity_load` after a change does not indicate the change made the file
more dangerous.

**(4) Appropriate vs inappropriate uses.** Appropriate: flagging structurally dense files for
a readability or refactor conversation; annotating "this change added branching/nesting";
retrieval of high-complexity files for triage queues unrelated to security. Inappropriate:
ranking files by `complexity_load` as a proxy for defect likelihood, or reading a post-fix
rise as evidence the fix made things worse.

---

## `guard_balance` (formerly `risk_safety_score`)

**(1) What it measures.** The net balance of guard constructs against danger constructs in a
file — a credit/debit composite, not a density.

**(2) What the record established.** This is the one vector in the whole schema that moved in
its pre-registered direction after a security fix on curl (H3: p=0.0072) — a genuine,
event-grounded positive, and the strongest single piece of evidence that the engine's
vocabulary carries real security semantics at the delta level. It did **not** replicate on
the second repository: in the nDPI cross-repo battery, every structural signature including
`guard_balance` failed to replicate (`docs/HYPOTHESES.md`, "Scope of validation to date"). The
mechanism is documented as being about formula *shape*: `guard_balance` is a net over
unlike-signed inputs, which is why it moved at all, while every density-shaped vector stayed
flat or produced an artifact (`docs/HYPOTHESES.md`, "What one repo taught us", point 2).

**(3) Explicit non-claims.** This value is not a defect-probability estimate. It is a
single-repository positive that did not survive cross-repo replication; it should not be read
as a validated predictor of anything. It describes the *composition* of a file's guard/danger
vocabulary balance, nothing more.

**(4) Appropriate vs inappropriate uses.** Appropriate: characterizing whether a change added
more guards than danger constructs (change characterization); annotating commit "shape" for a
changelog or review summary. Inappropriate: using the current `guard_balance` level to declare
a file low- or high-risk, given the replication failure.

---

## `debt_markers` (formerly `risk_tech_debt`) — REWORK flagged

**(1) What it measures, as currently formulated.** A density of debt-marker annotations
(explicit TODO/FIXME-style admissions and related tags) over the file's own denominator.

**(2) What the record established.** The H3 "signal" originally read as `debt_markers`
*dropping* after a fix (p=0.0011) is a formula artifact, not a real reduction in debt: fixes
almost never touch a debt marker, so the drop is the *density denominator* moving (fixes net-
add lines, which dilutes any per-line ratio) — diagnosed and traced to
[gitgalaxy#2984](https://github.com/squid-protocol/gitgalaxy/issues/2984) and
[gitgalaxy#2979](https://github.com/squid-protocol/gitgalaxy/issues/2979) (`ndpi_exposure_report.md`:
"the H3 tech_debt drop in fixes coexists with fixes almost never touching a debt marker — the
drop is the DENSITY DENOMINATOR"). The disposition table's verdict for this vector is
**REWORK** (count-based, not density) or delete — it is the one vector this document cannot
respecify as a clean surface meter as currently formulated. Renaming it to `debt_markers`
does not fix this artifact; the formula rework is separate, tracked work.

**(3) Explicit non-claims.** This value is not a defect-probability estimate, and — beyond the
general caveat — its current formula has a known artifact: it moves mechanically with net-LOC
dilution, independent of whether debt was actually added or removed. A change should not be
read as "reducing debt" because `debt_markers` fell.

**(4) Appropriate vs inappropriate uses.** Appropriate: reading the raw debt-marker count
(not the current density score) as a presence flag, pending the rework. Inappropriate: any
trend or ranking use of the density value as currently computed — including "this PR paid
down debt" or "this file is worse than that one" comparisons.

---

## `doc_surface` (formerly `risk_documentation`)

**(1) What it measures.** Per the engine's own formal score contract
(`docs/risk_documentation_contract.md`, gitgalaxy#2908): of the units extracted from a file,
the weight-share a reader cannot recover from documentation — a coverage-gap ratio over
extracted units (functions, methods, paragraphs, steps), not a density over lines.

**(2) What the record established.** `doc_surface` sits in the disposition table's
presence-meter group (with `dead_code_surface`, `spec_alignment`): untested-or-null as a
predictor, no artifacts found. Its event-class deltas are flat and unremarkable across both
repositories (`exposure_history_report.md` p=0.83; `ndpi_exposure_report.md` p=0.30) — it
simply does not move much around fix events, consistent with documentation coverage being a
slow-moving property of a file rather than something a single change alters.

**(3) Explicit non-claims.** This value is not a defect-probability estimate. It has not been
tested as a predictor of anything beyond documentation coverage itself; its near-flat
behavior around fix events is a null, not evidence either way about risk.

**(4) Appropriate vs inappropriate uses.** Appropriate: flagging under-documented files for
onboarding or review-routing purposes; annotation and retrieval by documentation coverage.
Inappropriate: ranking files by `doc_surface` as a defect-probability signal.

---

## `test_surface` (formerly `risk_verification`)

**(1) What it measures.** Test-adjacent surface: how much of the file's content engages a
testing framework — assertions, fixtures, framework references.

**(2) What the record established.** Disposition: KEEP-DESCRIPTIVE, with a flagged open
question. `test_surface` is the near-universal micro-leak term seen in the spillover audit —
untouched files show tiny nonzero deltas on this vector at noise level (≤0.0013), which the
record notes as something to investigate as a shared/leaking term in the extraction pipeline,
not as evidence of any predictive property
(`exposure_history_report.md`/`ndpi_exposure_report.md`, spillover section).

**(3) Explicit non-claims.** This value is not a defect-probability estimate. It has not been
shown to carry information beyond describing test-adjacent surface, and its very small
cross-file leakage is a measurement-quality note, not a risk signal.

**(4) Appropriate vs inappropriate uses.** Appropriate: annotating test-engagement surface;
retrieval of files with low test-adjacent surface for coverage-improvement queues.
Inappropriate: risk ranking by this vector.

---

## `connectivity` (formerly `risk_api_exposure`)

**(1) What it measures.** Connectivity and centrality: how much other code depends on or
imports this file, and related graph-position inputs (popularity/in-degree, PageRank-style
centrality).

**(2) What the record established.** This is the only vector in the schema carrying a live,
still-open predictive candidate. With proper statistical power (28/42 positives, bug-label
expansion), small-file centrality is dead — PageRank in ≤22-line files is actually *inverted*
(AUC 0.259) — but the shape is a genuine inverted U: centrality carries real lift specifically
in **mid-size files** (49–108 LOC: PageRank lift +0.145, lower bound +0.020; popularity lift
+0.132, lower bound +0.025 — `docs/bh_eval.md`, B-H1/B-H2 results, cited in
`docs/HYPOTHESES.md` point 4). This candidate is **registered for repo #3 (openssl), not yet
validated or claimed** as a general result.

**(3) Explicit non-claims.** This value is not currently a validated defect-probability
estimate. The mid-band centrality candidate is a pre-registered hypothesis awaiting a third,
independent repository — it has not cleared that bar yet. Do not treat current
`connectivity` values as validated risk indicators ahead of that result.

**(4) Appropriate vs inappropriate uses.** Appropriate today: surfacing structurally central
or heavily-depended-upon files for change-impact assessment and blast-radius annotation;
retrieval by connectivity. Not yet appropriate: prioritizing security review by
`connectivity` score as if the predictive candidate were confirmed — it is registered, not
validated.

---

## `concurrency_surface` (formerly `risk_concurrency`)

**(1) What it measures.** Concurrency surface: how much asynchronous or parallel-execution
vocabulary (threading, async constructs) is present in the file.

**(2) What the record established.** The clearest illustration in the whole program of what
this family of vectors actually does. CURL-CVE-2026-11586 produced the largest single rise in
the dataset (+47.1 per-event mean). The audit traced it: the CVE fix itself
(`lib/ws.c`) moved only +0.78; the rest of the swing was a companion test file
(`tests/http/test_20_websockets.py`) where `concurrency_surface` went from 0 to 87.26 because
the test added a new `threading` harness (`exposure_history_report.md`, footnote on the largest
rise; `docs/instrument_controls_forensics.md`). The meter worked exactly as built — threading
appeared in the file, the meter moved. The only miscalibration was the name: "risk" implied a
vulnerability signal; what actually happened was ordinary test infrastructure being added.

**(3) Explicit non-claims.** This value is not a defect-probability estimate. A large
`concurrency_surface` delta indicates that threading-related vocabulary changed in a file —
full stop. It does not indicate elevated defect risk, and the specimen above is the concrete
demonstration of that gap.

**(4) Appropriate vs inappropriate uses.** Appropriate: annotating "this change introduced or
touched threading logic"; retrieval of files with concurrency surface for domain-expert
review routing (e.g., routing to a reviewer with threading experience because the *content*
warrants it, not because the score implies danger); change characterization. Inappropriate:
ranking files by `concurrency_surface` as a proxy for how risky the file is.

---

## `dead_code_surface` (formerly `risk_dead_code`)

**(1) What it measures.** A presence meter for commented-out structural code and unused logic
trails, read from the comment stream.

**(2) What the record established.** Disposition table: presence meter, untested-or-null as a
predictor, no artifacts found. It shares the same "guard code reads as complexity" dynamic
noted for `complexity_load` — both move together in the H1 delta tables around fix events,
consistent with ordinary code churn rather than any defect signal
(`exposure_history_report.md`).

**(3) Explicit non-claims.** This value is not a defect-probability estimate. It has not been
tested as a predictor at all; absence of a finding here is absence of evidence, not evidence
of a validated risk signal.

**(4) Appropriate vs inappropriate uses.** Appropriate: flagging files with dead-code presence
for cleanup backlogs; annotation and retrieval. Inappropriate: any risk-ranking use.

---

## `spec_alignment` (formerly `risk_spec_match`)

**(1) What it measures.** A presence meter for audit/traceability tags establishing a link
between code and its intended specification.

**(2) What the record established.** Grouped in the disposition table with `dead_code_surface`
and `doc_surface` as an untested-or-null presence meter — no predictive claim was tested, and
none is implied by the record. In practice this signal is sparse enough that some cross-repo
correlation computations return `nan` for it (`ndpi_exposure_report.md`), reflecting how
rarely the underlying tag vocabulary appears rather than any property of risk.

**(3) Explicit non-claims.** This value is not a defect-probability estimate. It has not been
evaluated as a predictor of anything; its rarity in most codebases limits how much can be said
about it either way.

**(4) Appropriate vs inappropriate uses.** Appropriate: traceability annotation, retrieval of
files carrying (or lacking) spec/audit tags. Inappropriate: risk ranking.

---

## `mutation_surface` (formerly `risk_state_flux`)

**(1) What it measures.** A mutation-density surface — how much state-writing activity
(assignments into existing state) is present in the file, as currently formulated a largely
commit-size-shaped signal.

**(2) What the record established.** `mutation_surface` is a member of a size-proxy
co-movement cluster identified in the keyword-pool exploration: its summed delta correlates
with net-LOC at ρ=+0.66, above the program's own |ρ|≥0.5 threshold for flagging a signal as a
size proxy rather than something moving independently of size
(`docs/keyword_pools_explore.md`, "cluster 1 {state_flux, struct_snake_case, struct_var_decl}
… SIZE PROXY"). The disposition table's verdict is KEEP with an explicit size caveat, or
demote.

**(3) Explicit non-claims.** This value is not a defect-probability estimate, and it has been
specifically shown to move largely in step with file/commit size (ρ=+0.66) rather than
carrying information beyond it.

**(4) Appropriate vs inappropriate uses.** Appropriate: characterizing the state-mutation
surface/activity level of a file or change, with the size relationship stated alongside it.
Inappropriate: treating an elevated `mutation_surface` value as elevated risk, given its
documented size-proxy behavior.

---

## `credential_material` (formerly `risk_secrets_risk`) — REWORK flagged

**(1) What it measures, as currently formulated.** A density-based flag intended to surface
credential-shaped material (passwords, tokens, keys) written into the file.

**(2) What the record established.** Two independent problems, both traced:
a density-artifact correlation with file size (`ρ=−0.91` vs LOC,
[gitgalaxy#2979](https://github.com/squid-protocol/gitgalaxy/issues/2979)), and a surface
that is demonstrably orthogonal to the vulnerability surface it might be assumed to relate
to. The credential shunt underlying this vector fires almost entirely on test keys and CA
tooling — on curl, 6 of 392 CVE/control-implicated files (`exposure_history_report.md`); on
nDPI, 0 of 197 (`ndpi_exposure_report.md`). "CVEs live in protocol code, credentials in test
fixtures," as the record puts it. Disposition: **REWORK** to a plain count-based "credential
material present" flag — which is also why this vector's new name is `credential_material`
rather than a surface/density-implying name.

**(3) Explicit non-claims.** This value is not a defect-probability estimate, and — beyond the
general caveat — it is not currently a useful security-risk indicator at all: it is strongly
size-correlated as formulated, and it has been shown twice, on two repositories, to fire on
files that are not where vulnerabilities actually live.

**(4) Appropriate vs inappropriate uses.** Appropriate: as a raw presence flag for "does this
file contain credential-shaped strings" (secrets-scanning triage, pending the rework).
Inappropriate: using the current score as a vulnerability or risk indicator of any kind.

---

## `hist_stability` and `hist_churn` (formerly `risk_stability`, `risk_churn`) — PROMOTE, not descriptive

These two vectors are not re-documented as descriptive surface meters, and that is the
point of separating them out here. The disposition table's verdict for both is **PROMOTE** —
they are the process/history family, and they are the one part of the schema the validation
record actually supports as predictive. The `hist_` prefix (rather than a surface-style name)
marks that status explicitly: this family is **promoted pending**
[gitgalaxy#2987](https://github.com/squid-protocol/gitgalaxy/issues/2987)'s calibration
contract and [temporal-crucible#29](https://github.com/squid-protocol/temporal-crucible/issues/29)'s
history-enabled mode, not already a shipped predictive layer.

- **Churn** (change frequency) is the strongest single structural-adjacent feature measured
  anywhere in the program pooled (AUC 0.859), on par with a raw line count
  (`docs/incremental_value.md`, `docs/centrality_bands.md`).
- **Recidivism** (prior-fix count — closely related to this family, though not itself one of
  the 13 scored vectors today) is the single most replicated result of the whole program:
  decisive on both repositories, p<1e-4 (`docs/HYPOTHESES.md`, RW-H2).
- **Change entropy / Hassan HCM** (`HCM1_LD_30`) is the only *feature* in the entire program
  to beat a line count out-of-selection: selected on CVE labels, then validated frozen on
  fresh bug labels at AUC 0.868 vs LOC's 0.830 (lift +0.038, lower bound +0.021 —
  `docs/bh_eval.md`, B-H3).

**What this means for the current columns.** As shipped today, `hist_stability` and
`hist_churn` (persisted as `risk_stability`/`risk_churn`) are computed with
`GITGALAXY_DISABLE_GIT_HISTORY` set in every scan, so both are **ablated to zero on every
recorded row** — they currently carry no signal at all, predictive or descriptive
([temporal-crucible#29](https://github.com/squid-protocol/temporal-crucible/issues/29)). Do
not read a currently-recorded `hist_stability` or `hist_churn` value as meaningful, in either
direction, until history-enabled mode ships and the resulting metric clears
[gitgalaxy#2987](https://github.com/squid-protocol/gitgalaxy/issues/2987)'s defect-lift gate.
At that point these (or their promoted successors, alongside `change_entropy`/HCM and
`ownership_entropy`) become the predictive layer described in the preamble — a different
product claim, with a different evidentiary bar, from the 11 descriptive vectors above.

---

## Deprecation

The `risk_*` names (`risk_cognitive_load`, `risk_safety_score`, `risk_tech_debt`,
`risk_verification`, `risk_api_exposure`, `risk_concurrency`, `risk_state_flux`,
`risk_dead_code`, `risk_spec_match`, `risk_stability`, `risk_churn`, `risk_documentation`,
`risk_secrets_risk`) are **deprecated aliases**, retained for schema compatibility:

- They remain the actual DB column names in every persisted SQLite schema
  (`record_keeper.py`'s `file_data` table, `docs/self_scan/gitgalaxy_master.db`) and the
  actual JSON keys in every recorded artifact (`risk_vector`, `RISK_SCHEMA`-ordered
  payloads, SARIF output). No consumer reading `risk_*` — including temporal-crucible's
  queries, crucible bless baselines, and SARIF tooling — needs to change anything.
- The new names in the table above are the vocabulary used in human-facing surfaces going
  forward: report/brief headings and labels (the LLM architectural brief, the audit/GPU
  visualizer UI), this document, and the project README.
- **Removal is not scheduled.** There is no deadline on the `risk_*` aliases; they are not
  planned for deletion. New integrations should use the new names from the table above;
  existing integrations reading `risk_*` columns/keys require no changes.
- The canonical mapping lives in code as `VECTOR_NAMES` in
  [`gitgalaxy/standards/analysis_lens.py`](../gitgalaxy/standards/analysis_lens.py), next to
  `RISK_SCHEMA`.

## The tier model

**Status: current.** [gitgalaxy#2994](https://github.com/squid-protocol/gitgalaxy/issues/2994)
is the successor to this document's rename (#2993/#2991): where the rename made the
*claims* honest, #2994 makes the **arithmetic** honest. The formula audit behind the rename
established that 11 of the 13 vectors above are density formulas — the empirically convicted
shape (`vector_formulas.md`, [gitgalaxy#2984](https://github.com/squid-protocol/gitgalaxy/issues/2984)/
[gitgalaxy#2979](https://github.com/squid-protocol/gitgalaxy/issues/2979)) — squashed through
sigmoids carrying ~40 uncalibrated tuned constants (thresholds, slopes, breach floors, path
multipliers) that assert a 0–100 calibration nobody has ever validated against anything. #2994
adds a second, additive measurement system that sidesteps the calibration problem entirely
instead of trying to re-tune it.

**The bargain is identical to the rename's:** every `risk_*` column above keeps emitting
byte-identical values from the frozen legacy formulas — golden masters, bless baselines,
temporal-crucible's longitudinal DBs, and `supply_chain_firewall`'s 50.0-cutoff are all
unaffected (see [Deprecation](#deprecation) and the firewall note below). The tiers below are
new columns, new telemetry keys, and a new LLM-brief section — nothing is removed or
recalculated in place.

| tier | content | transform | constants |
|---|---|---|---|
| 0 | raw signal counts (the validated x-ray; existing `struct_/state_/arch_/def_` columns) | none — canonical | 0 |
| 1 | **families** — `SURFACE_FAMILIES`, a declarative `{family: [signal, ...]}` map, 22 families over the signal space; per-file value = raw sum of member counts | none | 0 |
| 2 | **snapshot percentiles** — the honest 0–100: "87" means *87th percentile of this surface in this repo*, true by construction | rank (Hazen) | 0 |
| 3 | **relations** — count÷count ratios with mechanism stories | ratio | 0 |

Sigmoid-87 (a `risk_*` value) asserts a threshold/saturation curve nobody calibrated;
percentile-87 (a `pct_fam_*`/`pct_vec_*` value) is a rank statement that cannot be wrong by
construction — it just restates where this file sits among the files actually scanned. Count÷
LOC density, the shape behind the `debt_markers`/`credential_material` REWORK flags above, is
retired from measurement entirely in the tier model; no new tier is density-shaped.

### Tier 1 — `SURFACE_FAMILIES`

`SURFACE_FAMILIES` (in [`gitgalaxy/standards/analysis_lens.py`](../gitgalaxy/standards/analysis_lens.py),
next to `SIGNAL_SCHEMA`) groups 63 of `SIGNAL_SCHEMA`'s 95 raw-signal names into 22 families:
`memory`, `cleanup`, `guards`, `danger`, `concurrency`, `connectivity`, `io`, `crypto`, `ipc`,
`time`, `serialization`, `regex`, `events`, `tests`, `docs`, `debt`, `mutation`, `dead_code`,
`credential`, `threat`, `ml_ai`, `ui`. A file's per-family value is a plain **integer sum** of
its member signals' raw counts — no formula, no constant, no sigmoid.

The remaining 32 names are declared exempt in `SURFACE_FAMILY_EXEMPT` (same file), each with a
one-line reason, in four groups: structural-shape signals that are substrate for complexity
rather than a measurement surface in their own right (11: `branch`, `structural_boundaries`,
`args`, `func_start`, `class_start`, `globals`, `decorators`, `import`,
`dependency_injection`, `macros`, `bitwise_ops`); cosmetic style/naming signals (8: the
`design_*_case`/`design_*_vars` family plus `indent_tabs`/`indent_spaces`); the single
`ownership` signal (its own concern, not a surface); paradigm markers (3: `closures`,
`generics`, `comprehensions`); `sec_*` lens duplicates of a signal already summed under its
non-`sec_` counterpart's family, which would double-count if also included (7); and two
permanent always-zero placeholders kept only for `SIGNAL_SCHEMA`'s positional stability
(`prompt_injection`, `agentic_rce` — see the comment at their definition site). Every
`SIGNAL_SCHEMA` name is in exactly one family XOR exempt — enforced by
`tests/core_engine/test_surface_families_contract.py`, the arbiter of the map, not this
document.

**Raw-truth semantics (the suppression contract).** Families sum `raw_signals` — the counts
the detector actually recorded — never the mitigation-suppressed `exposure_vector` that the
`risk_*` sigmoids above are computed from. An inline `galaxyscope:ignore` that zeroes a file's
`risk_safety_score` to 0.0 does **not** zero its `guards` family total: the family keeps
reporting what is actually in the file, independent of whatever the legacy display layer was
told to suppress. This is deliberate, not an oversight — families are "raw truth by
construction," a different epistemic claim from the legacy vectors' suppressible display
value. See the suppression-interplay test in `tests/core_engine/test_signal_processor.py`.

### Tier 2 — snapshot percentiles

`SignalProcessor._compute_snapshot_percentiles`, called in `summarize_galaxy_metrics`
immediately after `_normalize_temporal_metrics` (ordering is load-bearing — Pass 2 rewrites
`risk_vector`'s churn slot in place, so percentiles must rank the post-normalization value, not
the raw pre-normalization one; see the churn-ordering test), ranks 35 series per repo snapshot:
the 22 Tier-1 family sums and the 13 `RISK_SCHEMA` legacy-vector values (read-only — the
legacy values themselves are never modified by this pass).

The formula is the **Hazen plotting position**: `pct = (avg_rank − 0.5) / N × 100`, rounded to
2 decimal places, where ties share the mean of the ranks they would occupy. Two special cases:

- **All-zero series → 0.0 for every file.** If no file in the snapshot has a given surface at
  all, a naive average-rank computation would still assign every (tied) file the 50th
  percentile — misrepresenting "nobody has this signal in this repo" as "the median file has
  it." The all-zero override reads 0.0 instead, so an absent surface never looks like a
  median one.
- **N=1 → 50.0 for every series.** A single-file snapshot has nothing to rank against;
  "true middle" is the only honest value, for both a family with signal and one entirely
  absent.

Written to `telemetry["surface_percentiles"] = {"fam": {<family>: pct, ...}, "vec": {<slug>:
pct, ...}}` on every parsed file — never on the `summarize_galaxy_metrics` return dict, which
feeds the golden-mastered audit JSON (see [Golden-master constraint](#golden-master-constraint)
below).

**Firewall migration note.** `gitgalaxy/security/supply_chain_firewall.py` hardcodes a
50.0-cutoff against the legacy 0–100 sigmoid scores (`risk_*`). That cutoff is unaffected by
this reform — the firewall keeps reading frozen legacy values, unconditionally. A future
migration of the firewall's threshold semantics from "sigmoid ≥ 50.0" to "percentile ≥ some
cutoff" is a natural follow-up once the tier model has field experience, but it is **not**
part of #2994 and no code changes here. Anyone undertaking that migration should note the
50.0 in the firewall today is a sigmoid-calibration artifact, not a percentile — the two
"50"s mean genuinely different things (one is an uncalibrated curve's midpoint, the other is
the honest statement "half the repo is at or below this").

### Tier 3 — relations

Two count÷count ratios, each with a mechanism story, computed alongside the Tier-1 sums in
`calculate_risk_vector`:

- **`guard_balance_ratio`** = `guards / (danger + 1)` — defensive constructs per unit of
  danger surface. The `+1` denominator means a danger-free file (the common case) never
  divides by zero or spikes to an unbounded value.
- **`alloc_cleanup_pairing`** = `cleanup / (memory + 1)` — cleanup (free/close/dispose)
  constructs per unit of manual-allocation surface; this is the X-H1 feature from the
  temporal-crucible validation record, now exposed directly instead of folded into a sigmoid.

Written to `telemetry["surface_relations"]` on every parsed file. Like the families they're
built from, relations read `raw_signals` — the same raw-truth semantics apply.

### Where tiers surface

Additive only, nowhere replacing a golden-mastered value:

- Per-file: `telemetry["surface_families"]`, `telemetry["surface_relations"]` (both written in
  `calculate_risk_vector`), `telemetry["surface_percentiles"]` (written in
  `summarize_galaxy_metrics`, Tier 2).
- SQLite (`record_keeper.py`, `file_data` table): 22 `fam_<name>` INTEGER, 22
  `pct_fam_<name>` REAL, 13 `pct_vec_<risk-slug>` REAL, and `rel_guard_balance` /
  `rel_alloc_cleanup` REAL — 59 new columns, generated dynamically from `SURFACE_FAMILIES`/
  `RISK_SCHEMA` the same way the existing `risk_*`/hit-vector columns already are. A guarded
  `ALTER TABLE ADD COLUMN` heal (`_ensure_columns`) brings pre-#2994 databases up to date on
  the next write; `folder_data` is untouched.
- LLM brief: section "6b. SURFACE FAMILY PROFILE," directly below the legacy section 6
  sigmoid table — per-family repo total, files-with-signal count, p90 file value, and top
  file, plus the two relations as repo medians. Display-only, not golden-mastered.

### Golden-master constraint

`audit_recorder`'s output is hashed whole by the golden-master corpus — any new key breaks
every master. The tier model therefore changes `audit_recorder`'s output **not at all**: no
new key is added to its sanitized JSON, and `pytest -m golden_crucible` passing with masters
**untouched** (not regenerated) is the enforced proof that this reform is byte-identical to
legacy on every value the corpus hashes. Tiers surface only through the three channels listed
above — telemetry keys, DB columns, and the LLM brief — none of which the golden-master
corpus reads.

## Appendix

- [`vector_formulas.md`](vector_formulas.md) — the mechanical, per-calculator formula audit
  (inputs, arithmetic, constants, line references) extracted from
  `gitgalaxy/metrics/signal_processor.py`, referenced throughout this document.
- `SURFACE_FAMILIES` / `SURFACE_FAMILY_EXEMPT` in
  [`gitgalaxy/standards/analysis_lens.py`](../gitgalaxy/standards/analysis_lens.py) — the
  Tier-1 family map and its exemption ledger described above.
- `tests/core_engine/test_surface_families_contract.py` — the enforced contract (every
  `SIGNAL_SCHEMA` name in exactly one family XOR exempt; no column-name collisions) that is
  the arbiter of the family map, not this document.

## References

- [gitgalaxy#2994](https://github.com/squid-protocol/gitgalaxy/issues/2994) — the
  measurement-tier reform ([The tier model](#the-tier-model) above): `SURFACE_FAMILIES`,
  snapshot percentiles, count relations, additive and legacy-frozen. Successor to #2991;
  supersedes #2984/#2979 (frozen-deprecated rather than reworked).
- [gitgalaxy#2991](https://github.com/squid-protocol/gitgalaxy/issues/2991) — the naming/
  reframe issue this document implements (Option A), its disposition-table comment, and its
  formula-facts comment
- [gitgalaxy#2982](https://github.com/squid-protocol/gitgalaxy/issues/2982) — the validation
  epic (Rung 6)
- [gitgalaxy#2987](https://github.com/squid-protocol/gitgalaxy/issues/2987) — the calibration/
  promotion contract gating the predictive layer
- [temporal-crucible#29](https://github.com/squid-protocol/temporal-crucible/issues/29) — the
  history-enabled forward-prediction mode this predictive layer depends on
- [gitgalaxy#2984](https://github.com/squid-protocol/gitgalaxy/issues/2984),
  [gitgalaxy#2979](https://github.com/squid-protocol/gitgalaxy/issues/2979) — the density-
  denominator artifacts behind the `debt_markers` and `credential_material` REWORK flags
- `temporal-crucible/docs/HYPOTHESES.md` — the full hypothesis ledger and plain-language
  summary this document draws its evidence from
- `temporal-crucible/docs/{exposure_history_report,ndpi_exposure_report,
  instrument_controls_forensics,bh_eval,centrality_bands,class_signals,
  specificity_curl_heldout,specificity_density_explore,keyword_pools_explore,
  incremental_value}.md` — the individual reports cited above

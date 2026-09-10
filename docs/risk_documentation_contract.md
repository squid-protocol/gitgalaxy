# The `risk_documentation` score contract (#2908)

> **`risk_documentation` is the share of a file's extracted units — functions, methods,
> paragraphs, steps — whose meaning a reader cannot recover from documentation, weighted so
> that a public unit counts double and a unit doing runtime-decided work counts more. It is a
> ratio over units, never a density over lines. A file with no extracted units has no value.**

**Status: `draft`** — D1–D6 approved on #2908 (2026-09-09); Phase 3 landed the §1 equation in
`signal_processor.py`, so §2 now describes the *retired* density formula, kept as the record of
why it was replaced. This document flips to `stated` when Phase 4 re-blesses the corpus.

This is the first **score** contract (roadmap Phase 4, `docs/contract_roadmap.md` §4). The count
contracts it builds on: `docs/api_rule_contract.md` (#2730, the public surface),
`docs/unreferenced_by_name_contract.md` (#2806, the orphan census), and the `doc` row of
`gitgalaxy/standards/signal_contracts.py`. The audit that keeps §1 honest is
`tests/tools/audit_score_inputs.py documentation` (per-unit since Phase 3; its Phase-0
ancestor `audit_documentation_inputs.py` decomposed the §2 density formula and retired
with it).

## 1. The equation

```
for each extracted unit u:
    weight(u)  = (public_weight if public(u) else 1) + reflection_hits_inside(u)
    exposed(u) = weight(u) if not documented(u) else 0

risk_documentation = 100 × Σ exposed(u) / Σ weight(u) × (1 − umbrella_shield × doc_umbrella)
                   = n/a when Σ weight(u) = 0
```

Tuning: `public_weight` 2.0, `umbrella_shield` 0.5. Nothing else.

Three definitions carry the contract:

- **public(u)** — the unit's name is in the file's *public name set*: names the `api` rule matched
  on the unit's own header ∪ names in an export list (`_visibility_export`,
  `_visibility_export_list`; the #2823 machinery) ∪ units left uncalled in a file that something
  imports (the orphans the Contextual Baseline Fix converts). A **union of names**: a unit cannot
  be public twice, and a name the overlap test misses costs one unit instead of doubling the
  file. This is the per-unit form of #2771 (a per-file declaration count banded against a
  per-function median).
- **documented(u)** — a `doc`-rule match whose span ends inside the unit's *header window*: the
  few lines immediately before `start_line`, or the leading lines of the body (docstring
  position). **Not** the slicer's `docstring` field. That field is a per-language "preceding
  comment" heuristic: on the corpus it captures python's planted `# HACK:` comment as a
  docstring, reads 13 of 13 for jcl, and 0 for fortran, haskell and scheme. Reading it would
  import a fresh language bias into the one score this epic exists to make language-neutral.
- **reflection inside the unit** — #2719's dynamism kept where it belongs. Runtime-decided
  behaviour is what most needs documenting and what a reader cannot recover from the text; it
  raises the weight of *that* unit instead of adding a hit to a file total.

The umbrella is `doc_umbrella` exactly as today (GuideStar folder coverage, README-upgraded in
`galaxyscope.py`): the one file-level defence that survives, because a folder README genuinely
documents every unit in the folder a little.

**Weights are counts, not lengths.** Per-function `impact` is
`(branch + 1) × sqrt(args + 1) + 0.05 × effective_loc` (`detector.py`); weighting units by it
would put length back through the side door. Impact stays the hitlist's ranking key, beside
the score, not inside it.

## 2. What the current formula measures, and why it is replaced

`_calc_documentation` (`signal_processor.py`) is a per-LOC density:

```
defense  = doc + 0.5 × ownership + 0.33 × doc_loc + 50 × doc_umbrella
risk     = opaque_execution + 2 × api            (returns 0 when this is 0)
hits     = risk + reflection_metaprogramming
density  = max(0, hits − defense / 2) / (max(coding_loc, 50) + 20) × 100
score    = 100 / (1 + e^(−0.2 × (density − 10))) × (1 + popularity/10) × silo × mp
```

On the keyword-rosetta corpus every term but one is flat, measured per file by
`audit_documentation_inputs.py` (46 languages, 2026-09-09, engine `81b895cc`; every recorded
score reproduced from its recorded inputs):

- `opaque_execution` needs a function with impact above 50 and no docstring. No corpus function
  has impact above 50. The term is dead on small functions, which is most functions.
- Every corpus file is under the 50-line evidence floor (#2655), so the denominator is the
  constant 70. Length does not enter here — but on a 500-line real file it does, and the same
  three undocumented public functions score ≈15 instead of 40. That is the −0.83 length leak
  the bias report flags for this metric, seen from the other side.
- The popularity multiplier never fires: `meta["popularity"]` is not populated when
  `calculate_risk_vector` runs (#2909). `silo` is 0 and `mp` is 1 on the corpus.
- `doc`, `ownership` and `doc_loc` together move a file by about 2 points.

What remains is a sigmoid over the **adjusted api count**, and that is the whole spread:

| adjusted api per file | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| `risk_documentation` | 0 | 17.9 | 27.9 | 40.6 | 54.8 | 68.2 | 79.2 | 87.1 |

One api hit per file is worth 8 to 14 points on a 0–100 scale. The adjusted count is assembled
from two sources — the language's `api` rule plus the orphan-census credit, minus a
tokenizer-dependent overlap — and every way that assembly can fail lands in its own cluster:

| adjusted api / file | corpus files (a/b/c) | mechanism |
|---|---|---|
| 6 | makefile, m4, scheme, cobol → 77–79 | raw 3 + credit 3: the declared-orphan overlap test never recognises the names (#2827; m4/makefile re-plant owed after #2902) |
| 5 | c (a.c only) → 68 | the `globals` plants match c's api rule as top-level declarations (#2907) |
| 4 | css, agc_assembly, yacc → 55–62 | raw 1 + credit 3; yacc adds 4 reflection hits |
| 3 | the mainstream pack → 38–41; objective-c via credit alone (raw 0) | intended |
| 1 | dockerfile, html, yaml (census n/a), haskell (#2871) → 18 | raw 1, no credit |
| 0 | jcl, sqlite, objective-c main → 0 | the zero-evidence guard |

Four of the scoreboard's eleven open-defect cells and the corpus's one confirmed length leak
are this one formula. The equation in §1 removes each mechanism by construction: a unit is
public or it is not (no double count), the score is a ratio (no length regime), and there is
no sigmoid to turn a ±1 count into ±13 points.

## 3. What leaves the equation, and why

| term | why it goes |
|---|---|
| `doc_loc × 0.33` | a comment-line count is not coverage, and it is one of the two length terms |
| `ownership × 0.5` | *who* maintains a file is a different question, already carried by the silo and authorship views |
| `opaque_execution` | dead on small functions; its intent — load-bearing undocumented code — is what public weighting expresses |
| `/ (_mass_loc(loc) + 20)` and the sigmoid | the length regime; a ratio is already 0–100 |
| popularity and silo multipliers, path modifier `mp` | blast radius sits beside the score in the same report row; a coverage ratio does not change because the file lives in a config folder. The popularity term is dead today anyway (#2909), so its removal is score-neutral |
| `doc_weight` `ownership_weight` `doc_loc_weight` `loc_smoothing` `threshold_base` `sigmoid_slope` | six knobs become two |

## 4. Decisions (to approve on #2908 before Phase 2)

- **D1** The score is a ratio over extracted units; no per-LOC term, no sigmoid, no small-file
  floor. The #2655 floor stays for the density formulas that still need one.
- **D2** `public(u)` is the name-set union in §1. `risk_api_exposure` should read the same set;
  that formula's contract is a separate epic sharing #2908's Phases 1–2.
- **D3** `documented(u)` is the header-anchored `doc` match, not `docstring`. `docstring` is left
  as is (the brief prints it), not deleted.
- **D4** Ownership, doc_loc, opaque_execution, the popularity and silo multipliers and `mp` leave
  the equation. The ledger's `path-and-extension-modifiers` entry drops `risk_documentation`
  from its signal list when this lands.
- **D5** No damping for one-unit files (they read 0 or 100). The directory and repository
  roll-ups are already mass-weighted. Revisit only if Phase 5's real-code check shows hitlist
  noise.
- **D6** The engine keeps emitting a float; `n/a` is inferred by the reporting layer from a unit
  count of 0 — the convention the corpus tooling already uses for rule absence. No `None` in
  the risk vector.

## 5. Expected values (acceptance)

Amended twice by measurement. After Phase 2 (2026-09-10 status on #2908): css is **not** an
n/a language — it extracts public units and reads 100; and mains whose `units_public` reads 0
(agc_assembly, cobol, css, objective-c, yacc — ledgered in
`units-public-main-outside-api-contract`) read the unweighted ratio, the api contract cell
surfaced on purpose. After Phase 3's decomposition (185 files, 0 residuals): the n/a class the
engine actually records is **html, markdown, sqlite** (plus javascript's `package.json`
decoy) — dockerfile, jcl and yaml DO extract units (the slicer's grammar-recognised keyword
constructs and paragraphs/steps, the population #2728/#2792 kept), while sqlite's
`CREATE_Statement` buckets are synthetic slices, which the equation excludes exactly as the
function population does (#2691).

| file | before Phase 3 | after |
|---|---|---|
| rosetta a/b/c, every unit-bearing language (css included) | 17.9 → 79.2 depending on api assembly | **100** (public units, 0 documented) |
| rosetta main, `entry` documented, `entry` in the name set | 33.4 | **75** (weights 2+2+2+2, exposed 6) |
| rosetta main, `entry` documented, NOT in the name set | 33.4 | **86** (6/7 — an `api` contract cell, surfaced on purpose) |
| rosetta main, `units_public` 0 (agc_assembly, cobol, css, objective-c, yacc) | varies | **75** (unweighted 3/4) |
| html, markdown, sqlite a/b/c and main (no non-synthetic units) | 0 → 100 | **n/a** (engine emits 0.0, unit count 0, D6) |
| 500-line file, 10 public units, 2 documented | ≈ 15 | 80 |
| 20-line file, 3 public units, 0 documented | 40.6 | 100 |
| bias report length-leak row | rho −0.83, **leak** | rho 0 by construction |

## 6. Consumers

`risk_documentation` is one of the 13 `risk_*` columns: it feeds the per-file exposure vector,
the cumulative-risk hitlist in the architecture brief (`llm_recorder.py`, "12. Documentation
Risk Exposure"), the SARIF/SQLite recorders, and the corpus's `risk_documentation` gate. The
GuideStar "documentation bypass" (`blanket_risk_vector[... "documentation"] = 0.0`,
`signal_processor.py` ~L450) zeroes it for files a manifest declares documented; that shortcut
is unchanged by this contract.

## 7. Phase map

Phase 0 (this document + the audit tool) → Phase 1 (the name set: #2827, #2871, #2907, the
m4/makefile re-plant) ∥ Phase 2 (per-unit `is_public` / `is_documented` / `reflection_hits`) →
Phase 3 (the equation; golden bless; `rosetta:rebless-owed`) → Phase 4 (corpus re-bless; the
report stops banding this metric within a strictness stratum, which it only did because the
old formula read the fidelity table) → Phase 5 (real-code before/after; D5) → Phase 6 (`stated`).
The full list with done-when lines is on #2908.

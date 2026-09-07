# The `class_start` rule contract (#2856)

> **One hit is the declaration of a named type — a class, struct, record,
> interface, enum or object — or the file's compilation-unit container where
> that container is the language's only named-entity declaration.**

Stated 2026-09-07 by the #2856 audit (roadmap Phase 3, epic #2812), paired with
`docs/func_start_rule_contract.md`. Precedents as listed there. The
machine-readable row is `gitgalaxy/standards/signal_contracts.py`; the
cross-language pins are `tests/extraction/languages/test_structure_contract_2856.py`.

`class_start` is a **declaration**-kind, structure-phase signal. Its consumers:
the `classes_found` structure count is its tally (n/a when the rule is absent,
#2795); `signal_processor` reads it in the `entities` term. The SPEC probe
program is function-only (12 probes + an entry point, no type declarations), so
40 of 46 languages plant `class_start` 0 and the corpus median is 0. Before this
contract it carried 3 of the report's open-defect cells (dockerfile, jcl,
kotlin); after it, **zero** — all three were collective-ledger cross-product
mis-marks over a correct reading, and no rule was changed.

## Why no rule changed, and where the residue goes

Under the sentence above the 39 existing rules already conform. The five
nonzero corpus cells split cleanly:

- **cobol / css / jcl / yaml** — the compilation-unit container (`PROGRAM-ID`,
  a CSS class selector, the `//… JOB` card, `jobs:`). Already categorized
  `scoring` via `container-construct-reads-as-class-start` (engine-semantic).
  **Not touched here** — banding a per-language constant against a zero median
  is the declaration-requirement stratum question, #2796, a scoring-layer
  answer.
- **dockerfile** — `FROM … AS stage` opens a named build stage, the file's
  container, exactly the same morphology one structure-layer down
  (`container-construct-reads-as-class` / #2798). It simply was not yet in the
  `class_start` container entry; this contract adds it.
- **kotlin** — `object` is a singleton **class** declaration; the corpus plants
  two (`object Region {}` / `object Home {}`) because Kotlin has no
  module-level mutable state, so the `globals` plant *must* be an `object`.
  Plant-forced morphology (#2796's reading), re-dispositioned from
  keyword-overlap to intended-morphology.

## Corollaries

**C1 · A named type, in whatever form the language spells it.** class, struct,
union, enum, record, interface, trait, protocol, and the singleton `object` all
count; a bare type *use* or a variable of a type does not. The rule anchors the
defining keyword to the type's name.

**C2 · The compilation-unit container counts where it is the file's only
named-entity declaration.** A COBOL program *is* its `PROGRAM-ID` unit, a JCL
file *is* its `JOB`, a Dockerfile stage *is* its `FROM … AS`. These read against
a zero median because the SPEC probe declares no types — the deviation states a
true fact about the language, not an extraction error. Whether the scoreboard
should band such a constant against a declaration-requirement stratum instead
of the global zero is **#2796** (a scoring-layer change); this rule-layer
contract only states that the reading is correct and records it as morphology.

**C3 · Deliberate duals: one token, two constructs** (the fortran-COMMON shape,
kept — not the io/branch "one owner" case, because each token genuinely *is*
both constructs):

- dockerfile `FROM` — opens a named build stage (`class_start`) **and** names
  the base-image dependency (`import`). Both readings are correct; the token
  fires both rules.
- kotlin `object` — a singleton type (`class_start`) **and** the module-state
  plant (`globals`). Both correct (ledger `kotlin-object-dual-globals-classstart`,
  now intended-morphology).

**C4 · Stated absence.** A language with no type-declaration morphology records
`class_start: None` with a ledger entry: agc_assembly
(`agc-assembly-class-start-no-struct-pseudoop`), m4 (`m4-class-start-no-object-concept`),
makefile (`makefile-class-start-no-entity-declaration`), shell
(`shell-class-start-no-oop-morphology`), markdown (lit plane). The scan confirms
0 and the count is n/a (#2795), not red. (yacc's `%union` question is the open
`yacc-union-class-start-gap`.)

## The audit (corpus values, no rule change)

`rule_probe.py class_start all`, unchanged before/after. rosetta = hits across
the 4 keyword-rosetta shell files (median plant 0).

| language | rosetta | verdict |
|---|---|---|
| dockerfile | 4 | **scoring** — FROM stage container (C2); added to `container-construct-reads-as-class-start`. Was `extraction` via batch4's cross-product. |
| kotlin | 2 | **inherency** — plant-forced `object` (C3); `kotlin-object-dual-globals-classstart` re-dispositioned intended-morphology. Was `extraction`. |
| jcl | 1 | **scoring** — JOB card container (C2); already in `container-construct-reads-as-class-start`. Was `extraction` via batch4's redundant mark. |
| cobol | 1 | scoring — PROGRAM-ID container; unchanged |
| css | 1 | scoring — class selector container; unchanged |
| yaml | 7 | scoring — `jobs:`/`chain:` mappings; unchanged |
| agc_assembly, m4, makefile, markdown, shell | n/a | stated absence (C4) |
| the other 35 | 0 | conform — no type declaration in a function-only probe |

## Ledger dispositions this contract settles

- `batch4-dual-keyword-overlaps` — loses `class_start` from its signal union;
  dockerfile leaves `languages_seen` (FROM recorded here as a deliberate dual);
  jcl stays for its `SET` (globals+state_mutation) dual, and its `class_start`
  now resolves to the container entry alone.
- `container-construct-reads-as-class-start` — **dockerfile added** to
  `languages_seen` (FROM stage container, C2).
- `kotlin-object-dual-globals-classstart` — disposition keyword-overlap →
  intended-morphology (plant-forced, C3).
- The `classes_found` container cells and the declaration-requirement stratum
  stay open under #2795/#2796/#2798 (the scoring layer).

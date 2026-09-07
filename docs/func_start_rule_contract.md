# The `func_start` rule contract (#2856)

> **One hit is the syntax that opens an executable block of logic under its own
> name — a function, method, procedure or subroutine declaration anchored to
> its naming syntax, or, where the language has no named-callable form, the
> instruction that begins an executable step.**

Stated 2026-09-07 by the #2856 audit (roadmap Phase 3, epic #2812), paired with
`docs/class_start_rule_contract.md`. Precedents: `docs/api_rule_contract.md`
(#2730), `docs/state_mutation_rule_contract.md` (#2765),
`docs/branch_rule_contract.md` (#2822), `docs/io_rule_contract.md` (#2841),
`docs/test_rule_contract.md` (#2852). The machine-readable row is
`gitgalaxy/standards/signal_contracts.py`; the cross-language pins are
`tests/extraction/languages/test_structure_contract_2856.py`.

`func_start` is a **declaration**-kind, structure-phase signal. Its consumers:
the `functions_found` structure count is its tally (n/a when the rule is
absent, #2792/#2795); `signal_processor` reads it as the `entities` term
(`func_start + class_start`) and the density metrics; `detector.py` uses it as
the slicer's function-boundary anchor. Before this contract it carried 2 of the
report's open-defect cells (dockerfile, html); after it, **zero** — both were
collective-ledger cross-product mis-marks, not rule defects, and the rules were
not changed.

## Why no rule changed

Under the sentence above the 43 existing rules already conform: they anchor
`def`/`function`/`func`/`sub`/`proc`/`procedure`/method signatures, and — for
the languages with no named-callable form — the instruction that begins an
executable step (dockerfile `RUN`/`CMD`/`ENTRYPOINT`/`HEALTHCHECK`, a makefile
recipe target, a yaml `run:`/`script:` step). The two red cells were caused by
collective ledger entries claiming the cell through a signal×language
cross-product, the exact A.4 mis-mark `batch4` was corrected for twice before.

## Corollaries

**C1 · A reference is not a declaration.** Calling a function, or naming it in
a comment or a string, is not a `func_start`; only the site that *opens* the
block counts. dockerfile's `func_start` excludes a bare instruction word inside
a comment or an `ARG` value.

**C2 · The named-callable form, or the block instruction where there is none.**
Most languages open a block by naming a callable. A language whose imperative
unit is an unnamed instruction (a Dockerfile layer, a make recipe, a CI step)
counts that instruction — it is the language's executable-block-start form.
This is why dockerfile reads `func_start` 17 against a corpus median of 13: a
Dockerfile is a sequence of build instructions (`RUN`/`CMD`/`ENTRYPOINT`/
`HEALTHCHECK` across its stages), not a twelve-probe function file. The count
is morphology, not a defect (ledger `func-start-dockerfile-instruction-blocks`,
intended-morphology).

**C3 · Deliberate dual: one instruction, two constructs.** dockerfile
`HEALTHCHECK` opens an executable block (its `CMD …` probe runs) **and** is a
health/reliability probe — it fires both `func_start` and `safety`, the same
genuine two-construct overlap as fortran `COMMON` (globals + safety_bypasses).
It is kept, not retired: `HEALTHCHECK` is `func_start`'s by C2 and `safety`'s by
its own contract, and both readings are correct on the language. (dockerfile
`safety` already reaches its median without this dual via the planted
`USER probe`, keyword-rosetta#59, so no cell depends on the overlap.)

**C4 · Stated absence.** A language with no executable-block morphology records
`func_start: None` — markdown (lit-plane markup, ledger
`markdown-lit-plane-morphology`); the scan confirms 0 and the count is n/a, not
red.

**C5 · Markup declares no functions.** html's `func_start` anchors the
`<script>`/`<style>` opening tags — markup has no function declaration, and the
tags are the corpus's planted analogue (9 of 13, ledger
`html-func-start-counts-script-elements`, intended-morphology). The report read
this cell red only because `batch5-tier2-morphology-shapes` names `func_start`
in its signal union for *css* and html in its language list for an unrelated
`doc+ownership` dual — the cross-product falsely crossed them. `func_start`
leaves that entry's union (css's `@media`/`@supports` func_start is in band at
14 vs 13, needs no entry), and the cell falls through to its true
intended-morphology cause.

## The audit (corpus values, no rule change)

`rule_probe.py func_start all` reads identically before and after (no regex
edited). crucible = hits across the control corpus; rosetta = hits across the 4
keyword-rosetta shell files (median plant 13). Every value below is unchanged by
this contract; the "verdict" column records how each out-of-band cell is now
categorized.

| language | rosetta | verdict |
|---|---|---|
| dockerfile | 17 | **intended-morphology** — instruction-blocks (C2); `func-start-dockerfile-instruction-blocks`. Was `extraction` via batch4's cross-product. |
| html | 9 | **intended-morphology** — script/style tags (C5); `html-func-start-counts-script-elements`. Was `extraction` via batch5's cross-product. |
| haskell | 15 | in band (+15%) — foreign-import/where forms; no entry needed |
| makefile | 14 | in band — recipe targets (C2); its batch4 dual is `cleanup`+`api`, not func_start |
| css | 14 | in band — `@media`/`@supports` at-rule blocks (C2) |
| markdown | n/a | stated absence (C4) |
| the other 39 | 13 | conform — named-callable declarations |

## Ledger dispositions this contract settles

- `batch4-dual-keyword-overlaps` — loses `func_start` from its signal union;
  dockerfile leaves `languages_seen` (its only remaining duals, `HEALTHCHECK`
  and `FROM`, are now recorded here and in the class_start contract as
  deliberate). makefile stays for `cleanup`+`api`.
- `batch5-tier2-morphology-shapes` — loses `func_start` from its signal union
  (css's at-rule func_start is in band; the html mark was the cross-product).
- `func-start-dockerfile-instruction-blocks` — **new**, intended-morphology, the
  C2 morphology for dockerfile's 17.
- `html-func-start-counts-script-elements` — unchanged; now the sole explainer
  of html's cell.

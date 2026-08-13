# Document Alignment Guide

GitGalaxy's documentation is large enough that no single person reads all of it before
editing any of it: `README.md`, ~190 pages under `docs/wiki/`, six `docs/*.md` process docs,
and two evidence-generating subsystems (`docs/language_status/`, `docs/self_scan/`). Without
an explicit map, a claim gets tightened in one place (see
`docs/how_to_maintain_the_readme.md`, which already does this for `README.md` specifically)
while the page that's supposed to back it up keeps asserting something looser, older, or
flatly inconsistent — a reader who clicks through notices the seam before they notice the
engineering. This doc is the map: which doc owns which claim, what's supposed to link to
what, and where the two are currently *not* aligned so that gap doesn't get mistaken for
"nobody noticed."

This is the sibling of `how_to_maintain_the_readme.md` (README-specific tone rules) and
`readme_evidence_roadmap.md` (README-specific claim staging) — read those first. This doc
is scoped one level up: how the ~200-document site around the README relates to it.

## The canonical thesis (source of truth — trace other docs back to this, don't restate it)

GitGalaxy builds one deterministic structural graph of an entire repository — every
language in it, represented through the same ~97 regex-based structural signal categories
— instead of building a separate AST-derived model per language and reconciling them
afterward. That's the trade: less per-file syntactic precision than a parser like
Tree-sitter would give (now [measured, not assumed](../README.md#proof-not-just-claims),
item 4), in exchange for one comparable graph across a repository no single toolchain could
parse end to end. Security auditing, refactor prioritization, SBOM generation, and
legacy-to-modern translation are all consumers of that one graph, not separate engines.

Every page below either **backs** a piece of this thesis with evidence, or **applies** it to
a specific domain (security, legacy migration, visualization). If a page does neither, it's
either misplaced or the thesis needs updating — don't let a page just drift.

## Document tiers (hub and spoke)

| Tier | Docs | Role | Governing rules |
|---|---|---|---|
| 0 — Entry hub | `README.md` | First 90 seconds. Every claim here must be evidence-gated. | `how_to_maintain_the_readme.md`, `readme_evidence_roadmap.md` |
| 1 — Deep hub | `docs/wiki/index.md` | Full doc-site index, routes by role (security architect, legacy team, systems engineer). | This doc |
| 2 — Foundation & claims | `docs/wiki/01-*`, `03-*` | The thesis, spelled out: the blAST paradigm, the 10 numbered "Claims" pages, future outlook. | This doc (tone gap noted below) |
| 2 — Pipeline & math | `docs/wiki/02-*`, `06-*`, `07-*`, `08-*` | Stage-by-stage pipeline docs, per-signal risk-equation docs. One page per pipeline stage / equation, mirrors `gitgalaxy/core/README.md` and `gitgalaxy/metrics/`. | Should match the code at the path it documents — no separate rule doc yet (candidate follow-up, see below) |
| 3 — Evidence artifacts | `docs/language_status/`, `docs/self_scan/` (chart/CSV), `language-crucible`, `gitgalaxy-raw-output` (external repos) | What backs the claims — real measurements, not prose. | `.claude/skills/language-status/SKILL.md` |
| 4 — Applied spokes | `docs/wiki/04-*`/`05-*` (security tools, legacy tools), `cookbook/`, `agents/`, `LLM-reports/`, `museum-of-code/` | Domain-specific application of the thesis; task-oriented, not proof-oriented. | This doc |

## Claim → canonical doc → evidence map

The load-bearing claims in `README.md`, and where a reader lands if they click through:

| Claim | README anchor | Deep-dive doc(s) | Evidence artifact |
|---|---|---|---|
| Signature-based extraction instead of an AST, and why | `#one-graph-not-five-separate-tools` | [`01-03-the-blast-paradigm`](wiki/01-03-the-blast-paradigm.md), [`03-10-claim-10-ast-vs-heuristic-parsing`](wiki/03-10-claim-10-ast-vs-heuristic-parsing.md) | — (conceptual) |
| Regex signatures survive adversarial/pathological input | `#proof-not-just-claims` item 1 | [`03-08-claim-8-empirical-validation-of-ast-free-parsing`](wiki/03-08-claim-8-empirical-validation-of-ast-free-parsing.md) | `tests/README.md`, 3,649 regression tests |
| Correctness on real, uncompilable production code | `#proof-not-just-claims` item 2 | — | `language-crucible`, `tests/golden_master_audit.json` |
| Runs unmodified at real-world scale | `#proof-not-just-claims` item 3 | [`museum-of-code/`](wiki/museum-of-code/index.md) (per-repo teardowns), [`LLM-reports/`](wiki/LLM-reports/index.md) | `gitgalaxy-raw-output` |
| Measured extraction accuracy vs. Tree-sitter ground truth | `#proof-not-just-claims` item 4 | [`docs/language_status/`](language_status/README.md) | `docs/self_scan/tree_sitter_accuracy_chart.svg` + `_history.csv`, `tests/tree_sitter_accuracy_baseline_*.json` |
| Scan speed / scales near-linearly | "What Pain Point Does This Solve?" | [`03-01-claim-1-search-strategies`](wiki/03-01-claim-1-search-strategies.md) | `gitgalaxy-raw-output`'s speed telemetry |
| One graph feeds many tools (security, legacy, SBOM, AI guardrails) | "One Graph, Not Five Separate Tools", "Enterprise Codebase Tools & Use Cases" | `docs/wiki/04-*` (security), `05-*` (legacy), `cookbook/*` | Per-tool benchmark bullets in `README.md` itself |
| Risk scores are prioritization signals, not verdicts | "What GitGalaxy Finds — and What It Doesn't Claim" | [`08-01-methodology`](wiki/08-01-methodology.md) onward | — (methodology) |

When a new claim is added to `README.md` under `readme_evidence_roadmap.md`'s process,
add a row here too — this table is what keeps the deep-dive pages from silently going stale
relative to the front door.

## Known alignment gap (flagged, not fixed in this pass)

`03-08-claim-8-empirical-validation-of-ast-free-parsing.md` and
`03-10-claim-10-ast-vs-heuristic-parsing.md` — and the wider wiki tone generally (`index.md`
included) — predate the tree-sitter accuracy benchmark and `how_to_maintain_the_readme.md`'s
five rules, and it shows: "mathematically guarantee," "infallible," language implying
near-100% precision as a settled fact. That's no longer accurate next to the actual measured
numbers now linked from the README (median ~98% function recall, but a real range down to
39.1% on Kotlin, two languages fully written up, real bugs still being found). It's not a
small wording nit — a skeptical reader who follows the README's new item-4 link to Claim 10
right after reading "mathematically guarantee" on Claim 8 will notice the two pages don't
sound like they're describing the same engine.

This wasn't rewritten as part of this pass — it's ~190 pages of established voice, most of
which (the cookbook, agent reports, museum-of-code teardowns) don't carry evidence claims at
all and don't need this treatment. The two Claim pages above are the actual candidates: file
a follow-up issue (via the `issue-triage` skill) scoped to just those two, reconciling their
language with the measured numbers and adding a direct link to
`docs/language_status/README.md`, rather than a wholesale wiki tone pass.

## Cross-linking convention (for new pages, not retrofitted onto old ones)

New wiki pages that back a specific README claim should end with:

```markdown
---
**Backs:** [README § <section>](../../README.md#<anchor>)
**See also:** [<related spoke page>](<relative-link>.md)
```

This makes the tier-2/tier-3 relationship navigable from the spoke side, not just the hub
side — a reader who lands on a deep page via search should be able to find their way back to
the thesis without going through `index.md`. Existing pages aren't required to retrofit this
footer; add it opportunistically when a page is next touched for another reason.

## Maintaining this doc

Update the claim map whenever `readme_evidence_roadmap.md` moves an item from "Gated" to
"Shipped" and it lands in `README.md` — that's the trigger that a new deep-dive doc (or an
existing one) needs a row here too. This doc doesn't need its own separate roadmap; it rides
on the README's.

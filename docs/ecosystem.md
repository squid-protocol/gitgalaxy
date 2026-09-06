# The GitGalaxy repo constellation

GitGalaxy work routinely spans four or five intermingled repositories, and most of the recurring
workflows (a crucible pin bump, a rosetta sweep, a language addition) have steps in more than one
of them. This doc is the canonical, **agent-neutral** map: what each repo is for, where it lives,
what skills and agent guidance it carries, and how the cross-repo workflows sequence. It is
written for any coding agent (Claude, Antigravity/Gemini, or the next one) and for humans; the
per-agent files (`CLAUDE.md`, `ANTIGRAVITY.md`, `AGENTS.md`) point here rather than each carrying
their own drifting copy.

## The repos

Canonical local layout on the dev machine — all siblings under `/srv/storage_16tb/projects/`:

| Repo (GitHub, org `squid-protocol`) | Local checkout | What it is |
|---|---|---|
| **gitgalaxy** | `gitgalaxy/v6` | **The engine** (this repo). AST-free, LLM-free static analysis: bounded-regex structural signatures → knowledge graph → risk scoring / SBOM / 3D map. Everything else in this table exists to feed, verify, or showcase it. |
| **language-crucible** | `all_language_repo` | Zero-execution structural-parser **benchmark corpus** (`data/<language>/<repo-folder>/`, per-category `SOURCES.md`, machine-readable `PROVENANCE.json`). gitgalaxy CI pins it to a release tag (`LANGUAGE_CRUCIBLE_REF` GH Actions var + `tests/_crucible_pin.py`) and diffs golden masters against it. Releases per its `RELEASING.md`. |
| **keyword-rosetta** | `keyword-rosetta` | **Control corpus**: one identical 12-probe program shell in all 46 signature-bearing languages, exact planted keyword counts — measures whether the engine treats identical intent identically across languages (cross-language bias). Gates via `tools/verify_language.py`; deviations live in `deviation_ledger.json` per its `docs/GATING.md`. Its CI checks out gitgalaxy **main**, and gitgalaxy's `rosetta-audit` checks out its **main** — no pins in either direction (#2682). Its `bias-history.yml` regenerates the bias chart after every corpus push and daily. |
| **gitgalaxy-raw-output** | `gitgalaxy-raw-output` | Real, unedited **scan outputs** on independently-chosen production repos (`v<engine-version>/<repo>/<repo>_galaxy_llm.md` + gzipped audit/SBOM) plus speed charts. Evidence source for README claims and `docs/language_status/` §8 sections. |
| **squid-telemetry** | `squid-telemetry` | **Distribution/adoption analytics** (the engine itself is air-gapped and phones nothing home; this pipeline scrapes public GitHub/GitLab/PyPI fetch metrics daily via Actions and commits regenerated chart PNGs). |
| **gitgalaxy-population-analyses** | `gitgalaxy-population-analyses` | Offline **statistical analyses** over scan populations (risk-distribution ridgeplots, archetype clustering, threat-prediction distribution studies). Reads raw inputs from gitgalaxy-raw-output; never on any CI path. |
| **cobol_to_java_examples** | *(not usually checked out locally)* | **Legacy-modernization showcase**: 10 COBOL repos auto-translated by the engine's `cobol_to_java` pipeline into compiling Spring Boot architectures (entities/controllers/services + `ai_agent_jobs/` tickets). Evidence for the docs site's Legacy Bridge chapter. |
| **squid-protocol** (profile repo) | *(not usually checked out locally)* | The org/user **profile README** — the public front door linking the flagship projects. Update it when a new constellation repo becomes showcase-worthy. |

**Local-only directories that are NOT repos** (but matter):

- `gitgalaxy/data/` — the full-repo **source pool** (~113 clones, `corpus_<domain>/` collections,
  npm/pypi mirrors). Feeds the crucible; not pinned, not a git repo itself. Its `README.md`
  documents the layout. `gitgalaxy/data/gitgalaxy/` is a clone of the engine kept in the pool so
  the engine can scan itself — **never edit engine code there**.
- `gitgalaxy/v1` … `v5`, `museum*`, `temp/`, `threat_hunter/` — historical/scratch copies.
  **Only `gitgalaxy/v6` is the live engine checkout.** A repo-wide grep from `/srv/.../projects`
  or `/srv/.../gitgalaxy` will hit stale copies of files like `language_standards.py` in
  `temp/`, `threat_hunter/`, and the pool's self-scan clone — check the path before trusting or
  editing a hit.

## Public-facing surfaces & reusable assets

Things to link (never duplicate) when writing READMEs, docs, issues, or showcase material:

- **The docs site** — https://squid-protocol.github.io/gitgalaxy/ (source: this repo's `gh-pages`
  branch). ~100 pages: architecture chapters (pipeline 02-*, risk-equation methodology 08-*,
  visual-encoding 07-*), the ten claims (03-*), security landscape (04-*), the **Legacy Bridge
  chapter** (05-* — refraction controller, Spring Boot scaffolding, JCL forge/auditor, agent
  tickets), plus the [Museum of Code](https://squid-protocol.github.io/gitgalaxy/museum-of-code/)
  (full architectural teardowns), a cookbook, LLM-report examples, and the CLI reference.
- **The visualizer / product site** — https://gitgalaxy.io/ · **PyPI** —
  https://pypi.org/project/gitgalaxy/ · **Demo video** — https://www.youtube.com/watch?v=XWWSd8LmoCM
- **Auto-regenerating chart assets** (embed by raw URL; they update themselves, so never
  hand-copy the image):
  - keyword-rosetta bias chart: `https://raw.githubusercontent.com/squid-protocol/keyword-rosetta/main/docs/bias_variance_chart.svg` (regen by `tools/bias_report.py`)
  - raw-output speed charts: `https://raw.githubusercontent.com/squid-protocol/gitgalaxy-raw-output/main/speed_charts/latest/{loc_vs_time,rate_model}.png` (regen per scan batch)
  - telemetry adoption charts: `https://raw.githubusercontent.com/squid-protocol/squid-telemetry/main/{cumulative_downloads,conversion_funnel,discovery_channels,feature_intent,release_correlation}.png` (regen daily by Actions)
- **README convention**: every constellation repo's README carries a short "GitGalaxy
  constellation" section linking its neighbors (with a *you-are-here* marker) and the docs site —
  so a reader landing anywhere can navigate the whole web. The engine README's own linking is
  governed by `docs/how_to_maintain_the_readme.md` (evidence-shaped, five rules) — follow that
  doc, not this section, when editing it.

## Where the skills live

Skills are markdown workflows (`SKILL.md`) usable by any agent that reads them; each repo carries
the skills that operate **on that repo**, under `.claude/skills/` with an `.agents/skills` symlink
to the same directory so non-Claude agents find them at a vendor-neutral path.

| Repo | Skills |
|---|---|
| gitgalaxy | `harden-language-extraction`, `harden-strict-signatures`, `harden-class-start-extraction`, `tri-comparison-ledger-sweep`, `tree-sitter-accuracy-sweep`, `language-status`, `ci-push-checklist`, `self-scan-query`, `issue-generation`, `pipeline-check`, `readme-maintenance`, `release-notes`, `rule-contract-audit` (take one signal's contract from draft to stated across all corpus languages) |
| keyword-rosetta | `rosetta-language-sweep` (classify one language's out-of-band cells by cause; the per-language instrument a family audit calls -- the per-language tracking issues were closed 2026-09-06) |
| language-crucible | `expand-language-coverage` (fill a `data/<lang>/` category from the source pool) |

gitgalaxy additionally has `.claude/rules/` (always-on constraints: planning approval,
golden-master hygiene, CI self-healing, sandbox/permission discipline, tri-comparison regen) —
`ANTIGRAVITY.md` and `AGENTS.md` restate the same constraints for other agents; if you change a
rule, sync all three.

## Cross-repo workflows (and their merge order)

| Workflow | Repos touched (in merge order) | Documented in |
|---|---|---|
| **Crucible corpus growth → release → pin bump** | language-crucible (data PRs, tag per `RELEASING.md`) → gitgalaxy (`docs/self_scan/BUMPING_THE_CRUCIBLE_PIN.md`: regen golden masters + tri-comparison + tree-sitter artifacts, bump `LANGUAGE_CRUCIBLE_REF` + `PINNED_TAG`) | crucible `RELEASING.md`; gitgalaxy `BUMPING_THE_CRUCIBLE_PIN.md` |
| **Rosetta contract audit** (work one signal's cause family, not one language) | gitgalaxy engine PR first (rule fixes for every language the contract audit found, the signal's row in `standards/signal_contracts.py` → `stated`, `docs/<signal>_rule_contract.md`; its `rosetta-audit` lists the languages it moves — add `rosetta:rebless-owed`) → merge → keyword-rosetta corpus PR against engine main (plants, contract-level absences ledgered, manifests re-blessed) → merge; `bias-history.yml` regenerates the chart and the cause table. Capstones land in `docs/language_status/<lang>.md` §10 whenever a language reads clean by `language_deviations.py`. Roadmap and phase order: gitgalaxy `docs/contract_roadmap.md`. | gitgalaxy `rule-contract-audit` skill; keyword-rosetta `rosetta-language-sweep` (per-language classification); gitgalaxy `docs/self_scan/ROSETTA_AUDIT.md` |
| **Adding a language to the engine** | gitgalaxy (`standards/how_to_add_a_language.md`, includes authoring the rosetta control folder) → keyword-rosetta (`SPEC.md` shell + manifest) → optionally language-crucible (`expand-language-coverage`) | those three docs |
| **Tri-comparison / accuracy verification** | gitgalaxy only (ledger, chart, `manual_verification.json`), but reads the pinned crucible corpus | gitgalaxy `docs/self_scan/tri_comparison_README.md` |
| **README / evidence claims** | gitgalaxy README cites gitgalaxy-raw-output artifacts and the keyword-rosetta chart (embedded from that repo's raw main URL — it self-updates when rosetta main moves) | gitgalaxy `readme-maintenance` skill |

## PR convention for cross-repo work

Any PR that participates in a cross-repo workflow **must carry a "Cross-repo" note in its body**
stating: (1) the companion PR/issue links in the other repo(s), (2) which side merges first and
why (e.g. "draft here until squid-protocol/gitgalaxy#NNNN merges — this repo's CI checks out
gitgalaxy main"), and (3) what must be re-run after the other side lands (a CI rerun, a
re-baseline, a pin bump). A reviewer — human or agent — landing on either PR alone must be able
to reconstruct the whole change without hunting. Worked example: gitgalaxy#2611 ↔
keyword-rosetta#4 (the first rosetta jcl sweep).

## Agent-guidance file conventions

- **`AGENTS.md`** — vendor-neutral hard policies for the repo (any agent must follow).
- **`CLAUDE.md`** — Claude-specific guidance (loads automatically in Claude Code sessions).
- **`ANTIGRAVITY.md`** — Antigravity/Gemini-specific guidance, mirroring CLAUDE.md's constraints.
- **`.agents/skills` → `.claude/skills`** symlink — one skills directory, two discovery paths.
- Satellite repos keep their agent files **thin**: repo-specific gates plus a pointer to this doc
  — the constellation map is maintained *here only* (`docs/ecosystem.md` in gitgalaxy), so it
  cannot fork across repos. When the constellation changes (a new repo, a new cross-repo
  workflow, a moved skill), update this file and the satellites' pointers in the same pass.

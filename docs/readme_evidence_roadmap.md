# README Evidence Staging Roadmap

A living list of claims a skeptical reviewer would want that GitGalaxy doesn't have the
evidence for yet, plus two claims that don't need new data and should just be built. Nothing
in the "Gated" table goes into `README.md` until its activation trigger is literally true and
checkable in this repo — not "the script is half-written" or "we're pretty confident."
That's the same discipline `README.md`'s own "Proof, Not Just Claims" section already holds
itself to; this doc applies it to what hasn't been built yet.

Originated 2026-08-06 from an external review (paraphrased): the README's boldest claims
(planetary scale, AST replacement, universal logic extraction) aren't paired with the
benchmark/methodology/reproducibility/limitations a skeptical engineer needs before trusting
them — see `docs/how_to_maintain_the_readme.md` for the tone rules this roadmap exists to
enforce.

Update this doc whenever a gated item's trigger is met (move the row to "Shipped" and add the
claim to the README in the same PR) or whenever a new claim gets proposed for the README
before its evidence exists (add a row here instead of writing it into README.md early).

## Do now — no new data required

| Candidate addition | Why it's ready | Where it lands |
|---|---|---|

*(Empty as of this update — both rows previously here have shipped; see below.)*

## Gated — waiting on evidence

| Candidate addition | Status today | Activation trigger | Where it lands |
|---|---|---|---|
| Full-coverage manifest for the raw-output corpus | `gitgalaxy-raw-output`'s `corpus/v1/manifest.json` pins 323 repos, but the `v2.4.6/` batch actually archived there has output for 718 — the reproducibility claim currently covers less than half the real batch. Stated plainly in that repo's README rather than glossed over; see [gitgalaxy-raw-output#1](https://github.com/squid-protocol/gitgalaxy-raw-output/issues/1). | A `v2` manifest (or corrected `v1`) covering all 718 repos in `v2.4.6/`, with commit pins for each. | `gitgalaxy-raw-output/README.md`'s "Known gap" note gets deleted, not reworded |
| Head-to-head speed benchmark vs. a named scanner | Only a self-benchmark across 104 repos exists (no comparison baseline) | A runnable comparison script + committed results in a `benchmarks/` directory (can reuse the `language-crucible` corpus as the fixed input) | Benchmarks → new "vs. Other Scanners" subsection |
| Documented false-positive / false-negative rate | No labeled ground truth exists | A hand-labeled subset of `language-crucible` (or a dedicated labeled corpus) has measured precision/recall written up | Proof section → new "Accuracy" subsection |
| Independent / outside validation | No external contributors or citations yet | First externally-authored PR merges, or the project is cited/reviewed somewhere GitGalaxy didn't publish itself | New "Independent Validation" section — stays absent, not stubbed, until then |
| Written case studies (e.g. "we scanned Kubernetes") | Raw material is now substantially stronger than "partial" — `gitgalaxy-raw-output` has unedited scan artifacts (audit JSON, SQLite, LLM briefs) for hundreds of real repos, not just the earlier 170-Go-module Kubernetes SBOM claim and the OpenCV demo video. Still no *written* methodology+findings doc for any single repo. | A doc under `docs/case-studies/` (or similar) exists per repo, with real methodology and findings, drawing on the now-linked raw-output artifacts as its source data | New "Case Studies" section, one link per write-up |
| Conference talk / third-party blog coverage | None yet | It happens — don't manufacture a "Press" section to fill with nothing | Footer, one line, only once real |

## Shipped

| Candidate addition | Shipped | Where |
|---|---|---|
| Feature comparison table vs. Semgrep / CodeQL / Snyk / Dependabot | 2026-08-06, PR #1103-stack | README.md, "How This Compares, Architecturally" (after Weakness Classes) |
| Badge cleanup — drop unlinked superlative badges | 2026-08-06, PR #1103-stack | README.md header |
| `gitgalaxy-raw-output` linked as a third proof pillar (real-world-scale raw scan output, complementary to the curated golden-master corpus) | 2026-08-06 | README.md "Proof, Not Just Claims" (item 3) and "Benchmarks" |
| `language-crucible`'s README rewritten to lead with why it exists and explicitly name the CI mechanism as a "true golden diff," linking back to `README.md`'s Proof section | 2026-08-06 | `language-crucible/README.md` (separate repo) |
| Stale test-count fixed repo-wide: README.md and tests/README.md both cited 2,491/2,536 per-signature tests; actual collected count is 3,649 | 2026-08-06 | README.md, tests/README.md, `.claude/skills/readme-maintenance/SKILL.md` |
| "What Pain Point Does This Solve?" section, addressing external feedback that a first-time visitor couldn't tell within a minute whether GitGalaxy competes with CodeQL/Semgrep/SonarQube or does something else — explicit "this is not X" disambiguation linking to the comparison table, plus a real cited example (Kubernetes, 1.39M LOC, 50.83s scan) instead of an abstract claim | 2026-08-06 | README.md, right after the proof strip; also retitled "Whole-Repository Intelligence with a Security Layer" to lead with the "one graph, three consumers" framing instead of security-first branding |
| Restore the "0 dependencies" claim (stat line + badge) | 2026-08-06, [#1104](https://github.com/squid-protocol/gitgalaxy/issues/1104) — `PyYAML` moved from `pyproject.toml`'s `dependencies` into an optional `gitgalaxy[yaml]` extra; the 3 lazy-import call sites now raise/warn with an actionable install message instead of a silent no-op or bare `ImportError` | README.md stat line + badge |

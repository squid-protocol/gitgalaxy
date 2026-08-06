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
| Feature comparison table vs. Semgrep / CodeQL / Snyk / Dependabot | Buildable today from each tool's own public docs, the same way repowise builds its comparison tables. Only a prose comparison exists today. | After "Weakness Classes, Not Just CVEs" |
| Badge cleanup — drop unlinked superlative badges (`Velocity`, `Analysis`, `Architecture`) | Subtraction, not a new claim — no evidence needed to remove an unbacked assertion. | Header |

## Gated — waiting on evidence

| Candidate addition | Status today | Activation trigger | Where it lands |
|---|---|---|---|
| Restore the "0 dependencies" claim (stat line + badge) | Currently **false** — `pyproject.toml` lists `PyYAML>=6.0` as a hard dependency, even though it's only lazily imported in 3 call sites. Corrected to "1 dependency" in the README as of this pass; see [#1104](https://github.com/squid-protocol/gitgalaxy/issues/1104). | [#1104](https://github.com/squid-protocol/gitgalaxy/issues/1104) is merged: PyYAML moved to an optional extra, core install has zero hard dependencies again. | Stat line + badge, revert to "0 dependencies" |
| Head-to-head speed benchmark vs. a named scanner | Only a self-benchmark across 104 repos exists (no comparison baseline) | A runnable comparison script + committed results in a `benchmarks/` directory (can reuse the `language-crucible` corpus as the fixed input) | Benchmarks → new "vs. Other Scanners" subsection |
| Documented false-positive / false-negative rate | No labeled ground truth exists | A hand-labeled subset of `language-crucible` (or a dedicated labeled corpus) has measured precision/recall written up | Proof section → new "Accuracy" subsection |
| Independent / outside validation | No external contributors or citations yet | First externally-authored PR merges, or the project is cited/reviewed somewhere GitGalaxy didn't publish itself | New "Independent Validation" section — stays absent, not stubbed, until then |
| Written case studies (e.g. "we scanned Kubernetes") | Partial raw material exists (170-Go-module Kubernetes SBOM claim, 3.2M-line OpenCV demo video) but no written methodology+findings doc | A doc under `docs/case-studies/` (or similar) exists per repo, with real methodology and findings, not just a benchmark bullet | New "Case Studies" section, one link per write-up |
| Conference talk / third-party blog coverage | None yet | It happens — don't manufacture a "Press" section to fill with nothing | Footer, one line, only once real |

## Shipped

*(Move rows here as their trigger is met, with the date and the PR that added them to
README.md.)*

None yet.

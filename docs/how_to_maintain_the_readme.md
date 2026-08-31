# How to Maintain the GitGalaxy README

The README has two sections that already do this right: **"Risk exposure: what GitGalaxy
claims"** and **"Evidence, not just claims"** (renamed from "What GitGalaxy Finds — and What
It Doesn't Claim" and "Proof, Not Just Claims" in the 2026-08-22 structural rewrite — same
role, new names, see the "2026-08-22 rewrite" note at the bottom of this doc for what else
changed). Both state a limitation before a reader has to find it, and every claim links to
something inspectable (a test count, an epic, a corpus). Treat those two sections as the tone
bar for every other section — not because they're the least interesting content in the
README, but because they're the only sections that would survive a staff engineer asking
"show me the benchmark."

This doc exists because the rest of the README (and, on the same pass, `tests/README.md`)
drifts away from that bar under normal editing pressure — a new feature ships, someone adds
a paragraph in the moment's voice, and six months later the gap between the good sections and
the rest is wide enough that outside readers notice it before they notice the engineering.
Use this doc every time you touch README.md, not just on a dedicated cleanup pass.

## The five rules

1. **Every superlative gets a number and a link in the same sentence, or gets cut.**
   "Fastest," "most precise," "zero-trust" as a bare adjective are assertions, not evidence.
   If the number doesn't exist yet, the claim belongs in
   `docs/readme_evidence_roadmap.md`, not the README — see that doc for the exact
   staging process.
2. **A brand metaphor may name something once per section — not explain it.** blAST, Galaxy,
   Singularity, Observatory, Structural Physics: fine as a label on top of a mechanism, wrong
   as the mechanism's only description. If a sentence would be unclear to a reader who
   ignores the brand vocabulary entirely, rewrite it in plain engineering terms (what regex,
   what data structure, what algorithm) and let the metaphor sit beside it, not instead of it.
3. **No emoji as a section-heading decoration.** Emoji stay fine inline where they carry real
   information (a status glyph in a table cell), not as a rocket ship next to "Release Notes"
   or a telescope next to "Watch GitGalaxy in Action."
4. **Every "Benchmark:" line names its sample size and one thing it doesn't prove.** The
   pattern to copy: "Achieved a 27/27 Maven compile success rate... Compiling is a necessary
   but not sufficient signal of a correct translation... a business logic review is still
   required." A benchmark bullet with no named limitation is an incomplete benchmark bullet.
   (That exact COBOL line was cut in the 2026-08-22 rewrite along with the rest of "Tools &
   Use Cases" — the current "Real-world scale" section's Kubernetes bullet is the one
   surviving benchmark-shaped claim in the README, and it doesn't yet have a limitation
   clause. Fixing that is a good first task for whoever next touches that section.)
5. **New sections are ordered by how a skeptical reader would trust them, not how exciting
   they are.** Proof and limitations before benchmarks; benchmarks before adoption numbers;
   adoption numbers before enterprise/licensing. A skeptical engineer reads in that order —
   the README should match.

## Section order (current target state, as of the 2026-08-31 product-first restructure)

The 2026-08-31 restructure split the README in two: `README.md` leads with the product
(what a scan gives you, shown with real report excerpts), and the long proof narrative —
the structural-extraction thesis, the full tri-comparison section with its subsections,
the validity ladder, the risk-over-Git-history experiment, and the closing research
direction — moved intact to `docs/validation.md`. Edit proof prose there, not by
reintroducing it into README.md. The README keeps a condensed "Accuracy, measured"
summary with both charts and per-claim limitation clauses.

1. Title + one-line tagline + the Docs/Visualizer/Language Crucible/Keyword
   Rosetta/Raw Output link line. **No badges currently** — License, PyPI version, Python
   version, and Dependencies badges all existed before the 2026-08-22 rewrite and were
   dropped with it; restoring any of them (each still has a real link behind it, so each
   would pass rule 1) is an open gap, not a considered removal.
2. Proof strip — `1 scan · 97 structural signals · 50+ languages · no compilation ·
   19 risk-exposure categories · 6 outputs`. Still missing the "0 dependencies" claim
   (shipped and true as of #1104) — its absence remains a regression, not a status change.
3. **The short version** — plain-terms description folding in the old "The problem"
   polyglot code block, the consumer list as prose, the blockquoted central-thesis line,
   and a forward link to `docs/validation.md`.
4. **What a scan gives you** — the product section (new 2026-08-31): install/run command,
   the six-outputs table (absorbing the old standalone "Outputs" section), and "The
   architecture brief" showcase with two dated, reproducible scan excerpts (curl,
   cics-genapp), each carrying its own rule-4 limitation clause. Excerpt numbers are
   point-in-time by design — they name their scan date and the engine that produced them;
   refresh the excerpts (rerun `galaxyscope --llm-only` on the same public repos) rather
   than letting undated numbers drift. Ends with the "One graph, many consumers"
   consumer/question table + the sankey pipeline diagram.
5. **Accuracy, measured** — condensed two-part proof summary. Subsection headings
   "Structural validation: GitGalaxy vs Tree-sitter vs Ctags" (keeps the old
   `#structural-validation-gitgalaxy-vs-tree-sitter-vs-ctags` anchor resolving — do not
   rename it) and "Cross-language consistency: the Keyword Rosetta control corpus". Chart
   order is deliberate: tri-comparison SVG (accuracy on real code) before the
   keyword-rosetta bias-variance SVG (consistency on planted code, embedded from that
   repo's raw main-branch URL so it self-updates). Each subsection states one limitation
   and links to `docs/validation.md` for the full treatment. Proof sits before the
   speed benchmark on purpose (rule 5) — don't float "Real-world scale" back above it.
6. **Real-world scale** — Kubernetes benchmark + the fitted two-regime speed model as its
   rule-4 limitation clause (the clause rule 4 previously flagged as missing — now
   present; keep it) + the self-updating loc_vs_time chart.
7. **Risk exposure: what GitGalaxy claims** (tone-bar section #1 — do not rewrite its
   prose, only relocate it if needed; see the intro note above on why the name changed).
8. **Evidence, not just claims** (tone-bar section #2). Every bullet under it should name
   a real, current number — "Regression suite" in particular must cite the actual
   collected test count (`python -m pytest tests/ --collect-only -q`), not a vague
   "thousands"; numbers drift as the suite grows, so re-verify rather than copying
   forward. Now includes a "Keyword Rosetta control corpus" bullet alongside the
   tri-comparison one.
9. **What GitGalaxy is — and isn't** — is/is-not bullet lists + the tool-comparison table
   (carries what "How This Compares, Architecturally" used to; the old
   `#how-this-compares-architecturally` anchor still doesn't resolve anywhere).
10. **Git history and architecture** — churn/bus-factor/hotspot signals as a short
    paragraph, linking to the validation doc's Git-history experiment.
11. **Privacy and deployment** — one section, not two. If a future edit reintroduces a
    second privacy section (it has happened once already, pre-rewrite), merge them back.
12. **Installation** (+ CI/CD subsection).
13. **Explore the evidence** — link table; now includes `docs/validation.md` and Keyword
    Rosetta rows. Still the only place the Visualizer gets a dedicated mention.
14. **License.**

**Sections moved to `docs/validation.md` on 2026-08-31 (not cut):** "The
structural-extraction thesis," the full "Structural validation" section with its "what
the benchmark is asking" and "languages without comparator coverage" subsections,
"Validation is a ladder" (now seven rungs — a "Measurement consistency" rung for the
control corpus was added between structural and regression validity), "The next
validation: risk over Git history," and "Current research direction." The five rules
apply to that file exactly as they do to README.md.

**Sections present before the 2026-08-22 rewrite and currently absent:** badges (item 1
above), "Weakness Classes, Not Just CVEs," "Real-World Adoption" (stars/downloads, deliberately
below Benchmarks per rule 5), and "Tools & Use Cases" (the per-tool embedded-benchmark section,
which is also where the rule-4 COBOL example used to live). None of these were evaluated
against the five rules before being cut — treat their absence as an open question for whoever
next does a dedicated tone pass, not as a settled decision.

## Before adding a claim

Ask: does this claim have a link a reader can click to verify it themselves, right now, in
this repo? If yes, write it with the link. If no, it's a roadmap item — add it to
`docs/readme_evidence_roadmap.md` with a concrete activation trigger instead of writing it
into the README ahead of the evidence. Do not write a claim as if the evidence exists "soon"
or "in progress" — a claim in the README should be true today, not aspirationally true.

## Status check before a PR that touches README.md

1. Read your diff against the five rules above, line by line — not just a vibe check.
2. If you added a new section, confirm its position matches the trust-ordering in rule 5.
3. If you added or changed a Benchmark bullet, confirm rule 4's limitation clause is present.
4. Check `docs/readme_evidence_roadmap.md` — did this change unlock a roadmap item (e.g. a
   comparison script landed, a case study got written)? If so, move that item from the
   roadmap into the README in the same PR and update the roadmap doc's status.
5. Skim `tests/README.md` and the most recent release note for the same drift — they're not
   in scope for every README PR, but if you're already doing a tone pass, flag anything you
   notice rather than fixing README.md in isolation.

See `.claude/skills/readme-maintenance/SKILL.md` for the skill wrapper around this process,
`docs/how_to_write_release_notes.md` for the sibling guide covering release notes (same
underlying rules, applied to a different surface), and
`docs/document_alignment_guide.md` for the doc one level up — which wiki/deep-dive page is
supposed to back each README claim, and where that's currently out of sync.

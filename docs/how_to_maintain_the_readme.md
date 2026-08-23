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

## Section order (current target state, as of the 2026-08-22 rewrite)

1. Title + one-line tagline ("Repository-scale structural intelligence without
   compilation.") + the Docs/Visualizer/Language Crucible/Raw Output link line. **No badges
   currently** — License, PyPI version, Python version, and Dependencies badges all existed
   before this rewrite and were dropped along with it; restoring any of them (each still has
   a real link behind it, so each would pass rule 1) is an open gap, not a considered removal.
2. Proof strip — currently `1 scan · 97 structural signals · 50+ languages · no compilation ·
   19 risk-exposure categories · 6 outputs`. This dropped the dependency-count claim
   entirely; cross-check against `docs/readme_evidence_roadmap.md`'s PyYAML row before
   deciding whether to add "0 dependencies" back — that claim was shipped and true as of
   #1104, so its absence here is a regression, not a status change.
3. **The short version** — plain-terms description, the "same graph feeds N consumers"
   bullet list, and a blockquoted central-thesis line. No BLAST/genomics analogy anywhere in
   the current draft (the whole brand-metaphor vocabulary rule-2 exists for is currently
   unused) — reintroducing it is fine as long as rule 2 still holds once it's back.
4. **The problem** — ASCII-diagrammed statement of the trade GitGalaxy makes. This replaced
   "What Pain Point Does This Solve?"'s bulleted, externally-motivated framing (see that
   section's git history for why it existed — a first-time visitor couldn't tell within a
   minute whether this competes with CodeQL/Semgrep/SonarQube). The explicit "this is not X"
   disambiguation that used to live here now only exists later, folded into "What GitGalaxy is
   — and isn't" (item 13) — confirm that's still reachable early enough for a skeptical
   first-time reader before treating this as settled.
5. **One graph, many consumers** — consumer/question table + the architecture pipeline
   diagram (`docs/wiki/assets/sankey_v4.3.1.png`).
6. **The structural-extraction thesis** — the ~97 structural-signal-category list + the
   testable-hypothesis blockquote.
7. **Structural validation: GitGalaxy vs Tree-sitter vs Ctags** — the tri-comparison
   methodology, current coverage numbers (languages with 3/2/0 comparator tools, ledger
   validation count), and the "what the benchmark is/isn't asking" + "languages without
   comparator coverage" subsections. Anchor slug
   `#structural-validation-gitgalaxy-vs-tree-sitter-vs-ctags` is now a link target from later
   sections — keep it stable.
8. **Validation is a ladder** — new in this rewrite, no prior equivalent. Six escalating
   validity levels (structural → regression → scale → model → temporal → external). This is a
   genuinely stronger evidence framework than what existed before the rewrite; keep it even if
   other sections get walked back toward the pre-rewrite structure.
9. **Risk exposure: what GitGalaxy claims** (tone-bar section #1 — do not rewrite its prose,
   only relocate it if needed; see the intro note above on why the name changed).
10. **The next validation: risk over Git history** — forward-looking research section
    (git-history-as-validation-source experiment design). New in this rewrite.
11. **Evidence, not just claims** (tone-bar section #2). Every bullet under it should name a
    real, current number — "Regression suite" in particular must cite the actual collected
    test count (`python -m pytest tests/ --collect-only -q`), not a vague "thousands"; numbers
    drift as the suite grows, so re-verify rather than copying forward.
12. **What GitGalaxy is — and isn't** — is/is-not bullet lists + the tool-comparison table.
    This is the section that now carries what "How This Compares, Architecturally" used to
    carry (comparator table vs. Tree-sitter/Ctags/Semgrep/CodeQL/SCA tools); no longer at a
    stable, separately-named anchor, so re-check any old link pointing at
    `#how-this-compares-architecturally` — it no longer resolves here.
13. **Real-world scale** — the Kubernetes benchmark bullet. Needs a rule-4 limitation clause
    (currently missing — see rule 4 above).
14. **Outputs** — SARIF/SBOM/SQLite/LLM-brief/JSON/3D-viz table.
15. **Git history and architecture** — churn/bus-factor/hotspot signals, framed as feeding the
    Git-history validation direction (item 10).
16. **Privacy and deployment** — one section, not two. If a future edit reintroduces a second
    privacy section (it has happened once already, pre-rewrite — "Data Privacy & On-Premise
    Deployment" and "Zero-Trust Data Security" said the same three things in two places),
    merge them back.
17. **Installation** (+ CI/CD subsection).
18. **Explore the evidence** — link table to Docs/Language Crucible/Raw Output/tests/README.md
    /ledger/manual-verification/how-to-investigate/Visualizer. This is currently the only place
    the Visualizer gets a dedicated mention — it no longer has its own section.
19. **Current research direction** — closing sequence-of-questions narrative + what's next.
20. **License.**

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

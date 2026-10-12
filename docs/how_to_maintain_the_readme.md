---
description: "The README has two sections that already do this right: **'Risk exposure: what GitGalaxy"
---
# How to Maintain the GitGalaxy README

The README has two sections that already do this right: **"Risk exposure: what GitGalaxy
claims"** (full text now in `docs/validation.md`'s "What the Structural Surface Profile
claims", with a short summary in the README) and **"Evidence, not just claims"** (now folded
into the README's "Accuracy, measured") (renamed from "What GitGalaxy Finds — and What
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
5. **Show what it does first, then prove it, in one place.** (Changed 2026-10-12, owner
   request.) The top of the README answers "what is this and why should I care": the
   tagline, stat tiles, the pipeline diagram and the speed chart. Every stat tile carries
   its sample size and its limit in the tile caption, and links to the section that proves
   it, so rules 1 and 4 still hold on the first screen. All proof sits in **one** section,
   "Accuracy, measured", ordered proof and limitations before adoption, adoption before
   licensing. Do not scatter evidence into a second or third section again (the pre-2026-10-12
   README had three).

## Section order (current target state, as of the 2026-10-12 front-page restructure)

The 2026-10-12 restructure borrowed the *layout* (not the wording) of strong product READMEs:
benefit-first tagline, stat tiles, a nav row, "you ask / you get" tables, and a "pick your
front door" table, because the README covers two products (the scanner and the COBOL-to-Java
translator). The long proof prose moved to `docs/validation.md`. Edit it there.

1. **Hero** (centered): name, the benefit tagline ("Know any codebase deeply, and give your
   AI agents the same knowledge."), a three-sentence description covering both products,
   four stat tiles (Kubernetes scan time, languages split into functions with the recognized count in the caption, matching the collapsible `#languages` table under section 2, tri-comparison function precision,
   CICS and batch programs at L2+ from the evidence report), each with n + limit + a link to its proof, then the
   nav row (Quickstart, Scanner or translator, Scanner, Translator, Evidence, Is/isn't,
   Install, Docs, Visualizer). Re-verify tile numbers when their source sections change.
2. **One scan, every language, six reports**: the sankey pipeline diagram with a caption
   that walks it left to right. It is a product illustration, not a proof, so it sits on
   top.
3. **Every size, in seconds** (`#real-world-scale` anchor kept): the self-updating
   loc_vs_time chart, the Kubernetes number and the fitted two-regime model as its rule-4
   limitation clause.
4. **Quickstart**: install, `galaxyscope`, `--llm-only` for agents, the other modes.
5. **Pick your front door**: one row per audience, linking down.
6. **The scanner** (`#one-graph-not-five-separate-tools` anchor kept): "What you ask, what
   you get" table (each answer links to a doc), "What a scan gives you" six-outputs table,
   and "The architecture brief" with the dated curl and cics-genapp excerpts. Refresh the
   excerpts by rerunning `galaxyscope --llm-only` on the same repos, not by editing numbers.
7. **CICS to Java: ported, then proven** (renamed from "COBOL to Java" 2026-10-12; keep the
   explicit `#cobol-to-java-ported-then-proven` id above it, an inbound anchor): intro, the
   scoped "iterably solvable" paragraph (always says *six public estates* and that no blind
   trial has run; links discussion #4784), the five steps, then **"Every port ships with its
   evidence"**: what an evidence record holds, the L0-L5 table (from
   `definition_of_done.md`), and one dated "Where it stands" line of totals taken from
   `docs/language_status/evidence_report/README.md`. Do not copy the per-estate table into the
   README; link the generated report, which the bot refreshes on every push to main. The
   hero's translator tile uses the same totals; update both together. Model-written ports
   stay in `<details>` with their snapshot date. "What these levels do not show" stays
   visible, never collapsed.
8. **Accuracy, measured** (`#proof-not-just-claims`, `#evidence-not-just-claims` anchors
   kept): tri-comparison ("Structural validation: GitGalaxy vs Tree-sitter vs Ctags",
   heading text is an inbound anchor), graph validation, a short Keyword Rosetta summary,
   a short "What the Structural Surface Profile claims" summary, and "The rest of the
   evidence" table (regression suite count must be a real
   `python -m pytest tests/ --collect-only -q` number). Each subsection is a few
   sentences plus its chart. History, issue numbers and ledger detail go in
   `docs/validation.md`.
9. **What GitGalaxy is, and isn't**: two short paragraphs + the tool-comparison table + one
   sentence on Git history.
10. **Privacy and deployment**: one section, never two.
11. **Installation** (+ zero-dependency mode, CI/CD).
12. **Explore further**: the link table.
13. **License.**

**Moved to `docs/validation.md` on 2026-10-12 (not cut):** the full Structural Surface
Profile section, the Temporal Crucible write-up, and the long Keyword Rosetta paragraph
(its numbers updated in validation.md's own Rosetta section).

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

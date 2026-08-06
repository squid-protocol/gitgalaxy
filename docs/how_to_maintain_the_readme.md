# How to Maintain the GitGalaxy README

The README has two sections that already do this right: **"What GitGalaxy Finds — and What
It Doesn't Claim"** and **"Proof, Not Just Claims."** Both state a limitation before a reader
has to find it, and every claim links to something inspectable (a test count, an epic, a
corpus). Treat those two sections as the tone bar for every other section — not because
they're the least interesting content in the README, but because they're the only sections
that would survive a staff engineer asking "show me the benchmark."

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
   existing COBOL-tool line is the pattern to copy everywhere else: "Achieved a 27/27 Maven
   compile success rate... Compiling is a necessary but not sufficient signal of a correct
   translation... a business logic review is still required." A benchmark bullet with no
   named limitation is an incomplete benchmark bullet.
5. **New sections are ordered by how a skeptical reader would trust them, not how exciting
   they are.** Proof and limitations before benchmarks; benchmarks before adoption numbers;
   adoption numbers before enterprise/licensing. A skeptical engineer reads in that order —
   the README should match.

## Section order (current target state)

1. Badges — only ones with a real link behind them (License, PyPI version, Python version,
   CI status). Drop any badge that's a bare label with no destination.
2. One-paragraph description — plain terms first; the BLAST/genomics analogy can follow as an
   aside, not the primary explanation.
3. Proof strip — the `1 scan · 97 structural signals · 50+ languages · 0 need for
   compilation / 19 risk exposure scores · 6 final reports · 0 dependencies` line. Keep this
   verbatim — it's already the right shape (hard numbers, no adjectives) and doesn't need
   linking per-number since the sections immediately below back it up.
4. Architecture / pipeline diagram.
5. **What It Finds — and Doesn't Claim** (the tone-bar section — do not rewrite its prose,
   only relocate it if needed).
6. Weakness Classes, Not Just CVEs.
7. **Proof, Not Just Claims** (the other tone-bar section).
8. Benchmarks — every bullet follows rule 4 above.
9. Real-World Adoption — deliberately below Benchmarks. Stars/downloads are a popularity
   signal, not a correctness signal.
10. Installation & CI/CD Integration.
11. Tools & Use Cases — keep the pattern of an embedded benchmark per tool (that's rule 4
    already applied); cut standalone adjectives that don't carry a number ("extreme-velocity,"
    "hunts undocumented vulnerabilities").
12. Visualizer.
13. Data Privacy — one section, not two. If a future edit reintroduces a second privacy
    section (it has happened once already — "Data Privacy & On-Premise Deployment" and
    "Zero-Trust Data Security" said the same three things in two places), merge them back.
14. Licensing.

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
and `docs/how_to_write_release_notes.md` for the sibling guide covering release notes (same
underlying rules, applied to a different surface).

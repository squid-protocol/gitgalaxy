---
name: readme-maintenance
description: Develop, edit, or status-check the GitGalaxy README (and by extension tests/README.md) against the project's tone and evidence rules -- keeps new claims paired with links/numbers, keeps section order trust-ranked, and tracks which future claims are staged vs. shipped. Use when the user asks to update the README, add or reorder a README section, do a tone/quality pass on README.md, or check "readme status" / what's staged in the evidence roadmap.
---

Source of truth is `docs/how_to_maintain_the_readme.md` (the five style rules + target
section order) and `docs/readme_evidence_roadmap.md` (the living list of claims gated on
evidence that doesn't exist yet, plus the two items that are ready to build now). Read both
directly rather than reconstructing them from this file — they carry the actual rules,
current section order, and roadmap state, all of which will drift out of sync with any
summary kept here.

## Editing README.md

1. Read the two tone-bar sections first if you haven't recently — "What GitGalaxy Finds — and
   What It Doesn't Claim" and "Proof, Not Just Claims." Every other section is edited toward
   matching their register, not the other way around.
2. For a new claim: does it already have something in this repo a reader could click to
   verify (a test count, a corpus, a benchmark script)? If yes, write it with the link. If
   no, it belongs in `docs/readme_evidence_roadmap.md` as a new gated row with a concrete
   activation trigger — do not write it into README.md ahead of the evidence, even
   provisionally.
3. New or moved sections follow the trust-ordering in `how_to_maintain_the_readme.md`'s
   section-order list (proof and limitations before benchmarks, benchmarks before adoption
   numbers, adoption before licensing).
4. Run the five-rule self-check from the doc against your actual diff before considering the
   edit done — not a vibe check, line by line.
5. If the edit unlocks a roadmap item (e.g. a comparison script landed, a case study got
   written), move that row from "Gated" to "Shipped" in `readme_evidence_roadmap.md` in the
   same PR, and add the claim to README.md itself.

## "Readme status" checks

When asked for the README's current status (not asked to edit it): report which roadmap items
are Do-Now vs. Gated vs. Shipped from `readme_evidence_roadmap.md`, and whether README.md's
current section order/content still matches `how_to_maintain_the_readme.md`'s target state —
call out specific drift (a reintroduced duplicate section, an unlinked superlative, an emoji
heading) rather than a general impression.

## Scope beyond README.md

`tests/README.md` carries the same drift risk and is worth a glance on any dedicated tone
pass (not every routine README.md edit) — see the "Same Pass, Two Other Files" precedent: real
substance (3,649 tests, 45 languages) undersold by framing like "Mathematical Proofs" and
"widely considered impossible." Apply the same five rules there if asked to extend the pass,
but don't rewrite it unprompted as a side effect of an unrelated README.md edit.

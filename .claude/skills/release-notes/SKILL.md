---
name: release-notes
description: Draft or review GitGalaxy GitHub release notes in the project's established tone -- dry, specific, evidence-first (the v2.4.5 style), not enthusiasm-first (the v2.4.6 anti-pattern). Use when the user asks to write release notes, draft a changelog entry for a new tag, or review/tone-check an existing draft before publishing.
---

Source of truth is `docs/how_to_write_release_notes.md` — read it directly, it has the full
4-beat template (found / why nothing caught it / what we did / known limitations), the five
sentence-level rules, and real before/after quotes pulled from this repo's own v2.4.5 vs
v2.4.6 release notes. Don't paraphrase from memory of this skill file; the doc has the actual
examples.

## Drafting a new release note

1. Get the real change set before writing anything: `git log <previous-tag>..HEAD --oneline`
   (or `..<new-tag>` if the tag already exists), plus `gh pr list --state merged --search
   "merged:>=<date>"` or the closed-issue list for the cycle. Draft from the actual diff, not
   from a recollection of "what this cycle felt like" — the template's specificity
   requirement depends on having real specifics in front of you.
2. Sort changes into: fixes/behavior-changes (get the full 4-beat treatment) vs. pure
   additions (beats 1/3/4 collapse into one or two lines each; beat 2 only applies when
   something should have caught a bug and didn't).
3. Draft using the template. For every adjective describing scale or quality ("major,"
   "massive," "robust," "blistering"), either replace it with the actual number/fact or cut
   the sentence.
4. Self-check against the doc's "Don't" quote (the v2.4.6 excerpt) — if a sentence in the
   draft could be swapped into that quote unchanged, rewrite it.
5. Confirm the limitations beat is present and specific to this release, not boilerplate.
   "No known issues" is fine if genuinely true; a missing beat reads as "didn't check."

## Reviewing an existing draft

Read it once for content, then once purely against the five rules in the doc (number vs.
adjective, mechanism vs. metaphor, limitations stated, no unearned superlatives, no emoji
headings). Flag specific sentences, don't just say "make it less marketing-y" — point at the
clause and what it's missing (a number, a link, a limitation).

## After drafting

If the release touches parsing/detector/language-standards code, cross-check the note's
claims against what `crucible_check.py` / the golden-master diff actually showed for this
cycle — don't let the note claim a scope of testing broader than what was actually run.

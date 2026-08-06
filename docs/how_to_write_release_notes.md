# How to Write a GitGalaxy Release Note

Every GitHub release under squid-protocol/gitgalaxy gets read by two very different
audiences at once: someone deciding whether to upgrade, and a skeptical engineer deciding
whether to trust the project at all. The second audience is the one that catches drift —
and GitGalaxy has drifted before. Read `docs/readme_evidence_roadmap.md` for the fuller
context on why tone discipline matters here; this doc is the release-note-specific
mechanics of applying it.

## The house template

Four beats, in this order, for any release note that includes a bug fix or behavior
change (a pure feature-addition release can drop beat 2):

1. **What we found** — the concrete symptom or gap, stated plainly. Name the file,
   function, or config key if there is one.
2. **Why nothing caught it** (skip if nothing should have) — the actual mechanism that
   let it through: a mock that drifted from real config, a missing test case, a silent
   fallback. This is the beat that makes a release note trustworthy instead of just
   reassuring — it shows the fix wasn't luck.
3. **What we did** — the actual change, in engineering terms (renamed keys, added a
   regression test, wired a new CI gate) — not in outcome-adjective terms ("now rock
   solid").
4. **Known limitations, documented and deferred on purpose** — what the fix does *not*
   cover, scoped explicitly as a follow-up rather than glossed over. If there's nothing
   left out, say so in one line rather than omitting the beat — omission reads as
   "didn't check," not "nothing to report."

This is the v2.4.5 shape (`v2.4.5 - The Correctness Release`), not the v2.4.6 shape. Both
exist in this repo's release history — v2.4.6 is the example of what happens when the
template is dropped: enthusiasm words stand in for beats 1 and 2, and there's no limitations
section at all.

## Before / after, from this repo's own history

**Don't** (v2.4.6):
> "We are incredibly excited to announce the release of GitGalaxy v2.4.6... GitGalaxy has
> officially transitioned from a 'best-effort parser' to a production-grade, mathematically
> verified forensic security engine... We threw the kitchen sink at our regex engine to see
> where it would break."

Every clause here is an assertion about how the reader should feel, not a fact about what
changed. "Mathematically verified" and "production-grade" are unfalsifiable as written —
verified how, against what, according to whom?

**Do** (v2.4.5):
> "What we found: ... `prism.py`, the module responsible for stripping comments from source
> before analysis, was looking up its per-language delimiter rules under config keys that no
> producer in the codebase had ever written... Why nothing caught it: `test_prism.py`'s test
> fixtures were hand-built mocks that mirrored the *wrong* key names... What we did: Renamed
> the lookups to match the real taxonomy... Known limitations, documented and deferred on
> purpose: a 9-delimiter gap in `standard_block` affects 5 non-C-style languages, and
> `golden_master.json` was not regenerated as part of this fix."

Same underlying work (a real, serious bug, fixed correctly) — the second version is more
credible because it's falsifiable: every clause names a thing a reader could go check.

## Five rules, applied at the sentence level

1. **A number beats an adjective.** Not "much faster" — the actual before/after, or the
   actual test count, or the actual line count removed. If you don't have the number yet,
   that's a signal the change needs more instrumentation before it needs a release note,
   not a reason to reach for an adjective instead.
2. **Name the mechanism, not the metaphor.** "Hardened the regex engine" needs a next
   sentence saying which rules, which languages, what kind of hardening (ReDoS bound, added
   negative-match case, fixed a boundary bug) — the metaphor can label the section, not
   replace the explanation.
3. **State what's still broken or deferred.** Every fix has a scope boundary. Naming it
   costs one sentence and is the single highest-credibility line in the note — see the
   v2.4.5 example above.
4. **No unearned superlatives.** "Massive," "blistering," "incredible" describe the writer's
   emotional state, not the reader's evidence. If the number really is large, state the
   number and let the reader do the feeling.
5. **No emoji as a heading decorator.** Emoji in a section title (🚀, 🛡️, 🧪) reads as
   marketing regardless of what's under it. Plain section headings only.

## Process for drafting a release note

1. Pull the actual change set: `git log <previous-tag>..<new-tag> --oneline`, plus the
   PRs/issues it closes. Don't draft from memory of "what this cycle felt like" — the
   template's specificity requirement means you need the real diff in front of you.
2. Group changes into beats: what's a "found/fixed" item (needs the 4-beat treatment) vs.
   a pure addition (skip beat 2, keep 1/3/4 collapsed into one line if it's small).
3. Draft using the template above. For every sentence with an adjective describing scale or
   quality ("major," "significant," "robust"), either replace it with the number or cut it.
4. Read it back against the "Don't" example above — if a sentence in your draft could be
   swapped into that quote unchanged, rewrite it.
5. Check the limitations beat is present and specific. "No known issues" is fine if true;
   a missing beat is not.

See also `.claude/skills/release-notes/SKILL.md` for the skill wrapper that walks this
process, and `docs/how_to_maintain_the_readme.md` for the sibling guide covering the README
itself (same underlying tone rules, different surface).

---
description: "The locked method for meeting a new estate: scan, post the evidence, reflect and close the error classes, try the next one. 17 blind draws; the rules that keep first contact honest."
---
# Estate trial methodology

*Owner, 2026-11-08. This is the method behind the [estate journey](estate_journey.md). The operational checklist is the
`estate-trial` skill (`.claude/skills/estate-trial/SKILL.md`); the rules are
`.claude/rules/mainframe-evidence-policy.md`; the pre-registration is [estate4_preregistration.md](estate4_preregistration.md).*

## The cycle

Every estate goes through the same four steps, and the next estate starts only after the fourth:

1. **Scan.** Freeze `main`, record its SHA as T0, and run the translator over the estate exactly as it is. The T0
   number is **first contact**. It is never revised upward, only corrected when the count itself was wrong.
2. **Post the evidence.** Publish the T0 numbers and the gap table (counts and scrubbed gap classes only) in the
   trial's issue, before any fix.
3. **Reflect and close the error classes.** Each gap gets an owner issue. Fixes close the whole class, prove
   themselves on our own fixtures or burned programs, and are re-measured after each merge. Every gap is one of:
   - **fixed** (the translator or engine was wrong);
   - **named** (a source or clone defect, with an IBM citation or independent clone evidence and a review: rule 10);
   - **left open with a reason** (frontier or product dependency).
4. **Try again.** Run the pre-draw gates, write the estate's lessons into the [journey](estate_journey.md), and draw
   the next estate.

A trial's chart has one point per re-measure: merged PRs since first contact on the x axis, and the share of the
estate's programs at its level on the y axis.

## What is measured

| Estate kind | Level measured | Why |
|---|---|---|
| Development (burned) estates | **L2 executed equivalent** and above (L3, L4, L5) | Cases are written for them; the Java is run against the COBOL oracle |
| Census and blind estates | **L1 translated whole**, plus **accounted** | Rule 2: no cases on an estate that is not burned; rule 3: nobody reads its code |

The two are never on one axis. "Accounted" = whole, plus programs whose every gap is a named source defect.

## The blind draws

- **17 candidates**, chosen from metadata only, committed with a random-draw method on 2026-10-05
  ([candidates](estate4_candidates.md)). The first draw (2026-11-07) spent one, so **16 remain**.
- The draw runs **only at T0**, after the preflight passes and `main` is frozen. Nobody looks at the candidates before.
- A drawn estate becomes trialled. It is never drawn again, and after close-out it may become a development estate
  (owner's choice).
- Counting a candidate's code, even by tools, spends it. Corpus-wide measurements exclude every remaining candidate
  by name.

## Pre-draw gates (before every draw)

- `cics_census.py preflight --t0 SHA` with 0 findings: programs vs copy members, unknown copybook prefixes, every
  gap-map owner open, T0 recorded.
- Every source-defect row carries an IBM citation or independent clone evidence (a test enforces it, #8067).
- The lessons of the last estate are closed as classes or have open owners. After the first blind estate these are:
  - **copybook resolution checked independently** of the engine's resolver (#8111);
  - **compile listings and duplicates excluded** from the program basis (#8112);
  - **clone evidence from an independent search** (#8113).

## Corrections

A correction fixes the **count**, never the rules. It is recorded in the trial issue with both numbers kept
published. Example: the first blind estate was restated from 58 to 29 programs, because 29 were compile-listing
copies (#8073).

## Journal

Assumptions, surprises and corrections go into the journal of [estate_journey.md](estate_journey.md), dated, with
their issue or PR. Statements of work between estates do not.

# Third-party material policy

GitGalaxy's research compares COBOL→Java translations made by others: IBM WCA4Z, Devin (Cognition) workshops, SENTINEL IDE (NOAH Labs), Lightyear, lasserre-consulting, and more. This policy keeps that work conservative and clearly lawful. It applies to people and agents alike. It is a working practice, not legal advice. Anything commercial, or any doubt, goes to a lawyer.

## Rules

1. **Flag first.** Stop and ask the maintainer before any step that might be legally questionable:
   - copying or vendoring third-party code or files;
   - using material that has no licence;
   - quoting more than a few lines;
   - using third-party names or branding in a way that could suggest endorsement;
   - sending third-party or confidential material to an outside service;
   - shipping a feature inspired by a vendor's method for commercial use.
2. **Borrow ideas, not code.** Techniques, methods and published ideas may be implemented here independently, from observation, measurement or the published description. Code, text and other expression may not be copied. Record where each idea came from in the commit, the PR and the docs (e.g. "typed values: learned from the observational study §10; our own implementation").
3. **Never commit third-party code.** That includes permissively licensed code, unless the maintainer explicitly approves a specific case. In that case, follow the licence exactly: licence text, copyright and NOTICE kept, changes marked.
4. **Unlicensed sources** (no LICENSE file means all rights reserved, whatever a README badge says) may be run locally for evaluation from a pinned commit. They are fetched at run time, never committed, and quoted only briefly with attribution.
5. **Adapters are ours.** A harness adapter around third-party code must be our own code, kept minimal, committed separately, and must never modify the third-party code it wraps.
6. **Patents.** Before commercial use of a feature inspired by another party's method (e.g. #4175, scenario generation from path conditions, inspired by IBM's published papers), check for relevant patents or get legal review.
7. **Blameless reporting.** Describe third-party results factually, with pinned versions, and judge each piece of work by what it attempted. Never present it as representing a product beyond the artifact actually measured.

## Current sources

| Source | Licence | Our use |
|---|---|---|
| AWS CardDemo | Apache-2.0 | Corpus (pinned); fixtures with licence |
| CBSA, GenApp | EPL-2.0 | Corpus (pinned); fixtures with licence |
| IBM DBB MortgageApplication | per its repository (verify on onboarding) | Corpus (pinned) |
| Devin workshop repos (Cognition-Partner-Workshops, codev-workshops) | Apache-2.0 | Run at pinned SHAs; not vendored |
| IBM validation-c2j (WCA4Z LGACDB01) | none | Run at pinned SHA; brief quotes only |
| SENTINEL IDE port (noahlabsai) | none (badge only) | Run at pinned SHA; brief quotes only |
| Lightyear (howardweale), lasserre-consulting | none | Run or scanned at pinned SHAs; brief quotes only |
| xavierxmorris Azure slice | Apache-2.0 | Surveyed only |
| viniman27 API-recovery study | none | Surveyed only |

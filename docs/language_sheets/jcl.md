# jcl

Context: legacy/mainframe

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 186 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | not measured | | | | |
| Call links | not measured | | | | |
| Imports | not measured | | | | |
| Keywords | not measured | | | | |
| Rosetta | 52 of 52 passed, 0 failed | 52 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |
| Answer key | 100% precision / 100% recall; 68% of 2,792 facts cross-verified, weakest tier draft | 2,792 facts | answer-key | answer key over 8 corpora, 5 fields; weakest tier draft | `tests/cobol_mainframe/ground_truth_ledger.json` |

## Answer key fields

The engine against hand-built answer keys: a separately written reader drafted each key, and blind LLM reviewers
re-read the source. The reviewers are LLMs, not people, and no field has a human sign-off. The tier is the
weakest review behind a field in each corpus; the mix column counts facts per tier.

| field | facts | engine matched | engine reported | tier mix |
|---|---|---|---|---|
| JCL job flow | 1,784 | 1,784 | 1,784 | 1,618 cross_verified, 166 draft |
| JCL resolved DSNs | 830 | 830 | 830 | 105 cross_verified, 647 sample_verified, 78 draft |
| DD names | 89 | 89 | 89 | 89 cross_verified |
| JCL runner programs | 86 | 86 | 86 | 86 cross_verified |
| job submissions | 3 | 3 | 3 | 3 cross_verified |

[All languages](README.md)

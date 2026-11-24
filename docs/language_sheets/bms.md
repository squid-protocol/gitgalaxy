# bms

Context: legacy/mainframe

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 10 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | not measured | | | | |
| Call links | not measured | | | | |
| Imports | not measured | | | | |
| Keywords | not measured | | | | |
| Rosetta | 38 of 38 passed, 0 failed | 38 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |
| Answer key | 100% precision / 100% recall; 56% of 9,945 facts cross-verified, weakest tier draft | 9,945 facts | answer-key | answer key over 5 corpora, 2 fields; weakest tier draft | `tests/cobol_mainframe/ground_truth_ledger.json` |

## Answer key fields

The engine against hand-built answer keys: a separately written reader drafted each key, and blind LLM reviewers
re-read the source. The reviewers are LLMs, not people, and no field has a human sign-off. The tier is the
weakest review behind a field in each corpus; the mix column counts facts per tier.

| field | facts | engine matched | engine reported | tier mix |
|---|---|---|---|---|
| symbolic maps | 7,800 | 7,800 | 7,800 | 5,307 cross_verified, 2,493 draft |
| BMS screen fields | 2,145 | 2,145 | 2,145 | 286 cross_verified, 1,579 sample_verified, 280 draft |

[All languages](README.md)

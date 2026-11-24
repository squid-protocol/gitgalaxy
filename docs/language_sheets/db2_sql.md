# db2_sql

Context: legacy/mainframe

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 10 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | not measured | | | | |
| Call links | not measured | | | | |
| Imports | not measured | | | | |
| Keywords | decoy test only (2) |  | decoy-test |  | `tests/family_validity_baseline.json` |
| Rosetta | 56 of 57 passed, 1 failed | 57 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |
| Answer key | 100% precision / 100% recall; 89% of 127 facts cross-verified, weakest tier draft | 127 facts | answer-key | answer key over 5 corpora, 2 fields; weakest tier draft | `tests/cobol_mainframe/ground_truth_ledger.json` |

## Answer key fields

The engine against hand-built answer keys: a separately written reader drafted each key, and blind LLM reviewers
re-read the source. The reviewers are LLMs, not people, and no field has a human sign-off. The tier is the
weakest review behind a field in each corpus; the mix column counts facts per tier.

| field | facts | engine matched | engine reported | tier mix |
|---|---|---|---|---|
| DB2 table access | 71 | 71 | 71 | 58 cross_verified, 13 draft |
| DB2 table columns | 56 | 56 | 56 | 55 cross_verified, 1 draft |

[All languages](README.md)

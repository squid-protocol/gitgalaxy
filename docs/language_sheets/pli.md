# pli

Context: legacy/mainframe

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 3 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | not measured | | | | |
| Call links | not measured | | | | |
| Imports | not measured | | | | |
| Keywords | decoy test only (11) |  | decoy-test |  | `tests/family_validity_baseline.json` |
| Rosetta | 58 of 58 passed, 0 failed | 58 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |
| Answer key | 100% precision / 100% recall; 0% of 16,513 facts cross-verified, weakest tier draft | 16,513 facts | answer-key | answer key over 2 corpora, 4 fields; weakest tier draft | `tests/cobol_mainframe/ground_truth_ledger.json` |

## Answer key fields

The engine against hand-built answer keys: a separately written reader drafted each key, and blind LLM reviewers
re-read the source. The reviewers are LLMs, not people, and no field has a human sign-off. The tier is the
weakest review behind a field in each corpus; the mix column counts facts per tier.

| field | facts | engine matched | engine reported | tier mix |
|---|---|---|---|---|
| PL/I call sites | 8,014 | 8,014 | 8,014 | 8,014 sample_verified |
| PL/I layouts | 6,729 | 6,729 | 6,729 | 27 cross_verified, 6,702 sample_verified |
| PL/I data moves | 1,657 | 1,657 | 1,657 | 1,657 sample_verified |
| PL/I record fields | 113 | 113 | 113 | 113 draft |

[All languages](README.md)

# pli

Context: legacy/mainframe

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 3 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | not measured | | | | |
| Call links | not measured | | | | |
| Imports | not measured | | | | |
| Keywords | decoy test only (35) |  | decoy-test |  | `tests/family_validity_baseline.json` |
| Rosetta | 58 of 58 passed, 0 failed | 58 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |
| Answer key | 100% precision / 100% recall; 0% of 24,080 facts cross-verified, weakest tier draft; blind review of 1,481 sampled items found 3 key errors (at most 0.5% at 95%) | 24,080 facts | answer-key | answer key over 2 corpora, 4 fields; weakest tier draft | `tests/cobol_mainframe/ground_truth_ledger.json` |

## Answer key fields

The engine against hand-built answer keys: a separately written reader drafted each key, and blind LLM reviewers
re-read the source. The reviewers are LLMs, not people, and no field has a human sign-off. The tier is the
weakest review behind a field in each corpus; the mix column counts facts per tier.

| field | facts | engine matched | engine reported | tier mix |
|---|---|---|---|---|
| PL/I data moves | 9,224 | 9,224 | 9,224 | 9,224 sample_verified |
| PL/I call sites | 8,014 | 8,014 | 8,014 | 8,014 sample_verified |
| PL/I layouts | 6,729 | 6,729 | 6,729 | 27 cross_verified, 6,702 sample_verified |
| PL/I record fields | 113 | 113 | 113 | 113 draft |

### How much of the key was re-read

For the large fields a blind reviewer re-read a sample of the key's facts, not every fact. The error counts are
findings against the key **as first drafted**: where a review found a reader defect, it was fixed afterwards, so
the bound is a conservative one for the key as it is now. A sample bounds the key's error rate; it does not prove
the unsampled facts correct.

| section | items asked | key errors | upper bound on key error (95%) |
|---|---|---|---|
| pli_calls | 317 | 2 | 1.89% |
| pli_layouts | 309 | 0 | 0.97% |
| pli_moves | 359 | 1 | 1.24% |
| pli_resources | 363 | 0 | 0.82% |
| pli_uow | 133 | 0 | 2.23% |
| **all** | **1,481** | **3** | **0.51%** |

[All languages](README.md)

# csd

Context: legacy/mainframe

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | not measured | | | | |
| Functions | not measured | | | | |
| Call links | not measured | | | | |
| Imports | not measured | | | | |
| Keywords | decoy test only (3) |  | decoy-test |  | `tests/family_validity_baseline.json` |
| Rosetta | not measured | | | | |
| Answer key | 100% precision / 100% recall; 100% of 501 facts cross-verified, weakest tier cross_verified | 501 facts | answer-key | answer key over 5 corpora, 1 fields; weakest tier cross_verified | `tests/cobol_mainframe/ground_truth_ledger.json` |

## Answer key fields

The engine against hand-built answer keys: a separately written reader drafted each key, and blind LLM reviewers
re-read the source. The reviewers are LLMs, not people, and no field has a human sign-off. The tier is the
weakest review behind a field in each corpus; the mix column counts facts per tier.

| field | facts | engine matched | engine reported | tier mix |
|---|---|---|---|---|
| CSD resources | 501 | 501 | 501 | 501 cross_verified |

[All languages](README.md)

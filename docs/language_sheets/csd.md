# csd

Context: legacy/mainframe

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | not measured | | | | |
| Functions | not measured | | | | |
| Call links | not measured | | | | |
| Imports | not measured | | | | |
| Keywords | not measured | | | | |
| Rosetta | not measured | | | | |
| Answer key | 100% precision / 100% recall; 91% of 501 facts cross-verified, weakest tier draft | 501 facts | answer-key | answer key over 5 corpora, 1 fields; weakest tier draft | `tests/cobol_mainframe/ground_truth_ledger.json` |

## Answer key fields

The engine against hand-built answer keys: a separately written reader drafted each key, and blind LLM reviewers
re-read the source. The reviewers are LLMs, not people, and no field has a human sign-off. The tier is the
weakest review behind a field in each corpus; the mix column counts facts per tier.

| field | facts | engine matched | engine reported | tier mix |
|---|---|---|---|---|
| CSD resources | 501 | 501 | 501 | 457 cross_verified, 44 draft |

[All languages](README.md)

# jcl

Context: legacy/mainframe

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 186 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | not measured | | | | |
| Call links | not measured | | | | |
| Imports | not measured | | | | |
| Keywords | 7 of 25 families: 6 >90, 1 75-50; 7 more decoy-tested only | 402 oracle functions | tree-sitter | parser-labelled functions, lower of recall and precision per family | `tests/family_validity_baseline.json` |
| Rosetta | 52 of 52 passed, 0 failed | 52 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |
| Answer key | 100% precision / 100% recall; 75% of 2,792 facts cross-verified, weakest tier sample_verified; blind review of 442 sampled items found 0 key errors (at most 0.7% at 95%) | 2,792 facts | answer-key | answer key over 8 corpora, 5 fields; weakest tier sample_verified | `tests/cobol_mainframe/ground_truth_ledger.json` |

## Answer key fields

The engine against hand-built answer keys: a separately written reader drafted each key, and blind LLM reviewers
re-read the source. The reviewers are LLMs, not people, and no field has a human sign-off. The tier is the
weakest review behind a field in each corpus; the mix column counts facts per tier.

| field | facts | engine matched | engine reported | tier mix |
|---|---|---|---|---|
| JCL job flow | 1,784 | 1,784 | 1,784 | 1,784 cross_verified |
| JCL resolved DSNs | 830 | 830 | 830 | 145 cross_verified, 685 sample_verified |
| DD names | 89 | 89 | 89 | 89 cross_verified |
| JCL runner programs | 86 | 86 | 86 | 86 cross_verified |
| job submissions | 3 | 3 | 3 | 3 cross_verified |

### How much of the key was re-read

For the large fields a blind reviewer re-read a sample of the key's facts, not every fact. The error counts are
findings against the key **as first drafted**: where a review found a reader defect, it was fixed afterwards, so
the bound is a conservative one for the key as it is now. A sample bounds the key's error rate; it does not prove
the unsampled facts correct.

| section | items asked | key errors | upper bound on key error (95%) |
|---|---|---|---|
| dsns | 442 | 0 | 0.68% |
| **all** | **442** | **0** | **0.68%** |

[All languages](README.md)

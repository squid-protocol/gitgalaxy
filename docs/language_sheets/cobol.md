# cobol

Context: legacy/mainframe

## What was possible

> Unconfirmed: these statements are a draft until the search log is signed off.

- **Parsers found:** A tree-sitter COBOL grammar exists in tree-sitter-language-pack, but the tree-sitter accuracy audit has no node map for it yet, so functions are not compared against tree-sitter. GnuCOBOL is the runtime oracle for the equivalence work.
- **Public corpus:** Nine pinned open estates keyed by hand: CardDemo, CBSA, GenApp, zECS, DSF, DBB MortgageApplication, example-health-apis, zopeneditor-sample and the cicsdev async credit-card example (168 programs).
- **Reference analyser:** None independent of this repo's own answer-key reader.
- **Best method:** A hand-built answer key from a separately written reader, re-read by blind LLM reviewers (cross_verified). No mainframe engineer has signed any field (human_signed).
- **Why:** Proprietary mainframe dialects (IBM Enterprise COBOL, CICS, Db2), few public parsers, and estates that are hard to obtain.

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 570 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 100% precision / 100% recall | 2,527 units | answer-key | answer key over 9 corpora, 168 programs (paragraphs and sections); weakest tier cross_verified | `tests/cobol_mainframe/ground_truth_ledger.json` |
| Call links | 100% precision / 92.9% recall | 2,717 edges | answer-key | answer key over 9 corpora, 168 programs (PERFORM and GO TO edges inside a program); weakest tier draft | `tests/cobol_mainframe/ground_truth_ledger.json` |
| Imports | 98.1% precision / 100% recall | 503 copybook paths | answer-key | answer key over 9 corpora, 168 programs (COPY members resolved to a file); weakest tier cross_verified | `tests/cobol_mainframe/ground_truth_ledger.json` |
| Keywords | 3 of 56 families: 2 >90, 1 90-75 | 3,895 oracle functions | tree-sitter | parser-labelled functions, lower of recall and precision per family | `tests/family_validity_baseline.json` |
| Rosetta | 58 of 58 passed, 0 failed | 58 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |
| Answer key | 100% precision / 99.5% recall; 18% of 41,057 facts cross-verified, weakest tier draft; blind review of 4,200 sampled items found 105 key errors (at most 2.9% at 95%) | 41,057 facts | answer-key | answer key over 9 corpora, 32 fields; weakest tier draft | `tests/cobol_mainframe/ground_truth_ledger.json` |

## Answer key fields

The engine against hand-built answer keys: a separately written reader drafted each key, and blind LLM reviewers
re-read the source. The reviewers are LLMs, not people, and no field has a human sign-off. The tier is the
weakest review behind a field in each corpus; the mix column counts facts per tier.

| field | facts | engine matched | engine reported | tier mix |
|---|---|---|---|---|
| data moves | 13,905 | 13,905 | 13,905 | 13,905 sample_verified |
| record fields | 6,270 | 6,270 | 6,270 | 6,270 sample_verified |
| CICS resources | 3,699 | 3,699 | 3,699 | 448 cross_verified, 3,251 sample_verified |
| unit extents | 2,923 | 2,922 | 2,923 | 186 cross_verified, 2,024 llm_verified, 713 draft |
| copybook layouts | 2,759 | 2,759 | 2,759 | 628 cross_verified, 2,131 sample_verified |
| intra-program edges | 2,717 | 2,525 | 2,525 | 178 cross_verified, 1,811 llm_verified, 728 draft |
| units of work and handlers | 2,643 | 2,643 | 2,643 | 882 cross_verified, 1,761 sample_verified |
| units | 2,527 | 2,527 | 2,527 | 2,527 cross_verified |
| CICS RIDFLD | 781 | 781 | 781 | 92 cross_verified, 689 sample_verified |
| copybook paths | 503 | 503 | 513 | 503 cross_verified |
| refmod spans | 373 | 373 | 373 | 373 cross_verified |
| dynamic call targets | 306 | 306 | 306 | 306 cross_verified |
| file I/O moves | 247 | 247 | 247 | 247 cross_verified |
| CICS task control | 223 | 223 | 223 | 56 cross_verified, 167 sample_verified |
| call targets | 202 | 202 | 202 | 202 cross_verified |
| MOVE truncation | 187 | 187 | 192 | 187 sample_verified |
| dead (differs by design, not in the aggregate) | 177 | 125 | 332 | 177 cross_verified |
| program_id | 168 | 168 | 168 | 168 cross_verified |
| CALL USING | 153 | 153 | 153 | 153 cross_verified |
| file control | 89 | 89 | 89 | 89 cross_verified |
| entry transactions | 62 | 62 | 62 | 62 cross_verified |
| inputs | 55 | 55 | 55 | 55 cross_verified |
| dead (non-trivial) (differs by design, not in the aggregate) | 42 | 33 | 240 | 42 cross_verified |
| IMS definitions | 39 | 39 | 39 | 39 cross_verified |
| outputs | 37 | 37 | 37 | 37 cross_verified |
| DL/I calls | 36 | 36 | 36 | 36 cross_verified |
| JCICS | 36 | 36 | 36 | 36 cross_verified |
| VSAM defines | 30 | 30 | 30 | 30 cross_verified |
| MQ calls | 22 | 22 | 22 | 22 cross_verified |
| IMS segment access | 21 | 21 | 21 | 21 cross_verified |
| web services | 18 | 18 | 18 | 18 cross_verified |
| IMS access check | 15 | 15 | 15 | 15 cross_verified |
| async children | 6 | 6 | 6 | 6 cross_verified |
| dynamic CALLs | 5 | 5 | 5 | 5 cross_verified |

### How much of the key was re-read

For the large fields a blind reviewer re-read a sample of the key's facts, not every fact. The error counts are
findings against the key **as first drafted**: where a review found a reader defect, it was fixed afterwards, so
the bound is a conservative one for the key as it is now. A sample bounds the key's error rate; it does not prove
the unsampled facts correct.

| section | items asked | key errors | upper bound on key error (95%) |
|---|---|---|---|
| data_moves | 2,392 | 17 | 1.05% |
| records | 1,808 | 88 | 5.77% |
| **all** | **4,200** | **105** | **2.93%** |

## Notes

- **Functions:** Paragraphs and sections (the `units` field) against the answer key, summed over 9 corpora. The reviewers are LLMs, not people. The answer key shares no code with the engine.
- **Call links:** PERFORM and GO TO edges inside a program (`intra-program edges`). Recall is 92.6% because 184 of the 192 missed edges are a defect recorded in the ground-truth ledger: GO TO ... DEPENDING records only its first target (the ledger cites #4244). 8 are by design: a GO TO back to the paragraph it is in is not recorded (#3362). Some corpora's edges are still at the draft tier, so the row's weakest tier is draft. CALL targets alone are 202 of 202, cross_verified.
- **Imports:** COPY members resolved to a file (`copybook paths`). The 10 extra paths are by design: IBM-supplied system copybooks are resolved to a shipped stand-in (#8120).

[All languages](README.md)

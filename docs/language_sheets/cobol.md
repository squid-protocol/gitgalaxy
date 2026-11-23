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
| Call links | 100% precision / 92.6% recall | 2,608 edges | answer-key | answer key over 9 corpora, 168 programs (PERFORM and GO TO edges inside a program); weakest tier draft | `tests/cobol_mainframe/ground_truth_ledger.json` |
| Imports | 98.1% precision / 100% recall | 503 copybook paths | answer-key | answer key over 9 corpora, 168 programs (COPY members resolved to a file); weakest tier cross_verified | `tests/cobol_mainframe/ground_truth_ledger.json` |
| Keywords | not measured | | | | |
| Rosetta | 58 of 58 passed, 0 failed | 58 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |

## Notes

- **Functions:** Paragraphs and sections (the `units` field) against the answer key, summed over 9 corpora. The reviewers are LLMs, not people. The answer key shares no code with the engine.
- **Call links:** PERFORM and GO TO edges inside a program (`intra-program edges`). Recall is 92.6% because 184 of the 192 missed edges are a defect recorded in the ground-truth ledger: GO TO ... DEPENDING records only its first target (the ledger cites #4244). 8 are by design: a GO TO back to the paragraph it is in is not recorded (#3362). Some corpora's edges are still at the draft tier, so the row's weakest tier is draft. CALL targets alone are 202 of 202, cross_verified.
- **Imports:** COPY members resolved to a file (`copybook paths`). The 10 extra paths are by design: IBM-supplied system copybooks are resolved to a shipped stand-in (#8120).

[All languages](README.md)

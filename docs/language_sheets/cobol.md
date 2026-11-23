# cobol

Context: legacy/mainframe

## What was possible

> Unconfirmed: these statements are a draft until the search log is signed off.

- **Parsers found:** GnuCOBOL is used as the runtime oracle for equivalence work in this repo. Whether a maintained public COBOL parser grammar exists for function extraction: not yet checked.
- **Public corpus:** Open COBOL estates pinned for the CICS and batch work (CardDemo, CBSA, and others); size per language-crucible: not yet counted here.
- **Reference analyser:** None found for call links or COPY resolution. Not yet searched.
- **Best method:** Hand audit plus the GnuCOBOL oracle for behaviour; no independent call-graph reference known.
- **Why:** Proprietary mainframe dialects (IBM Enterprise COBOL, CICS, Db2) and few public parsers.

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 570 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | not measured | | | | |
| Call links | not measured | | | | |
| Imports | not measured | | | | |
| Keywords | not measured | | | | |
| Rosetta | 58 of 58 passed, 0 failed | 58 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |

[All languages](README.md)

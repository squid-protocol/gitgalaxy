# makefile

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 4 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 100% recall / 100% precision | 1 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_makefile.json` |
| Call links | not measured | | | | |
| Imports | not measured | | | | |
| Keywords | decoy test only (9) |  | decoy-test |  | `tests/family_validity_baseline.json` |
| Rosetta | 57 of 57 passed, 0 failed | 57 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |

[All languages](README.md)

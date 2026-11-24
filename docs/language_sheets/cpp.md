# cpp

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 29 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 100% recall / 100% precision | 1,381 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_cpp.json` |
| Call links | 98.6% precision / 41.7% recall | 3,301 reference edges | analyser | libclang (c++) 18.1.1 | `tests/call_graph_resolution_cpp_baseline.json` |
| Imports | 99.4% precision / 100% recall | 171 imports | tree-sitter | import statements in fmtlib/fmt | `tests/import_graph_accuracy_baseline.json` |
| Keywords | decoy test only (24) |  | decoy-test |  | `tests/family_validity_baseline.json` |
| Rosetta | 59 of 59 passed, 0 failed | 59 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |

[All languages](README.md)

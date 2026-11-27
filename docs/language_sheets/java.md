# java

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 14 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 100% recall / 100% precision | 385 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_java.json` |
| Call links | 99.8% precision / 82.5% recall | 7,858 reference edges | analyser | scip-java 0.12.3 | `tests/call_graph_resolution_java_baseline.json` |
| Imports | 100% precision / 100% recall | 1,085 imports | tree-sitter | import statements in google/gson | `tests/import_graph_accuracy_baseline.json` |
| Keywords | 11 of 55 families: 8 >90, 1 90-75, 1 75-50, 1 <50; 32 more decoy-tested only | 1,450 oracle functions | tree-sitter | parser-labelled functions, lower of recall and precision per family | `tests/family_validity_baseline.json` |
| Rosetta | 59 of 59 passed, 0 failed | 59 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |
| Answer key | not measured | | | | |

[All languages](README.md)

# kotlin

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 6 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 100% recall / 100% precision | 28 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_kotlin.json` |
| Call links | 97.5% precision / 42.5% recall | 1,386 reference edges | analyser | scip-java (kotlin) 0.13.2 | `tests/call_graph_resolution_kotlin_baseline.json` |
| Imports | 100% precision / 99.2% recall | 377 imports | tree-sitter | import statements in square/kotlinpoet | `tests/import_graph_accuracy_baseline.json` |
| Keywords | 12 of 57 families: 4 >90, 2 90-75, 1 75-50, 5 <50 | 11,239 oracle functions | tree-sitter | parser-labelled functions, lower of recall and precision per family | `tests/family_validity_baseline.json` |
| Rosetta | 58 of 58 passed, 0 failed | 58 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |

[All languages](README.md)

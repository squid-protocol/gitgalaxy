# scala

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 7 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 100% recall / 100% precision | 541 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_scala.json` |
| Call links | 99.2% precision / 93.8% recall | 3,359 calls | tree-sitter | tree-sitter call nodes (which names a function calls) | `tests/call_graph_accuracy_baseline.json` |
| Imports | 100% precision / 98.3% recall | 529 imports | tree-sitter | import statements in circe/circe | `tests/import_graph_accuracy_baseline.json` |
| Keywords | 12 of 57 families: 3 >90, 3 90-75, 1 75-50, 5 <50 | 10,189 oracle functions | tree-sitter | parser-labelled functions, lower of recall and precision per family | `tests/family_validity_baseline.json` |
| Rosetta | 59 of 59 passed, 0 failed | 59 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |

[All languages](README.md)

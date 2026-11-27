# swift

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 6 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 96.9% recall / 96% precision | 351 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_swift.json` |
| Call links | 99.3% precision / 96.2% recall | 918 calls | tree-sitter | tree-sitter call nodes (which names a function calls) | `tests/call_graph_accuracy_baseline.json` |
| Imports | 100% precision / 98.8% recall | 510 imports | tree-sitter | import statements in apple/swift-argument-parser, swiftlang/swift-package-manager | `tests/import_graph_accuracy_baseline.json` |
| Keywords | 13 of 57 families: 11 >90, 2 90-75; 30 more decoy-tested only | 889 oracle functions | tree-sitter | parser-labelled functions, lower of recall and precision per family | `tests/family_validity_baseline.json` |
| Rosetta | 58 of 58 passed, 0 failed | 58 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |
| Answer key | not measured | | | | |

[All languages](README.md)

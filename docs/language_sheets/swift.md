# swift

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 6 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 100% recall / 99.2% precision | 132 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_swift.json` |
| Call links | 99.7% precision / 95.6% recall | 387 calls | tree-sitter | tree-sitter call nodes (which names a function calls) | `tests/call_graph_accuracy_baseline.json` |
| Imports | 100% precision / 98.8% recall | 510 imports | tree-sitter | import statements in apple/swift-argument-parser, swiftlang/swift-package-manager | `tests/import_graph_accuracy_baseline.json` |
| Keywords | 12 of 57 families: 2 >90, 5 90-75, 4 75-50, 1 <50 | 3,039 oracle functions | tree-sitter | parser-labelled functions, lower of recall and precision per family | `tests/family_validity_baseline.json` |
| Rosetta | 58 of 58 passed, 0 failed | 58 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |

[All languages](README.md)

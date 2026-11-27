# haskell

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 7 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 93.8% recall / 98.2% precision | 658 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_haskell.json` |
| Call links | 94.7% precision / 97.6% recall | 2,452 calls | tree-sitter | tree-sitter call nodes (which names a function calls) | `tests/call_graph_accuracy_baseline.json` |
| Imports | 100% precision / 100% recall | 139 imports | tree-sitter | import statements in koalaman/shellcheck | `tests/import_graph_accuracy_baseline.json` |
| Keywords | decoy test only (38) |  | decoy-test |  | `tests/family_validity_baseline.json` |
| Rosetta | 58 of 58 passed, 0 failed | 58 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |
| Answer key | not measured | | | | |

[All languages](README.md)

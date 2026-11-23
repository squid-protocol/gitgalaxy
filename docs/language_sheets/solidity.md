# solidity

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 7 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 100% recall / 94.3% precision | 99 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_solidity.json` |
| Call links | 114% precision / 99.3% recall | 149 calls | tree-sitter | tree-sitter call nodes (which names a function calls) | `tests/call_graph_accuracy_baseline.json` |
| Imports | 100% precision / 99.8% recall | 812 imports | tree-sitter | import statements in OpenZeppelin/openzeppelin-contracts | `tests/import_graph_accuracy_baseline.json` |
| Keywords | decoy test only (17) |  | decoy-test |  | `tests/family_validity_baseline.json` |
| Rosetta | 57 of 57 passed, 0 failed | 57 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |

[All languages](README.md)

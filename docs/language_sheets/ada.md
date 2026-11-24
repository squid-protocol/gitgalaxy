# ada

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 50 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 97.8% recall / 96.8% precision | 949 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_ada.json` |
| Call links | 82.2% precision / 58.6% recall | 2,795 calls | tree-sitter | tree-sitter call nodes (which names a function calls) | `tests/call_graph_accuracy_baseline.json` |
| Imports | not measured | | | | |
| Keywords | decoy test only (1) |  | decoy-test |  | `tests/family_validity_baseline.json` |
| Rosetta | 59 of 59 passed, 0 failed | 59 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |
| Answer key | not measured | | | | |

[All languages](README.md)

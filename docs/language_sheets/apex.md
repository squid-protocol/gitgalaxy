# apex

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 7 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 100% recall / 100% precision | 38 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_apex.json` |
| Call links | 95.7% precision / 97.5% recall | 276 calls | tree-sitter | tree-sitter call nodes (which names a function calls) | `tests/call_graph_accuracy_baseline.json` |
| Imports | not measured | | | | |
| Keywords | decoy test only (15) |  | decoy-test |  | `tests/family_validity_baseline.json` |
| Rosetta | 59 of 59 passed, 0 failed | 59 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |
| Answer key | not measured | | | | |

[All languages](README.md)

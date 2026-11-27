# groovy

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 305 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | not measured | | | | |
| Call links | 90.1% precision / 95.3% recall | 737 calls | tree-sitter | tree-sitter call nodes (which names a function calls) | `tests/call_graph_accuracy_baseline.json` |
| Imports | 99.3% precision / 96.3% recall | 1,105 imports | tree-sitter | import statements in spockframework/spock | `tests/import_graph_accuracy_baseline.json` |
| Keywords | decoy test only (32) |  | decoy-test |  | `tests/family_validity_baseline.json` |
| Rosetta | 59 of 59 passed, 0 failed | 59 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |
| Answer key | not measured | | | | |

[All languages](README.md)

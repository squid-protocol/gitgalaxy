# perl

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 21 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 100% recall / 100% precision | 943 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_perl.json` |
| Call links | 97.1% precision / 97.8% recall | 4,524 calls | tree-sitter | tree-sitter call nodes (which names a function calls) | `tests/call_graph_accuracy_baseline.json` |
| Imports | 98.7% precision / 99.2% recall | 397 imports | tree-sitter | import statements in libwww-perl/HTTP-Message, plack/Plack | `tests/import_graph_accuracy_baseline.json` |
| Keywords | decoy test only (20) |  | decoy-test |  | `tests/family_validity_baseline.json` |
| Rosetta | 59 of 59 passed, 0 failed | 59 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |

[All languages](README.md)

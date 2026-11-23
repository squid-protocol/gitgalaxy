# rust

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 46 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 100% recall / 100% precision | 2,127 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_rust.json` |
| Call links | 98.3% precision / 81.5% recall | 1,084 reference edges | analyser | rust-analyzer 1.90.0 | `tests/call_graph_resolution_rust_baseline.json` |
| Imports | 99.5% precision / 99.3% recall | 814 imports | tree-sitter | import statements in BurntSushi/ripgrep, serde-rs/json | `tests/import_graph_accuracy_baseline.json` |
| Keywords | 11 of 59 families: 4 >90, 2 75-50, 5 <50 | 2,278 oracle functions | tree-sitter | parser-labelled functions, lower of recall and precision per family | `tests/family_validity_baseline.json` |
| Rosetta | 59 of 59 passed, 0 failed | 59 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |

[All languages](README.md)

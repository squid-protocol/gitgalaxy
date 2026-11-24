# javascript

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 20 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 100% recall / 98.1% precision | 632 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_javascript.json` |
| Call links | 99.4% precision / 90.3% recall | 528 reference edges | analyser | tsc (allowJs) 6.0.2 | `tests/call_graph_resolution_javascript_baseline.json` |
| Imports | 100% precision / 99.8% recall | 433 imports | tree-sitter | import statements in axios/axios, expressjs/express | `tests/import_graph_accuracy_baseline.json` |
| Keywords | 11 of 66 families: 5 >90, 1 90-75, 1 75-50, 4 <50 | 495 oracle functions | tree-sitter | parser-labelled functions, lower of recall and precision per family | `tests/family_validity_baseline.json` |
| Rosetta | 59 of 59 passed, 0 failed | 59 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |
| Answer key | not measured | | | | |

[All languages](README.md)

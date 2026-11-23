# php

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 36 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 100% recall / 100% precision | 1,707 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_php.json` |
| Call links | 99.9% precision / 97.9% recall | 3,059 reference edges | analyser | scip-php 0.0.2 | `tests/call_graph_resolution_php_baseline.json` |
| Imports | 99.2% precision / 100% recall | 390 imports | tree-sitter | import statements in guzzle/guzzle | `tests/import_graph_accuracy_baseline.json` |
| Keywords | 12 of 56 families: 7 >90, 2 90-75, 1 75-50, 2 <50 | 26,456 oracle functions | tree-sitter | parser-labelled functions, lower of recall and precision per family | `tests/family_validity_baseline.json` |
| Rosetta | 59 of 59 passed, 0 failed | 59 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |

[All languages](README.md)

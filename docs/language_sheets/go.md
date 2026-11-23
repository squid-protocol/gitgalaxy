# go

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 69 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 100% recall / 100% precision | 917 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_go.json` |
| Call links | 99.6% precision / 77.8% recall | 4,706 reference edges | analyser | go-callgraph 0.37.0 | `tests/call_graph_resolution_go_baseline.json` |
| Imports | 100% precision / 100% recall | 149 imports | tree-sitter | import statements in gin-gonic/gin, prometheus/client_golang, spf13/cobra | `tests/import_graph_accuracy_baseline.json` |
| Keywords | 12 of 57 families: 4 >90, 2 90-75, 3 75-50, 3 <50 | 2,306 oracle functions | tree-sitter | parser-labelled functions, lower of recall and precision per family | `tests/family_validity_baseline.json` |
| Rosetta | 59 of 59 passed, 0 failed | 59 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |

[All languages](README.md)

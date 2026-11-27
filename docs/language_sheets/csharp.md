# csharp

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 8 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 99% recall / 99.9% precision | 1,235 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_csharp.json` |
| Call links | 99.7% precision / 79% recall | 4,727 reference edges | analyser | scip-dotnet 0.2.16 | `tests/call_graph_resolution_csharp_baseline.json` |
| Imports | 17.5% precision / 66.7% recall | 39 imports | tree-sitter | import statements in JamesNK/Newtonsoft.Json, xunit/xunit | `tests/import_graph_accuracy_baseline.json` |
| Keywords | 13 of 58 families: 13 >90; 31 more decoy-tested only | 2,657 oracle functions | tree-sitter | parser-labelled functions, lower of recall and precision per family | `tests/family_validity_baseline.json` |
| Rosetta | 59 of 59 passed, 0 failed | 59 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |
| Answer key | not measured | | | | |

[All languages](README.md)

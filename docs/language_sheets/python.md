# python

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 269 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 100% recall / 100% precision | 2,408 functions | exact-parser | Python ast on the stdlib corpus | `tests/ast_accuracy_baseline.json` |
| Call links | 99.9% precision / 54.8% recall | 3,565 reference edges | analyser | pyan3 2.9.0 | `tests/call_graph_resolution_baseline.json` |
| Imports | 99.9% precision / 100% recall | 2,101 imports | tree-sitter | import statements in encode/httpx, fastapi/fastapi, pallets/flask | `tests/import_graph_accuracy_baseline.json` |
| Keywords | 24 of 67 families: 15 >90, 9 90-75; 29 more decoy-tested only | 9,656 oracle functions | tree-sitter | parser-labelled functions, lower of recall and precision per family | `tests/family_validity_baseline.json` |
| Rosetta | 59 of 59 passed, 0 failed | 59 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |
| Answer key | not measured | | | | |

[All languages](README.md)

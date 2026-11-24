# lua

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 113 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 100% recall / 100% precision | 623 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_lua.json` |
| Call links | 97.5% precision / 98.2% recall | 1,356 calls | tree-sitter | tree-sitter call nodes (which names a function calls) | `tests/call_graph_accuracy_baseline.json` |
| Imports | 100% precision / 99.2% recall | 354 imports | tree-sitter | import statements in luarocks/luarocks | `tests/import_graph_accuracy_baseline.json` |
| Keywords | 10 of 52 families: 5 >90, 1 75-50, 4 <50 | 260 oracle functions | tree-sitter | parser-labelled functions, lower of recall and precision per family | `tests/family_validity_baseline.json` |
| Rosetta | 59 of 59 passed, 0 failed | 59 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |
| Answer key | not measured | | | | |

[All languages](README.md)

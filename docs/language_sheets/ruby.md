# ruby

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 13 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 98.5% recall / 100% precision | 135 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_ruby.json` |
| Call links | 99.9% precision / 96.3% recall | 1,045 calls | tree-sitter | tree-sitter call nodes (which names a function calls) | `tests/call_graph_accuracy_baseline.json` |
| Imports | 99.6% precision / 99.6% recall | 239 imports | tree-sitter | import statements in rack/rack | `tests/import_graph_accuracy_baseline.json` |
| Keywords | 11 of 56 families: 2 >90, 1 90-75, 4 75-50, 4 <50 | 9,804 oracle functions | tree-sitter | parser-labelled functions, lower of recall and precision per family | `tests/family_validity_baseline.json` |
| Rosetta | 59 of 59 passed, 0 failed | 59 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |
| Answer key | not measured | | | | |

[All languages](README.md)

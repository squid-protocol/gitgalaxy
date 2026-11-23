# shell

Context: unclassified

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 264 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 84.2% recall / 98.1% precision | 970 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_shell.json` |
| Call links | 98.3% precision / 98.2% recall | 1,743 calls | tree-sitter | tree-sitter call nodes (which names a function calls) | `tests/call_graph_accuracy_baseline.json` |
| Imports | 100% precision / 100% recall | 100 imports | tree-sitter | import statements in Bash-it/bash-it, bats-core/bats-core, ohmybash/oh-my-bash, tfutils/tfenv | `tests/import_graph_accuracy_baseline.json` |
| Keywords | 9 of 51 families: 2 >90, 2 90-75, 2 75-50, 3 <50 | 833 oracle functions | tree-sitter | parser-labelled functions, lower of recall and precision per family | `tests/family_validity_baseline.json` |
| Rosetta | 57 of 57 passed, 0 failed | 57 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |

[All languages](README.md)

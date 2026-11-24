# c

Context: modern-tooled

## What was possible

- **Parsers found:** tree-sitter grammar; libclang 18.1.1 resolves calls (the call-link reference).
- **Public corpus:** Pinned language-crucible files plus hiredis and libuv for the import and call graphs.
- **Reference analyser:** libclang 18.1.1.
- **Best method:** A compiler front end (libclang) for call links; tree-sitter for functions and imports.

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 40 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 100% recall / 99.5% precision | 1,715 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_c.json` |
| Call links | 100% precision / 53% recall | 13,286 reference edges | analyser | libclang 18.1.1 | `tests/call_graph_resolution_c_baseline.json` |
| Imports | 100% precision / 100% recall | 811 imports | tree-sitter | import statements in libuv/libuv, redis/hiredis | `tests/import_graph_accuracy_baseline.json` |
| Keywords | 10 of 55 families: 5 >90, 2 90-75, 1 75-50, 2 <50 | 1,775 oracle functions | tree-sitter | parser-labelled functions, lower of recall and precision per family | `tests/family_validity_baseline.json` |
| Rosetta | 59 of 59 passed, 0 failed | 59 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |

[All languages](README.md)

# typescript

Context: modern-tooled

## What was possible

- **Parsers found:** tree-sitter grammar; the TypeScript 6.0.2 type checker resolves calls (the call-link reference).
- **Public corpus:** Pinned language-crucible files plus zod for the import and call graphs.
- **Reference analyser:** The TypeScript compiler's own type checker (tests/tools/ts_callgraph.js).
- **Best method:** The compiler itself for call links; tree-sitter for functions and imports.

## Measured

| stat | value | sample | method | against | source |
|---|---|---|---|---|---|
| Detection | 100% recall / 100% precision | 29 files | corpus-label | labelled language-crucible files | `tests/detection_accuracy_baseline.json` |
| Functions | 99.8% recall / 100% precision | 8,484 functions | tree-sitter | tree-sitter functions on language-crucible | `tests/tree_sitter_accuracy_baseline_typescript.json` |
| Call links | 100% precision / 83% recall | 2,661 reference edges | analyser | tsc 6.0.2 | `tests/call_graph_resolution_typescript_baseline.json` |
| Imports | 100% precision / 100% recall | 870 imports | tree-sitter | import statements in colinhacks/zod | `tests/import_graph_accuracy_baseline.json` |
| Keywords | 12 of 66 families: 3 >90, 2 90-75, 2 75-50, 5 <50 | 10,415 oracle functions | tree-sitter | parser-labelled functions, lower of recall and precision per family | `tests/family_validity_baseline.json` |
| Rosetta | 59 of 59 passed, 0 failed | 59 comparable cells | keyword-rosetta | the 12-probe program, engine a48ee0ad95 | `docs/language_sheets/rosetta_snapshot.json` |

[All languages](README.md)

# Graph comparison: calls and imports, reconciled like the tri-comparison

The call graph and the import graph are compared against tree-sitter the way structural
extraction is compared against tree-sitter and ctags ([`tri_comparison_README.md`](tri_comparison_README.md)):
a disagreement is a **discrepancy**, not a GitGalaxy error, until someone reads the source and
records a verdict (#3641). Decided 2026-09-25 by Joe:

- **Same process, separate file.** Shapes live in `docs/self_scan/graph_comparison_ledger.json`,
  written and read through `tests/tools/tri_comparison_ledger.py`: the same schema, lifecycle and
  `credit_tools` geometry, and the same investigation guide
  ([`how_to_investigate_a_discrepancy.md`](how_to_investigate_a_discrepancy.md)). The structural
  ledger and its chart are untouched.
- **A shape** is `language / call / cause / agree[claiming reader]_vs[other reader]`. The cause is
  the syntactic label `call_graph_accuracy.py --buckets` assigns (`inner-named-function_definition`,
  `not-a-call-in-ts:tuple_struct_pattern<match_pattern`, `call_expression/template_function+generic`,
  ...), so one verdict covers every occurrence of one systematic cause.
- **Two numbers per language.** *Raw* agreement keeps the `--ci` regression gate. *Validated*
  precision and recall apply the verdicts, and are the only numbers to quote.

## How a verdict moves the validated numbers

| shape | verdict | effect |
|---|---|---|
| `agree[gitgalaxy]` (GitGalaxy-only call) | `credit_tools: ["gitgalaxy"]` | GitGalaxy was right: the FP becomes a TP |
| | validated, no credit | GitGalaxy was wrong: stays an FP |
| `agree[tree_sitter]` (tree-sitter-only call) | `credit_tools: ["tree_sitter"]` | GitGalaxy missed it: stays an FN |
| | validated, no credit | tree-sitter was wrong: leaves the FN count |

With two readers there is no consensus (the tri-comparison's third reader), so an **unvalidated**
shape counts exactly as it does raw. The validated numbers only ever move on a recorded verdict,
and a language with any open shape carries a `*`: its number is not a claim. When a third reader
(a SCIP indexer, #3641 step 3) is added, the ctags model applies.

## The contract the comparison scores against

`docs/calls_out_rule_contract.md`. Two rulings shape the comparison itself:

- **C8**: a call inside an anonymous function belongs to the enclosing named unit, and a call
  inside a nested named function belongs to that unit only. The harness follows it: an anonymous
  function never becomes an owner of calls (before 2026-09-25 it silently dropped them, which
  read as 213 JavaScript and 505 TypeScript GitGalaxy "false positives").
- **C3**: constructors, conversions and macros are calls; a pattern (`Ok(t) =>`) is not. The
  harness counts go `type_conversion_expression` and names a generic call by its function, not its
  type argument (`collect::<Vec<_>>()` is `collect`).

A mechanical harness bug is fixed in code; a judgment about which reader is right is a ledger
verdict, never a hard-coded exclusion.

## Running it

```sh
python tests/tools/call_graph_accuracy.py --buckets 3   # raw + validated, causes with examples
python tests/tools/call_graph_accuracy.py --ledger      # merge this run's shapes into the ledger
python tests/tools/call_graph_accuracy.py --ci          # raw regression gate
```

**Who writes what.** A PR adds verdicts. The count churn -- `last_seen_count`,
`last_seen_examples` (5 per shape, `LEDGER_EXAMPLES`), `still_reproduces` and new `unvalidated`
shapes -- is committed after merge by `.github/workflows/graph-comparison-history.yml`, the twin
of `tri-comparison-history.yml`, which never touches a verdict or the raw baseline.

The ledger lives here, not in a sibling repo: an engine fix and the verdicts it retires land in
one PR, and the contract, issues, tool and gate it references are all in this repo. Bulk
per-occurrence evidence, if ever needed, belongs in `gitgalaxy-raw-output`.

Validate a shape by reading its recorded examples, then set `status`, `verdict`,
`investigated_by`, `investigated_at` and (only when the geometry above allows it)
`credit_tools` by hand. Never set them from a guess about whether a shape "should" hold.

## Imports

`import_graph_accuracy.py --buckets N` / `--ledger` put the import graph in the same ledger
(symbol type `import`; both tools share `tests/tools/graph_ledger.py`, and each refreshes only its
own symbol type's shapes). Precision counts engine edges, recall counts resolvable import
statements. Import causes name the LAYER that disagrees:

| cause | layer | meaning |
|---|---|---|
| `fn:capture-missed` / `fn:capture-none-in-file` | capture | no engine token for the import (none at all in the file) |
| `fn:token-unresolved` | resolution | a token names the target file, but no edge |
| `fn:declaration-unresolved` | resolution | a dotted token names a declaration in the target's package |
| `fn:truth-names-several-files` | truth side | the parser's answer is several files (wildcard, package, duplicate) |
| `fp:same-name-other-path` | resolution | the engine linked a same-named file at another path |
| `fp:truth-sees-no-import-in-file` | capture / truth | the parser resolves no import in this file at all |
| `fp:target-is-test-file` / `fp:target-not-imported` | resolution | the target is not among the importer's real imports |

The truth side follows `docs/import_rule_contract.md`: a whole-package wildcard expects its
package object's edge or none (C7), and a build-variant copy is the importer's own variant (C8).
Two scala truth-side bugs fixed with C7 held most of scala's old 51.6% recall: every top-level
`import_declaration` was indexed as a declaration of its first name, and member imports cut back
into the enclosing package -- together 410 "missed" imports that were never GitGalaxy's.

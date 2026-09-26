# Graph accuracy gates

GitGalaxy's two graphs, the file-level **import graph** (PageRank, blast radius, popularity,
`dependency_density`) and the function-level **call graph** (`fcall_data`, function PageRank),
are measured against parser ground truth on every pull request that touches parsing or
resolution. Each check reads a committed baseline and fails a PR that moves a number the wrong
way by more than 0.5 percentage points. A fix that improves a number is locked in by regenerating
that baseline in the same PR.

| Check | Tool | Ground truth | Corpus | Baseline | Workflow |
|---|---|---|---|---|---|
| Callee names (call graph, Level 1) | `tests/tools/call_graph_accuracy.py` | tree-sitter call nodes | language-crucible | `tests/call_graph_accuracy_baseline.json` | `call-graph-accuracy-audit.yml` |
| Call resolution (call graph, Level 2) | `tests/tools/call_graph_resolution.py python` | pyan3 2.8.1 call graph | language-crucible Python | `tests/call_graph_resolution_baseline.json` | `graph-accuracy-audit.yml` |
| Call resolution (call graph, Level 2) | `tests/tools/call_graph_resolution.py typescript` | the TypeScript 6.0.2 type checker (`tests/tools/ts_callgraph.js`) | pinned typescript repos, `tests/import_graph_corpus.json` (zod) | `tests/call_graph_resolution_typescript_baseline.json` | `graph-accuracy-audit.yml` |
| Import edges | `tests/tools/import_graph_accuracy.py` | each language's import statements (Python `ast`, tree-sitter), resolved by the language's own rule | pinned real repos, `tests/import_graph_corpus.json` | `tests/import_graph_accuracy_baseline.json` | `graph-accuracy-audit.yml` |
| Span anchoring | `tests/tools/span_anchor_audit.py` | the declaration line in the raw source | language-crucible | `tests/span_anchor_baseline.json` | `graph-accuracy-audit.yml` |

Every step appends its table to the workflow's job summary, so the current numbers are on the
PR's checks page. The committed baselines hold the numbers on `main`.

## Import edges

The import graph had no edge-level check before this one. `graph_parity.py` pins the graph
*maths* against networkx, and `docs/import_rule_contract.md` pins the import *count*, but neither
asks whether an edge joins the two files the source actually joins.

- **Scoring is per import statement.** A statement names a set of files: a Go import is a
  package, a directory of files; `from a import b` can mean `a/__init__.py` or `a/b.py`.
  Precision is the share of engine import edges that land in one of the source file's resolved
  sets. Recall is the share of resolvable statements with at least one engine edge into their set.
- **Imports that resolve outside the repo are not scored.** That covers packages, the stdlib,
  bare npm specifiers and tsconfig aliases.
- **Resolution follows each language's rule, not the engine's.** Examples: Go's module path
  from `go.mod`, PHP's PSR-4 map from `composer.json`, Python's source roots (`import types` is
  the stdlib even when `pkg/types.py` exists), and a quoted C include tried in the including
  file's directory first. The tool's docstring lists every rule.
- **Why pinned repos and not language-crucible.** The crucible's samples are flattened into one
  directory per repo. `py/compile.h`, `../core.js` or a PSR-4 namespace path no longer exist
  there, so no parser can say what an import meant.
  `python tests/tools/import_graph_accuracy.py --fetch-only` clones the pinned repos into
  `IMPORT_GRAPH_CORPUS_PATH` (default `../import-graph-corpus`, a sibling of the checkout). Moving
  a pin moves the numbers, so regenerate the baseline in the same PR.
- **Each repo is scanned on its own**, in a subprocess pinned to the checkout under test.
  Scanning several repos as one lets an import resolve into a different repo, which no real scan
  can do.

A disagreement is a lead, not a verdict. Check it against the source before quoting a number
(CLAUDE.md, "Comparative-correctness claims"). The known ones: a dynamic import the parser cannot
see (`__import__('x')`) counts against precision even when the engine got it right, and PHP
references to same-namespace classes that no `use` statement names are not statements, so an
engine edge for one counts as a false positive.

## Call resolution in TypeScript

The Python check scores the engine's links against pyan3, a static analyser that infers edges
without full types. The TypeScript check uses the compiler itself: `tests/tools/ts_callgraph.js`
builds a program from every `.ts`/`.tsx` file of the repo under its root `tsconfig.json`, and asks
the type checker which declaration each call and `new` resolves to. Scoring is the same (`agree`,
`wrong`, `unconfirmed`, per confident and ambiguous link), with one verdict pyan cannot give:

- **`external`**: the checker resolved the call only to declarations outside the repo, such as
  `lib.d.ts` or `node_modules`. `input.data.trim()` on a string is `String.prototype.trim`, so an
  engine link to the repo's own `ZodString.trim()` is provably wrong. These are reported as
  `confident_strict_precision_pct`, which is agree / (agree + wrong + external). The number is
  baselined but not gated yet.
- **`unmapped`** counts engine links with an end the checker has no function for. On zod these
  are almost all bodyless signatures: interface methods, `abstract` methods and type members.
- **The corpus is the pinned import-graph repos, not language-crucible.** The crucible's
  TypeScript samples are flattened, so no relative import resolves and the checker would see
  almost nothing. Fetch with `import_graph_accuracy.py --fetch-only`. The checker's version is
  pinned (`TYPESCRIPT_VERSION`). A different version prints a warning under `--ci`, and
  `--regenerate` refuses to run with it. TypeScript 7 (the native Go port, npm's `latest`) can't serve as the reference:
  its package ships no JavaScript compiler API. The script exits with a message saying so.
- **It is a reference, not ground truth.** An `any` receiver or an unresolved package import
  (zod is not `npm install`ed) leaves the checker silent. Those links count as `unconfirmed`,
  never as `wrong`.

## Span anchoring

A unit is mis-anchored when its `start_line` opens before the declaration, on lines that belong
to other code: blank lines, comments, or lines that end a previous construct (`{`, `}`, `,`, `;`,
`*/`). Annotation, attribute, decorator, `template <...>` and C return-type lines are part of the
declaration and are not counted. Lower is better. The shape comes from #3543, where a
`func_start` pattern swallows the newline before the declaration.

## Running locally

```sh
PYTHONPATH="$PWD" python tests/tools/import_graph_accuracy.py --fetch-only       # once
PYTHONPATH="$PWD" python tests/tools/import_graph_accuracy.py --samples 5        # report + examples
PYTHONPATH="$PWD" python tests/tools/call_graph_resolution.py python --ci       # needs pyan3==2.8.1
PYTHONPATH="$PWD" python tests/tools/call_graph_resolution.py typescript --ci   # needs node + typescript@6.0.2
PYTHONPATH="$PWD" python tests/tools/span_anchor_audit.py --ci
# after an intended improvement: the same commands with --regenerate, committed with the fix
```

All of them refuse to pass on an empty measurement (#2682).

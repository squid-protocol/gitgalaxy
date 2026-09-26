# The function call graph (Epic #3265)

GitGalaxy's file graph is built from import statements. Its function graph is
built from calls: each function's `calls_out_to` (the names its body invokes,
contract in `docs/calls_out_rule_contract.md`, #3327) is linked to the
definition each name most plausibly means, and the confident links form a
directed graph with its own PageRank, and they also connect files in the
file dependency graph (#3333). It runs without an AST, so it is a
heuristic approximation of a real call graph. What it can and cannot get right
is measured, not assumed: see *Accuracy* below.

## How a call is linked (`core/call_resolver.py`, #3328/#3329)

Every (caller, callee name) pair goes down the ladder until one step matches:

| step | meaning | class |
|---|---|---|
| `class` | a method of the caller's own class, or an ancestor's (via `self`/`this`/a bare call) | scoped |
| `qualified` | `Store.make()` / `Store::make()`: a method of the named class | scoped |
| `typed` | `x.save()` where the same function shows `x`'s class (`x = Store()`, `def f(x: Store)`, `with Store() as x`): a method of that class or its nearest ancestor. Python only; the evidence is `function_data.calls_out_receiver_types` | scoped |
| `file` | defined in the caller's own file | scoped |
| `import` | defined in a file the caller imports, or its own directory for an untyped receiver | scoped |
| `unique` | the only definition of the name in the repository | unique |
| `unseen` | the only definition, but a bare call in a package-scoped language (Python, JS/TS, Perl, Zig, Rust, Dart; Go and the JVM languages outside the caller's directory) cannot see it: not imported, not its own package (#3443) | ambiguous |
| `nearest` | several definitions; the nearest by path is recorded as a guess | ambiguous |
| `receiver` | `obj.m()` with an untyped `obj`, and `m` not visible to the caller | ambiguous |
| `tie` | several definitions, equally near | ambiguous |
| `none` | defined nowhere in the repository (built-in, stdlib, package) | external |

The receiver chain written before a C-style call (`utils.parse`, `self.save`,
`$this->load`) is captured as `function_data.calls_out_qualifiers`, and is what
keeps `d.get()` on a dictionary from landing on the repository's one `get`
method. **Ambiguous pairs are never graph edges.**

In TypeScript and JavaScript the detector also records what each definition is
(`function_data.def_shape`, #3757), because only some shapes can be called by name:

- **`binding`**: `function f`, `const/let/var f = ...`. The only shape a bare call
  `f()` can reach. When a file has several bindings of the name in different
  scopes (a `const Node = ...` in each test callback), the call goes to the
  nearest one written before it, or to the last one when none precedes it,
  because a function declaration is hoisted (#3759).
- **`member`**: an object-literal method `f() {}`, an object property
  `f: () => ...`, or a member assignment `x.f = () => ...`. Only reachable through
  its object, so a bare call never lands on it (#3758).
- **`signature`**: an interface member, an `abstract` method, or an overload
  signature. No code runs there, so it is never a call target (#3757). A call to
  an overloaded function reaches its implementation.

Other languages leave `def_shape` NULL and resolve as before.

## Edge kinds

`fcall_data.kind` says what a row's link is. Every kind resolves down the same ladder;
only `call` counts toward the call-resolution rates (`fcall_rate_data`, #3331).

| kind | from -> to | recorded for | why it is an edge |
|---|---|---|---|
| `call` | caller -> callee | every C-style language, and the per-language paradigms | the callee runs when the caller does |
| `transfer` | paragraph -> paragraph | COBOL `GO TO` (#3362) | control reaches the target without returning |
| `decorator` | decorated function -> decorator | Python (`decorated_by`) | the decorator's wrapper runs around every call to the function (`@retry(3)`, `@provide_bucket_name`), or registers it (`@app.post(...)`) |
| `reference` | function -> function it uses as a value | Python (`references_to`) | a callback the framework or caller will invoke: `Depends(get_db)`, `key=sort_key`, `callback=self.on_done`, `return wrapper` |

A `reference` row exists only when the name reaches a function through a scoped step
(`class`, `qualified`, `typed`, `file`, `import`): a bare name is far more often a
variable than a function, so `unique` is not enough. All four kinds reach function
fan-in and PageRank (#3330); only `call` rows join the file graph as `fcall` edges
(`confident_file_pairs`), so file-level metrics measure calls alone.

Python also records the code a module runs at import (`app = FastAPI()`,
`@app.post("/items")`, `if __name__ == "__main__": main()`) as a calls-only
`__global_context__` unit: a synthetic caller with no weight, persisted in
`synthetic_unit_data` so a delta scan resolves it like a fresh scan.

## What the call graph adds to a parser

A parser such as tree-sitter reports syntax: there is a call named `post` here. It does
not say which `post`. Everything below is resolution, which a parser does not attempt, so
none of it is a claim that GitGalaxy parses more accurately than tree-sitter (that
narrower kind of claim lives in `docs/why_gitgalaxy_beats_ast_here.md`, one measured
case at a time). It is what the graph knows on top of the names.

| capability | what it resolves | Python measurement (pyan3, language-crucible) |
|---|---|---|
| definition linking (the ladder above) | `utils.parse()` -> `pkg/utils.py:parse` | 99.8% precision over 1,806 judged confident links |
| barrel re-exports (#3689) | `from fastapi import Depends` -> `fastapi/param_functions.py`, through `fastapi/__init__.py` | resolution recall 71.8% -> 90.2% at higher precision |
| constructors (#3690) | `Foo(...)` -> `Foo.__init__` (or the language's constructor) | edge recall 36.1% -> 39.3% on its own |
| local receiver types (#3693) | `app = FastAPI()` ... `app.post(...)` -> `FastAPI.post` | resolution recall 90.2% -> 96.9% |
| module-level code (#3704) | route registration and wiring at import time | fastapi: 416 of 417 module-level call pairs confident; pyan has no module node, so not scored against it |
| decorators (#3708) | `@provide_bucket_name` on `get_key` -> `provide_bucket_name` | 100.0% precision over 575 judged |
| references (#3712) | `Depends(get_db)` -> `get_db`; `return wrapper` -> the nested `wrapper` | 99.7% precision over 323 judged |
| nested definitions (#3712) | a function's own nested `wrapper`, not the file's first | call precision 99.4% -> 99.8% |

Together: recall of pyan3's function edges across calls, decorators and references is
77.3% (calls alone: 51.6%). Read the numbers with their limits:

- **Two reference tools, two languages.** pyan3 is a reference, not ground truth: a
  hand-checked sample of edges it has and GitGalaxy does not were pyan inferences with
  no basis in the source (a getter that only reads an attribute). TypeScript is measured
  against the compiler's own type checker on zod: 99.9% confident precision over 1,520
  judged links, 57.1% recall, 73.7% resolution recall. The checker also shows that 52
  confident links point into the repo for a call that runs a built-in (`str.trim()`,
  `map.get()`), so strict precision is 96.6% (#3756). Other languages run the same
  machinery unmeasured.
- **Tuned on the corpus it is scored on.** Every change above was found and verified on
  language-crucible's Python repos; a held-out check has not been run.
- **What stays out of reach without types.** `x.method()` where `x` comes from a loop over
  mixed types or a function's return value; dynamic dispatch (`getattr`, dicts of
  callables); a receiver bound in an enclosing scope's loop. These stay ambiguous rows,
  never edges.
- **`@property` reads.** `self.x` where `x` is a property runs a function. The reference
  kind records many of them; a call site it misses is a plain attribute read to the
  engine, and pyan does not count these at all.

The per-kind numbers are regenerated by `python tests/tools/call_graph_resolution.py python`
and kept in `tests/call_graph_resolution_baseline.json` (the call metrics gated, the
decorator and reference lines reported). The TypeScript numbers come from the
`typescript` mode and `tests/call_graph_resolution_typescript_baseline.json`.

## Where it lands in the master DB

- `fcall_data`: one row per (caller, callee) pair the repository defines, with
  its `step`, `candidates` count and the destination file/function/class ids.
  External pairs are not rows. They are the function's `calls_out_to` entries
  that have no row.
- `edge_data` rows of kind `'fcall'` (#3333): confident cross-file calls
  between two files that no import joins. They are **part of the dependency
  graph**, at the weight of one plain import (`CALL_EDGE_WEIGHT` = 1.0), so
  `pagerank_score`, `popularity`, `internal_dependency_links`, betweenness,
  closeness and blast radius all see them. `import_statements` holds the number
  of calling functions.
- `edge_data` rows of kind `'call'`/`'exec'` (#3200, in the graph since #3237):
  the mainframe program-level edges -- a resolved COBOL `CALL`, CICS
  `LINK`/`XCTL` or JCL `EXEC PGM=`. The same rule as `'fcall'`: a pair no import
  or function call already joins becomes a graph edge at `CALL_EDGE_WEIGHT`, so
  every graph metric above sees them; an unresolved target has no edge. The
  table keeps one row per (src, dst, kind) with its `call_sites` count, so a pair
  can have an import row and a call row; per file, distinct neighbours over every
  kind equal `internal_dependency_links` / `popularity`.
- `fcall_rate_data` (#3331): scoped / unique / ambiguous / external counts per
  language and for the repository (`language = '*'`). The brief's section 15
  shows the same figures.
- `function_data` (#3330):
  - `func_pagerank`: PageRank over the confident links.
  - `func_fan_in` / `func_fan_out`: distinct confident callers and callees.
  - The transitive blast radius is a query (below), not a column. An all-nodes
    reachability pass is O(N^2) and exceeded any reasonable budget on real
    repositories.

COBOL `GO TO` targets are transfers, not calls (#3362). They're held in
`function_data.transfers_to` and linked as `fcall_data` rows with `kind = 'transfer'`.
Function fan-in, PageRank and the blast-radius query follow them, so a paragraph reached
only by `GO TO` is not orphaned. The call-resolution rates (`fcall_rate_data`) count
calls only.

Module-level code is a caller node: it gives fan-in and PageRank but has no row
of its own. A constructor call that resolved to a class has no function node,
so it adds no edge.

## Queries

The busiest functions:

```sql
SELECT fd.file_path, fn.func_name, fn.func_fan_in, fn.func_fan_out, fn.func_pagerank
FROM function_data fn JOIN file_data fd ON fd.id = fn.file_id
ORDER BY fn.func_pagerank DESC LIMIT 20;
```

Everything upstream of one function (what a change to it can break). The same
query runs as `python tests/tools/function_blast_radius.py <db> <function>`
(`--downstream` for the other direction):

```sql
WITH RECURSIVE reach(func_id, depth) AS (
    SELECT id, 0 FROM function_data WHERE func_name = 'parse_config'
    UNION
    SELECT c.src_func_id, r.depth + 1
    FROM fcall_data c JOIN reach r ON c.dst_func_id = r.func_id
    WHERE c.step IN ('class', 'qualified', 'typed', 'file', 'import', 'unique')
      AND c.src_func_id IS NOT NULL AND r.depth < 50
)
SELECT fd.file_path, fn.func_name, MIN(r.depth)
FROM reach r JOIN function_data fn ON fn.id = r.func_id JOIN file_data fd ON fd.id = fn.file_id
WHERE r.depth > 0 GROUP BY r.func_id ORDER BY 3;
```

## Accuracy

A confident link is one the resolver chose, not one that was verified.
`tests/tools/call_resolution_rates.py` tracks the confidence shares on
language-crucible (`docs/self_scan/call_resolution_history.csv`). Correctness,
meaning precision and recall of callee names and of resolved targets against
tree-sitter and type-aware call graphs, is #3332. Both levels are gated per PR
against committed baselines; see `docs/graph_accuracy.md`, which also covers the
import graph. Until that is published, no README claim or badge uses these numbers
(CLAUDE.md).

## Cost

Measured on elasticsearch (39.5k files, 305k functions, 1.5M call pairs)
against the pre-#3328 engine: scan wall 144 s -> ~160 s. The resolver takes ~8 s,
the function-graph pass (#3330: PageRank + fan-in/out over the confident links)
~2.4 s, and the rest is extraction and recording. The master DB grows 262 MB ->
~375 MB, almost all of it the `fcall_data` relation. cpython: 31 s -> ~35 s.

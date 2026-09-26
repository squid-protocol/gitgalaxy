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
  of calling functions. The mainframe program-level `'call'`/`'exec'` rows are
  still outside the graph (#3237).
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

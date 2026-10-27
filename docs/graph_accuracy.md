---
description: "GitGalaxy's two graphs, the file-level **import graph** (PageRank, blast radius, popularity,"
---
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
| Call resolution (call graph, Level 2) | `tests/tools/call_graph_resolution.py python` | pyan3 2.9.0 call graph | language-crucible Python | `tests/call_graph_resolution_baseline.json` | `graph-accuracy-audit.yml` |
| Call resolution (call graph, Level 2) | `tests/tools/call_graph_resolution.py typescript` | the TypeScript 6.0.2 type checker (`tests/tools/ts_callgraph.js`) | pinned typescript repos, `tests/import_graph_corpus.json` (zod) | `tests/call_graph_resolution_typescript_baseline.json` | `graph-accuracy-audit.yml` |
| Call resolution (call graph, Level 2) | `tests/tools/call_graph_resolution.py javascript` | the TypeScript 6.0.2 type checker with `allowJs` (`tests/tools/ts_callgraph.js --js`) | pinned javascript repos, `tests/import_graph_corpus.json` (express) | `tests/call_graph_resolution_javascript_baseline.json` | `graph-accuracy-audit.yml` |
| Call resolution (call graph, Level 2) | `tests/tools/call_graph_resolution.py java` | scip-java 0.12.3 (javac-resolved SCIP, through `tests/tools/scip_callgraph.py`) | pinned java repos, `tests/import_graph_corpus.json` (gson) | `tests/call_graph_resolution_java_baseline.json` | `graph-accuracy-audit.yml` |
| Call resolution (call graph, Level 2) | `tests/tools/call_graph_resolution.py rust` | rust-analyzer (pinned toolchain 1.90.0; SCIP, through `tests/tools/scip_callgraph.py`) | pinned rust repos, `tests/import_graph_corpus.json` (serde-rs/json) | `tests/call_graph_resolution_rust_baseline.json` | `graph-accuracy-audit.yml` |
| Call resolution (call graph, Level 2) | `tests/tools/call_graph_resolution.py go` | golang.org/x/tools 0.37.0 VTA call graph (`tests/tools/go_callgraph`, Go 1.24+) | pinned go repos, `tests/import_graph_corpus.json` (cobra) | `tests/call_graph_resolution_go_baseline.json` | `graph-accuracy-audit.yml` |
| Call resolution (call graph, Level 2) | `tests/tools/call_graph_resolution.py c` | libclang 18.1.1 resolved calls (`tests/tools/clang_callgraph.py`, pip `libclang`) | pinned c repos, `tests/import_graph_corpus.json` (hiredis, libuv) | `tests/call_graph_resolution_c_baseline.json` | `graph-accuracy-audit.yml` |
| Call resolution (call graph, Level 2) | `tests/tools/call_graph_resolution.py cpp` | libclang 18.1.1 resolved calls, linked by USR (`tests/tools/clang_callgraph.py cpp`, pip `libclang` plus a host g++ for the C++ system headers) | pinned c++ repo, `tests/import_graph_corpus.json` (fmtlib/fmt) | `tests/call_graph_resolution_cpp_baseline.json` | `graph-accuracy-audit.yml` |
| Import edges | `tests/tools/import_graph_accuracy.py` | each language's import statements (Python `ast`, tree-sitter), resolved by the language's own rule | pinned real repos, `tests/import_graph_corpus.json` | `tests/import_graph_accuracy_baseline.json` | `graph-accuracy-audit.yml` |
| Span anchoring | `tests/tools/span_anchor_audit.py` | the declaration line in the raw source | language-crucible | `tests/span_anchor_baseline.json` | `graph-accuracy-audit.yml` |

Every step appends its table to the workflow's job summary, so the current numbers are on the
PR's checks page. The committed baselines hold the numbers on `main`.

Span anchoring is the longest single gate (about 5 min on a CI runner), so it can run as parallel shards
(#5501): `span_anchor_audit.py --shard I/N --json part.json` scans every Nth language directory, and
`--merge part*.json --ci` sums the counts and applies the one baseline. A shard cannot gate on its own: a
language's files sit in several directories (a `.h` file under `c/` can be C or a makefile), so only the summed
counts give the real rate. The merged shards equal the unsharded run exactly (51 languages, same counts).

**Coverage at a glance:**
[`self_scan/graph_coverage_chart.svg`](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/self_scan/graph_coverage_chart.svg) shows the checks
above for every language on one chart, with n. Languages that no check measures yet are listed
by name. How it's drawn is in
[`self_scan/graph_comparison_README.md`](self_scan/graph_comparison_README.md#the-coverage-chart).

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
- **Hub agreement (#3797).** Edge precision and recall do not say whether the engine's most
  depended-on files are the right ones. Per repo and language, both graphs (engine edges; the
  parser's resolved sets, one edge to each file a statement names) go through the engine's own
  `graph_engine.pagerank` over the same file set. `hub_overlap_at_10` is the share of the top 10
  the two agree on; `hub_spearman` is the rank correlation over the union of both top 10s. The
  language figure is the mean over repos with at least 10 files and a truth edge (PageRank does
  not pool across repos). It is recorded in the baseline, not yet gated.

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
- **`unmapped`** counts engine links with an end the checker has no function for. Before
  `def_shape` (#3757) there were 216 of these on zod, almost all links to bodyless signatures
  (interface methods, `abstract` methods, type members). Now 10 remain.
- **The corpus is the pinned import-graph repos, not language-crucible.** The crucible's
  TypeScript samples are flattened, so no relative import resolves and the checker would see
  almost nothing. Fetch with `import_graph_accuracy.py --fetch-only`. The checker's version is
  pinned (`TYPESCRIPT_VERSION`). A different version prints a warning under `--ci`, and
  `--regenerate` refuses to run with it. TypeScript 7 (the native Go port, npm's `latest`) can't serve as the reference:
  its package ships no JavaScript compiler API. The script exits with a message saying so.
- **It is a reference, not ground truth.** An `any` receiver or an unresolved package import
  (zod is not `npm install`ed) leaves the checker silent. Those links count as `unconfirmed`,
  never as `wrong`.

## Call resolution in Java, and SCIP (#3783)

Java is scored against **scip-java**. It's the SCIP index (<https://github.com/sourcegraph/scip>)
that javac's own symbol resolution produces, read by one shared adapter,
`tests/tools/scip_callgraph.py`. The adapter decodes the protobuf itself, so it needs no
dependency. Every language with a SCIP indexer can use the same adapter.

How it reads an index:
- **Edges:** a reference in call position (`f(`, `f<T>(`, `new X(`) inside a named callable
  definition's `enclosing_range` becomes an edge. A method reference (`Foo::bar`), a type and
  a field are not calls.
- **Callers:** calls inside an anonymous function belong to the named unit around it (C8).
- **External calls:** a callable defined outside the repo (the JDK) makes the call
  `external`.
- **Names follow the engine:** a constructor takes its class's name, each overload keeps its
  own line, an anonymous class's methods are units, and abstract or interface methods are
  not.

How the index is built: `scip-java index` re-runs the Maven build with a forked javac, and
that breaks on builds that turn warnings into errors. So the adapter builds it itself:
1. one reactor `mvn -fae compile dependency:build-classpath`;
2. javac with the `semanticdb-javac` plugin, per module, main and test sources together;
3. `scip-java index-semanticdb`.

A module that doesn't compile is listed under `skipped` in the contract. The first run
fetches the pinned jars from Maven Central, which rate-limits bursts; `MAVEN_FLAGS` retries
429s. After that, gson builds in about 45 seconds.

**Numbers vs scip-java on gson** (7,858 reference edges):

| metric | first (#3783) | after overload choice (#3835) | after generic constructors (#4124) |
|---|---|---|---|
| confident precision | 59.8% (4,778 judged) | 92.7% (3,474 judged) | 93.2% (3,727 judged) |
| recall | 36.3% | 41.0% | 44.2% |
| resolution recall | 38.7% | 43.6% | 45.3% |
| strict precision (JDK calls counted wrong) | 54.4% | 82.9% | 84.0% |

#4124 has two parts:
- **Generic constructors are extracted.** `calls_out` now takes `new TypeToken<X>() {}` and
  `new ArrayList<>(xs)`.
- **The reference picks the right constructor.** For an anonymous subclass, scip-java
  references the class, not a constructor. The adapter used to map every such reference to
  the class's last constructor. It now picks the constructor by argument count. Without that
  fix, 137 right links to `TypeToken()` scored as wrong overloads.

**Overloads were most of the first gap.** 1,653 of the first 1,923 `wrong` links went to
a different **overload of the right method** in the same class, which is why
`call_graph_resolution.py` reports an overload-blind view for `OVERLOADED_LANGS` (baselined,
not gated).

#3835 made the resolver choose an overload by argument count:
- **What the detector records:** for Java, the argument counts each callee is called with
  (`calls_out_arities`).
- **One match:** the call links to the one overload declaring that many parameters. A
  method that calls two overloads links to both.
- **Several matches, or none:** a count that matches several overloads (`fromJson(String,
  Class)` vs `fromJson(Reader, Type)`) or none (varargs) becomes the ambiguous step
  `overload`. That's a row, never an edge: triage's `ambiguous/overload`, 1,396 reference
  edges.

The overload-blind view now equals the strict one: no confident link lands on the wrong
overload.

**What scip-java can't see:** calls through an abstract type or an interface (`typeAdapter.read()`)
point at a bodyless declaration. Those links come out `unconfirmed`, not `wrong`.

**SCIP or a native tool, per language?** The deciding check ran scip-typescript 0.4.0 on
zod through the same adapter and compared it edge by edge with `ts_callgraph.js`:
- **Its edges are trustworthy:** 96.5% of them are in tsc's graph too.
- **It covers only 52.4% of tsc's edges.** 88% of the gap is callers that scip-typescript
  doesn't record as definitions with an extent: zod's `inst.refine = (...) =>` member
  assignments, quoted keys, and object-literal methods.

**The decision:**
- Use a SCIP indexer when it runs the language's compiler and records definitions fully,
  as scip-java does.
- Keep a native adapter where one already sees more, as tsc does for TypeScript.
- Before adopting SCIP for a new language, repeat the cross-check where a native reference
  exists:

```sh
python tests/tools/scip_callgraph.py contract <index.scip> <source-root> --lang <lang> > scip.json
python tests/tools/callgraph_refs.py <lang> <repo> > native.json
python tests/tools/scip_callgraph.py compare native.json scip.json
```

## Call resolution in Go (#3782)

Go is scored against the call graph of `golang.org/x/tools` 0.37.0, built by
`tests/tools/go_callgraph/main.go` (run through `go run -C`, so it needs a Go 1.24+ toolchain on
PATH; the repo's own `go.sum` pins the module). It type-checks every package of the repo,
`_test.go` files included (the engine scans them too, and leaving them out left 1,019 engine
ends unmapped against 2 with them), builds SSA, and takes the VTA graph over a CHA seed.
Functions are named bare (`Execute`, not `Command.Execute`) at the line of their `func`
keyword, as the engine names them. A closure's calls belong to its enclosing function, a
generic instantiation to its declaration, and a call that resolves to a function without a
body in the repo is `external` (the strict-precision count).

**What the Go reference cannot see (cobra, 1,636 reference edges):** build tags are the host's
(linux/amd64), so a call in a file a build constraint excludes (a `_windows.go`) is not in the reference. VTA only follows an interface
call to types that reach it in the analysed program, so a library method called by clients
outside the repo has no incoming edge. Calls through `reflect` or a value that comes from
outside get none. Read those as the reference's blind spot, not engine error. The `external`
verdicts are the engine's: 123 confident links land on a name (`Len`, `Error`) that the checker
resolves to the standard library, the bare-name collision the strict precision counts.

## Call resolution in C (#3784)

C is scored against **libclang** (`tests/tools/clang_callgraph.py`, the pip `libclang==18.1.1`
bindings with a bundled library; `pip install libclang==18.1.1`). Each `.c` file is one translation
unit, with every directory holding a header as an `-I` path; no compilation database is needed for a
call graph. Directories named `win` are not parsed (they need `<windows.h>`).

- A def is a function with a body, in a `.c` file or a header. A prototype is not (#3757).
- A static callee is that translation unit's own definition; any other callee is linked by symbol name to
  every external-linkage def, which is the link group across translation units. Where per-platform files
  define one external name (`uv__io_poll`), the reference links the call to each.
- A callee with no def in the repo (libc, a system header) is `external`. A call through a function
  pointer names no function and is skipped. A macro that expands to a call is a call.

**First numbers vs libclang** (hiredis + libuv, 2,163 confident links judged): precision 100.0%, recall
25.3%, resolution recall 58.8%, 2,790 confident links unmapped.

**What the reference cannot see:** it parses one preprocessor configuration (Linux), so code under
another platform's branch has no reference def (its engine links are `unmapped`); Windows-only sources are a second link group since #3784 (below). And
the recall gap has engine-side causes the reference is right about: libuv's `TEST_IMPL(name)` functions
(612 reference defs the engine does not extract) and `docs/code/` (113 defs, files the engine does not ingest).
Headers libclang cannot find (the bundled build has no compiler headers) leave some types unknown, but a
call to a declared function still resolves.


## Call resolution in C++ (#3784)

C++ is scored against the same **libclang** adapter in `cpp` mode (`tests/tools/clang_callgraph.py cpp`,
`pip install libclang==18.1.1`; the wheel ships no C++ system headers, so the host g++'s `#include <...>`
list is passed as `-isystem`). Each `.cc`, `.cpp` or `.cxx` file is one translation unit.

- Edges link by USR, so an overload resolves exactly; a call to a template resolves to the pattern, whatever the
  instantiation. Internal linkage (`static`, an anonymous namespace) stays the translation unit's own definition.
- A definition is named as the engine names it: bare, except an out-of-line member (`int Foo::bar() {...}`) is
  `Foo::bar`. A callee with no def in the repo (std, libc) is `external`.

**First numbers vs libclang** (fmt, 1,741 confident links judged): precision 91.1% (96.3% overload-blind, 81.5%
strict), recall 16.3%, resolution recall 63.8%, 90 wrong-overload links, 204 external, 1,680 unmapped.

**What the reference cannot see:** it parses one preprocessor configuration, and it deliberately does not mimic
the engine's leading `::name` for out-of-line members of template classes, so those links count as unmapped.
The low recall is mostly engine-side and is not tuned away: gtest `TEST` macros in `test/`, the `::name`
convention and template-overload line mismatches. They feed a later miss sweep. A template conversion operator is
named without its template arguments (`operator Box`), as the engine does.

**gtest bodies (#3784):** a `TEST(suite, name)` body is the reference's `suite_name_Test::TestBody`; the adapter now
reads the macro line and names it `name`, as the engine does, so 6,117 of the former 6,409 `caller_unmapped` misses map.
That alone dropped confident precision 91.1% -> 79.1%: their `fmt::format(...)` calls reached an unrelated `format`
member such as `formatter<X>::format` through the import-stem step. With a namespace-qualified call no longer landing
on a class member there (`_NAMESPACE_QUALIFIED_LANGS`, C++ only), the first numbers on the larger judged set
(2,325 confident links, was 1,741) are precision 84.1% (92.9% overload-blind, 75.2% strict), recall 20.1% (was 16.3%),
resolution recall 58.8%, 203 wrong-overload links. The `import` links to chrono/ranges `formatter::format` are gone.
**Scope marker (#3784):** the detector also marks a C++ call written `ns::f()` by prefixing its qualifier with `::`
(`::fmt`, `::a.b`, `::` for a global `::f()`); `x.f()` and `p->f()` stay unmarked. The resolver then tries a free
function the caller can see (its own file, or one it imports) before the untyped-receiver method ladder, so `fmt::format`
no longer lands on a `format` member of the caller's own file (the `file` step), and an unmarked `x.f()` can reach a
member by import stem again. A marked call with no visible free definition falls back to the method ladder; a free
function the caller cannot see is never linked (`std::move` must not reach a repo `move`). Measured on fmt (2,479
confident links judged, was 2,325): precision 84.1% (unchanged), recall 21.5% (was 20.1%), resolution recall 63.3% (was
58.8%), ambiguous precision 35.1% (was 34.1%), 220 wrong-overload links (was 203; more links are judged).

**Lock-annotation tail (#3772):** `void Mock::AllowLeak(const void* p)` followed on its own indented line by
`GTEST_LOCK_EXCLUDED_(mu) {` was named after the macro, so its callers were unmapped. The `func_start` tail now
accepts an indented annotation macro with arguments from the LOCK / EXCLUDE / REQUIRE / ACQUIRE / RELEASE / GUARDED
vocabulary. Before -> after: confident precision 91.1% -> 91.4%, recall 16.3% -> 17.0%, ambiguous precision
41.5% -> 47.1%, 162 fewer `caller_unmapped`, 67 more links. Resolution recall reads 63.8% -> 62.6% because the 162
newly mapped callers enter its denominator and only 67 of their edges link; the other 95 fall in buckets already open
(`ambiguous/receiver` +33, `not_extracted/other` +28, `resolved_outside` +22). Linked edges rose by a net 67; confident-wrong links did not rise (wrong-overload 90 -> 89).

**Overload choice (#3784):** C++ joins `OVERLOAD_LANGS`: the detector records each callee's argument counts
(`calls_out_arities`), and the resolver picks the same-class, same-file overload declaring that many parameters. A
count that matches several overloads or none (a default argument, a variadic, an uncounted `Type x(args)`
construction) leaves an ambiguous `overload` row, never an edge. Measured on fmt (2,188 confident links judged, was
2,479): precision 92.3% (was 84.1%), strict 82.0% (was 74.9%), wrong-overload links 23 (was 220), recall 20.8% (was
21.5%), resolution recall 60.5% (was 63.3%). The recall dip is the trade: calls the counts cannot choose are no longer
guessed. **C (hiredis, libuv)** has no overloads; the reference run is unchanged (2,163 judged, precision 100.0%,
recall 25.3%, resolution recall 58.8%), so the unmapped links (2,789) are the open C item.

**Class-template member names (#3772):** `Foo<T>::bar(...) {` was named `::bar`: the name tokenizer split at the
`<`, `,` and `>` of the class's argument list and kept the tail. The detector now strips a class-template argument list
that is directly followed by `::` (three nesting levels, as the `func_start` rule), so the unit is `Foo::bar` as libclang
names it (constructors, destructors, operators, `ns::Foo<T>::m` and `template<>` specialisations alike; `operator<`,
`operator<<` and a return type's `<...>` keep theirs). The own-header filter strips the same list, so the header's
`Foo<T>::m(` is not read as a call to `m`. Measured on fmt, before -> after: linked edges 2,089 -> 2,139, recall 21.5% ->
22.0%, resolution recall 59.8% -> 61.3%, `caller_unmapped` 1,249 -> 1,226, confident precision 92.5% -> 92.2% (inside the
0.5-point tolerance), wrong 170 -> 180 and `unmapped_src` 504 -> 544: callers that were unnamed enter the judged set
with their links, 10 of them wrong (not read in source one by one). Test:
`tests/extraction/languages/test_cpp_template_member_names_3772.py`.

**One-line namespace members (#3772):** `func_start` is anchored at the start of a line, so a definition written after
its namespace opener (`namespace n { template<class T> T Box<T>::get() {...} }`) was not extracted at all. `cpp` now
accepts up to three `namespace [qualified::name] {` openers before the definition. fmt call-graph metrics are unchanged
(no such line there) and neither crucible golden nor any doom-rosetta port moves. Not covered: the same shape after
`extern "C" {` (the one-line form is not reached by the cpp rule; the multi-line form works). Test:
`tests/extraction/languages/test_cpp_namespace_oneline_member_3772.py`.

**C macro-defined functions (#3784):** libuv defines its tests as `TEST_IMPL(kill) {`, which declares `run_test_kill`;
the engine names the unit `kill`. The adapter now names a def written as a one-argument macro by the argument (the
same idea as the gtest names above), so those engine ends map. Adapter only, no engine change. Before -> after
(hiredis + libuv): confident links judged 2,163 -> 3,532, unmapped 2,789 -> 1,356, precision 100.0% (unchanged),
recall 25.3% -> 41.5%. Resolution recall reads 58.8% -> 53.6% because the newly mapped callers enter its denominator.
**C Windows link group (#3784):** libuv `src/win/` (25 files), `test/runner-win.c` and hiredis `sockcompat.c` were not
parsed because their names collide with the Unix ones. The adapter now parses them as a second group under
`-D_WIN32`: a Windows caller links to the Windows definitions of a name, falling back to the shared ones (not under
`unix/`); a Unix caller never links to a Windows definition. No `windows.h` on the host, so a Win32 API call is
`external`, never an edge. Adapter only, no engine change. Before -> after (hiredis + libuv): confident links judged
3,532 -> 3,942, unmapped 1,356 -> 635, precision 100.0% (unchanged), recall 41.5% -> 42.3%, resolution recall
53.6% -> 55.2%.
**C platform link groups (#3784, slice 6):** a file that names a platform macro (`_WIN32`, `__APPLE__`/`__MACH__`,
`_AIX`, `__sun`) is now parsed once more with it defined, besides the Linux parse (a Windows-only source is parsed only
under `-D_WIN32`). That covers the in-file branches the file-name rule missed: libuv `fsevents.c`, `aix.c`, `sunos.c`,
the `uv_barrier_*` fallbacks in `thread-common.c`, and the `_WIN32` bodies of `test/test-tty-escape-sequence-processing.c`,
`test-fs.c`, `test-fs-event.c`, `test-spawn.c`. A def only a platform parse saw belongs to that platform's group; a
platform caller links its group's definitions first, then the shared ones; a Linux caller never links to a platform
def. One function written as several `#if` variants in one file is one unit to the engine, so an edge to one variant
links all of them (without that, 20 links were judged `wrong` for picking the other variant). The Windows-only sources also
get `-D_MSC_VER=1800` (libuv's `snprintf.c` fallback); other files do not (it made hiredis `ffc.h` calls resolve
outside the repo). Adapter only, no engine change. Before -> after (hiredis + libuv): confident links judged
3,942 -> 4,264, unmapped 635 -> 237, precision 100.0% (unchanged). **Recall reads 42.3% -> 36.7% and resolution recall
55.2% -> 49.4%** because the reference now holds the per-platform edges (9,314 -> 11,608): the denominator grew, the
engine's links did not get worse.
**What stays unmapped (237):** the `REDIS_TEST` and SSL-only test bodies, the Qt adapter and example, `m4/` macros, and
other platforms' branches with no macro on the list. C++ (fmt) has no platform-only sources and was measured in the
section above; its adapter needs no change for this slice.
**C more platform rows (#3784, slice 7):** `__FreeBSD__`, `__QNX__` and `__MVS__` join `PLATFORMS` (libuv `freebsd.c`,
`qnx.c` and the in-file branches of `kqueue.c`, `tty.c`, `fs.c`). Measured honestly, the gain is small: confident links
judged 4,264 -> 4,266, unmapped 237 -> 236, reference edges 11,608 -> 11,617, precision 100.0%, recall 36.7% and
resolution recall 49.4% unchanged. Most of those files are already parsed through an existing row, or their
platform-only defs are not called from elsewhere. Adapter only; the baseline is regenerated.

### The three expected findings (#3784 acceptance)

| Expected finding | Where the reference handles it | Pinned by |
|---|---|---|
| Calls into header prototypes (bodyless declarations, #3757) | C: a prototype is no def, the call links to the body in whichever `.c` file or header defines it. C++: edges link by USR, which a prototype and its definition share | `test_clang_callgraph_resolves_c_calls_across_translation_units`, `..._cpp_calls_by_usr_with_engine_names` |
| The C/C++ link group across translation units | C: a non-static callee links by symbol name to every external-linkage def; static callees stay in their own unit; Windows and per-platform parses are further groups. C++: USR linking; an anonymous-namespace or `static` callee stays in its own unit | the same two tests, plus `..._links_windows_sources_as_their_own_group`, `..._parses_a_file_naming_a_platform_macro_once_more_per_platform`, `..._parses_freebsd_qnx_and_mvs_branches_as_platform_groups` |
| Macros that look like calls | Judged as the compiler sees them: `SQ(x)` expanding to arithmetic is not a call, `VIA(x)` expanding to `helper(x)` is. A def written as a one-argument macro (`TEST_IMPL(kill) {`) is named by the argument, as is a gtest body | the C test above (`SQ` / `VIA`), `..._names_a_one_argument_macro_def_as_the_engine_does`, `..._names_a_gtest_body_by_its_test_name` |

All three are covered and gated by `graph-accuracy-audit.yml` against `tests/call_graph_resolution_c_baseline.json` and
`tests/call_graph_resolution_cpp_baseline.json`. Open engine-side gaps the reference exposes (unextracted `docs/code/`,
the `::name` template-member convention, 236 unmapped C ends) are miss-sweep leads for the engine, not reference work.

## Span anchoring

A unit is mis-anchored when its `start_line` opens before the declaration, on lines that belong
to other code: blank lines, comments, or lines that end a previous construct (`{`, `}`, `,`, `;`,
`*/`). Annotation, attribute, decorator, `template <...>` and C return-type lines are part of the
declaration and are not counted. Lower is better. The shape comes from #3543, where a
`func_start` pattern swallows the newline before the declaration.

## Adding a language, and finding what to fix (#3772)

Each reference is an adapter registered in `tests/tools/callgraph_refs.py`. It emits one
JSON contract: `defs`, `edges` (each with its first call site), and optionally `external`.
The scorer never changes per language. A new language is an adapter, a registry entry
(tool, pinned version, corpus) and a baseline.

The reference graph depends only on the corpus repo's content (its git tree), the tool
version and the adapter's code, so it's cached (`GITGALAXY_CALLGRAPH_CACHE`, default
`~/.cache/gitgalaxy/callgraph_refs`). Re-running a gate after an engine change costs only
the engine scan: zod's reference loads in about 1 second, where building it takes about 20.

| tool | question it answers |
|---|---|
| `callgraph_triage.py <lang>` | Where is the gap? Every missed reference edge goes into one bucket (`not_extracted/in_string`, `ambiguous/receiver`, `resolved_outside`, …), and every confident link gets a precision verdict. Buckets are ranked by count, with source lines, and add up exactly to the recall gap. `--split <bucket>` breaks one bucket down by call-site shape and receiver (`z.x()`, `...f()`, `new X()`), and `--json` adds each sample's source line. |
| `explain_call.py <db\|repo> <file>:<function> [callee]` | Why did one call resolve the way it did? It re-runs the real resolver on the scan's own inputs, checks the result against the recorded rows, and lists every candidate with its `def_shape` and whether a bare call or a receiver can reach it. |
| `callgraph_check.py` | Is the PR ready? It runs the per-language gates, the focused tests, crucible, the tree-sitter audit and the lint audits, one line per step, with logs on disk. A missing tool or pin fails the run, and `--regenerate` rewrites baselines only when everything passes. |

Two skills turn these into a routine. `callgraph-language-onboarding` is the checklist for
adding a language's reference, and `callgraph-miss-sweep` is the fix loop: triage, then the
known-pattern table, then source verification, then the fix, then the net-change rule. The
Haiku `callgraph-triage-scout` agent does their mechanical runs.

A fresh Claude Code on the web session installs all of this at CI's pins through
`.claude/hooks/session-start.sh`. That covers pyan3, typescript 6.0.2, the test and lint
tools, and both corpora, and it reports up front when the environment can't run
full-precision golden masters.

### What the JavaScript reference cannot see (#3781)

`javascript` runs the TypeScript checker with `allowJs` over express's `.js/.cjs/.mjs` files
(`ts_callgraph.js --js`). CommonJS `require` and `exports.f = function` /
`module.exports = function` declarations resolve and are named as the engine names them
(no unmapped ends). The checker has little to go on without types: `this.route(...)` inside a
function assigned to `app.x` and calls on untyped parameters get no edge, so those engine
links come back `unconfirmed` or the reference edge is simply absent (express: 29 reference
edges in 341 definitions). Read those as the reference's blind spot, not engine error. All
numbers are "vs tsc (allowJs)".

### What the Rust reference cannot see (#3785)

`rust` reads rust-analyzer's SCIP index of serde-rs/json through the shared adapter
(`scip_callgraph.rust_analyzer_contract`). An `impl` method is named by its method name, a
trait method without a default body is not a definition (#3757), and a macro reference is not
a call. Macro-generated calls (the `serde` derives, `format_args!` expansions) are invisible
to a text extractor and to the index's call positions: a deliberate limit, not an engine
defect. Calls through a trait object or a generic bound resolve to the bodyless trait
declaration, so they count as neither an edge nor `external`. All numbers are "vs
rust-analyzer".

Measured against rust-analyzer 1.90.0 on serde-rs/json: confident precision 93.8% (694 judged),
ambiguous 60.4%, recall 60.1%, resolution recall 64.9%; 41 confident links resolve outside the
repo and 207 end at a function the index has none for. Read from the real index:

- **`impl` methods carry no owner** (`class_start` has `struct`/`enum`/`trait` but an `impl` block is
  a separate span), so `self.m()` had no class to walk and 239 of the first 424 `resolved_outside`
  edges were `self.` calls into the same file. The resolver now lets a `self` receiver in Rust reach
  any definition (`_IMPL_SELF_LANGS`: recall 39.9% -> 60.1%, precision 92.1% -> 93.8%). Widening
  every receiver the same way was tried and rejected: `x.len()` linked to every repo `len`
  (`external` 40 -> 138, precision down to about 71%). A typed receiver (`de.m()`) and a
  `Type::new(` path need the impl's type as the owner, a detector change not made here.

- rust-analyzer emits **no `enclosing_range`**, so the adapter reads a fn's extent from the
  source (`scip_callgraph._rust_enclosing`: to the `;` of a bodyless declaration, else through
  the matching `}`).
- Code behind a `cfg` feature the index was not built with (`arbitrary_precision`) is not
  indexed: its links are unmapped.
- A call through a generic bound or trait object (`visitor.visit_bool(v)`, `R::set_failed`)
  resolves to the trait declaration or a dependency, so the engine's link to one concrete impl
  is `external` or `unconfirmed`, not wrong. A bare `Type::new(` the engine ties to the wrong
  `new` (`from_slice` -> `IoRead::new`, not `SliceRead::new`) and a same-name fn in a sibling
  module (`normalize`, `iadd_impl` in `lexical/math.rs`) are real engine errors.
- A call inside a `macro_rules!` body (`tests/test.rs`) is a macro limit.

The baseline is committed, the CI gate runs it (`graph-accuracy-audit.yml`, toolchain 1.90.0), and the session hook installs the toolchain.

## Running locally

```sh
PYTHONPATH="$PWD" python tests/tools/import_graph_accuracy.py --fetch-only       # once
PYTHONPATH="$PWD" python tests/tools/import_graph_accuracy.py --samples 5        # report + examples
PYTHONPATH="$PWD" python tests/tools/call_graph_resolution.py python --ci       # needs pyan3==2.9.0
PYTHONPATH="$PWD" python tests/tools/call_graph_resolution.py typescript --ci   # needs node + typescript@6.0.2
PYTHONPATH="$PWD" python tests/tools/call_graph_resolution.py javascript --ci   # same checker, allowJs
PYTHONPATH="$PWD" python tests/tools/call_graph_resolution.py rust --ci         # needs rustup toolchain 1.90.0 + rust-analyzer
PYTHONPATH="$PWD" python tests/tools/call_graph_resolution.py go --ci           # needs Go 1.24+ on PATH
PYTHONPATH="$PWD" python tests/tools/call_graph_resolution.py c --ci            # needs libclang==18.1.1
PYTHONPATH="$PWD" python tests/tools/call_graph_resolution.py cpp --ci          # libclang==18.1.1 plus a host g++
PYTHONPATH="$PWD" python tests/tools/span_anchor_audit.py --ci
python tests/tools/callgraph_triage.py typescript --samples 3     # ranked buckets of misses and wrong links
python tests/tools/callgraph_check.py                             # the whole chain, one line per step
# after an intended improvement: the same commands with --regenerate, committed with the fix
```

All of them refuse to pass on an empty measurement (#2682).

**Which gates run (#6501).** `graph-accuracy-audit.yml` starts with a `plan` job (`tests/tools/graph_accuracy_plan.py`, stdlib) that maps the
changed files to the gates they can move: a language's standard selects its call gate (if it has one), import-graph (if the language is in
`tests/import_graph_corpus.json`) and span anchoring; a gate's tool or baseline selects that gate, and a shared adapter selects every gate on it;
shared core, the workflow and the corpus list select all; anything else selects none. Toolchains and corpora install only for the selected
gates. A failed plan runs every gate; the check name `graph-accuracy-audit` is unchanged.

**Call-graph and detection audits (#6501).** `call-graph-accuracy-audit.yml` and `detection-accuracy-audit.yml` each start with a `plan` job
(`tests/tools/accuracy_audit_plan.py --audit call-graph|detection`, stdlib). A change to a shared input (the tool, its baseline, the crucible pins,
`detector.py`/`prism.py` or `language_lens.py`/`gitgalaxy_config.py`, any `language_standards` file that is not one language's) runs the audit. A
language file runs it only when the diff moves something the audit reads: for call-graph, any code line of a baseline language, else a detection
key; for detection, a `rules` entry (every rule is scored) or a key the lens reads. Comments, `_meta` and underscore-prefixed rules skip it. A hunk
the planner cannot place, a new file, a non-PR event or a failed plan runs it. The saving is small for detection by construction.

**Tree-sitter audit and history (#6501).** `tree-sitter-accuracy-audit.yml` and `tree-sitter-accuracy-history.yml` also start with a `plan` job
(`accuracy_audit_plan.py --audit tree-sitter|tree-sitter-history`) that outputs `langs`: a language's file selects that language (an underscore rule
counts, `_dependency_capture` is read), a baseline file selects its language, a key the lens reads or any shared input selects all; comments and `_meta` select none.
The history plans the diff since the last successful run, not `github.event.before` (a replaced queued run would drop its push).

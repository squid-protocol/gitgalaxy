# DOOM Port Speedrun harness (#5468)

Reproduces the DOOM port study (#5457) from the repo: 44 DOOM ports pinned by SHA in `tests/doom_rosetta/manifest.csv`, cloned shallow
at that SHA into a scratch directory, scanned with the current engine, and scored by seven clean-scan checks. Each run
is keyed by the engine's git SHA, so before/after for one fix is a diff of two result directories. This corpus is
becoming DOOM-rosetta, a golden-gated CI test (#5619).

**No third-party code is committed.** The manifest holds names, URLs, SHAs, languages, class, license and lineage
only; clones are fetched at run time under `--work` (default `/tmp/gitgalaxy-scratch/doom-speedrun`, refused inside
the repo). The zero-drift gate and the nightly runs are in CI (`tests/doom_rosetta/README.md`); this harness is also run by hand.

"DOOM" is used descriptively only. This project is not affiliated with or endorsed by id Software, ZeniMax Media or
Microsoft. No WADs or other game data are fetched, committed or cached.

## Licensing rule (owner, 2026-10-19)

GitGalaxy is an LLC, so every use is commercial. Only **clearly licensed** ports go into this manifest, and from it
into CI, its caches, any committed golden and any publication: an OSI license (or CC0 for content) read from the
repo's own files, original or properly released source, no provenance concern. GitHub's detected license is often
`NONE` when the file sits in a subdirectory (`prboom2/COPYING`, `licenses/`, `doc/LICENSE`), so read the files; the
`license` column records what was found and where when it is not at the root.

Anything questionable (no license file, code reverse-engineered from a commercial release, mixed per-file notices) is
**internal only**: the maintainer keeps a separate manifest and license register outside this repo and runs it with
`--manifest`. Nothing from it is committed, cached in CI, or named or quoted in public issues, PRs or docs; an engine
bug it reveals is filed with our own fixture. Not legal advice.

To add a port: read its license from the files, pin a SHA, add a row with `class` and `license`, and run
`run --only <name>` (rc 0) before committing.

## Manifest columns

`name`, `upstream`, `sha` (the pinned commit), `branch` (informational), `languages`, `lineage`, `license`, and
`class`: `engine-port` (derived from or translated from id's released engine source, in any language),
`reimplementation` (an independent engine that plays DOOM data), `raycaster` (a DOOM-like raycaster, not the DOOM
engine), `separate-engine` (a later id engine) or `assets` (a content project).

`fidelity`, `fidelity_file`, `fidelity_phrase` (#5620): what the port's own README says about its fidelity to the
original, read from the pinned clone. `fidelity` is `original` (linuxdoom), `faithful` (aims to reproduce the original,
bugs included), `compatible` (states demo / data / behaviour compatibility while changing or adding), `enhanced`
(states added features, no fidelity claim), `divergent` (disclaims being a port of, or exact to, the original) or
`unstated` (no README, or silent). Anything but `original` / `unstated` names the README and a short quoted phrase.
It records a claim, not a measurement. `fidelity.py check --work DIR` re-reads every phrase from the clones (a missing
clone is reported as unchecked; `--strict` makes it an error) and `fidelity.py report` prints the class x fidelity counts.

```bash
python tests/tools/doom_speedrun/doom_speedrun.py run --oracle                # all ports: clone, scan, score, report
python tests/tools/doom_speedrun/doom_speedrun.py run --only linuxdoom,gore   # a subset
python tests/tools/doom_speedrun/doom_speedrun.py score --oracle              # re-score existing scans
```

Compare two runs, or a run against round 2 (`diff BEFORE AFTER`; each ref is a `clean_check.csv`, a results dir, an
engine SHA under `<work>/results`, or `round2` for the study's CSV, overridable with `DOOM_ROUND2_CSV`):

```bash
python tests/tools/doom_speedrun/doom_speedrun.py diff round2 41777e5f4 --fail-on-regression
```

It prints the PERFECT counts, each port whose scored columns moved, and the regressions (a port that gained a failed
check or vanished); `--fail-on-regression` exits 1 on any. Round 2's CSV has no tree-sitter columns, so only columns
both files carry are compared. A diff against round 2 is expected to move (the engine changed): read it, don't gate on it.

Steps (`fetch`, `scan`, `score`, `report`) can be run singly and are resumable. Scans go through
`tests/tools/box/heavy-run.sh` when present. Results land in `<work>/results/<engine-sha>/`: `clean_check.csv`,
`clean_check.md` (table) and `details.json` (the offending files and rules).

## The seven checks (first-party code only)

| # | check | passes when |
|---|---|---|
| 1 | coverage | every first-party source file is mapped; a "Machine-Generated" exclusion counts only with a generator banner in the head; a payload-blocked file with zero ctags definitions is reported as `data_files_excluded`, not a miss; files excluded by design (a `docs/` tree, `__MACOSX/` / `._*` AppleDouble, a `third_party` / `thirdparty` directory, re2c/bison/flex-generated parser source by banner, a Bison parser or `@generated` marker without a "generated by" banner, and `build/scripts` / `web/site` tooling directories) are counted in `excluded_by_design` with a per-category reason column (`excluded_by_design_reasons`, each file in `details.json`), not as a miss |
| 2 | language | each mapped file's language fits its extension (`.h` as objective-c needs ObjC syntax, `.m` must be objective-c, ...) |
| 3 | functions | engine function count within 3% of Universal Ctags (definitions only, per-language kinds) OR of tree-sitter over the mapped files; the `functions_agree` column says which (`ctags` tried first) |
| 4 | typosquat | no `TYPOSQUATTING DETECTED` log lines |
| 5 | credentials | no `has_credentials` files (SARIF error-level results are listed in `details.json` for review, never scored) |
| 6 | health | scan rc is 0 and no `[ERROR]` / `CLASSIFICATION REFUTATION` / `Traceback` log lines (engine-wide warnings ignored) |
| 7 | callgraph | call edges match the tree-sitter body oracle (C/C++: `callgraph_oracle.py`, below; go, java, csharp, rust, javascript, python, kotlin, lua, shell, tcl: `ts_callgraph_oracle.py`): zero misses and zero engine-only edges of kind `absent` or `comment/string`. Columns `callgraph_recall`, `callgraph_precision`, `callgraph_misses`, `callgraph_engine_only` (scored) and `callgraph_unscored` (engine-only `type`, `function-pointer`, `macro`). A port with no oracle (a licensed C/C++ port with no C/C++ function, or none of those seven languages: dart, scheme, crystal, fsharp, cobol, fortran, assembly, sql) reports every column as `n/a`: a pass, but shown as unscored |

The report prints two PERFECT counts while check 7 lands: seven checks (`verdict`) and the first six (`verdict6`).

Vendoring is decided by the engine's own `VendorDirectoryDetector`. `--legacy-vendor` adds the round-2 study's
hand-kept vendor-name list, for comparing against round 2's table.

## Second oracle (`--oracle`)

`treesitter_functions` / `ts_delta_pct`: tree-sitter function-definition node counts over the same files, reported
beside ctags; it is scored only as the fallback of check 3 (within 3% of ctags OR tree-sitter). ctags misses macro-defined functions (#5461), so agreeing with ctags alone is not the
claim.

## libclang subset oracle (`--clang PORTS`)

```bash
pip install libclang          # the wheel bundles the shared library; import is lazy, so it is optional
python tests/tools/doom_speedrun/doom_speedrun.py score --clang linuxdoom,doomretro   # or --clang all
```

`doom_clang.py` parses each mapped C/C++ file with libclang, which runs the preprocessor first, and counts function
definitions (functions, methods, constructors, destructors, templates) located in that file itself (a definition in an
included header counts for the header). Flags come from the repo's `compile_commands.json` (or `build/`) when it
lists the file; otherwise `-I` for the file's directory, the repo root and every header directory (capped at 300).
Columns, only when `--clang` is given: `clang_files`, `clang_files_with_errors`, `clang_compile_commands_files`,
`clang_functions`, `clang_gg_functions` (the engine's count over the same files), `clang_delta_pct`. Without the
wheel the columns stay empty and `details.json` says so.

Blind spots of this oracle:
- **Only the active preprocessor configuration is counted.** Code behind an `#ifdef` that the guessed flags leave off
  (Windows-only files, SDL back ends) counts 0, so the engine looks like it over-counts there. First scan at
  `41777e5f4`: linuxdoom 0.3%, doomgeneric 2.9%, chocolate-doom 4.2%, doomretro 4.2%, all positive, the files behind
  the gap being platform code.
- **Missing headers.** Most ports have no build here, so `clang_files_with_errors` is high (89/129 on linuxdoom);
  macros that depend on a missing header may expand differently. A real `compile_commands.json` is the fix, and
  no pinned repo ships one at its SHA.
- Like the others it measures counts, not which functions: read the disputed files before claiming either tool right.

## Known blind spots

- **Agreement is not correctness.** A 0% delta means two counters agree on a number; it says nothing about which
  functions. Per `CLAUDE.md`, a correctness claim needs someone reading the disputed source.
- **ctags and tree-sitter share blind spots on C macros.** Both can miss a function a macro generates (`DEFINE_*(...)`),
  and tree-sitter may count a mis-parsed macro use as a function; the delta can cancel real misses and extras.
- **Languages ctags/tree-sitter lack** (assembly, makefile, ...) are in no oracle: checks 3 and the oracle skip them.
- **Check 1 only sees `SRC_EXT` files**; a first-party file with another extension is invisible to it. `SRC_EXT` covers every code language in the manifest (a test pins it); SQL and JCL are not in it.
- **Vendoring is the engine's call**: a vendored tree the detector misses leaks into check 1/2/3 as first-party.
- **Check 6 reads the log text**, so a new log wording needs `log_problems` updated.
- **Check 7 does not score the edge convention (open owner question, #5874):** a C++ constructor (`new T(...)`,
  `T x(...)`, kind `type`) and a bare function-pointer reference are engine-only edges the oracle does not count; so is
  a callee named only inside a preprocessor line in the body (`macro`). They are in `callgraph_unscored`, so a port can
  pass with a wrong-by-convention precision (doom3-bfg's gap is mostly `type`). The oracle is one tree-sitter body
  walk: it shares tree-sitter's blind spots (a macro-generated call, a misparsed region falls back to text).
  `ts_callgraph_oracle.py` is the same walk for the ten other covered languages, matched by bare name: no text
  fallback (a function with no node at its start line is counted `unmatched`), a Rust macro's tokens are read as
  `name (...)` (so `vec![T::default()]` counts) except under `quote!`/`quote_spanned!`/`stringify!`, a C# `: base(...)`
  initializer counts, a shell or Tcl command word naming a function the port defines is a call (a Lua call is an ordinary call; the three were added for #5640's shapes, measured at 0 misses on edge-classic, sqldoom and odamex), a Kotlin trailing-lambda-only call of a stdlib scope function (`run`, `map`, ...) is no call, and a Dart/Scheme/... port is `n/a`. Crystal is not covered: its grammar swallows ~46% of doo-cr's functions in ERROR nodes. It has no baseline file and no `LICENSED` gate (it
  reads only the scan DB and clone the scorer already has); a mixed port in `LICENSED` (a C port with a Python tool)
  is scored by the C/C++ oracle only.
- **Pinned SHAs are the ports' HEAD at study time** (2026-10-18); a force-pushed upstream makes `fetch` fail loudly.
- **Round 2's CSV was produced at engine `585c243e9`**; the current engine will differ, which is the point.
- **`#ifdef`/`#else` alternate definitions are both counted.** A static scan cannot know the build configuration, so both branches are real source (owner ruling nyx-o9, 2026-10-21, #5462).

## C/C++ call-graph oracle (`callgraph_oracle.py`, #5630)

Structural extraction has ctags, tree-sitter and libclang beside it; C/C++ call edges had no independent check (the
Graph Accuracy Audit covers Python, TypeScript and Java). This reads the scans `scan` leaves and checks
`calls_out_to` two ways, licensed ports only (the `LICENSED` set; any other port is refused):

```bash
python tests/tools/doom_speedrun/doom_speedrun.py scan --only <the 20 C/C++ ports in callgraph_baseline.json>
python tests/tools/doom_speedrun/callgraph_oracle.py --only all --baseline tests/tools/doom_speedrun/callgraph_baseline.json --fail-on-regression
python tests/tools/doom_speedrun/callgraph_oracle.py --only eternity,odamex,gzdoom --family linuxdoom,doomgeneric,doom-ascii,sdl-doom
```

1. **Body oracle**: each engine function is matched to the tree-sitter `function_definition` at its start line; every
   `call_expression` whose callee the port defines (`f(`, `f<T>(`, `obj.f(`, `ns::f(`; a declaration such as
   `std::unique_lock<...> lock(m)` is not a call) is an oracle call. Self-edges are ignored on both sides (the engine
   drops recursion by contract, #3327; owner ruling 2026-10-19, #5630), never scored as a miss. A miss is
   named by the call's parent: statement, nested-argument, condition/return, assignment-rhs, after-cast,
   after-operator, subscript, or `unparsed` (below). An engine-only edge is named by how the callee appears in the
   body: function-pointer (a bare reference), type (a C++ class named as a type: `new T`, `T x(...)`), macro (only in a
   `#define` line), comment/string, or absent. `--only all` runs every licensed port that has a scan.
2. **Family consensus** (`--family`, default the nine vanilla-lineage ports): an edge >= 75% of the siblings that
   define both ends carry (at least 3 such siblings), missing from one port, is looked up in that port's body: a call
   or reference there is an **engine miss**, otherwise a real divergence. A lone edge no sibling (of at least 4)
   carries, whose callee is not in the body, is a possible false edge. Consensus catches what the body oracle cannot
   score as a call, such as a function passed as a pointer.

Output: `<work>/results/<sha>/callgraph.{json,md}` (per port and per shape, with up to 3 `path:line caller -> callee`
examples each). `--write-baseline FILE` writes the numbers-only view; `--baseline FILE --fail-on-regression` exits 1
when a port's recall or precision drops by more than `--tolerance` (0.001), a baseline port is missing, or the
consensus engine-miss or false-edge count grows. That is the hook for the DOOM-rosetta nightly (#5619, #5630): the `callgraph` job of `.github/workflows/doom-rosetta.yml` (schedule and manual dispatch only, never a PR check) runs `fetch` and `scan` on the baseline's ports, then the `--only all --baseline` command, and writes `callgraph.md` to the job summary; regenerate the baseline only with an explained engine change.

Attribution convention (owner ruling nyx-o8, 2026-10-21): a call inside a nested function is credited to the nested
function, never to the enclosing one, matching the engine (a C++ local class's method and a GNU C nested function are
each their own unit). The `else if` that `#ifdef` splitting makes tree-sitter read as a nested definition is not a
function and stays with the enclosing body. A lambda is not a named function: its calls stay with the enclosing one.

Blind spots:
- **Tree-sitter does not preprocess either.** An `else if` split by `#ifdef` parses as a nested function definition,
  and a macro table with no semicolon swallows the function after it. The first is read by a text fallback over the
  misparsed region, the second by brace matching from the engine's start line (`text_fallback_functions`); calls
  found that way are shape `unparsed`. A function neither finds is `unmatched_functions` and is not scored. Error
  recovery around a bare macro statement (`ADD_FILE_COUNTER` with no `;`) can also close a body early; when the body
  holds an `ERROR` node and the braces from the start line run past it, brace matching is used instead.
- **Tree-sitter 0.26 Python bindings:** read a node position as `node.start_point[0]`, never `.start_point.row`. The
  attribute read on the temporary `Point` corrupted the heap and segfaulted full runs (passes under
  `PYTHONMALLOC=debug`, so it looks like a flake).
- **Names, not symbols.** Edges are compared by unqualified name and restricted to names the port defines, so a call
  to a same-named function in another scope, or through a function-pointer variable, is outside it.
- **Code under `#if 0` counts** on both sides (neither tool preprocesses); libclang (#3784) is the planned check of
  the active configuration.

## Lineage vs linuxdoom (`lineage.py`, #5620)

How much of id Software's linuxdoom-1.10 survives in each port: the round-1 study's survival and landmark-function
scripts, ported onto the harness. It reads the scans and clones `scan` leaves; licensed ports only (`LICENSED`: the
call-graph oracle's C/C++ set plus the other licensed ports of the manifest; any other port is refused).

```bash
python tests/tools/doom_speedrun/doom_speedrun.py scan                      # once per engine SHA
python tests/tools/doom_speedrun/lineage.py [--only chocolate-doom,crispy-doom] [--sha SHA]
```

Each engine function's body is sliced from the clone (from its first `{`, so the signature line does not count),
C-style comments dropped, tokenised and hashed. A linuxdoom function (>= 20 body tokens, in `linuxdoom-1.10/`,
`sndserv/`, `ipx/`, `sersrc/`) survives in a port by **name** (same name once the class qualifier, case and `_` are
dropped), **exact** body (same hash anywhere in the port), **near** (best same-name body has difflib token
similarity >= 0.9) or **derived** (>= 0.6). Results in `<work>/results/<sha>/lineage/`:

| file | what |
|---|---|
| `survival.csv`, `lineage.md` | per port: the four survival percentages, LOC-weighted similarity, linuxdoom file stems kept, the stated lineage from `tests/doom_rosetta/manifest.csv`, its `parent` (the manifest port named by the lineage text's opening words, never itself) and `exact_vs_parent` (exact-body points gained or lost against that parent; linuxdoom counts as 100) |
| `survival_subsystem.csv` | the same per linuxdoom subsystem (file prefix: `r_` renderer, `p_` playsim, `m_` misc, ...) |
| `survival_functions.csv` | each linuxdoom function x port: class (exact / near / derived / name-only / gone), best similarity |
| `filename_survival.csv` | linuxdoom file stems present in the port's tracked sources |
| `divergence_{names,bodies,core}.csv` | pairwise: Jaccard of first-party function names and body hashes; mean similarity of the linuxdoom functions both ports keep (`__n`: how many) |
| `canonical_functions.csv` | complexity / LOC of twelve landmark functions (`P_UseSpecialLine`, `R_DrawColumn`, `G_Ticker`, ...) per port, largest first-party match, Heretic/Hexen/Strife trees skipped |

Blind spots:
- **Name matching is the lineage claim for rewrites.** A C# or Java port that renames into classes keeps
  `PTicker` / `p_ticker` and counts by name; a body never matches across languages, so exact / near / derived are
  meaningful for C-family ports only.
- **Comments are stripped only for C-style languages** (`C_STYLE`); elsewhere they stay in the tokens.
- **A body hash matches anywhere in the port** (a function moved or renamed still counts as exact); near / derived
  compare same-name bodies only (at most 20 candidates).
- **Vendoring is the engine's call** (`VendorDirectoryDetector`), used for divergence and the landmarks only:
  survival looks at every function the port has.
- **`parent` is read from free text**: a lineage naming no manifest port (`WinMBF <- MBF <- Boom`, `PrBoom`) has
  none, and the tool does not walk chains.

## Function-metric distributions (`distribution.py`, #5620)

How each port's per-function metrics are shaped next to linuxdoom's: the round-1 study's distribution script, ported
(stdlib only). It reads the scans alone (no clone); licensed ports only (`lineage.LICENSED`), `assets` projects and
ports under `--min-functions` (30) code functions skipped.

```bash
python tests/tools/doom_speedrun/distribution.py [--only gore,room4doom] [--sha SHA] [--min-functions N]
```

Per port, over the functions of code languages (`CODE_LANGUAGES`): median and 90th percentile of complexity, LOC,
call fan-out, token mass and argument count, plus the share of functions with complexity >= 10. `dist` is the mean,
over those five metrics, of the 1-D Wasserstein distance to linuxdoom (mean gap between 201 matching quantiles)
divided by linuxdoom's standard deviation for the metric. A second table places linuxdoom's median among the ports'
medians. Results in `<work>/results/<sha>/distribution/`: `distribution.csv`, `distribution.json`, `distribution.md`.
On the 0e2bf4ade scans it reproduces the study script's numbers for all 30 shared ports (to 1e-14).

Blind spots:
- **A distance is a shape comparison, not a correctness claim.** A port in another language moves every metric by how
  the engine counts that language (what the cross-language slice is for); a large `dist` says "different", not "wrong".
- **Vendored code is excluded** (#6097; the round-1 script did not): functions under a directory the engine's
  `VendorDirectoryDetector` calls vendored are dropped, so the numbers differ from round 1 for a port that bundles a
  library. This reads the clone (`<work>/repos/<port>`, as `lineage.py` does); a port with a scan but no clone is skipped.
- **The majority language names the port** (`lang`); a polyglot port's functions of other code languages stay in.

## Study write-up tables (`study_report.py`, #5620)

One command regenerates every table of `docs/research/doom-port-study.md` (clean-scan before/after, fidelity, lineage,
distributions, cross-language landmarks, and the `sfs` subway figures) from the scans `run --oracle` leaves under
`--work`; licensed ports only.

```bash
python tests/tools/doom_speedrun/study_report.py --work DIR --sha SHA --subway subway.csv --write   # --check: rc 1 when stale
```

- The before column defaults to `--before round2` (the round-2 `clean_check.csv`).
- A port whose scorer saw 0 first-party files is marked `(vacuous)`; one with no ctags reading shows `not compared`.
- `--subway` is the `subway.csv` of `sfs compare ... --subway-reference linuxdoom`; without it the block says so.

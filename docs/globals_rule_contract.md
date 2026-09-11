# The `globals` rule contract (#2858)

> **One hit is a declaration of a binding with program lifetime — file,
> module, class-static or process scope — or a read or write of the process's
> ambient environment through its named handle, in a form an ordinary
> identifier cannot match.**

Stated 2026-09-07 by the #2858 audit (roadmap Phase 3, epic #2812).
Precedents: `docs/api_rule_contract.md` (#2730), `docs/args_rule_contract.md`
(#2773), `docs/state_mutation_rule_contract.md` (#2765),
`docs/branch_rule_contract.md` (#2822), `docs/io_rule_contract.md` (#2841),
`docs/test_rule_contract.md` (#2852), `docs/func_start_rule_contract.md` and
`docs/class_start_rule_contract.md` (#2856). The machine-readable row is
`gitgalaxy/standards/signal_contracts.py`; the cross-language pins are
`tests/extraction/languages/test_globals_contract_2858.py`.

`globals` is a **declaration**-kind signal. Its consumers: the
`encapsulation_ratio` (`signal_processor.py`: `1 - globals / (core_var_decl +
globals)` — "how much of the file's data is locked inside functions"), the
secrets-risk careless amplifier (`1 + debug_prints + dead_code + globals`,
tripled when an LLM API is called with no global at all), the
`statistical_auditor` extraction-density group, the "Global State
Dependencies" display row, and two per-language fidelity coefficients
(`fidelity_table.py`: cobol, csharp). Before this contract it carried 2 of the
corpus's 27 open-defect cells (csharp, shell — 5% of its 44 comparable cells);
after it, every corpus language reads **2**.

The sentence has two halves on purpose. The declaration half is what the
encapsulation ratio divides into `core_var_decl`; the ambient-handle half
(`os.environ`, `$PATH`) is a *site*, not a declaration, and inflates that
ratio's numerator. Whether the ratio should read the declaration half alone is
a commensurability question for Phase 4 (#2766, the encapsulation formula),
not this rule's — the rule counts both because both are couplings to state
the unit does not own, which is what every consumer is asking about.

## Corollaries

**C1 · Scope, not mutability — and a local never counts.** A program-scope
binding counts whatever its constness: java's `public static final X =`,
kotlin's `const val`, dart's `static const`, zig's `const`, rust's `static` and
`const` items, c's `static const byte ops[] =`. Constness is
`immutability_locks`' axis (#2772); a `static final Logger` is a global
object however `final` its binding. The other side of the same corollary is
the one the crucible measured hardest: a **function-local binding is never a
global, whatever keyword precedes it**. c's rule matched `T x = v` at any
indentation, so `PyThreadState *tstate = _PyThreadState_GET();` — every local
with an initializer — counted (2,771 crucible hits on 32 files, 247 after: the
file-scope declaration anchors to column 0, the #2651 dart/zig shape, and an
indented `static` counts only because C makes it a program-lifetime local).
lua's `arg` matched `local arg = {...}`, rust's `static mut` matched the
lifetime `&'static mut A` (both of its crucible hits), kotlin's bare `object`
matched an anonymous object expression, go could not see `var mu sync.Mutex`
(no initializer) or a package-level `const` at all.

**C2 · A declaration or the ambient handle — not a reference.** An ordinary
read of a global by name is invisible to a regex and stays invisible; what
counts is the declaration, or a read/write of the process's ambient state
through the handle the language names it by: `os.environ`, `process.env`,
`$PATH`, `System.getenv`, `%ENV` / `$ENV{…}`, `sy-subrc`, `msg.sender`,
`sqlite_master`, `$(MAKE)`, `the platform`, perl's punctuation variables
(`$_`, `$@`, `$!`, `$$`). A reference to a named *constant* is a reference:
agc_assembly's `CAF BIT14` loads a bit-mask from the fixed constant table (125
of its 150 crucible hits); a flagword (`FLAGWRD7`) is the shared erasable
every program section reads and writes, and stays. haskell gains the
`System.Environment` reads (`getEnv`, `lookupEnv`, `getArgs`) beside its
`unsafePerformIO`-IORef idiom; rust gains `env::var`/`env::args`; python gains
the `global x` statement (its own declaration form, which only the embedded
twin counted) and `sys.modules`.

**C3 · The ambiguity anchor** (io C1, test C3). An everyday word fires only in
its global form:

- **shell** — the rule was a bare word list, `\b(PATH|HOME|…|TERM|…)\b`, so the
  planted safety handler `trap : TERM` counted the signal name (the open
  cell), and on the crucible so did `trap "" INT TERM QUIT`, `# HOME
  verification` and `"etcd must be in your PATH"`. An environment variable is
  global state in its variable form — `$NAME`, `${NAME`, or a top-level
  `NAME=` / `export NAME=` — and nowhere else. Crucible 174 → 141.
- **swift** — bare `shared`/`standard`/`default`: `default` is a `switch`
  case as often as a singleton. The accessor counts behind its dot
  (`UserDefaults.standard`, `FileManager = .default`, `.shared`); the corpus
  plant `let region = shared` / `let store = standard` was two bare
  identifiers authored to the old rule and is re-planted as the ambient
  handles `ProcessInfo.processInfo` / `UIApplication.shared`.
- **cobol** — `-` is a regex word boundary, so `COMMON` matched inside
  `COMMON-RETURN`, `CA-POLICY-COMMON`, `COMMON-8-BIN` (the #2622 hyphen shape;
  185 → 16, every removed hit an identifier). `(?<![-\w])…(?![-\w])`.
- **livecode** — `it` is the handler-local result variable (`return it`,
  `if it is empty`), not global state; `the platform` / `the environment`
  are the ambient reads. 385 → 74.
- **perl** — `$$options{$param}` and `$$self{OPTIONS}` are scalar derefs, not
  the pid variable; `$_[2]` is the argument array, not the topic. 2,694 → 911,
  the remainder the punctuation globals themselves. `$ENV{PATH}` joins.
- **typescript / javascript** — every `global.` crucible hit was
  assemblyscript's `let global = <Global>element`; `self.` is `const self =
  this` as often as a worker's global. The unambiguous handle is
  `globalThis.`; `window.`, `document.`, `navigator.`, `process.env` and
  `import.meta.env` stay (VS Code's `document.uri` parameter is the accepted
  residue, 2 of 27). 113 → 27.
- **lua** — `arg` is the script's argument table unless it is being declared
  as a local, assigned, or read as a field.
- **kotlin** — the *named* `object X` declaration is the singleton;
  `object : Runnable {` is an expression.

**C4 · Linkage and region headers are not state.** A storage-class keyword on
a *procedure* declares linkage: cpp's bare `static`/`extern` counted
`static void _bind_methods();` and `extern "C" {`, objective-c's `extern`
counted `extern char *WWW_nameOfFile(…)`, fortran's `EXTERNAL` declares a
procedure *name* (9 of its 16 crucible hits: `LOGICAL, EXTERNAL ::
wrf_dm_on_monitor`) and the corpus plant `EXTERNAL HELPER` was authored to
it. The c-family rules now stop at a `(` before the statement ends (a
lookahead that halts at `=`, so `static T x = f();` still counts), and
fortran's plant is re-planted as `DATA HOME /2/` — a DATA-initialised variable
is implicitly SAVEd, program lifetime. A **region header** opens the area
globals live in and is not one either: #2805 dropped cobol's
`WORKING-STORAGE SECTION`; assembly's rule counted the section switch
(`.data`, `section .bss`) instead of the labeled storage the section holds,
so a file with three sections and forty variables read 3. The rule now counts
`label: .directive` / `label directive` storage (`buf: resd 4`, `msg: .asciz`,
`.comm sym,4`; 70 → 226 on the same files) and the plant moves from
`section .data` to `region dd 1`.

**C5 · One owner.** Process control through the ambient class is
`high_risk_execution`'s: csharp's `\bEnvironment\.` prefix counted the planted
`Environment.Exit(payload)` (the other open cell); the prefix now excludes
`Exit` and `FailFast`, high_risk keeps them (mass conserved). `locals()` is a
reflective handle on the *local* namespace — nobody's global — and leaves
python and embedded_python. Three duals are genuine two-construct tokens (the
fortran-COMMON shape, #2856's reading) and are kept, not retired:

| token | rules | why both are right |
|---|---|---|
| kotlin `object Region {}` | globals + class_start | a singleton *is* a class declaration and is how Kotlin spells a global |
| fortran `COMMON /X/ A` | globals + safety_bypasses | shared storage aliased with no type checking |
| jcl `// SET X=1` | globals + state_mutation | the symbol assignment is jcl's only declaration of a job-wide value |

The fallback dual for a language with no declaration syntax stands with it:
lua's SCREAMING_CASE assignment (`X = true`) is the first assignment without
`local` — the declaration — and the same line is state_mutation's write.

**C6 · Stated absence.** html and markdown record `None` (ledger
`html-2578-declarative-globals-state-mutation-morphology`,
`markdown-lit-plane-morphology`): purely declarative surfaces with no
scoped-vs-global morphology. css keeps its rule (`:root`, `html`, `body`, `*`
are the global style scope).

## Deliberate duals and deferred residue

- **zig 1,892 crucible hits** — every top-level Zig declaration is a `const`
  binding (`const std = @import("std");`, `const Foo = struct {`), so the
  column-0 `const|var` rule reads the language's morphology, not a defect;
  rule untouched.
- **perl `$_`** — the topic variable is package-global by definition and stays
  counted (`local $_;` is a dynamic-scope write to it); it dominates perl's
  911.
- **swift's branch rule** counted the bare `default` in `FileManager.default`
  (the singleton accessor, not a `switch` case) — branch contract C3 (#2822),
  **resolved in #2859**: swift's branch `default` now carries a `(?<!\.)` guard,
  so the dotted accessor (io/events' hit) no longer counts as a decision
  (crucible 781 → 759).
- **lua's SCREAMING_CASE assignment arm (`^X =`)** — the fallback declaration
  for a language whose first assignment without `local` *is* the declaration;
  the same line is `state_mutation`'s write (the jcl-`SET` dual shape). Kept as
  a deliberate dual, recorded here, not the ledger — no cell moves (#2859).
- **The narrower-than-contract forms #2858 deferred are now widened (#2859):**
  go `var (` / `const (` group members (via the `go_declaration_group` scope
  filter — over-match then keep only members directly inside a column-0 group);
  java/csharp class statics beyond `public … SCREAMING_CASE` (any static field,
  the `[=;]` terminator excluding methods and initializer blocks); dart
  `static var` and column-0 `late final`; assembly's label-on-its-own-line
  two-line form; tcl's `$global` read dropped and the `global NAME…` statement
  kept; agc_assembly's `NAME ERASE` erasable allocation in with the dead prose
  vocabulary and the routine-label `COMMON` out (the `EQUALS`/`=` equate stays
  out — a constant binding under C2, and a rosetta decoy). Each was gated on a
  `rule_probe` crucible measurement; the moved cells are re-blessed and
  re-planted with #2859.

## The 46-language audit

`rule_probe.py globals all --samples 10` before → after. crucible = hits across
the real-world corpus; rosetta = hits across the 4 keyword-rosetta shell files
(median plant: 2). Languages not listed: rule `None` by stated absence (html,
markdown) or no globals morphology declared (batch, blp, csv, glsl, hlo, json,
mlir, nix, pbtxt, plaintext, proto, td, xml).

| language | crucible | rosetta | verdict |
|---|---|---|---|
| abap | 48 | 2 | conforms (`TABLES`/`STATICS`/`CLASS-DATA` declarations, `SY-*` ambient reads) |
| ada | — | 2 | conforms (`Global =>` aspect, `pragma Volatile`) |
| agc_assembly | 150 → 23 | 2 | **C2**: `BIT\d+` constant references out; flagwords stay. #2859: dead `ERASABLE MEMORY`/`FIXED MEMORY`/`WORKING-STORAGE` prose and the routine-label `COMMON` out; `NAME ERASE` (erasable allocation) in. The `EQUALS`/`=` equate is a constant binding (C2) and a rosetta decoy — not counted |
| apex | 0 | 2 | conforms (`UserInfo`, `System.Label`, `Cache.Org` handles) |
| assembly | 70 → 478 | 2 | **C4**: section switch out, labeled storage in; plant re-planted (`region dd 1`). #2859: the label-on-its-own-line two-line form (`msg:` ⏎ `.asciz`) in |
| c | 2771 → 247 | 2 | **C1/C4**: column-0 file scope + indented `static`; locals and prototypes out |
| cobol | 185 → 16 | 2 | **C3**: hyphen guards; `COMMON-RETURN` was an identifier |
| cpp | 485 → 218 | 2 | **C4**: `static`/`extern` on a prototype and `extern "C"` out; one hit per `static thread_local` |
| csharp | 0 → 5 | 3 → 2 | **C5**: `Environment.Exit`/`FailFast` are high_risk's (main.cs 1 → 0). **C1** (#2859): any class-static field, not just `public … SCREAMING_CASE =` |
| css | 32 | 2 | conforms (`:root`/`html`/`body`/`*` global scope) |
| dart | 25 | 2 | conforms (top-level `final`/`const`/`var` at column 0, `static const`, `Platform.environment`). **C1** (#2859): `static var` and column-0 `late final` added (no crucible instance) |
| dockerfile | 10 | 2 | conforms (`ENV NAME` — globals only since #2765) |
| embedded_python | 7 | 2 | **C5**: `locals()` out; `global` anchored to the statement; `sys.argv` in |
| fortran | 16 → 7 | 2 | **C4**: `EXTERNAL` out, `DATA` in; plant re-planted (`DATA HOME /2/`) |
| go | 36 → 237 | 2 | **C1**: package-level `var` without initializer and `const` in. #2859: `var (`/`const (` group members in, via the `go_declaration_group` scope filter (over-match then keep only members directly inside a column-0 group; struct-literal fields and body statements drop) |
| groovy | 17 | 2 | conforms (`System.getenv`/`getProperty`, `project.ext`) |
| haskell | 0 | 2 | **C2**: `System.Environment` reads join the IORef idiom |
| java | 8 → 22 | 2 | `ThreadLocal`, `System.getenv`. **C1** (#2859): any class-static field (`private static final Logger LOG`, `static int counter;`), not just `public … SCREAMING_CASE =`; the `[=;]` terminator keeps methods and `static {}` blocks out |
| javascript | 18 → 12 | 2 | **C3**: `global.`/`self.` out; `import.meta.env` in |
| jcl | 73 | 2 | conforms (`//JOBLIB DD`, `SET`, `EXPORT SYMLIST`; SET dual ledgered) |
| kotlin | 3 | 2 | **C3**: named `object` only; `const val`/top-level `val` unchanged |
| livecode | 385 → 74 | 2 | **C1**: handler-local `it` out |
| lua | 407 → 392 | 2 | **C1/C3**: `local arg` and `t.arg` out; `_G`/`_ENV`/SCREAMING_CASE fallback unchanged |
| m4 | 10 | 2 | conforms (`AC_ARG_VAR` precious-variable declaration) |
| makefile | — | 2 | conforms (`$(MAKE)`/`$(SHELL)`/… ambient variables) |
| matlab | 3 | 2 | conforms (`global`/`persistent` declarations, `getenv`/`setenv`) |
| objective-c | 16 → 30 | 2 | **C4**: `extern` on a prototype out; `static` data declarations in (`static NSString *const kKey`) |
| perl | 2694 → 911 | 2 | **C3**: `$$ref` derefs and `$_[n]` out; `$ENV{…}` in |
| php | 157 | 2 | conforms (`global $x`, `$_SERVER`/`$_ENV`/`$GLOBALS`) |
| powershell | 790 | 2 | conforms (`$global:`/`$script:`/`$env:` scoped forms, preference variables) |
| python | 13 → 46 | 2 | **C2/C5**: `global x` statement and `sys.modules` in; `locals()` out |
| ruby | 1 | 2 | conforms (`$name` globals, `ENV`/`ARGV`/`STD*` constants) |
| rust | 2 → 30 | 2 | **C1**: `'static` lifetime out; `static`/`const` items and `env::` reads in; `const _` excluded |
| scala | 8 | 2 | conforms (`object X` singleton, `sys.env`/`sys.props`) |
| scheme | 65 | 2 | conforms (module-scope `define` via the `lisp_body_position` scope filter, #2674) |
| shell | 174 → 141 | 3 → 2 | **C3**: variable form only (`$NAME`, `${NAME`, `NAME=`); `trap : TERM` was a signal name (a.sh 3 → 2) |
| solidity | 6 | 2 | conforms (`msg.*`/`block.*`/`tx.*` ambient state) |
| sqlite | 6 | 2 | conforms (`sqlite_master`/`sqlite_schema`/`sqlite_stat*` registries) |
| swift | 33 → 29 | 2 | **C3**: dotted accessor only; bare `default`/`shared`/`standard` out; plant re-planted |
| tcl | 193 | 2 | conforms (`global` statement, `::env`, `upvar #0`). **C3** (#2859): the `(?<!\$)` guard drops `$global` (an ordinary variable read), keeps the `global NAME…` statement |
| typescript | 113 → 27 | 2 | **C3**: `global.` (assemblyscript's local) and `self.` out |
| yacc | 0 | 2 | conforms (`yylval`/`yylloc`/`yynerrs`/`yydebug` parser globals) |
| yaml | 0 | 2 | conforms (`${{ env.* }}`/`${{ github.* }}`, `$VAR`) |
| zig | 1892 | 2 | conforms by morphology (every top-level declaration is a `const` binding) |

## Ledger dispositions this contract settles

- `csharp-environment-exit-is-global-and-danger` — **resolved** (C5);
  main.cs re-blessed 1 → 0.
- `shell-trap-signal-env-collision` — **resolved** (C3); a.sh re-blessed
  3 → 2.
- `batch4-dual-keyword-overlaps` — globals half confirmed: the jcl SET dual is
  the one globals overlap that stays; livecode's `global` dual was already
  gone (#2675) and dockerfile ENV is globals-only since #2765.
- `kotlin-object-dual-globals-classstart`,
  `fortran-common-globals-safety-dual-classification` — unchanged, now cited
  as the C5 deliberate duals.
- `os-sys-prefix-overlaps-io`, `cobol-working-storage-globals`,
  `indented-declaration-globals` — already resolved (#2626, #2805, #2651),
  cited as precedents.
- `html-2578-declarative-globals-state-mutation-morphology`,
  `markdown-lit-plane-morphology` — unchanged (C6).
- New: `globals-contract-2858` (the verifying scan, every moved cell).

## Bless scope

Golden-master movement: 769 diffs per fixture, 491 topological (the
corpus-wide X/Y/Z re-solve) and 278 substantive — 232 per-file `Global State
Dependencies` cells across 21 languages, the ecosystem aggregates that read
them, and **one newly excluded artifact**: cobol `cics-genapp/lgpolicy.cpy`
(85 LOC), a copybook whose only recorded signals were the phantom `COMMON`
hits inside its `CA-POLICY-COMMON`-style item names; with those gone it reads
0 signals and the aperture's zero-density guard excludes it (the #2765
`RESPSTR.cpy` finding in the other direction — a rule change can cross the
aperture). Every cics-genapp directory-group aggregate shift traces to that
one file leaving. Newly parsed: none.

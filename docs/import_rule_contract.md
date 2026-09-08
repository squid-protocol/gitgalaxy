# The `import` rule contract (#2875)

> **One hit is a statement or directive that binds an external unit — a
> module, package, header, library, file, stage or base image — into the
> current unit, in the language's own dependency form.**

Stated 2026-09-08 by the #2875 audit (roadmap Phase 3, epic #2812).
Precedents: `docs/api_rule_contract.md` (#2730), `docs/args_rule_contract.md`
(#2773), `docs/state_mutation_rule_contract.md` (#2765),
`docs/branch_rule_contract.md` (#2822), `docs/io_rule_contract.md` (#2841),
`docs/test_rule_contract.md` (#2852), `docs/func_start_rule_contract.md` and
`docs/class_start_rule_contract.md` (#2856), `docs/globals_rule_contract.md`
(#2858), `docs/safety_rule_contract.md` (#2869). The machine-readable row is
`gitgalaxy/standards/signal_contracts.py`; the cross-language pins are
`tests/extraction/languages/test_import_contract_2875.py`.

`import` is a **declaration**-kind signal. Its consumers: the
`statistical_auditor` extraction-density group (`SIGNAL_KEYS`), the
"Dependency Resolution" display row, and two per-language fidelity
coefficients (`fidelity_table.py`: dockerfile `0.75`, embedded_python
`0.4286` — exactly 3/4 and 3/7, the table pricing the two cells this audit
settles). The dependency graph itself — popularity, pagerank, blast radius,
`dependency_density`, orphan→api conversion — is built by the sibling
`_dependency_capture`, not by this count (`test_dependency_density_floor.py`
pins that split: the count keeps every capture, the density reads resolved
edges). That independence is what makes the count's unit a choice this
contract has to make rather than inherit. Before this contract it carried 2
of the corpus's 17 open-defect cells (dockerfile 4, embedded_python 7, both
against a median of 3); after it, dockerfile reads **3** and
embedded_python's 7 is ledgered as the classifier's own floor (C4 below).

## Corollaries

**C1 · The dependency form — re-exports and loader calls included.** The
statement that brings a unit into the current one counts whatever it is
spelled: `import`, `#include`, `use`, `using`, `require`, `with`, `COPY`,
`INCLUDE`, `FROM`, `uses:`, `@import`, `<link rel="stylesheet">`. A
re-export counts (`export { b } from './b.js'`, `pub use`, dart `export`,
`part`/`part of`): it binds the unit in order to re-publish it. Where the
language's load form is a call, the call is the statement: `require(`,
`import(`, `__import__(`, `importlib.import_module(`, `Type.forName(`,
`dofile(`, `load_extension(`, `@import(`. csharp's alias directive
`using Alias = Target.Namespace;` binds a unit and was already captured for
the graph; it joins the count (crucible 95 → 96). go's single-line aliased
form `import _ "embed"` / `import f "fmt"` joins for the same reason.

**C2 · The unit is the statement, not the edge.** `import (…)`,
`use a::{b, c};`, `import a, b`, `with a, b;`, `import java.lang.{Long =>
JLong}` are **one hit each**; the graph's edges are `_dependency_capture`'s
and are counted there. The reverse failure is the one the crucible measured:
scala's class `[\w.{}\s,]+` included `\s`, so a block of eight `import` lines
and the `def` after them was one match — **16 → 275** crucible hits once the
rule reads one statement per line (the corpus's 3 never moved, because each
shell file has one import followed by a blank line). A regex for this signal
must not be able to span statements.

**C3 · A binding, not a reference or a self-declaration.** A qualified name
(`acct.Id`, `Account.Name`, `LoggingLevel.INFO`), a call through an imported
symbol, a type annotation, the file's own `module`/`package`/`library`
header and host association are invisible. apex has no import statement at
all — every class in the org is visible — and its second alternation counted
any `receiver.Member` reference (#2671 had scoped the `[A-Z]` guard that
re.IGNORECASE neutralised; the contract retires the arm: **22 → 0**, the
`Type.forName(` chain the corpus plants is the language's one load form).
livecode's `module com.livecode.array` declares the file's *own* module and
`end module` closes it (35 of 83 hits); the LCB import form `use
com.livecode.foreign` was not counted at all (83 → 33, the 27 real imports
plus `start using`). fortran's `IMPORT` is host association inside an
interface body — nothing external is bound. abap's `INCLUDE TYPE` /
`INCLUDE STRUCTURE` binds a type's components into a structure, not a unit.

**C4 · A named unit.** A form that names nothing binds nothing: dockerfile
`FROM scratch` (the reserved empty base — no image is pulled, no layer
bound, and `_dependency_capture` recorded an edge to a unit that cannot
exist; `class_start` still opens the stage, #2856's dual); agc_assembly's
bare `BANK` and numeric `BANK 31` are location-counter directives (the
capture's own reading is a symbolic operand in opcode position: 104 → 50).
The other side of C4 is **embedded_python**: the language's detection regex
is `^[ \t]*(?:import|from)\s+(?:machine|board|…)\b`, so a file *is*
embedded_python only by carrying an import of a hardware module. Every one of
its seven corpus lines is a genuine hit under this sentence, its floor is 4 by
construction, and a rule that did not count `import machine` would be wrong on
the wild corpus — the cell is the classifier's inherency, ledgered as such
(`embedded-python-classifier-import-floor`), not an extraction defect.

**C5 · Statement or command position** (io C1, test C3, globals C3). An
everyday word fires only in its loading form: `include` inside an abap
template string, `use ysu (option1)` inside a fortran string literal, m4's
`include/Makefile \` (a path whose first component is a directory), shell's
lone `.` after a plain space (`find -s . -mindepth`, `--init-path . name`,
`rsync … .`: 103 → 41), makefile's tab-initial `include` (a recipe command, never a directive — #844 fixed func_start and the capture and deliberately left this rule), a doctest `>>> import numpy` line. python and
embedded_python anchor to `(?:^|;)` with the loader calls unanchored —
twin parity with the already-anchored twin; on the code stream this moves
one crucible hit (1541 → 1540), because Prism strips docstrings before rules
run, so the 279 doctest lines in numpy's docstrings were never counted. shell's
anchor closed the two "known limitation" pins in `test_shell.py` (a
commented-out `# source .env` and a spaced string lookalike no longer
capture) — by the boundary set, not by string-awareness (#2535 still holds:
strings count uniformly).

**C6 · One owner, with the stated duals kept.** dockerfile `FROM` is
class_start's *and* import's (the fortran-COMMON shape, #2856); html's `<link
rel="stylesheet" href>` is io's attribute reading and import's element
reading (manifest-recorded since the corpus was locked); sqlite `.read` /
`.import` are import's alone since io C2 (#2841). agc_assembly's `EBANK=` is
args' token (`[EFB]BANK=`) and an addressing directive — out of both the
count and the capture. markdown records the stated absence (None).

## Deliberate duals and deferred residue

- **dockerfile `FROM`** (class_start) and **html `<link href>`** (io) — kept,
  pinned in the contract module.
- **sqlite `.import`** — `.import FILE TABLE` ingests CSV rows, which reads
  as data (io) rather than a unit of code; #2841 C2 assigned it to import a
  day before this audit and the corpus plants `.read`, so nothing moves
  today. Recorded here as the one owner question this contract inherits
  rather than reverses; io's call.
- **html inline `<script type="module">` / `<script type="importmap">`** —
  an inline module script binds nothing by itself (its inner `import`
  statements are javascript's hits via Prism's partition) and an import map is
  a resolution table; `<script src>` binds a unit but is io's `src=` hit.
  No cell evidence; left in place.
- **zig `callconv(@import("std").os.windows.WINAPI)`** — 54 of zig's 440
  hits are the `@import("std")` expression used inline as a namespace; Zig has
  no declaration form, `@import` is the load form wherever it appears, and
  each is one call (C1). Morphology, rule untouched.
- **perl pragmas** (`use strict`, `use warnings`, `no strict 'refs'`) load
  `strict.pm` and are `use` statements by the language's own definition;
  kept.
- **javascript/typescript `[^;]*?\bfrom\b`** — the lazy scan across a
  `from`-less payload is quadratic (the contract module's detonation found
  it); bounded to `{0,2000}` characters with no semantic change on the
  crucible.
- **shell `wrapper … source file`** — a wrapper function that evals its
  arguments (kubernetes' `log-wrap 'Name' source file`) hides the source from
  command position; two crucible edges lost, recorded in the bless scope.
- **go `import (…)` groups** count 1 (C2) — the same shape as rust's
  `use a::{b, c}`; the graph counts the specs.

## The 46-language audit

`rule_probe.py import all --samples 8` before → after. crucible = hits across
the real-world corpus (Prism code stream, comments stripped); rosetta = hits
across the 4 keyword-rosetta shell files (median plant: 3, the
main→a→b→c chain). Languages not listed: rule `None` by stated absence
(markdown) or no import morphology declared (batch, blp, csv, glsl, hlo,
json, mlir, nix, pbtxt, plaintext, proto, td, xml).

| language | crucible | rosetta | verdict |
|---|---|---|---|
| abap | 7 → 6 | 3 | **C5/C3**: statement position; `INCLUDE TYPE|STRUCTURE` out |
| ada | — | 3 | conforms (`with a, b;` one hit; pragma names excluded) |
| agc_assembly | 104 → 50 | 3 | **C4/C6**: symbolic BANK/SETLOC operand only; `EBANK=` is args' |
| apex | 22 → 0 | 3 | **C3**: reference arm retired; `Type.forName(` only |
| assembly | 81 | 3 | conforms (`%include`/`.include`/`INCLUDE` forms) |
| c | 306 | 3 | conforms (`#include`/`#embed`) |
| cobol | 494 | 3 | conforms (`COPY`, `INCLUDE`; `COPY … REPLACING` one hit) |
| cpp | 743 | 3 | conforms (`#include`, `import x;`, `export import`) |
| csharp | 95 → 96 | 3 | **C1**: alias directive joins; `using (…)`/`using var` stay out |
| css | 9 | 3 | conforms (`@import`; the url() io dual is #2752's) |
| dart | 195 | 3 | conforms (`import`/`export`/`part`/`part of`) |
| dockerfile | 113 → 103 | 4 → 3 | **C4**: `FROM scratch` out (c.dockerfile 1 → 0); `COPY --from=` stays |
| embedded_python | 65 | 7 | **C4/C5**: classifier floor (ledgered inherency); loader calls join |
| fortran | 309 → 269 | 3 | **C5/C3**: statement position; `IMPORT` out; `#include` in |
| go | 14 | 3 | **C1**: aliased single-line form `import _ "embed"` joins (no crucible instance; groups count 1) |
| groovy | 693 | 3 | conforms |
| haskell | 138 | 3 | conforms (`import qualified … as`) |
| html | 36 | 3 | conforms; inline module/importmap left (residue) |
| java | 336 | 3 | conforms (`import static`) |
| javascript | 450 | 3 | conforms; scan bounded (ReDoS) |
| jcl | 93 | 3 | conforms (`// INCLUDE MEMBER=`) |
| kotlin | 25 | 3 | conforms |
| livecode | 83 → 33 | 3 | **C3**: own `module` header and `end module` out; `use` in |
| lua | 156 | 3 | conforms (`require`/`dofile` call forms) |
| m4 | 2 → 0 | 3 | **C5**: `include(` form; `include/Makefile` was a path |
| makefile | — | 3 | **C5**: a tab-initial `include` is a recipe command (the #844 fix, applied to this rule at last) |
| matlab | 0 | 3 | conforms (`import pkg.*`) |
| objective-c | 41 | 3 | conforms (`#import`/`#include`/`@import`) |
| perl | 426 | 3 | conforms (`use`/`require`/`no`; pragmas kept) |
| php | 760 | 3 | conforms (`use`, `require`/`include` family) |
| powershell | 22 | 3 | conforms (`Import-Module`, `using module`, dot-source) |
| python | 1541 → 1540 | 3 | **C5**: statement position + loader calls (twin parity) |
| ruby | 21 | 3 | conforms (`require`/`require_relative`/`load`/`autoload`) |
| rust | 401 | 3 | conforms (`use`/`pub use`; `use a::{b, c}` one hit) |
| scala | 16 → 275 | 3 | **C2**: one statement per line (the class swallowed newlines) |
| scheme | 17 | 3 | conforms (`(import`/`(use-modules`/`(require`) |
| shell | 103 → 41 | 3 | **C5**: command position; `.` as a path argument out |
| solidity | 26 | 3 | conforms |
| sqlite | 14 | 3 | conforms (`.read`/`.load`/`.import`, `ATTACH DATABASE`, `load_extension`) |
| swift | 6 | 3 | conforms (`@_exported import`) |
| tcl | 70 | 3 | conforms (`package require`, `source`, `load`) |
| typescript | 511 | 3 | conforms; scan bounded (ReDoS) |
| yacc | 11 | 3 | conforms (`#include` in the prologue) |
| yaml | 0 | 3 | conforms (`uses:`/`image:`) |
| zig | 440 | 3 | conforms by morphology (`@import(` is the load form wherever it appears) |

## Ledger dispositions this contract settles

- `batch4-dual-keyword-overlaps` — **import half retired**: the two cells it
  excused by cross-product were never keyword overlaps (dockerfile's was
  `FROM scratch`, embedded_python's is the classifier floor); `import` leaves
  the signal union and dockerfile leaves `languages_seen` (its ENV,
  HEALTHCHECK and FROM halves are all stated elsewhere).
- New: `import-contract-2875` (upstream-bug, resolved; dockerfile c
  re-blessed 1 → 0, the verifying scan).
- New: `embedded-python-classifier-import-floor` (intended-morphology,
  still reproduces by design; C4).
- `apex-import-ignorecase-type-guard` — already resolved by #2671; cited as
  the precedent C3 completes.
- `sqlite-dot-read-dual-import-io`, `css-import-url-io-triple-overlap` —
  unchanged, cited as the C6 owner decisions this contract inherits.
- `embedded-python-per-file-classification` — retired 2026-09-06; its
  verdict is the evidence for C4's floor.
- `markdown-lit-plane-morphology` — unchanged (stated absence).

## Bless scope

Golden-master movement (both fixtures): 294 diffs, **0 topological**, 294
substantive, all in the import family or the graph it feeds — 98 per-file
`Module Dependencies (Imports)` cells and 86 `Extracted Dependencies` lists
(livecode 107 entries, shell 106, agc_assembly 30, fortran 12, scala 7, moby
6, apex 4, abap/csharp/python 1 each), the dependency-network keys that
re-solve from those captures (`Direct/Total Upstream`, `Direct/Total
Downstream`, `Popularity Rank` — which is why two cpp, two rust, one perl,
one lua and one typescript file move an upstream count without any rule of
theirs changing: shell's old capture turned comment prose such as `# $1
source path of kube-proxy manifest.` into edges named `path`, and those
resolved by stem across the scan), two `Tech Debt Exposure` cells plus the
ecosystem `tech_debt`/`avg_tech_debt` (the orphan→api conversion reads
popularity) and one `Unreferenced By Name`. Newly parsed: none. Newly
excluded: none. The one non-signal line is the `Unparsable Artifacts` queue's
`PROVENANCE.json` entry (`imports_unknown`), a graph-total echo.

One narrowing is recorded rather than worked around: kubernetes'
`log-wrap 'SourceConfigureKubeApiserver' source ${KUBE_BIN}/configure-kubeapiserver.sh`
sources a file through a wrapper function that evals its arguments; under C5
`source` is an argument there, not a command, and the two edges are lost
(`configure-helper.sh` Direct Upstream 11 → 3 — the other eight were the
comment-prose phantoms). A wrapper-aware form would need the wrapper's
semantics; shell's residue, with #2875's issue thread as its home.

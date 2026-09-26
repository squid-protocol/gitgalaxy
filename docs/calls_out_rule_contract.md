# The `calls_out` rule contract (#3327)

> **One entry is one distinct callable unit, by name, that the function's own body invokes -- a
> call, a constructor or conversion, a macro, or a verb-form invocation (`CALL`, `PERFORM`,
> `EXEC PGM=`, a command word) -- other than the function itself.**

Declared 2026-09-23 by #3327, step 0 of the function call graph (#3265). Precedents:
`docs/import_rule_contract.md` (#2875), `docs/unreferenced_by_name_contract.md` (#2806). The
machine-readable row is `gitgalaxy/standards/signal_contracts.py`, and the pins are
`tests/extraction/languages/test_calls_out_contract_3327.py`.

**Status: `declared`, not `stated`.** The sentence, the corollaries and the four product
decisions below are fixed. The rules that disagree are **filed, not fixed** (#3359-#3362), which
is how `signal_contracts.py` defines `declared`. The row becomes `stated` when those land.

`calls_out` is not a count. It fills each function's `calls_out_to`, the ordered list of distinct
callee names, which `function_data.calls_out_to` persists as JSON. Today its readers are the
test-to-production mapping in `network_risk_sensor.py` and the wrapper census in
`wrapper_extractor.py` (#3313). #3265 adds the resolver (#3328), which links each name to a
definition, the qualifier (#3329), and function PageRank (#3330). No formula reads the list's
length, so its `site` kind has no commensurability consequence yet.

## The four decisions (#3327, decided by Joe 2026-09-23)

| question | decision | consequence |
|---|---|---|
| Built-ins / stdlib (`print`, `len`, `console.log`) | **They are calls.** The resolver (#3328) labels them `external` because nothing in the repo defines them. Extraction does not filter them. | Fixed by #3361 (after #3328): `_CALLS_OUT_GLOBAL_IGNORE` and the per-language `_calls_out_ignore` sets hold keywords, pragmas and syntax only. |
| Recursion | **Dropped.** `calls_out_to` never lists the function's own name. | Matches today. A self-edge adds nothing to fan-in, and in PageRank it only inflates the node's own score. |
| Multiplicity | **Deduplicated.** Call-site counts are not recorded, and function-graph edges are unweighted. | Matches today. A call inside a loop is not more dependency than one outside it. |
| References vs invocations (`map(f, xs)`, bare `@decorator`, `getattr`) | **Invocations only.** | See C1. |

## Corollaries

**C1 · Invocation, not reference.** A name passed as a value is not a call: `map(visit, xs)`
lists `map`, not `visit`. The same goes for a name that is assigned, returned, or named in a type
or signature. This is `unreferenced_by_name`'s corollary 3 seen from the calling side.
- A decorator applied without arguments (`@cache`) is a reference.
- A decorator factory that is itself invoked (`@retry(3)` in Python/TypeScript) is a call to `retry`.
- Metadata annotations (`@SuppressWarnings("x")`, `@available(...)`, `@Throws(...)`, C#
  `[Obsolete(...)]`) are declarations, never calls, even with parentheses.
- Dynamic dispatch (`getattr(o, n)()`, `call_user_func($f)`, `send(:m)`, `eval`) is a call to the
  dispatcher. The dynamic target is not recorded, since there is no AST and no data flow.

**C2 · Keywords are never calls; built-ins are.** A control-flow, declaration or operator
keyword followed by `(` is not a call: `if (`, `foreach (`, `elseif(`, `returns (`,
`pub(crate)`, `let (a, b)`, `case (x, y)`, `not (`, `func() {...}`. A built-in or stdlib
function is a call (decision 1): `print(`, `len(`, `printf(`, the `log` of `console.log(`,
zig's `@intFromEnum(`. A load form that the `import` contract owns (`require(`, `import(`,
`include`) is `import`'s, not a second signal here (COUNT_CONTRACT corollary 4). Keywords are per
language: `throw` is one in C++, Java and JavaScript, but go's runtime `throw("...")`, matlab's
and haskell's are functions, so it sits in each keyword language's `_calls_out_ignore`, never in
the global set (#3645).

**C3 · Constructors, conversions and macros are calls to the name written.** `new Foo(a)`,
Python `Foo(a)`, rust `Some(x)`, go `uint32(x)`, C `Py_DECREF(o)` and m4 `AC_DEFUN(...)` are all
calls to `Foo` / `Some` / `uint32` / `Py_DECREF` / `AC_DEFUN`. A go conversion to a parenthesized type,
`(*T)(x)` or `(*unsafe.Pointer)(p)`, is a call to `T` / `Pointer` (#3645). The resolver matches the name to a
class, type, variant or macro definition, or labels it `external`. A language whose indexing is
spelled exactly like a call (matlab `x(1)`) cannot tell the two apart without types. That is an
inherent limit, recorded per language, not something a rule fix can reach.
A *pattern* is not a call, even though it is spelled like one (#3641, decided by Joe
2026-09-25): rust `Data::Struct(x) =>` and `Ok(t) =>` in a `match`, and any destructuring
pattern that only tests or binds, construct nothing. The same `Ok(t)` in an expression is a
constructor call. Rust's own pattern (`CALLS_OUT_RUST`, #3643) drops a capitalised `Name(…)` whose
one-line argument list is followed by `=>`, a pattern `|`, a binding `=` or a guard `if`; it also
takes macros (`format!(`, `vec![`) and turbofish calls (`collect::<Vec<_>>()`). A closure-trait bound
(`F: Fn(&T)`, `impl FnOnce(u8)`) is a type, and `Fn`/`FnMut`/`FnOnce` are in rust's keyword set (C2).

**C4 · A transfer is not a call.** An unconditional jump that does not return (`goto`, COBOL
`GO TO`, assembly `jmp`, AGC `TC Q` used as a return) is not an invocation. The branch contract
(#2822) says the same. **Where the jump's target is a callable unit, the transfer is kept
beside the calls, not dropped** (#3362, decided by Joe: option C). A COBOL `GO TO <paragraph>`
lands in the function's `transfers_to`, through cobol's `_transfers_out` helper pattern. The
resolver links it like a call, as an `fcall_data` row of `kind = 'transfer'`. Reachability,
blast radius and function fan-in/PageRank follow it; the call-resolution rates and the
file graph do not. Dropping it outright would have orphaned the quarter of the crucible's
COBOL paragraphs (2,288 of 9,148) that nothing PERFORMs, which is also how the mainframe answer
keys read liveness.

**C5 · A declaration is not a call.** A function or class declared inside the body
(`def inner(`, `local function f (`, a nested `fn`) is not a call to `inner`. Shared
`CALLS_OUT_C_STYLE` still matches these headers, and since #3360 the detector drops a capture
that sits on a nested header of the language's own `func_start` rule when the slicer emitted that
nested unit. A later real call to `inner(...)` in the same body is kept.

**C6 · The entry is the bare name.** `obj.save()`, `self.save()`, `utils.save()` and
`Store::save()` are all `save`. The qualifier (`obj`, `self`, `utils`, `Store`) is a separate
datum (#3329), kept beside `calls_out_to` and never folded into its elements. That keeps the list's
element type, and every consumer, unchanged. Positional-invocation languages (jcl, #3292) are the
one exception to self-removal: a step that runs a program of its own name is not recursion.

**C7 · Strings and comments are not calls, and blind is declared, not guessed.**
`calls_out` is the one rule that runs after `_apply_literal_shield`, so a name inside a string
literal is not a call. This is a documented exception to STREAM_CONTRACT corollary 1, and tcl's
brace-quoted strings are the gap (#3359). A language with no by-name invocation form, or one where
only an AST could tell (shell, markup, data, config), sets `CALLS_OUT_UNSUPPORTED` and records an
empty list, never a heuristic.

**C8 · A call belongs to the innermost named unit around it** (#3641, decided by Joe
2026-09-25).
- A call inside a nested *named* function belongs to that inner unit only, never also to the
  outer one. This is C5 seen from the body side: the nested function is its own unit, so its
  calls are its own.
- A call inside an *anonymous* function (lambda, arrow function, closure, block, callback)
  belongs to the enclosing named unit. An anonymous function cannot be called by name, so it
  is never a unit of its own, and its body is part of the body it is written in.
- Comparisons follow the same rule: `call_graph_accuracy.py` gives an anonymous function's
  calls to its enclosing named function, never drops them.

## Fallback families

| family | pattern | languages |
|---|---|---|
| C-style | `CALLS_OUT_C_STYLE` `\b(name)\s*\(` | the C-family languages, from ada to zig |
| Ruby | `CALLS_OUT_RUBY`: `obj.name`, `name(`, `name?`/`name!`, a statement-opening command (`puts x`); never a bare word (#3377) | ruby |
| CALL verb | `CALLS_OUT_CALL_VERB` | assembly, fortran, pli, rexx, db2_sql |
| command position | `CALLS_OUT_COMMAND_POSITION` + a keyword `_calls_out_ignore` | tcl, powershell, livecode |
| lisp | `CALLS_OUT_LISP_FAMILY` | scheme |
| own | a language-local rule | abap, agc_assembly, batch, cobol, haskell, hlasm, hlo, jcl, makefile, mlir, objective-c |
| blind | `CALLS_OUT_UNSUPPORTED` | 18 languages (C7) |

## Audit (language-crucible v1.4.0, engine `origin/main` 48efa456)

`funcs` is functions sliced on the crucible; `names` is distinct callee names emitted, summed
over functions. Disagreement classes: **K** keyword captured (C2, #3359) · **A** annotation
captured (C1, #3359) · **S** string content (C7, #3359) · **D** nested declaration (C5, #3360)
· **G** transfer captured (C4, #3362) · **I** inherent (C3) · **R** ledgered recall/precision
gap from #3264. **B** (built-ins filtered, C2, #3361) applied to *every* C-style, lisp and
command-position language through the global ignore set, so it is not repeated per row. #3361
fixed it: the census below predates that fix.

| language | family | funcs | names | verdict |
|---|---|---|---|---|
| abap | own | 124 | 1 | agrees (PERFORM, CALL FUNCTION/METHOD/TRANSACTION) |
| ada | C-style | 962 | 2,713 | K: `is` (269, expression-function `is (`), `else`/`then`/`not`; pragmas already ignored |
| agc_assembly | own | 812 | 829 | agrees; `TC Q` (61) is the return idiom through the Q register, not a call -- K |
| apex | C-style | 38 | 197 | agrees |
| assembly | CALL verb | 1,114 | 267 | agrees (`call` only; `jmp` is a transfer, correctly not captured) |
| batch | own | 0 | 0 | agrees (`call :label`); no functions sliced on the crucible |
| blp | blind | -- | -- | agrees (C7: declared blind) |
| bms | blind | -- | -- | agrees (C7: declared blind) |
| c | C-style | 1,743 | 9,174 | agrees; macros are calls (C3) |
| cobol | own | 9,154 | 9,614 | ~~G~~ fixed by #3362 (`GO TO` is now `transfers_to`); K: `PERFORM VARYING/UNTIL` (inline PERFORM, 35) |
| cpp | C-style | 1,370 | 9,068 | K: `static_assert`, `operator()`, `if constexpr`; macros are calls -- mostly agrees |
| csd | blind | -- | -- | agrees (C7: declared blind) |
| csharp | C-style | 964 | 4,722 | K: `foreach` 67, `nameof` 37, `default(T)`, `var (a, b)`, `static` lambdas, pattern `is`/`not`/`or` |
| css | blind | -- | -- | agrees (C7: declared blind) |
| csv | blind | -- | -- | agrees (C7: declared blind) |
| dart | C-style | 1,750 | 2,652 | A: `@pragma(`, `@Deprecated(` (37) |
| db2_sql | CALL verb | 1,426 | 354 | agrees (CALL + named routines, #3305) |
| dockerfile | blind | -- | -- | agrees (C7: declared blind) |
| embedded_python | C-style | 135 | 527 | D (nested def); B |
| fortran | CALL verb | 139 | 415 | agrees (CALL) |
| glsl | C-style | 0 | 0 | no functions sliced on the crucible (no evidence) |
| go | C-style | 897 | 4,732 | K: `func` literal (436); conversions `uint32(x)` are calls (C3) |
| groovy | C-style | 745 | 1,760 | A: `@Issue(` etc. (71) |
| haskell | own | 147 | 281 | own juxtaposition rule; captures lambda/pattern variables (`x`, `m`, `f`) -- R (recall/precision gap, ledgered #3264) |
| hlasm | own | 1 | 0 | agrees (`=V()` only; system macros a ledgered recall gap) |
| hlo | own | 0 | 0 | agrees (`calls=`/`to_apply=`); no functions sliced |
| html | blind | -- | -- | agrees (C7: declared blind) |
| java | C-style | 318 | 879 | A: `@Annotation(` (23); K: `this(` constructor chaining |
| javascript | C-style | 827 | 3,598 | D (nested `function f(`, 49); B (`console.log` -> `log`) |
| jcl | own | 376 | 373 | agrees (EXEC PGM=/PROC, positional, #3292) |
| json | blind | -- | -- | agrees (C7: declared blind) |
| kotlin | C-style | 28 | 35 | A: `@Throws(`, `@JvmName(` |
| livecode | command position | 1,063 | 2,527 | K: `private` 250, `public` 99, `command` 95, `variable`, `case`, `break`, `module`, `handler`, `default`, `constant` (~800 of 2,527) |
| lua | C-style | 1,370 | 3,301 | K: `not (`/`or (`/`and (`; D (`local function f`, 55) |
| m4 | C-style | 39 | 142 | agrees (macro invocations are calls) |
| makefile | own | 1 | 0 | agrees (`$(call f)`) |
| markdown | blind | -- | -- | agrees (C7: declared blind) |
| matlab | C-style | 138 | 812 | I: indexing `x(1)` is spelled like a call (`EEG`, `data`, `g`) -- inherent |
| mlir | own | 0 | 0 | agrees (`call @f`); no functions sliced |
| nix | blind | -- | -- | agrees (C7: declared blind) |
| objective-c | own | 156 | 269 | own rule: unary selectors are a ledgered recall gap; agrees otherwise |
| pbtxt | blind | -- | -- | agrees (C7: declared blind) |
| perl | C-style | 886 | 2,580 | K: `qw(` 30, `and`/`or`/`do`/`until` |
| php | C-style | 1,703 | 7,104 | K: `foreach` 237, `isset` 209, `empty` 152, `elseif` 114, `array` 111, `unset` 78, `use` 44, `fn` 44, `match`, `die` |
| plaintext | blind | -- | -- | agrees (C7: declared blind) |
| pli | CALL verb | 7 | 6 | agrees (CALL) |
| powershell | command position | 474 | 1,417 | K: `break`/`exit`/`continue`/`default`/`Function`/`Return`/`Throw` in command position |
| proto | blind | -- | -- | agrees (C7: declared blind) |
| python | C-style | 3,750 | 9,820 | D (nested def, 380); K: `in (`, `not (`, `and (`, `or (`, `elif(`; B (`print`, `len`, `map`, `getattr`, ...) |
| rexx | CALL verb | 115 | 90 | agrees (CALL) |
| ruby | C-style | 132 | 111 | agrees; B (`super`). Since #3377 its own family: paren-less calls took Level-1 recall 34.4% -> 92.9% |
| rust | C-style | 2,113 | 7,898 | K: `pub(crate)` 81, `let (a, b)` 68, `fn(` pointer types; D (nested `fn`, 78); variants `Some(`/`Ok(` are constructors (C3) |
| scala | C-style | 541 | 3,434 | K: `case (` 55, `val (` 27; D (nested def, 72); A (`@deprecated(`) |
| scheme | lisp | 83 | 3,480 | K: special forms `let*`/`let-values`/`case-lambda`/`syntax-case`/`define-record-type` and binding lists `((x 1))` |
| shell | blind | -- | -- | agrees (C7: declared blind) |
| solidity | C-style | 105 | 321 | K: `returns (` 74, `assembly`, `override(` |
| sqlite | blind | -- | -- | agrees (C7: declared blind) |
| swift | C-style | 133 | 319 | A: `@available(`, `@escaping`, `@Sendable` (25) |
| tcl | command position | 394 | 1,110 | S: SQL keywords inside brace-quoted strings in command position (`SELECT`, `WHERE`) |
| td | blind | -- | -- | agrees (C7: declared blind) |
| typescript | C-style | 5,770 | 13,765 | K: `async (` 34; D (nested `function`, 172); B |
| xml | blind | -- | -- | agrees (C7: declared blind) |
| yacc | C-style | 27 | 89 | agrees (C actions) |
| yaml | blind | -- | -- | agrees (C7: declared blind) |
| zig | C-style | 3,525 | 19,370 | D (nested `fn`, 296); K: `and (`/`or (`, `union(enum)`; `@builtin(` are calls (C2) |

Summary: 37 of 65 languages agree outside the global **B**. The rest are **K** (19), **A** (6),
**D** (8), **S** (1: tcl), **G** (1: cobol), **I** (1: matlab) and **R** (1: haskell). Every
disagreement is precision (a non-call emitted), except **B**, which is recall.

## #3359 resolution (classes K, A, S)

Fixed by #3359, re-censused on the same crucible plus keyword-rosetta: 4,300+ non-call names
left `calls_out_to` across 25 languages, and every one was checked to be a keyword, special
form, annotation or string word (no real callee dropped).

- **K:** keyword entries added to each language's `_calls_out_ignore` (built-ins and
  `_CALLS_OUT_GLOBAL_IGNORE` untouched; #3361 owns those). The per-language set is now compared
  **exactly** in a case-sensitive language and casefolded only for `identifier_case:
  insensitive`, so a keyword never swallows a capitalised callee (go `v.Type()`, C#
  `factory.This()`, perl `$self->Warn(`).
- **A:** `CALLS_OUT_C_STYLE_NO_ANNOTATION` (`(?<!@)`) for java, kotlin, swift, dart, groovy and
  scala. Python/TypeScript/JavaScript keep the plain pattern: `@retry(3)` is a call.
- **S:** tcl's command-position rule skips upper-case SQL keywords that start the lines of a
  brace-quoted query (upper-case only: `set`/`update` are real Tcl commands).
- **cobol:** `END-PERFORM`/`END-CALL` no longer hand the next statement's first word to the
  verb (`(?<![\w-])`), which also recovered a real `PERFORM` target; inline
  `PERFORM VARYING/UNTIL/WITH TEST` names no paragraph. **agc:** `TC Q` (the return) is ignored.

Left open (a regex change too invasive for a keyword list, or not a keyword after all):
scheme `let` binding lists `((x 1))` (the same `((` shape is a `cond` clause or a curried call);
dotted and use-site annotations (`@a.b.C(`, `@file:JvmName(`); rust `Fn(` trait sugar and
`#[cfg(not(...))]` predicates; tcl brace-quoted *prose* (lower-case words at line start);
powershell hashtable-key and enum-member lines in command position; cobol
`PERFORM <data-name> TIMES`. Not keywords on inspection, so kept as calls: perl `do`/`then`
(every crucible hit is `$dbh->do(` / `->then(`), php `match` (`$this->match(`), tcl `default`
(a macports command), perl `qx(` (runs a shell command).

## How the census was taken

A scratch probe (not committed; same shape as `tests/tools/wrapper_probe.py`) ran the
detector's `splice()` over every crucible file of each language. It tallied `calls_out_to` and,
for each raw capture, the word before it. That preceding-word table is what separates `def:`,
`function:`, `@` and `->`/`.` contexts. Keyword candidates were checked against a reserved-word
list and read by hand, because most list hits (`get`, `open`, `next`) are ordinary method names.

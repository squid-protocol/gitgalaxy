# The `args` rule's contract

> Filed as [#2773](https://github.com/squid-protocol/gitgalaxy/issues/2773). Same shape as
> `docs/api_rule_contract.md` (#2730): this document is the stated contract, plus the audit of all
> 46 corpus languages against it. `gitgalaxy/standards/how_to_add_a_language.md` carries the
> one-line form next to the rule in the output schema; this file carries the reasoning, the
> fallback family, and the per-language verdicts.

## The contract

> **`args` matches the parameters a callable declares.**

Three corollaries, each of which the audit below found a language violating:

1. **A call is not a declaration.** A call site *consumes* a parameter surface; it does not
   publish one. `free(conn);`, `describe(kit);`, `[store setVersion:V]`, `assertEquals(a, b)` are
   all references to somebody else's parameter list. (`objective-c` counted 146 C calls and 120
   Objective-C message sends; `typescript` counted 6133 call statements; `groovy` and `apex` still
   do — see the audit. `css` did too, until [#2893](https://github.com/squid-protocol/gitgalaxy/issues/2893)
   answered it with a stated absence rather than a narrowing.)
2. **The declaration anchor has to be in the rule.** A parameter list is `(...)`, and so is a call,
   a cast, a grouped expression and an `if` condition. What separates them is always local
   context — a `def`/`fn`/`func`/`proc` keyword, a `-`/`+` method lead, a return type, a body
   brace — and the rule has to require it. `func_start` can afford the ambiguity because
   `_slice_by_braces` re-validates every match downstream; `args` cannot, because `struct_args` is
   the raw rule count over the whole code stream with nothing downstream of it.
3. **A reference to a parameter is not a declaration of one either — at the per-function level.**
   In a language with no formal parameter list, `$1`/`$@` in a body is the only parameter surface
   there is, and at file level counting each occurrence is the language's own morphology, not a
   defect (keyword-rosetta ledgers this for `m4` as `m4-parameters-are-use-sites`). But
   `avg_func_args` is an *arity*, and an arity is the **highest position declared**, not the
   first one seen. Without `_args_findall_max_groups` the per-function path `.search()`es the
   block and trusts the LEFTMOST hit, which drops every higher position after it (`$1 … $3`
   reads 1) and counts `$0` — the macro's own name — as a parameter. `shell` fixed this in
   #1518; `m4` followed in #2784.

## What this is used for

`args` feeds two very different consumers, and only one of them has a safety net:

- **`struct_args`** — `record_keeper.py` maps the rule's raw per-file count straight to this
  column. Nothing filters it. This is what the corpus's bias table reads, and what the
  tri-comparison's argument-accuracy figure (98.9% across 45 languages, the #1261 close criterion)
  is computed against.
- **`avg_func_args`** — `signal_processor.py:577` averages the *per-function* `args` counts
  produced by `_calculate_block_metrics`, which then feeds `log_avg_func_args` into scored risk
  (and `security_auditor.py:383` recomputes it the same way). For a handful of languages
  (`objective-c`, `c`, `cpp`, `dart`) `_slice_by_braces` bounds that per-function search to the
  matched signature text via `args_search_text`; for every other language the rule is searched
  over the whole block, body included, and the first match wins.

So an over-broad `args` rule is wrong twice: it inflates a file's coupling signal directly, and —
wherever there is no signature bound — it lets a function with no parameters borrow an argument
count off the first call statement in its own body.

## The documented fallback family

Some languages have no formal parameter-list syntax at all. For those, `args` counts the
**construct that stands in for a declared parameter**, and that substitution is deliberate, not a
defect — `docs/why_gitgalaxy_beats_ast_here.md` logs the bash/Perl case (#1518/#1519) as one of the
places GitGalaxy reads a file more accurately than a tree-sitter parse of it does.

| language | stands in for a declared parameter |
|---|---|
| `shell` | `$1`…`$9`, `$@`, `$*`, `$#` — the highest position referenced, not the number of references |
| `perl` | `shift` / `my (...) = @_` unpacking idioms in the body |
| `m4` | `$1`…`$n`, `$@`, `$*` |
| `makefile` | `$(1)` / `${1}` inside a `define`, and `$(call fn,...)` |
| `yacc` | `$1`…`$n`, `$$` — a rule action's semantic values |
| `assembly` | the argument-passing registers of the calling convention |
| `agc_assembly` | the erasable/bank operand of an instruction |
| `abap` | `IMPORTING`/`EXPORTING`/`CHANGING`/`RETURNING`/`EXCEPTIONS` blocks owned by a declaration statement (`METHODS`/`CLASS-METHODS`/`FORM`/`FUNCTION`/`MODULE`), via the `abap_declaration_statement` scope filter ([#2824](https://github.com/squid-protocol/gitgalaxy/issues/2824)) — the same six keywords at a `CALL FUNCTION`/`PERFORM`/`RAISE EXCEPTION`/functional-call site pass actuals and do not count |
| `cobol` | `USING` / `RETURNING` in a `PROCEDURE DIVISION` header |
| `jcl` | `PARM=` on `EXEC`, and a `PROC` statement's own symbolic parameters |
| `dockerfile` | `ARG` — a build-time parameter declaration |
| `sqlite` | bind parameters (`?`, `?n`, `:name`, `@name`) and a CTE's column list |
| `html` | the addressable attributes of a form/element (`name`, `value`, `for`, `data-*`, `aria-*`) |
| `yaml` | a `with:`/`inputs:`/`args:` block's direct children, via the `yaml_parameter_block` scope filter ([#2753](https://github.com/squid-protocol/gitgalaxy/issues/2753)) |

`css` is deliberately **not** in that table: it records a stated absence instead (see "One stated
absence" below).

`keyword-rosetta`'s `deviation_ledger.json` carries the matching decline under
`args-no-parameter-surface-morphology` for the languages whose shells score 0 or near-0 against a
planted 13 (`css`, `html`, `dockerfile`, `makefile`, `sqlite`, `yacc`, `cobol`, and `yaml` until
#2753). That entry covers the **low** tail — and since #2893 it covers css as an *absence* rather
than a low count. This document's audit is the first pass over the **high** tail.

## The audit — all 46 corpus languages

Counts are `args` matches over the **code stream** (comments stripped, exactly what the engine
scans), on the `keyword-rosetta` control corpus (SPEC plants 13 — one parameter per probe) and on
the `language-crucible` real-world corpus. `a → b` is this change; a single number means the rule
was already inside the contract and is untouched. `a/f` is crucible `args` over crucible
`func_start` — not a target ratio, just the cheapest smell test for a rule that scales with call
density rather than declaration count.

| language | keyword-rosetta (planted 13) | crucible | crucible a/f | verdict |
|---|---|---|---|---|
| `abap` | 16 → 13 | 167 → 121 | 0.98 | violated corollary 1 -- the six binding keywords appear verbatim at call sites (`CALL FUNCTION ... EXPORTING/EXCEPTIONS`, `PERFORM ... CHANGING`, `RAISE EXCEPTION ... EXPORTING`, `walk( EXPORTING ... )`), audited clean in #2773 only because neither corpus then contained one. FIXED in #2824 via the `abap_declaration_statement` scope filter (the decision is statement-scoped and `re` has no variable-width lookbehind, so it cannot live in the rule); all 46 crucible drops verified as call sites, the corpus 16 → 13 is exactly the three `PERFORM` clauses #2806 planted |
| `ada` | 13 | n/a | n/a | anchored to `procedure`/`function` |
| `agc_assembly` | 13 | 416 | 0.51 | fallback family -- instruction operands |
| `apex` | 13 | 39 | 1.00 | violated corollary 1 -- the return-type prefix was optional, so `probeBranch(argv)` at line start counted. FIXED in #2783 (return type mandatory + a `{`-anchored constructor branch); the crucible's old 41-vs-41 was 38 real plus 3 false positives |
| `assembly` | 13 | 18837 | 16.54 | fallback family -- argument-passing registers |
| `c` | 13 | 4106 | 2.35 | the parameter list must open with a type token |
| `cobol` | 1 | 295 | 0.03 | fallback family -- `USING`/`RETURNING` |
| `cpp` | 13 | 3178 | 2.57 | the parameter list must open with a type token |
| `csharp` | 13 | 1283 | 1.30 | a return type is mandatory; a constructor must reach `: base`/`this` or `{` |
| `css` | 6 → **n/a** | 3855 → **0** | — | **stated absence** (#2893): CSS declares no callable, so no parameter surface. Was the fallback family's one knowingly-approximate member |
| `dart` | 13 | 1289 | 0.72 | anchored by the `(?=\{|=>|:|async|sync)` terminator lookahead |
| `dockerfile` | 4 | n/a | n/a | fallback family -- `ARG` |
| `embedded_python` | 13 | 135 | 1.00 | anchored to `def`/`lambda` |
| `fortran` | 13 | n/a | n/a | anchored to `SUBROUTINE`/`FUNCTION`/`ENTRY` and `INTENT` |
| `go` | 13 | 897 | 1.00 | anchored to `func` |
| `groovy` | 13 | 991 | 1.13 | violated corollary 1 -- the return-type run was `{0,3}`, so `close(conn)` at line start counted. FIXED in #2782 (a `{`-anchored bodied arm plus a typed bodyless arm for interface/abstract declarations) |
| `haskell` | 15 | 169 | 0.68 | inside the contract -- an arrow-less `::` signature is a CAF, and a Haskell top-level value IS a nullary function (ledger `haskell-caf-bindings-count-as-functions`); `func_start` agrees with `args` on it |
| `html` | 3 | 676 | 6.76 | fallback family -- addressable attributes |
| `java` | 13 | 384 | 1.21 | a return type is mandatory; a constructor must reach `throws` or `{` |
| `javascript` | 13 | 1020 | 1.22 | the class-member arm carries a `(?=[ \t\n]*\{)` body lookahead -- the precedent typescript had dropped |
| `jcl` | 13 | 43 | 0.12 | fallback family -- `PARM=` and `PROC` symbolics |
| `kotlin` | 13 | 28 | 1.00 | anchored to `fun`/`constructor` |
| `livecode` | 13 | 527 | 0.55 | anchored to `on`/`command`/`function`/`getprop`/`setprop` |
| `lua` | 13 | 1551 | 2.44 | anchored to `function` |
| `m4` | 18 | 70 | 1.79 | fallback family at file level (ledger `m4-parameters-are-use-sites`), unchanged. `avg_func_args` violated corollary 3 -- no `_args_findall_max_groups`, so the leftmost hit won: `$1 ... $3` read 1 and `$0` read 1. FIXED in #2784 (note: that issue's `$1 ... $1` example never reproduced -- it already read 1) |
| `makefile` | 1 | 0 | 0.00 | fallback family -- `$(1)` inside `define`, `$(call ...)` |
| `markdown` | 0 | n/a | n/a | no rule (no callables) |
| `matlab` | 13 | 36 | 1.57 | anchored to `function` |
| `objective-c` | 21 → **13** | 378 → **101** | 0.64 | **fixed here** -- the selector arm now requires a `-`/`+` method lead, the C arm a named typed parameter |
| `perl` | 13 | 1142 | 1.18 | anchored to `sub`/`method`, plus the documented `shift`/`@_` body idioms |
| `php` | 13 | 1901 | 1.12 | anchored to `function`/`fn` |
| `powershell` | 13 | 462 | 0.97 | anchored to `param`/`function`/a typed method head |
| `python` | 13 | 3779 | 1.01 | anchored to `def`/`lambda`/`cdef` |
| `ruby` | 13 | 61 | 0.49 | anchored to `def` |
| `rust` | 13 | 2638 | 1.25 | anchored to `fn` and closure `|...|` |
| `scala` | 13 | 1365 | 2.52 | anchored to `def` and `=>` |
| `scheme` | 13 | 262 | 1.00 | anchored to `(define (` |
| `shell` | 13 | 972 | 0.85 | fallback family -- highest `$n` position referenced (`_args_findall_max_groups`) |
| `solidity` | 13 | 114 | 1.00 | anchored to `function`/`modifier`/`error`/`event`/`constructor` |
| `sqlite` | 1 | 161 | 0.69 | fallback family -- bind parameters and CTE column lists |
| `swift` | 13 | 168 | 1.23 | anchored to `func`/`init`/`subscript` and closure heads |
| `tcl` | 13 | 394 | 1.00 | anchored to `^proc NAME {...}` (`_args_tcl_pattern_list_groups`) |
| `typescript` | 15 → **13** | 16844 → **11025** | 1.28 | **fixed here** -- the class-member arm now requires `{` or a `:` return type, the arrow arm a bounded return-type gap |
| `yacc` | 2 | 114 | 4.22 | fallback family -- `$n` semantic values |
| `yaml` | 13 | 0 | - | `inputs:`/`with:`/`args:` children, via the `yaml_parameter_block` scope filter (#2753) |
| `zig` | 13 | 3784 | 1.07 | anchored to `fn` (`_args_bare_body_groups`) |

`ada`, `dockerfile`, `fortran` and `markdown` have no files in the `language-crucible` corpus, so
their crucible columns read `n/a`.

### What the audit found

**Two languages fixed here (#2773).** `objective-c` and `typescript` were the two the issue
measured, and both turned out to be worse on real code than on the control shells:

| | rosetta (planted 13) | crucible `args` | crucible precision |
|---|---|---|---|
| `objective-c` before | 21 (+62%) | 378 | 26.7% -- 101 declarations, 277 call sites |
| `objective-c` after | **13** | **101** | ~100% (the one residual hit is a method definition tree-sitter itself mis-parses) |
| `typescript` before | 15 (+15%) | 16844 | 61.3% -- 10326 declarations, 6518 call sites |
| `typescript` after | **13** | **11025** | 99.0% -- 10910 declarations, 115 call sites |

Precision is measured by classifying every regex match against a `tree-sitter` parse of **the same
code stream the engine scans**: a match whose parenthesised span resolves to `formal_parameters` /
`parameter_list` / `method_definition` is a declaration, one that resolves to `arguments` /
`argument_list` / `message_expression` is a call. (Parsing the code stream rather than the raw file
keeps byte offsets aligned, since prism blanks comments in place.) The typescript fix also *raises*
recall — 10326 → 10910 real declarations — because the over-reaching arrow arm used to swallow real
parameter lists inside an over-long match.

**Two filed for follow-up, and two corrections to this audit's first draft.**
[#2782](https://github.com/squid-protocol/gitgalaxy/issues/2782) (`groovy`, +46%) and
[#2783](https://github.com/squid-protocol/gitgalaxy/issues/2783) (`apex`, +38%) are the same defect
in the same rule family — a `^[ \t]*IDENT(...)` member arm whose return-type prefix is optional.
Both are live, and keyword-rosetta's ledger carries them as
`args-call-site-counting-apex-groovy`.

The first draft of this audit also called `m4` and `haskell` violations. Both were **already
settled in keyword-rosetta's `deviation_ledger.json`**, and checking it first would have avoided
re-litigating them — a lesson worth more than either finding:

- `haskell` is **inside** the contract. `haskell-caf-bindings-count-as-functions` (validated
  2026-09-04) reads an arrow-less `::` signature as a CAF, and a Haskell top-level value genuinely
  *is* a nullary function. The engine is consistent about it — `func_start` counts it too, and
  `_args_arrow_count_groups` derives arity 0 — so the narrowing this document originally proposed
  would have made the two rules disagree on the same binding.
  [#2785](https://github.com/squid-protocol/gitgalaxy/issues/2785) is closed.
- `m4`'s **file-level** count is intended morphology (`m4-parameters-are-use-sites`): a macro names
  no parameters, so `$1` in the body is the parameter, and equalising the count would mean writing
  macros that never reference their own argument. What survives is narrower and untouched by that
  verdict — `avg_func_args` has no `_args_findall_max_groups`, so `AT_SETUP($1) AT_CHECK($1)` reads
  arity 2 for a one-parameter macro. [#2784](https://github.com/squid-protocol/gitgalaxy/issues/2784)
  is rescoped to that.

**Read the ledger before calling a language's `args` a defect.** It is the corpus's audit trail of
questions already asked and answered, and two of this audit's four findings were in it.

**One stated absence.** ([#2893](https://github.com/squid-protocol/gitgalaxy/issues/2893), which
replaced this section's former heading, "One knowingly approximate fallback".) `css` counted the
arguments of value functions — `calc()`, `var()`, `url()` — which are call sites, and corollary 1
says a call is not a declaration. That was kept for a while on the argument that *"CSS has no
callable of any kind, so the honest alternatives are this approximation or 0 forever, and 0 says a
stylesheet full of computed values has no coupling at all."* Both halves of that turned out to be
wrong, and `css` now records `args: None`.

**There is a third alternative, and the sheet already mandated it.** `signal_contracts.py`'s
`COUNT_CONTRACT` corollary 3: a language that cannot express the construct records *"a
contract-level absence (`None` rule + a ledgered `intended-morphology` entry) rather than a
manufactured construct. The two answers cannot coexist inside one signal."* `None` is not `0` — an
n/a cell leaves the median instead of being compared against it. `docs/io_rule_contract.md` C3
records the same answer for solidity (`io: None`, the EVM cannot reach outside itself).

**A stylesheet's coupling is measured — by the rules whose contracts name it.** Composition of all
3855 hits the old rule made on the language-crucible's 38 css files (code stream):

| head | hits | share | who owns it now |
|---|---:|---:|---|
| `var(` | 2521 | 65.4% | `safety` owns 512 of them (the guarded `var(x, fallback)` read); the rest is the named residual below |
| `rgba(` `rgb(` `oklch(` `color-mix(` | 931 | 24.2% | nobody, and nobody should — a colour written longhand is not coupling |
| `calc(` | 321 | 8.3% | `reflection_metaprogramming` owns the nested form; **226 of the 321 already contained a `var()`** |
| `url(` | 77 | 2.0% | `io`, since [#2752](https://github.com/squid-protocol/gitgalaxy/issues/2752) |
| `clamp(` `min(` | 5 | 0.1% | `safety` |

And on those same files: `api` counts **3597 `--custom-property:` declarations** — the definitions
of the very tokens `var()` reads, a *larger* surface than the reads — plus `safety` 515, `io` 14,
`reflection_metaprogramming` 24, `import` 9. Three of those five rules postdate the sentence they
disprove.

**It was also wrong twice per file.** css receives no `args_search_text` (only `objective-c`, `c`,
`cpp` and `dart` do), so `_calculate_block_metrics` searched the whole block *body* and took the
first match — the failure this document describes under "What this is used for". Six at-rules
carried 13 parameters borrowed from their own bodies: `tailwindcss_atrules/preflight.css:291`'s
`@supports` has no parenthesised call in its prelude at all and read arity **3** off a
`color-mix(in oklab, currentcolor 50%, transparent)` three lines inside the block. tree-sitter
reads 0 for all 25 css at-rules; `args_exact_match` went **19/25 → 25/25**.

**The named residual.** The *unguarded* `var(--x)` read — 2521 − 512 = **2009** crucible
occurrences — is now unmeasured. This is deliberate and is recorded rather than hidden: no stated
contract owns "reads a document-lifetime binding by name" (the `globals` contract's **C2**
explicitly excludes an ordinary read by name), and inventing a home for it to preserve a number is
the failure mode the absence exists to end. If it earns measurement, it earns its own signal.

**Reopen condition.** `css.py`'s `extensions` claims `.scss`, `.sass`, `.less`, `.styl` and
`.pcss`, and **Sass and Less genuinely declare parameters** — `@mixin button($size, $color)`,
`@function foo($a, $b)`, Less `.mixin(@a; @b)`. So "CSS has no callable of any kind" is false at
the scope this definition claims, and this absence does **not** cover those dialects. Narrowing the
rule to those declaration forms — which would satisfy the contract rather than except it — was
considered and rejected on measurability alone: there are zero `.scss`/`.sass`/`.less` files in the
language-crucible, zero in `keyword-rosetta`, and zero on the build box, so the rule could not be
measured on either corpus. **If a preprocessor dialect enters the crucible, write the
declaration-form rule and retire the absence.**

(Contrast `matlab`'s `api` fallback in `docs/api_rule_contract.md`, which is still kept: MATLAB
*has* callables, so an approximation there is a precision question, not a category error.)

**Everything else was already inside the contract**, and the compliant rules cluster into four
recognisable anchors, worth knowing before writing a new one:

1. **A declaration keyword** — `def`, `fn`, `func`, `function`, `sub`, `proc`, `procedure`,
   `define`, `SUBROUTINE`. Nineteen languages. Cheapest and strongest anchor there is.
2. **A mandatory return type** — `java`, `csharp`. Works wherever the grammar has no
   type-inferred declaration form.
3. **A terminator lookahead** — what FOLLOWS the parameter list. `javascript` (`(?=[ \t\n]*\{)`),
   `dart` (`(?=\{|=>|:|async|sync)`), and now `typescript`. The only option when both the keyword
   and the return type are optional.
4. **A typed parameter list** — `c`, `cpp`, and now `objective-c`'s C arm: the list must *open*
   with a type token. Note that a type token alone is not enough — `_*[A-Z]\w*`, the PascalCase
   typedef fallback all three share, matches the first argument of `StrAllocCopy(Address, tag);`.
   `objective-c` additionally requires a parameter *name* after the type.

## Notes for the next rule

- **`args` has no downstream validator, and `func_start` does.** This is the single most useful
  thing to know here. `func_start`'s own class-member arms are just as ambiguous as `args`'s were,
  and that is fine: `_slice_by_braces` re-checks every match for a real body and drops the ones
  without. `struct_args` is the raw count. Never reason from "`func_start` gets away with it".
- **Where there is no signature bound, an over-broad rule reaches into the body.** For most
  languages `_calculate_block_metrics` searches the `args` pattern over the whole block and takes
  the first match, so a zero-parameter function whose body opens with a call statement used to
  borrow that call's argument count. Only `objective-c`, `c`, `cpp` and `dart` pass
  `args_search_text`.
- **If you widen the rule, grep every consumer.** #2753's yaml scope filter made `args`
  deliberately over-broad and had to teach `_calculate_block_metrics` to read the filtered
  `hit_vector` instead of re-running the raw rule. `_scope_filters` and the `_args_*_groups`
  helpers are both part of the rule's contract, not decoration.
- **`_args_*_groups` helpers are the precedent for a non-`(...)` parameter surface.** `tcl`'s
  `_args_tcl_pattern_list_groups` (a braced list), `haskell`'s `_args_pattern_list_groups` (an
  equation's LHS), `shell`'s `_args_findall_max_groups` (positional references), `zig`'s
  `_args_bare_body_groups` (an already-unwrapped list), `perl`'s `_args_prototype_groups` (a sigil
  prototype that carries types but not arity). Reach for one of these before inventing counting
  logic in `detector.py`.
- **Measure on both corpora, and on both metrics.** The control shells are four small files;
  `keyword-rosetta` landing on exactly 13 proves the anchor is *right*, not merely narrower, but it
  cannot show you what a real file does — `objective-c` read +62% on the shells and +274% on
  `worldwideweb`. And a file-level count cannot show you a *misattributed* match: the first
  spelling of typescript's arrow-arm gap excluded `(` outright, which made the arm skip a curried
  arrow's real parameter list and match the one inside its return-type annotation instead. The
  file-level totals barely moved; `tree_sitter_accuracy_audit.py --lang typescript` caught it
  (`args_exact_match` 2881 → 2875, 6 fp-ts functions). **Run that audit after any `args` change**,
  for every language it baselines.
- **Check `keyword-rosetta/deviation_ledger.json` before calling anything a defect.** Every
  language's odd `args` reading has probably already been triaged there, with a `disposition`
  (`intended-morphology`, `engine-semantic`, `upstream-bug`) and a dated verdict. Two of the four
  violations this audit first reported were already settled in it. `grep '"signal": "args"'` is a
  30-second check that outranks any amount of measurement.
- **The oracle for this rule is tree-sitter over the CODE STREAM.** Parse
  `prism.split_streams(src, lang)["code_stream"]`, not the raw file — prism blanks comments in
  place, so byte offsets stay aligned — then for each match find the smallest node covering the
  parenthesised span the rule captured. `formal_parameters` / `parameter_list` /
  `method_definition` is a declaration; `arguments` / `argument_list` / `message_expression` is a
  call. That turns "is this rule right?" into a per-match confusion matrix over the whole corpus in
  one pass, and unlike #2753's PyYAML oracle or #2752's CSS walker it works for any language in
  `tree_sitter_language_pack`.

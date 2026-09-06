# The `state_mutation` rule's contract

> Filed as [#2765](https://github.com/squid-protocol/gitgalaxy/issues/2765), Phase 3 of the contract
> roadmap ([#2812](https://github.com/squid-protocol/gitgalaxy/issues/2812), `docs/contract_roadmap.md`).
> Same shape as `docs/api_rule_contract.md` (#2730) and `docs/args_rule_contract.md` (#2773): this
> document is the stated contract, plus the audit of all 46 corpus languages against it.
> `gitgalaxy/standards/signal_contracts.py` carries the machine-readable row and
> `gitgalaxy/standards/how_to_add_a_language.md` the one-line prompt form; this file carries the
> reasoning, the fallback family and the per-language verdicts. The executable form of the audit is
> `tests/extraction/languages/test_state_mutation_contract_2765.py`.

## The contract

> **`state_mutation` matches a statement that writes a new value into state that already exists:
> a re-assignment (plain, compound or `++`), an in-place update of a container or structure, or a
> write through a mutable cell or reference.**

Kind `site`, unit `sites`: one hit is one writing statement, the population `risk_state_flux`
divides by mass to get a flux density.

The issue framed this as a real design choice between two sentences. The rejected one, *"the
introduction or use of mutable state"*, is what rust/kotlin/swift/scala/zig implemented (a `var`
or `let mut` declaration counted, the write to it did not) and it turns the signal into a style
measure: a file that declares ten mutable locals and never re-assigns one would out-score a file
that re-assigns one global a hundred times. The chosen sentence is what every consumer of the count
already assumes: `_calc_state_flux` names its input "raw mutation", nets it against
`immutability_locks`, and calls the density *flux*; the cascading-flux proximity weight fires on a
mutation *near a decision*; the `cascading_state_mutation` bottleneck ranks files by it. All of
those read as behaviour, so the count has to be behaviour.

Four corollaries, each of which the audit found a language violating:

1. **A declaration is not a write, however mutable, even with an initializer.** `let mut x = 5;`,
   `var x = 5`, `int x = 5;`, go's `x := 5`, perl's `my $x = shift`, lua's `local t = {}`, ada's
   `X : Integer := 5` all bring state into existence; the signal counts where that state *changes*.
   The rule's assignment arm therefore anchors a **statement start** to a **bare lvalue** -- a type
   name or a `let`/`var`/`my`/`local` in front of the lvalue breaks the match. Where the language
   has no declaration syntax at all (shell, php, powershell, tcl, livecode, matlab, fortran, cobol,
   groovy scripts, jcl), the assignment statement is the only write form there is, and it counts:
   that is the corollary's fallback, the analogue of `api` corollary 3.
2. **A type, modifier or annotation naming mutable state is not a write.** `counter :: IORef Int`,
   `AtomicInteger counter;`, `volatile int held;`, `mutable int held;`, `MutableList<T>`, `Cell::`,
   `@State`, `@Setter`, a C# `set;` accessor -- these say what *could* be written; the write is
   `writeIORef`, `.set(`, `x = v`.
3. **A read, a bind or a cast is not a write.** javascript's `this.` in an rvalue or before a
   method call, haskell's `<-` (a monadic bind), perl's bare `shift` unpacking `@_`, C++'s `&x` and
   `std::move(x)`, solidity's `payable(x)`, sqlite's `ON UPDATE CASCADE` inside a constraint, a
   `.pop` used to read the last element into a declaration.
4. **One statement is one hit, and a token another rule owns for the same construct is not a
   second signal.** `UPDATE t SET ...` is one write (it counted twice); `ALTER TABLE t RENAME TO u`
   one (it counted twice); `s = append(s, x)` one (go counted the `=` and the `append(`).
   dockerfile `ENV` is `globals`; matlab `clear`/`clearvars`, m4 `popdef` and apex `.clear(` are
   `cleanup`; apex `delete`/`undelete` are `high_risk_execution`; lua `rawset` is
   `safety_bypasses`. The deliberate exception, recorded in keyword-rosetta's ledger under the
   `keyword-overlap` disposition, is jcl `// SET X=`: a job-wide symbol *and* its assignment
   (#2750), the language's only assignment form. sqlite's `UPDATE` likewise stays an `io` hit,
   because a table write is disk I/O -- that dual predates this contract and is ledgered.

### The documented fallback family

Some languages have no general assignment statement. For those `state_mutation` counts the
construct that stands in for a write, and that substitution is deliberate:

| language | stands in for a writing statement |
|---|---|
| `assembly` | a read-modify-write mnemonic in instruction position: `xchg`, `cmpxchg`, `xadd`, `inc`, `dec`, `neg`, `not` |
| `agc_assembly` | a store mnemonic: `TS`, `DXCH`, `XCH`, `INCR`, `AUG`, `DIM`, `STORE`... |
| `cobol` | the verb that performs the write: `MOVE`, `COMPUTE`, `ADD`, `SUBTRACT`, `MULTIPLY`, `DIVIDE`, `SET`, `INITIALIZE`, `STRING`, `UNSTRING`, `EXEC CICS PUT CONTAINER` |
| `sqlite` | a data-modifying statement: `UPDATE`, `ALTER TABLE`, `REPLACE INTO`, `INSERT OR REPLACE`, `ON CONFLICT DO UPDATE`, `json_set()` and friends |
| `jcl` | `// SET X=` (also `globals`, by design) |
| `makefile` | `+=` and `!=` -- the forms that modify an existing variable; `=`/`:=`/`?=` define one |
| `dockerfile` | the shell payload of a `RUN` step: `export X=` |
| `yaml` | an `env:` block (the step/job environment) and `export X=` inside a `run:` |
| `m4` | `pushdef`, `m4_append`, `m4_set_add`... (`popdef` is `cleanup`) |
| `scheme` | the `set!` family in operator position |
| `haskell` | the operation on a mutable cell: `writeIORef`, `modifyIORef`, `writeTVar`, `putMVar`, `modify`, `put`... |
| `dart` | the framework's write sites `setState(`/`notifyListeners(`/`markNeedsBuild(` alongside ordinary assignment |
| `css`, `html`, `markdown` | `None` -- purely declarative; ledgered as `intended-morphology` (`css-declarative-no-runtime-payload-morphology`, `html-2578-declarative-globals-state-mutation-morphology`, `markdown-lit-plane-morphology`) |

## What this is used for

`state_mutation` is read by four formulas in `signal_processor.py`, and by two proximity pairs:

- **`_calc_state_flux`** -- `risk_state_flux`: `max(0, flux - 0.5 * immutability_locks)` per mass
  line through a sigmoid. The corpus's worst metric by consistency (42-44%) because its input was.
- **`_calc_cog_load`** -- the `flux_density` term of `risk_cognitive_load`.
- **`_calc_safety`** -- `flux_weight * state_mutation` inside `attack_hits`.
- **`file_mass`** -- added to `sum_function_impacts + api + concurrency`.
- **the cascading-flux pair** (`branch` within 150 chars -> +2 per hit in the weighted view,
  #2546/#2631/#2813) and **the race-condition pair** (`concurrency` near unsynchronised flux).
  Since #2813 both live in the score layer's weighted view, so the recorded count *is* the rule's
  hit count and this contract governs what the corpus reads.

A rule that counts declarations makes `risk_state_flux` a measure of how many variables a file
names; a rule that counts `this.` reads (typescript: 376 hits of `this.error(` in one file) makes
it a measure of how object-oriented the code is. A rule that misses plain re-assignment
(javascript, typescript, ruby, python) makes the same construct invisible in one language and
scored in the next. All three were live on 2026-09-06.

## The audit -- all 46 corpus languages

Counts are `state_mutation` matches over the **code stream** (comments stripped, exactly what the
engine scans), on the `language-crucible` corpus at `v1.2.0` and on the `keyword-rosetta` control
corpus (raw rule hits over the four shell files; matlab's figure is before the return-channel scope
filter, which the engine applies afterwards). `a -> b` is this change; a single number means the
rule was already inside the contract and is untouched.

| language | crucible | keyword-rosetta | verdict |
|---|---|---|---|
| `abap` | 48 -> 402 | 2 -> 4 | too narrow: `MOVE`/`APPEND` only, modern ABAP writes with `=` |
| `ada` | -- | 2 | too broad: `X : T := v` declarations counted |
| `agc_assembly` | 1450 | 2 | agrees (fallback) |
| `apex` | 45 -> 38 | 3 -> 2 | too broad: `.clear(` (cleanup), `delete`/`undelete` (high_risk) |
| `assembly` | 255 -> 225 | 2 | too broad: `inc` matched the `.inc` of an `include` |
| `c` | 10644 -> 6300 | 5 -> 2 | too broad: declarations (`PyObject *dict = ...` 7534 of 8675 in #2743's sibling audit), `--` inside string dashes |
| `cobol` | 27561 -> 27038 | 2 | too broad: `END-STRING`/`END-ADD` scope terminators, the `REPLACE` directive |
| `cpp` | 11623 -> 4005 | 3 -> 0 | too broad: `&` (every `a && b`), `mutable`, `std::move`, `std::atomic`, declarations |
| `csharp` | 1749 -> 1527 | 2 | too broad: `set;` accessors, `volatile`, `x => y` lambdas, `ref int x` parameter declarations |
| `css` | `None` | n/a | contract-level absence (ledgered) |
| `dart` | 764 -> 2052 | 2 | too narrow: only *unspaced* `x=1` matched; `x = 1` was invisible |
| `dockerfile` | 13 -> 3 | 4 -> 2 | too broad: `ENV` is `globals` (corollary 4) |
| `embedded_python` | 190 | 2 | agrees on its plant; see `python` |
| `fortran` | 6344 -> 5066 | 3 | too broad: `INTEGER :: X = 1`, `CALL f(UNIT = 10)` mid-line specifiers |
| `go` | 3344 -> 1548 | 5 -> 2 | too broad: `:=` declarations, `_ = x` discards, `append(` double-counting its own `=` |
| `groovy` | 730 -> 895 | 2 | too broad/narrow: `@Setter`/`@Data` counted; `+=`, `++`, `.add(` did not |
| `haskell` | 41 -> 1 | 4 -> 2 | too broad: `IORef` in a type signature (the issue's finding), `<-` binds |
| `html` | `None` | n/a | contract-level absence (ledgered) |
| `java` | 133 -> 211 | 2 -> 0 | too broad/narrow: `volatile`/`Atomic*`/`@Setter` counted, setter *declarations* counted; `this.x = v` in constructors did not |
| `javascript` | 1661 -> 3078 | 2 -> 0 | too broad/narrow: `let`/`var` declarations and every `this.` read counted; `x = v` did not |
| `jcl` | 39 | 2 | agrees (fallback; `SET` dual with `globals` is ledgered) |
| `kotlin` | 52 -> 47 | 2 -> 0 | too broad: `var` declarations, `Mutable*`/`Atomic*` types |
| `livecode` | 3640 | 3 | agrees; the corpus's third hit is the decoy's own `put ... into` (corpus re-plant) |
| `lua` | 6025 -> 2248 | 2 | too broad: `local x = v` declarations, `{ key = value, }` constructor fields, `table.concat` |
| `m4` | 0 | 4 -> 2 | too broad: `popdef` is `cleanup` (corollary 4) |
| `makefile` | -- | 2 | agrees (fallback) |
| `markdown` | `None` | n/a | contract-level absence (ledgered) |
| `matlab` | 1321 -> 1303 | 19 -> 17 | too broad: `clear`/`clearvars` are `cleanup` (corollary 4) |
| `objective-c` | 507 -> 399 | 3 -> 2 | too broad: `NSString *note = ...` declarations, `x == y` |
| `perl` | 5838 -> 3932 | 4 -> 2 | too broad: `my $x = v` declarations, bare `shift` (98 of `my $self = shift;`), `delete` inside a string |
| `php` | 6096 -> 6328 | 2 | too broad/narrow: `global $x` (globals), `&$x`, `$a == $b`; `$a[] = v` did not count |
| `powershell` | 5206 | 3 | agrees; c.ps1's 1 is the corpus's `probe_debt` assignment (corpus re-plant) |
| `python` | 1461 | 2 | **too narrow, deferred**: counts attribute/container writes and `global`/`nonlocal`, never a plain re-assignment `x = v` (see below) |
| `ruby` | 54 | 2 | too broad: `class << self`, `def delete`, heredocs; plain local re-assignment is invisible (deferred with python) |
| `rust` | 2331 -> 636 | 2 -> 0 | too broad: every `mut` (`&mut self` 71 hits), `Cell::`/`RefCell::`/`Atomic*` types |
| `scala` | 274 -> 322 | 2 -> 0 | too broad/narrow: `var` declarations, `mutable`/`Atomic*` imports; `+=` did not count |
| `scheme` | 932 -> 944 | 3 | agrees; the corpus's third hit is the decoy's own `set!` (corpus re-plant) |
| `shell` | 2769 | 2 | agrees (`declare x=v` dropped as a declaration; `let` kept) |
| `solidity` | 104 -> 18 | 3 -> 1 | too broad: `payable(x)` casts, bare `=` in declarations and `=>` mappings |
| `sqlite` | 35 -> 4 | 2 -> 1 | too broad: `ON UPDATE CASCADE` constraints (9 of 35), `UPDATE ... SET` twice per statement |
| `swift` | 151 -> 120 | 2 -> 0 | too broad: `var` declarations (computed properties `var x: T {`), `inout`/`mutating`/`@State` |
| `tcl` | 2524 | 3 | agrees; the corpus's third hit is the decoy's own `set` (corpus re-plant) |
| `typescript` | 9069 -> 5618 | 2 -> 0 | too broad/narrow: `this.` reads (376 x `this.error(`), `let` declarations; `x = v` did not count |
| `yacc` | 93 -> 79 | 2 | too broad: C declarations inside action blocks |
| `yaml` | 0 | 2 | agrees (fallback) |
| `zig` | 2233 -> 3131 | 2 -> 0 | too broad/narrow: `var` declarations counted; `x = v`, `x += 1` did not |

### What the audit found

**The three families the issue named were real, and a fourth appeared.** Family (b) -- mutable
*declarations* counted, writes not -- was rust, kotlin, swift, scala, zig and also javascript,
typescript (`let`/`var`) and java (`volatile`/`Atomic*`). Family (c) -- every `=` including
initialization -- was c, cpp, objective-c, yacc, solidity, go (`:=`), lua (`local`), perl (`my`),
ada (`X : T := v`), fortran (`INTEGER :: X = 1`). Family (a), named verbs, mostly agreed, with the
verbs' own false positives (cobol `END-STRING`, assembly `.inc`, apex `delete`). The fourth family
is **reads counted as writes**: typescript's and javascript's `this.` (any use), haskell's `<-`,
perl's `shift`, C++'s `&`.

**The corpus plants moved in every family-(b) language.** The corpus authored those plants to the
rules as they were (`var first = items` twice), so under the contract they read 0. The re-plant is
`first = 1` / `first = 2` after one declaration, which is what "two mutations" means in those
languages; keyword-rosetta's companion PR carries it, together with the `probe_debt` bodies in
abap/fortran/matlab/powershell that assigned into a language with no declaration syntax and so
carried a `state_mutation` into a file planted at 0.

**Two rules moved by more than the issue predicted, both in the widening direction.** `dart`'s old
character-class arm `[^!=<>...\s]=` required the byte before `=` to be a non-space, so
`_hasBeenAnnotated = true;` (66 hits in one flutter file) had never counted; `abap`'s `=`
assignment -- the language's primary write form -- had never been in the rule at all. abap's
widening is bounded by the statement period: a named parameter in a multi-line call
(`iv_path = lv_path` on its own line) does not end its line with `.`, and a line that closes a `)`
it never opened is a call, not a statement. The first draft without that guard read 792 on
abapGit, more than half of them parameters.

**What the contract cannot do with a regex, and does not pretend to:**

- **python / embedded_python / ruby locals.** Python has no declaration syntax, so corollary 1's
  fallback says every assignment statement is a write -- and python's rule counts none of them,
  only `self.x =`, `global`/`nonlocal` and container mutators. ruby is the same for locals. Both
  read 2 on the corpus (the plants are container writes, which are writes) and both are honestly
  *narrower than the contract*: `x = x + 1` counts in lua, php, shell and go and not in python.
  Widening python is a one-line regex and a population-wide reprice of `risk_state_flux` for the
  engine's most-scanned language, so it is filed separately rather than folded into a 30-language
  PR: [#2817](https://github.com/squid-protocol/gitgalaxy/issues/2817). Until it lands, python and ruby
  sit in a narrower stratum, stated here rather than implied.
- **A class-body field initializer** (`count = 0;` inside a TS/JS class, an enum member's last
  line, a kotlin named argument without a trailing comma) is indistinguishable from a statement
  at the text level. The trailing-comma guard `(?![^\n(]{0,300},[ \t]*$)` removes the common
  case; the remainder is a bounded over-count in the same direction for every C-family language.
- **Default parameter values** (`function f(x = 1)`, php `function f($x = 1)`) are matched where
  the language's `(` is a statement start for the rule (c-family `for (i = 0; ...)`). javascript,
  typescript, java, kotlin, scala, swift, dart and csharp therefore do *not* treat `(` as a
  statement start, and their `for (i = 0` init is counted only through its `i++`.

## Adding a language after this

When you write a new language's `state_mutation` rule, answer these in order:

1. Does the language have a declaration keyword or a type-before-name form? Then anchor the
   assignment to a statement start with a bare lvalue, so the declaration form cannot match, and
   add the compound operators and `++`/`--` with an operand touching them.
2. If it has no declaration syntax, the assignment statement *is* the write: count it, and say so
   in the rule's comment (corollary 1's fallback).
3. Add the in-place container/structure mutators with their receiver's dot (`\.push\(`, never
   `\bpush\b`), so a method *declaration* of the same name does not count as a call.
4. Never match a type or modifier that names mutable state, a read (`this.x` as an rvalue), a
   bind, a cast, or a token another rule already owns for the same construct. If a corpus
   measurement shows the rule firing on one, that is a bug in the rule, not a quirk of the corpus.
5. If the language has no assignment at all, pick the construct that performs a write (a store
   mnemonic, a data-modifying statement, a `SET`), add it to the fallback table above, and record
   any deliberate dual with another rule in keyword-rosetta's ledger as `keyword-overlap`.

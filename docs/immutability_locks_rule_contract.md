# The `immutability_locks` rule contract (#2772, rule half)

> **One hit is an added marker or lock call that prevents a binding or value
> from being changed after initialisation, where the language's default would
> permit it — a modifier or qualifier on an otherwise-mutable declaration, a
> restricted constant-declaration form distinct from the general-purpose
> binding, a runtime lock call, or an immutable reference pin. The language's
> ordinary binding keyword is a binding choice, not a lock, and a language
> whose bindings are immutable by default records the stated absence.**

Stated 2026-09-08 by the #2772 audit (roadmap Phase 3, epic #2812). Precedents:
`docs/api_rule_contract.md` (#2730) through `docs/cleanup_rule_contract.md`
(#2888). The machine-readable row is `gitgalaxy/standards/signal_contracts.py`;
the cross-language pins are
`tests/extraction/languages/test_immutability_locks_contract_2772.py`.

`immutability_locks` is an **annotation**-kind signal, unplanted (SPEC declines
to plant it) and ungated, but not harmless: its single consumer is
`_calc_state_flux`, where it is subtracted from `state_mutation` at half
weight. `risk_state_flux` is the corpus's worst gated metric, and its **low
tail was entirely this rule**: swift 2.98, kotlin/scala/typescript 4.20 against
a 7.75 median, on identical planted mutations, because the shell was written
with `let`/`val`/`const` instead of `var`.

## The disease

The old rules rewarded a *notation*, not a property. rust's immutable-by-
default `let` — the strongest guarantee in the corpus — was invisible (its
rule listed `const|static|immutable|readonly`), while swift's `let`, the same
guarantee spelled the same way, scored 11 because `let` happened to be in
swift's own list. The issue's resolution options were to add every default
form or drop them all; **this contract drops them all** — a hit must be a
deliberate act distinguishable from simply declaring a variable.

## Corollaries

**C1 · The ordinary binding keyword is not a lock.** swift `let`, kotlin and
scala `val`, javascript/typescript/zig `const`, dart `final` are how those
languages declare essentially every local. What counts is the *added* form:
kotlin `const val`, scala `final val` / a `collection.immutable` choice,
typescript `readonly` / `as const` / `Object.freeze(`, dart `const` (the
restricted compile-time form) / `@immutable`. go and rust `const`/`static`
items stay: they are restricted constant-declaration forms a general-purpose
binding cannot take.

**C2 · A lock on something other than data is not this signal.** abap `FINAL`
and `final class` / scala `sealed` lock a *hierarchy* against subclassing;
solidity `view`/`pure` and rust `const fn` lock a *function's behavior*;
html `disabled`/`inert`/`aria-disabled` gate *interactivity* (`readonly`,
which locks the field's value, stays); swift `Sendable` is a concurrency
marker (#2870's family).

**C3 · A name is not a lock.** shell's 88 crucible hits were dominated by
`readonly='readonly'` inside echo'd HTML strings — command position is now
required. cobol's `CONSTANT` fired inside `AN-CONSTANT`/`CONSTANT-VALUES`
hyphenated names — hyphen/quote guards, the #2888 shape. powershell's bare
`readonly` matched pattern strings — the `New-/Set-Variable -Option
Constant/ReadOnly` act is the lock. rust's `&'static` is a lifetime and
`*const` the ordinary raw-pointer spelling — neither locks a binding.

**C4 · Immutable-by-default is an absence, not a zero-matching rule.**
haskell (whose rule counted monadic `return` — 84 crucible hits, all noise),
swift and zig (whose `const` is the binding form for locals, imports and
containers alike) are now `None` with a ledgered contract-level absence — the
io/solidity precedent. Their guarantee is ambient; there is no site to count,
and `_calc_state_flux` already treats a missing signal as 0.

**C5 · Quoting is literal syntax.** scheme's rule counted every datum quote
(`'()`, `#'(...)` — 987 crucible hits). A quote is how scheme writes a
literal; the explicit lock call (`string->immutable-string`) stays.

## The audit — all 46 corpus languages

Corpus totals on the identical 12-probe shell (nothing is planted — every hit
is idiomatic residue) and the crucible. `a → b` is this change; a single
number means the rule was already inside the contract.

| language | corpus | crucible | verdict |
|---|---|---|---|
| `abap` | 1 → 0 | 5 → 4 | C2: `FINAL` locks a class; `CONSTANTS`/`READ-ONLY` stay |
| `ada` | 0 | — | in contract (`constant`) |
| `agc_assembly` | 0 | 0 | in contract (`FIXED MEMORY`) |
| `apex` | 0 | 0 | in contract (`final` modifier) |
| `assembly` | 0 | 36 | in contract (`equ`, `.rodata`) |
| `c` | 1 | 461 | in contract (`const`/`constexpr` qualifiers — opt-in against a mutable default) |
| `cobol` | 0 | 15 → 10 | C3: hyphen/quote guards; the 10 left are mid-string prose (recorded residue) |
| `cpp` | 1 | 3149 | in contract (qualifier family) |
| `csharp` | 0 | 216 | in contract (`readonly`/`init`/`Immutable*`) |
| `css` | 0 | 7302 | in contract — `!important` locks a declaration against cascade override, css's own lock form |
| `dart` | 2 → 0 | 1768 → 235 | C1: `final` is the ordinary binding choice; `const` (compile-time) and `@immutable` stay |
| `dockerfile` | 0 | 7 | in contract (digest pins, `--read-only`, `:ro`) |
| `embedded_python` | 0 | 0 | in contract (`Final`/`frozenset`, python twin) |
| `fortran` | 1 | 710 | in contract (`PARAMETER`, `INTENT(IN)`) |
| `go` | 0 | 53 | in contract (`const` is go's restricted constant form, not its binding form) |
| `groovy` | 0 | 90 | in contract (`final` modifier) |
| `haskell` | 0 → n/a | 84 → n/a | C4: immutable by default; the rule counted monadic `return`. **None + stated absence** |
| `html` | 1 | 76 → 8 | C2: `disabled`/`inert`/`aria-disabled` gate interactivity; `readonly` stays |
| `java` | 0 | 102 | in contract (`final` fields/locals) |
| `javascript` | 17 → 0 | 2002 → 0 | C1: `const` is the ordinary ES6+ binding; `Object.freeze/seal` are the lock calls (`readonly`/`final` were dead tokens) |
| `jcl` | n/a | — | no rule (unchanged) |
| `kotlin` | 6 → 0 | 39 → 0 | C1: `val` is the ordinary binding; `const val` stays |
| `livecode` | 0 | 97 | in contract (`constant`) |
| `lua` | 0 | 60 | in contract (`<const>` — the model opt-in attribute) |
| `m4` | n/a | — | `None` (macros are mutable by design; unchanged) |
| `makefile` | 0 | — | in contract (`override`) |
| `matlab` | 0 | 0 | in contract (`Constant` properties) |
| `objective-c` | 0 | 26 | in contract (`const` qualifier) |
| `perl` | 0 | 0 | in contract (`Readonly`/`Const::Fast`) |
| `php` | 1 | 54 | in contract (`const`/`readonly`/`final` — all opt-in in php) |
| `powershell` | 0 | 6 → 0 | C3: bare `readonly` matched pattern strings; the `-Option Constant/ReadOnly` act stays |
| `python` | 0 | 8 | in contract (`Final`/`frozenset`/`mappingproxy`) |
| `ruby` | 1 | 1 | in contract (`.freeze`) |
| `rust` | 0 | 153 → 40 | C3: `&'static` lifetimes and `*const` pointers are not locks; `const`/`static` items stay. **The inversion's other half: rust's `let` immutability is ambient, and now swift's reads the same way** |
| `scala` | 3 → 0 | 1151 → 2 | C1: `val` is the ordinary binding, `sealed` a hierarchy lock; `final val` and `immutable.*` stay |
| `scheme` | 0 | 987 → 0 | C5: datum quotes are literal syntax; `string->immutable-string` stays |
| `shell` | 0 | 88 → 65 | C3: command position — the 23 dropped were `readonly='readonly'` in echo'd HTML |
| `solidity` | 0 | 63 → 8 | C2: `view`/`pure` are purity annotations; `constant`/`immutable` stay |
| `sqlite` | 0 | 1 | unchanged (`STRICT`/`WITHOUT ROWID` are schema rigidity — questionable, recorded residue, no cell) |
| `swift` | 11 → n/a | 366 → n/a | C1/C4: `let` is the ordinary binding — the issue's headline cell. **None + stated absence** |
| `tcl` | 0 | 0 | in contract (write-trace guard) |
| `typescript` | 14 → 0 | 6041 → 2617 | C1: `const` dropped; `readonly` (the added property modifier), `as const` and freeze/seal stay |
| `yacc` | 0 | 4 | in contract (C prologue `const`) |
| `yaml` | 0 | 0 | in contract (action digest pins) |
| `zig` | 3 → n/a | 16468 → n/a | C1/C4: `const` is zig's binding form for everything. **None + stated absence** |

## What this does to `risk_state_flux`

The mitigation subtrahend is now ~uniform on the corpus (0–1 everywhere, from
idiomatic residue only), so the metric's low tail — swift −62%,
kotlin/scala/typescript −46%, javascript −25%, all on identical planted
mutations — collapses toward the median without touching the formula. The
**formula half of #2772 stays open for Phase 4**: a raw lock count subtracted
from a raw mutation count still compares quantities with different
denominators, and `_calc_state_flux` should compute a ratio if a ratio is the
intent. This document only makes the subtrahend mean the same thing in every
language.

## Recorded residue (no issue filed; no cell evidence)

- cobol mid-string `CONSTANT` prose (10 crucible hits) — same bound as
  #2888's cobol note.
- rust `starts_with("const ")` — a string literal containing the token
  (2 hits).
- sqlite `STRICT`/`WITHOUT ROWID` are schema rigidity, not data locks; left
  in place with 1 crucible hit and no cell.
- java/groovy/apex/php `final class` still counts under the `final`
  alternative (a hierarchy lock, C2) — the field/local use dominates the
  crucible mass and a class-form exclusion has no cell evidence to justify
  its blast radius.

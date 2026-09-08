# The `safety` rule contract (#2869)

> **A site that handles or forestalls a runtime failure at the value level —
> a guarded region's opener or its typed handler, a runtime assertion or
> validation call, a fallback or handled-absence form, an installed failure
> handler or watchdog, or a hardening instruction — in a form an ordinary
> identifier, type annotation or constructor cannot match.**

Stated 2026-09-07 by the #2869 audit (roadmap Phase 3, epic #2812).
Precedents: `docs/api_rule_contract.md` (#2730), `docs/args_rule_contract.md`
(#2773), `docs/state_mutation_rule_contract.md` (#2765),
`docs/branch_rule_contract.md` (#2822), `docs/io_rule_contract.md` (#2841),
`docs/test_rule_contract.md` (#2852), `docs/func_start_rule_contract.md` and
`docs/class_start_rule_contract.md` (#2856), `docs/globals_rule_contract.md`
(#2858). The machine-readable row is `gitgalaxy/standards/signal_contracts.py`
(`status="stated"`, `doc="docs/safety_rule_contract.md"`, `issue=2869`); the
cross-language pins are
`tests/extraction/languages/test_safety_contract_2869.py`.

`safety` is a **site**-kind signal. Its consumers: the high_risk×safety
proximity pair's silencer dampeners (`spatial_correlation.py:215` — safety
positions dampen amplified-RCE hits), `_calc_safety` (`WEIGHT_DEFENSE`,
fidelity-weighted), the safety_score formula (`verification·fid_test +
safety·fid_safety − bypassed·2.0`), `FIDELITY_SIGNALS`, the "Error &
Exception Exposure" report row, the `statistical_auditor` extraction-density
group. Before this contract it carried 2 of the report's 19 open-defect
cells (embedded_python, haskell — both `extraction` in the cause table);
after it, every corpus language reads **2**.

## Corollaries

**C1 · Value-level, not declaration-level.** A type name, constructor or
annotation is invisible to the rule; the runtime call, guarded arm or
handled-absence form is the shape that counts. haskell's bare data
constructors (`Just`, `Nothing`, `Right`, `Left`) drop — a constructor in an
ordinary expression is not a handled-absence site — leaving the value-level
forms `fromMaybe` and the total-match `Nothing ->` arm. rust drops the type
names (`Option`, `Result`) and the smart-pointer group (`Mutex`, `RwLock`,
`Arc`, `Rc`, `Box`, `RefCell`) and the bare constructors (`Ok`, `Err`,
`Some`, `None`), keeping the fallback family (`unwrap_or`, `unwrap_or_else`,
`unwrap_or_default`, `ok_or`, `ok_or_else`, `map_or`, `map_or_else`) and the
handled `None =>` arm. scala drops `Option`/`Some`/`None`/`Success`/`Failure`/
`Either`/`Left`/`Right`/`sealed`/`| Null`, keeping `require`/`assert`/
`assume`/`Try(`. java and groovy drop `Optional` (a type name); python drops
`dataclass`/`Field`/`TypeGuard`/`override` (declaration/type-level markers,
#2822's boundary restated on the safety side). This is #2822's `typescript
unknown|never|void` finding (`typescript-type-keywords-count-as-safety`,
already retired) generalized: a type annotation is not a defensive construct
any more than `IORef Int` in a signature is a write
(`docs/state_mutation_rule_contract.md` C2).

**C2 · Raising is not handling.** A construct that signals a failure outward
is not the same as one that handles or forestalls it. go drops
`errors.New` (constructs an error, does not handle one) while keeping
`errors.Is`/`errors.As`/`errors.Join` and `recover()`. lua drops `error(`
(raises) while keeping `pcall`/`xpcall`/`assert`. kotlin drops `error()`
(throws `IllegalStateException`) while keeping `require`/`requireNotNull`/
`check`/`checkNotNull`. livecode drops its `throw` alternative — the last
remaining half of the batch4 `livecode throw (safety+branch)` dual
(`batch4-dual-keyword-overlaps`) — retiring that entry's safety side.

**C3 · One verified owner.** A token that also belongs to another signal's
contract is that signal's alone unless the ledger names a genuine dual
(the fortran-COMMON shape, `docs/globals_rule_contract.md` C5). haskell's
`bracket`/`finally`/`onException` are cleanup's (`cleanup`:
`\b(hClose|close|free|bracket|finally|onException)\b`) — resolving
`haskell-finally-dual-cleanup-safety`, which still reproduced through
#2858. lua's `<close>`/`<toclose>` are cleanup's; `<const>` is
immutability's. go's `sync.Once`/`sync.WaitGroup` are concurrency-adjacent
and drop with the smart-pointer-style group; `context.Context` is a type
name (C1). cobol's `ON ERROR`/`AT END`/`INVALID KEY` stay branch's — the
`branch-contract-2822` disposition, verified unchanged, not touched here.

**C4 · Structure and reflection are not safety.** cobol's `END-IF`/
`END-PERFORM`/`END-EVALUATE`/`END-READ`/`END-WRITE`/`END-COMPUTE`/`END-CALL`
are block closers, not runtime guards — `DECLARATIVES`/`VALIDATE`/`CHECK`
are the value-level forms, hyphen-guarded in the #2622 shape
(`(?<!-)\b(...)\b(?!-)`, so `PARA-VALIDATE.` stays an identifier). assembly's
`enter`/`leave`/`.align`/`.p2align` are frame/alignment structure; the
CFI and pointer-authentication hardening instructions (`endbr64`,
`paciasp`, `autiasp`, `bti`, `retab`) stay — a hardening instruction is
exactly the sentence's last clause. python's bare `getattr` is
reflection_metaprogramming's (mass conserved: `hasattr` stays, `getattr`
alone is a read, not a guard).

**C5 · The ambiguity anchor.** An everyday word or an ordinary quoting form
fires only in its runtime-guard shape:

- **shell** — a bare `"$@"`/`"$*"` or any `"${...}"` quoted expansion is
  ordinary shell quoting, not a guard; the fallback operator
  (`${VAR:-default}`, `${VAR:=default}`, `${VAR:?msg}`) is the value-level
  form and stays, alongside `set -e`/`set -eu`/`set -o pipefail`, a `trap`
  on `ERR`/`EXIT`/`INT`/`TERM`, and `command -v`. Crucible 2,985 → 777.
- **objective-c** — bare `nil`/`Nil` is every null literal in the language,
  not a safety-specific site; `NSError` is a type name (C1). The ARC
  qualifiers (`__weak`, `__strong`, `__auto_type`) and the assertion macros
  (`NSAssert`, `NSParameterAssert`) stay — zeroing weak references are a
  runtime crash-prevention mechanism, kept under this corollary rather than
  retired with the bare-null noise. Crucible 31 → 0 (an honest zero: the
  corpus sample carried no ARC/assertion vocabulary, only bare `nil`).
- **kotlin** — a bare `fold` is an ordinary fold over a collection or
  string, not a `Result`-handling call; it drops with `sealed` and `Result`
  (C1) and `error()` (C2), leaving `require`/`requireNotNull`/`check`/
  `checkNotNull`/`is`/`!is`/`onSuccess`/`onFailure`/`runCatching`.

**C6 · Deliberate duals are kept, not retired.** A token verified as a
genuine two-construct site stays in both rules; only the disproven pairings
(C2's `throw`, C3's cleanup/concurrency tokens) leave.

| token | rules | why both are right | disposition |
|---|---|---|---|
| dockerfile `HEALTHCHECK` | func_start + safety | it is both the container's declared entry point and its installed watchdog | pre-existing, `docs/func_start_rule_contract.md`/`docs/class_start_rule_contract.md` (#2856) |
| rust `if let` | branch + safety | `if` is a decision point (branch's) and the `let`-pattern match is the handled-absence form (safety's) | pre-existing, `docs/branch_rule_contract.md` (#2822) |
| scala `Try(...)`/`Try {` | safety + immutability_locks | a guarded region opener is also `val`-adjacent immutable-binding vocabulary in scala's rule table | deferred to #2772 |
| go `errors.Is`/`errors.As`/`errors.Join` | safety + encapsulation | the comparison/wrap form is both a runtime guard and an encapsulation-boundary call | deferred to #2766 |

fortran's `COMMON` is a `globals` + `safety_bypasses` dual, not a safety one
(`docs/globals_rule_contract.md` C5 table) — noted here only because the
batch4 collective ledger entry (`batch4-dual-keyword-overlaps`) lists it
alongside the safety-side duals this contract resolves; it does not move.

## The two open cells

- **embedded_python 4 → 2.** a.py's single planted guard
  `assert isinstance(value, int)` is canonical at **2**: the bare `assert`
  and the bare `isinstance` both fire on one defensive statement — one
  guard, two value-level forms, correctly two hits (pinned in
  `test_safety_contract_2869.py`'s `COUNTS`). The excess was b.py's two bare
  `except:` — the `safety_bypasses` plant, the anti-safety marker — which
  also counted as safety because `except` sat in both rules. A swallowed
  exception is the opposite of a runtime guard; the twin-parity fix (C2 in
  `python.py`'s own edit, applied here for its embedded twin per #2852's
  lesson) anchors `except` to a named, non-`(Base)?Exception` type:
  `\bexcept\s+(?!(?:Base)?Exception\b)[A-Za-z_]\w*`. `except:` and
  `except Exception:` now fire zero; `except ValueError:` still fires one.
  One owner, mass conserved: `safety_bypasses` still reads the bare
  `except:` alone.
- **haskell 3 → 2.** a.hs's plant was only a **type signature**:
  `probeSafety :: Maybe Int -> Either Int Int` (body `= 0`, nothing
  defensive at the value level), which recorded 2 via the `Maybe`/`Either`
  type constructors — not a runtime defensive construct any more than a
  `typescript unknown`/`never` annotation is (C1). The plant is re-planted
  at the value level as a `fromMaybe`-shaped guard, and the type-signature
  form is the contract's negative pin
  (`probeSafety :: Maybe Int -> Either Int Int` — `COUNTS` == 0). c.hs's
  `finally` was cleanup's plant, double-counting as safety
  (`haskell-finally-dual-cleanup-safety`, still reproduced through #2858);
  C3 gives it one owner — cleanup — and the ledger dual is resolved, not
  merely re-verified.

## Measured with no red cell

The full sweep moved several languages' crucible counts with no open-defect
cell attached — narrower, more honest rules the corpus corroborates rather
than contradicts:

- **cobol** `END-*` closers out: 2,500 → 68, leaving `DECLARATIVES`/
  `VALIDATE`/`CHECK` (the #2622 hyphen-guard shape, C4).
- **shell** quoted-expansion out: 2,985 → 777, keeping `set`/`trap`/
  `command -v`/`${VAR:-fallback}` (C5).
- **rust** type-and-constructor tokens out: 3,182 → 316, leaving
  `if-let`/`while-let`/`let-else`/the `unwrap_or` family/`None =>` arms
  (C1).
- **lua** `error`/`type`/`pairs`-class introspection out: 4,438 → 3,660
  (C2/C4).
- **scala** 321 → 1, the type/constructor group leaving almost the entire
  count (C1) — the crucible's one remaining hit is a genuine `require(`.
- **python** typed-except plus dropped declaration-level tokens: 3,304 →
  2,999.
- **livecode** `throw` leaving `panics_and_aborts`: 295 → 173 (C2).
- **objective-c** bare `nil` out: 31 → 0, and **assembly** frame mechanics
  out: 54 → 0 — both now honest zeros on the sampled corpus files rather
  than noise-inflated counts, the same shape as `docs/globals_rule_contract.md`'s
  makefile/yaml rows (a narrow, correctly-scoped rule reading zero on a
  sample that happens to carry none of its vocabulary is not a defect).

## The 46-language audit

`rule_probe.py safety all --samples 8` before → after. crucible = hits
across the control corpus; keyword-rosetta = hits across the
keyword-rosetta shell files (median plant: 2). Languages not listed: rule
`None` by stated absence or no safety morphology declared (batch, blp, csv,
glsl, hlo, json, markdown, mlir, nix, pbtxt, plaintext, proto, td, xml).

| language | crucible | keyword-rosetta |
|---|---|---|
| `abap` | 86 | 2 |
| `ada` | -- | 2 |
| `agc_assembly` | 70 | 2 |
| `apex` | 19 | 2 |
| `assembly` | 54 -> 0 | 2 |
| `batch` | rule is `None` | n/a |
| `blp` | rule is `None` | n/a |
| `c` | 1363 | 2 |
| `cobol` | 2500 -> 68 | 2 |
| `cpp` | 278 | 2 |
| `csharp` | 718 | 2 |
| `css` | 515 | 2 |
| `csv` | rule is `None` | n/a |
| `dart` | 4760 | 2 |
| `dockerfile` | 9 | 2 |
| `embedded_python` | 247 -> 155 | 4 -> 2 |
| `fortran` | 1700 | 2 |
| `glsl` | rule is `None` | n/a |
| `go` | 268 -> 195 | 2 |
| `groovy` | 88 -> 83 | 2 |
| `haskell` | 159 -> 22 | 3 -> 2 |
| `hlo` | rule is `None` | n/a |
| `html` | 109 | 2 |
| `java` | 87 -> 85 | 2 |
| `javascript` | 2003 | 2 |
| `jcl` | 33 | 2 |
| `json` | rule is `None` | n/a |
| `kotlin` | 7 | 2 |
| `livecode` | 295 -> 173 | 2 |
| `lua` | 4438 -> 3660 | 2 |
| `m4` | 116 | 2 |
| `makefile` | -- | 2 |
| `markdown` | rule is `None` | n/a |
| `matlab` | 296 | 2 |
| `mlir` | rule is `None` | n/a |
| `nix` | rule is `None` | n/a |
| `objective-c` | 31 -> 0 | 2 |
| `pbtxt` | rule is `None` | n/a |
| `perl` | 160 | 2 |
| `php` | 1401 | 2 |
| `plaintext` | rule is `None` | n/a |
| `powershell` | 575 | 2 |
| `proto` | rule is `None` | n/a |
| `python` | 3304 -> 2999 | 2 |
| `ruby` | 10 | 2 |
| `rust` | 3182 -> 316 | 2 |
| `scala` | 321 -> 1 | 2 |
| `scheme` | 125 | 2 |
| `shell` | 2985 -> 777 | 2 |
| `solidity` | 33 | 2 |
| `sqlite` | 301 | 2 |
| `swift` | 152 | 2 |
| `tcl` | 406 | 2 |
| `td` | rule is `None` | n/a |
| `typescript` | 399 | 2 |
| `xml` | rule is `None` | n/a |
| `yacc` | 1 | 2 |
| `yaml` | 0 | 2 |
| `zig` | 14039 | 2 |

## Deliberate duals kept

- **dockerfile `HEALTHCHECK`** — func_start + safety, pre-existing
  (`docs/func_start_rule_contract.md`/`docs/class_start_rule_contract.md`,
  #2856): it is simultaneously the container's declared entry point and its
  installed watchdog.
- **rust `if let`** — branch + safety, pre-existing
  (`docs/branch_rule_contract.md`, #2822): `if` opens the decision, the
  `let`-pattern is the handled-absence arm.
- **scala `Try`** — safety + immutability_locks, deferred to #2772: the
  one-owner call belongs to the immutability rule's half of the audit.
- **go `errors.Is`** — safety + encapsulation, deferred to #2766: the
  one-owner call belongs to the encapsulation-formula audit.
- **fortran `COMMON`** — globals + safety_bypasses (not a safety dual;
  cross-referenced here only because `batch4-dual-keyword-overlaps` lists
  it beside the safety-side entries this contract resolves;
  `docs/globals_rule_contract.md` C5 is its home).

## Known limits

An import line that names a guard fires the token rule the same as a
value-level use — `import Data.Maybe (fromMaybe)` fires haskell's `safety`
once on `fromMaybe`, `from pydantic import BaseModel` fires python's
`safety` once on `BaseModel`. This is the same cross-signal import
morphology `docs/test_rule_contract.md` C4 already names for test-framework
mentions (`import unittest` splits into `import`'s hit on the keyword and
`test`'s hit on the framework name) — pre-existing, not introduced by this
contract, and not worth gating: the import statement is genuine evidence
the file has the guard vocabulary in scope.

livecode's lens has a block-structure sensitivity found only by one-file
scans during this audit: `catch tError` is safe to re-plant with (a
`catch` line only ends a `try`/`catch`/`end try` region, matching the
language's existing structure), but a bare `try` line on its own shifts the
lens's block-structure accounting and manufactures a phantom `arch_api` hit
downstream (`api_orphan_credit`) — invisible on the aggregate corpus,
visible only when scanning the changed file in isolation. The corpus
re-plant for livecode uses `catch tError`, not `try`, for this reason.

## Deferred by design

Forms measured adjacent to this contract with no open-defect cell to move
and no evidence to act on now are filed with #2870: cpp's
`std::atomic`/RAII-pointer group boundary, dart's declaration-modifier
guards (`late`/`required`/`@immutable`/`@mustCallSuper`), csharp's
`required`/`nameof`, javascript/typescript's `===`/`!==` "type-safe
equality" morphology, swift's `Sendable` type marker, objective-c's ARC
qualifier boundary, rust's `?` operator (propagation, not handling — an
absence by design), scala's `Try`/immutability_locks and go's
`errors.Is`/encapsulation one-owner questions (both listed above as kept
duals, tracked to their respective issues), fortran's declaration-time
strictness versus its uncounted `IOSTAT=`/`STAT=` runtime forms, makefile's
zero-crucible narrowness, and python's dropped `Field(` call-form surface.
None of these move a corpus cell today; #2870 records them so the next
audit does not re-derive the same list. Parent: #2812 Phase 3.

## Bless scope

Corpus PR pairs with #2869: the engine PR carries the 15 rule edits above
plus the strict-pin flips in each edited language's
`tests/extraction/languages/test_<lang>_strict.py`; the corpus PR carries
the re-plants named in "The two open cells" (embedded_python's twin-parity
`except`, haskell's value-level `fromMaybe` guard) and livecode's
`catch tError` re-plant, with both open-defect ledger entries
(`haskell-finally-dual-cleanup-safety`, and embedded_python's `safety`/
`safety_bypasses` `except` overlap) resolved. Golden-master movement is
confined to the `safety` signal and the formulas that read it (the
high_risk×safety proximity dampeners, `_calc_safety`, `safety_score`);
watch the layer boundary named in the original issue: `safety_bypasses`
(planted in the same files) must not move.

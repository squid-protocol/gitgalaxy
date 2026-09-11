# The `test` rule contract (#2852)

> **One hit is a site that engages a testing framework — a test-case or
> fixture declaration, a framework assertion or expectation call, or the
> framework itself named — in a form an ordinary identifier cannot match;
> the language's own runtime guard is safety's hit, never test's.**

Stated 2026-09-07 by the #2852 audit (roadmap Phase 3, epic #2812).
Precedents: `docs/api_rule_contract.md` (#2730), `docs/args_rule_contract.md`
(#2773), `docs/state_mutation_rule_contract.md` (#2765),
`docs/branch_rule_contract.md` (#2822), `docs/io_rule_contract.md` (#2841).
The machine-readable row is `gitgalaxy/standards/signal_contracts.py`; the
cross-language pins are `tests/extraction/languages/test_test_contract_2852.py`.

`test` is a **site**-kind signal. Its consumers: the `risk_verification`
formula (`signal_processor.py` reads the hit count as `verification`, weighted
by the fidelity table), the `FIDELITY_SIGNALS` tuple, the "Testing Exposure"
display row, the `statistical_auditor` extraction-density group, and
`network_risk_sensor`'s per-function `test_hits`. (`detector.py`'s
name-verb heuristic tags a function whose *name* contains test/assert/mock —
that is a name heuristic, not this rule.) Before this contract it carried 3 of
the corpus's 34 open-defect cells (c, embedded_python, perl — 7% of its
comparable cells); after it, every corpus language reads **2**.

## Corollaries

**C1 · The runtime guard is safety's.** The language's built-in production
assertion guards the running program — it fires in deployment, not under a
harness — so safety's contract claims it, and in every affected language the
safety rule already owned the token (mass conserved): C's `assert(` (assert.h),
python's and embedded_python's `assert` statement, Lua's builtin `assert(`.
This is #2626's python resolution stated as a rule for language 47:
embedded_python still carried the bare `assert` token #2626 removed from
python (the twin was missed), and c's rule ended `|\bassert\s*\(`. A
*framework's* assertion form is test's: `CU_ASSERT`, `ASSERT_*`/`EXPECT_*`
(the uppercase macro is the framework form — CPython's own
`ASSERT_DICT_LOCKED()` runtime macros are indistinguishable by surface and
accepted), `assertEquals`, `XCTAssert…`, `assert_eq!`, and luassert's matcher
chain `assert.<chain>` (`assert.are.equal`, `assert.True`), which is exactly
the shape that separates busted's assertion from Lua's guard: the dot, not
the paren. Lua's crucible count fell 3471 → 134 on this line alone, and the
134 that remain are all `assert.are_*`/`assert.error_*` chains.

**C2 · One statement is one hit; a module qualifier is not a separate hit
from the call it qualifies.** perl's `Test::More::ok($kit)` fired twice —
once for the framework name `Test::More`, once for the call form `ok(` — so
the corpus read 3 against a planted 2. The module names now carry `(?!::)`:
a qualified call counts once through its call form, a bare mention
(`use Test::More;`) still counts once as the framework named (C4).

**C3 · The ambiguity anchor** (io C1). An everyday word fires only anchored
to its framework form; the crucible measured each of these misfiring:

- **dart** — bare `test` matched a predicate parameter (`if (test(element))`)
  and bare `group` a loop variable (`for (final group in
  siblingMergeGroups)`); a test-case declaration is now the call with its
  description string (`test('adds', …)`, `group('kit', …)`), the corpus probe
  re-planted to the honest form. Crucible 38 → 2.
- **php** — bare `test` matched Twig's ordinary `->test(` method and bare
  `mock` the `$mock` variable; everyday words now anchor to their call form
  (`test('adds', function`, `mock(User::class)`, `$this->expects(`), with
  `(?<!->)` on `test`/`it` because Pest's forms are bare calls and a method
  named `test` is not a test case. Crucible 53 → 7, the remainder Mockery
  calls.
- **cobol** — `-` is a regex word boundary, so `TEST-CASE` matched *inside*
  `UT-TEST-CASE-COUNT` — cblunit's own counter variables, 51 hits of an
  identifier, the exact #2622 hyphen shape. The rule now carries
  `(?<!-)…(?!-)` guards. Crucible 51 → 0 (the framework's counters were the
  only hits; a real `ASSERT X = Y` statement still fires).

An unambiguous framework name (`pytest`, `unittest`, `PHPUnit`, `busted`,
`luassert`, `Test::More`, `testWidgets`, `XCTest`) may fire bare — the
crucible shows no identifier collisions on them.

**C4 · Naming the framework counts, once.** A testing-framework name is test
evidence wherever it appears — the planted position in python and
embedded_python is a bare mention (`suite = unittest`), and it stands. Where
the mention sits inside an inclusion statement (`import unittest`,
`use Test::More`), the include keyword is import's hit and the framework name
test's — different tokens on one line, a deliberate overlapping taxonomy
(the fortran COMMON shape), not a dual to retire.

**C5 · Stated absence.** A language records `test: None` when it has no
per-case idiom a framework executes: yacc (ledger
`yacc-test-no-native-testing-concept` — `%expect N` is a one-shot declarative
pragma already claimed for file routing), jcl ("test has no JCL concept",
`jcl-2610-rebaseline-residual-morphology`), markdown (lit plane,
`markdown-lit-plane-morphology`). The absence answer and the rule answer
cannot coexist in one language; absence needs crucible evidence, not merely
an unplanted corpus.

## Deliberate duals and deferred residue

- **groovy Spock labels** (`when:`/`then:`/`expect:` line-anchored) are the
  framework form of a block label — 948 crucible hits, all Spock specs; kept.
- **assembly's `testcase` macro table** — each `testcase {…}` data row
  declares one case for the harness that expands it; 275 hits, kept.
- **powershell Pester** (`Should`, `BeforeAll`) — framework vocabulary; kept.
- **dart `when (`** — dart 3's switch-case guard clause collides with
  mockito's `when(` (1 crucible hit); accepted, the guard form is rare and
  mockito's is planted nowhere.
- **php `public static function spy()`** — Mockery declaring its own `spy`
  method fires the call-anchored form once; accepted (it is framework
  source).
- **Bare-word menus, resolved in #2853.** ruby's `before`/`after`/`let`/
  `subject`/`context`, javascript's bare `describe`/`expect`/`assert`, java's
  and groovy's `assert…(` runtime-statement exposure, and assembly's `(?i)`
  prose vocabulary — all deferred at #2852 as "conforming-by-absence-of-
  evidence" — were validated once the v1.2.0 corpus grew files for these
  languages (ruby, javascript, groovy 312, assembly 239; java present but with
  no test sites). C3 anchors the everyday word to its framework form: ruby's
  words to their rspec/minitest call/block (`describe "x" do`, `before(:each)`,
  `let(:u)`, `assert_equal`), javascript's `describe`/`expect` to `\s*\(` and
  bare `assert` to the chai chain `assert.<x>`, assembly's menu dropped in
  favour of the `testcase` macro. C1 hands the runtime guard to safety: java's
  and groovy's `assert\w*\(` → `assert\w{1,40}\(` (the parenthesized power-
  assert/JLS statement is safety's; `assertEquals(` stays; also closes a latent
  `\w+\(` backtracking exposure), and js's bare `assert(`. Pipeline reprice:
  javascript 5 → 0, ruby 2 → 0, assembly 284 → 275, groovy 954 → 954
  (unchanged — no bare power-assert in corpus), java 0 → 0. **Residual:**
  non-black/unspaced forms and languages still thin on test files (java has no
  `@Test` sites in its springboot corpus) are validated by the contract test's
  positive/negative pairs rather than a corpus cell.

## The 46-language audit

`rule_probe.py test all --samples 8` before → after. crucible = hits across
the control corpus; rosetta = hits across the 4 keyword-rosetta shell files
(median plant: 2). Languages not listed: rule `None` by stated absence (yacc)
or no test morphology declared (batch, blp, csv, glsl, hlo, json, mlir, nix,
pbtxt, plaintext, proto, td, xml); jcl and markdown are n/a by intended
morphology.

| language | crucible | rosetta | verdict |
|---|---|---|---|
| abap | 0 | 2 | conforms (`FOR TESTING`/`CL_ABAP_UNIT_ASSERT` anchored) |
| ada | — | 2 | conforms (`AUnit`, `Assert(` — Ada has no runtime assert keyword) |
| agc_assembly | 13 | 2 | conforms (SELFCHECK/ROPECHK are its self-test ops) |
| apex | 116 | 2 | conforms (@isTest/System.assert anchored forms) |
| assembly | 284 → 275 | 2 | validated (#2853): kept the `testcase` macro + `it(`; dropped the `(?i)` prose menu and the linker `ASSERT(` guard (safety's) |
| c | 1052 → 97 | 3 → 2 | **C1**: `assert(` → safety's; uppercase `ASSERT_*` macros stay (framework form) |
| cobol | 51 → 0 | 2 | **C3**: hyphen guards; `UT-TEST-CASE-COUNT` was an identifier (#2622 shape) |
| cpp | 0 | 2 | conforms (framework macros only, no bare assert() alternative) |
| csharp | 0 | 2 | conforms (attribute-anchored `[Test]`/`[Fact]`) |
| css | 0 | 2 | conforms (`data-testid` attribute form) |
| dart | 38 → 2 | 2 | **C3**: `test`/`group` anchored to description-string call; probe re-planted |
| dockerfile | 0 | 2 | conforms (command forms `npm test`/`pytest`) |
| embedded_python | 0 | 3 → 2 | **C1**: bare `assert` removed (#2626 applied to the twin) |
| fortran | 0 | 2 | conforms (pFUnit `@test`/`@assertEqual` directive-anchored) |
| go | 2 | 2 | conforms (`TestX`/`t.Run`/`assert.X(` anchored) |
| groovy | 954 → 954 | 2 | validated (#2853): C1 `assert\w{1,40}\(` drops the parenthesized power-assert (none in corpus); Spock labels + `assertEquals(` kept |
| haskell | 0 | 2 | conforms (hspec/QuickCheck names, `prop_` prefix) |
| html | 0 | 2 | conforms (`data-testid=` attribute form) |
| java | 0 → 0 | 2 | validated (#2853): C1 `assert…{1,40}\(` keeps `assertEquals(`, drops the JLS runtime `assert(cond)`; no test sites in the springboot corpus, so pinned by the contract test |
| javascript | 5 → 0 | 2 | validated (#2853): C3 anchors `describe`/`expect` to `\s*\(`, bare `assert` to the chai chain `assert.`; the 5 were comment/string prose, now gone |
| kotlin | 1 | 2 | conforms (annotation + call-anchored forms) |
| livecode | 0 | 2 | conforms (`command test*`/`pass test` statement forms) |
| lua | 3471 → 134 | 2 | **C1**: bare `assert` → safety's; luassert chain `assert.<chain>` added (the 134 are all chains) |
| m4 | 0 | 2 | conforms (autotest `AT_*` macros) |
| makefile | 0 | 2 | conforms (command forms) |
| matlab | 0 | 2 | conforms (`matlab.unittest`/`verifyEqual` names) |
| objective-c | 0 | 2 | conforms (`XCTAssert*` family) |
| perl | 0 | 3 → 2 | **C2**: `(?!::)` on module names; `Test::More::ok(` counts once |
| php | 53 → 7 | 2 | **C3**: everyday words call-anchored, `(?<!->)` on `test`/`it`; remainder Mockery calls |
| powershell | 203 | 2 | conforms (Pester `Should`/`Describe`/`It` forms) |
| python | 1221 | 2 | conforms (#2626 already removed `assert`; framework names + `def test_`) |
| ruby | 2 → 0 | 2 | validated (#2853): C3 anchors describe/context/it/before/after/let/subject/expect and minitest assert_*/refute_* to their framework forms; prose (`# context`, `assertions`) no longer fires |
| rust | 464 | 2 | conforms (`#[test]`/`assert!` macros — the macro *is* the framework form) |
| scala | 0 | 2 | conforms (framework names + `it should`) |
| scheme | 0 | 2 | conforms (paren-anchored srfi-64 forms) |
| shell | 59 | 2 | conforms (bats `@test`/shunit2 `assert_eq` forms) |
| solidity | 0 | 2 | conforms (Foundry `test*`/`assertEq` prefix forms) |
| sqlite | 75 | 2 | conforms (`.testcase`/`PRAGMA integrity_check` statement forms) |
| swift | 0 | 2 | conforms (`XCTest` family + `@Test`/`#expect`) |
| tcl | 68 | 2 | conforms (`do_test`/`tcltest::` command forms) |
| typescript | 310 | 2 | conforms (call-anchored, `(?<!\.)` guards already present) |
| yaml | 0 | 2 | conforms (workflow command forms) |
| zig | 105 | 2 | conforms (`test "…"` block declaration) |

## Ledger dispositions this contract settles

- `assert-overlaps-safety-and-test` — **resolved** for its two remaining
  languages (c, perl); python was resolved by #2626. c's dual is retired by
  C1, perl's double-fire by C2. The entry closes.
- `batch4-dual-keyword-overlaps` — loses its test half for embedded_python
  (the bare `assert` token); the other itemized duals are untouched.
- `yacc-test-no-native-testing-concept` — unchanged, now cited as the C5
  precedent.
- `jcl-2610-rebaseline-residual-morphology` / `markdown-lit-plane-morphology`
  — unchanged (n/a cells, not defects).

## Bless scope

Golden-master movement is confined to the `test` signal and the formulas that
read it (`risk_verification`, the fidelity-weighted verification term);
newly parsed/excluded: none. The large crucible deltas (c −955, lua −3337,
php −46, cobol −51, dart −36) are the C1/C3 misfires leaving the count.

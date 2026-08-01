# How to Harden a Language's Extraction Coverage

This is the companion doc to `gitgalaxy/standards/how_to_add_a_language.md`, scoped specifically to
the four extraction gauntlets in this directory (`test_function_extraction_strict.py`,
`test_args_extraction_strict.py`, `test_class_extraction_strict.py`,
`test_dependency_extraction_strict.py`). Read `readme.md` first for the 3-tier
valid/invalid/pathological framework these gauntlets already use — this doc is about making that
framework *thorough* per language rather than a thin smoke test, and about the process for doing
that language-by-language across an epic.

**Why this doc exists:** an audit of the four existing gauntlet files (2026-07-30) found them
"structurally excellent, but dangerously sparse" — most languages carry only 2-3 `valid` cases,
2-3 `invalid` cases, and exactly **one** `pathological` case. For an AST-free engine where every
downstream metric (RAG mapping, 3D visualization, risk scoring) depends on these regexes parsing
correctly, one pathological case per language is a smoke test, not a gauntlet. Worse, a first pass
at deepening just 8 languages' function-extraction coverage (2026-07-30) surfaced **real,
previously-undetected bugs** in under an hour of empirical testing — not test-authoring gaps, actual
engine defects:

- `javascript`/`typescript` `func_start` false-positive-matches a single-line string literal
  containing function-shaped text (`let query = "function Foo() {";`). Root cause: `detector.py`'s
  `_slice_by_braces` computes `func_start.finditer(code)` against the **raw** code, before building
  the string/comment-shielded `safe_code` used later for the brace search — this affects every
  language routed through `_slice_by_braces` (Mode B), not just JS/TS.
- `typescript` `func_start` false-positive-matches a `type Foo = (a: T) => R;` type alias as if it
  were a real arrow-function assignment (no exclusion for a preceding `type` keyword).
- `java` `func_start` breaks on one-level-nested generic bounds (`<T, U extends Comparable<U>>`) —
  the same "Rule 11" nested-delimiter bug class already fixed elsewhere in the strict-parsing epic
  (`gitgalaxy/standards/how_to_add_a_language.md`'s Rule 11), just never checked for this rule.
- `go` `func_start` doesn't recognize Go 1.18+ generics (`func Foo[T constraints.Ordered](...)`) at
  all — mainstream, five-year-old Go syntax, currently invisible to the engine.

None of these were hypothetical. Expect more like them. This doc exists so that finding them is
systematic instead of accidental.

## Scope: the four pillars, one language at a time

Each of the four gauntlets validates a different rule:

| Gauntlet | Rule validated | What it proves |
|---|---|---|
| `test_function_extraction_strict.py` | `func_start` | Exact function/method name isolation |
| `test_args_extraction_strict.py` | `args` | Parameter-block capture without ReDoS |
| `test_class_extraction_strict.py` | `class_start` | Exact class/struct/interface/trait name isolation |
| `test_dependency_extraction_strict.py` | `_dependency_capture` | Exact import/dependency path extraction |

**Work language-by-language, not gauntlet-by-gauntlet.** Pick one language, load its full `rules`
dict from `language_standards.py` into context once, and harden all four gauntlets for it in the
same sitting before moving to the next language. This is a deliberate token-efficiency choice: the
alternative (finish all languages' `func_start` cases, then start over for `args`) means
re-deriving the same language's regex quirks from scratch four times instead of once.

## Proposed file layout: per-language files, not four giant dicts

The four existing files are flat dicts keyed by language (`EXTRACTION_CASES["python"] = {...}`)
inside one shared module per gauntlet. That layout was fine at 2-3 cases per language; it will not
survive 10-15 pathological cases × dozens of invalid/valid cases × ~40 languages — one file would
balloon into a many-thousand-line dict no single edit could safely navigate (see
`test_language_standards_strict.py`, already 14,000+ lines, for what that endgame looks like for a
*single* file covering one concern).

**New layout, one file per language:**

```
tests/extraction/languages/
    test_python.py
    test_javascript.py
    test_typescript.py
    test_java.py
    test_csharp.py
    ...
```

Each per-language file owns all four concerns for that language in one place — four dicts
(`FUNCTION_CASES`, `ARGS_CASES`, `CLASS_CASES`, `DEPENDENCY_CASES`) plus four thin test functions
that reuse the *same* parametrization/assertion logic the current gauntlets use (lift
`test_positive_function_extraction`/`test_negative_function_extraction`/
`test_pathological_function_extraction` and their args/class/dependency counterparts into a shared
`tests/extraction/_extraction_harness.py` helper module so each per-language file is just data plus
a few `pytest.mark.parametrize` calls, not four copies of the same loop).

**Migration is a cutover, not a duplication.** When a language's issue is worked, its entry is
*removed* from the four old monolithic dicts and its (now much larger) case set lives only in the
new `tests/extraction/languages/test_<lang>.py`. Don't test the same language in both places. Once
every language has migrated, the four old files should be near-empty (or deleted, with `readme.md`
updated to point at the new layout) — but expect this to take the whole epic to complete; the old
files stay live and authoritative for not-yet-migrated languages in the meantime.

## Per-language checklist

For each of the four rules on a given language, cover all three tiers below. Not every language
will have something in every row (e.g. `dependency` cases don't apply to `cobol` sections) — a row
that doesn't apply is a `None`/absence, not something to force.

### `valid` — the Iron Wall

- The modern/idiomatic form (already covered by existing cases — keep these).
- **At least one case per major syntax era the language has gone through**, where relevant. This is
  the single biggest gap in the current suite — it only tests the *current* idiom, never the
  decade(s) of legacy code these regexes will actually be run against in real repos:
  - Python: `def`, `async def`, and (if the language's `class_start`/`args` support it) old-style
    `%`-formatting-era code, pre-3.5 code with no type hints, PEP 695 (3.12+) generic syntax
    (`def Foo[T](x: T) -> T:`).
  - JavaScript: ES5 `function` declarations/expressions, ES6 arrow functions, ES6 class methods,
    ES6+ object-literal method shorthand, `async`/`await`, generators (`function*`).
  - TypeScript: everything JS has, plus generics, decorators, `abstract`/`readonly`/`public`
    modifiers, overloads.
  - Java: pre-8 (no lambdas/generics-heavy code), 8+ (lambdas, default/static interface methods),
    annotations-heavy modern code, records (Java 16+), sealed classes (17+).
  - C#: pre-6 (no expression bodies), 6+ expression-bodied members, `async`/`await`, records (C#
    9+), top-level statements (C# 9+), generic constraints (`where T : ...`).
  - C++: C++03/11/14/17/20/23-era feature usage where the rule cares (`auto` return types, trailing
    return types `-> T`, concepts/`requires` clauses, structured bindings if relevant to
    args/class).
  - Go: pre-1.18 (no generics) and 1.18+ (generics with constraints).
  - Rust: editions where relevant (2015/2018/2021), const generics, `impl Trait` in argument and
    return position, async fn.
  - Ruby: `def`, `define_method`, `class << self` singleton methods.
  - PHP: PHP 5-era vs PHP 7/8 (attributes, union types, readonly properties, enums).
- **Testing-framework-shaped functions that ARE real functions and must still match.** These are
  extremely common in real repos and are exactly the kind of "looks unusual but is 100% valid"
  code an AST-free engine needs to get right:
  - Python: `pytest` fixtures/parametrized tests (`@pytest.mark.parametrize(...)\ndef
    test_foo(...):`), `unittest.TestCase` methods.
  - JavaScript/TypeScript: Jest/Mocha/Jasmine `describe`/`it`/`test` blocks (these are function
    *calls* whose last argument is a function — verify the engine's existing behavior here is
    intentional, not accidental).
  - Java: JUnit 4/5 `@Test`-annotated methods, parameterized tests.
  - C#: xUnit/NUnit `[Fact]`/`[Theory]`/`[Test]`-annotated methods (some existing coverage already;
    expand it).
  - Ruby: RSpec `describe`/`it`/`context` blocks.

### `invalid` — Ghost Prevention (false-positive lookalikes)

Go beyond "a different keyword entirely" (the current cases are mostly this). Real lookalikes:

- **String literals containing function/class-shaped text on the same line**
  (`let query = "function Foo() {";`, `String s = "public void Foo() {";`). This is the class of
  bug that broke JS/TS above — expect it to be real for any language whose rule isn't `^`-anchored
  to true line-start, and worth checking even for anchored rules (a triple-quoted/heredoc string
  can put lookalike text at true line-start).
- **Type-level lookalikes**: TypeScript `type Foo = (...) => R;`, C++ `using Foo = std::function<...>;`,
  Rust `type Foo = fn(...) -> R;` — these describe a function *shape* without being a real function.
- **Assignment-in-condition / pointer-math lookalikes**: `if ((x = TargetFunc()) != null)`,
  `if (int* p = &TargetFunc)`.
- **Macro-expansion lookalikes**: `#define TargetFunc(a, b) ((a) + (b))` (C/C++), attribute-macro
  calls that resemble declarations.
- **Member-initializer-list lookalikes** (C++): `MyClass::MyClass() : TargetFunc(0), b_(1) {` — here
  `TargetFunc` is a field being initialized, not a function.
- **Generic-typed variable declarations**: `Dictionary<string, Func<int,int>> TargetFunc = new();`
  (C#), `Map.Entry<String,Integer> TargetFunc = getEntry();` (Java) — the generic soup can fool a
  rule that isn't careful about what follows the closing `>`.

### `pathological` — the Frankenstein Test

The existing single case per language (usually: stack some modifiers, add vertical whitespace) is a
reasonable *floor*. Push further — aim for 10-15 per major language covering, independently:

- Extreme annotation/decorator/attribute stacking (5+, not the current 1-2), including ones with
  complex nested-paren arguments (`@Route("api/v1", methods=["GET","POST"])`).
- Deeply nested generics/templates (2+ levels), including the exact "Rule 11" flat-`[^>]*`-style
  bug shape from `how_to_add_a_language.md` — this is worth checking explicitly for every language
  with generics/templates, not assuming it's already been swept.
- Destructured/complex parameter patterns where the language supports them (JS/TS object/array
  destructuring with defaults, Python `*args`/`**kwargs` mixed with keyword-only params).
- Multi-line signatures split at every plausible boundary (between modifiers, between generic
  params, inside the parameter list, before the return type).
- Language-specific historical oddities (COBOL margin rules, Fortran fixed-form column rules,
  assembly label conventions) already have some coverage — extend rather than replace.

## Verification discipline (non-negotiable)

1. **Empirically verify every candidate case against the real compiled regex before adding it to
   the test file.** Use `tests/extraction/tools/verify_candidates.py` — `check_case()`/`check_many()`
   from a scratch script, or the CLI for a single ad-hoc check — instead of rewriting the same
   checker function from scratch (every language pass before this tool existed did exactly that).
   Don't guess whether a payload matches. A case that's wrong about the engine's actual behavior is
   worse than no case: it either bakes in a bug as "expected" or fails for the wrong reason.
2. **A failing verification is a finding, not necessarily a bug to fix immediately.** Triage each
   one: is the payload realistic (a fair test), or did the payload accidentally test something the
   rule was never meant to handle (e.g. a single-line object-literal method shorthand when the rule
   is `^`-anchored and the real-world form is always multi-line; a nested-generic depth beyond what
   the established one-level-nesting idiom claims to support)? Rewrite unrealistic payloads before
   concluding there's a bug, and don't force a fix to reach a depth/case the architecture was never
   designed to handle — see recurring-bug-class notes on generic nesting and bare-call ambiguity
   below for two concrete examples of "investigated, documented, deliberately not fixed."
3. **Real bugs get fixed with the full existing discipline**, not just documented:
   - ReDoS scaling check if the fix touches a quantifier — `verify_candidates.py`'s
     `check_redos_scaling()` for quick iteration; a real assertion (`assert_redos_immune`, already
     available from `_extraction_harness.py`) once the pattern is finalized.
   - `python tests/tools/audit_check.py` (add `--regenerate` if it reports pure line-shifts — see its
     own docstring) instead of running `ruff format`/`ruff_audit.py --ci`/`mypy_audit.py --ci`/
     `dead_key_audit.py --ci` as four separate commands and manually eyeballing each diff.
   - Full relevant test suites.
   - If the fix touches `language_standards.py`, `detector.py`, or `prism.py`:
     `python tests/tools/crucible_check.py` (never hand-build venvs — see `CLAUDE.md`'s Differential
     Scan section for why a stale/shared venv silently scans the wrong checkout). A real diff must be
     confirmed **confined to the language(s) you actually changed** before blessing — pull the unique
     language names out of the diff output and check nothing else shows up — not just eyeballed for
     "the magnitude looks plausible." Only then `python tests/tools/crucible_check.py --update --yes`
     to regenerate both golden masters in one call (it builds/refreshes both venvs itself; you do not
     need to `source .../bin/activate` anything by hand).
4. **A fix that spans many languages at once** (like the `_slice_by_braces` raw-vs-shielded-code
   ordering bug) is an architectural fix, not a per-language one — file it as its own issue, fix it
   on its own branch/PR, and note in the affected languages' sub-issues that it's covered elsewhere
   rather than re-fixing it N times. If verifying the broad version surfaces an unrelated pre-existing
   bug elsewhere (e.g. #859's PHP `prism.py` corruption, found while verifying the shared
   `_slice_by_braces` fix), gate the fix to just the language(s) actually in scope rather than either
   shipping the regression or blocking on the unrelated bug too.
5. **Any new test file that imports a sibling helper module must use `sys.path` insertion, not a
   dotted `tests.x.y` import.** This repo's `tests/` tree has no `__init__.py` anywhere, so
   `from tests.extraction._extraction_harness import ...` passes every local `python -m pytest` run
   (which prepends the CWD to `sys.path`) but fails in CI with `ModuleNotFoundError: No module named
   'tests'` (CI invokes the `pytest` console script directly, which doesn't). See any file under
   `tests/extraction/languages/` for the exact working pattern — insert `Path(__file__).resolve().
   parent.parent` onto `sys.path`, then import the helper as a bare top-level module name. **Before
   pushing any new test file with this kind of import, verify it by running plain `pytest <file>`
   (not `python -m pytest`) from an unrelated working directory** — this reproduces CI's actual
   invocation style and catches the failure locally instead of on a wasted CI round-trip.

## Recurring bug classes (seed list — extend this as the epic progresses)

Mirrors `how_to_add_a_language.md`'s own recurring-bug-class list, scoped to extraction rules
specifically. Check every language against these *first* before assuming a rule is clean:

1. **Nested-generic/template flattening (Rule 11 shape)**: any rule using a flat `<[^>]*>` or
   `\([^)]*\)`-style class where the real language allows one level of nesting inside it (Java
   bounded generics, C++ templates, C# generic constraints, Rust trait bounds). Fix: the established
   one-level-nesting idiom `<(?:[^<>]|<[^<>]*>)*>` (or the paren equivalent).
2. **Missing modern-era syntax entirely**: a rule written against an older language version never
   updated for a newer one's mainstream feature (Go 1.18+ generics, C# top-level statements already
   covered by #789, Python 3.12 PEP 695 generics). Check the language's own version history for
   features added in roughly the last 5-8 years.
3. **Unshielded string/comment content reaching a Mode-B rule's `finditer` call** — confirmed for
   `_slice_by_braces`; check whether `_slice_by_indentation`/`_slice_by_labels`/`_slice_by_terminator`
   have the same ordering issue for their respective language sets.
4. **Type-alias vs. real-declaration ambiguity**: any language where a `type X = ...`/`using X =
   ...`/`typedef` construct has the same surface shape as a real function/class declaration, with no
   preceding-keyword exclusion. **Confirmed real in typescript (#815)**: `type Foo = (a: T) => R;`
   shares the exact `IDENT = (...) => ...` shape as a real arrow-function assignment.
5. **(#815) Identifier-then-optional-type-annotation-then-operator**: any rule assuming an
   identifier is followed *directly* by the operator it cares about (`=`, `(`, etc.) without
   accounting for an optional type annotation in between — common in every statically-typed
   language (`const Foo: React.FC<Props> = (...) => {`; the equivalent shape exists in Kotlin,
   Swift, Rust, C#). Fix shape: an optional bounded skip-zone (`:` then bounded content excluding
   the real operator's own character) before the operator check — but watch for the operator
   appearing *inside* the type itself (e.g. a function-type annotation's own `=>`), which the skip
   zone can't safely cross without additional care (documented as a known limitation in #815, not
   solved there).
6. **(#815) Rule 11 also applies to inheritance/extends clauses, not just args/return-types**:
   `class_start`'s own generic step-over (between the class name and its `extends`/`implements`
   clause) can have the exact same flat-`<[^>]*>` bug — an easy miss because the class NAME still
   matches fine even when this breaks (only the extends/implements capture group silently goes
   missing). Check class_start's generic handling explicitly for any future language with generics.
7. **(#815) Bare-call-vs-bare-definition ambiguity — a known, ACCEPTED limitation class, not
   something to keep re-attempting**: in any C-family/JS-family language, a bare call statement at
   true line start (`it('test', fn);`, `foo();`) can be textually identical to a bare
   method/function signature with no body shown. Same fundamental ambiguity #789 (csharp) hit and
   deliberately did not fix at the regex level (a terminator requirement broke the cross-language
   "extraction gauntlet expects bare fragments to match" convention). Document with a dedicated
   known-limitation test per language rather than re-investigating whether it's fixable — it
   generally isn't, without real scope-tracking this engine doesn't have.
8. **(#815) A "zero diff" on `crucible_check.py` after adding a regex feature can mean the corpus
   doesn't exercise it, not that the feature is wrong** — same pattern as #735. Conversely, confirm
   a real per-language diff is confined to that language (`grep` the diff for other language names)
   before blessing, not just eyeballed for plausible magnitude.
9. *(All of `how_to_add_a_language.md`'s existing recurring-bug-class list — trailing/leading `\b`
   against symbolic or word-character boundaries, missing `re.M`, adjacent-overlapping-quantifier
   ReDoS — applies here too; these rules live in the same file and share the same authorship
   patterns.)*
10. **(#816) `class_start`'s generic step-over can be MISSING entirely, not just flat.** TypeScript's
    #815 bug (class 6 above) was a flat `<[^>]*>` that needed widening to the one-level-nesting
    idiom. Java's version of the same underlying bug was a different shape: no generic-parameter
    step-over between the class name and the extends/implements check at all, so ANY generic class
    with a subsequent extends/implements clause (`class Foo<T> extends Base<T> {`) silently lost the
    entire inheritance capture. Same fix (`(?:\s*<(?:[^<>]|<[^<>]*>)*>)?` inserted before the
    extends/implements check), but **check whether the step-over exists at all before assuming it
    just needs widening** — both failure shapes present identically at the test level (name capture
    fine, inheritance capture silently empty).
11. **(#816) `_dependency_capture` is matched against raw, unshielded file content for EVERY
    language, unconditionally — broader than class 3.** Unlike `func_start`'s Mode-B
    `_slice_by_braces` path (gated to js/ts, tracked via #859), `_dependency_capture` runs via
    `import_regex.finditer(content_buffer)` in `galaxyscope.py` against the raw file content read
    straight off disk, for every language, with no shielding gate at all. Confirmed reproducible for
    java: an `import ...;`-shaped line inside a Java 15+ text block (`"""..."""`) at true line start
    still produces a phantom dependency-graph edge. Not fixed (would require shielding
    `content_buffer` before every language's `_dependency_capture.finditer()` call -- a pipeline-wide
    change, not a per-language one) -- check for the same shape (comment/string content containing
    import-statement-shaped text at true line start) on every future language's dependency pass and
    record it as a known limitation rather than re-discovering it.
12. **(#816) Class 3 (unshielded content reaching a Mode-B rule) reproduced on a second, unrelated
    language feature**: Java 15+ text blocks produce the exact same `func_start` false positive as
    js/ts template literals, confirming this is a genuine cross-language architectural gap rather
    than a js/ts-specific quirk -- strengthens the case for broadening the `_slice_by_braces`
    shielding gate as its own follow-up PR (tracked in the epic's "Related architectural issue"
    section).
13. **(#817) A generic-step-over bug can be scoped to just ONE of the four rules, even in a
    generics-heavy language.** Java (#816) had the bug in `func_start`/`args` (shared) and a
    different-shaped version in `class_start`; typescript (#815) had it in `func_start` and
    `class_start`. Go's `class_start` and `args` already had the correct step-over -- only
    `func_start` (specifically the receiverless/top-level-function path) was missing it. **Check
    each of the four rules independently for the generic-step-over pattern rather than assuming a
    bug found in one implies the same gap everywhere** -- some rule authors already got three out
    of four right.
14. **(#817) Class 3 reproduced on a THIRD, unrelated language feature.** Go's raw string literals
    (backtick-delimited, common for embedded SQL/templates/regex) produce the same
    `func_start`/`_dependency_capture` false positive as js/ts template literals and Java text
    blocks. Three languages, three unrelated syntax features, same root cause -- strong evidence
    this is a real general gap, not a per-language curiosity.
15. **(#818) Rule 11 isn't angle-bracket-specific -- it hit python's SQUARE-bracket PEP 695 (3.12+)
    generics identically.** `func_start`/`args`/`class_start` all shared a flat `[^\]]*`
    generic-parameter step-over, breaking any nested-bracket type bound (`def Foo[T:
    Sequence[int]](x: T) -> T:`). Same fix idiom, square-bracket variant:
    `\[(?:[^\[\]]|\[[^\[\]]*\])*\]`. Whenever a language's generics use `[...]` instead of `<...>`
    (Python, Go), check for the identical flat-negated-character-class mistake -- don't assume Rule
    11 only applies to angle-bracket languages.
16. **(#818) Mode C (`_slice_by_indentation`, python/yaml) ALREADY does the shield-before-match fix
    that Mode B (`_slice_by_braces`) only has gated to js/ts.** Verified empirically: python's real
    pipeline shields triple-quoted/standard strings and comments via an index-aligned shield BEFORE
    calling `func_start.finditer()`, so the string-literal false positive confirmed at the regex
    level (same shape as class 3) is NOT a live pipeline bug for python. This is the reference
    implementation the eventual `_slice_by_braces`-broadening follow-up should mirror -- check
    whether a language's actual routing mode already solves class 3 before assuming it needs the
    fix.
17. **(#818) Not every vertical-split seam needs pathological-test coverage -- check against what
    real formatters actually produce.** A vertical split between an identifier and an
    immediately-following generic bracket (`def Foo\n[T](...)`) fails to match; judged a
    pre-existing, deliberately-undocumented-as-a-bug gap since no formatter (black, ruff format)
    ever inserts a line break at that exact seam. Realism-triage (step 2 of the verification
    discipline above) applies to formatting seams the same way it applies to feature coverage.
18. **(#819) A prior partial Rule-11 fix can leave a SIBLING rule un-fixed.** Rust's `func_start`
    already carried an explicit "BUG FIX (Rule 11...)" comment and a two-level-nesting idiom from an
    earlier pass, but `args` (parsing the exact same `fn <generics>(...)` shape) was never updated
    and still had the flat `<[^>]*>`. A fix comment on one rule is not proof the sibling rules got
    the same treatment -- check all four rules independently even when the code comments suggest
    "this was already handled."
19. **(#819) A `_dependency_capture` character class missing a single common symbol can hide an
    entire common statement shape.** Rust's capture char class (`[a-zA-Z0-9_:{},\s]`) was missing
    `*`, so EVERY glob import (`use std::io::*;`, `use super::*;`) produced zero dependency-graph
    edges -- confirmed via `crucible_check.py` (a real corpus file's detected-dependency count
    jumped 1 -> 5). Check a `_dependency_capture` character class against every symbol the
    language's own import/use syntax can contain, not just what the existing cases happen to cover.
20. **(#819) Class 3 reproduced on a FOURTH, unrelated language feature.** Rust's raw string
    literals (`r#"..."#`) produce the same false positive as js/ts template literals, Java text
    blocks, and Go raw strings.
21. **(#814) A fix's own whitespace tolerance can open a NEW false-positive path -- caught only by
    `crucible_check.py`, not by hand-written tests.** Fixing javascript's `func_start`/`args` to
    recognize ES6 generator methods (`*foo() {}`) initially used a whitespace-tolerant
    `\*?[ \t\n]*`, matching the style of the other modifier gaps around it. This let a JSDoc
    comment continuation line (`* A (storage) buffer attribute...` -- `*` is the comment marker,
    "A" is prose) get hallucinated as a generator method, confirmed against a real corpus file. No
    hand-written pathological case would have caught this shape. Fix: require the star to hug the
    name with zero whitespace (every real formatter emits `*foo()`, never `* foo()`) -- stricter
    AND more accurate, not a flexibility regression. **General lesson:** when a fix widens a rule
    with a "reasonable-sounding" whitespace-tolerant character class, check whether that specific
    optional character can ALSO appear as the leading character of a comment/string in real code --
    if so, match the strictest shape real formatted code actually produces, not the most permissive
    shape the grammar technically allows. This is exactly why step 3's crucible-check requirement
    exists even for "obviously safe" widenings.
22. **(#820) `class_start`'s missing-generic-step-over bug keeps recurring independently across
    unrelated languages.** java (#816), python (#818), and csharp (#820) all had it, each
    discovered separately, from a 4-language sample of generics-capable languages checked so far.
    **For any future language with generics, check `class_start`'s name-to-base-list gap FIRST**
    given this hit rate, rather than treating it as a fresh discovery each time. csharp also needed
    a companion fix no prior language required: a primary-constructor parameter-list step-over
    (`record Foo<T>(T Value) : Base<T>`, C# 9+ records / C# 12 primary constructors) -- check for
    this shape in any language with "primary constructor"-style class declarations (Kotlin, Scala).
23. **(#820) A `_dependency_capture` rule can be missing an entire real-world statement SHAPE, not
    just a character.** csharp's `using Alias = Target;` alias directive didn't match AT ALL --
    no allowance for the `IDENT =` prefix at all (contrast with rust's #819 finding, which was just
    a missing `*` in an existing shape). The alias target itself also needed its own generic-suffix
    step-over (`using StringList = List<string>;`, the primary real-world reason alias directives
    exist), confirmed via `crucible_check.py`. When reviewing `_dependency_capture`, check whether
    the rule's grammar covers every statement FORM the language's import syntax supports (plain,
    aliased, static, global, generic-targeted), not just variations on one form.
24. **(#821) Out-of-line member definitions (`Class::member(...)`) are worth checking explicitly
    for C-family languages -- operator overloads specifically are easy to miss.** cpp's
    `func_start`/`args` supported `Class::method(...)` for plain identifiers but had ZERO
    allowance for a class-qualifier before `operator` -- `TargetClass::operator=(...)` was
    completely invisible even though bare `operator=(...)` already worked. Distinct failure mode
    from Rule 11 (not a nesting bug -- the `operator` branch simply never got the qualifier-prefix
    group the plain-identifier branch already had). **Don't assume a recurring bug class means the
    SAME rule breaks again for the next language** -- java/python/csharp all had the class_start
    generics bug, but cpp's actual new finding was in func_start/args instead; check all four rules
    independently every time regardless of what the streak so far suggests.
25. **(#821) When checking a `crucible_check.py` diff for confinement, don't grep the raw `git
    diff` text -- it reports false "other language" hits from dependency-list VALUES and unrelated
    context lines, not just changed `Parsed Files` keys.** On a large golden-master JSON, do a
    STRUCTURAL diff instead: load pre- and post-update JSON and diff only the top-level
    `"6. Parsed Files (Scanned Artifacts)" -> "<repo>" -> "Files"` keys against each other. A
    naive textual grep after cpp's fix surfaced dozens of unrelated `.zig`/`.pm`/`.h` paths that
    looked like a confinement violation but were just pre-existing values inside other files'
    entries.
26. **(#822) "Confined to the language you changed" can legitimately span multiple repo buckets --
    polyglot/embedded files in a differently-labeled repo are expected, not a violation.** c's
    `class_start` fix changed files in `python/numpy`, `lua/redis`, `scheme/racket`,
    `cobol/gnucobol_internals`, and `cpp/godot`'s `object.h` (engine-classified `Language: "C"` via
    sibling-file disambiguation, despite the repo's folder-dominant language being cpp). All
    confirmed genuine `.c`/`.h` files embedded in those repos, not files in the repo's nominal
    language. After the structural diff (class 25) flags changed repos, verify every changed FILE
    within them is actually classified as the language you fixed -- check the file's own
    `"1. Artifact Identity" -> "Language"` field, not just its extension or the repo's folder label.
27. **(#822) Recurring class 3 can manifest via COMMENTS instead of strings, and some languages
    are structurally immune to the string-literal variant.** C has no raw strings, and every
    string-literal content line necessarily starts with a literal `"` (blocking `^[ \t]*` from
    reaching function-shaped text) -- the string variant confirmed on 6 other languages does NOT
    reproduce for C. It DOES reproduce via un-decorated block-comment continuation lines (no
    leading `*` marker). Check a language's comment syntax independently of its string syntax, and
    record a confirmed-safe negative result explicitly rather than silently skipping it.
28. **(#822) ALWAYS grep `test_language_standards_strict.py` for the rule you're about to change
    before treating a permissive match as a bug -- it may be intentional, tested, and documented.**
    A first version of c's `class_start` fix required a trailing `{` to reject what looked like an
    obvious false positive (`struct foo_ops ops;` matching as a "class start"). This broke
    `test_c_intentional_double_classification_sweep`, which explicitly documents that exact match
    as deliberate -- designed to co-fire with the `dependency_injection` rule's
    `_ops`-vtable-suffix heuristic. Reverted, keeping only the uncontested optional-tag-name fix.
    This repo has an entire test file dedicated to documenting cross-rule ambiguity and
    intentional double-classification as tested behavior -- grep it for the payload shape before
    "fixing" what looks like an obviously-wrong match. The full pytest suite step (already
    required) does catch this eventually, but checking proactively is cheaper than a red test
    after the fact.
29. **(#823) When fixing a missing-declaration-shape gap that would require making a shared
    branch's name optional, check whether a NARROWLY-SCOPED new alternative achieves the same fix
    without loosening anything else.** kotlin's `companion object { ... }` (almost always
    anonymous) never matched `class_start`. Making the general `class|interface|object|enum class`
    branch's name optional would have opened a new false positive on object EXPRESSIONS
    (`object : Base() {`). A dedicated alternative scoped to the literal `companion object` shape
    with its own optional name fixed it without touching the general branch at all.
30. **(#823) Recurring class 3 confirmed on a SEVENTH language (kotlin, via triple-quoted raw
    strings)** -- same shape as js/ts/java/go/rust/csharp/cpp, another confirming data point for
    the eventual `_slice_by_braces`-broadening follow-up.
31. **(#824) Rule 11 has now been a NEW confirmed finding in 7 of 9 languages checked with any
    generics-like syntax (java, typescript, go, python, rust, csharp, kotlin, swift) -- the two
    exceptions (cpp, already immune from a pre-epic pass except in args; c, no generics) prove the
    rule rather than break it. Flip the default: assume any new generics-capable language's
    generic-parameter step-over has this bug until empirically disproven, and check it FIRST.**
    swift's variant came from Swift 5.7+ primary associated type constraints
    (`func foo<T: Collection<Int>>(x: T) {`) -- different concrete syntax, identical root cause
    and fix.
32. **(#824) Recurring class 3 confirmed on an EIGHTH language (swift) via TWO distinct string
    forms in the same language** -- both triple-quoted multi-line strings and `#"..."#` raw string
    literals reproduce the false positive independently.
33. **(#825) The identifier-capture-class rule (`how_to_add_a_language.md`'s Rule 16) is a real,
    recurring cross-language finding, not a one-off Scheme curiosity.** Scala's `func_start`/`args`
    name capture required a plain `[a-zA-Z_]\w*`, so backtick-quoted arbitrary identifiers (Scala's
    escape hatch for reserved-word/space-containing names, e.g. `` def `should handle edge cases`():
    Unit = {} ``, a real ScalaTest/Java-interop idiom) never matched. Fixed as an alternative
    capture group, resolved via `match.lastindex` (existing infrastructure, see java's
    `(init)|(constructor)` groups) rather than widening the plain-identifier class. **Kotlin has the
    identical backtick grammar and the identical gap, missed during #823's pass** -- when a language
    supports backtick/escaped identifiers, check func_start/args/class_start's capture class against
    that grammar explicitly, and don't assume a prior "closed" sub-issue for a sibling
    backtick-identifier language already covers it.
34. **(#825) A `_dependency_capture` rule can have NO statement-boundary logic at all -- a worse
    failure mode than recurring class 19's missing-symbol gap.** Scala's capture was a flat
    `[\w.{}\s,]+` class with no anchor stopping it at one logical import's end; since `\s` matches
    newlines, it silently bled across a SECOND real import statement into the following unrelated
    line on a realistic multi-import file, so the second import was never separately detected.
    `crucible_check.py` against the real corpus (Kafka) confirmed the severity concretely: several
    files' detected dependency counts roughly DOUBLED once fixed. Fix idiom: replace the flat class
    with a bounded segmented-path grammar (repeat `identifier.` segments, end on either a `{...}`
    block or a bare trailing identifier/wildcard) rather than just adding more characters to the
    class. Check any `_dependency_capture` rule using bare `\s` instead of a real statement boundary
    for this same bleed-over risk.
35. **(#825) A confirmed real `_dependency_capture` fix's `crucible_check.py` diff can legitimately
    ripple into completely unrelated languages/repos via the shared cross-repo dependency graph --
    that is NOT automatically a confinement violation.** Unlike the other three rules (per-file
    scoped), `_dependency_capture` feeds `network_risk_sensor.py`'s PageRank/blast-radius scoring
    and `spatial_mapper.py`'s 3D projection, both computed over the WHOLE scanned corpus as one
    graph. Fixing scala's bleed-over (class 34) shifted Topological Coordinates, PageRank-derived
    blast-radius counts, and corpus-relative percentiles for 9 unrelated language/repo pairs plus
    global ecosystem-summary aggregates. Verified genuine (not confinement-violating) by confirming
    every non-target-language diff line was one of these global/derived metric types, never a raw
    per-file signature count for an untouched language. When a fix touches `_dependency_capture`
    specifically, expect and check for this ripple shape rather than treating any non-target-language
    diff line as an automatic confinement bug.
36. **(#834) Rule 11 also manifests for a flat PARENTHESES-wrapped parameter/argument list, not just
    generic type parameters.** PowerShell's `args` rule (`param(...)`/`function NAME(...)`) used the
    flat `\([^)]*\)`, truncating at the FIRST `)` -- breaking on a default-value expression
    containing its own parens/array-subexpression syntax (`param($Tag = @('Slow', 'Feature'))`, a
    realistic idiom). Confirmed severity via `crucible_check.py`: a real PowerShell Core corpus
    file's detected parameter count for one function jumped 3 -> 9 once fixed. Same fix idiom as
    every other Rule-11 instance, just the paren-list variant -- check any flat `\([^)]*\)`
    parameter-list rule for this, not just generic-bracket rules.
37. **(#834) Adding coverage for a bare, unprefixed declaration shape (`Identifier(params) { body
    }`, no keyword, no return-type marker -- PowerShell class constructors) WILL collide with that
    same language's own control-flow statement shape (`if/while/switch/for/foreach (cond) {
    body }`), since they're textually identical to a flat regex.** A negative-lookahead keyword
    exclusion is required alongside the new alternative. Caught here by hand-testing the fix's own
    "invalid" case immediately after writing it, not by `crucible_check.py` -- the same "a new
    alternative can open its own blind spot" lesson as recurring class 21, but at authoring time via
    manual verification instead of a corpus diff. Check for this collision risk BEFORE shipping any
    bare-identifier-plus-body alternative in a C-family-control-flow language.
38. **(#834) A modifier/scope prefix attached to an identifier via a delimiter can make a capture
    group swallow the PREFIX instead of the real name -- silently wrong data, not just a non-match,
    and easy to miss in review.** PowerShell's scope qualifiers (`global:`/`script:`/`local:`/
    `private:` before a function name) aren't in the identifier character class, so the capture
    stopped at the delimiter and returned the scope keyword itself as if it were the function name.
    Same root shape as Rule 16 (identifier grammar) but the failure mode -- confidently wrong output
    vs. a safe non-match -- is worse and doesn't show up as a dramatic test failure the way a
    non-match does.
39. **(#834) An "optional quote pair" idiom (`['"]?...['"]?`) around a capture class that excludes
    whitespace is a DIFFERENT bug shape from recurring class 19 (a missing symbol) -- it truncates
    any quoted value containing that excluded symbol even though quoting should have protected it.**
    PowerShell's `_dependency_capture` used exactly this shape, so a quoted path containing a space
    (`'C:\Program Files\MyModule\MyModule.psd1'`, an extremely common Windows idiom) silently
    truncated at the first space. Fix: real per-quote-style alternatives (a quoted branch permitting
    the excluded symbol inside real quotes, a separate bare/unquoted branch that still excludes it),
    not just widening the shared class -- widening it would also re-break the original
    over-capture problem the optional-quote shape was trying to avoid.
40. **(#834) `_dependency_capture`'s comment-lookalike vulnerability (class 3's shape) is NOT
    universal -- confirmed a SECOND language (powershell, after c's #822 finding, class 27) where
    the rule's own `^[ \t]*` anchor structurally blocks a comment marker from ever reaching the
    keyword. But the SAME rule instance in the SAME language can still be vulnerable via a DIFFERENT
    unshielded-content vector**: PowerShell here-strings (`@"..."@`) land their inner content at true
    line start with no blocking marker, so import-shaped text inside one still produces a phantom
    dependency edge. Check comment- and string-literal vectors independently per language/rule --
    confirmed immunity to one vector doesn't imply immunity to the other.
41. **(#843) A "block requires an immediate newline after its header key" idiom breaks on a
    trailing same-line comment on the header itself.** YAML's `args` rule (`with:[ \t]*\n...`)
    required an immediate newline after `with:`, so `with: # inputs for this action\n  node-version:
    '18'` (a real CI-YAML authoring style) never matched. Same general shape as classes 5/6 (an
    unaccounted-for optional element between two required tokens) but for a block-header-to-body
    transition. Fix: an optional `(?:#.*)?` before the newline. Check any "header line, then
    indented body" rule for the same gap if that language's comment marker can appear on the header
    line.
42. **(#843) A "declaration name, then immediately the thing we care about" shape can be too strict
    when real usage inserts OTHER keys/statements in between -- a SEQUENCING problem, distinct from
    Rule 11's nesting problem.** YAML's `class_start` required `uses:`/`image:` to be the literal
    first line after a job name, but real reusable-workflow-call/container jobs routinely have
    `needs:`/`if:`/`permissions:` first. Fixed with a BOUNDED (max 10) step-over for intervening
    key:value lines -- bounded so it can't bleed into an unrelated subsequent job's own content once
    no `uses:`/`image:` is found. Check for this shape whenever a rule assumes its target keyword is
    the immediate next line/token after an anchor, when the real language allows other optional
    statements in between.
43. **(#843) An "optional-quote" idiom can be missing ENTIRELY, not just shaped wrong (class 39's
    finding for PowerShell was a wrong shape; this is a total absence).** YAML's
    `_dependency_capture` had no quote-tolerance at all for `uses:`/`image:` values, so a quoted
    value (`uses: "actions/checkout@v4"`, a real yamllint-driven authoring style) never matched.
    Fixed with the same real per-quote-style-alternative idiom as #834's fix. Note: `import` (a
    sibling, non-gauntlet-scoped rule with nearly the same pattern) was deliberately left unfixed --
    out of the four-gauntlet scope for a given issue, not an oversight; don't feel obligated to fix
    every structurally-similar sibling rule outside the four gauntlets in the same pass.
44. **(#856) A negative lookahead exclusion can be entirely neutralized by the character class that
    immediately follows it.** Assembly's `func_start` tried to exclude local labels like `.L` via
    `(?!\.L)([a-zA-Z_]...)`, but `[a-zA-Z_]` already rejected any identifier starting with a dot.
    This meant legitimate global labels starting with `.` were blocked, and the lookahead was dead
    code. When adding a negative lookahead, verify that the subsequent matching logic actually
    permits the excluded shape to begin with.

## Process: the epic and its sub-issues

One epic issue tracks this whole effort. One sub-issue per language, titled
**"Extraction hardening: `<language>`"**, scoped to all four gauntlets for that language together
(matching the "one language's context, all four concerns" work pattern above). A sub-issue is
in scope for any language with at least one non-`None` rule among `func_start`/`args`/
`class_start`/`_dependency_capture` — languages with none of the four (e.g. `csv`, `json`,
`markdown`, `plaintext`, `xml`, `proto`, `mlir`, `hlo`, `glsl`, `td`, `blp`, `batch`, `nix`, `pbtxt`)
are out of scope entirely, not "all `None`, still write a sub-issue."

Each sub-issue should end with an **"Update the epic" checklist item**: any newly-confirmed
recurring bug class, or any language-specific gotcha likely to recur (e.g. "this language's
generics syntax also trips up rule X the same way"), gets appended to this doc's recurring-bug-class
list before the sub-issue is closed — so the *next* language's pass starts from a sharper checklist,
not from scratch. This is the same "audit trigger" discipline that made epic #518's later languages
faster to close than its earlier ones.

### Sub-issue template

```markdown
Part of the extraction-hardening epic (#<epic-number>). See
`tests/extraction/how_to_harden_extraction.md` for the full methodology this issue follows.

### Language: `<lang>`

Rules in scope (non-`None` in `LANGUAGE_DEFINITIONS["<lang>"]["rules"]`):
- [ ] `func_start`
- [ ] `args`
- [ ] `class_start`
- [ ] `_dependency_capture`

(Strike through any not defined for this language — that's an intentional gap per Strict Feature
Parity, not something to force.)

### Checklist (per the methodology doc, for each in-scope rule above)
- [ ] `valid`: modern idiom + legacy/historical syntax eras + testing-framework-shaped functions
- [ ] `invalid`: string-literal lookalikes, type-level lookalikes, assignment-in-condition,
      macro-expansion lookalikes, and any language-specific lookalike shape
- [ ] `pathological`: 10-15 cases covering annotation/attribute stacking, nested generics/templates,
      destructured/complex params, multi-line splits at every plausible boundary
- [ ] Every case empirically verified against the real compiled regex before being added
- [ ] Any genuine bug found is fixed (full ReDoS/lint/type/crucible discipline) or filed separately
      if it's a multi-language architectural fix
- [ ] Migrated out of the four old monolithic dict files into
      `tests/extraction/languages/test_<lang>.py`
- [ ] Epic updated with any new recurring-bug-class findings before closing this issue
```

## Suggested ordering

No strict requirement, but a sensible default: start with the languages already flagged with
confirmed bugs above (`javascript`, `typescript`, `java`, `go`), since their sub-issues start with
known findings to fix rather than needing a fresh sweep. After that, prioritize by real-world
prevalence/complexity (the languages with the largest, most actively-maintained rule sets) before
the long tail of smaller/legacy languages (`cobol`, `fortran`, `assembly`, `abap`, etc.), which tend
to have simpler, more stable extraction rules and fewer syntax eras to cover.

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
   the test file.** Write a throwaway script that imports `LANGUAGE_DEFINITIONS`, compiles nothing
   extra, and calls `.search()` directly — don't guess whether a payload matches. A case that's
   wrong about the engine's actual behavior is worse than no case: it either bakes in a bug as
   "expected" or fails for the wrong reason.
2. **A failing verification is a finding, not necessarily a bug to fix immediately.** Triage each
   one: is the payload realistic (a fair test), or did the payload accidentally test something the
   rule was never meant to handle (e.g. a single-line object-literal method shorthand when the rule
   is `^`-anchored and the real-world form is always multi-line)? Rewrite unrealistic payloads
   before concluding there's a bug.
3. **Real bugs get fixed with the full existing discipline**, not just documented: ReDoS scaling
   check if the fix touches a quantifier, `ruff format`/`ruff_audit.py --ci`/`mypy_audit.py --ci`/
   `dead_key_audit.py --ci`, full relevant test suites, and — if the fix touches `language_standards.py`,
   `detector.py`, or `prism.py` — `tests/tools/crucible_check.py` with the diff verified file-by-file
   against ground truth (not just "the diff count looks plausible") before regenerating golden
   masters. See `CLAUDE.md`'s Differential Scan section.
4. **A fix that spans many languages at once** (like the `_slice_by_braces` raw-vs-shielded-code
   ordering bug) is an architectural fix, not a per-language one — file it as its own issue, fix it
   on its own branch/PR, and note in the affected languages' sub-issues that it's covered elsewhere
   rather than re-fixing it N times.

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

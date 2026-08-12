# Extending #1264's class_start named-entity extraction (epic: #1295)

## Background

`detector.py`'s named-entity class extractor (the source of `class_data`/`class_count`,
distinct from the numeric `class_start` signal count used for risk scoring) used to run one
hardcoded, language-agnostic regex instead of consulting each language's own `class_start`
rule -- unlike `func_start`, which was already wired correctly. #1264 fixed this, gated behind
an allowlist so the fix only applies where it's been verified safe:

```python
# gitgalaxy/core/detector.py
_CLASS_START_NAMED_EXTRACTION_LANGS = frozenset({
    "apex", "cpp", "csharp", "fortran", "groovy", "java", "javascript",
    "lua", "makefile", "matlab", "php", "powershell", "python", "scala",
    "shell", "solidity", "tcl", "typescript",
})
```

13 more languages regressed when tried the same way and were left on the legacy fallback:
**c, css, dart, go, haskell, html, kotlin, objective-c, perl, ruby, rust, swift, zig**. Extending
the allowlist to them -- one at a time, with real verification -- is what epic #1295 tracks, and
what this doc + `tests/tools/class_start_diff.py` exist to make cheap. **go, objective-c, swift,
kotlin, zig, rust, haskell, and c are done** (flipped into the allowlist, see the table below);
5 remain.

Read `_resolve_class_start_match` in `gitgalaxy/core/detector.py` before touching anything --
it's the exact name-resolution algorithm the live pipeline uses (prefer capture group 1, fall
back to group 2 for Fortran/Lua/ABAP-shaped alternation, else `"Anonymous_Class"` for patterns
with no capture group at all), and `class_start_diff.py` imports it directly so the two can never
drift apart.

## IMPORTANT: a shared prerequisite blocks 7 of the 13 languages -- fix this first

Before assuming a language's `class_start` regex is the problem, run
`python tests/tools/class_start_diff.py --lang <x>` and check `real_classes`. If it reads `0` (or
implausibly low) despite the corpus obviously containing real declarations, **the bug is in
`tree_sitter_accuracy_audit.py`'s own ground truth, not in `language_standards.py`.** Confirmed
during #1295's scaffolding pass -- do not re-derive this, just apply the fixes below:

### Done: `_get_node_name` ground-truth fixes already landed

| Language | Status |
|---|---|
| **go** | Fixed (#1295 PR): `type_declaration` has no `name` field, but its `type_spec` child does. Flipped into `_CLASS_START_NAMED_EXTRACTION_LANGS`: `found_classes` 0→69, `extra_classes` 0→0. The 15 tree-sitter-only "missing" are all plain type aliases (`type WaitStatus uint32`) that go's own `class_start` intentionally excludes (requires `struct`/`interface` to follow) -- a scope mismatch, not a recall bug, documented in the baseline commit. |
| **objective-c** | Fixed (#1295 PR): `class_interface`/`class_implementation`/`class_declaration` have no `name` field; first positional `identifier` child is the class name (second is the superclass for `class_interface` only). Flipped into the allowlist: `found_classes` 0→5, `extra_classes` 0→0, a perfect match. |
| **swift** | Fixed (PR #1361): `class_start` had a capture group added (name only had an unparenthesized `[a-zA-Z_]\w*` before), widened to an optional dotted chain for nested-type extensions (`extension AFError.ParameterEncoderFailureReason`). Also hit the ground-truth measurement gap: tree-sitter-swift's protocols are a separate `protocol_declaration` node type, not `class_declaration` -- added to `NODE_MAPS["swift"]["class_node_types"]`. `real_classes` 37→38, `found_classes` 23→38, `extra_classes` stays 0. Flipped into the allowlist. |
| **kotlin** | Fixed (PR #1365): three separate bugs stacked on this one. (1) `class_start` had no capture group -- added group 1 for the main class/interface/object/enum-class branch and group 2 for companion object's own optional name (Fortran/Lua-shaped alternation). (2) `fun interface Foo` (SAM declarations, Kotlin 1.4+) wasn't recognized -- `fun` was missing from the modifier list, a real recall gap confirmed against okhttp's `fun interface Factory`. (3) ground-truth gap: kotlin's `object` declarations (including `actual`/`expect` multiplatform variants) get their own `object_declaration` node type, not `class_declaration` -- added to `NODE_MAPS["kotlin"]["class_node_types"]` and `_get_node_name`. `real_classes` 4→7, `found_classes` 3→7, `extra_classes` stays 0. Golden master updated (okhttp/Call.kt's class count went 1→2). Flipped into the allowlist. |
| **zig** | Fixed (PR #1367): the biggest/messiest one so far (32 corpus files, `real_classes` in the hundreds), and the first to land with `extra_classes`/`missing_classes` still non-zero by design after investigation -- same discipline as csharp's enum precedent, not a shortcut. Ground truth gap: zig's error sets (`const Foo = error{...};`) get their own `ErrorSetDecl` node type, distinct from `ContainerDecl` -- a class-like entity GitGalaxy's own `class_start` regex intentionally matches (its comment literally says "struct, enum, union, error, opaque"). Added to `NODE_MAPS["zig"]` and dispatched through the same `_get_zig_container_name` resolver. Also widened `class_start` with an optional `\(`/`\*` step-over for two confirmed corpus idioms: a parenthesized-wrapped anonymous struct (`const lenAsc = (struct {...}).lenAsc;`) and a pointer-to-opaque handle type (`const HMONITOR = *opaque {};`). Net result: `extra_classes` 10→1, `found_classes` 0→630 (was 0 because the *legacy fallback* regex structurally can't match zig's `const X = struct` shape at all -- zig's own `class_start` always had a capture group, it just wasn't on the allowlist). The remaining `extra_classes=1` ("Borrowed" in bun/MimallocArena.zig) is a confirmed tree-sitter-zig grammar limitation (the file uses Zig's newer `#field` private-field syntax, which the grammar can't parse -- `has_error=True` on that node -- so error recovery swallows the declaration), the same shape as csharp's `LanguageParser` precedent in #1264. `--regenerate` correctly refuses on a raw `extra_classes` regression (0→1) even though `found_classes` improved massively -- baseline was hand-blessed to the measured numbers, same as csharp's precedent. `missing_classes` (23→26 net) stays non-zero **by design**, categorized in the "recurring cause classes" section below rather than chased in this PR -- see class 7. |
| **rust** | Fixed (#1295 PR): no regex change at all -- two ground-truth-side items. (1) `union_item` (tree-sitter-rust's node type for `union Foo {...}`) was missing from `NODE_MAPS["rust"]["class_node_types"]` -- a real class-like entity rust's own `class_start` regex already matches (its comment covers struct/enum/union/trait), confirmed via wasmtime's `FRegUnion`/`VRegUnion`/`XRegUnion`, plain top-level unions with no macro involvement. Added it: `real_classes`/`found_classes` 242→245, `extra_classes` 11→25 (see next point for why that's not a regression). (2) every one of the 25 remaining `extra_classes` traced to a struct/enum/trait declaration sitting inside a macro invocation or `macro_rules!`/proc-macro-template body (`cfg_not_rt! { pub(crate) struct JoinHandle<R> {...} }`, `pin_project! { pub enum MaybeDone<Fut: Future> {...} }`, `ast_struct! { pub struct Variant {...} }`, serde's `$typaram`-templated visitor structs) -- tree-sitter treats macro bodies as opaque token trees so `real_classes` can't see them at all, while GitGalaxy's regex (raw text) matches them fine. Same accepted blind spot already documented for #1311/#1319's `extra_functions`, now confirmed to apply identically to classes -- not chased, baseline hand-blessed to the measured `extra_classes=25` the same way as csharp/zig's precedent (`crucible_check.py` both modes clean: the ~80-repo golden-master corpus's own rust files didn't hit this pattern noticeably, since the legacy fallback already covered plain `struct`/`enum`/`trait` reasonably -- `union` was the only real recall gain there). Flipped into the allowlist. |
| **haskell** | Fixed (#1295 PR): no regex change -- pure ground-truth fix, same shape as rust's `union_item`. Haskell's own `class_start` regex already intentionally matches `data(?:\s+family)?\|newtype\|class\|type(?:\s+family)?` under an "Object / Entity Declarations" comment, but `NODE_MAPS["haskell"]["class_node_types"]` only had `{"class_decl", "class"}` -- missing tree-sitter-haskell's separate node types for `data`/`newtype`/`type` declarations (`data_type`, `newtype`, `type_synomym` -- that misspelling is the grammar's own, kept verbatim -- `data_family`, `type_family`), all of which expose a usable `name` field natively (no `_get_node_name` branch needed, unlike go/kotlin/zig's special-casing). Confirmed via pandoc's `data PandocOutput`/`data Filter`/etc. Added all 5 node types: `real_classes`/`found_classes` 1→16, `extra_classes` 15→0 -- a perfect match, not an accepted-gap case. Flipped into the allowlist. Delegated to an independent Gemini/Antigravity implementation pass (epic #1295's first cross-model run) with a full second-pass re-verification before merge -- see the epic's own comment thread for the process note. |
| **c** | Fixed (#1295 PR): the hardest of the batch, flagged going in as needing real declaration-vs-usage disambiguation (recurring cause class 2) rather than a mechanical NODE_MAPS/capture-group fix. c's `class_start` intentionally matches BOTH real declarations (`struct Foo {`) and bare usage/forward-reference sites (`struct foo_ops ops;`) for a deliberate reason -- `test_c_intentional_double_classification_sweep` (epic #813/#822's `_ops`-vtable dependency-injection risk heuristic) requires that co-firing, and a prior attempt to add a trailing-`{` requirement to the shared regex was reverted for breaking it. The fix stays entirely OUT of the shared `class_start` regex's matching behavior (verified `test_c_intentional_double_classification_sweep` passes identically before/after) -- two parts instead: (1) ground truth (`tree_sitter_accuracy_audit.py`/`class_start_diff.py`): tree-sitter-c's `struct_specifier`/`union_specifier`/`enum_specifier` nodes have a `body` field that's populated for real declarations and `None` for usage sites -- only count nodes with a body as real classes (also added `union_specifier`/`enum_specifier` to `NODE_MAPS["c"]`, previously only `struct_specifier` even though c's own regex also matches union/enum). (2) `detector.py`'s NAMED-EXTRACTION loop only (a different consumer of the same matches): made the tag-name capture group capturing (purely additive -- doesn't change `.finditer()`'s match count/positions), and added a new C-specific bounded 200-char lookahead (`_CLASS_START_REQUIRES_BODY_ANCHOR`) that skips a match from `class_data` entirely unless a `{` is the first of `{;,)=` encountered after it. `real_classes` 79→61 (ground truth now excludes usage sites too), `found_classes` 0→61 (100% recall), `extra_classes` 23→17 -- all 17 residual are `"Anonymous_Class"` entries for anonymous typedef'd structs (`typedef struct { ... } Bar;`, where the alias name lives one grammar level above `struct_specifier` and isn't chased), a documented grammar-shape limitation, not an unexplained regression. Flipped into the allowlist. Implemented via an independent Gemini/Antigravity delegation pass, then independently re-verified end to end (full diff re-read, accuracy audit, the regression test by name, both crucible modes, full test suite) before merge -- see the epic's own comment thread for a process note, including a permission-boundary incident during the delegation that's worth reading before running this kind of task unattended again. |

### Needs a judgment call, not a quick field-name fix

| Language | Issue |
|---|---|
| **perl** | `class_node_types = {"class_statement"}` targets modern Perl 5.38+ `class Foo {...}` syntax. Real-world Perl in the corpus (exiftool) uses the traditional `package Foo;` idiom almost exclusively, which is a different node type entirely -- not a name-lookup bug, a *wrong ground-truth target*. Decide whether `class_statement` is even the right node type for what GitGalaxy's own `class_start` regex means by "a perl class" (its regex matches `package`/`class`/`role`), and whether `package_statement` should be added to `class_node_types` too. |
| **css** | `rule_set` (a CSS selector block) has no `name` field because it conceptually isn't named the way a class/struct is -- it has a *selector*, possibly compound/multiple. GitGalaxy's own CSS `class_start` regex matches selector text (`.foo`, `#bar`), a fundamentally different concept than an OOP "class". Recommend deciding whether CSS belongs in this exercise **at all** before spending time on it -- it may be a conceptual mismatch, not a bug to fix. |
| **html** | `class_node_types = {"element"}` matches *every* HTML element, but GitGalaxy's own HTML `class_start` regex only fires on a specific curated tag list (`form`, `table`, `svg`, custom elements, etc.) -- ground truth is far broader than what the regex is trying to measure. Same "is this even the right comparison" question as CSS. |

**Do this measurement-tool work in `tests/tools/tree_sitter_accuracy_audit.py`'s `_get_node_name`
and `NODE_MAPS`, verify with `python tests/tools/class_start_diff.py --lang <x>` until
`real_classes` looks plausible, *then* move to the per-language regex workflow below.** Treat
each fix as its own small commit/PR (it changes a shared measurement file, not
`language_standards.py`) -- don't bundle it with the regex work for the same language.

### Languages where ground truth already works -- go straight to the regex workflow below

**dart** (167), **ruby** (9). (**swift, kotlin, zig, rust, haskell, c** done -- see the "Done"
table above.)

Note on **ruby**: `class_start_diff.py --lang ruby` shows `extra_classes=9` on top of a clean
`found_classes=9`/`missing_classes=0` -- i.e. every real class is already matched correctly, and
the 9 extras are `module Foo` declarations plus `class << self`/`class << @var` singleton-class
reopening, both of which ruby's own `class_start` intentionally matches (see its "Object / Entity
Declarations" comment in `language_standards.py`) but aren't in `NODE_MAPS["ruby"]["class_node_types"]`
(`{"class", "singleton_class"}`). `singleton_class` IS already in that set but has no `name` field
of its own (it wraps an expression, not an identifier) -- likely another ground-truth measurement
gap (class 6) for `_get_node_name`, not the scope-mismatch class 5 that `module` is. Check
`singleton_class`'s actual child structure in `tree_sitter_language_pack`'s ruby grammar before
assuming it can't be named -- it may resolve to the enclosing class name via a short ancestor walk
(same shape as csharp/zig's precedents), which would leave `module` as the only real scope
question for ruby.

## Per-language workflow (once ground truth is trustworthy)

1. **Get the raw diff.** `python tests/tools/class_start_diff.py --lang <x>` -- prints, per file,
   every extra (GitGalaxy-only) and missing (tree-sitter-only) class name with source-line
   context. This previews the *live* name-resolution algorithm against the language's real
   `class_start` rule, with no detector.py edits required yet.
2. **Classify every `extra` entry** against the recurring-cause list below. A failing name is a
   finding to triage, not an automatic regex change.
3. **If it's `"Anonymous_Class"` flooding** (the count next to it, not a single line): the
   language's `class_start` has no/optional capture group around the name (same as C/kotlin).
   Decide whether the name is realistically recoverable (a capture group can be added around an
   existing optional span) or whether the rule was only ever meant for numeric counting and
   should stay off the allowlist.
4. **If it's a real name, wrongly matched**: read the source context class_start_diff.py printed.
   Is GitGalaxy matching a *usage* site instead of a *declaration* (C's `struct foo_ops ops;`
   shape)? A compound-modifier gap? Fix the regex in `language_standards.py`, following
   `gitgalaxy/standards/how_to_add_a_language.md`'s 12 engine rules (ReDoS/boundary correctness)
   -- this is regex surgery, keep it in the main conversation, not a subagent.
5. **If it's a real name GitGalaxy found but tree-sitter ground truth doesn't have** (the csharp
   precedent: enums intentionally treated as class-like by the regex but excluded from
   `class_node_types`): confirm by checking `NODE_MAPS[lang]["class_node_types"]` yourself --
   this is a ground-truth *scope* question, not a bug. Document it in the baseline-regeneration
   commit, same as csharp's.
6. **Flip the allowlist and verify for real** (raw-text triage above is an approximation --
   this is the authoritative check):
   ```bash
   # add <lang> to _CLASS_START_NAMED_EXTRACTION_LANGS in gitgalaxy/core/detector.py
   python tests/tools/tree_sitter_accuracy_audit.py --lang <x> --ci
   python tests/tools/tree_sitter_accuracy_audit.py --lang <x> --regenerate   # if clean/improved
   python tests/tools/tree_sitter_accuracy_audit.py --summary-table
   python tests/tools/crucible_check.py                                       # both modes
   python tests/tools/audit_check.py --regenerate                             # if pure line-shifts
   python -m pytest tests/core_engine/ tests/extraction/
   ```
   If `--regenerate` refuses because of a real `extra_classes`/`found_classes` regression that
   you've confirmed (step 5) is a legitimate ground-truth scope mismatch rather than a bug, hand-
   edit the baseline JSON to the freshly measured numbers and explain why in the PR -- same as
   csharp's precedent in #1264's PR description. Never hand-edit it for an unexplained regression.
7. **Close the loop**: comment on #1295 with the result, update this doc's tables if a new
   recurring-cause class turns up.

## Recurring cause classes (seed list -- add to this as more languages are done)

1. **No capture group at all** -- the rule was written purely for numeric signal-counting
   (`class_start` feeding `equations`/`counts`, same tier as `branch`/`io`) and never needed a
   name. Confirmed: C, Kotlin, Groovy, PowerShell, assembly (Swift was in this class too --
   fixed by adding a capture group, PR #1361, no other blocker). Every match becomes
   `"Anonymous_Class"`, which floods `class_data` with one phantom entry per file that has any
   match at all -- `class_start_diff.py` surfaces this explicitly (`N unnamed match(es)`), don't
   let it get filtered out of a triage pass.
2. **Declaration vs. usage ambiguity** -- the rule intentionally also matches non-declaration
   *usage* sites for risk-signal purposes (C's `struct foo_ops ops;` matches the same as
   `struct foo_ops {`). A capture group alone doesn't fix this; the rule needs a real
   declaration anchor (e.g. requiring a following `{`) which historically broke other accepted
   test cases when tried (see C's own inline comment, epic #813/#822) -- expect this to be
   genuinely hard, not a quick regex tweak.
3. **Compound modifier stacks** -- multiple modifier keywords before the class keyword
   (`internal sealed partial class`, `public with sharing class`) that a single-slot or
   3-word-alternation modifier group can't express. Already fixed for Apex/C# in #1264; likely
   also relevant to Dart, Kotlin, Scala-shaped languages.
4. **Alternation producing the name in a different capture group** -- Fortran/Lua/ABAP-shaped
   rules where which group holds the name depends on which alternative branch matched.
   `_resolve_class_start_match` already handles this generically; not a per-language bug.
5. **Ground-truth scope mismatch** -- GitGalaxy's `class_start` intentionally treats something
   as class-like (enums, for csharp) that tree-sitter's `class_node_types` for that language
   deliberately excludes. Not a detector bug; document and hand-bless the baseline.
6. **Ground-truth measurement gap in `tree_sitter_accuracy_audit.py` itself** -- the chosen
   `class_node_types` node exists and matches real declarations, but has no `name` field
   (the name lives on a child or ancestor node instead), so `_get_node_name` silently returns
   `None` for every match and `real_classes` reads as 0 regardless of how good or bad the
   regex is. New class discovered during #1295's scaffolding pass -- go/kotlin/objective-c/zig
   all hit this (now fixed, see the "Done"/"ground truth already works" tables above).
   **Always check this first** before touching a language's `class_start` regex.
7. **The ground-truth *walk* over-reaches beyond the regex's declaration anchor** -- a variant of
   class 5, discovered on zig (PR #1367). The ground-truth node exists, resolves to a real name, and
   isn't a scope-*category* mismatch (it genuinely is a struct/enum/error-set) -- but the ancestor
   walk that recovers the name (`_get_zig_container_name`, bounded to `max_hops`) finds it
   regardless of *how deeply nested* the anonymous type is inside the enclosing declaration's
   initializer expression, while GitGalaxy's regex only anchors on the type keyword sitting
   *immediately* after `=` (plus a narrow, explicitly-added set of step-overs). Four concrete
   shapes seen on zig, none fixed in that PR (documented as accepted gaps, not chased):
   - **Nested inside a generic call's argument**: `const Extra = List(struct { u32 });` -- the
     anonymous struct is a type *argument* to `List(...)`, not the direct RHS value.
   - **Nested inside an array-element type**: `const targets = [_]struct {...}{...};` -- same
     shape, the struct describes the array's element type, not `targets` itself.
   - **Type-annotation position, not initializer position**: `var op: enum {...} = .example;` --
     the anonymous type sits between `:` and `=`, a different grammatical slot GitGalaxy's regex
     (which only ever looks *after* `=`) doesn't parse at all.
   - **A binary chain of named error sets terminating in a literal**: `const X = A || B ||
     error{C};` -- tree-sitter resolves the *whole* union's declared name correctly; GitGalaxy's
     regex would need to skip an unbounded-looking `ident || ident || ...` chain before the
     `error` keyword, meaningfully more regex complexity/ReDoS-review than the other step-overs.
   Each is a real, understood gap -- worth a dedicated follow-up decision (especially the
   type-annotation-position one, which recurred 6x in zig's own corpus) rather than folding
   into whichever PR happens to discover it.
8. **Macro invocation / definition body opacity** -- a declaration is real and syntactically
   ordinary, but sits inside a macro invocation (`pin_project! { pub enum Foo {...} }`,
   `cfg_not_rt! { pub struct Bar {...} }`) or a `macro_rules!`/proc-macro-template body using
   placeholder syntax (`struct Visitor<T $(, $typaram)*> {...}`). Tree-sitter treats the macro's
   argument/body as an opaque token tree it doesn't parse into real declaration nodes, so
   `real_classes`/`real_functions` can never see it, while GitGalaxy's regex (raw text, no
   macro-awareness) matches it fine -- the reverse direction of class 6 (a real GitGalaxy match
   ground truth can't corroborate, not a phantom one). Already documented for `extra_functions`
   on rust in #1311/#1319; confirmed to apply identically to `extra_classes` on rust (#1295 PR,
   all 25 `class_start_diff.py` extras after the `union_item` fix traced to this). Not fixable
   without real macro expansion -- document and hand-bless the baseline, same as class 5.

## Parallelizing across languages -- NOT fully independent, unlike epic #1069's per-language files

Each language's `class_start` regex lives in its own block of `language_standards.py`, but three
files are shared touchpoints every language's PR edits:

- `gitgalaxy/core/detector.py`'s `_CLASS_START_NAMED_EXTRACTION_LANGS` frozenset (one shared
  literal -- concurrent edits from different languages collide on the same lines).
- `language_standards.py`'s `<!-- TREE_SITTER_ACCURACY_TABLE:BEGIN/END -->` summary table
  (regenerated wholesale by `--summary-table`, not edited per-language).
- `tests/golden_master_audit.json` / `tests/golden_master_zero_dep_audit.json` (re-blessed
  wholesale by `crucible_check.py --update`, reflects whichever languages' fixes are present in
  the working tree at bless time).

Prefer **one language (or the tiny obviously-related batch of single-digit-extra ones -- html,
objective-c, kotlin, ruby all showed small counts) per PR, merged before starting the next**,
rather than fully concurrent worktree agents the way #1069's strict-signature sweep parallelized.
If concurrency is worth it anyway (e.g. splitting the 6 ground-truth-gap fixes, which don't touch
`language_standards.py` or the allowlist at all, from the regex-hardening languages), keep the
two kinds of work in separate PRs so they don't fight over the same three files.

## Tooling reference

- `python tests/tools/class_start_diff.py --lang <x>` -- offline per-file name diff, the main
  tool for this doc's workflow. `--json` for machine-readable/all-files output, `--max-examples N`
  to control human-readable truncation. Read its own module docstring for the raw-text-vs-shielded
  caveat before trusting its numbers as final.
- `python tests/tools/tree_sitter_accuracy_audit.py --lang <x>` -- the authoritative, baseline-
  gated measurement (goes through the real `galaxyscope` pipeline, including `prism.py`
  shielding). Always the final check before `--regenerate`.
- `python tests/tools/crucible_check.py` -- required before pushing anything that touches
  `language_standards.py` or `detector.py`; confirms the ~80-repo golden master only shows the
  diff you expect.

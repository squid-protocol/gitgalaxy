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
and kotlin are done** (flipped into the allowlist, see the table below); 9 remain.

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
| **zig** | Ground truth already fixed (`ContainerDecl` resolves via `_get_zig_container_name`, walking up to the enclosing `VarDecl`) -- `real_classes` reads 642. **Not yet flipped into the allowlist**: `extra_classes` is 10, `missing_classes` is 23 -- a real per-file diff is needed before concluding whether `class_start` over/under-matches zig's `const X = struct {...}` idiom. Moved to the "ground truth already works" list below.
| **swift** | Fixed (PR #1361): `class_start` had a capture group added (name only had an unparenthesized `[a-zA-Z_]\w*` before), widened to an optional dotted chain for nested-type extensions (`extension AFError.ParameterEncoderFailureReason`). Also hit the ground-truth measurement gap: tree-sitter-swift's protocols are a separate `protocol_declaration` node type, not `class_declaration` -- added to `NODE_MAPS["swift"]["class_node_types"]`. `real_classes` 37→38, `found_classes` 23→38, `extra_classes` stays 0. Flipped into the allowlist. |
| **kotlin** | Fixed (PR #1365): three separate bugs stacked on this one. (1) `class_start` had no capture group -- added group 1 for the main class/interface/object/enum-class branch and group 2 for companion object's own optional name (Fortran/Lua-shaped alternation). (2) `fun interface Foo` (SAM declarations, Kotlin 1.4+) wasn't recognized -- `fun` was missing from the modifier list, a real recall gap confirmed against okhttp's `fun interface Factory`. (3) ground-truth gap: kotlin's `object` declarations (including `actual`/`expect` multiplatform variants) get their own `object_declaration` node type, not `class_declaration` -- added to `NODE_MAPS["kotlin"]["class_node_types"]` and `_get_node_name`. `real_classes` 4→7, `found_classes` 3→7, `extra_classes` stays 0. Golden master updated (okhttp/Call.kt's class count went 1→2). Flipped into the allowlist. |

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

**c** (real_classes=79), **rust** (242), **dart** (167), **ruby** (9),
**haskell** (1, small corpus), **zig** (642, but `extra_classes`=10/
`missing_classes`=23 needs a real per-file diff before concluding what's over/under-matching).
(**swift, kotlin** done -- see the "Done" table above.)

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

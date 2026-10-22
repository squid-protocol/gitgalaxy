---
description: "Crystal (.cr) structural-signature coverage, added for #5623: keyword-scope slicing on ruby's Mode D shape, heredoc rule, limits."
---
# Crystal — Structural Signature Coverage

Snapshot 2026-10-20 against `main` (#5695). Source: `LANGUAGE_DEFINITIONS["crystal"]` in
`gitgalaxy/standards/language_standards/languages/crystal.py`, `tests/extraction/languages/test_crystal_strict.py`.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` (new, first release) |
| `_meta.target_version` | Crystal 1.x (macros, annotations, lib/fun C bindings, fibers and channels) |
| `lexical_family` | `line_exclusive` (`#` comments only; `#{}` interpolation is shielded with the strings) |
| Structural signature keys wired | 54 / 54 rules (plus 2 helper keys, `_calls_out_ignore` and `_dependency_capture`) |
| Function-slicing integration mode | **Mode D (keyword scope, `end`-delimited)**, ruby's shape, own scope entry in `core/detector.py` |
| Strict test file | `test_crystal_strict.py` (13) |

## 2. Identification surface

- **Extension:** `.cr` (unambiguous, no discriminator needed). **Shebang:** `crystal`.
- **Project anchors:** `shard.yml` and `shard.lock` (the shards manifest and lockfile) are discriminators.
- `require "./x"` names a file beside the requiring one (`imports_resolve_from_importer_dir`, ruby's #3553 shape).

## 3. What GitGalaxy detects

`func_start`: `def` and `macro`, optionally `private`/`protected`, `self.` or `Type.` qualified, including operator
methods (`def ==`, `def []`, `def <=>`); a **column-0** `fun name(...) ... end` is a unit too (a C-callable export).
`abstract def` has no body and opens no scope; an indented `fun` inside a `lib` is a bodiless C declaration, not a unit.
`class_start`: `class`, `struct`, `module`, `enum`, `lib`, `annotation`, optionally `abstract`/`private`.
`args` counts a `def`/`macro` parameter list through type restrictions and `Hash(K, V)` generics, block parameters and
`->(x : Int32)` proc literals. `branch` counts `if/unless/elsif/case/when/in/while/until/select`, `&&`, `||` and the
`?:` ternary, not a `foo?` method name. `safety_bypasses`: `not_nil!`, `unsafe_*`, `uninitialized`.
`decorators`: `@[Annotation]`; `reflection_metaprogramming`: `{% %}`, `{{ }}`, hook macros, `@type`.
**Heredocs:** only `<<-ID` / `<<-'ID'` open one; `x << FRACBITS` is a shift or append, not a heredoc (a Crystal-only
opener in `_apply_literal_shield`, since ruby's `<<ID` form would swallow the rest of the file).

## 4. What it does not track

No type inference or overload resolution; no positional invocation model (calls are by name, `calls_out` reuses
`CALLS_OUT_RUBY` with a Crystal keyword ignore list). Macro expansion output is not seen, only the `macro` source.

## 5. Known limitations

- `class_count` is 0: `crystal` is not yet in `_CLASS_START_NAMED_EXTRACTION_LANGS`.
- Units produced by macro expansion (`def {{name}}` inside a `macro`) are not counted as separate functions.
- `shard.yml` / `shard.lock` are classified but not parsed for SBOM.

## 6. Test depth

`test_crystal_strict.py`: `.cr` routing, `def`/`macro` units and the abstract-`def` exclusion, spans following `end`,
a modifier `if` not swallowing the next unit, the shift-versus-heredoc case, column-0 `fun` versus a `lib` `fun`
declaration, class/struct/module discovery, argument counting through type restrictions and generics, `require`
capture, branch/ternary counting, annotations and macro blocks, `not_nil!`, and a ReDoS sweep over every rule.

## 7. Real-world evidence

Scan of `doo-cr` at 4e17635d (from #5695): 41 of 43 `.cr` files mapped (the other 2 are Aperture exclusions), 1509
functions. Grep counts of `def`/`macro`/`fun` match the engine on `am_automap` (35), `p_main` (247) and
`implementation` (642).

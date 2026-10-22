---
description: "F# (.fs/.fsi/.fsx) structural-signature coverage, added for #5623: content-proved .fs routing, offside-rule slicing, limits."
---
# F# — Structural Signature Coverage

Snapshot 2026-10-19 against the #5623 branch. Source: `LANGUAGE_DEFINITIONS["fsharp"]` in
`gitgalaxy/standards/language_standards/languages/fsharp.py`, `tests/extraction/languages/test_fsharp_strict.py`.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` (new, first release) |
| `_meta.target_version` | F# 9 |
| `lexical_family` | `recursive_block` (`//`; nested `(* *)` is not modelled, see §5) |
| Structural signature keys wired | 54 / 54 rules |
| Function-slicing integration mode | **Mode C (indentation / offside rule)**, selected in `core/detector.py` |
| Strict test file | `test_fsharp_strict.py` (16) |

## 2. Identification surface

- **Extensions:** `.fs`, `.fsi`, `.fsx`. **`.fs` is content-decided:** GLSL fragment shaders and Forth also use it.
  F# owns it only when `internal_discriminator` proves F# (`module`/`namespace` header, `open X`, `let` binding with
  `=`, `match ... with`, `type ... =`, `[<Attribute>]`, `|>`). Mechanism as for PostgreSQL (#5622):
  `extensions_needing_discriminator` plus `.fs` in `COLLISION_FREQUENCIES`. F# is the only `.fs` claimant, so
  Tier 3 of `language_lens.py` now drops a proof-only language even when it is the sole candidate: a GLSL or Forth
  `.fs` is `undeterminable`, not won by default.
- **Project file:** `.fsproj` is a discriminator (csharp's `.csproj` precedent), not a source extension.

## 3. What GitGalaxy detects

`func_start`: `let`, `let rec`, `inline`/`private`/`internal`/`public` modifiers, `member`/`override`/`static member`
and `and` heads with a parameter pattern; value bindings (`let x = 42`, `let mutable c = 0`) are not functions.
`class_start`: `type`, `module`, `namespace`, `exception`, `and` + capitalised name. `args` counts a tupled list or a
curried pattern list. `branch` counts `if/elif/match/when/for/while` and match arms (not union-case declarations).
`state_mutation` counts `<-` and `:=` assignments.

## 4. What it does not track

No positional invocation model (F# calls are by name, `unreferenced_by_name`). No type inference, computation
expression or active-pattern semantics.

## 5. Known limitations

- Mode C needs a body line under a unit's header: adjacent one-line `let f x = ...` bindings are not sliced (the
  same limit Haskell has).
- Nested `(* *)` comments stay in the code stream: no lexical family pairs `//` with nested block comments.
- `class_count` is 0: `fsharp` is not yet in `_CLASS_START_NAMED_EXTRACTION_LANGS`.
- Multi-line parameter lists and operator names (`let (+) a b`) are not seen by `func_start`.
- `.fsproj` is classified but not parsed for SBOM/NuGet (`manifest_parser.py` handles `.csproj` only).

## 6. Test depth

`test_fsharp_strict.py`: routing in both collision directions through the real `LanguageDetector`, function shapes
and spans, arg counting, branch / mutation rules, and a ReDoS sweep over every rule.

## 7. Real-world evidence

Scan of `fsharp-doom` at d7bcf5c5 (18 `.fs` files, fetched from GitHub into scratch): 18 / 18 map to `fsharp`;
`function_count` equals the structural `func_start` count on 13 of 15 files with functions (BufferObject 4, Loader 5,
Map 10, Program 3, ...); Shader (8 of 9), Texture (3 of 4) and Timer (3 of 4) lose one single-line unit each (§5); the three
data-only files (Constants, MapPosition, Rgba) have 0.

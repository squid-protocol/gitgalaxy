---
description: "Snapshot generated 2026-10-18 against `main`. Source: LANGUAGE_DEFINITIONS[\"zscript\"]"
---
# ZScript — Structural Signature Coverage

Snapshot generated 2026-10-18 against `main` (issue #5465, slice 2). Source:
`LANGUAGE_DEFINITIONS["zscript"]` in `gitgalaxy/standards/language_standards/languages/zscript.py` and
`tests/extraction/languages/test_zscript_strict.py`. Re-run the `language-status` skill's data-gathering commands
before trusting these numbers if this doc looks old relative to `last_updated` below.

ZScript is the object-scripting language of GZDoom: C#/Java-like classes, structs and enums,
`States {}` / `Default {}` blocks, `Class<T>` / `Array<T>` / `Map<K,V>` generics, `deprecated("..","..")` /
`version("x")` attributes, and `#include "path"`. Identifiers are case-insensitive.

**No tree-sitter ground truth.** The keyword-rosetta control folder (`data/zscript/`) landed separately (#5783).

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | ZScript 4.x (GZDoom) |
| `_meta.blueprint_version` | v5.0 |
| `_meta.last_updated` | 2026-10-18 |
| `lexical_family` | `standard_block` (`//` and `/* */`) |
| Structural signature keys wired | 40 / 57 (17 explicit `None`, see §4) |
| Strict-signature tests (`test_zscript_strict.py`) | 54 |

## 2. Identification surface

- **Extensions:** `.zs` only.
- **Exact filenames / shebangs:** none.
- **Discriminators:** `.zs`.
- **Out of scope:** the root `zscript.txt` lump, DECORATE, MAPINFO, SNDINFO and ACS (`.acs`): data DSLs or a
  different language, no extension to anchor on.

## 3. What GitGalaxy detects

| Key | What it captures for ZScript |
|---|---|
| `func_start` | A method header with a `{` body: modifier run (`override virtual static action play ui clearscope native deprecated(..) version(..) ...`), return type (`void`, `Class<Actor>`, `Array<Array<int> >`, multi-return `int, bool`), name. Bodiless `native`/`abstract` declarations (end in `;`) and call statements never match. |
| `args` | The parameter list of the same header, one level of nested parens. |
| `class_start` | `class`, `struct`, `enum`, plus `extend` / `mixin` forms, with a modifier prefix (`abstract`, `ui`, `play`, `version(..)`). |
| `api` | A method header not marked `private` / `protected` (implicitly public). |
| `branch` | `if else switch case while until for foreach do`, `&&`, `\|\|`, `?`. |
| `safety_bypasses` | `clearscope` / `virtualscope`: stepping out of the play/ui scope sandbox. |
| `io` | `CVar.GetCVar/FindCVar`, `Wads.ReadLump/FindLump/CheckNumForName`. |
| `listeners` | EventHandler callbacks (`WorldTick`, `PlayerEntered`, `RenderOverlay`, ...) with optional `override`/`virtual` and `ui`/`play` prefix. |
| `import` / `_dependency_capture` | `#include "path"` and the quoted path. |
| `events`, `memory_alloc`, `explicit_casts`, `debug_prints`, `panics_and_aborts`, `cleanup`, `bitwise_ops`, `time_date_logic`, `ipc_rpc_bridges`, `system_config_mutation`, `immutability_locks`, `encapsulation`, `planned_debt`, `fragile_debt`, `spec_exposure`, `ownership`, `dead_code`, `state_mutation` | ZScript-specific forms; see the profile's inline comments. `bitwise_ops` requires spaces around `>>` because `Array<Array<int>>` closes with it. |

## 4. Explicit `None` signals (17)

`high_risk_execution` (no process/shell/eval facility in the sandboxed VM), `doc`, `test`, `concurrency`,
`closures`, `ssr_boundaries`, `dependency_injection`, `macros`, `pointers` (object references only), `inline_asm`,
`telemetry`, `thread_sleeps`, `sync_locks`, `test_skip`, `auth_middleware`, `serialization_parsing`,
`regex_execution`. None of these exist in the language.

## 5. Real-corpus check (gzdoom `wadsrc/static/zscript`, 293 files)

Scanned end to end: `.zs` routed to `zscript` for all 293 files. Raw rule counts: `func_start` 2084, `class_start`
2137, `api` 3619, `args` 2103. A grep-based miss check found 0 class misses after the fixes in §6. Zero hits
for `import` (the `#include` lines live in `wadsrc/static/zscript.zs`, outside the scanned directory),
`ownership` and `spec_exposure`. Sample precision of `state_mutation`, `branch` and `api` was not hand-audited.

## 6. Defects found and fixed while building the profile

- `deprecated("3.8", "Use X() instead")`: a `)` inside the string literal ended the attribute early; `_MODS` now
  accepts quoted strings.
- `class Service abstract`, `class X deprecated(..)`, `struct Wads // comment` were missed by a lookahead after the
  name; replaced with `\b`.
- `Class<Actor>` as a return type was excluded by the keyword guard against `class` declarations; the guard now
  skips `class` followed by `<`.
- `listeners` matched 0 on gzdoom (`virtual ui void` prefix); the prefix is now optional-wide.

## 7. Known gaps

- `class_start` names stay empty until `zscript` joins `_CLASS_START_NAMED_EXTRACTION_LANGS` in `detector.py`
  (needs the harden-class-start-extraction pass).
- No `tri_comparison_chart.py` `_GG_ONLY_LANGS` entry.
- No ACS / DECORATE / MAPINFO / SNDINFO support.

---
description: "Snapshot generated 2026-10-18 against `main`. Source: LANGUAGE_DEFINITIONS[\"acs\"]"
---
# ACS (Action Code Script) — Structural Signature Coverage

Snapshot generated 2026-10-18 against `main` (issue #5465, slices 3-4). Source:
`LANGUAGE_DEFINITIONS["acs"]` in `gitgalaxy/standards/language_standards/languages/acs.py` and
`tests/extraction/languages/test_acs_strict.py`.

ACS is the map-scripting language of Hexen, ZDoom and GZDoom (compiled by ACC / BCC / GDCC-ACC): numbered
or named `script` blocks, file-local `function`s, `#include` / `#import` / `#library` / `#define` directives, C-style
control flow and `//`, `/* */` comments. `.acs` is the only extension.

**No tree-sitter ground truth, no cross-language control corpus yet.**

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `lexical_family` | `standard_block` |
| Strictness row | `(static_types=False, enforced_errors=False, memory_safe=True, no_implicit_globals=True)` |
| Strict-signature tests (`test_acs_strict.py`) | see file (rule tables + ReDoS sweep) |

## 2. Identification surface

- **Extensions:** `.acs`. No exact filenames, no shebangs.
- **Out of scope (decision for #5465):** ACS lumps inside WADs / pk3 (`SCRIPTS`, no extension), and the DECORATE /
  MAPINFO / SNDINFO / ZMAPINFO data-definition lumps (no extension to anchor on; they are data DSLs, not code, and
  a `.txt` extension cannot be routed without misclassifying every other text file).

## 3. What GitGalaxy detects

| Key | What it captures for ACS |
|---|---|
| `func_start` | `script <number \| "name" \| word \| << n >>>` headers and `function <type> <name>(` headers. A call statement or a string holding the word `script` never matches. |
| `args` | The parameter list of the same headers. |
| `api` | Every `script` (reachable by number or name from map lines and other scripts). |
| `listeners` | Lifecycle script types: `OPEN ENTER RESPAWN DEATH LIGHTNING UNLOADING DISCONNECT KILL REOPEN RETURN`. The type is read after the name and parameters, so `script "Open Door"` is not an `OPEN` script. |
| `events` | `NET`, `CLIENTSIDE`, `EVENT` scripts. |
| `import` / `_dependency_capture` | `#include "f"` and `#import "f"`, with the quoted path. |
| `macros` | `#define`, `#libdefine`, `#undef`. |
| `structural_boundaries`, `panics_and_aborts` | `terminate` / `restart` end or rerun a script. |
| `concurrency`, `thread_sleeps` | `Delay`, `TagWait`, `PolyWait`, `ScriptWait`. |
| `io`, `system_config_mutation`, `ipc_rpc_bridges`, `ui_framework`, `globals`, `debug_prints`, `cleanup`, `scientific`, `bitwise_ops`, `branch`, `state_mutation`, `dead_code`, `safety` | ACS builtins; see the inline comments in the profile. |

## 4. Explicit `None` signals

`class_start` (no classes or structs), `safety_bypasses`, `high_risk_execution` (no process or eval facility),
`doc`, `test`, `closures`, `generics`, `decorators`, `comprehensions`, `pointers`, `memory_alloc`, `inline_asm`,
`explicit_casts`, `immutability_locks`, `encapsulation`, `telemetry`, `sync_locks`, `ssr_boundaries`,
`dependency_injection`, `test_skip`, `auth_middleware`, `serialization_parsing`, `regex_execution`.

## 5. Real-corpus check

gzdoom `wadsrc/static/strifehelp.acs` (419 lines, the only `.acs` in gzdoom): a scan routes
it to `acs`; its single `script << 0 >> (int type, int tag)` is found (`func_start`, `args`, `api`), as are its
`#include` and two `#define` lines. The file uses the pre-ZDoom `<< n >>` script-number form, which the profile
accepts. Sample precision of `state_mutation`, `branch` and the builtin-name sensors was not hand-audited.

## 6. Known gaps

- `identifier_case` is not declared: ACS identifiers are case-insensitive, but declaring it also needs the
  `test_exactly_the_declared_languages_carry_a_lexicon` literal widened (a sixth hand-written file in this slice).
- No `tri_comparison_chart.py` `_GG_ONLY_LANGS` entry.
- A one-line `script "x" (int t) CLIENTSIDE { ... }` is detected by `func_start` but sliced together with a neighbour
  (the slicer needs the brace on its own line); unverified beyond a synthetic sample.

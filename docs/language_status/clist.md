---
description: "Snapshot written 2026-11-19 for the CLIST language profile (#8625, slices 1-6)."
---
# CLIST — Structural Signature Coverage

Snapshot written 2026-11-19 (#8625, under the legacy-mainframe work). Source:
`LANGUAGE_DEFINITIONS["clist"]` in `gitgalaxy/standards/language_standards/languages/clist.py`,
`tests/extraction/languages/test_clist_strict.py`, `tests/extraction/languages/test_extensionless_rexx_clist_8625.py`
and the CLIST cases in `tests/security_auditing/test_mainframe_secrets_lens_8625.py`. Re-run the
`language-status` skill's data-gathering commands before trusting these numbers if this doc looks old
relative to `last_updated` below.

**Scope note:** CLIST is the z/OS TSO/E Command List language (control statements `PROC`, `SET &x = ...`,
`IF`/`DO`/`SELECT`, `GOTO`, `READ`/`WRITE`, `OPENFILE`/`GETFILE`/`PUTFILE`, `SYSCALL`, plus TSO commands). It is
tree-sitter-blind to this repo's comparison tooling, so there is no ground-truth parser diff and no §9. The pinned
language-crucible corpus carries no CLIST member (both golden masters show zero diff for the profile). No
keyword-rosetta `data/clist` control shell exists yet (see §7), so the rules are validated by the strict suite alone.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | z/OS TSO/E CLIST |
| `_meta.last_updated` | 2026-11-18 |
| `lexical_family` | `standard_block` — `/* */` comments, never nested |
| `invocation_model` | default (`by_name`): `GOTO label` and `SYSCALL name` reach labels by writing their names, so the `unreferenced_by_name` census applies |
| Structural signature keys wired | 24 live rules, 31 explicit `None` (see §4) |
| Strict-signature tests (`test_clist_strict.py`) | 52 |
| Routing tests (`test_extensionless_rexx_clist_8625.py`) | extensionless REXX and CLIST members, both directions |

## 2. Identification surface

A CLIST member has no extension on z/OS; a repository checkout that keeps one names it `.clist`
(`extensions: [".clist"]`). Extensionless members route (slice 4, #8648) by:

1. **Dataset-qualifier directory** — `library_directory_suffixes` `clist`, `clistlib`, `sysproc`
   (`USER.CLIST/MEMBER`, `SYS1.SYSPROC/MEMBER`), then `language_lens._CLIST_MEMBER_SHAPES`; or
2. **Body alone** in an ordinary directory.

The body test needs at least two distinct CLIST-only statement shapes (`PROC n`, `CONTROL NOMSG`-style, `SET &X =`,
`WRITE`/`READ` of an `&` variable, a `&SYSxxx` function), so shell, Pascal and Perl text with one coincidental shape
does not route. A REXX exec in a CLIST library stays REXX when its first line comments `REXX`. Ecosystem anchors
(`discriminators`): `.clist`, `.jcl`, `.rexx`, `.exec`. `case_insensitive_imports: True`.

## 3. What GitGalaxy detects

A CLIST symbol is letters, digits and `@ # $ _`; the national characters are regex non-word characters, so
every keyword rule carries explicit guards (`(?<![\w@#$&])` / `(?![\w@#$])`) rather than a bare `\b`.

### Topology
- **`func_start`** — a label `name:` at a line start (what `GOTO` and `SYSCALL` reach).
- **`args`** — the parameter list of `PROC n positional keyword(default)`.
- **`calls_out`** — `%name` (run another member) and `SYSCALL name`; the callee is group 1.
- **`class_start`** — `None`: no named-type declaration.
- Unit extraction runs through **Mode A** (label runs to `RETURN`/`EXIT` or the next label), the REXX slot. Before
  slice 5 (PR #8649) a CLIST member produced zero units (it fell through to the brace slicer).

### Logic and risk
- **`branch`** — `IF`, `ELSE`, `WHEN`, `OTHERWISE`, and the loop openers `DO WHILE` / `DO UNTIL` / `DO &I = ...`; a plain
  `DO` is a group, not a branch.
- **`safety`** — `ERROR DO|ACTION`, `ATTN DO|ACTION` (the handlers) and `&LASTCC` / `&MAXCC`.
- **`safety_bypasses`** — `ERROR OFF`, `ATTN OFF`, `CONTROL ... NOFLUSH`, and `GOTO` (the unstructured jump).
- **`high_risk_execution`**, **`panics_and_aborts`** — `EXIT` (ends the whole member, even from a sub-procedure).
- **`io`** — `READ`, `READDVAL`, `WRITE`, `WRITENR`, `OPENFILE`, `GETFILE`, `PUTFILE`, `CLOSFILE`.
- **`state_mutation`** — `SET &x`, CLIST's only assignment. **`cleanup`** — `FREE`, `CLOSFILE`.
- **`debug_prints`** — `WRITE` / `WRITENR`. **`telemetry`** — `CONTROL LIST|CONLIST|SYMLIST|MSG`.
- **`ui_framework`** — `ISPEXEC DISPLAY|ADDPOP|REMPOP|SETMSG|PQUERY|LMDDISP|TBDISPL`.
- **`globals`** — `GLOBAL` and `&SYSxxx` ambient variables; **`time_date_logic`** — `&SYSDATE|TIME|JDATE|SDATE`.
- **`ipc_rpc_bridges`** — `%name` and `EXEC`.
- **Documentation/debt** — `doc` (`/* PURPOSE:` and kin), `ownership` (`/* Author:` and kin), `dead_code` (commented-out
  `SET` / `IF` / `GOTO` / `SYSCALL`), shared planned/fragile debt, `spec_exposure`.

### Case folding
`identifier_case: insensitive` (top level, never inside `rules`) makes `SYSCALL clean_up` reach `CLEAN_UP:` in the
`unreferenced_by_name` census (slice 5, PR #8649, open when this was written; pinned in `test_unreferenced_by_name_contract_2806.py`).

### Security lens
CLIST is a mainframe-scope language for the security lens (slice 5, PR #8649, `_MAINFRAME`): `IKJEFT01`, `BPXBATCH` and `IRXJCL`
are execution vectors in a CLIST, and mainframe credential shapes in a `.clist` member are counted as
`hardcoded_secrets` (#8645). The per-language `hardcoded_secrets` rule is deliberately `None`; the lens owns it.

## 4. Explicit `None` keys (31)

`_dependency_capture`, `api`, `auth_middleware`, `bitwise_ops`, `class_start`, `closures`, `comprehensions`,
`concurrency`, `decorators`, `dependency_injection`, `encapsulation`, `events`, `explicit_casts`, `generics`,
`hardcoded_secrets` (security lens), `immutability_locks`, `import`, `inline_asm`, `listeners`, `macros`, `memory_alloc`,
`pointers`, `reflection_metaprogramming`, `regex_execution`, `scientific`, `serialization_parsing`, `ssr_boundaries`,
`sync_locks`, `system_config_mutation`, `test`, `test_skip`, `thread_sleeps`. A CLIST has no import mechanism (so no
dependency edges from `_dependency_capture`), no types, threads or tests; the strict suite pins that these stay `None`.

## 5. Test depth

`test_clist_strict.py` (52 cases): a positive and a near-miss negative for every live rule, a guard that no live rule
lacks a case, the `None`-key set, registration, case-blind matching, `calls_out` group capture, the `DO` group-versus-loop
split, `GOTO` / `ERROR OFF` as bypass, comment shielding through the prism, and a ReDoS payload per unbounded shape.

## 6. Known limits

- No import graph: `%name` and `SYSCALL name` are `calls_out` only; no cross-member dependency edge is built.
- Not run on a real CLIST estate: the only evidence is invented fixtures. Scan evidence will come with the
  keyword-rosetta control shell.

## 7. Not yet done (#8625)

keyword-rosetta `data/clist` and its `_GG_ONLY_LANGS` entry (companion PR in the rosetta repo).

## 8. Closed work that shaped it

#8645 (profile, `.clist` credentials), #8641 (SecurityLens mainframe shapes, `.proc`), #8648 (extensionless routing),
#8649 (Mode A label slicer, `identifier_case`, security scope).

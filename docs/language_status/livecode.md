# LiveCode (LiveCode Script + LiveCode Builder)

## 1. At a glance

| Metric | Value |
| :--- | :--- |
| **Status** | production |
| **Target Version** | LiveCode 9.6 / 10.0 (Current Stable/DP) |
| **Lexical Family** | multi_style_live (`--`, `//`, `#`, `/* */`) |
| **Rules Wired** | 47 / 52 |
| **Extraction tests** | 4 parametrized cases in `test_livecode.py` (~85 payloads, incl. `.lcb` `handler`) |
| **Strict tests** | 29 in `test_livecode_strict.py` (109 collected) |
| **Detector routing** | Mode D (keyword depth-tracking) — `ScopeParsingRegistry["livecode"]` |
| **Comparison tools** | none — no tree-sitter grammar, no ctags parser (one of ~14 gg_only languages) |

## 2. Identification surface

- **Extensions**: `.lc`, `.livecodescript`, `.lcb`, `.livecode`, `.stack`, `.rev`
- **Exact matches**: (none)
- **Discriminators**: `.lc`, `.livecode`, `.lcb`, `.livecodescript`
- **Shebangs**: `livecode-server`

Two distinct dialects share this config: **LiveCode Script** (the HyperTalk-derived
`.livecodescript` / `.lc` form — `on`/`command`/`function` handlers, `end <name>`
terminators, unparenthesized `command Foo pA, pB` parameters) and **LiveCode
Builder** (the typed, compiled `.lcb` form — `module com.x.y`, `handler Foo(in x
as String)` with parenthesized typed parameters).

## 3. What GitGalaxy detects

**Topology & Structure**
- `branch`: `if`/`then`/`else`/`switch`/`case`/`repeat`/`while`/`until`/`try`/`catch`/`throw`, plus `and`/`or`/`not`.
- `func_start`: handler headers in both dialects — LiveCode Script `on`/`command`/`function`/`getprop`/`setprop <name>` and LiveCode Builder `.lcb` `handler <name>(…)` (with optional `private`/`public`). `foreign handler` FFI binding declarations and `handler type <Name>()` typedefs are excluded. Routed to detector Mode D (keyword depth-tracking) — LiveCode has no braces.
- `args`: the parameter list following a handler header — LiveCode Script's unparenthesized `pA, pB` and LiveCode Builder's parenthesized, typed `(in x as String, out y as Integer)`.
- `class_start`: object/entity declarations — `.livecodescript` `script "Name"` (quoted export header), `.lcb` `module`/`widget`/`library`/`behavior` (bareword, incl. dotted reverse-DNS).
- `structural_boundaries`: xTalk verbs (`put`, `get`, `set`, `send`, `dispatch`, `pass`, `return`, arithmetic commands, `visual effect`, `play`, `sort`, `find`, `replace`).

**Safety & Risk**
- `safety`: `try`/`catch`/`finally`/`throw`, `lock screen`/`lock messages`/`lock errordialogs`, `assert`, `strict compilation`, `is a`/`is strictly`.
- `safety_bypasses`: `disable messages`, `unlock screen`/`unlock messages`, `global`, raw `do <expr>`.
- `high_risk_execution`: `answer`/`ask` (blocking UI), `do` (dynamic eval), `delete file`/`folder`/`url`, `quit`, `exit to top`.

**Resource Management**
- `io`: `open`/`read from`/`write to`/`close` file/socket/process, `get url`/`put url`/`post ... to url`/`load url`.
- `concurrency`: `send ... in ... seconds`, `wait ... with messages`, `dispatch`, `pendingMessages`, `cancel`.
- `cleanup`: `delete variable`, `close file`, `stop using`, `remove script`.

**State & Architecture**
- `state_mutation`: `put ... into/after/before`, `set the <prop> to`, `add ... to`, `subtract ... from`.
- `import` / `_dependency_capture`: `start using stack`/`start using behavior`, `require`, `include`, `module`.
- `dependency_injection`: `set the behavior of`, `insert script into front/back`.
- `events` / `listeners`: `on mouseUp`/`openCard`/`openStack`/`rawKeyDown`/… message handlers.
- `ownership`: `-- Author:` / `Created by:` / `Maintainer:` / `Copyright:` comments.

**Domain Sensors** (abridged): `ui_framework`, `reflection_metaprogramming`, `serialization_parsing`,
`regex_execution`, `time_date_logic`, `ipc_rpc_bridges`, `bitwise_ops`, `telemetry`, `scientific`,
`comprehensions` (`repeat for each …`, `filter … with …`), `ssr_boundaries` (`<?lc … ?>`), `test`
(`command testX`, `Levure`, `LcU`).

## 4. What GitGalaxy explicitly does not track

- `closures`: None (LiveCode has no closure literal).
- `generics`: None.
- `macros`: None.
- `memory_alloc`: None (no manual allocation).
- `inline_asm`: None.

## 5. Known limitations (filed, not yet fixed)

None currently. All of livecode's `func_start` / `class_start` extraction gaps found by the
tri-comparison manual-verification sweep are fixed:
[#2409](https://github.com/squid-protocol/gitgalaxy/issues/2409) /
[#2410](https://github.com/squid-protocol/gitgalaxy/issues/2410) (Mode-D routing + `.lcb`
handlers), [#2419](https://github.com/squid-protocol/gitgalaxy/issues/2419) (string-escape shield),
and [#2411](https://github.com/squid-protocol/gitgalaxy/issues/2411) (leading UTF-8 BOM stripped
at ingestion — un-blocked 39 `.livecodescript` `script "Name"` declarations, corpus-wide fix
across 6 languages). See §9.

## 6. Test depth

- **Extraction-gauntlet tests**: `tests/extraction/languages/test_livecode.py` — `func_start`,
  `class_start` (incl. the quoted-name branch), `args` (incl. the multi-line `re.M` anchor
  regression), `_dependency_capture`.
- **Strict-signature tests**: `tests/extraction/languages/test_livecode_strict.py` — 109
  ReDoS-immunity / trailing-boundary / vertical-formatting cases, plus the
  `class_start` dotted/quoted-name and `args` multi-line regressions from the 2026-08-28
  manual-verification pass.

## 7. Relevant closed work

- **Epic-level hardening passes**:
  - [#851](https://github.com/squid-protocol/gitgalaxy/issues/851): Extraction hardening: livecode
  - [#593](https://github.com/squid-protocol/gitgalaxy/issues/593): Strict parsing tests: `livecode` structural signatures — a systematic sweep that fixed multiple trailing-`\b`/space-excluding-quantifier bugs across `io`, `state_mutation`, `safety_bypasses`, `class_start`, `doc`.
  - [#708](https://github.com/squid-protocol/gitgalaxy/issues/708): livecode's real comment styles (`--`, `#`) weren't in the delimiter table — comments leaked into the code stream.

## 8. Real-world evidence

- [`livecode`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.6/livecode/livecode_galaxy_llm.md) — a full scan of the LiveCode Script + Builder standard-library corpus.

## 9. Manual verification (no comparison tool)

LiveCode has neither a tree-sitter grammar nor a ctags parser, so the tri-comparison tool has
nothing to reconcile against — its precision and recall are established by **direct source
cross-check** instead, on the `../language-crucible/data/livecode` corpus (99 code files: 63
`.livecodescript` LiveCode Script, 35 `.lcb` LiveCode Builder, 1 dropped for size on each side →
97 ingested).

### Method

For each signature: (1) run the raw `func_start` / `class_start` / `args` regex directly against
every corpus file's text and record every match with its line and captured text; (2) run the real
`galaxyscope --db-only` pipeline and compare the DB's raw structural signal (`struct_*`) and its
NAMED list (`function_data` / `class_data`) against that; (3) establish ground truth by reading
the actual declaration lines. Step 2 is where three real engine defects surfaced that step 1
alone would have missed.

### Results

| Signature | Raw regex | Pipeline `struct_*` | Named list | Verdict |
| :--- | ---: | ---: | ---: | :--- |
| `class_start` | 34 → **57** | 33 → **57** | 0 → **97** | ✅ **97/97 precision, 0 false positives, 0 missed** — badge earned (0→57 in the 2026-08-28 pass; 57→58 via #2415; 58→**97** via #2411's BOM strip, all verified) |
| `args` (file signal) | 0 → **471** | 0 → **442** | — | signal alive; per-function count fixed by #2410 (see 2026-08-29 subsection) |
| `func_start` | 847 | 781 → **~960** | 1 → **964** | raw signal was always correct; named extraction fixed by #2409 + #2410 + #2419 (see 2026-08-29 subsection) |

(`struct_*` < raw regex in every row is correct: `prism.py` legitimately strips `func_start`/
`args`-shaped lines that sit inside `/* … */` doc/comment blocks — 32 in
`revsaveasandroidstandalone.livecodescript`'s commented-out block, 29 args lines likewise. Not a
defect; verified by locating every one.)

### Fixes shipped in this pass

1. **`args` regex was compiled `re.I` only, missing `re.M`** (`language_standards.py`). The
   pattern is `^`-anchored per-line exactly like its `func_start` sibling, so without `re.M` the
   `^` matched only the start of the file — **0 `args` matches across the entire corpus** (every
   file has a license header before its first handler). One-flag fix; the pattern itself was
   already correct on a single line, which is why every prior single-line test missed it. Added
   `test_livecode_args_multiline_anchor_regression`.
2. **`class_start` captured barewords only** (`language_standards.py`). `.livecodescript` object
   exports open with `script "Name"` (quoted) — the dominant form for the Script half of the
   corpus. Added a real quoted-name capture branch (`"([^"\r\n]{1,200})"`) as its own alternation
   arm, next to the existing bareword/dotted branch for `.lcb` `module com.x.y`.
   `_resolve_class_start_match` in `detector.py` already handles the group-1-or-group-2 shape
   (same as fortran/lua/abap).
3. **livecode was missing from `_CLASS_START_NAMED_EXTRACTION_LANGS`** (`detector.py`). Even with
   the regex fixed, the named class list stayed empty (the generic fallback regex is lowercase
   `class|struct|interface|trait|enum`, which never matches `script`/`module`). Added.

### What "97/97" means

`97/97` is a **precision AND recall** record: every class object GitGalaxy claims maps to a real
declaration line, and — after [#2411](https://github.com/squid-protocol/gitgalaxy/issues/2411)
stripped the leading UTF-8 BOM at ingestion — there are **no more missed `.livecodescript`
objects**. Forms: `.livecodescript` `script "Name"` + `.lcb` `module com.x.y` (bareword
reverse-DNS); `map.lcb`'s `module` line is commented out and correctly not counted. Verified by a
string-aware independent scanner + full name-diff over all 98 files.

### 2026-08-29: BOM strip — [#2411](https://github.com/squid-protocol/gitgalaxy/issues/2411)

`galaxyscope.py`'s content read used `encoding="utf-8"`, so a leading BOM (`EF BB BF`) stayed as
the first character of the buffer and every `^`-anchored line-1 signal rule silently failed on
that file. 39 `.livecodescript` files in the corpus open with `﻿script "Name"` on line 1;
switching the read to `utf-8-sig` un-blocks all of them (livecode `class_start` 58 → 97, every
one verified). Corpus-wide fix — 58 BOM files across 6 languages — but livecode is the only one
where line 1 carries a named signal, so at the tri-comparison level it's the only visible change.

### 2026-08-29: `func_start` recovered — [#2409](https://github.com/squid-protocol/gitgalaxy/issues/2409) + [#2410](https://github.com/squid-protocol/gitgalaxy/issues/2410)

The `func_start` row above ("named list: **1**") is now fixed. Two changes, one PR:

1. **`detector.py` Mode D routing (#2410).** LiveCode had no `ScopeParsingRegistry` entry, so it
   fell through to Mode B brace-slicing — which finds no `{`/`}` and produced **one**
   `FunctionNode` for the entire 98-file corpus despite 781 correct raw `func_start` signals.
   Added a `mode_d` entry: statement-anchored openers (`on`/`command`/`function`/`getprop`/
   `setprop`/`handler` + `repeat`/`if`/`switch`/`try`/`unsafe`), a bare `end` closer, and a
   `function_opener` for nested-handler detection. Anchoring makes `next repeat` / `exit repeat`
   / `else if` / `else` fall out for free; a dedicated `_slice_by_keywords` guard handles the
   `if COND then <statement>` one-liner (no `end if`). Same routing-only failure class as
   MATLAB #1266 / yacc #2351.
2. **`language_standards.py` `.lcb` `handler` regex (#2409).** `func_start` / `args` only knew
   LiveCode Script's unparenthesized `on|command|function… <name>` form. Added a second
   alternation arm for LiveCode Builder's `[public|private] handler <name>(…)` — parenthesized,
   typed. `foreign handler` (344 FFI binding declarations, C-prototype shaped, no body) and
   `handler type <Name>()` (function-pointer typedefs) are excluded by construction.

**Verification (string-aware independent-scanner name-diff, whole corpus).** Ground truth = every
real handler *definition* header, from an independent scanner that shares no implementation with
`func_start` and does its own string-aware `/* */` + line-comment removal. Result after
[#2419](https://github.com/squid-protocol/gitgalaxy/issues/2419) landed: **964 truth defs, 964 GG
named funcs, ZERO missing, ZERO extra, ZERO truncation markers anywhere in the corpus.**

| Signature | before #2409/#2410 | after #2409/#2410 | after #2419 |
| :--- | ---: | ---: | ---: |
| `func_start` named list | 1 | 934 (1 truncated) | **964** (0 truncated) |
| `func_recall` matched_consensus (Func Found panel) | 1 | 934 | **964** |
| `func_precision` total_slots | 1 | 934 | **964** → `964/964**` + **G** badge |
| `gg_args_found` (Args Found panel) | 2 | 950 | **~990** |

**#2419 (fixed in the same sweep, own PR).** prism's `multi_style_live` string mask (and the
detector Mode-D shield's) was C-escape-aware, so `"\"` — a real one-character LiveCode string
containing a backslash (`replace quote with "\" & quote`) — was misread as an escaped quote,
desyncing quote pairing until a `/*` inside a later string literal (`"Android/*"`) opened a bogus
block comment that blanked ~30 real handlers in one 2183-line file. LiveCode has **no** `\`
string escapes; the mask is now single-line, `"`-only, non-escaping. Both the earlier `934` count
*and its verification* undercounted for the same reason — corrected to `964`.

**Chain:** livecode gauntlet + strict + prism + detector (303 passed) · full
`tests/core_engine/` + `tests/extraction/` · `audit_check.py` clean (ruff / mypy / dead-key /
ast-accuracy) · `crucible_check.py` full corpus — **every diff is livecode or its downstream
ripple**, zero unrelated-language diffs (`multi_style_live` is livecode-only; the Mode-D shield
change is `lang_id == "livecode"`-gated) · both golden masters re-blessed and re-verified `PASS`.
`tri_comparison_chart.svg` is regenerated by the post-merge `tri-comparison-history.yml` job, not
here.

See `docs/self_scan/manual_verification.json`'s `"livecode"` entry for the record in the same
format abap / agc_assembly / dockerfile / jcl use.

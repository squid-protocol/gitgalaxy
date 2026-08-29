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

- **[#2419](https://github.com/squid-protocol/gitgalaxy/issues/2419) — `_apply_literal_shield`
  treats `/*` / `*/` inside a LiveCode string literal as a block-comment delimiter.** Exactly one
  handler in the corpus (`addExternalFromFile` in the 2183-line
  `revsaveasandroidstandalone.livecodescript`, which has `"Android/*"` and `"*/R.java"` string
  literals) over-extends its body because its own `end` lines fall inside a bogus comment span.
  A narrow shield edge, not a Mode D gap — every other handler slices cleanly; does not affect
  the 934/934 handler-*existence* count (§9).
- **[#2411](https://github.com/squid-protocol/gitgalaxy/issues/2411) — a leading UTF-8 BOM
  defeats `^`-anchored line-1 extraction.** 38 real `.livecodescript` class objects (of 95) are
  missed purely because `head -1` is `﻿script "Name"` and `^[ \t]*` will not step over the BOM.
  A general engine gap (58 BOM files across 6 languages in the corpus), not a livecode
  `class_start` defect.

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
| `class_start` | 34 → **57** | 33 → **57** | 0 → **57** | ✅ **57/57 precision, 0 false positives** — badge earned |
| `args` (file signal) | 0 → **471** | 0 → **442** | — | signal alive; per-function count fixed by #2410 (see 2026-08-29 subsection) |
| `func_start` | 847 | 781 → **~900** | 1 → **934** | raw signal was always correct; named extraction fixed by #2409 + #2410 (see 2026-08-29 subsection) |

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

### What "57/57" means, and what it doesn't

`57/57` is a **precision** record: of the 57 class objects GitGalaxy claims, every one was
checked against its declaration line and is correct (24 `.livecodescript` `script "Name"` + 33
`.lcb` `module`; `map.lcb`'s `module` line is commented out and correctly not counted). GitGalaxy
separately has a **recall** gap — 38 more real `.livecodescript` objects exist (95 real total)
that it misses entirely because of the leading-BOM issue [#2411](https://github.com/squid-protocol/gitgalaxy/issues/2411).
That gap is visible in the chart's unranked "Classes Found" panel (`57`), not in the precision
number, and it is an engine-wide `^`-anchor gap rather than a livecode `class_start` defect.

### Verification chain run

livecode extraction gauntlet + strict tests (113 passed) · core-engine suite (674 passed) ·
`audit_check.py` (ruff / mypy / dead-key / ast-accuracy all clean against baseline) ·
`crucible_check.py` against the full ~80-repo corpus (all ~290 diffs are livecode-only:
`Function Parameters` 0 → real, `Class/Entity Declarations` 0 → 1, and the topological /
structural-magnitude ripple that recomputes from the corrected counts — zero diffs in any other
language; livecode's global mass share rises ~6× purely because a whole language's `args` signal
went from artificially-zero to real) · both golden master fixtures re-blessed ·
`tri_comparison_chart.py --all --write` regenerated (livecode Class Precision now renders
`57/57**` with a **G** badge).

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

**Verification (independent-scanner name-diff, whole corpus).** Ground truth = every real handler
*definition* header (an independent line scanner sharing no implementation with `func_start`,
skipping `end`/`foreign handler`/comments). Result: **934 truth defs, 934 GG named funcs, 1
missing / 2 extra before a `handler type` guard was added → 934 / 934, zero false positives, zero
missed** after it. `.livecodescript`: ~815 handlers; `.lcb`: 121 real `handler` definitions.

| Signature | before | after |
| :--- | ---: | ---: |
| `func_start` named list | 1 | **934** (933 clean + 1 `_[Truncated]`, see #2419) |
| `func_recall` matched_consensus (Func Found panel) | 1 | **934** |
| `func_precision` total_slots | 1 | **934** → `934/934**` + **G** badge |
| `gg_args_found` (Args Found panel) | 2 | **950** |

**One body-extent limitation, filed as [#2419](https://github.com/squid-protocol/gitgalaxy/issues/2419)**,
does not affect the existence count: `addExternalFromFile` (in the 2183-line
`revsaveasandroidstandalone.livecodescript`) is the only truncation in the corpus, caused by
`_apply_literal_shield` mis-reading `/*` / `*/` inside that file's string literals.

**Chain:** livecode gauntlet + strict (113 passed) · new `test_detector_mode_d_livecode_*` (2) ·
full `tests/core_engine/` + `tests/extraction/` (6803 passed) · `audit_check.py` clean
(ruff / mypy / dead-key / ast-accuracy) · `crucible_check.py` full corpus — **every diff is
livecode or its downstream ripple**, zero unrelated-language diffs (livecode's global mass share
*drops* ~18× as its one monster function splits into ~934 correctly-sized ones; `dominant_language`
corrects `livecode` → `c`) · both golden masters re-blessed and re-verified `PASS`.
`tri_comparison_chart.svg` is regenerated by the post-merge `tri-comparison-history.yml` job, not
here.

See `docs/self_scan/manual_verification.json`'s `"livecode"` entry for the record in the same
format abap / agc_assembly / dockerfile / jcl use.

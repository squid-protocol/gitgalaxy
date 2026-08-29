# Lua — Structural Signature Coverage

Snapshot generated 2026-08-29 against `main`. Source: `LANGUAGE_DEFINITIONS["lua"]` in
`gitgalaxy/standards/language_standards.py`, `tests/extraction/languages/test_lua.py` /
`test_lua_strict.py`, closed GitHub issues, and the tri-comparison ledger. Re-run the
`language-status` skill's data-gathering commands before trusting the §1–8 numbers if this doc
looks old relative to `last_updated` below.

**Scope note:** §9 was written by the `tri-comparison-ledger-sweep` skill and is the part of this
doc with the most recent, most detailed investigation behind it — a real 3-way
GitGalaxy / tree-sitter-lua / Universal-Ctags comparison on the `language-crucible` corpus, with
two engine defects found and fixed in the same pass. §§1–8 are the standard primary-source
snapshot.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | Lua 5.5 / Luau / LuaLS Annotations / LuaJIT |
| `_meta.blueprint_version` | v5.0 |
| `_meta.last_updated` | 2026-08-29 |
| `lexical_family` | `multi_style_dash` (`--` line comments, `--[[ ]]` long comments) |
| Structural signature keys wired | 50 / 52 (2 explicit `None`: `macros`, `inline_asm`) |
| Function-slicing integration mode | **Mode D (keyword handshake stack)** — `function`/`if`/`while`/`for`/`repeat` open, `end`/`until` close |
| Extraction-gauntlet + strict test files | `test_lua.py` (41), `test_lua_strict.py` (78) — 119 passing |

## 2. Identification surface

- **Extensions:** `.lua`, `.luau`, `.nse` (Nmap scripts), `.pd_lua` (Pure Data), `.wlua`
  (wxLua), `.rockspec` (LuaRocks package specs).
- **Exact filenames:** `config.ld` (LDoc config).
- **Discriminators:** `.lua`, `.luacheckrc`, `stylua.toml`, `.rockspec` — a Lua file almost
  always sits next to at least one of these in a real project.
- **Shebangs:** `lua`, `luajit`, `luau`, `texlua`.

## 3. What GitGalaxy detects

`func_start` targets a real named function declaration head —
`^ (local )? (export )? function <name> (` — where `<name>` may be dotted or method-style
(`function a.b.c()` / `function obj:method()`) and an optional Luau generic list
(`function f<T>(...)`) is stepped over before the parameter `(`. `args` counts the parenthesised
parameter list on that same head. `class_start` is a deliberate best-effort heuristic for Lua's
two "type-shaped" idioms: a LuaLS `---@class Name` annotation, or a Capitalised name assigned a
table literal (`Account = {`) — Lua has no `class` keyword, so this is the closest analog the
cross-language schema has (see §9 for what that costs in precision). The remaining 47 wired keys
(branch, io, safety, memory_alloc, closures, coroutines via `concurrency`, `bitwise_ops`,
`reflection_metaprogramming`, …) run against the function bodies and module scope.

## 4. What GitGalaxy explicitly does not track

Two keys are wired to `None`:

- `macros` — Lua has no C-style preprocessor.
- `inline_asm` — no inline-assembly construct.

Everything else in the 52-key schema is wired. `class_start` is **not** `None` (unlike most
keyword-less languages) — it is a heuristic on purpose, for schema comparability; §9 covers the
tradeoff.

## 5. Known limitations (accepted / tracked)

- **Mid-file Mode-D keyword desync** ([#2437](https://github.com/squid-protocol/gitgalaxy/issues/2437)).
  A keyword used as a plain identifier, or a structurally hard construct the literal shield
  doesn't fully neutralise, can leave one scope open so a single oversized `<name>_[Truncated]`
  satellite spans to a far-away `end` and swallows the real declarations inside it. #2405's
  blast-radius containment re-scans the EOF remnant, and this pass removed the two most common
  desync sources (see §9), but a desync whose scope *does* eventually close mid-file still
  produces one bad satellite. ~6 corpus occurrences remain (`binarytrees.lua`, `events.lua`,
  `fetch.lua`, `maxmind.lua`).
- **Dotted / method-style declaration heads not fully name-resolved in the nested pass**
  ([#2438](https://github.com/squid-protocol/gitgalaxy/issues/2438)). The `function_opener`
  second pass (§9) recovers nested `function` declarations, but its line-start pattern doesn't
  yet widen to `function a.b.c:f()` / `function a:deep()` heads, so a handful of deeply-nested
  dotted declarations are still missed.
- **`class_start` heuristic over-matches ALL_CAPS data tables**
  ([#2439](https://github.com/squid-protocol/gitgalaxy/issues/2439)). `[A-Z]\w* = {` also
  catches Capitalised *data* tables (`redis/life.lua`'s Conway's-Game-of-Life cell patterns
  `FISH` / `EXPLODE` / `BUTTERFLY`; one/two-letter test fixtures). No ground-truth tool can
  corroborate or refute a Lua "class" (§9), so this is a precision question on GitGalaxy's own
  heuristic, tracked for tightening.

## 6. Test depth

- **Extraction-gauntlet tests:** 41 cases in `tests/extraction/languages/test_lua.py`
  (`func_start` / `args` / `class_start` / `_dependency_capture`, valid / invalid / pathological).
- **Strict-signature tests:** 78 cases in `tests/extraction/languages/test_lua_strict.py` (ReDoS
  immunity, scaling-ratio methodology, boundary correctness).

## 7. Relevant closed work

- [#832](https://github.com/squid-protocol/gitgalaxy/issues/832) — extraction hardening: lua.
- [#594](https://github.com/squid-protocol/gitgalaxy/issues/594) — strict parsing tests for
  `lua` structural signatures.
- [#621](https://github.com/squid-protocol/gitgalaxy/issues/621) — `standard_block` comment
  stripping only covered C-style delimiters; lua (among others) got zero comment/code separation
  until `multi_style_dash` handling landed.
- [#1070](https://github.com/squid-protocol/gitgalaxy/issues/1070) — ReDoS regression tests for
  6 languages with no coverage, lua included.

## 8. Real-world evidence

The tri-comparison corpus is `language-crucible/data/lua/` — 109 files / ~620 real functions
across `cosmopolitan` (the Lua 5.4 test suite, heavily nested and adversarial by design),
`pandoc` (Lua filters / custom readers), `redis` (embedded scripting), and
`freebsd-src` (`flua` system scripts).

## 9. Tri-comparison: GitGalaxy vs. tree-sitter-lua vs. Universal Ctags

**Summary.** All **8** discrepancy shapes the tri-comparison tool flagged for Lua were
investigated and marked `validated` in one pass (2026-08-29) via the
`tri-comparison-ledger-sweep` skill. Two were confirmed GitGalaxy engine defects and **fixed in
the same pass**; the rest are tool-architecture differences or absences with no privileged ground
truth. Net effect of the fixes, measured by `tree_sitter_accuracy_audit.py --lang lua`:

| Metric | Before | After |
|---|---:|---:|
| `found_functions` | 505 | **557** |
| `extra_functions` (lower is better) | 12 | **7** |
| `args_exact_match` | 463 | **516** |
| Named-function extraction (gather total) | 517 | **564** |

Both golden masters were re-blessed and `tests/tree_sitter_accuracy_baseline_lua.json` regenerated
in the same PR.

### Confirmed engine defects, both fixed

**1 — Mode-D recall gap: nested `function` declarations folded into the enclosing satellite**
(shape `lua/function/existence/agree[ctags,tree_sitter]_vs[gitgalaxy]`, was ~82 occurrences).
The same `#1262` class of bug Ruby had ("0/117 real methods detected"). GitGalaxy's `func_start`
regex matched every one of these in isolation, but `_slice_by_keywords`' stack-depth scan only
ever emits the *outermost* open scope's satellite, so a `function` / `local function` declared
inside a `do` block, nested in another function's body, or after a keyword-count desync was
folded into the enclosing satellite instead of getting its own `FunctionNode`. Fixed by giving
Lua a `function_opener` entry in `detector.py`'s `ScopeParsingRegistry` — a second,
nesting-independent pass over every real declaration line, exactly Ruby's own `#1262` mechanism,
gated on the key so `shell`/`vb`/`elixir` (no corpus audit yet) keep their existing behavior.

**2 — literal shield mis-tokenised Lua's `#` and `//`, and ignored long-bracket literals**
(fed shape 1 above and shape `lua/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`,
the `_[Truncated]` artifacts). `_apply_literal_shield` used the shared default comment-marker set
`#|--|//` for Lua, but `#` is Lua's length operator and `//` is floor division (5.3+) — so
`for i = 1, #arg do ... end` was truncated at the `#` as a bogus "comment", dropping the
`do ... end`'s closing `end` from the keyword count (a +1 desync per vararg loop). It also did
not shield Lua long-bracket literals `[[ ... ]]` / `[=[ ... ]=]` / `--[[ ... ]]` at all, so
`function` / `for` / `end` tokens inside string and long-comment bodies
(`gc.lua`'s `local prog = [[ ... function foo(x,y) ... ]]`, `coroutine.lua`'s
`T.testC(state, [[ ... # get function for body ... ]])`) corrupted the depth stack and were
mis-sliced as real declarations. Fixed with a Lua branch: `comment_markers = "--"` only, plus a
dedicated long-bracket sub (`(?:--)?\[(=*)\[.*?\]\1\]`) run before the quote pass.

### Where the other tools have real, documented gaps

- **Universal Ctags over-detects massively** (shape
  `lua/function/existence/agree[ctags]_vs[gitgalaxy,tree_sitter]`, ~476 occurrences). Ctags' Lua
  parser tags the LHS name of *every* statement whose right-hand side contains the token
  `function` — ~136 anonymous callbacks passed as call arguments
  (`res, msg = pcall(function() ... end)` → tags `res`), ~210 `name = function(...)`
  anonymous-assignment forms, ~84 table-constructor / metamethod fields, ~29 the literal word
  `function` inside a string, ~19 inside a comment. GitGalaxy and tree-sitter-lua both correctly
  scope this out. Documented in `tests/tools/ctags_reader.py`'s lua section.
- **Ctags emits no `signature:` field for Lua at all** (shape
  `lua/function/args/agree[none]_vs[gitgalaxy,tree_sitter]`). It structurally cannot participate
  in a per-function argument-count comparison — so the `args` metric here is real 2-tool
  corroboration between GitGalaxy and tree-sitter-lua on the parenthesised parameter list, not a
  discrepancy.
- **Ctags misses method-style and nested declarations** GitGalaxy and tree-sitter-lua agree on
  (`db.lua:a:f` = `function a:f()`; `closure.lua` inner closures the `function_opener` pass now
  recovers).
- **tree-sitter-lua has a small recall gap** on a few real functions GitGalaxy and ctags agree
  on (`constructs.lua:foo`, `errors.lua:main`, `main.lua:f`) — parse reports no error, the misses
  sit in regions the audit's own blind-spot heuristics exclude. ~3 occurrences, noted not filed.

### Architecture tradeoffs (not defects)

- **Deep nesting** (shape `lua/function/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]`).
  tree-sitter-lua descends into function bodies and names every nested closure
  (`calls.lua:a:add`, `a.b.c:f2`, `foo1` two levels deep); both GitGalaxy's Mode-D extractor and
  ctags' single-pass scanner report only the top-level / one-level declarations. Same shape as
  shell's `moby/check-config.sh::zgrep`. tree-sitter's reading is more complete; GitGalaxy and
  ctags' is more consistent across eras.
- **Lua has no class syntax** (shape `lua/class/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`,
  14 occurrences). tree-sitter-lua has no class-shaped node and ctags' Lua kind table has no
  class kind, so both report 0 forever. GitGalaxy's 14 `class_start` hits are its heuristic (§5,
  [#2439](https://github.com/squid-protocol/gitgalaxy/issues/2439)) — the `0` is a structural
  absence, not a refutation. Same category as css/html classes
  (`_CLASS_EXTRACTION_OUT_OF_SCOPE`).

### `credit_tools` / `debit_tools`

None on any of the 8 shapes. The confirmed-defect shapes were fixed rather than left as a
standing claim; the rest are absences or architecture differences where no tool is "wrong for a
shared reason." This is the common case per the skill's step 4 guidance.

### Issues filed

- [#2437](https://github.com/squid-protocol/gitgalaxy/issues/2437) — residual mid-file Mode-D
  desync `_[Truncated]` satellites.
- [#2438](https://github.com/squid-protocol/gitgalaxy/issues/2438) — dotted / method-style
  function heads not fully name-resolved in the nested pass.
- [#2439](https://github.com/squid-protocol/gitgalaxy/issues/2439) — `class_start` heuristic also
  matches ALL_CAPS data tables.

### Full record

`docs/self_scan/tri_comparison_ledger.json` (filter to `lua/`), each entry's `verdict` field,
`docs/self_scan/tri_comparison_points_of_interest.md`'s `## lua` section, and
`docs/self_scan/tri_comparison_chart.svg`.

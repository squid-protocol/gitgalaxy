# Lua — Structural Signature Coverage

Snapshot generated 2026-08-29 against `main`. Source: `LANGUAGE_DEFINITIONS["lua"]` in
`gitgalaxy/standards/language_standards.py`, `tests/extraction/languages/test_lua.py` /
`test_lua_strict.py`, closed GitHub issues, and the tri-comparison ledger. Re-run the
`language-status` skill's data-gathering commands before trusting the §1–8 numbers if this doc
looks old relative to `last_updated` below.

**Scope note:** §9 was written by the `tri-comparison-ledger-sweep` skill and is the part of this
doc with the most recent, most detailed investigation behind it — a real 3-way
GitGalaxy / tree-sitter-lua / Universal-Ctags comparison on the `language-crucible` corpus, with
six engine defects found and fixed across three PRs. §§1–8 are the standard primary-source
snapshot.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | Lua 5.5 / Luau / LuaLS Annotations / LuaJIT |
| `_meta.blueprint_version` | v5.0 |
| `_meta.last_updated` | 2026-02-18 (rules unchanged; engine logic hardened 2026-08-29, §9) |
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

- **Two recall misses** (skill step 2.6 recall audit, 2026-08-29 — func recall 99.7%), both
  filed as [#2461](https://github.com/squid-protocol/gitgalaxy/issues/2461):
  - `constructs.lua:105` — `local a; local function f(x) ... end`. `func_start` is
    start-of-line anchored, so a `local function` that is not the first statement on its line is
    missed. GitGalaxy finds the other 4 `function f` in the file; this is a real, narrow gap.
  - `literals.lua:80` — `local function lexerror (s, err)`, inside `test/literals.lua` (the Lua
    suite's *lexer-torture fixture*, adversarial nested `[==[[===[[=[…]]=][====[…]` long
    brackets that defeat `_LUA_LONG_BRACKET_RE`'s single-backref shielding). Only ever exercised
    by this one fixture.
- **`class_start` keeps one borderline hit** (`tracegc.lua:M` — `local M = {}` with
  `function M.start` / `function M.stop` / `return M`, a real module table). #2439's proto-table
  "tell" gate dropped the other 13 ALL_CAPS-data-table false positives; `M` is legitimately
  class-like. Lua class precision still renders `0.0%` because no ground-truth tool
  (tree-sitter-lua, ctags) reports any lua class to corroborate against — an unavoidable artifact
  of the frontier, not a refutation (§9).

### Closed this cycle

- [#2438](https://github.com/squid-protocol/gitgalaxy/issues/2438) — one-line `function f(...)
  ... end` declarations (net keyword change ≤ 0) were filed as global dust and never became a
  `FunctionNode`; fixed by extending the `function_opener` pass to top-level self-closing
  declarations. The issue's original "dotted-head" framing was a misdiagnosis —
  `_extract_semantic_name` already resolves `a.b.c.f1` / `a:deep`.
- [#2440](https://github.com/squid-protocol/gitgalaxy/issues/2440) — a `<style>` / `<script>`
  inside a `Write([[<!doctype html> … ]])` heredoc split the enclosing lua function; fixed by
  masking lua long-bracket literals in `_partition_segments`' embedded-language trigger scan
  (offsets preserved, slicing unchanged).
- [#2439](https://github.com/squid-protocol/gitgalaxy/issues/2439) — `class_start` heuristic
  over-matched ALL_CAPS data tables; fixed with the proto-table tell gate above.
- [#2437](https://github.com/squid-protocol/gitgalaxy/issues/2437) — mid-file keyword desync.
  Fully resolved for lua: #2441 handled the `#` / `//` / `[[ ]]` sources, and a dedicated `\z`
  string-continuation fix (`\z` skips whitespace *including line breaks*, so
  `'… tests for \z\nuserdata <<<\n'` is one string the newline-bounded shield couldn't match —
  it leaked the word `for` as a `\bfor\b` opener) cleared the last one, `events.lua`. lua
  `extra_functions` 1 → 0, function precision **100.0%**. Kept open as a general Mode-D hardening
  task (the containment-heuristic half is deliberately not done — no remaining repro to validate
  it against).

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
`tri-comparison-ledger-sweep` skill. **Six** confirmed GitGalaxy engine defects were found and
fixed across three PRs (#2441; the #2438/#2439/#2440 follow-up; then a `\z` string-continuation
fix for #2437); the rest are tool-architecture differences or absences with no privileged ground
truth. Cumulative effect, measured by `tree_sitter_accuracy_audit.py --lang lua`:

| Metric | Baseline | After #2441 | After #2438/9/40 | After #2437 |
|---|---:|---:|---:|---:|
| `found_functions` | 505 | 557 | 618 | **618** |
| `extra_functions` (lower is better) | 12 | 7 | 1 | **0** |
| `extra_classes` (lower is better) | 14 | 14 | 1 | **1** |
| `args_exact_match` | 463 | 516 | 572 | **572** |

Lua recall 81.5% → **99.7%**, function precision 97.7% → **100.0%**. Both golden masters were
re-blessed and `tests/tree_sitter_accuracy_baseline_lua.json` regenerated in each PR.

### Confirmed engine defects (6, all fixed)

Defects 1–2 landed in PR #2441; defects 3–5 in the #2438/#2439/#2440 follow-up; defect 6 in the
`\z` fix for #2437.

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

**3 — one-line function declarations were never emitted** (#2438; shape
`agree[ctags,tree_sitter]_vs[gitgalaxy]`, drove it ~33 → 2). A one-liner
`function a:x (x) return x+self.i end` has an equal count of openers and closers, so its net
scope change is ≤ 0 — the primary Mode-D scan filed it as global dust and the `function_opener`
pass skipped it (`depth_before_line[i] <= 0` gate). Affected plain names too
(`function deep (n) ... end`, redefinitions, `local function ret2 (a,b) return a,b end`) and
every nested declaration inside a bare `do` block (`do` isn't a Mode-D opener). Fixed by
extending `function_opener` to top-level self-closing declarations, lua-scoped so
ruby/matlab/livecode keep the strict gate. `found_functions` +61 in a single pass.

**4 — polyglot segmentation split a function at embedded markup** (#2440; shape
`agree[gitgalaxy]_vs[ctags,tree_sitter]`, 7 → 1). `detector.py`'s `_partition_segments` scans for
`^\s*<style` / `^\s*<script` on raw text, so the HTML inside
`Write([[<!doctype html> … <style> … ]])` in the redbean demo files (`fetch.lua`,
`binarytrees.lua`, `maxmind.lua`) got carved into a `css` segment *mid-function*, producing a
`<name>_[Truncated]` satellite. Fixed by scanning triggers against a view where lua long-bracket
literals are blanked to same-length filler (byte offsets and line numbers preserved; segment
slicing still uses the untouched text).

**5 — `class_start` heuristic over-matched ALL_CAPS data tables** (#2439; shape
`class/existence/agree[gitgalaxy]_vs[...]`, 14 → 1). Lua has no `class` keyword; the `Name = {`
heuristic fired on `local FISH = { … }` (Game-of-Life patterns), `local Arr = {}`, one-letter
test fixtures. Fixed by requiring a proto-table "tell" within a bounded window — `function
Name[.:]`, `Name.__index`, `setmetatable(…, Name)`, or `Name[.:]new` — for the heuristic branch
(the explicit `---@class` annotation branch is never gated). Only `tracegc.lua:M` (a real module
table) survives.

**6 — `\z` string continuation defeated the literal shield** (#2437; shape
`agree[gitgalaxy]_vs[ctags,tree_sitter]`, 1 → 0). Lua's `\z` escape skips the following run of
whitespace *including line breaks*, so `'\n >>> testC not active: skipping tests for \z\nuserdata
<<<\n'` (`events.lua`) is a single string spanning two physical lines. `_apply_literal_shield`'s
newline-bounded quote patterns couldn't match it, leaking the word **`for`** as live code — a
`\bfor\b` Mode-D opener with no `end`, running to EOF as an `Anonymous_Block_[Truncated]`
satellite. Fixed by adding `\z[ \t\r\n]*` as an explicit cross-newline alternative to lua's
`standard_double` / `standard_single` shield patterns (plain `\<newline>` continuation was
already covered by `\\.` under `re.DOTALL`). This was #2437's last lua repro; function precision
reached 100.0%. #2437's other half — a mid-file blast-radius containment heuristic — was
deliberately **not** built: after this fix there is no remaining corpus repro to validate it
against, and fixing desync *sources* (6/6 of this sweep's defects) has consistently beaten adding
containment backstops.

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
  tree-sitter-lua descends into function bodies and names every nested closure; ctags' single-pass
  scanner reports only top-level declarations. After #2438 GitGalaxy recovers the *one-level*
  nested declarations too (so this shape no longer reproduces — it moved into
  GitGalaxy+tree-sitter consensus), but GitGalaxy still deliberately does not record
  arbitrarily-deep closures as peer `FunctionNode`s. Same design boundary as shell's
  `moby/check-config.sh::zgrep`.
- **Lua has no class syntax** (shape `lua/class/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`,
  now 1 occurrence). tree-sitter-lua has no class-shaped node and ctags' Lua kind table has no
  class kind, so both report 0 forever. After #2439 GitGalaxy's single remaining hit
  (`tracegc.lua:M`) is a real module table — the `0` is a structural absence, not a refutation.
  Similar category to css/html classes (`_CLASS_EXTRACTION_OUT_OF_SCOPE`), but lua keeps a
  tightened heuristic rather than opting out entirely.

### `credit_tools` / `debit_tools`

None on any of the 8 shapes. The confirmed-defect shapes were fixed rather than left as a
standing claim; the rest are absences or architecture differences where no tool is "wrong for a
shared reason." This is the common case per the skill's step 4 guidance.

### Issues

- [#2437](https://github.com/squid-protocol/gitgalaxy/issues/2437) — **fixed** for lua: `#` /
  `//` / `[[ ]]` sources (#2441) + `\z` string continuation (defect 6). Kept open as a general
  Mode-D containment-hardening task with no lua repro left to drive it.
- [#2438](https://github.com/squid-protocol/gitgalaxy/issues/2438) — **fixed**: one-line
  function declarations never emitted.
- [#2439](https://github.com/squid-protocol/gitgalaxy/issues/2439) — **fixed**: `class_start`
  heuristic matched ALL_CAPS data tables.
- [#2440](https://github.com/squid-protocol/gitgalaxy/issues/2440) — **fixed**: polyglot
  segmentation split a function at `<style>` / `<script>` inside a `[[ ]]` string.
- [#2461](https://github.com/squid-protocol/gitgalaxy/issues/2461) — `local function` not first
  on its line (`local a; local function f(x)`); + the `literals.lua` lexer-torture nested-bracket
  shielding gap. Found by the step 2.6 recall audit — §5.

### Full record

`docs/self_scan/tri_comparison_ledger.json` (filter to `lua/`), each entry's `verdict` field,
`docs/self_scan/tri_comparison_points_of_interest.md`'s `## lua` section, and
`docs/self_scan/tri_comparison_chart.svg`.

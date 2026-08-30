# CSS — Structural Signature Coverage

Snapshot generated 2026-08-30 against `feature/tri-comparison-css-precision-recall`. Source:
`LANGUAGE_DEFINITIONS["css"]` in `gitgalaxy/standards/language_standards.py`,
`tests/extraction/languages/test_css.py` / `test_css_strict.py`, closed GitHub issues, and
[`gitgalaxy-raw-output`](https://github.com/squid-protocol/gitgalaxy-raw-output). Re-run the
`language-status` skill's data-gathering commands before trusting these numbers if this doc looks
old relative to `last_updated` below.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | Modern CSS (2025 Baseline) — native nesting (`&`), container queries, `@layer`, `@scope`, `@property`, scroll-driven timelines, relative color / `color-mix()` |
| `_meta.blueprint_version` | v5.0 |
| `_meta.last_updated` | 2026-02-18 |
| `lexical_family` | `standard_block` (`/* */` block comments; the SCSS/Less/Stylus dialects sharing this entry also use `//` line comments — not modelled, see §5) |
| Structural signature keys wired | 30 / 48 (18 explicit `None`, see §4) |
| Extraction-gauntlet tests (`test_css.py`) | 18 |
| Strict-signature tests (`test_css_strict.py`) | 74 |
| Total dedicated CSS test cases | 92 |

CSS is a declarative stylesheet language, so its rule set is deliberately smaller than a
Turing-complete language's: nearly every `None` below is a documented refusal to hallucinate an
imperative concept (I/O latency, state flux, memory management, debug output) onto a stylesheet.
It still carries a `func_start`/`class_start`/`args`/`_dependency_capture` extraction surface so
it produces the same comparable schema every other language does — anchored on at-rule blocks and
class/ID selectors rather than on real functions.

## 2. Identification surface

- **Extensions:** `.css .scss .sass .less .styl .pcss` — standard stylesheets plus the Sass, Less,
  Stylus, and PostCSS preprocessor dialects, all routed through this one language entry.
- **Exact filenames:** none — CSS has no extensionless canonical entry-point convention.
- **Discriminators:** `.css`, `postcss.config.js`, `tailwind.config.js`, `.stylelintrc`,
  `.stylelintignore` — linting / PostCSS / utility-framework ecosystem anchors used to
  disambiguate.
- **Shebangs:** none — CSS is never executed from a line-1 interpreter.

## 3. What GitGalaxy detects

Grouped by the phase headers `language_standards.py` uses for CSS. Description is what CSS's
*actual* regex matches, not the generic cross-language definition.

**Topology & structure (Phase 1)**
| Key | What it captures for CSS |
|---|---|
| `branch` | The conditional at-rules `@media @supports @container @starting-style`, plus the logic-gating functional pseudo-selectors `:has() :is() :where() :not()` (argument span bounded to one level of parenthesis nesting so it stays linear). The four `@`-prefixed alternatives were pulled out of a shared leading-`\b` wrapper by the cross-language `@`-boundary sweep (#645) — before that they never matched at all |
| `args` | CSS value/math function calls — `calc clamp min max var env url rgba? hsla? lch oklch color-mix light-dark` — with the parenthesised span captured in its own group under a one-level-nesting bounded form (Rule 11). The old flat `[^)]*` truncated `calc(100% - var(--sidebar, calc(...)))` at the first inner `)`; fixed in #737 / #955 |
| `structural_boundaries` | The structural at-rules `@layer @scope @property @font-face @keyframes @page @charset @namespace`. Same leading-`\b`-before-`@` bug as `branch`, fixed in the same #645 sweep |
| `func_start` | Anchors an at-rule *block* at line start: `^[ \t]*` then `@media|@supports|@container|@layer|@keyframes|@-webkit-keyframes` with a `{` ahead of the next `}`. Deliberately **excludes** class/ID selectors (that's `class_start`'s job) to keep the "executable block" count from ballooning to every rule in the file |
| `class_start` | `.class` / `#id` selectors, with full CSS identifier grammar: unicode escapes (`.\31 23-number`), backslash-escaped specials (`.\@special\+chars`), and a `{`-before-`;`/`}` lookahead. Negative lookbehinds exclude the universal `*`, and quoted / backslash-escaped positions (so `[value=".not-a-class"]` and `content: "#id"` don't fire) |

**Safety & risk (Phase 2)**
| Key | What it captures for CSS |
|---|---|
| `safety` | `@supports` feature queries, `var(--x, <fallback>)` with a fallback value present, `minmax()` / `clamp()` bounded ranges, and `contain: strict\|content\|paint\|layout` — CSS's defensive-fallback and containment constructs |
| `safety_bypasses` | A line-start universal selector `*`, and a line-start high-specificity `#id { ... }` override block |
| `high_risk_execution` | Legacy IE script-in-CSS and engine-thrash constructs: `expression(...)`, `behavior`, `-ms-filter` |
| `io` | `None` — see §4 |
| `api` | Design-token / exposed-surface markers: `:root`, `@property`, a custom-property *definition* (`--name:`), and `::part(...)` |
| `state_mutation` | `None` — see §4 |
| `dead_code` | Commented-out (`/* ... */`) at-rules, class / ID selectors, or a `tag {`-style rule opener |
| `doc` | `/**` doc-comment openers and `/* @param @return @author @example @prop @define @theme` (KSS / SassDoc-style annotations) |
| `test` | Test-hook attribute selectors: `[data-testid]`, `[data-cy]`, `[data-test]`, `[data-test-id]`, `[data-qa]` |

**Architecture & domain sensors (Phase 3)**
| Key | What it captures for CSS |
|---|---|
| `ui_framework` | Layout-primitive density — `display: flex`, `display: grid`, `justify-content`, `align-items`, `gap`, `grid-template-columns`, `absolute`, `relative` — plus the Tailwind `@apply` directive |
| `closures` | Native CSS nesting: a `&` nesting selector followed by `{` (optionally through a combinator / pseudo prefix) |
| `globals` | Line-start global-scope selectors `:root`, `html`, `body`, `*` |
| `scientific` | Trig / math functions with an argument list — `sin cos tan asin acos atan atan2 hypot abs sign mod rem round pow sqrt exp log` — with the same one-level-nesting fix as `args` (#737 / #955) |
| `reflection_metaprogramming` | Catastrophic-specificity / recursive-logic shapes: repeated `&&&` nesting, `:has()/:is()/:not()` chains nested into another such pseudo, and `calc(...)` recursively containing another `calc(` |
| `import` | `@import` |
| `_dependency_capture` | Extracts the exact target path from `@import url(...)` or `@import "..."` (feeds the dependency DAG) |
| `ownership` | `/* @author ... */`, `Author:`, `Created by`, `Maintainer`, `Copyright` in a block comment |

**Specialized subsystems (Phase 4)**
| Key | What it captures for CSS |
|---|---|
| `planned_debt` / `fragile_debt` | Shared `GLOBAL_` TODO/FIXME/HACK-family markers |
| `spec_exposure` | `[SPEC-123]`, `[spec ...]`, `[audit ...]` traceability tags, plus `figma.com/file/` design links. `\d+` bounded to `\d{1,10}` and `[^\]]*` to `{0,300}` to kill the adjacent-unbounded-quantifier ReDoS shape (`css` had its own unfixed copy of this pattern — #737 / #798) |
| `events` | Scroll-driven animation timelines: `@scroll-timeline`, `@view-timeline`, `animation-timeline: scroll(...)` / `view(...)` |

**Resource management & stability (Phase 5)**
| Key | What it captures for CSS |
|---|---|
| `panics_and_aborts` | Cascade value resets: `unset initial revert revert-layer` |
| `thread_sleeps` | `transition-delay`, `animation-delay` |
| `immutability_locks` | `!important`, and the legacy `constant` keyword |
| `encapsulation` | Scoping / shadow-DOM part boundaries: `@scope`, `::part`, `::slotted` |
| `listeners` | Subscribing to an external timeline: `animation-timeline`, `@scroll-timeline` |
| `test_skip` | `[data-skip]`, `[data-ignore]` attribute markers |

Two pairs above are **deliberate double-classifications**, asserted as intentional in
`test_css_strict.py`:
- `@supports` fires both `branch` (it is a conditional) and `safety` (it is a defensive
  feature-query fallback) — `test_css_safety_and_branch_supports_intentional_double_classification`.
- `@scope` fires both `structural_boundaries` (it is a structural at-rule) and `encapsulation` (it
  is an explicit scoping mechanism) —
  `test_css_encapsulation_and_structural_boundaries_scope_intentional_double_classification`.

## 4. What GitGalaxy explicitly does not track

Eighteen keys are hard-set to `None` in CSS's `rules` dict. Five carry a substantial inline
rationale in `language_standards.py` (CSS is declarative — forcing an imperative regex onto it
produces confident nonsense); the rest are constructs the language simply has no syntax for.

**`None` with an explicit "declarative hallucination" rationale in source:**
- **`io`** — `url()` / `@import` fetch a visual asset during browser paint; they do not block a
  compute thread on a database read or file write. A regex here would hallucinate severe I/O
  bottlenecks on ordinary stylesheets.
- **`state_mutation`** — defining a custom property (`--color: red;`) is a static declaration, not
  a sequential mutation like `x = x + 1`. Treating it as flux makes stylesheets mathematically
  outrank complex controllers in volatility.
- **`debug_prints`** — CSS has no runtime console. Any hit here is guaranteed to be a false
  positive on a string literal (`content: "console.log";`).
- **`cleanup`** — `clear: both;` is a float-layout property; it destroys no variables and frees no
  memory. A regex would trick the risk model into reading the stylesheet as doing active memory
  management.
- **`memory_alloc`** — no manual allocation exists to track (paired with the `cleanup` rationale
  above).

**`None` because the construct does not exist in CSS:**
`concurrency`, `decorators`, `generics`, `comprehensions`, `ssr_boundaries`,
`dependency_injection`, `macros`, `pointers`, `inline_asm`, `telemetry`, `explicit_casts`,
`bitwise_ops`, `sync_locks` — CSS has no threading, no user-defined decorators or generics, no
comprehension syntax, no server-render boundary, no DI container, no C-style preprocessor, no
pointers or inline assembly, no logging framework, no explicit cast operator, no bitwise
operators, and no lock primitive.

## 5. Known limitations (accepted, not fixed)

There are **no `known_limitation`-named tests** in `test_css.py` or `test_css_strict.py`. Two
accepted gaps are nonetheless documented in the test suite / closing PRs rather than fixed:

1. **`//` line comments in SCSS / Less / Stylus are invisible to `dead_code` (and the
   comment-stripping engine).** CSS's `lexical_family` is `standard_block`, which models only
   `/* */`. The `.scss` / `.less` / `.styl` / `.sass` dialects share this language entry and
   commonly use `//` line comments, so a `//`-commented-out selector is not detected as
   `dead_code` and is not shielded as a comment. Confirmed and documented in
   `test_css_lexical_family_dual_comment_style_dead_code_audit` — consistent with the
   `standard_block` baseline, and preprocessor line-comment support was explicitly out of scope
   for the strict-testing pass (#577).
2. **Structural lookalikes inside string literals / multi-line block comments can still
   false-positive at the raw-regex level.** Per PR #955's own "Known Regex Limitations" note: with
   no CSS tokenizer, a construct like `content: "calc(100%)";` or a lookalike spread across a
   multi-line `/* ... */` block may still be captured. The isolated `INVALID_*` cases in
   `test_css.py` cover the single-line string-literal shape for `func_start` / `class_start` /
   `_dependency_capture` (the anchoring and lookbehinds hold), but this is a variant of the
   engine-wide "match against shielded code, not raw content" bug class, not a CSS-specific fix.

## 6. Test depth

- **Extraction gauntlet** (`func_start` / `args` / `class_start` / `_dependency_capture`): 18
  tests in `tests/extraction/languages/test_css.py` — valid / invalid / pathological (ReDoS)
  cases per rule, including unicode-escape identifiers, nested `calc(var(calc()))`, vendor-prefix
  `@-webkit-keyframes`, and multi-line-split selectors. **Partially migrated:** a small number of
  CSS cases still sit in the old monolithic files — `test_function_extraction.py` (`@media` /
  `@keyframes` valid, `.x {` / `#x {` invalid) and `test_dependency_extraction.py` (`@import
  url(...)` / `@import "..."`). No CSS cases remain in `test_args_extraction.py` or
  `test_class_extraction.py`.
- **Strict signature suite** (all other wired keys): 74 tests in
  `tests/extraction/languages/test_css_strict.py` (epic #518, issue #577) — a positive/negative
  table across all 30 wired signatures plus adversarial cases for the high-ambiguity ones
  (`branch`, `args`, `func_start`, `class_start`, `structural_boundaries`, `safety`,
  `reflection_metaprogramming`), the `@`-boundary leading-`\b` regression, dedicated ReDoS
  regressions for `class_start`, `args`/`scientific`, and `spec_exposure`, the
  `class_start`-vs-`func_start` no-collision check, the two intentional-double-classification
  assertions from §3, the dual-comment-style audit from §5, and a full ReDoS-immunity sweep over
  every compiled CSS pattern.

## 7. Relevant closed work

**Epic-level hardening passes:**
- [#577](https://github.com/squid-protocol/gitgalaxy/issues/577) — Strict parsing tests for CSS
  structural signatures (epic #518), merged as
  [#737](https://github.com/squid-protocol/gitgalaxy/pull/737). Added positive/negative +
  ambiguity + ReDoS coverage for all 30 wired signatures and **found and fixed 6 real bugs**
  along the way:
  1. `args` / `scientific` — flat `[^)]*` could not represent one level of nesting; modern CSS
     math (`calc(var(--x) + 1px)`) truncated at the first inner `)`. Upgraded to the bounded
     one-level-nesting form.
  2. `class_start` — confirmed O(n²) ReDoS in the trailing lookahead (two adjacent quantifiers,
     the first's charset a strict subset of the second's). The redundant first quantifier was
     dropped.
  3. `spec_exposure` — the adjacent-overlapping-quantifier ReDoS already fixed in
     `embedded_python`'s copy; CSS had its own unfixed copy.
  4–6. `dead_code` — `\.[a-zA-Z]` / `#[a-zA-Z]` matched exactly one letter (real multi-character
     class/id names never matched), and the `{`-ending tag-selector alternative shared a trailing
     `\b` that can't fire when formatting puts whitespace after `{` (`div { color: red; }`).
- [#841](https://github.com/squid-protocol/gitgalaxy/issues/841) — Extraction hardening for CSS
  (epic #813), merged as [#955](https://github.com/squid-protocol/gitgalaxy/pull/955). Re-derived
  and re-verified the `class_start` ReDoS and the `args`/`scientific` nested-paren truncation
  against an adversarial corpus, added unicode-escape identifier support to `class_start`
  (`.\31 23-number` was fully blocked by the old `[a-zA-Z_]` class), added the `@-webkit-keyframes`
  vendor prefix to `func_start`, and migrated the 18-case gauntlet into
  `tests/extraction/languages/test_css.py`.

**Cross-language fixes that touched CSS along the way:**
- [#645](https://github.com/squid-protocol/gitgalaxy/pull/645) (closing dart issue #578) — the
  systemic `@`-prefixed leading-`\b` boundary bug across 10 languages. A shared leading `\b`
  before a `@`-prefixed alternative can only fire when a word character immediately precedes the
  `@`, which never happens for real at-rules. This had silently blinded CSS's `branch` (4
  at-rules) and `structural_boundaries` (8 at-rules) to **every** at-rule match. Each `@`
  alternative was pulled out of the shared `\b(...)\b` wrapper.
- [#798](https://github.com/squid-protocol/gitgalaxy/pull/798) (issue #713) — bounded the
  `spec_exposure` ReDoS shape across the remaining 17 vulnerable languages; CSS's copy was
  bounded here (also independently re-confirmed in #737).

**Measurement-tool-only findings (not GitGalaxy engine defects):**
- [#1313](https://github.com/squid-protocol/gitgalaxy/issues/1313) (CLOSED, merged
  [#1315](https://github.com/squid-protocol/gitgalaxy/pull/1315)) — `tree_sitter_accuracy_audit.py`
  reported `real_functions=0` and `real_classes=0` for CSS across its entire corpus. Root cause:
  `NODE_MAPS["css"]["func_node_types"]` was `{"at_rule"}`, but the pinned `tree-sitter-language-pack`
  CSS grammar emits `media_statement` (and sibling node types) for `@media (...) { ... }` — the
  node type `at_rule` never appears in the parse tree. A measurement-harness ground-truth gap,
  not a GitGalaxy regression.
- [#2421](https://github.com/squid-protocol/gitgalaxy/issues/2421) /
  [#2452](https://github.com/squid-protocol/gitgalaxy/issues/2452) (both CLOSED) — when the
  `language-crucible` corpus gained an HTML file with an inline `<style>` block, the accuracy /
  tri-comparison harnesses scored GitGalaxy's (correct) polyglot detection of a `@media` block
  inside `<style>` as an over-detection, because their own tree-sitter walk modelled
  `<style>…</style>` as inert `raw_text`. Both fixes inject the CSS grammar into the harness's
  embedded-language walk so the tree-sitter side sees the real CSS constructs; neither changed
  the CSS engine.

Search performed via `gh issue list --search 'in:title "Extraction hardening: css"'` /
`'in:title "Strict parsing tests" css'` / `'in:title css'` (2026-08-30). Issue #2440 ("Lua:
polyglot segmentation splits a function when a `[[ ]]` long string contains embedded
HTML/CSS/JS") is a Lua segmentation bug that merely mentions CSS and is excluded here.

## 8. Real-world evidence (`gitgalaxy-raw-output`)

Four repos from the `v2.4.7` batch, chosen for a size/shape spread — a large SCSS-heavy
framework, an adversarial CSS-only codebase, a mid-size presentation framework, and a small
canonical baseline:

- **[`bootstrap`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/bootstrap/bootstrap_galaxy_llm.md)**
  — `twbs/bootstrap`, the largest CSS/SCSS corpus available: 91 CSS-family files / ~6k LOC / 64.5%
  of the repo, a deep `@import` mixin graph (`bootstrap.scss` has 40 outbound dependencies), and
  heavy `@media` / `@supports` / `calc()` / `var()` use — exercises `import` / `_dependency_capture`,
  `branch`, `args`, and the nested-paren fix directly. Scanned in 15.44s.
- **[`css_doom_pure`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/css_doom_pure/css_doom_pure_galaxy_llm.md)**
  — `NielsLeenheer/cssDOOM`, a rendering of DOOM in pure CSS with no JavaScript. A genuinely
  adversarial CSS-only codebase: enormous generated selector graphs and catastrophic-specificity
  shapes, the exact input `reflection_metaprogramming` and the `class_start` ReDoS regression
  exist for. Scanned in 0.48s.
- **[`reveal.js`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/reveal.js/reveal.js_galaxy_llm.md)**
  — `hakimel/reveal.js`, a mid-size presentation framework with a substantial hand-written theme
  stylesheet layer (SCSS source + compiled CSS) alongside its JS — a useful polyglot contrast
  point. Scanned in 0.5s.
- **[`html5-boilerplate`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/html5-boilerplate/html5-boilerplate_galaxy_llm.md)**
  — `h5bp/html5-boilerplate`, a small canonical starter with a normalize-style base stylesheet; a
  low-noise baseline against the framework and adversarial extremes above. Scanned in 0.13s.

Each `_galaxy_llm.md` is the human-readable architectural brief; `_galaxy_audit.json.gz` and
`_galaxy_sbom.json.gz` in the same directory carry the raw per-file signature counts and SBOM if
deeper inspection is needed.

## 9. Tri-comparison: GitGalaxy vs. tree-sitter vs. ctags

A different shape from python.md's/javascript.md's §9 on purpose: those diff GitGalaxy against one
privileged ground-truth parser. CSS has no privileged ground truth — the comparison is 3-way
against `tree-sitter-css` and `universal-ctags`, neither treated as correct by default
(`tests/tools/tri_comparison_reconcile.py`'s module docstring explains why). Every discrepancy the
three tools produced was investigated by reading real corpus source
(`docs/self_scan/how_to_investigate_a_discrepancy.md`), not assumed. Full record:
`docs/self_scan/tri_comparison_ledger.json`, filtered to `"language": "css"`; human-scannable
form in `docs/self_scan/tri_comparison_points_of_interest.md`.

CSS only has a **function** panel. Class extraction is permanently out of scope for CSS
(`_CLASS_EXTRACTION_OUT_OF_SCOPE` in `tree_sitter_accuracy_audit.py` — a selector is not a class
definition; see §3), and CSS has no parameter-list construct, so there is no args panel.
"Function" for CSS means the block-bearing at-rule — `@media` / `@supports` / `@container` /
`@layer name {` / `@keyframes` / `@-webkit-keyframes` — the closest function-shaped construct the
language has ([#1313](https://github.com/squid-protocol/gitgalaxy/issues/1313)).

**Result: 3 of 3 discrepancy shapes resolved, zero confirmed GitGalaxy engine defects.** The 29
occurrences investigated (20 already-agreeing + 5 keyframes + 4 `@layer`) all resolved either as
GitGalaxy-correct or as a bug in this repo's own comparison tooling
(`tree_sitter_accuracy_audit.py`). GitGalaxy's `css` `func_start` regex needed no change.

Current measured numbers (`tri_comparison_chart.py --languages css`, `language-crucible/data/css/`
— bootstrap, Tailwind CSS v4, Gutenberg CSS modules, three.js editor UI, MediaWiki, Odoo,
Element; 21 real files):

| Signal | GitGalaxy | tree-sitter | ctags | Read as |
|---|---|---|---|---|
| Functions found | 25 | 25 | 0 | ctags has no CSS function kind at all; GitGalaxy and tree-sitter agree exactly on every file |
| Function precision | **100%** (25/25) | **100%** (25/25) | — (0/0) | fully reconciled; GitGalaxy / tree-sitter tie, no asterisk |

### Recall audit (skill step 2.6)

Every function tree-sitter reports that GitGalaxy does not was individually read. Before the
tooling fix: **4 occurrences, all one mechanism** — the bodyless `@layer a, b, c;` cascade-layer
*ordering* statement (`gutenberg_css_modules/{button,card,tabs}.module.css:1`,
`tailwindcss_atrules/index.css:1`). GitGalaxy's `func_start` deliberately matches only
block-bearing at-rules (its `(?=[^{]*\{)` lookahead), the same body-bearing-definition-only
convention that makes the audit drop C/C++ forward declarations — the bodyless `@layer` list is
the CSS analogue and is not a function. **Bucket 2 (comparison-tool artifact), zero bucket-1 real
gaps.** Fixed in `_get_node_name`: the `at_rule` branch now returns `None` when the node has no
`block` child. **CSS func recall: 4-miss → 0, 100%.**

### Two bugs found in this repo's tri-comparison tooling, fixed the same pass

Both in `tests/tools/tree_sitter_accuracy_audit.py`'s `_get_node_name`; neither a GitGalaxy,
tree-sitter, or ctags defect ([#2499](https://github.com/squid-protocol/gitgalaxy/issues/2499),
same bug class as the closed [#1313](https://github.com/squid-protocol/gitgalaxy/issues/1313)):

1. **`keyframes_statement` name branch was dead code (precision).** It looped for a child of node
   type `at_keyword`, but the pinned `tree-sitter-css` grammar names that child literally
   `@keyframes` / `@-webkit-keyframes` (only `@media`/`@supports` use the `at_keyword` shape). The
   loop never matched, so the reader returned `None` for every `@keyframes` node and the walk
   dropped it — tree-sitter silently reported **0** keyframes corpus-wide despite the nodes being
   present in its parse tree, while GitGalaxy's `func_start` matched them fine. Ledger shape
   `css/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]` (5 occ):
   `tailwindcss_atrules/theme.css:443/449/457/463` (nested in a Tailwind-v4 `@theme default { }`
   block) and `gutenberg_css_modules/button.module.css:237` (top-level). All 5 are real
   `@keyframes` rules GitGalaxy correctly found. Fixed: accept the `@keyframes` /
   `@-webkit-keyframes` child types, fall back to `"keyframes"`. tree-sitter now corroborates all 5.
2. **Bodyless `@layer a, b;` counted as a function (recall).** See the recall audit above. Ledger
   shape `css/function/existence/agree[tree_sitter]_vs[ctags,gitgalaxy]` (4 occ).

### Where GitGalaxy and tree-sitter both do fine

Once the two reader bugs are fixed, GitGalaxy and tree-sitter agree on the CSS function count in
**every one of the 21 corpus files** (verified by a direct `gather_language('css')` name-diff,
not just the capped ledger sample). Notably, both handle `@keyframes` nested inside Tailwind v4's
non-standard `@theme` block (`theme.css:443–463`) even though that file trips
`tree.root_node.has_error` — tree-sitter's error recovery keeps the nested `keyframes_statement`
nodes intact and GitGalaxy's line-anchored regex is unaffected by the surrounding unknown at-rule.

### Where the *other* tools have real, structural gaps

- **ctags has no CSS function concept at all.** `ctags_reader.py`'s `FUNCTION_KIND_MAP` has
  `'css': set()` — confirmed empty (`ctags_funcs: []`) across all 21 corpus files. ctags isn't
  wrong about a claim here; it has no claim to make. The reconciler's `total_slots` mechanics
  handle its abstention — it is neither credited nor debited.

### Confirmed GitGalaxy engine bugs found via this sweep: zero

Every investigated occurrence resolved as GitGalaxy-correct or as a bug in this repo's comparison
tooling. Contrast with `rust`, where the same methodology found real `detector.py` defects — the
contrast is the finding, not a gap in this pass.

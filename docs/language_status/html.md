# HTML — Structural Signature Coverage

Snapshot generated 2026-08-30 against `main` (branch `fix/html-audit-nonexec-script-type`).
Source: `LANGUAGE_DEFINITIONS["html"]` in `gitgalaxy/standards/language_standards.py`,
`tests/extraction/languages/test_html.py` / `test_html_strict.py`, closed GitHub issues/PRs, and
the [`gitgalaxy-raw-output`](https://github.com/squid-protocol/gitgalaxy-raw-output) corpus.
Re-run the `language-status` skill's data-gathering commands before trusting these numbers if
this doc looks old relative to `last_updated` below.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | Modern HTML Living Standard (2025) & Web Components |
| `_meta.blueprint_version` | v5.0 |
| `_meta.last_updated` | 2026-02-18 |
| `lexical_family` | `block_exclusive` — SGML-style `<!-- -->` block delimiters only, no single-line comment anchor (moved here from a mistagged `line_exclusive` by [#733](https://github.com/squid-protocol/gitgalaxy/issues/733) / PR [#758](https://github.com/squid-protocol/gitgalaxy/pull/758), which also implemented the `block_exclusive` comment compiler) |
| Structural signature keys wired | 39 / 48 (9 explicit `None`, see §4) |
| Extraction-gauntlet tests (`test_html.py`) | 91 |
| Strict-signature tests (`test_html_strict.py`) | 123 |
| Total dedicated HTML test cases | 214 |
| Tri-comparison tool coverage | tree-sitter-html only (no `ctags` HTML class kind); `<style>`/`<script>` bodies scored via an injected css/javascript grammar (§7, [#2421](https://github.com/squid-protocol/gitgalaxy/issues/2421)/[#2452](https://github.com/squid-protocol/gitgalaxy/issues/2452)). Class metrics forced N/A in the tree-sitter audit (`_CLASS_EXTRACTION_OUT_OF_SCOPE = {"css", "html"}`) |

## 2. Identification surface

- **Extensions:** `.html .htm .xhtml .cshtml .vue .svelte .astro .ejs .hbs .twig .erb` — standard
  markup, XML-based HTML, Razor, and the JS/server-side component-framework single-file formats.
- **Exact filenames:** `index.html`, `404.html` — standardized routing/entry-point anchors.
- **Discriminators:** `.html`, `package.json`, `vite.config.js`, `webpack.config.js`,
  `nuxt.config.js` — sibling extension plus frontend-build-tool anchors used to prove context.
- **Shebangs:** none — HTML is declarative markup with no execution line.

## 3. What GitGalaxy detects

Grouped by the phase headers `language_standards.py` uses for HTML. Each line describes what
HTML's *actual* regex matches (its own alternation list / inline comments), not the generic
cross-language schema definition. Attribute-value patterns accept **either** single or double
quotes since PR [#801](https://github.com/squid-protocol/gitgalaxy/pull/801) (see §7, [#735](https://github.com/squid-protocol/gitgalaxy/issues/735)).

**Topology & structure**
| Key | What it captures for HTML |
|---|---|
| `branch` | `<details>` / `<summary>` / `<noscript>` disclosure elements, plus framework conditionals — Vue `v-if`, Angular `ng-if` and `*ngIf`, Alpine `x-if`, HTMX `hx-swap`, Jinja/Twig `{% if/elif/else/endif %}`, Handlebars `{{#if}}` |
| `args` | Attribute signatures that define input coupling — `data-*`, `aria-*`, `name`, `value`, `placeholder`, `for`, `alt`, `step`, `min`, `max`, with an optional quoted/unquoted `=value`. Bounded to prevent ReDoS on very large data attributes |
| `structural_boundaries` | Document-flow tags — `html head body main section article header footer div span p h1-h6 ul ol li dl dt dd nav aside figure figcaption search address`, plus 1990 CERN-era tags `nextid`, `hp1`/`hp2`, `dir`, `menu` |
| `func_start` | `<script` or `<style` element openings — the only executable-behavior blocks in markup (the "one comparable schema across every language" reason markup gets a `func_start` rule at all). Case-insensitive; tolerates `/`, space, tab, newline, form-feed as the post-tag delimiter |
| `class_start` | Structural entities and component declarations — `form table svg canvas picture video audio dialog template fieldset legend`, plus any custom-element / web-component name (a lowercase tag name containing a hyphen, `<a-b>`), which also covers framework single-file-component roots |

**Safety & risk**
| Key | What it captures for HTML |
|---|---|
| `safety` | Browser security / validation constraints — boolean `required`/`readonly`/`disabled`, `pattern=`, `sandbox=`, `rel="noopener noreferrer"`, `integrity=` (SRI), and `<meta http-equiv="Content-Security-Policy">` |
| `safety_bypasses` | `target="_blank"` with no following `rel="noopener"`, `href="javascript:…"`, and inline `on*=` handlers whose value contains `eval(` or `document.write(` |
| `high_risk_execution` | `None` — see §4 |
| `io` | Hyperlink navigation and resource fetching — `src=`/`href=`/`action=`/`poster=`/`data=` attributes, and the elements `a form iframe audio video object embed source track img` |
| `api` | Exposed identifiers and metadata-consumption surface — `id`/`name`/`role`/`exportparts`/`part`/`itemprop`/`itemscope`/`itemtype` attributes, `<slot>`, and OpenGraph/Twitter-card `<meta property="og:…">` / `<meta name="twitter:…">` |
| `state_mutation` | `None` — see §4 |
| `dead_code` | An HTML comment (`<!--`) whose first content is an opening structural tag (`<div`, `<script`, `<style`, `<form`, `<table`, `<a`, `<p`, `<section`, `<span`, `<img`, `<ul`, `<li`, `<nav`, `<header`, `<footer`, `<main`) |
| `doc` | `<title>…</title>`, `<meta name="description\|keywords\|author" content="…">`, and `aria-description`/`aria-label`/`aria-labelledby`/`aria-describedby`/`aria-details` |
| `test` | `data-testid` / `data-cy` / `data-test` / `data-test-id` / `data-qa` attributes (Cypress / Playwright / Testing-Library hooks) |

**Architecture & domain sensors**
| Key | What it captures for HTML |
|---|---|
| `concurrency` | `async`/`defer` script attributes, `loading="lazy"`, `fetchpriority="high\|low"`, `decoding="async"`, and `<link rel="preload\|prefetch\|preconnect\|modulepreload\|prerender">` |
| `ui_framework` | Presentational inline tags (`b i u strong em mark small del ins sub sup`) and Tailwind/Bootstrap utility-class density inside a `class=` value (`flex`, `grid`, `absolute`, `relative`, `block`, `inline-block`, `container`, `row`, `col-N`, `justify-center`, `items-center`, `w-full`, `h-full`) |
| `closures` | `<template shadowrootmode="…">` / `<template shadowroot="…">` — declarative Shadow DOM encapsulation |
| `globals` | `None` — see §4 |
| `decorators` | Directive-based logic mutation — bare boolean `hidden`/`inert`, the `class`/`style`/`tabindex`/`draggable`/`spellcheck`/`dir`/`lang`/`translate` attributes, and HTMX `hx-*` / Alpine `x-*` / Vue `v-*` directive attributes |
| `generics` | `<slot …>` with attributes — parameterized component-slot projection |
| `comprehensions` | Declarative iteration — Vue `v-for`, Angular `ng-repeat` and `*ngFor`, Alpine `x-for`, Jinja/Twig `{% for %}`, Handlebars `{{#each}}` |
| `scientific` | MathML (`math mfrac mi mo`) and SVG geometry (`svg canvas path circle rect polygon polyline`) elements, plus an SVG path-data `d="M…"` attribute |
| `reflection_metaprogramming` | Presence of any inline `style="…"` attribute or any `on*="…"` event-handler attribute — the "high logic heat" bucket (inline styling / inline-JS pollution) |
| `import` | `<script type="module\|importmap">` and `<link rel="stylesheet">` / `<link rev="…">` |
| `_dependency_capture` | Extracts the exact `src` path from `<script src=…>` and the exact `href` path from `<link href=…>` (feeds the dependency DAG) |
| `ownership` | `<meta name="author\|creator\|publisher" content="…">` and `<link rev="made" href="mailto:…">` (CERN-era authorship convention) |

**Specialized subsystems**
| Key | What it captures for HTML |
|---|---|
| `planned_debt` / `fragile_debt` | Shared `GLOBAL_` TODO / FIXME-family markers |
| `spec_exposure` | `[SPEC-N]`, `[spec …]`, `[audit …]`, `[RFC …]`, `[W3C …]`, `[CERN …]`, `[TBL …]` traceability tags, both quantifiers bounded (ReDoS Rule 14 / [#713](https://github.com/squid-protocol/gitgalaxy/issues/713)) |
| `ssr_boundaries` | Back-end template hydration — `<?php`, `<%` / `<%=` (ASP/ERB/EJS), `{{ … }}` / `{% … %}` template expressions, and `data-reactroot`/`data-server-rendered`/`ng-version`/`nuxt-ssr` hydration markers |
| `events` | Declarative event dispatchers — HTMX `hx-trigger`, Vue `@event=` / `v-on:event=`, Angular `(event)=` bindings |
| `dependency_injection` | `<script type="importmap">` — module-specifier remapping as an IoC container |
| `macros` | Apache/nginx Server Side Includes — `<!--#include\|exec\|echo\|config\|if\|else\|endif …-->` |
| `pointers` / `memory_alloc` / `inline_asm` | `None` — see §4 |

**Resource management & stability**
| Key | What it captures for HTML |
|---|---|
| `telemetry` | Analytics-vendor script `src` (`analytics`, `gtag`, `gtm`, `segment`, `plausible`, `mixpanel`), `data-layer`, `navigator.sendBeacon` |
| `debug_prints` | `document.write(`, `alert(`, `confirm(`, `prompt(`, `console.log/error/warn/dir/trace/info(` inside inline scripts |
| `explicit_casts` | `None` — see §4 |
| `panics_and_aborts` | `process.exit(`, `history.back(`, `window.close(` |
| `thread_sleeps` | `setTimeout(` / `setInterval(` |
| `bitwise_ops` / `sync_locks` | `None` — see §4 |
| `immutability_locks` | Boolean `readonly` / `disabled` / `inert`, and `aria-disabled="true"` |
| `cleanup` | `removeEventListener`, `clearInterval`, `clearTimeout`, `remove(`, `innerHTML = ""` |
| `encapsulation` | `<template>`, `shadowrootmode`, `<slot>` — declarative / Shadow-DOM boundaries |
| `listeners` | `hx-trigger`, `v-on:`, `@event=`, `addEventListener`, `on*=` handler attributes |
| `test_skip` | `data-skip`, `data-ignore`, `mock-data`, `test-skip` attributes |

Several rules deliberately overlap — `<slot>` fires `api`, `generics`, and `encapsulation`;
`<template shadowrootmode>` fires `closures` and `encapsulation`; `<script type="importmap">`
fires `import` and `dependency_injection`; `disabled`/`readonly` fire `safety` and
`immutability_locks`; an `on*=` attribute fires `safety_bypasses` (if it contains `eval(`),
`reflection_metaprogramming`, and `listeners`. These are intentional multi-classification, not
collisions.

## 4. What GitGalaxy explicitly does not track

Nine keys are hard-set to `None` in HTML's `rules` dict (Rule 4 of the engine's generation
rules: explicitly `None`, never a forced-fit regex, when a dimension doesn't exist natively):

- **`high_risk_execution`** — "HTML is declarative markup. Execution dangers (`eval`,
  `setTimeout`) belong in JS."
- **`state_mutation`** — "HTML is declarative markup. State mutation (DOM manipulation) belongs
  in JS."
- **`globals`** — "HTML is declarative markup. Browser globals (`window`, `document`) belong in
  JS."
- **`pointers`** — no pointer-arithmetic or memory-addressing concept in markup (fragment
  identifiers / `nextid` name-pointers were considered and rejected as not the same thing).
- **`memory_alloc`** — no manual memory allocation.
- **`inline_asm`** — no bare-metal / inline-assembly construct.
- **`explicit_casts`** — no type-casting concept.
- **`bitwise_ops`** — no bitwise operators.
- **`sync_locks`** — no synchronization-primitive concept.

The last six carry no inline reason comment; the omission is self-evident given markup has never
had any of these constructs. Anything that *is* executable in an HTML file (the contents of a
`<script>` or `<style>` block) is routed to the `javascript` / `css` rule sets by the polyglot
detector, which is why these six stay `None` here rather than being force-fit onto inline-script
text.

## 5. Known limitations (accepted, not fixed)

There are **no `known_limitation`-named tests** in `test_html.py` or `test_html_strict.py`. Two
behaviors are, however, deliberately documented in the test suite rather than fixed:

1. **Tag-anchored rules have no comment/string awareness at match time.** `func_start`,
   `class_start`, `structural_boundaries`, `io`, and the other `<tag`-anchored rules match on the
   literal `<tag` text wherever it appears — including inside an HTML comment or inside an
   attribute string value. `FUNC_START_INVALID` in `test_html.py` carries commented-out
   `"<!-- <script> -->"` and `"<div title=\"<script>\">"` cases annotated *"Disguised tags
   (comments/strings) are very hard for naive regex"* — an explicit acknowledgement of this gap
   (recurring bug class 3: string/comment lookalikes). In the other direction, `dead_code` and
   `macros` are *supposed* to match inside `<!-- -->` — that is their entire purpose.
2. **`dead_code` / `macros` were authored against un-stripped raw text.**
   `test_html_dead_code_and_macros_rely_on_unstripped_comments` documents that both rules search
   for the literal `<!--` prefix directly against raw source and cites [#733](https://github.com/squid-protocol/gitgalaxy/issues/733)
   (html was mistagged `line_exclusive`, so `<!-- -->` comments were never stripped). #733 has
   since been closed by PR [#758](https://github.com/squid-protocol/gitgalaxy/pull/758) (html
   moved to `block_exclusive`, and that family's comment compiler implemented), so this
   dependency is worth re-verifying on a future pass — but no test currently fails.

## 6. Test depth

- **Extraction gauntlet** (`func_start` / `args` / `class_start` / `_dependency_capture`): 91
  cases in `tests/extraction/languages/test_html.py` — valid (modern + legacy/CERN-era + custom
  element), invalid (tag lookalikes, `</script>` closers, `<scripting>` substrings), and
  pathological (10 000-space attribute stretches, newline/tab/form-feed delimiter splits,
  `<script>console.log('</script>')</script>` nesting) coverage, plus ReDoS-immunity assertions.
  Migrated to the per-language file by epic [#813](https://github.com/squid-protocol/gitgalaxy/issues/813)
  / issue [#840](https://github.com/squid-protocol/gitgalaxy/issues/840); small superseded stubs
  for `html` still sit in the old monolithic `test_function_extraction.py` and
  `test_dependency_extraction.py` (2 tiny parametrized entries) and can be ignored.
- **Strict-signature suite** (all other wired keys): 123 cases in
  `tests/extraction/languages/test_html_strict.py` — positive/negative match per signature, an
  adversarial sweep, a `_HTML_DEEP_CASES` deep-parametrized set, a 14-rule ReDoS-immunity sweep
  (`args`, `safety`, `io`, `api`, `ui_framework`, `decorators`, `comprehensions`, `scientific`,
  `reflection_metaprogramming`, `ssr_boundaries`, `events`, `spec_exposure`, `class_start`,
  `_dependency_capture`), single-quoted-attribute-value regression tests (#735), and dedicated
  boundary regressions for each of the 8 `\b`-adjacent-to-non-word bugs the epic #587 pass
  fixed. Originally 54 tests in the monolithic
  `tests/core_engine/test_language_standards_strict.py` (PR [#734](https://github.com/squid-protocol/gitgalaxy/pull/734)),
  since migrated to the per-language file and deepened.

## 7. Relevant closed work

**Epic-level hardening passes:**
- [#587](https://github.com/squid-protocol/gitgalaxy/issues/587) — Strict parsing tests for
  `html` structural signatures (epic [#518](https://github.com/squid-protocol/gitgalaxy/issues/518)),
  closed via PR [#734](https://github.com/squid-protocol/gitgalaxy/pull/734). Covered all 39
  non-`None` signatures and **found and fixed 8 real bugs, all the same shape**: a `\b`
  word-boundary sitting adjacent to a non-word character inside a shared alternation group,
  which can never fire. Affected Angular's `*ngIf` (`branch`) and `*ngFor` (`comprehensions`)
  structural directives, `pattern=` / `sandbox=` / `rel="noopener"` / `integrity=` (`safety`),
  `loading="lazy"` / `fetchpriority=` / `decoding="async"` (`concurrency`), the importmap
  `dependency_injection` rule, and `aria-disabled="true"` (`immutability_locks`).
- [#840](https://github.com/squid-protocol/gitgalaxy/issues/840) — Extraction hardening for
  `html` (epic [#813](https://github.com/squid-protocol/gitgalaxy/issues/813)). Landed via PR
  [#951](https://github.com/squid-protocol/gitgalaxy/pull/951), reverted by PR
  [#953](https://github.com/squid-protocol/gitgalaxy/pull/953), and re-landed by PR
  [#957](https://github.com/squid-protocol/gitgalaxy/pull/957). Added the missing
  `re.IGNORECASE` flag (`<SCRIPT>` / `<STYLE>` were invisible before), HTML5 delimiter handling
  (newline / slash / unquoted / valueless-boolean attributes), and custom-element `<a-b>`
  capture in `class_start`.

**Real bugs found along the way:**
- [#733](https://github.com/squid-protocol/gitgalaxy/issues/733) (found while starting #587) —
  `html` was tagged `lexical_family: "line_exclusive"` despite its own inline comment saying
  `block_exclusive`, so `<!-- -->` comments were never stripped from `code_stream`; and
  `block_exclusive`'s own delimiter config in `gitgalaxy_config.py` was broken anyway (empty
  opening delimiter, only the rare `--!>` close token). Fixed by PR
  [#758](https://github.com/squid-protocol/gitgalaxy/pull/758), which implemented the
  `block_exclusive` regex compiler and moved `html` (and `xml`) onto it.
- [#735](https://github.com/squid-protocol/gitgalaxy/issues/735) (found while closing #587) —
  ~20 of `html`'s rules hard-coded a literal `"[^"]*"` attribute-value delimiter, so
  single-quoted attributes (`<div class='flex'>`, equally valid HTML) never matched at all.
  Deferred out of #587 as too broad for that pass, then fixed by PR
  [#801](https://github.com/squid-protocol/gitgalaxy/pull/801), which widened every affected
  rule to the `["'][^"']*["']` idiom already used by `_dependency_capture` (no new ReDoS
  surface — still one unbounded quantifier per gap).

**Measurement-tool findings (not GitGalaxy engine defects):**
- [#2421](https://github.com/squid-protocol/gitgalaxy/issues/2421) — `html`'s `func_start`
  anchors `<style>` / `<script>` *tag* boundaries, but `tree-sitter-html` models `<style>…</style>`
  as a `style_element` wrapping inert `raw_text` and extracts nothing there. When the corpus
  gained a Jinja `layout.html` with a `<style>` block, tree-sitter func-precision for `html`
  went `N/A → 0.0%`. Fixed by PR [#2434](https://github.com/squid-protocol/gitgalaxy/pull/2434):
  the tree-sitter accuracy audit now does the same polyglot descent GitGalaxy does — injecting
  the css/javascript grammar to score the real CSS/JS *inside* the block (GitGalaxy correctly
  names `layout.html`'s `<style>` after its `@media only screen { … }` rule).
- [#2452](https://github.com/squid-protocol/gitgalaxy/issues/2452) — `tri_comparison_gatherer.py`'s
  separate, simpler tree-sitter walk had the same `<style>`/`<script>` blind spot, making a
  correct GitGalaxy polyglot find look like an over-detection in the tri-comparison ledger.
  Fixed in the same sweep by mirroring the audit's embedded-grammar branch. `html` class
  metrics remain forced N/A in the tree-sitter audit
  (`_CLASS_EXTRACTION_OUT_OF_SCOPE = {"css", "html"}`) — `<form>` / `<table>` / custom-element
  boundaries aren't what tree-sitter counts as a class.
- [#2492](https://github.com/squid-protocol/gitgalaxy/issues/2492) (found by the 2026-08-30
  tri-comparison sweep) — the #2421 / #2452 embedded-grammar injection descended into **every**
  `<script>` regardless of its `type`, so `<script type="text/template">` slide samples in
  `revealjs_decks/demo.html` contributed two phantom "functions" that counted against GitGalaxy's
  html recall (94.9%). Part 1 (fixed this pass): `_html_embedded_ts_funcs` now skips a
  non-executable `<script type>`; recall → 100%. Part 2 (open): the symmetric `type=` exclusion
  for HTML's own `func_start`. See §9.

**Cross-language fixes that touched HTML routing:**
- [#2440](https://github.com/squid-protocol/gitgalaxy/issues/2440) — `detector.py`'s mid-file
  language-switching ran on text where Lua `[[ ]]` long-string literals were not shielded, so a
  `Write([[<!doctype html> … <style> … </style> … ]])` call inside a Lua function got carved
  into its own embedded `html`/`css` segment mid-function, emitting a `_[Truncated]` satellite.
  A polyglot-segmentation bug surfaced through HTML embedding, not a defect in `html`'s own
  rules.

Search performed via `gh issue list --repo squid-protocol/gitgalaxy --state closed --search
"html in:title"` and `gh pr list --state merged --search "html in:title"` (2026-08-30); unrelated
title hits (`node-html-markdown`, `Museum of Code` MkDocs migration, a CodeQL HTML-filtering
alert) were skimmed out as not html-coverage-specific.

## 8. Real-world evidence (`gitgalaxy-raw-output`)

HTML is a minority language in essentially every real repository — there is no "pure HTML"
project of note the way there is for C or Python — so these four are picked from the `v2.4.7`
batch for a spread of *markup shape* rather than repo size:

- **[`html5-boilerplate`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/html5-boilerplate/html5-boilerplate_galaxy_llm.md)**
  — `h5bp/html5-boilerplate`, the canonical "correct HTML document" reference. Tiny (2 `.html`
  files, 74 LOC, 12.5% of the repo: `src/index.html` + `src/404.html`) — a clean baseline sanity
  check. Scanned in 0.13s.
- **[`bootstrap`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/bootstrap/bootstrap_galaxy_llm.md)**
  — `twbs/bootstrap`. HTML appears as `js/tests/visual/*.html` interaction fixtures (6 files,
  466 LOC, 4.3%); several `.html` files are perimeter-excluded for `>500`-char line saturation,
  a useful look at how the aperture filter handles attribute-dense / near-minified markup.
  Scanned in 15.44s.
- **[`vue`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/vue/vue_galaxy_llm.md)**
  — `vuejs/vue`. The largest HTML surface in the set (22 files, 1,974 LOC, 7.4%): example apps
  and benchmarks (`todomvc`, `big-table`, `elastic-header`, `svg`) that exercise the
  `v-if` / `v-for` / `v-on` framework-directive branches of `branch`, `comprehensions`, and
  `events` directly. Scanned in 0.83s.
- **[`tailwindcss`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/tailwindcss/tailwindcss_galaxy_llm.md)**
  — `tailwindlabs/tailwindcss`. Only 3 `.html` files (565 LOC, 0.7%), but
  `crates/oxide/src/fixtures/example.html` alone lands 140 signature hits — dense utility-class
  markup that stresses the `ui_framework` Tailwind-density heuristic harder than anything else
  in the corpus. Scanned in 6.06s.

Each `_galaxy_llm.md` is the human-readable architectural brief; `_galaxy_audit.json.gz` and
`_galaxy_sbom.json.gz` in the same directory carry the raw per-file signature counts.

## 9. Tri-comparison (tree-sitter + ctags)

HTML is compared against `tree-sitter-html` (with the css/javascript grammars injected for
`<style>` / `<script>` bodies, the same polyglot descent GitGalaxy does — §7, #2421 / #2452) and
Universal Ctags. `ctags`-html has no CSS parser and only a thin JS-in-markup model, so almost
every `<script>` / `<style>`-derived signal is a GitGalaxy-vs-tree-sitter comparison with ctags
absent. Class metrics are forced N/A (`_CLASS_EXTRACTION_OUT_OF_SCOPE = {"css", "html"}`).

**Sweep (2026-08-30):** 3 ledger shapes, **all validated**; recall audit clean; 0 real GitGalaxy
engine defects; 1 comparison-tooling defect found and fixed.

| Ledger shape | Occ | Verdict |
| :--- | :---: | :--- |
| `agree[gitgalaxy,tree_sitter]_vs[ctags]` | 37 | **Real 2-tool consensus.** GitGalaxy's polyglot descent names `<style>` / `<script>` blocks after their embedded CSS at-rule (`media` — `cpython_jinja/layout.html:40`, `html5_boilerplate/{dist,src}_404.html:40`) or JS function (`startup` — `cesium_sandcastle/gallery_cylinders_and_cones.html:29`; `runTests` / `createHTML` / `wrapInTrustedHtml` / `toString` — `jquery_test_fixtures/trusted-html.html`; `goRemote` / `goLocal` — `playwright_dom_fixtures/dynamic-oopif.html`). `ctags`-html emits nothing (no CSS parser; documented in `ctags_reader.py`). No credit/debit. |
| `agree[gitgalaxy]_vs[ctags,tree_sitter]` | 1 | **Minor GitGalaxy over-anchor.** `script` @ `revealjs_decks/demo.html:142` — the bare `<script type="text/template">` tag opening a reveal.js code-listing slide. HTML `func_start` (`<(script\|style)…`) anchors a function-analog on every `<script>`/`<style>` block; for a non-executable `text/template` block with no embedded code it recognises, the anchor is left with the bare name `script` and no corroboration. Symmetric `type=` exclusion for `func_start` filed as [#2492](https://github.com/squid-protocol/gitgalaxy/issues/2492) part 2 (deferred — `language_standards.py` change, needs its own differential scan). No credit/debit — a marginal FP, not a structural win. |
| `agree[tree_sitter]_vs[ctags,gitgalaxy]` | 2 | **Resolved / non-reproducing — comparison-tooling artifact.** `Example` @ `revealjs_decks/demo.html:145`, `SecondExample` @ `:158`, both `function` declarations inside the same `<script type="text/template">` slide-sample block. `tree_sitter_accuracy_audit._html_embedded_ts_funcs` (shared by `tri_comparison_gatherer`) injected the JavaScript grammar into **every** `<script>`, checking only `src=` and never `type=` — parsing two phantom functions from a data block the browser never runs, GitGalaxy never descends into, and ctags never reads. **Fixed this pass** ([#2492](https://github.com/squid-protocol/gitgalaxy/issues/2492) part 1): `_html_embedded_ts_funcs` now skips a `<script>` whose `type` is present and not in `_EXECUTABLE_SCRIPT_TYPES` (mirrors its `src=` skip and the HTML spec's classic/module-script gate). Regression test: `tests/tools/test_html_embedded_ts_funcs.py`. |

### Recall audit (skill step 2.6)

Every function `tree-sitter` or `ctags` reports that GitGalaxy does not, across the whole 54-file
`language-crucible/data/html` corpus, was individually assessed (`recall_audit.py html` +
whole-corpus name-diff via `gather_language("html")`).

- **Post-fix: 0 non-detections.** GitGalaxy has **zero real recall gaps** in html — every
  `<script>` / `<style>`-embedded function and every plain-markup structural signal `tree-sitter`
  finds, GitGalaxy also finds.
- **Pre-fix: 2 non-detections**, both bucket 2 (comparison-tool artifact, GitGalaxy correct):
  `Example` / `SecondExample` in the `text/template` block above. Zero bucket-1 (real gap).

### Measured accuracy (post-fix, `tests/tree_sitter_accuracy_baseline_html.json`)

| Metric | Value | Note |
| :--- | :---: | :--- |
| Function recall | **37 / 37 = 100%** | was 94.9% (39 real) — the 2 phantom `real_functions` removed by the #2492 fix |
| Function precision | 37 / 38 = 97.4% | the 1 "extra" is the `script`@142 over-anchor ([#2492](https://github.com/squid-protocol/gitgalaxy/issues/2492) part 2) |
| Class recall / precision | N/A | `<form>` / `<table>` / custom-element boundaries are not what tree-sitter counts as a class |

On this corpus `tree-sitter` currently leads html function precision (37/37 vs GitGalaxy's
37/38) on the strength of that single `script`@142 over-anchor; #2492 part 2 closes the gap.

### Where GitGalaxy wins outright

The 37-occurrence consensus shape: GitGalaxy's polyglot detector descends into `<style>` and
`<script>` blocks and names the embedded CSS at-rules / JS functions inside them —
`ctags`-html cannot parse embedded CSS or JS at all, so it reports nothing for any of the 54
files' style/script content.

### Where the other tools have real, documented gaps

- **ctags-html**: no CSS parser, minimal JS-in-markup — structurally blind to every embedded
  `<style>` / `<script>` construct (noted in `tests/tools/ctags_reader.py`'s html section).
- **tree-sitter-html**: models `<style>` / `<script>` bodies as opaque `raw_text` — the tri-
  comparison and accuracy tools compensate by injecting the css/javascript grammar (#2421 /
  #2452), and now correctly skip non-executable `<script type>` blocks (#2492 part 1).

### Bugs found & fixed in comparison tooling

- [#2492](https://github.com/squid-protocol/gitgalaxy/issues/2492) part 1 —
  `_html_embedded_ts_funcs` counted phantom functions from non-executable `<script type=...>`
  blocks (`text/template`, `x-shader/*`, `math/tex`). Fixed + regression-tested this pass.

### Full record

`docs/self_scan/tri_comparison_ledger.json` (filter `html/`) and
`docs/self_scan/tri_comparison_points_of_interest.md` (`## html`).

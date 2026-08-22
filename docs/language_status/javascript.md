# JavaScript — Structural Signature Coverage

Snapshot generated 2026-08-10 against `main`. Source: `LANGUAGE_DEFINITIONS["javascript"]` in
`gitgalaxy/standards/language_standards.py`, `tests/extraction/languages/test_javascript.py` /
`test_javascript_strict.py`, closed GitHub issues, and
[`gitgalaxy-raw-output`](https://github.com/squid-protocol/gitgalaxy-raw-output). Re-run the
`language-status` skill's data-gathering commands before trusting these numbers if this doc looks
old relative to `last_updated` below.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | ES2025 / React 19 / Node 22+ |
| `_meta.blueprint_version` | v5.0 |
| `_meta.last_updated` | 2026-02-18 |
| `lexical_family` | `standard_block` (`//` line comments, `/* */` block comments) |
| Structural signature keys wired | 61 / 64 (3 explicit `None`, see §4) |
| Extraction-gauntlet tests (`test_javascript.py`) | 53 |
| Strict-signature tests (`test_javascript_strict.py`) | 73 |
| Total dedicated JavaScript test cases | 126 |
| Real-world function recall vs. tree-sitter ground truth | 90.9% (expressjs/express) / 67.5% (GitGalaxy's own `site/js/`) — see §9 |
| Real-world function precision vs. tree-sitter ground truth | 84.7% (express) / 92.8% (`site/js/`) — see §9 |
| Real-world class recall vs. tree-sitter ground truth | 100% (`site/js/`; express has no classes) — see §9 |
| Real-world args-count exact match (for functions found) | 100% (both corpora) — see §9 |

## 2. Identification surface

- **Extensions:** `.js .mjs .cjs .jsx .es6 .es .pac .sjs .ssjs .xsjs .xsjslib .jsm ._js .bones .gs` — modern/legacy suffixes, JSX, proxy-autoconfig scripts, SAP/enterprise server-side dialects, and Google Apps Script.
- **Exact filenames:** `Jakefile` — extensionless build-tooling script.
- **Discriminators:** `.js`, `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `bower.json`, `.eslintrc`, `.prettierrc` — ecosystem anchors.
- **Shebangs:** `node`, `nodejs`, `deno`, `bun`, `zx`, `phantomjs`, `casperjs`.

## 3. What GitGalaxy detects

Grouped by the phase headers `language_standards.py` and `how_to_add_a_language.md` use.
Description is what JavaScript's *actual* regex matches, not the generic cross-language definition.

**Topology & structure**
| Key | What it captures for JavaScript |
|---|---|
| `branch` | `if else switch case default for while do catch finally continue break try`, `&& \|\| ? ??` |
| `args` | Three signature shapes, each with its own capture group (bounded to prevent ReDoS on massive positional/destructured sets): `function`/`async function`/generator parameter lists; arrow-function parameter lists (`(x, y) =>` or a bare `x =>`); and ES6 class/object method shorthand (`name(...) {`), the last gated behind an explicit "Invocation Shield" `(?=[ \t\n]*\{)` requiring the signature to actually open a block — added specifically because, without it, the engine hallucinated plain invocations as definitions (see §9/#1221 for a case where the *sibling* `func_start` regex still has this exact gap) |
| `structural_boundaries` | `let var import export return class extends super await delete yield`, `=>` |
| `func_start` | Standard `function`/generator declarations, namespace assignments (`foo.bar = function`), object-literal methods (`foo: function`), ES6 class/object methods, and arrow functions assigned across a "Vertical Assignment Shield" that tolerates the `=`/`:`/`=>` split across multiple lines |
| `class_start` | `class Name [extends Base]` |

**Safety & risk**
| Key | What it captures for JavaScript |
|---|---|
| `safety` | (see `language_standards.py` for the exact alternation — not separately audited in this pass) |
| `safety_bypasses` | Loose `==`/`!=` (non-strict comparison), `with`, `void`, `eslint-disable` comments, `@ts-nocheck` |
| `high_risk_execution` | (AI/ML + shell-out sensors — not separately audited in this pass) |
| `io` | (not separately audited in this pass) |
| `api` | `export`, `module.exports`, `exports.`, NestJS-style `@Controller/@Resolver/@Get/@Post/@Put/@Delete` decorators |
| `state_mutation` | (not separately audited in this pass) |
| `dead_code` | Commented-out `// if/for/while/function/class/return/var/const/let/import` |
| `doc` | `/**` JSDoc blocks, `@param @return @throws @deprecated @typedef @type @template` |
| `test` | (Jest/Mocha-family sensors — not separately audited in this pass) |

**Architecture & domain sensors**
| Key | What it captures for JavaScript |
|---|---|
| `concurrency` | (not separately audited in this pass) |
| `ui_framework` | (not separately audited in this pass) |
| `closures` | `=> {`, `() =>`, `function(...) {` |
| `globals` | `window. global. process.env document. navigator. self. globalThis.` |
| `decorators` | Any `@identifier` |
| `generics` | JSDoc `@template`/`@type` annotations (JS has no native generics syntax) |
| `comprehensions` | `.map/.filter/.reduce/.flatMap/.some/.every/.find/.forEach/.groupBy(` — JS's functional-array-method idiom, not a native comprehension syntax |
| `scientific` / `hardware_bridge` / `cryptography` / `reflection_metaprogramming` | Import-statement-scoped SDK/API sensors (numpy-family via node bindings, serialport/usb/bluetooth/websocket, crypto/bcrypt/jsonwebtoken, dunder-hook-equivalents) |
| `llm_api` / `llm_orchestrator` / `llm_vector_store` / `ml_traditional` / `dl_frameworks` | Shared cross-language `GLOBAL_` AI/ML SDK sensors (issue #322 moved JS off a hand-pasted per-language duplicate, same as Python) |
| `import` / `_dependency_capture` / `_named_token_capture` | ES module `import`/`export`, CommonJS `require`, dynamic `import(`; `_dependency_capture` extracts the dotted/quoted module path, `_named_token_capture` the `{ ... }` named-import list |
| `ownership` | `@author`/`Created by` JSDoc tags |

**Resource management & stability**
| Key | What it captures for JavaScript |
|---|---|
| `telemetry` | (logging-SDK sensors — not separately audited in this pass) |
| `debug_prints` | `console.log/warn/error/dir/trace/info/table/time` |
| `explicit_casts` | `Number String Boolean BigInt Symbol Array.from(` |
| `panics_and_aborts` | `throw abort process.exit` |
| `thread_sleeps` | `sleep delay setTimeout setInterval Atomics.wait` |
| `bitwise_ops` | `<< >> >>> ^ ~` |
| `sync_locks` | (not separately audited in this pass) |
| `immutability_locks` | `const readonly final Object.freeze Object.seal` |
| `cleanup` | `dispose close destroy clearTimeout clearInterval removeEventListener delete` |
| `encapsulation` | `private protected internal` keywords (TS-flavored, still scanned for JS), `#` private-field/method prefix |
| `listeners` | `on addEventListener subscribe watch effect` |
| `test_skip` | `test.skip it.skip describe.skip xit xdescribe mock stub` |

**Advanced algorithmic / hybrid domain / AppSec sensors**
| Key | What it captures for JavaScript |
|---|---|
| `lazy_evaluation` | `yield`, `yield*`, `function*` |
| `vectorized_math` | `matmul dot cross multiply(` |
| `serialization_parsing` | `JSON.parse JSON.stringify` |
| `regex_execution` | `new RegExp`, `.match/.replace/.search/.split(` |
| `time_date_logic` / `ipc_rpc_bridges` / `rce_funnel` / `exfiltration_camouflage` | (not separately audited in this pass — see `language_standards.py` for the exact alternations) |
| `memory_alloc` | `new ClassName` (heap-allocation proxy; JS is otherwise GC-managed) |

## 4. What GitGalaxy explicitly does not track

Three keys are hard-set to `None` in JavaScript's `rules` dict (Rule 4 of the engine's generation
rules: explicitly `None`, never a forced-fit regex, when a dimension doesn't exist natively):

- **`macros`** — JavaScript has no C-style preprocessor.
- **`pointers`** — no native pointer/address-of concept.
- **`inline_asm`** — no native inline-assembly construct.

## 5. Known limitations (accepted, not fixed)

Three gaps are deliberately documented rather than fixed, via `known_limitation`-named tests in
`test_javascript.py`:

1. **No whitespace tolerance between a generator method's `*` and its name.** `*foo()` matches;
   `* foo()` does not. Deliberate: an earlier whitespace-tolerant version false-positive-matched a
   JSDoc comment continuation line (`* A (storage) buffer attribute...`) as a generator method
   named `A`, caught via `crucible_check.py` against real corpus code (three.js).
2. **A bare call statement at true line start with no preceding modifier keyword is
   indistinguishable from a real method signature**, when the call's own argument list contains an
   inline callback (e.g. a Jest/Mocha `it('...', () => {...})` block). Same fundamental ambiguity
   #789 (csharp) and #815 (typescript) hit and deliberately did not fix at the regex level — real
   scope-tracking would be needed to disambiguate "method signature" from "call with an inline
   callback argument" from text shape alone. **Note:** this documented limitation is narrower than
   what §9 below found — see #1221, which is a *different*, unguarded case (no `{` anywhere on the
   statement at all, e.g. `next();`) that this known-limitation test doesn't cover.
3. **`func_start` has no string/comment awareness at the regex level.** Function-shaped text
   inside a string or template literal that happens to land at true line start still matches the
   raw regex (e.g. `let query = "function Foo() {";`). The real fix is downstream, in
   `detector.py`'s `_slice_by_braces` working against shielded code — gated for javascript/typescript
   specifically (most other Mode B languages aren't yet) and verified at the pipeline level in
   `test_detector.py`, not in this file.

## 6. Test depth

- **Extraction gauntlet** (`func_start`/`args`/`class_start`/`_dependency_capture`): 53 tests in
  `tests/extraction/languages/test_javascript.py` — valid/invalid/pathological cases per rule,
  plus the three known-limitation tests above (epic #813, issue #814).
- **Strict signature suite** (all other wired keys): 73 tests in
  `tests/extraction/languages/test_javascript_strict.py` (epic #518, issue #589; deepened further
  by issue #1072's AI/ML sensor pass).

## 7. Relevant closed work

**Epic-level hardening passes:**
- [#589](https://github.com/squid-protocol/gitgalaxy/issues/589) — Strict parsing tests for JavaScript structural signatures (epic #518).
- [#814](https://github.com/squid-protocol/gitgalaxy/issues/814) — Extraction hardening for JavaScript (epic #813).
- [#1072](https://github.com/squid-protocol/gitgalaxy/issues/1072) — Closed AI/ML sensor test-coverage gaps shared with Python.
- [#1209](https://github.com/squid-protocol/gitgalaxy/issues/1209) (PR [#1216](https://github.com/squid-protocol/gitgalaxy/pull/1216)) — Added the missing `args` capture group so `function_data.args` isolates the real parameter-list span instead of falling back to the whole match (the same class of bug #1199 fixed for Python). Directly verified as fixed by this doc's own §9 pass: args-count exact match is 100% on both measured corpora, for every function GitGalaxy found.

**Cross-language fixes that touched JavaScript along the way:**
- [#322](https://github.com/squid-protocol/gitgalaxy/issues/322) — Moved JavaScript's (and Python's) hand-pasted AI/LLM SDK detection onto the shared `GLOBAL_LLM_*`/`GLOBAL_ML_*`/`GLOBAL_DL_*` pattern.
- [#1041](https://github.com/squid-protocol/gitgalaxy/issues/1041) — Nested functions were silently dropped from extraction (affected every Mode B language, JavaScript included).

**Real defects found via this doc's own §9 measured-accuracy pass (2026-08-10), filed, not yet fixed:**
- [#1220](https://github.com/squid-protocol/gitgalaxy/pull/1220) (fix landed while building this pass's tooling, not a JS-specific bug) — a hardcoded, stale-length synthetic `risk_vector` in `galaxyscope.py`'s credential-leak escalation path crashed `--db-only` scans of any repo containing a flagged secret. Blocked scanning `expressjs/express` (its committed `.npmrc` trips the detector) until fixed.
- [#1221](https://github.com/squid-protocol/gitgalaxy/issues/1221) (OPEN) — `func_start`'s method-shorthand branch has no trailing-`{` requirement (unlike `args`' own "Invocation Shield" for the same shape), so bare call statements at line start (`next();`, `hash({...}, function(...) {`) are misidentified as function definitions. Confirmed on real code: 9 of 59 "functions" GitGalaxy reported for the express corpus were phantom call-sites (~15% precision loss). Also confirmed to affect `typescript`, `java`, `csharp`, `apex`, `dart`, `groovy` via the same regex-level check.
- [#1222](https://github.com/squid-protocol/gitgalaxy/issues/1222) (OPEN) — A real, differently-named, same-shaped function can be silently dropped from `function_data` even though `func_start`'s regex correctly finds it — confirmed for a top-level duplicate-shaped function pair in express, and far more severely for ES6 class methods in GitGalaxy's own `site/js/` (one file recorded only its `constructor`, silently losing 9 of 10 real methods). Root cause not yet pinned down, but likely the same `_slice_by_braces` body-boundary/`last_end_idx` absorption mechanism #789 diagnosed (and left unfixed) for csharp.

Search performed via `gh issue list --search 'in:title "Extraction hardening: javascript"'` /
`'in:title "Strict parsing tests: `javascript`"'` / `'in:title javascript'` (2026-08-10).

## 8. Real-world evidence (`gitgalaxy-raw-output`)

Four repos from the `v2.4.7` batch, chosen for a size/shape spread:

- **[`express`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/express/express_galaxy_llm.md)** — small, canonical middleware framework; the corpus this doc's own §9 pass measures against directly (pinned to tag `v5.2.1`, cloned fresh rather than reusing this snapshot, since §9 needs raw source to diff against).
- **[`jquery`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/jquery/jquery_galaxy_llm.md)** — older-era, prototype-heavy single-file library; a useful stylistic contrast to express's modern module-per-file layout.
- **[`d3`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/d3/d3_galaxy_llm.md)** — data-visualization library, functional/declarative style.
- **[`three.js`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/three.js/three.js_galaxy_llm.md)** — large 3D-rendering engine; the real-corpus source of the generator-method known-limitation fix in §5, and thematically adjacent to GitGalaxy's own WebGPU visualizer (`site/js/`, this doc's §9 self-scan leg).

Each `_galaxy_llm.md` is the human-readable architectural brief; `_galaxy_audit.json.gz` and
`_galaxy_sbom.json.gz` in the same directory carry the raw per-file signature counts and SBOM if
deeper inspection is needed.

## 9. Measured accuracy (real-world corpus, vs. tree-sitter ground truth)

Everything above describes what's *wired* and how it's *tested in isolation*. This section
measures what the engine actually gets right on **real, unmodified production code**. Python's own
`docs/language_status/python.md` §9 used the stdlib `ast` module as ground truth; JavaScript has no
stdlib parser, so this pass uses `tree-sitter-language-pack` (PyPI, confirmed available, pre-compiled
`tree-sitter-javascript` grammar, no toolchain needed) — the exact path python.md's own §9 proposed
for scaling this methodology beyond Python.

**Methodology:** two independent corpora, chosen for different failure-mode exposure:

1. **`expressjs/express`** at pinned tag `v5.2.1`, cloned fresh (not reusing the `gitgalaxy-raw-output`
   snapshot in §8, which has no raw source to diff against) — 43 JavaScript files, mostly small
   top-level functions and Express-middleware-style callbacks, effectively zero ES6 classes.
2. **GitGalaxy's own `site/js/`** (the WebGPU 3D visualizer, real hand-written code, not
   generated/vendored) — 10 files, heavily class-based (`SearchController`, `AllyController`, the
   galaxy-engine renderer), the opposite shape from express.

For each JavaScript file in a `galaxyscope --db-only` scan, walked the file with tree-sitter and
collected every `function_declaration`/`generator_function_declaration`, every named
`function_expression`/`arrow_function` assigned to a variable/property/object-key, and every
`method_definition` (class and object-literal methods) — matching the shapes `func_start`'s own
comment claims to capture (see §3). Diffed names against `function_data.func_name` for the same
file, and per-function argument count (tree-sitter's `formal_parameters` named-child count, one
slot per positional/default/rest/destructured parameter — the same "calling-convention slot"
philosophy `ast_accuracy_audit.py` uses for Python) against `function_data.args`.

**A real, filed defect blocked this measurement entirely before it could run**: `galaxyscope
<express-checkout> --db-only` crashed with `sqlite3.OperationalError: 172 values for 167 columns`
on every run. Isolated to a hardcoded, stale-length synthetic `risk_vector` in the credential-leak
escalation path (`galaxyscope.py`) — express's own committed `.npmrc` trips the hardcoded-secrets
detector, and the escalation code built an 18-element vector against a `RISK_SCHEMA` that's now 13
elements. Fixed in [#1220](https://github.com/squid-protocol/gitgalaxy/pull/1220) before this
measurement could proceed — worth flagging because it means `--db-only` was silently unusable on
*any* repo containing a flagged secret until now, not just this one.

| Signal | express (v5.2.1) | `site/js/` | Combined |
|---|---|---|---|
| Real functions (tree-sitter) | 55 | 114 | 169 |
| Function recall | 90.9% (50/55) | 67.5% (77/114) | 75.1% (127/169) |
| Extra (phantom) functions | 9 | 6 | 15 |
| Function precision | 84.7% (50/59) | 92.8% (77/83) | 89.4% (127/142) |
| Real classes (tree-sitter) | 0 | 8 | 8 |
| Class recall | n/a | 100% (8/8) | 100% (8/8) |
| Args-count exact match (functions found) | 100% (50/50) | 100% (77/77) | 100% (127/127) |

**Read as:** args-count accuracy is a clean, unambiguous win — 100% exact match on every function
GitGalaxy found, across two structurally different corpora, directly confirming #1209/#1216's `args`
capture-group fix works correctly on real code, not just the synthetic fixtures in
`ARGS_COUNT_FIXTURES`. Class extraction is also fully reliable on the one corpus that has classes.
Function-level recall/precision is the weak spot, and the two corpora expose two *different* root
causes rather than one:

1. **Precision (phantom functions):** every extra function in both corpora was a bare call
   statement at line start (`next();`, `hash({...}, function(...) {`, `requestAnimationFrame(...)`,
   `setTimeout(...)`) misidentified as a definition — filed as
   [#1221](https://github.com/squid-protocol/gitgalaxy/issues/1221). Root cause: `func_start`'s
   method-shorthand branch has no trailing-`{` requirement, unlike `args`' own "Invocation Shield"
   for the identical shape (see §3's `args` row) — confirmed to also affect `typescript`, `java`,
   `csharp`, `apex`, `dart`, `groovy`.
2. **Recall (missing functions):** `site/js/`'s much lower recall (67.5% vs. express's 90.9%) tracks
   directly with class-method density — `search.js`'s `SearchController` class lost 9 of its 10
   real methods (only `constructor` survived), despite `func_start`'s regex correctly finding all
   10 at their real positions in the raw text. Filed as
   [#1222](https://github.com/squid-protocol/gitgalaxy/issues/1222), with a same-shaped but milder
   case in express too (a same-shaped, differently-named sibling function silently dropped). Root
   cause not pinned down precisely, but most likely the same `_slice_by_braces` body-boundary/
   `last_end_idx`-absorption mechanism issue #789 diagnosed (and left unfixed, scoped out as its
   own follow-up that was apparently never filed) for the analogous csharp case.

**Net effect:** this pass didn't just re-confirm #1209's fix (though it did, cleanly) — it surfaced
one blocking infra bug (fixed same-day, #1220) and two real, previously-undiscovered-for-JS
extraction defects (#1221, #1222), the second of which turns out to already have a well-understood
but unfixed architectural diagnosis on the books from over a year of engine history (#789). Neither
new issue was fixed here, matching this skill's own scope discipline (measure and file, don't fix
inline) — both need the fuller `harden-language-extraction` treatment (ReDoS sweep, golden-master
diff, per-language verification) given they touch `func_start`/`detector.py`'s shared slicing logic
rather than being isolated one-file config bugs.

## 10. Tri-comparison sweep (GitGalaxy vs. tree-sitter vs. ctags, no privileged ground truth)

§9 above compares GitGalaxy against tree-sitter alone, treated as ground truth. This section is a
different exercise, run via the `tri-comparison-ledger-sweep` skill (2026-08-21): a genuine 3-way
comparison across an 18-file jquery/react/threejs corpus
(`language-crucible/data/javascript/`), where no single tool is assumed correct — every
disagreement is root-caused by reading real source before it's recorded either way. All 8 shapes
the tri-comparison ledger had accumulated for javascript were investigated and validated in this
pass; none remain open (`docs/self_scan/tri_comparison_ledger.json`, keys prefixed
`javascript/`).

**Summary: 8 shapes investigated, 0 confirmed GitGalaxy engine defects, 2 confirmed bugs in this
repo's own comparison tooling (fixed), 1 methodology-only artifact (no fix possible or needed).**
Every real discrepancy traced back to the *other* two tools, not to GitGalaxy — a cleaner outcome
than `c`'s own tri-comparison pass (0 defects either way) and a starker one than `rust`'s (2 real
GitGalaxy bugs found) — see those languages' own docs for contrast.

**Where GitGalaxy wins outright:**

- **Flow-typed react source breaks both other tools, independently, for different reasons.** All
  four affected corpus files (`react/ReactFiberBeginWork.js`, `ReactFiberWorkLoop.js`,
  `ReactFlightServer.js`, `ReactSymbols.js`) carry the `@flow` pragma. tree-sitter-javascript can't
  parse Flow's parenthesized type-cast syntax (`(expr: Type)`) — confirmed directly:
  `ReactFiberWorkLoop.js`/`ReactFlightServer.js` each produce a SINGLE `ERROR` node spanning the
  *entire file*, and real functions inside it (`beginWork`, `attemptEarlyBailoutIfNoScheduledUpdate`,
  18 others sampled) have no tree-sitter node at all. ctags' independent hand-written JS scanner
  hits its own cascade on a *different* trigger — a Flow return-type annotation (`): Type {`) —
  confirmed via a minimal isolated repro, not just the corpus observation. A Flow parameter type
  with a union (`current: Fiber | null`) can also corrupt a surviving tree-sitter node's own
  argument count without losing the function entirely (`updateForwardRef`: 5 real params,
  GitGalaxy=5, ctags=5, tree-sitter=4). GitGalaxy's regex depends on neither tool's parse state and
  is unaffected by any of this. Full write-up: `docs/why_gitgalaxy_beats_ast_here.md`'s Claim 3
  extension.
- **ctags' "class" kind is a blanket pre-ES6-constructor heuristic, not a real class check.** ctags
  tags its `c` kind on any bare object-literal assignment (`var cssHooks = {...}`) or
  function-expression assignment (`jQuery.Event = function(){}`), whether or not `new` is ever used
  on it — 93 occurrences across the corpus (`jqXHR`, `cssHooks`/`cssShow`, `promise`,
  `Event`/`event`/`special`, threejs's `ALPHA_MODES`/`WEBGL_CONSTANTS`/etc.). GitGalaxy's
  `class_start` regex and tree-sitter's `class_declaration` node both correctly require the literal
  `class` keyword.
- **ctags loses real function names inside call-argument object literals.** A function-valued
  object-literal property (`ajaxSetup: function(...) {...}`) keeps its real name when directly
  assigned, but loses it (falling back to a synthetic placeholder) specifically when the literal is
  a call argument — e.g. jquery's own `jQuery.extend(jQuery, {ajaxSetup: ..., ajax: ..., ...})`
  idiom, which drops `jquery/core.js`'s entire 26-function utility-belt down to a single real ctags
  tag. 265 occurrences, the single largest shape in the corpus.

**Bugs found and fixed in the comparison tooling itself, separate from either tool's grammar/scanner
limitations above:**

1. `tests/tools/tri_comparison_gatherer.py`'s own tree-sitter walker (deliberately simpler than
   `tree_sitter_accuracy_audit.py`'s) had never been given the reserved-keyword/known-hallucination
   `method_definition` filter the latter already proved necessary for this exact Flow-cascade
   mechanism (`#1633`) — every phantom `if`/`for`/`let`-named node was still polluting the ledger's
   own javascript readings. Fixed by reusing the existing `tsaa` frozensets directly (one source of
   truth) plus adding one newly-confirmed hallucination name.
2. ctags' javascript-specific `AnonymousFunction<hex>`/`AnonymousClass<hex>` synthetic-placeholder
   scheme (distinct from the C parser's `__anon<hex>` scheme this module already filtered) was
   unfiltered, inflating ctags' apparent function/class counts with unnamed-callback noise. Fixed —
   but an early, ungated version of this fix was caught regressing an *unrelated* language before
   it shipped: PHP's ctags parser reuses the identical `AnonymousClass<hex>` text for its own real
   `new class {...}` anonymous-class language feature, so the filter had to be gated to
   `lang == "javascript"` specifically, not applied to every language the way the C-side `__anon`
   check already safely is. Caught by re-running the full 45-language chart regeneration and
   diffing every changed panel before committing, not assumed safe from the javascript corpus
   check alone.

**Methodology-only artifact (no defect, no fix):** `jquery/event.js` defines two structurally
unrelated pairs of object-literal properties both named `setup`/`trigger` (one pair takes 1 param,
a later, different pair takes 0). Ledger reconciliation pairs occurrences by name across the whole
file with no scope disambiguation, so this same-name collision produces a spurious 2-occurrence
args mismatch that isn't a real counting defect in any tool — just a limitation of comparing by
name alone.

Full record: `docs/self_scan/tri_comparison_ledger.json` (grep for `"javascript/`), and
`docs/self_scan/tri_comparison_points_of_interest.md` for the ranked human-readable log.

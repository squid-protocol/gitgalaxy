# Markdown (CommonMark / GFM / AsciiDoc)

## 1. At a glance

Markdown is GitGalaxy's canonical **literary language**: it is deliberately measured on its own
`lit_*` signal plane (headers, fenced code blocks, diagrams, links) instead of the code-signal
plane, and it is one of the five `is_inert` static-asset languages (with plaintext/json/yaml/csv)
that skip the security lens and popularity census entirely. Its entire body is documentation
mass: prism's Prose Bypass (#691) routes every line into the comment/doc surface, so
`coding_loc` is always 0 and `doc_loc` carries the file. Since #2638 it is also the first inert
language with a real dependency surface: relative links (`[text](sibling.md)`) are captured
into the import DAG, giving documentation popularity scoring and orphaned-docs detection.

## 2. Identification surface

- **Extensions:** `.md`, `.markdown`, `.mdown`, `.mkd`, `.mdx`, `.adoc`, `.asciidoc`
- **Exact matches:** extensionless `README`, `LICENSE`, `CHANGELOG`, `CONTRIBUTING`, `SECURITY`
- **Discriminators:** `mkdocs.yml`, `_config.yml`, `docusaurus.config.js`
- **Lexical family:** `line_exclusive` (HTML/SGML block comments are the only comment idiom)
- No shebangs (declarative text).

## 3. What GitGalaxy detects

The four literary signals (all `re.M`-anchored, one nesting level, ReDoS-bounded):

| rule | construct | notes |
|---|---|---|
| `lit_headers` | ATX headers `#`–`######` | the "probe analogue" — structure without functions |
| `lit_code_blocks` | ``` fenced blocks | fences count in pairs; ≤3-space indent only |
| `lit_diagrams` | ```` ```mermaid/plantuml ```` fences | case-insensitive; a subset of code blocks |
| `lit_links` | `[text](url)` inline links | one-level nested brackets and inner parens supported |

These feed the **instructional-density multiplier**: a folder's `doc_umbrella` shield scales up
to 2.0× with diagram/code-block/header/link mass, so high-quality docs measurably dampen the
risk of the code they sit next to.

**Dependency capture (#2638).** `_dependency_capture` extracts the target of every inline link
(image form included) whose target is a repo-relative path — scheme-prefixed (`https:`,
`mailto:`), protocol-relative (`//…`) and pure-anchor (`#…`) targets are excluded, and the
capture stops before fragments and titles, so the DAG resolver receives a bare path that the
census suffix map resolves in O(1). A README chain `main.md → a.md → b.md → c.md` produces
real DAG edges, popularity for the linked docs, and `import_count` on the linkers. Two engine
facts make this work, both fixed/established by #2638:

1. An `is_inert` language that **declares** `_dependency_capture` opts back into Phase-6
   dependency extraction (the other inert skips stay skipped).
2. detector.py's early-return paths (prose deflection, low-confidence bypass, empty
   `code_stream`, catastrophic-failure fallback) no longer emit a placeholder
   `"raw_imports": []` — that placeholder used to clobber the worker's already-extracted
   dependencies for every file that hit those paths.

## 4. What GitGalaxy explicitly does not track

All 18 code signals are absent **by design**, reviewed cell-by-cell and ledgered as validated
intended morphology in the rosetta corpus (`markdown-lit-plane-morphology`, 2026-09-01):
`args`, `branch`, `class_start`, `cleanup`, `doc`, `fragile_debt`, `func_start`, `globals`,
`high_risk_execution`, `import`, `io`, `ownership`, `planned_debt`, `safety`,
`safety_bypasses`, `state_mutation`, `telemetry`, `test`. The recurring reasons:

- Markdown has no callable units, control flow, or state — `lit_headers` are the structural
  analogue, and prose *about* io/safety/testing is documentation, not executable signal.
- A `doc` keyword rule would double-count the prose mass prism already routes to `doc_loc`.
- An `import` keyword rule would triple-count links, which are already counted as `lit_links`
  and captured for the DAG by `_dependency_capture`.
- Debt keywords (`TODO`/`FIXME`) in prose are content; with an empty code payload the debt
  rules could never fire anyway.

Fenced code blocks are **not** scanned as their embedded language: the planted
` ```text ` tripwire in the rosetta corpus pins that fenced content must never leak into code
signals.

## 5. Known limitations (accepted, not fixed)

- Reference-style link definitions (`[label]: ./target.md`) and autolinks (`<https://…>`) are
  not captured as dependencies — inline links only. Extendable if real-repo evidence shows
  reference-style locals are common.
- Links inside fenced code blocks DO count for `_dependency_capture` (it runs on the raw
  content buffer, the engine-wide convention for import extraction).
- `galaxyscope.py`'s global `import_cleaner` strips leading `import|from|require|use|source`
  with no word boundary; a captured `usage.md`/`sources.md` link target is mangled before DAG
  resolution (pre-existing, engine-wide; noted in #2638).

## 6. Test depth

`tests/extraction/languages/test_markdown_strict.py`: positive/negative pairs for all four
`lit_*` rules plus nested-delimiter, indentation, and case-sensitivity regressions (#597), and
the `_dependency_capture` suite (#2638): 7 positive capture cases, 7 negative
(scheme/anchor/protocol-relative/malformed), fragment/title boundary assertions, and 4 ReDoS
detonations. `tests/core_engine/test_detector.py` pins the early-return
`raw_imports`-placeholder regression.

## 7. Relevant closed work

- #691 — markdown prose deflection: route through `comment_analysis` so `lit_*` counts exist
  at all while `coding_loc`/`doc_loc` semantics stay untouched.
- #597 — strict-coverage hardening of the four `lit_*` regexes (nested delimiters, Wikipedia
  parens, closed ATX headers).
- #2638 — relative-link dependency capture + the inert opt-in + the early-return
  `raw_imports` placeholder fix (this doc's §3).

## 8. Rosetta cross-language consistency (control-corpus capstone)

This section is the [keyword-rosetta](https://github.com/squid-protocol/keyword-rosetta)
capstone: the control corpus plants identical intent in 46 languages and asks whether GitGalaxy
measures markdown the same way — every deviation from the 46-language median is measured bias,
tracked in [#2587](https://github.com/squid-protocol/gitgalaxy/issues/2587) (epic
[#2560](https://github.com/squid-protocol/gitgalaxy/issues/2560)) and validated in the corpus's
[deviation ledger](https://github.com/squid-protocol/keyword-rosetta/blob/main/deviation_ledger.json).

**Summary (2026-09-01).** The issue's original **29🔴 / 1🟡** was largely a reporting artifact
of comparing a markup language against a code-language median: the n/a machinery (GATING.md
"n/a semantics") reclassified the 18 absent-rule cells out of the red count, and this sweep
reviewed and ledgered every one of them (`markdown-lit-plane-morphology`) so none stays an
unreviewed warning. Final state: **11🔴 / 1🟡 across 19 comparable metrics, zero unreviewed
n/a cells, every residual ledgered** — the close criterion is met by the "every remaining
deviation ledgered as intended morphology" clause. The five-cause decomposition:

1. **One real engine gap, fixed** (#2638): `dependency_links` 0 vs median 3. The corpus plants
   a real `main→a→b→c` link chain and markdown links to sibling files ARE dependencies. Root
   cause was two-fold: markdown (as an `is_inert` language) skipped Phase-6 import extraction
   entirely, and detector.py's early-return paths clobbered worker-extracted imports with a
   placeholder `"raw_imports": []`. With both fixed, the chain resolves exactly to the median
   (`import_count` main/a/b = 1, c = 0; popularity a/b/c = 1; `api` stays 0 — orphan→api
   conversion needs functions).
2. **Missing rule with genuine morphology:** none — every absent rule failed the bucket-2
   "name the language's own idiom" test (see §4).
3. **Corpus authoring gap:** none — the shells plant the lit plane and the link chain correctly.
4. **Intended morphology, ledgered:** the 18 n/a cells + `functions_found` 0 (headers are the
   probe analogue) + `keyword_hits` −45% (only 4 lit rules can hit) + `comment_lines` +183%
   (a documentation format measuring high on a documentation-mass metric is correct —
   `markdown-prose-is-doc-morphology`), and all nine §3 risk metrics: a no-code language's
   risk formulas bottom out at their constant terms (`risk_documentation` measures
   documentation *of code*), structurally incomparable rather than biased.
5. **Median inflation:** none affecting markdown.

**Side effect worth naming:** the inert opt-in also woke yaml's deliberately-authored (but
silently dead) `_dependency_capture` — GitHub Actions `uses:`/`image:` values now produce real
DAG edges too (`dependency_links` 0→3 on the corpus, supply-chain relevant on real repos).
That moves [#2606](https://github.com/squid-protocol/gitgalaxy/issues/2606)'s numbers as a
free improvement; yaml's own sweep remains separate work.

**Remaining out-of-band** (all accounted, none actionable): the ledgered morphology above.
Every residual is either on the lit plane by design or a downstream risk shadow; the close
criterion is "every remaining deviation ledgered as intended morphology".

Reproduce: `GALAXYSCOPE_BIN=<venv>/bin/galaxyscope python tools/verify_language.py markdown`
in the corpus repo (gate: 89 assertions), `python tools/language_deviations.py markdown` for
the live vs-median band table, and the corpus's
[findings_by_language.md#markdown](https://github.com/squid-protocol/keyword-rosetta/blob/main/docs/findings_by_language.md#markdown) /
[bias chart](https://github.com/squid-protocol/keyword-rosetta/blob/main/docs/bias_variance_chart.svg).

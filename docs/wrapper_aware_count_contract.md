# The wrapper-aware count contract (`wrapped_<rule>`)

> Epic [#3313](https://github.com/squid-protocol/gitgalaxy/issues/3313), step 4. Same shape as
> `docs/unreferenced_by_name_contract.md`, with the same up-front difference: this is **not a
> rule**. No language registry produces it. It is derived once per scan by
> `core/wrapper_resolver.py` from the wrapper fact channel (`wrapper_data`, step 3), and it sits
> **beside** a literal rule's count, never inside it.

## Why it exists

A literal-vocabulary rule counts calls to a primitive by name. A project that wraps the primitive
in its own helper hides every call site of the helper from the rule
(`docs/known_blind_spots.md`, Blind spot 1). curl's 8.17 → 8.18 refactor is the measured case:
its allocator call sites moved behind `curlx_*` macros and its literal `memory_alloc` fell 82%
while nothing about its memory management changed. This count is the part of the behaviour the
literal rule cannot see.

## The contract

> **One hit is one unqualified call site that resolves to a project-local wrapper of the rule
> recorded in `wrapper_data`.**

Columns: `file_data.wrapped_debug_prints`, `wrapped_panics_and_aborts` and
`wrapped_memory_alloc` (0 when a file has none), and the same three on `repo_data`, summed from
the snapshot's `file_data` rows. `kind` is `site` and `unit` is **sites**, the same unit as the
literal rule's count, so `literal + wrapped` is a count of distinct code sites that reach the
behaviour, either directly or through a project wrapper.

Corollaries, each pinned by a test in `tests/core_engine/test_wrapper_aware_counts.py` or the
step-3 resolver tests:

1. **A literal hit is never a wrapped hit.** The primitive's own call inside a wrapper's body
   (`malloc(` inside `xmalloc`) is the literal count's. Only calls *to* the wrapper are wrapped
   sites, so the two columns never count the same site twice.
2. **A macro body is not a call site.** `#define Curl_safefree(p) do { curlx_free(p); ... }`
   calls `curlx_free` once per *use* of `Curl_safefree`; the use is the site. Uses are counted
   where they appear in function bodies.
3. **A chain is several sites, each counted once.** `curl_free(p)` in a caller is one site (of
   `curl_free`); the `curlx_free(p)` inside `curl_free`'s body is another (of `curlx_free`). Each
   is a real place the code reaches the behaviour.
4. **Resolution is step 3's, unchanged.** Same file first, then a unique definition. Ambiguous
   names, methods and qualified calls (`x.f(`) count nothing, so an unresolved call lowers the
   count rather than inventing one.
5. **Scope is step 3's measured scope.** `debug_prints`/`panics_and_aborts`: short branchless
   function wrappers in every by-name language. `memory_alloc`: C/C++/Objective-C functions,
   `#define` aliases and their closure. Outside that scope the count is 0 by construction, which
   means "not measured here", not "none". Allocator wrapping in other languages is the stated
   blind spot, not a measured absence.
6. **It is recomputed every scan.** A delta scan re-resolves from the persisted
   `file_data.wrapper_facts`; the count itself is never restored from a previous run.

## Decisions

- **D1: no score reads it.** No risk formula, exposure, archetype or graph metric takes a
  `wrapped_*` value as input. It is a reported fact beside the literal signal, so a reader can
  tell "low" from "hidden". A guard test fails if anything under `gitgalaxy/metrics/` references
  one. Letting a score read it is a separate, measured change (the `score-contract-audit`
  process), because it would move every score that reads the literal rule for every repository
  with wrappers.
- **D2: it is never folded into the literal column.** The literal rule's count keeps its
  syntactic, cross-language contract (`docs/signal_contracts.md`, stream contract corollary 3).
  The wrapper-aware figure is a separate column and a separate report line.
- **D3: report surfaces are presence-keyed.** The audit report's `12. Calls Through Idiom
  Wrappers` block appears only on files with wrapped sites, showing literal and wrapped side by
  side. The LLM brief's section 14 shows the repo-wide totals per rule.

## Acceptance: curl 8.17 → 8.18

The epic's acceptance evidence is that the literal signal still drops across the refactor while
literal + wrapped shows the behaviour moving behind `curlx_*` rather than vanishing. The measured
walk is recorded in the step-4 PR.

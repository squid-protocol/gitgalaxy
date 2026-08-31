# Tcl — Structural Signature Coverage

Snapshot generated 2026-08-30 against `main`. Source: `LANGUAGE_DEFINITIONS["tcl"]` in
`gitgalaxy/standards/language_standards.py`, `tests/extraction/languages/test_tcl.py` /
`test_tcl_strict.py`, closed GitHub issues, and the tri-comparison ledger. Re-run the
`language-status` skill's data-gathering commands before trusting the §1–8 numbers if this doc
looks old relative to `last_updated` below.

**Scope note:** §9 was written by the `tri-comparison-ledger-sweep` skill and is the part of this
doc with the most recent, most detailed investigation behind it — a real 3-way
GitGalaxy / tree-sitter-tcl / Universal-Ctags comparison on the `language-crucible` corpus. §§1–8
are the standard primary-source snapshot.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | Tcl 8.6 / SQLite Test Suite |
| `_meta.blueprint_version` | (unset) |
| `_meta.last_updated` | 2026-03-11 |
| `lexical_family` | `line_exclusive` (`#`-to-end-of-line only — Tcl has no native block comment; `if 0 { ... }` is a real but unrecognized developer hack, not a comment form this engine models) |
| Structural signature keys wired | 39 / 47 (8 explicit `None`) |
| Function-slicing integration mode | **Mode B (brace slicing)** — no `ScopeParsingRegistry` entry; `proc name {args} {body}`'s trailing `{ }` bounds the body directly, same default path as most brace languages |
| Extraction-gauntlet + strict test files | `test_tcl.py` (43), `test_tcl_strict.py` (65) — 108 passing |

## 2. Identification surface

- **Extensions:** `.tcl`, `.itcl`, `.tbc` (compiled bytecode), `.tm` (Tcl Modules). **`.test` was
  deliberately removed** (inline comment: `# Removed .test`) — see §5, this has a real, sizable
  effect on what the real-world corpus below actually gets scanned.
- **Exact filenames:** `tclIndex`, `pkgIndex.tcl` (package index files).
- **Discriminators:** `.tcl`, `tclIndex`, `.test`, `Makefile` — `.test` is listed here as a
  disambiguation *anchor* only (helps confirm a directory is a Tcl project), never as a
  scannable extension itself; the two lists serve different purposes and aren't the same
  question.
- **Shebangs:** `tclsh`, `wish` (Tk), `bin/expect`, `jimsh` (Jim Tcl).

## 3. What GitGalaxy detects

`func_start` anchors `^\s*proc\s+<name>` where `<name>` allows Tcl's real identifier character
set for procs (`a-zA-Z0-9_:\-!?` — colons for namespace qualification, plus the `-`/`!`/`?`
Tcl convention for predicate/mutator-style names like `dict-exists?`), optionally followed by the
full brace-nested parameter list (up to 3 levels of `{ }` nesting, to survive deeply nested
default-value forms) before the lookahead confirms a real declaration head. `args` captures that
same brace-nested parameter list with the identical 3-level-nesting tolerance and reports it via
`_args_tcl_pattern_list_groups` (an opt-in depth-aware parsing mode, not a plain capture group,
needed because Tcl parameter lists routinely nest — `proc foo {{db db} {mode readonly}} {...}`).
`class_start` covers Tcl's three real OOP conventions — `oo::class create <Name>` (Tcl 8.6's
native TclOO), `snit::type <Name>` (Snit), `itcl::class <Name>` (incr Tcl) — and is in
`_CLASS_START_NAMED_EXTRACTION_LANGS`, so a real match reaches the named class list, not just a
signal count (see §5 — the corpus at hand has none of these forms to exercise it against).

The `test` key is Tcl's own **"SQLite mega-sensor"** — a rule built specifically to recognize
SQLite's Tcl test-harness vocabulary (`do_test`, `do_execsql_test`, `do_catchsql_test`,
`do_eqp_test`, `do_ioerr_test`, `do_faultsim_test`, bare `test <name>`, `tcltest::`,
`finish_test`) alongside standard `tcltest`. `_dependency_capture` anchors
`package require` / `source` / `load` and captures the module/file argument through an optional
`-exact` flag and optional brace/quote wrapping. The remaining wired keys (`branch`, `safety`,
`safety_bypasses`, `io`, `concurrency`, `reflection_metaprogramming`, `globals`, `encapsulation`,
…) read Tcl's own control-flow and command vocabulary directly — e.g. `safety_bypasses` is
`eval`/`uplevel`/`upvar` (Tcl's actual unrestricted-evaluation/context-manipulation primitives,
not a generic cross-language stand-in), and `globals` specifically handles `::env` needing no
leading `\b` (`$::env(HOME)` sits between two non-word characters, where a real word boundary can
never fire).

## 4. What GitGalaxy explicitly does not track

Eight keys are wired to `None`:

- `decorators` — Tcl has no decorator/annotation syntax.
- `generics` — no generic/type-parameter syntax.
- `dependency_injection` — no DI/IoC framework convention in the language itself.
- `ssr_boundaries` — not a web-rendering language construct Tcl has.
- `macros` — no C-style preprocessor.
- `pointers` — no pointer/address-of syntax.
- `memory_alloc` — no manual memory-management primitives.
- `inline_asm` — no inline-assembly construct.

Everything else in the 47-key schema is wired.

## 5. Known limitations (accepted / tracked)

- **`.test` files are entirely outside the scannable extension surface**, by design (§2). The
  real-world consequence is large, not theoretical: the `language-crucible` tcl corpus has 156
  real files across 9 upstream repo folders (see §8's `SOURCES.md`), but only **29** carry a
  `.tcl`/`.itcl`/`.tbc`/`.tm` extension — the other **114** (73% of the corpus, all of SQLite's
  own `*.test` regression suite: `sqlite_core_dml`, `sqlite_query_planner`, `sqlite_cte_window`,
  `sqlite_json_triggers`, `sqlite_fts5`, `sqlite_rtree`) never reach prism/detector at all.
  Confirmed directly (`find data/tcl -type f | sed 's/.*\./&/' | sort | uniq -c`: 114 `.test`
  vs. 32 `.tcl`) and via `tree_sitter_accuracy_audit.py --lang tcl` (`files_scanned: 29`). This
  is an intentional scoping choice (`# Removed .test` in `language_standards.py`, no other
  language in this repo claims `.test` as a real extension, so it isn't a collision-avoidance
  case either) with no further rationale recorded in issue/commit history — worth a deliberate
  look, not silently assumed correct or incorrect. **Every number in §9 below is scoped to the
  29 `.tcl` files only** — it says nothing about extraction quality on the other 114.
- **`class_start` has zero real-world corpus coverage.** All three of its wired conventions
  (TclOO `oo::class create`, Snit `snit::type`, incr Tcl `itcl::class`) are real, correctly-wired
  patterns, but neither `macports_port_api`/`macports_registry` (procedural, namespace-based Tcl,
  no OOP framework in use) nor the SQLite test harness declares a single one — confirmed via
  `tree_sitter_accuracy_audit.py --lang tcl` (`found_classes: 0`, `real_classes: 0`) and ctags'
  own Tcl kind table having no class-shaped kind at all (`CTAGS_CLASS_KINDS["tcl"] = set()`).
  Structurally the same "frontier language, no ground truth" situation lua's `class_start`
  heuristic is in (see `lua.md` §5/§9) — the difference is Tcl's three forms are explicit
  keyword-anchored declarations, not a best-effort heuristic, so there's less inherent precision
  risk if a real one ever appears; it just hasn't in this corpus yet.
- No `known_limitation`-named test cases exist in `test_tcl.py`/`test_tcl_strict.py` — the
  gauntlet has no currently-accepted, deliberately-not-fixed extraction gap on record.

## 6. Test depth

- **Extraction-gauntlet tests:** 43 cases in `tests/extraction/languages/test_tcl.py`
  (`func_start` / `args` / `class_start` / `_dependency_capture`, valid / invalid / pathological).
- **Strict-signature tests:** 65 cases in `tests/extraction/languages/test_tcl_strict.py` (ReDoS
  immunity, scaling-ratio methodology, boundary correctness).

## 7. Relevant closed work

- [#848](https://github.com/squid-protocol/gitgalaxy/issues/848) — extraction hardening: tcl
  (epic #813).
- [#614](https://github.com/squid-protocol/gitgalaxy/issues/614) — strict parsing tests for `tcl`
  structural signatures (epic #1069).
- [#1512](https://github.com/squid-protocol/gitgalaxy/issues/1512) — `args` regex overcounted a
  default-value braced pair (`proc foo {{db db}}` measured `got=2, real=1`); fixed in
  [#1539](https://github.com/squid-protocol/gitgalaxy/pull/1539).
- [#1504](https://github.com/squid-protocol/gitgalaxy/issues/1504) — `tree_sitter_accuracy_audit`
  itself never found tcl's own parameter list (grammar field is `arguments`, the audit was
  reading `parameters`) — a ground-truth-tool bug, not a GitGalaxy defect; fixed in
  [#1507](https://github.com/squid-protocol/gitgalaxy/pull/1507).
- [#2218](https://github.com/squid-protocol/gitgalaxy/issues/2218) — "func_start misses procs
  with nested braces in args", fixed in [#2224](https://github.com/squid-protocol/gitgalaxy/pull/2224)
  — later shown by #2242's own re-investigation to have named the wrong mechanism (the real cause
  was a `detector.py` quote-shielding bug, not `func_start` itself), though the fix direction
  (crediting ctags/tree-sitter, debiting GitGalaxy) was already correct.
- [#2242](https://github.com/squid-protocol/gitgalaxy/issues/2242) — real confirmed engine
  defect: `detector.py`'s generic (non-language-specialized) quote-shielding branch used an
  *unbounded* single-quote pairing regex for tcl (which has no single-quote string syntax at
  all), so an odd count of literal `'` characters in unrelated SQL text
  (`sqlite/tester.tcl:2234`'s `string map {' ''} $contents`) desynced the pairing and blanked out
  two real proc headers (`drop_all_tables`, `drop_all_indexes`) as if they were inside a string.
  Fixed in [#2266](https://github.com/squid-protocol/gitgalaxy/pull/2266) by gating tcl out of
  that shielding branch entirely (same convention already used for perl/powershell, which also
  have no single-quote string syntax).
- [#2512](https://github.com/squid-protocol/gitgalaxy/issues/2512) / the ctags-side fix landed
  2026-08-30 (see §9) — not a GitGalaxy issue at all, a fix to this repo's own `ctags_reader.py`
  tri-comparison tooling.

## 8. Real-world evidence

The tri-comparison corpus is `language-crucible/data/tcl/` — 156 files across 9 upstream repo
folders (see the corpus's own `SOURCES.md`), though only 29 are scannable `.tcl` files (§5):

- **[macports-base](https://github.com/macports/macports-base)** (`macports_port_api/`,
  `macports_registry/`, 30 total files / 27 `.tcl`) — real, non-test-harness application Tcl: the
  `Portfile` DSL implementation (`src/port1.0/`, namespace-qualified procs, `option`/`options`
  metaprogramming, heavy `eval`/`uplevel`/`upvar`) and the installed-port registry/receipts layer
  (`src/registry2.0/`, SQLite-backed state via Tcl bindings). This is the source of the
  namespace-qualification convention §9 investigates. `_galaxy_llm.md` on
  `gitgalaxy-raw-output/v2.4.7/macports-base`.
- **[sqlite](https://github.com/sqlite/sqlite)** (`sqlite/`, plus the 6 `sqlite_*` `.test`-only
  subdirectories excluded from scanning per §5) — the *canonical* stress case for the `test`
  key's SQLite mega-sensor: `tester.tcl` (the test harness itself) and `malloc_common.tcl`
  (fault-injection helpers) are the two real `.tcl` files that make it into scope; the 114
  `.test` regression files (full-text search, R-Tree, window functions, JSON, the query planner)
  document the SQLite project's real Tcl test-suite scale even though they aren't scanned today.
  `_galaxy_llm.md` on `gitgalaxy-raw-output/v2.4.7/sqlite`.

## 9. Tri-comparison: GitGalaxy vs. tree-sitter-tcl vs. Universal Ctags

**Summary.** Tcl's ledger backlog is fully cleared: **8/8** discrepancy shapes are
`status: "validated"`, **0** currently reproduce as open questions. One real GitGalaxy engine
defect was found and fixed across this doc's history (#2242, three duplicate/stale ledger shapes
all tracing to the same root cause); one real tri-comparison-*tooling* defect (not a GitGalaxy
engine bug) was found and fixed 2026-08-30. Measured via `tree_sitter_accuracy_audit.py --lang
tcl` (scoped to the 29 real `.tcl` files, §5):

| Metric | Value |
|---|---:|
| `files_scanned` | 29 |
| `real_functions` (tree-sitter ground truth) | 337 |
| `found_functions` | 337 |
| `extra_functions` (GitGalaxy-only, tree-sitter has no record) | 3 |
| `real_classes` / `found_classes` | 0 / 0 (§5 — no corpus coverage, not a defect) |
| `args_exact_match` | 337 / 337 |

Function recall **100.0%** (337/337), precision **99.1%** (337/340) against tree-sitter alone —
all 3 "extra" occurrences are ledger-validated as GitGalaxy-correct (below), so the real
tri-comparison precision (crediting GitGalaxy where the ledger confirms it) is effectively 100%
too; the raw 99.1% is an artifact of tree-sitter's own narrower reading, not a GitGalaxy gap.
These numbers are **unchanged** by the 2026-08-30 ctags fix below — that fix corrected how this
repo's own tooling *reads* ctags' output, not GitGalaxy's extraction, so it's invisible to a
2-tool (GitGalaxy vs. tree-sitter) audit; it only ever showed up in the 3-way ledger.

### Confirmed engine defect (1, fixed)

**Unbounded single-quote pairing swallowed two real proc headers**
(shapes `agree[ctags,tree_sitter]_vs[gitgalaxy]`, `agree[tree_sitter]_vs[ctags,gitgalaxy]`,
`agree[tree_sitter]_vs[gitgalaxy]` — 3 ledger keys, all the *same* 2 real occurrences, drift
between stale/live-rerun snapshots of the same underlying comparison; [#2242](https://github.com/squid-protocol/gitgalaxy/issues/2242)).
Root-caused by driving GitGalaxy's own pipeline directly (`Prism.split_streams` →
`StructuralExtractor._build_brace_safe_stream`) rather than guessing from symptoms: `drop_all_tables`
(`sqlite/tester.tcl:2254`) and `drop_all_indexes` (`:2279`) were completely absent from the
`safe_code` text `func_start` actually matches against, though present in the raw code stream.
`detector.py`'s generic (non-language-specialized) quote-shielding branch — used for tcl since it
had no dedicated branch — included an unbounded single-quote pairing regex (`'(?:\\.|[^'\\])*'`)
with no length cap and no per-language gate, the identical bug class already fixed for
rust/zig/scala/perl. Tcl has **no single-quote string syntax at the language level at all**, so
this shielding was actively harmful, not just imprecise: `sqlite/tester.tcl:2234`'s
`string map {' ''} $contents` (a normal SQL-single-quote-doubling idiom, 3 literal `'` characters
in a 7-char span) desyncs the naive pairing — two of the three get consumed as one `'string,'`
leaving the third to pair with an unrelated `'` inside `drop_all_tables`' own embedded SQL
(`WHERE type IN('`), blanking lines ~2235–2281 as if they were string content, including both
proc headers. Fixed in [#2266](https://github.com/squid-protocol/gitgalaxy/pull/2266) by gating
tcl out of the single-quote pairing entirely, following the same perl/powershell convention. An
earlier fix attempt ([#2218](https://github.com/squid-protocol/gitgalaxy/issues/2218)/[#2224](https://github.com/squid-protocol/gitgalaxy/pull/2224))
had already corrected the ledger's *direction* (crediting ctags/tree-sitter, debiting GitGalaxy)
but misdiagnosed the mechanism as "func_start misses nested braces in args" — #2242's
investigation corrected the root cause without changing the verdict's outcome.

### Confirmed tri-comparison-tooling defect (1, fixed, not a GitGalaxy issue)

**ctags' namespace-qualified proc names were read as bare names**
(shape `agree[ctags]_vs[gitgalaxy,tree_sitter]`, 93 occurrences, all in
`macports_port_api/*.tcl`; fixed 2026-08-30, no separate GitHub issue — found and fixed in the
same tri-comparison-ledger-sweep pass). Every occurrence is a namespace-qualified proc
(`proc portfetch::percent_encode {str} {` in `fetch_common.tcl`). GitGalaxy's `func_start` and
tree-sitter-tcl both read the qualified identifier straight out of the source text
(`portfetch::percent_encode`), matching each other exactly on all 93 — ctags instead splits it
into a bare `name:percent_encode` tag plus a separate `scope:portfetch`/`scopeKind:namespace`
extension field (confirmed directly via `ctags --output-format=json --fields=+znS`), and this
repo's `tests/tools/ctags_reader.py` was dropping that scope field on the floor for tcl
specifically — a pure naming-convention mismatch, not a real disagreement about whether these
procs exist. Fixed by adding `"tcl"` to `ctags_reader.py`'s `_QUALIFY_NAME_WITH_SCOPE`, reusing
the identical scope-joining + verbatim-source-line-guard mechanism already proven for C++'s
`Class::method` out-of-class-definition convention — Tcl's `namespace` scope kind and `::`
separator are both already covered by that generic machinery, so no new parsing logic was
needed, only the language gate. Verified: 0 ctags-only misses remain for tcl functions
corpus-wide (was 93); C++'s own qualification behavior (the only other consumer of this
mechanism) is confirmed byte-for-byte unchanged on all 4 of its own existence discrepancy shapes.

### Where the other tools have real, documented gaps

- **Universal Ctags misses namespace-nested / brace-shape edge cases GitGalaxy and tree-sitter
  agree on** (shape `agree[gitgalaxy,tree_sitter]_vs[ctags]`, 16 occurrences; "GitGalaxy correctly
  extracts proc" — validated by direct sweep 2026-08-24). No credit/debit applied.
- **tree-sitter-tcl misses procs Ctags and GitGalaxy agree on** (shape
  `agree[ctags,gitgalaxy]_vs[tree_sitter]`, 13 occurrences; same verdict shape, direct sweep
  2026-08-24). No credit/debit applied.
- **GitGalaxy alone finds real procs neither comparison tool records**, ledger-validated as
  GitGalaxy-correct, for at least two different reasons:
  - `faultsim_test_result` (`sqlite/malloc_common.tcl:348`) — `proc faultsim_test_result {args}
    "uplevel faultsim_test_result_int $args ..."`, where the proc body is a **double-quoted
    string**, not a brace-delimited block. Tcl genuinely allows this (the quoted body undergoes
    variable substitution differently than a braced one) — both ctags and tree-sitter-tcl's
    grammars expect a brace body and miss it entirely. Shapes `agree[gitgalaxy]_vs
    [ctags,tree_sitter]` and `agree[gitgalaxy]_vs[tree_sitter]`, credited to GitGalaxy.
  - `_check_registry` (`macports_registry/portimage.tcl:259`) — a perfectly ordinary brace-body
    proc with a default-value parameter; ctags misses it specifically, tree-sitter finds it fine
    (this pairing is why it lands in `agree[gitgalaxy]_vs[ctags,tree_sitter]`, not the larger
    ctags-only shape). Investigated further while writing this doc, beyond what the existing
    ledger verdict's terse "correctly extracts proc" covered: a raw `ctags -x
    --language-force=Tcl` on the same file also misses `deactivate_composite`/`deactivate`
    (lines 153/162) — real procs with declaration heads structurally IDENTICAL to the
    successfully-tagged `activate_composite`/`activate` pair just above them — while everything
    from `_activate_files` (line 331) onward tags correctly again. The three misses form one
    contiguous block starting right after `activate`'s own body (lines 79–152) contains
    `"Image error: Can't find image file $location"` (line 119, one bare apostrophe inside a
    double-quoted string) and ending once a second `'$v'`-shaped pair (two more apostrophes,
    line 159, inside `deactivate`'s body) appears — the exact odd/even single-quote-parity
    desync shape already confirmed for **GitGalaxy's own** pre-#2242 bug, this time apparently
    inside ctags' own Tcl parser. Consistent with, not independently proven against ctags' own
    source — noted here and in `ctags_reader.py` (below) rather than filed as an issue against a
    third-party tool this repo doesn't maintain.
  - `distcheck_main` (`macports_port_api/portdistcheck.tcl`) and `uninstall`
    (`macports_registry/portuninstall.tcl`) — confirmed via `tree_sitter_accuracy_audit.py`'s
    "extra" sample; real, correctly-declared procs tree-sitter-tcl's own walk doesn't record for
    this corpus (not independently re-investigated to a named mechanism beyond that — noted, not
    filed, since GitGalaxy's own reading is independently confirmed correct against source).

### `credit_tools` / `debit_tools`

- `agree[ctags,tree_sitter]_vs[gitgalaxy]`, `agree[tree_sitter]_vs[ctags,gitgalaxy]`,
  `agree[tree_sitter]_vs[gitgalaxy]` — `debit_tools: ["gitgalaxy"]` (the 3 stale/live-rerun
  shapes for the same #2242 defect); `credit_tools` set to whichever of `ctags`/`tree_sitter`
  each specific shape's `agreeing_tools` names.
- `agree[gitgalaxy]_vs[ctags,tree_sitter]` — `credit_tools: ["gitgalaxy"]`
  (`faultsim_test_result`'s double-quoted-body proc).
- All other shapes (including the newly-cleared `agree[ctags]_vs[gitgalaxy,tree_sitter]`) —
  neither, per the skill's common case: a confirmed tool-side artifact or an architecture
  difference, not a claim that one tool's otherwise-uncorroborated reading was real, or that two
  tools shared a mistake.

### Issues

- [#848](https://github.com/squid-protocol/gitgalaxy/issues/848) / [#614](https://github.com/squid-protocol/gitgalaxy/issues/614) — epic-level extraction/strict hardening, closed.
- [#1512](https://github.com/squid-protocol/gitgalaxy/issues/1512) — **fixed**: `args`
  overcounted a default-value braced pair.
- [#1504](https://github.com/squid-protocol/gitgalaxy/issues/1504) — **fixed**: ground-truth-tool
  (not GitGalaxy) bug in `tree_sitter_accuracy_audit.py`'s own tcl param-count reader.
- [#2218](https://github.com/squid-protocol/gitgalaxy/issues/2218) — **fixed**, later
  re-diagnosed by #2242 (same outcome, corrected mechanism).
- [#2242](https://github.com/squid-protocol/gitgalaxy/issues/2242) — **fixed**: unbounded
  single-quote pairing swallowed real proc headers.
- No open issue for the `.test`-extension scoping question (§5) — flagged as worth a deliberate
  look, not filed, since it's a documented intentional choice rather than a confirmed defect.

### Full record

`docs/self_scan/tri_comparison_ledger.json` (filter to `tcl/`), each entry's `verdict` field,
`docs/self_scan/tri_comparison_points_of_interest.md`'s `## tcl` section, and
`docs/self_scan/tri_comparison_chart.svg`.

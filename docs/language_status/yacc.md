# YACC / Bison / Lex — Structural Signature Coverage

Snapshot generated 2026-08-27 against `main`. Source: `LANGUAGE_DEFINITIONS["yacc"]` in
`gitgalaxy/standards/language_standards.py`, `tests/extraction/languages/test_yacc.py` /
`test_yacc_strict.py`, closed GitHub issues, and the tri-comparison ledger. Re-run the
`language-status` skill's data-gathering commands before trusting the §1–8 numbers if this doc
looks old relative to `last_updated` below.

**Scope note:** YACC has no tree-sitter grammar available to this repo's comparison tooling (one
of 9 "tree-sitter-blind" languages), so §9 below is a 2-way GitGalaxy/ctags comparison rather
than the usual 3-way shape. §9 was written by the `tri-comparison-ledger-sweep` skill and is the
part of this doc with the most recent, most detailed investigation behind it.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | GNU Bison / Yacc / Flex |
| `_meta.blueprint_version` | v5.1 |
| `_meta.last_updated` | 2026-03-11 |
| `lexical_family` | `standard_block` |
| Structural signature keys wired | 31 / 47 (16 explicit `None`, incl. `class_start` — a grammar file has no object/type concept) |
| Function-slicing integration mode | **Mode A (label-greedy)** since 2026-08-27 (was Mode B / brace-based — see §9) |
| Extraction-gauntlet + strict test files | `test_yacc.py`, `test_yacc_strict.py` (68 passing, 1 skipped) |

## 2. Identification surface

- **Extensions:** `.y .yy .ypp` (yacc/bison grammars, incl. C++ output variants) and
  `.l .ll .lpp` (lex/flex scanners — they share the yacc rule set: `%{ %}` prologue, `%%`
  section markers, `name:` / `name` rule heads, C action blocks).
- **Exact filenames / shebangs:** none — grammar files are always invoked through a build system.
- **Discriminators:** `.c`, `.cpp`, `.h`, `Makefile`, `CMakeLists.txt`, `configure.ac` — a `.y`/
  `.l` file almost always sits next to the C/C++ project it generates a parser for.

## 3. What GitGalaxy detects

`func_start` targets the **grammar-rule definition** (`Name:` at line start, optionally with
whitespace/comments before the `:`) — the closest function-analog the cross-language schema has
for a grammar language, the same design decision behind `makefile` targets and `assembly` labels.
`args` counts `$1`/`$2`/`$$` positional value references inside a rule's action as a per-rule
argument-count proxy (the same spirit as the documented bash/Perl `$1`/`$2` precedent in
`docs/why_gitgalaxy_beats_ast_here.md`). `class_start` is `None`. The remaining 29 wired keys
(branch, io, safety, memory_alloc, macros, pointers, …) run against the embedded C/C++ action and
prologue/epilogue code.

## 4. What GitGalaxy explicitly does not track

`class_start` and 15 other keys are wired to `None`: `test`, `concurrency`, `ui_framework`,
`closures`, `decorators`, `comprehensions`, `scientific`, `ssr_boundaries`, `events`,
`dependency_injection`, `inline_asm`, `thread_sleeps`, `sync_locks`, `listeners`, `test_skip` —
none have a meaningful analog in a grammar-definition file.

## 5. Known limitations (accepted, not fixed)

- **Last rule per file over-measures its body.** Mode A slices each rule's body greedily to the
  next rule head; the final rule in a file therefore absorbs the trailing `%%` C epilogue as its
  "body" (inflated LOC/complexity on that one function). Existence and precision are unaffected.
  Identical to how every other Mode A language behaves at end-of-segment.
- **The embedded C/C++ epilogue's own functions are not separately extracted** as C functions —
  the whole file is scanned as yacc. A grammar file's C epilogue is usually small helper code;
  not currently considered worth mid-file language switching.
- **`c/sqlite/parse.y`** (a *lemon* grammar, not yacc/bison — rules are `lhs ::= rhs.`) is
  currently excluded from `file_data` by an unrelated corpus-routing gate, so it does not appear
  in any comparison. Noted as an incidental finding during the 2026-08-27 sweep; not yet filed.

## 6. Test depth

`tests/extraction/languages/test_yacc.py` (extraction gauntlet) and `test_yacc_strict.py` (ReDoS /
boundary correctness, scaling-ratio methodology). 68 passing, 1 skipped as of this snapshot.

## 7. Relevant closed work

- [#616](https://github.com/squid-protocol/gitgalaxy/issues/616) — strict-parsing tests for yacc
  structural signatures.
- [#846](https://github.com/squid-protocol/gitgalaxy/issues/846) — extraction hardening for yacc.
- [#713](https://github.com/squid-protocol/gitgalaxy/issues/713) — `spec_exposure` unbounded-`[^\]]*`
  ReDoS fix, applied across 28 languages including yacc.
- [#1926](https://github.com/squid-protocol/gitgalaxy/issues/1926) — both real `.y` corpus files
  were silently excluded from `file_data` by `statistical_auditor.py`; fixing it is what first
  made yacc visible to the tri-comparison tool at all (the §9 ledger shape was `first_seen` the
  same day).

## 8. Real-world evidence

The comparison corpus is small (`language-crucible/data/yacc/freebsd/` — FreeBSD's `config.y` and
`jailparse.y`), plus `.y`/`.l` files that live inside other language corpora
(`cobol/gnucobol_internals/parser.y` + `scanner.l`, an 18k-line real Bison grammar).

## 9. Tri-comparison: GitGalaxy vs. ctags (no privileged ground truth)

**Summary.** The one discrepancy shape the tri-comparison tool ever flagged for yacc
(`yacc/function/existence/agree[gitgalaxy]_vs[ctags]`, 18 occurrences, first seen 2026-08-27) was
investigated and validated the same day via the `tri-comparison-ledger-sweep` skill. GitGalaxy was
correct on all 18. The shape had **two independent causes, both fixed in the same pass**, plus a
third finding logged as a `why_gitgalaxy_beats_ast_here.md` claim. After the fixes GitGalaxy and
ctags agree exactly on all 27 grammar rules across the gather corpus (`config.y` 20/20,
`jailparse.y` 7/7) — the chart cell moved from `18*` / `0*` (GitGalaxy alone, unvalidated) to a
verified `27` / `27` tie.

### Cause 1 — test-harness kind-map bug (audit tool)

`tests/tools/ctags_reader.py` mapped `CTAGS_FUNC_KINDS["yacc"]` to `set()`, with a comment
asserting ctags "structurally cannot see" grammar rules. That was wrong: `ctags
--list-kinds-full=YACC` shows `l` (label) is the parser's only kind, and it tags **every** rule
LHS with it (`Spec  label  line:126`). The empty set dropped ctags' own correct reading before
reconciliation, making GitGalaxy look alone on 18 occurrences it was in fact right about. Mapped
`{"l"}` — same function-analog precedent as `makefile` `t` and `assembly` `l`, and the same
kind-map gap shape as the already-fixed cpp `g` / kotlin `o` / fortran `m,i,S,b` entries. Filed as
[#2352](https://github.com/squid-protocol/gitgalaxy/issues/2352).

### Cause 2 — real engine defect: action-less rules dropped from the named list

YACC had no `ScopeParsingRegistry` entry and `lexical_family="standard_block"`, so
`gitgalaxy/core/detector.py` routed it to `Mode_B_Braces`. A yacc grammar rule only contains a
`{`/`}` pair when one of its productions carries a C semantic action — so every **action-less**
rule (`Configuration:`, `Many_specs:`, `Opt_list:`, `Dev_list:`, …) could not be brace-sliced and
was silently dropped from `function_data`, even though the raw `struct_func_start` signal counted
it. `config.y` raised 20 raw signals but only 11 reached the named list. Same bug class as
[#1899](https://github.com/squid-protocol/gitgalaxy/issues/1899) (abap),
[#1975](https://github.com/squid-protocol/gitgalaxy/issues/1975) (jcl/m4), and the dockerfile
Mode-B fallthrough. Fixed by routing yacc through `Mode_A_Labels` — grammar rules never nest, so
"greedy to the next rule head" is the correct body boundary, exactly like COBOL's label-only
paragraphs. `config.y` → 20/20; `gnucobol_internals/parser.y` → 1148/1148 at 100% precision (up
from 781). Filed as [#2351](https://github.com/squid-protocol/gitgalaxy/issues/2351).

### Where GitGalaxy wins outright (why 1148 > ctags' 823 on `parser.y`)

Confirmed on GnuCOBOL's real 18k-line Bison grammar, and logged as a **second instance of Claim 12**
in `docs/why_gitgalaxy_beats_ast_here.md` (lexical coverage a generic parser's identifier
convention excludes):

- ctags' YACC parser emits **no tag** for any rule whose name starts with `_` — GnuCOBOL's
  pervasive "optional form of a nonterminal" convention: `_program_body:` (line 3398),
  `_options_paragraph:` (3564), `_data_division:` (5803), … **325 rules**, all real, all found by
  GitGalaxy, none tagged by ctags (which tags every plain sibling in the same neighbourhood).
- ctags also drops the single-character rule name `x:` (line 17101) while tagging its neighbours
  `x_list:` / `x_common:`.
- ctags tags `encryption_clause:` (line 5168) even though that whole rule sits inside a
  `/* FXIME: disabled … */` block comment (lines 5167–5179); GitGalaxy's `prism.py` strips the
  comment and correctly does not count it.

Net: 823 ctags tags (0 leading-underscore, 0 single-char, 1 bogus commented-out) vs GitGalaxy's
1148, every one a real grammar rule.

### `credit_tools` / `debit_tools`

None. The shape resolved into genuine agreement once the harness bug was fixed, rather than one
tool's uncorroborated claim standing alone — the common case, per the skill's step 4 guidance.

### Full record

`docs/self_scan/tri_comparison_ledger.json` (filter to `yacc/`), the entry's `verdict` field, and
`docs/self_scan/tri_comparison_chart.svg`.

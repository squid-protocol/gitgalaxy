# Embedded Python (MicroPython / CircuitPython / Bare-Metal)

## 1. At a glance

| Metric | Value |
| :--- | :--- |
| **Status** | production |
| **Target Version** | Embedded Python (MicroPython / CircuitPython / Bare-Metal) |
| **Lexical Family** | line_exclusive |
| **Rules Wired** | 51 / 52 (`dependency_injection` intentionally null) |
| **Extraction tests** | `tests/extraction/languages/test_embedded_python.py` |
| **Strict tests** | `tests/extraction/languages/test_embedded_python_strict.py` |

## 2. Identification surface

- **Extensions**: `.py`, `.mpy`
- **Exact matches**: `boot.py`
- **Discriminators**: `boot.py`, `mip.json`, `upip`
- **Shebangs**: `micropython`, `mpy-cross`
- **Internal discriminator**: a `.py` file is only claimed as `embedded_python` (over plain
  `python`) if it itself imports one of `machine`/`board`/`microcontroller`/`busio`/`digitalio`/
  `analogio`/`usb_hid`/`neopixel`/`rp2`/`esp32`/`pyb`/`wifi`/`socketpool`. This is per-file, not
  per-directory: a pure-logic sibling module in the same embedded-firmware project (a logger, a
  protocol codec, a diagnostics helper) that never itself imports a hardware library gets
  classified as plain `python` instead, even sitting next to files that do. Observed directly in
  the `language-crucible/data/embedded_python/meow_turtle/` reference corpus -- of 14 real `.py`
  files, only 7 self-trigger the discriminator; the other 7 (`diagnostics.py`, `logging.py`,
  `meowprotocol.py`, `mpu6050.py`, `ota.py`, `tester.py`, `tsl2591.py`) route to `python` on their
  own content. This is working as designed (the discriminator's job is disambiguation, not
  directory grouping) and every real function in all 14 files is still extracted correctly --
  just split across two `language` values in per-file output. Noted here rather than treated as a
  defect since it doesn't affect any tri-comparison metric (§9 only measures files GitGalaxy
  itself classifies as `embedded_python`, the same methodology used for every other language).

## 3. What GitGalaxy detects

Same structural-signature surface as plain Python (`func_start`/`args`/`class_start`/branch/
structural_boundaries plus the full Phase 2+ risk/domain sensor set -- safety, io, api,
state_mutation, concurrency, closures, decorators, generics, comprehensions, macros, pointers,
memory_alloc, inline_asm, bitwise_ops, sync_locks, cleanup, encapsulation, serialization_parsing,
regex_execution, time_date_logic, `_dependency_capture`, etc.), plus the identification-layer
additions in §2 that route real-world embedded/microcontroller Python to this language definition
instead of generic `python`.

## 4. What GitGalaxy explicitly does not track

- `dependency_injection`: null -- no embedded/microcontroller-specific DI convention identified
  yet (mirrors plain Python's own scope here).

## 5. Known limitations (accepted, not fixed)

- The per-file hardware-import discriminator (§2) means a project-wide "this whole codebase is
  embedded firmware" signal doesn't exist -- classification is always per-file. Accepted as
  correct disambiguation behavior, not a recall gap (see §2 and §9's scope note).

## 6. Test depth

- **Extraction-gauntlet tests**: 21 cases in `tests/extraction/languages/test_embedded_python.py`
- **Strict-signature tests**: 18 cases in `tests/extraction/languages/test_embedded_python_strict.py`

## 7. Relevant closed work

- [#839](https://github.com/squid-protocol/gitgalaxy/issues/839): Extraction hardening:
  embedded_python
- [#580](https://github.com/squid-protocol/gitgalaxy/issues/580): Strict parsing tests:
  `embedded_python` structural signatures
- Cross-cutting fixes that also touched embedded_python's shared code paths: #1199 (args capture
  group), #1209 (25-language args regression), #1193/#1954 (`line_exclusive` family comment
  stripping), #713 (spec_exposure ReDoS).

## 8. Real-world evidence

No `gitgalaxy-raw-output` assessment project for embedded_python yet -- the primary real-world
evidence is the `language-crucible/data/embedded_python/meow_turtle/` reference corpus (a 14-file,
~4,500-line MicroPython/RP2-class firmware project: actuators, sensors, BLDC/vibration motor
drivers, OTA update flow, boot/rollback sequencing, and application logic) used directly by §9's
tri-comparison measurement below.

## 9. Tri-comparison: GitGalaxy vs. ctags (no tree-sitter grammar available)

embedded_python has no tree-sitter grammar in `tree_sitter_language_pack` (confirmed: every
`tri_comparison_ledger.json` shape for this language names only `ctags`/`gitgalaxy`, never
`tree_sitter`), so this is a 2-tool comparison, same shape as cobol/fortran/scheme/m4/yacc/sqlite.
Both open discrepancy shapes (2026-08-30 first-seen) were investigated 2026-08-31 by reading real
source and the pipeline's own DB output, not assumed -- full record in
`docs/self_scan/tri_comparison_ledger.json`, filterable to `"language": "embedded_python"`.

**Result: 2 of 2 discrepancy shapes resolved, both confirmed real GitGalaxy engine defects, fixed
and verified in the same pass.**

### Root cause

`embedded_python` is real, indentation-scoped Python (no braces anywhere), but it was registered
as a language definition and never wired into any of the Python-specific special-case branches
that make brace-less parsing actually work:

- `detector.py`'s Mode C (indentation-scoping) function-body-slicing dispatch tuple --
  missing, so every function body fell through to Mode B (brace search), which only "succeeds"
  when a stray `{`/`}` happens to appear nearby (a dict/set literal).
- The class-body `use_indentation_scoping` tuple -- same gap, for class scope.
- `_CLASS_START_NAMED_EXTRACTION_LANGS` -- missing, so the named class list had no allowlist
  entry (though in practice the generic fallback regex already covered plain `class Name:`
  syntax, so this had no measurable effect here; added anyway for consistency with the
  cobol/dockerfile precedent).
- The docstring-harvest-below-signature tuple and the single-line-function-body bypass tuple --
  same "never added" gap.
- `prism.py`'s docstring-stripping and carry-aware-quote-tracking gates referenced a stale
  `"micropython"` identifier that is not a registered language id anywhere in
  `LANGUAGE_DEFINITIONS` (the real id is `embedded_python`) -- a leftover from an apparent
  pre-rename codename, so these gates silently never fired for the real language.

Confirmed via direct evidence, not inference: the raw `func_start` regex, run standalone against
the 7 files GitGalaxy classifies as `embedded_python`, matched 82/82 real functions (matching
ctags' own 82 exactly) -- but the live pipeline's `function_data` named list only reached 13
before the fix (`sensors.py` alone: 17 raw matches, only 4 reached the named list; `bldc_driver.py`/
`pio_programs.py`/`vibration_driver.py`: 100% dropped, 0 of 5/2/5). All six gaps were fixed by
adding `embedded_python` alongside `python` to each tuple/allowlist -- the exact same fix shape
already proven for abap/dockerfile/jcl/m4/yacc/haskell in this same detector.py dispatcher.

### Verification chain

1. Standalone regex re-test: 82/82 real matches, unaffected by the fix (the regex was never the
   problem).
2. `tests/extraction/languages/test_embedded_python.py` + `test_embedded_python_strict.py`: 342
   cases pass (run alongside `test_python.py`/`test_python_strict.py` as a regression check on the
   shared tuples).
3. `python tests/ruff_audit.py --ci` / `python tests/mypy_audit.py --ci`: no new findings.
4. `python tests/tools/crucible_check.py` against the full ~80-repo corpus: 53 mismatches, every
   one traced to embedded_python's own corrected function/LOC/composition counts or expected
   downstream ripple (repo-wide aggregate averages, 3D topological repositioning of unrelated
   files as overall corpus composition shifts slightly) -- zero regressions in any other
   language's function/class counts.
5. Both golden master fixtures (`tests/golden_master_audit.json`,
   `tests/golden_master_zero_dep_audit.json`) re-blessed via `update_golden_master.py --yes`; every
   mismatch line read and confirmed to trace to the same root cause (e.g. `sensors.py`'s Function
   Analysis going from 4 mis-sliced functions to the real 17; `boot.py` from 1 to 23).

### Recall audit (2026-08-31, skill step 2.6)

Every function ctags reports that GitGalaxy does not, across the whole corpus, individually
enumerated via `tests/tools/recall_audit.py embedded_python`: **zero**, after the fix (was 64
before it -- the existence shape's full scope, one more than the ledger's stale 69-count snapshot
by direct re-measurement). No tree-sitter grammar exists for this language, so the tree-sitter
column is trivially empty, not a gap.

### Current measured numbers

`tests/tools/tri_comparison_chart.py --languages embedded_python`, `language-crucible/data/
embedded_python/` (the meow_turtle corpus):

| Signal | GitGalaxy | ctags | Read as |
|---|---|---|---|
| Functions found (of 82 total claimed by either tool) | 82 | 82 | full agreement, zero misses either direction |
| Function precision (of what each tool claimed, how much corroborates) | **100%** (82/82) | **100%** (82/82) | genuine tie -- both tools independently found the exact same 82 real functions |
| Classes found / precision | **100%** (11/11) | **100%** (11/11) | same shape as functions |
| Args exact-match | **100%** (all matched occurrences) | **100%** | zero mismatches at the per-occurrence (name+line-rank paired) level across the whole corpus |

No `credit_tools`/`debit_tools` adjustment applied to either ledger entry -- this isn't a case of
an uncorroborated-but-secretly-right claim, just a genuine engine defect that's now fixed, so a
fresh gather naturally shows full agreement. The rate/count tie between GitGalaxy and ctags is a
real one (identical rate *and* identical absolute count, not a small-sample artifact), not
something CLAUDE.md's tie-break rule needs to resolve further.

### Scope note

This 2-shape sweep only covers what GitGalaxy-vs-ctags disagreement actually surfaced. It does not
independently re-verify every already-agreeing occurrence from first principles (the recall audit
in §2.6 covers that specifically for existence; args/class exactness above is covered by the
full-corpus per-occurrence diff in the same pass).

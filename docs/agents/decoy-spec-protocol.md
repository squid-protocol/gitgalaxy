# SOP-002: Specification-Grade Per-Language Decoy Testing Protocol (#8863)

**Protocol ID:** `SOP-002`  
**Current Version:** `SOP-002-v1`  
**Skill:** `.claude/skills/family-decoy-spec/SKILL.md`  
**Predecessor (Tier 1):** `SOP-001` (`docs/agents/decoy-testing-protocol.md`, `.claude/skills/family-decoy-rigor/SKILL.md`)  
**Runner:** `tests/tools/family_decoy_runner.py`  
**Baseline:** `tests/family_validity_baseline.json`  
**Per-Language Spec Suites:** `tests/decoys/test_decoy_<lang>.py`

---

## 1. Two-Tier Model: SOP-001 vs SOP-002

| Tier | Protocol | Scope per PR | Purpose | Baseline Tag |
|---|---|---|---|---|
| **Tier 1** | `SOP-001-v1` | Whole fleet / many languages | Fast automated 6-gate sweep (1 trigger per cell) to eliminate systemic blindness and catch obvious comment/boundary leaks | `"protocol": "SOP-001-v1"` |
| **Tier 2** | `SOP-002-v1` | **1–3 languages per PR** | Hand-verified, specification-grade decoy suite covering every alternation branch, every spec comment form (incl. nesting), all structured rules, and cross-family negative controls | `"protocol": "SOP-002-v1"` |

A language graduates from `SOP-001-v1` to `SOP-002-v1` only when every gate below is verified against that language's actual specification and locked in `tests/decoys/test_decoy_<lang>.py`.

---

## 2. The SOP-002-v1 Spec-Grade Requirements

All checks MUST run through the **real GitGalaxy pipeline** (`Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS).split_streams()` + `StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice()`).

### Requirement A — Complete Specification Comment Matrix (All Forms)
Read the language's actual specification (and `gitgalaxy/standards/language_standards/languages/<lang>.py`) and test **every** comment form the language defines, not just one line comment and one block comment:
- All line comment forms (e.g. Fortran `!` free-form AND column-1 `C`/`*` fixed-form; COBOL column-7 `*` AND COBOL-2002 inline `*>`; Batch `REM` AND `::`; HCL `#` AND `//`; REXX `/* */` AND `--`; ABAP column-1 `*` AND inline `"`).
- All block / documentation comment forms (e.g. Perl `=pod ... =cut`; Ruby `=begin ... =end`; Julia `#= ... =#`; Nim `#[ ... ]#`; MATLAB `%{ ... %}`; Haskell `{- ... -}`; Scheme `#| ... |#`; Lua `--[[ ... ]]`; PowerShell `<# ... #>`; OCaml/F# `(* ... *)`).
- **Nested block comments** whenever the language specification allows nesting (Rust, Swift, Kotlin, Haskell, OCaml, F#, Nim, Julia, Zig N/A): test `/* outer /* inner */ <kw> */` (or the language's equivalent) to verify `Prism` does not close the comment early on the first closer and leak `<kw>`.
- **Inline trailing comments** and **string-to-comment boundaries** (including escaped quotes and comment-like URLs inside strings: `"http://x" // <kw>`, `"a \" b" // <kw>`).

### Requirement B — All-Branch Word-Boundary Audit (Exhaustive G5)
SOP-001 tests only the first matching keyword of a family regex. Under SOP-002, audit **every literal alternation branch** in every defined code-stream rule for `<lang>`:
- **Bare word branches (`kw`)**: embed inside a valid identifier (`my_<kw>_val` / `MY_<KW>_VAL`) -> must produce **0** hits.
- **Call-shaped branches (`fn(`)**: embed with a leading identifier prefix (`my_<fn>(x)`) -> must produce **0** hits.
- **Dotted / qualified branches (`Mod.fn` / `obj.method(`)**: embed with a leading prefix (`MyMod.fn` / `obj.my_method(`) -> must produce **0** hits.

Every branch that leaks is a real precision bug in the rule regex — record it and file a GitHub issue (do not skip the branch to make the suite pass).

### Requirement C — Zero Untested Code-Stream Families (Structured G1 Coverage)
For every defined code-stream family in `<lang>` that SOP-001's automated scraper missed (multi-token, line-anchored, or structured syntax such as HTML `<script>`, HCL `resource "a" "b" {}`, JCL `//STEP1 EXEC ...`, Erlang `mod:fn(x)`, Dockerfile `RUN ...`, multi-line SQL/COBOL), write an authentic, minimal positive-control snippet in `tests/decoys/test_decoy_<lang>.py` and verify G1–G6 through the real pipeline.
- Target: **0 untested code-stream families** for `<lang>` (if a rule is genuinely unreachable or dead, file an issue rather than silently skipping it).

### Requirement D — Cross-Family Negative Controls (Precision Without a Parser)
Using `gitgalaxy/standards/signal_contracts.py` and `docs/agents/family-validity-checklist.md` rulings, write language-authentic **negative controls** in `tests/decoys/test_decoy_<lang>.py` for the highest-risk over-counting families defined by `<lang>`:
- `branch`: closing keywords (`end if`, `endif`, `fi`, `esac`), exception handlers (`catch`, `except`, `rescue`), `assert`, `return -1`.
- `io`: pure path manipulation (`Path.join`, `filepath.Join`, `os.path.join`), string formatting, process exit.
- `bitwise_ops`: type unions (`int | str`), generic angle brackets (`List<List<int>>`), logical operators (`&&`, `||`), shell pipes (where applicable per contract).
- `closures`: named function/method declarations (not anonymous callables).
- `panics_and_aborts`: `assert`, ordinary error returns (`return -1`), method `.exit()` calls.
- `time_date_logic` vs `thread_sleeps`: sleeps/timers must not fire `time_date_logic`, and clock reads must not fire `thread_sleeps`.
- `telemetry` vs `debug_prints`: bare `print` must not fire `telemetry`, and structured logger calls must not fire `debug_prints`.

### Requirement E — Dedicated Per-Language Pytest Suite + Baseline Promotion
1. Commit `tests/decoys/test_decoy_<lang>.py` with clear docstrings citing `SOP-002-v1` and `#8863`.
2. Known unfixed engine leaks discovered during SOP-002 hardening MUST be marked `@pytest.mark.xfail(strict=True, reason="https://github.com/squid-protocol/gitgalaxy/issues/<N>")` with a filed GitHub issue — never deleted, never silently skipped.
3. Promote `<lang>`'s entries in `tests/family_validity_baseline.json` to `"protocol": "SOP-002-v1"` and regenerate `docs/self_scan/family_validity_chart.svg` and `docs/self_scan/family_validity_matrix.svg`.

---

## 3. Batching & Progress Tracking

Work **1–3 languages per PR** (grouped by shared lexical family or domain, e.g. ML-family `ocaml` + `fsharp`, BEAM `elixir` + `erlang`, SQL `postgresql` + `sqlite` + `db2_sql`, mainframe `hlasm` + `jcl` + `bms`).

Track fleet-wide graduation from `untested` → `SOP-001-v1` → `SOP-002-v1`:
```sh
python tests/tools/family_decoy_runner.py --audit-superficial
```

---

## 4. PR Checklist (Paste into Every SOP-002 PR)

- [ ] Protocol referenced: `SOP-002-v1` (`docs/agents/decoy-spec-protocol.md`)
- [ ] Scope: 1–3 languages (`<langs>`), each audited against its language specification
- [ ] **Req A:** All spec comment forms tested (line, block, alternate markers, nested block comments where spec allows, inline, string-comment boundary)
- [ ] **Req B:** Exhaustive all-branch G5 boundary audit run (bare word + call-prefix `my_<fn>(` + qualified prefix)
- [ ] **Req C:** 0 untested code-stream families remaining for `<langs>` (or dead-rule issue filed)
- [ ] **Req D:** Cross-family negative controls written in `tests/decoys/test_decoy_<lang>.py` against `signal_contracts.py` rulings
- [ ] **Req E:** Every discovered leak has a filed GitHub issue and `xfail(strict=True, reason=...)` in `tests/decoys/test_decoy_<lang>.py`; baseline promoted to `"protocol": "SOP-002-v1"`
- [ ] `python tests/tools/family_validity_chart.py --write` and `--check` pass
- [ ] `pytest tests/decoys/test_decoy_<lang>.py tests/tools/test_family_decoy_runner.py tests/tools/test_family_validity_chart.py` pass
- [ ] `ruff_audit.py --ci`, `mypy_audit.py --ci`, `dead_key_audit.py --ci`, `doc_refs_audit.py --ci` pass with 0 new findings

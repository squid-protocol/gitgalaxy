---
name: family-decoy-spec
description: Graduate 1-3 languages from SOP-001 automated decoys to SOP-002 specification-grade decoy suites (epic #8863) -- testing every comment form in the language spec (including nested block comments and alternate markers), exhaustive all-branch G5 word/call-prefix boundaries, structured positive controls for 0 untested code-stream families, and cross-family negative controls in tests/decoys/test_decoy_<lang>.py. Use when the user asks to "run SOP-002 on <lang>", "harden decoy tests for <lang>", "upgrade <lang> decoys to spec grade", or "do a SOP-002 batch". NOT for fast fleet-wide first-pass sweeps (family-decoy-rigor / SOP-001) or parser-measured red cells (family-validity-fix).
---

# Specification-Grade Per-Language Decoy Hardening (SOP-002)

`SOP-001` (`family-decoy-rigor`) eliminates systemic blindness quickly with 1 automated trigger per cell. **`SOP-002`** (`docs/agents/decoy-spec-protocol.md`) is the deep, progressive hardening pass — **1–3 languages per PR** — that verifies every language against its actual specification and locks the result in `tests/decoys/test_decoy_<lang>.py`. **Read `docs/agents/decoy-spec-protocol.md` first.**

## Workflow (1–3 Languages per PR)

1. **Pick the batch and inspect current SOP status:**
   ```sh
   python tests/tools/family_decoy_runner.py --audit-superficial
   ```
   Choose 1–3 related languages (e.g. `ocaml` + `fsharp`, `elixir` + `erlang`, `postgresql` + `sqlite` + `db2_sql`, `ada` + `fortran`, `hlasm` + `jcl` + `bms`).

2. **Read the language's rules and real specification:**
   - Read `gitgalaxy/standards/language_standards/languages/<lang>.py` completely.
   - List **every** comment form in the language specification: primary line, alternate line (`REM` + `::`, `!` + col-1 `C`/`*`, `*` + `*>`, `#` + `//`), block/doc comments (`=pod =cut`, `(* *)`, `#= =#`, `#[ ]#`, `%{ %}`, `{- -}`, `#| |#`, `--[[ ]]`, `<# #>`), and whether the spec allows **nested block comments**.
   - Read `gitgalaxy/standards/signal_contracts.py` and `docs/agents/family-validity-checklist.md` rulings for any cross-family boundaries.

3. **Run an exhaustive all-branch G5 boundary audit (Requirement B):**
   Inspect every compiled code-stream rule in `<lang>.py` and test **every** literal alternation branch through `Prism.split_streams` + `StructuralExtractor.splice`:
   - bare identifier branch `kw` → `my_<kw>_val` must yield 0 hits
   - call-shaped branch `fn(` → `my_<fn>(x)` must yield 0 hits
   - qualified branch `Mod.fn` → `MyMod.fn` must yield 0 hits

4. **Cover every remaining untested code-stream family (Requirement C):**
   Write minimal, authentic positive controls for every rule SOP-001's scraper missed (HTML tags, HCL blocks, JCL cards, Erlang `mod:fn()`, Dockerfile instructions, multi-line SQL/COBOL) so the language reaches **0 untested code-stream families**.

5. **Write `tests/decoys/test_decoy_<lang>.py` (Requirements A–E):**
   Include parametrized tests through the real `Prism` + `StructuralExtractor` pipeline for:
   - Every spec comment form (including nested block comments where spec allows) + inline + string-comment boundaries
   - All-branch G5 boundary checks
   - Positive controls for all code-stream families (including structured rules)
   - Cross-family negative controls (`end if`/`catch` vs `branch`, `Path.join` vs `io`, type unions/generics vs `bitwise_ops`, `.exit()` vs `panics_and_aborts`, sleep vs time, print vs telemetry)
   - Mark any unfixed real engine leak with `@pytest.mark.xfail(strict=True, reason="https://github.com/squid-protocol/gitgalaxy/issues/<N>")` after filing one GitHub issue per root cause citing `SOP-002` and `#8863`.

6. **Promote baseline entries to `SOP-002-v1` and refresh charts:**
   - Update `<lang>`'s entries in `tests/family_validity_baseline.json` to `"protocol": "SOP-002-v1"` (adding newly covered structured families).
   - Run:
     ```sh
     python tests/tools/family_validity_chart.py --write
     ```

7. **Verify and open one PR per batch:**
   - Run `pytest -q tests/decoys/test_decoy_<lang>.py tests/tools/test_family_decoy_runner.py tests/tools/test_family_validity_chart.py tests/tools/test_language_sheets.py`
   - Run `ruff format`, `ruff_audit.py --ci`, `mypy_audit.py --ci`, `dead_key_audit.py --ci`, `doc_refs_audit.py --ci`
   - Open the PR with the SOP-002 PR checklist from `docs/agents/decoy-spec-protocol.md` filled in, citing `SOP-002-v1` and `#8863`.

## Do not
- bundle more than 3 languages into a single SOP-002 PR (keep each spec review focused and auditable)
- skip an alternation branch or comment form because `Prism` or the rule leaks it — file the issue and lock an `xfail(strict=True)` test
- promote a language to `"protocol": "SOP-002-v1"` without a committed `tests/decoys/test_decoy_<lang>.py`
- mix engine/rule fixes into a SOP-002 measurement PR unless explicitly requested (with full golden-master attribution)

## Report back
- Languages graduated to `SOP-002-v1` and cells promoted (including previously untested structured rules now covered)
- Every spec comment form tested (and whether nested block comments passed or leaked)
- All-branch G5 boundary leaks and cross-family negative-control leaks found, with GitHub issue links
- Verification results and PR link

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

GitGalaxy (the "blAST engine") is an AST-free, LLM-free static analysis engine. It ingests a
repository, extracts **Structural Signatures** via bounded, ReDoS-proof regexes (no compiler
toolchain, no ASTs), and builds a mathematical knowledge graph used for risk scoring, SBOM
generation, dependency mapping, and 3D visualization. CLI entry points: `galaxyscope` / `blast`.

## The repo constellation (read before cross-repo work)

This engine is the hub of several sibling repos — the language-crucible benchmark corpus
(pinned by CI), the keyword-rosetta cross-language control corpus (whose CI checks out THIS
repo's main), gitgalaxy-raw-output (scan evidence), squid-telemetry, and population-analyses —
plus local-only directories (the `gitgalaxy/data/` source pool; the stale `v1`–`v5`/`temp/`/
`threat_hunter/` copies — only `v6` is live). **`docs/ecosystem.md` is the canonical map**: per-
repo purpose, where every skill lives, the cross-repo workflows and their merge order, and the
PR convention — any PR in a cross-repo workflow must carry a "Cross-repo" note naming its
companion PRs, which side merges first, and what re-runs after. Read it before a crucible pin
bump, a rosetta sweep, or any change whose companion lives in another repo, and keep it (not
this file) updated when the constellation changes.

## Commands

```bash
pip install -e ".[yaml]"                      # editable install (yaml extra needed for the full test suite -- see below)
galaxyscope <path-to-repo>                     # run a scan
python -m pytest tests/                        # full suite (golden_crucible tests excluded by default, see pyproject.toml addopts)
python -m pytest tests/core_engine/test_foo.py::test_bar -q   # single test
python -m pytest -m golden_crucible            # opt-in: needs a local language-crucible checkout (LANGUAGE_CRUCIBLE_PATH)
python tests/ruff_audit.py --ci                # baseline-gated lint (see "Baseline-gated audits" below)
python tests/mypy_audit.py --ci                # baseline-gated type check
python tests/dead_key_audit.py --ci            # baseline-gated dead-config-key audit
ruff format .                                  # zero-tolerance formatting (not baseline-gated)
```

## Working autonomously: commits & PRs to main

Creating commits and opening pull requests targeting `main` in this repo are pre-authorized —
don't pause to ask for confirmation before `git commit` or `gh pr create` against `main`. This
does not extend to merging a PR, force-pushing, or any other destructive/irreversible git
operation (`reset --hard`, `--no-verify`, rewriting published history, etc.) — those still need
explicit confirmation each time per the standard git safety protocol. Still follow existing repo
discipline: only commit files relevant to the change at hand (never a broad `git add -A`), verify
`main..HEAD` doesn't carry unrelated in-progress work before committing, and run the relevant
baseline-gated audits / `crucible_check.py` before pushing anything that touches parsing logic.

- `.gitignore` ignores `*.json` repo-wide: a new committed JSON (data, a baseline, generated package
  data) needs a `!path` whitelist line like the existing ones, or `git add -f`. Confirm with
  `git ls-files <path>` before pushing.
- A PR merged into a stacked base branch (not main) never fires its `Closes #N`; stacked PRs run few CI checks until retargeted.
- Text with backticks (PR bodies, commit messages, rulings) goes through a quoted heredoc
  (`<<'EOF'`) or a file, never an unquoted heredoc or a double-quoted `-c` string.
- Third-party code, papers or tools: `docs/research/third-party-material-policy.md` (ideas only, never their code).
- Agent knowledge (lessons, traps, owner policy) lives in the repo, not personal memory:
  `.claude/rules/agent-memory.md`.

## Scratch files & working directory

Throwaway scripts, repro cases, debug output and generated artifacts do **not** belong in the repo tree, not even
temporarily (~130 `scratch*.py`/`pr_*_body.md` files were committed and purged twice, #1091). Use
`/tmp/gitgalaxy-scratch/claude/` (create if missing) or your harness Scratchpad Directory (agy uses
`/tmp/gitgalaxy-scratch/antigravity/`, see `ANTIGRAVITY.md`). If a file must live in-repo temporarily (relative pytest
discovery), prefix it `scratch_` so `.gitignore` catches it, and delete it before ending the task.

## Architecture

Data flows through `gitgalaxy/core/` in a fixed pipeline, each stage handing off to the next
(writeup: `gitgalaxy/core/README.md`):

1. **`aperture.py`** — zero-trust ingestion filter (rejects binaries/huge files pre-I/O).
2. **`guidestar_lens.py`** — parses manifests for an "Intent Lock" baseline.
3. **`prism.py`** — splits source into executable payload vs. comment/doc surface, shielding string literals.
4. **`detector.py`** — applies the per-language regex rules from `gitgalaxy/standards/language_standards.py`
   to count signatures (branch, io, safety_bypasses, ...), including mid-file language switching.
5. **`network_risk_sensor.py`** — import-statement dependency DAG, PageRank for blast radius.
6. **`spatial_mapper.py`** — projects the DAG into 3D coordinates for the WebGPU visualizer.
7. **`state_rehydrator.py`** — incremental-scan cache (SQLite-backed previous-run state).

Downstream of core: `gitgalaxy/metrics/` (risk scoring math, false-positive suppression),
`gitgalaxy/security/` (network-weighted threat scoring, taint tracking, AI/agentic threat
detection), `gitgalaxy/recorders/` (output formatting: SARIF, SBOM, LLM-optimized summaries,
SQLite), `gitgalaxy/standards/` (the per-language rule registry + `gitgalaxy_config.py` global
config), `gitgalaxy/tools/` (standalone DevSecOps/legacy-migration CLIs built on top of core).
Each has its own `README.md`: read it before working deep inside.

The archetype brains (`analysis_lens.GENERAL_FUNCTION_INFERENCE_MODEL`, the file model and
`gitgalaxy/standards/archetype_brains/*.json`) are not golden-neutral at any level: the golden
audit records the function-archetype distribution and the repo composition archetype. Swapping a
brain, or changing `SIGNAL_SCHEMA`, means a golden re-bless with the drift attributed to it.

## Orientation, debugging, signatures (pointers; details are on demand)

- **Before editing a file, even when the task names exact lines**, check its risk standing (brief Sections 7, 8, 11: `python tests/tools/generated_branch.py show docs/gitgalaxy_architecture_brief.md`, published daily to the `generated` branch and not in the checkout, or the self-scan DB) rather than guess how conservative to be. Query recipes, DB regen, and dependency caveats: `docs/agents/self-scan-orientation.md`.
- Signal looks wrong for a file: check the engine's actual extraction first (`galaxyscope <path> --db-only --debug --output <scratch>`, grep `[WORKER-TRACE]`). Details, including the registry-declaration trap (a string value inside a language's `rules` is compiled to a regex; helper keys go at the TOP LEVEL of the definition) and scan non-determinism (`GALAXYSCOPE_MAX_WORKERS=1`): `docs/agents/detector-debugging.md`.
- Adding or hardening a language: read `gitgalaxy/standards/how_to_add_a_language.md` directly (never paraphrase it); use the `harden-language-extraction` skill. Layout of strict/gauntlet tests: `docs/agents/language-signatures.md`.

## Baseline-gated audits (ruff / mypy / dead-key)

These are regression gates, not zero-tolerance floors: each has a committed baseline file
(`tests/ruff_audit_baseline.json` etc.) and `--ci` mode fails only on *new* findings beyond it.
If you fix backlog findings, regenerate the baseline with `--write-baseline`
(`python tests/ruff_audit.py --write-baseline`, same for `mypy_audit.py`). `ruff format
--check` is the one zero-tolerance exception (no backlog to carry).

Use `python tests/tools/audit_check.py` (add `--regenerate`) instead of running the three `--ci`
scripts separately: it bundles all three plus the format check. Baseline keys are content-based
(not line numbers); a new finding or new duplicate of a baselined line still fails. Details:
`docs/agents/baseline-audits.md`.

Don't write module-level optional-import fallbacks (`try: import yaml` / `except ImportError: yaml
= None`): a local mypy with `types-PyYAML` passes, but CI's mypy env (`tests/requirements-mypy.txt`)
has no stubs and fails. Import lazily inside the function.

## Mainframe / COBOL

- Ground-truth ledger (`tests/cobol_mainframe/ground_truth_ledger.json`): `mainframe-ground-truth.yml` runs
  `ground_truth_ledger.py check` on **every** PR and fails on an unlisted mismatch *and* on a listed one that no
  longer reproduces. After a change that moves a score: `mainframe_corpus.py fetch`, then `ground_truth_ledger.py update`;
  new entries are `UNTRIAGED` until you `assign` a cause with an issue; explain the moves in the PR.
- **Every engine or forge defect found on a mainframe estate is logged in
  `tests/cobol_mainframe/field_testing.json`, in the same PR that finds or fixes it** (CI fails on an invalid record or
  stale report; regenerate with `tests/tools/field_testing.py report --write`). Quote coverage only from that report.
- **Every port-side blocker (det port, transaction forge, facade, harness, runtime) goes in
  `tests/cobol_mainframe/port_blockers.json` the same way** (regenerate with `tests/tools/port_blockers.py report --write`;
  `test_port_blockers.py` fails on an invalid ledger or stale page, #5051).
- Porting loop (`porting-loop` skill) and deterministic port (`det-port` skill; after a translator change run
  `det_port.py check --work DIR` and re-prove exactly the ports it lists).
- Full text (tiers, cross-verify, oracle register, #5057 render rule, epic #3445): `docs/agents/mainframe.md`.

## Testing conventions

`tests/` has no `__init__.py` anywhere in this repo. A new test file that needs to import a
sibling helper module (not the `gitgalaxy` package itself, which is always safely importable via
its normal `pip install -e .` editable install) must insert that sibling's directory onto
`sys.path` and import it as a bare top-level module — **never** a dotted `tests.x.y.some_module`
import. That form passes every local `python -m pytest` run (which prepends the CWD to
`sys.path`) but fails in CI with `ModuleNotFoundError: No module named 'tests'`, because CI
invokes the `pytest` console script directly, which doesn't do that prepending. See any file
under `tests/extraction/languages/` for the working pattern. Before pushing a new test file with
this kind of import, verify it by running plain `pytest <file>` (not `python -m pytest`) from an
unrelated working directory — that reproduces CI's actual invocation style locally instead of on
a wasted CI round-trip.

- Never `os.environ.setdefault` / assign scan env vars (e.g. `GITGALAXY_DISABLE_GIT_HISTORY`) at
  import time or process-wide in a module tests import: it leaks across the pytest session (it
  broke `test_chronometer`). Use a save/restore context manager.
- A `tests/tools` script inserts REPO_ROOT on `sys.path` BEFORE any `from gitgalaxy` import
  (`# noqa: E402`); otherwise a shared venv's editable install of another checkout runs silently.
- Python 3.11 is the floor (`requires-python = ">=3.11"`, ruff `target-version = "py311"`, the CI
  matrix). A local 3.12 hides newer syntax (an f-string reusing its quote inside `{}`):
  `ruff check <changed files>` before pushing.
- Evidence-report tests assert only the case under test, never counts from committed reports. Use
  `db2_fixture(..., isolate=True)` (`tests/tools/test_evidence_report.py`) for single-route Db2 tests.

## The Differential Scan (PR protocol for engine/regex changes)

Any PR touching parsing logic (`detector.py`, `language_standards.py`, `prism.py`, etc.) is
verified against `tests/golden_master_audit/` / `tests/golden_master_zero_dep_audit/` by the
`crucible-audit` CI check. A failing diff is either a bug or an intentional improvement needing a re-bless.
**Never hand-edit these fixtures** (they are directories of per-section JSON parts, #3384). Regenerate with
`python tests/tools/crucible_check.py --update --yes` (both fixtures, own venvs, re-runs `pip install -e . --no-deps`);
explain *why* output changed in the PR description. Call `update_golden_master.py` directly only from inside one
mode's venv: from your default shell it silently updates just one fixture (#2547).

- **Never reuse a shared/personal venv across worktrees** (its editable install points at one checkout: false "zero
  diff" locally, real drift in CI, #579/#723). Use `crucible_check.py`.
- `crucible_check.py` output is capped (~28 of N differences shown): scoping a bless needs your own regenerate and
  diff, with `GITGALAXY_DISABLE_GIT_HISTORY=1` (NOT optional, #2985). Recipe: `docs/agents/differential-scan.md`.
- Rebasing a parser/channel PR after a sibling merges: `python tests/tools/rebase_rebless.py` (dry run by default;
  `--execute`, then `--push` = `--force-with-lease`).
- Also run on those paths: `tri-comparison-audit.yml` and `tree-sitter-accuracy-audit.yml` (blocking, baseline-gated).
  Their local runners need the main `.venv` on PATH and refuse to pass on zero languages checked.
- Full protocol, conflict handling (`golden_store.py export`), runner commands: `docs/agents/differential-scan.md`.

## Changing CI to make it faster or cheaper

Read `docs/ci_experiments_log.md` first: what has been tried, measured and dropped (and why), so a dead end is not
re-proposed. The pool of ~20 concurrent runners is the limit, so judge a change by the **slot-minutes** it frees (a
queued job holds no slot), not by how many runner requests it removes. Add an entry, with the measurement and its
sample, in the PR that makes the change.

## Re-running the OS x Python matrix

`full-suite-gate.yml` runs on the `labeled` event only, so commits pushed after labelling never go through the
matrix. After pushing to a labelled PR: `gh workflow run "Full Suite Gate (All OS x Python)" --ref <branch>`
(`-f full_matrix=true` for 12-way). Don't use `synchronize` (#3209). Details: `docs/agents/full-suite-matrix.md`.

## Comparative claims and AST comparison

- **Never treat a raw number comparison as settling which measurement is more correct.** A claim of correctness (badge,
  chart, README, PR text) needs someone reading the real disputed source and recording why; a cell earns a badge only
  when every ledger entry touching it is `status == "validated"` (`tri_comparison_ledger.py`).
- Before running `tri_comparison_chart.py` or editing `tri_comparison_ledger.json` read
  `docs/self_scan/tri_comparison_README.md`; confirm `ctags --version` says "Universal Ctags" (Arduino ctags silently
  degrades to 2-tool, PR #2111); regenerate only with `--all --write`; never hand-set `status`/`verdict`/`still_reproduces`.
- A rate-only tie is broken by absolute count of *validated-correct* occurrences, never unverified counts.
- A specific evidenced case where GitGalaxy beats tree-sitter goes in `docs/why_gitgalaxy_beats_ast_here.md` as a dated
  Claim N (narrow, measured before/after).
- Full text: `docs/agents/claims-and-ast-comparison.md`.

## Issue generation and pipeline/CI triage

Pinned-model subagents keep routine triage off the main context: `.claude/agents/issue-triage.md` (files well-formed
issues from findings) and `.claude/agents/pipeline-manager.md` (CI / Dependabot triage; reports, never merges, closes or
pushes on its own authority). Invoke via the `issue-generation` / `pipeline-check` skills or the Agent tool.

## Model tiering

Sonnet by default; Opus manually for architecture planning; subagents pin models in frontmatter. Details: `docs/agents/model-tiering.md`.

## Licensing

PolyForm Noncommercial 1.0.0: commercial use needs a separate license; contributions use the same terms (`CONTRIBUTING.md`).

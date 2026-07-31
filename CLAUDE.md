# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

GitGalaxy (the "blAST engine") is an AST-free, LLM-free static analysis engine. It ingests a
repository, extracts **Structural Signatures** via bounded, ReDoS-proof regexes (no compiler
toolchain, no ASTs), and builds a mathematical knowledge graph used for risk scoring, SBOM
generation, dependency mapping, and 3D visualization. CLI entry points: `galaxyscope` / `blast`.

## Commands

```bash
pip install -e .                              # editable install
galaxyscope <path-to-repo>                     # run a scan
python -m pytest tests/                        # full suite (golden_crucible tests excluded by default, see pyproject.toml addopts)
python -m pytest tests/core_engine/test_foo.py::test_bar -q   # single test
python -m pytest -m golden_crucible            # opt-in: needs a local language-crucible checkout (LANGUAGE_CRUCIBLE_PATH)
python tests/ruff_audit.py --ci                # baseline-gated lint (see "Baseline-gated audits" below)
python tests/mypy_audit.py --ci                # baseline-gated type check
python tests/dead_key_audit.py --ci            # baseline-gated dead-config-key audit
ruff format .                                  # zero-tolerance formatting (not baseline-gated)
```

## Architecture

Data flows through `gitgalaxy/core/` in a fixed pipeline, each stage handing off to the next
(see `gitgalaxy/core/README.md` for the full writeup):

1. **`aperture.py`** — zero-trust ingestion filter (rejects binaries/huge files before any I/O).
2. **`guidestar_lens.py`** — parses manifests (`package.json`, `Cargo.toml`, etc.) for an
   "Intent Lock" baseline, avoiding expensive heuristic guessing downstream.
3. **`prism.py`** — splits raw source into the executable payload vs. the comment/doc surface,
   shielding string literals so the splitter can't be fooled by delimiter-like text inside them.
4. **`detector.py`** — the structural extractor: applies the per-language regex rules from
   `gitgalaxy/standards/language_standards.py` to count signatures (branch, io, safety_bypasses,
   etc.), including mid-file language switching for polyglot/embedded code.
5. **`network_risk_sensor.py`** — builds the import-statement dependency DAG, runs PageRank for
   blast-radius scoring.
6. **`spatial_mapper.py`** — projects the DAG into 3D coordinates for the WebGPU visualizer.
7. **`state_rehydrator.py`** — incremental-scan cache (skips re-parsing unchanged files via the
   SQLite-backed previous-run state).

Downstream of core: `gitgalaxy/metrics/` (risk scoring math, false-positive suppression),
`gitgalaxy/security/` (network-weighted threat scoring, taint tracking, AI/agentic threat
detection), `gitgalaxy/recorders/` (output formatting: SARIF, SBOM, LLM-optimized summaries,
SQLite), `gitgalaxy/standards/` (the per-language rule registry + `gitgalaxy_config.py` global
config), `gitgalaxy/tools/` (standalone DevSecOps/legacy-migration CLIs built on top of core).
Each of those directories has its own `README.md` — read the relevant one before working deep
inside it rather than re-deriving the architecture from source.

## Adding or hardening a language's structural signatures

Full protocol (LLM generation prompt, the 12 numbered engine rules for ReDoS/boundary
correctness, strict-testing prompt) lives in
`gitgalaxy/standards/how_to_add_a_language.md` — read that file directly rather than expecting
a summary here; it's long because the rules matter and drift if paraphrased. Tests for this
live in `tests/core_engine/test_language_standards_strict.py`, one section per language.

## Baseline-gated audits (ruff / mypy / dead-key)

These are regression gates, not zero-tolerance floors: each has a committed baseline file
(`tests/ruff_audit_baseline.json` etc.) and `--ci` mode fails only on *new* findings beyond it.
This lets CI enforce "no new problems" without demanding the pre-existing backlog be fixed
first. If you fix backlog findings, regenerate the baseline by running the script without
`--ci`. `ruff format --check` is the one zero-tolerance exception (whole repo was reformatted
once at adoption, so there's no backlog to carry).

Use `python tests/tools/audit_check.py` (add `--regenerate`) instead of running the three
`--ci` scripts separately and manually diffing each baseline by eye — it bundles all three plus
the format check, and auto-detects "pure line-shift" findings (same file/code/message, just moved
because an earlier edit in the same file shifted everything below it) from genuine new findings
that need real review, only regenerating the former.

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

## The Differential Scan (PR protocol for engine/regex changes)

Any PR touching parsing logic (`detector.py`, `language_standards.py`, `prism.py`, etc.) is
expected to be verified against `tests/golden_master_audit.json` /
`tests/golden_master_zero_dep_audit.json` — snapshots diffed by the `crucible-audit` CI check
against a ~80-repo corpus plus the PR's target repo. A failing diff means output changed: either
a bug, or an intentional improvement that needs the baseline re-blessed. **Never hand-edit these
fixtures.** Regenerate with `python tests/tools/update_golden_master.py` (shows the diff, asks
for confirmation) and explain *why* in the PR description — CI flags any PR touching these files.

**Verifying locally before pushing:** use `python tests/tools/crucible_check.py` (add `--update`
to regenerate) instead of hand-building venvs. It builds/reuses two venvs at
`.crucible_venvs/{full_precision,zero_dependency}` *inside the current checkout* and — critically
— re-runs a fast `pip install -e . --no-deps` before every check. Skipping that step is a real
footgun: a venv's editable install is a pointer to whatever path was passed to `pip install -e .`
at creation time, and `galaxyscope` is invoked as a subprocess, so reusing a venv across worktrees
(e.g. a long-lived personal dev venv) makes it silently scan a *different* checkout's code — this
produced a false "zero diff" pass locally while CI correctly failed on real output drift (PR
#579/#723, 2026-07-28). Never point `LANGUAGE_CRUCIBLE_PATH`/a shared venv at this without
confirming which checkout its editable install actually resolves to
(`python -c "import gitgalaxy; print(gitgalaxy.__file__)"` from inside that venv).

## Issue generation and pipeline/CI triage

Two subagents with pinned models are set up for this so routine triage doesn't burn main-context
tokens or a premium model: `.claude/agents/issue-triage.md` (filing well-formed GitHub issues
from findings) and `.claude/agents/pipeline-manager.md` (CI status / Dependabot triage — reports
recommendations, never merges/closes/pushes on its own authority). Invoke via the
`issue-generation` and `pipeline-check` skills, or the Agent tool directly.

## Model tiering (token budget)

This repo pins models per-role instead of running everything on one tier, so the expensive
model is only spent where the extra judgment actually pays for itself.

**Main session (manual `/model` switch)**
- **Sonnet (default)**: everyday coding, debugging, code review, regex/rule work.
- **Opus**: switch in manually for architecture-level planning, high-ambiguity design
  decisions, or multi-system tradeoffs (e.g. redesigning the core pipeline stage boundaries,
  not writing one more detector rule) — the extra compute is worth it there.

**Subagents (pinned in each agent's frontmatter)**
- **Haiku**: mechanical, read-heavy, well-defined output shape, no judgment calls beyond
  "escalate if ambiguous" — `issue-triage`, `pipeline-manager`. Both are written to hand
  anything ambiguous (duplicate calls, label taxonomy, destructive actions) back to the main
  conversation rather than guess, which is what makes Haiku safe here.
- **Sonnet**: anything requiring nuanced judgment, synthesis across multiple sources, or
  writing/reviewing code on the subagent's own authority.

When adding a new subagent, default it to Haiku unless the task demonstrably needs more
judgment than "read input, produce well-formed output, escalate ambiguity" — don't pin Sonnet
out of caution alone.

## Licensing

PolyForm Noncommercial 1.0.0 — free for research/education/hobby use; commercial use requires a
separate license. Contributions are licensed under the same terms (see `CONTRIBUTING.md`).

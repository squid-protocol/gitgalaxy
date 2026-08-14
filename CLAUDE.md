# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

GitGalaxy (the "blAST engine") is an AST-free, LLM-free static analysis engine. It ingests a
repository, extracts **Structural Signatures** via bounded, ReDoS-proof regexes (no compiler
toolchain, no ASTs), and builds a mathematical knowledge graph used for risk scoring, SBOM
generation, dependency mapping, and 3D visualization. CLI entry points: `galaxyscope` / `blast`.

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

## Scratch files & working directory

Throwaway scripts, reproduction cases, one-off debug output, and generated test artifacts that
aren't meant to become part of the repo do **not** belong in the repo tree, not even temporarily
— that's how `scratch3.py`, `fix_java_strict.py`, `pr_949_body.md`, and ~130 similar files ended
up committed and had to be purged twice (see #1091). Use `/tmp/gitgalaxy-scratch/claude/` (create
it if missing) instead, or the harness-provided per-session Scratchpad Directory named in your own
system prompt if one is present — either is fine, both are outside the repo and never risk a
`git add`. Antigravity (agy) has the same convention under its own `/tmp/gitgalaxy-scratch/antigravity/`
— see `ANTIGRAVITY.md` — so the two models don't collide in a shared directory.

If a throwaway file genuinely must live inside the repo temporarily (e.g. something that only
works via relative pytest discovery), prefix its name `scratch_` at minimum so `.gitignore`'s
backstop patterns catch it, and delete it before ending the task rather than leaving it for a
future cleanup pass.

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

## Using GitGalaxy's self-scan output for orientation (token efficiency)

GitGalaxy scans its own repo and produces two artifacts specifically to make an LLM coding
session cheaper and safer to run — reach for these *before* an Explore subagent, a broad `grep`,
or reading a large file cold, when the question is really "how big/risky/depended-on is this
thing" rather than "what does this specific code do."

This still applies even when a task already points at exact file/line locations — e.g. a GitHub
issue that quotes the specific lines to change. Knowing *where* to edit isn't the same as knowing
the file's risk standing: check the brief's blast-radius/risk lists (Sections 7, 8, 11) or query
the DB for that file's complexity/fan-in anyway before editing, so "how conservative should this
diff be" is answered from data instead of a guess informed only by the issue text.

- **`docs/gitgalaxy_architecture_brief.md`** — auto-committed on every merge to main (a byproduct
  of the CI scan that also produces SARIF/SBOM), so it's always close to current HEAD. This scan
  always installs `networkx`/`tiktoken`/`xgboost`/`pandas`/`numpy` first (`gitgalaxy.yml`'s
  "Install GitGalaxy & Full Precision Engines" step) — confirm by checking the brief's own
  Section 0 traceability table, which reports `Zero-Dependency Mode: Inactive (Full Precision)`.
  Use it for *repo-wide* framing before a large refactor: Section 7 has the actual blast-radius
  ranking ("Top 5 Structural Pillars" by import fan-in, "Top 5 Orchestrators" by fan-out),
  Section 8 has the heaviest functions repo-wide, Section 11 has the top 10 files by cumulative
  risk. If a file you're about to touch shows up in one of these lists, that's a real signal to
  be more conservative (smaller diffs, more explicit tests) — not a vague guess.
- **`docs/self_scan/gitgalaxy_master.db`** (SQLite, via `tests/tools/self_scan.py`) — targeted,
  near-zero-token ad hoc queries about one specific file/function instead of reading the whole
  file just to count its functions or gauge its complexity. **It's gitignored and NOT committed
  on purpose** (a full rescan is ~6-8s, cheaper than storing history) — it may be missing or
  stale in your checkout. Regenerate with `python tests/tools/self_scan.py` (needs `galaxyscope`
  on PATH, i.e. an activated venv with `pip install -e .`), or pull the latest
  `gitgalaxy-self-scan-db` artifact from the most recent push-triggered "Full Report" run of
  `gitgalaxy.yml` on main if you'd rather not run a local scan.
  - Always confirm column names with `.schema <table>` first rather than trusting any list here
    — the recorder schema evolves. Two concrete, verified examples as of this writing:
    ```bash
    # Heaviest/most complex functions in a file before editing it -- avoids reading the
    # whole file just to find what's risky inside it.
    sqlite3 docs/self_scan/gitgalaxy_master.db \
      "SELECT f.func_name, f.complexity, f.loc, f.calls_out_to
       FROM function_data f JOIN file_data fd ON f.file_id = fd.id
       WHERE fd.file_path LIKE '%detector.py%' ORDER BY f.complexity DESC LIMIT 5;"

    # Which directory groups are heaviest, before deciding where new code belongs
    sqlite3 docs/self_scan/gitgalaxy_master.db \
      "SELECT directory_group, COUNT(*) files, SUM(total_loc) loc, SUM(function_count) funcs
       FROM file_data GROUP BY directory_group ORDER BY loc DESC LIMIT 8;"
    ```
  - **Full-precision dependencies required:** `pagerank_score`, `normalized_blast_radius`, and
    other network/ML-derived columns need `networkx`, `tiktoken`, `numpy`, `pandas`, `xgboost`,
    and `pyyaml` importable in whatever environment runs the scan — without all of them,
    galaxyscope silently drops into Zero-Dependency Mode and those columns come back NULL (this
    is *not* caused by `--db-only` itself, which only selects which recorder writes output; a
    local dev venv missing one of these packages was the actual cause the one time this bit us).
    `self_scan.py` now checks for all six before scanning and aborts loudly if any are missing,
    rather than silently producing a degraded DB — if you hit that, `pip install` whatever it
    lists. CI's copy (the `gitgalaxy-self-scan-db` artifact) always has these installed first, so
    it's always full-precision; only a local run can be affected.
  - It also doesn't parse inside large dict/list literals (e.g. it can't tell you where the
    `"scala"` key starts inside `language_standards.py`'s `LANGUAGE_DEFINITIONS`) — it's for
    orientation and prioritization, not symbol lookup. Read the actual file for that.

## Adding or hardening a language's structural signatures

Full protocol (LLM generation prompt, the 12 numbered engine rules for ReDoS/boundary
correctness, strict-testing prompt) lives in
`gitgalaxy/standards/how_to_add_a_language.md` — read that file directly rather than expecting
a summary here; it's long because the rules matter and drift if paraphrased. Tests for this
live in `tests/extraction/languages/test_<lang>_strict.py`, one file per language, colocated
alongside that directory's own extraction-gauntlet `test_<lang>.py` files (the `_strict` suffix
avoids a basename collision between the two, since this repo has no `tests/__init__.py`
anywhere). They share a `_strict_harness.py` ReDoS-testing helper module the same way the
extraction gauntlets share `_extraction_harness.py` — two independent per-concern harnesses, not
one shared module. `tests/core_engine/test_language_standards_strict.py` now holds only the
handful of genuinely cross-language/global tests (registry-wide sanity checks, the harness's own
self-tests).

**Hardening the four extraction gauntlets** (func_start/args/class_start/_dependency_capture
test depth per language) is a related but distinct exercise, driven by
`tests/extraction/how_to_harden_extraction.md` — the companion doc epic #813 (closed) used to
take all 44 in-scope languages through a documented valid/invalid/pathological methodology, a
43-entry (and growing) recurring-bug-class list, and a strict verification chain
(`tests/extraction/tools/verify_candidates.py` → `audit_check.py` → `crucible_check.py`). Per-
language cases now live in `tests/extraction/languages/test_<lang>.py`, not the four old
monolithic dict files. Use the `harden-language-extraction` skill to pick this up for a new
language or a follow-on bug sweep rather than re-deriving the process from scratch.

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

## Logging cases where GitGalaxy beats tree-sitter/AST ground truth

The general rule, stated plainly in `README.md`'s "One Graph, Not Five Separate Tools" section, is
that tree-sitter/AST parsing is *more precise per file* than GitGalaxy's regex-based structural
signatures — that's the trade GitGalaxy makes for one comparable signal set across every language
without a per-language toolchain. It doesn't hold universally, though: any time work in this repo
turns up a specific, evidenced case where GitGalaxy's output is *more* accurate than tree-sitter's
own parse (not just "different" — genuinely more correct, with a concrete before/after), log it as
its own dated Claim N in `docs/why_gitgalaxy_beats_ast_here.md` rather than leaving it as a PR
description or code comment only. Two examples already there: `args` counting in languages with no
formal parameter-list syntax at all (bash/traditional Perl, #1518/#1519), and function recall
inside dialect/extension syntax a base grammar has no concept of (Cython's `cdef class` inside
plain tree-sitter-python, #1526). Keep each claim narrow and evidence-backed (a measured
before/after, not "heuristics are sometimes better") — this doc's whole value is that it doesn't
overstate the exception into "GitGalaxy is more accurate than tree-sitter" in general, which isn't
true.

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

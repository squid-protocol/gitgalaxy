# ANTIGRAVITY.md

This file provides guidance to Antigravity when working with code in the GitGalaxy repository. It is modeled after the `CLAUDE.md` to ensure seamless CI passes and token-efficient workflows.

## 1. What this is (The Pipeline)

GitGalaxy (the "blAST engine") is an AST-free, LLM-free static analysis engine. It ingests a repository, extracts Structural Signatures via bounded regexes, and builds a mathematical knowledge graph.
Data flows through `gitgalaxy/core/` in this pipeline:
1. **`aperture.py`** — Zero-trust ingestion filter.
2. **`guidestar_lens.py`** — Parses manifests (e.g. package.json) for intent lock baseline.
3. **`prism.py`** — Splits raw source into executable payload vs. comment/doc surface.
4. **`detector.py`** — Structural extractor (applies regex rules to count signatures).
5. **`network_risk_sensor.py`** — Builds dependency DAG and runs PageRank for blast-radius scoring.
6. **`spatial_mapper.py`** — Projects DAG into 3D coordinates.
7. **`state_rehydrator.py`** — Incremental-scan cache.

## 2. CI & Baseline Audits

- **Baseline-Gated Lint/Typing:** ruff, mypy, and dead-key audits are regression-gated using checked-in baselines.
- **Workflow:** **Never** run the individual `--ci` scripts and diff by eye. Instead, use:
  ```bash
  python tests/tools/audit_check.py --regenerate
  ```
  This command bundles format checking, auto-detects line-shifts, and regenerates baselines only when genuinely required.

## 3. The Language Crucible & Golden Master Differential Scans

Any PR touching parsing logic (`detector.py`, `prism.py`, etc.) is checked against the **Language Crucible** (a separate repo of hostile code structures) to guard against regex regressions.
- GitGalaxy pins the crucible corpus and runs differential scans against `tests/golden_master_audit.json` and `tests/golden_master_zero_dep_audit.json`.
- **CRITICAL:** **Never hand-edit these fixtures.** If output intentionally changes, update them.
- **Local Verification before Push:** Run:
  ```bash
  python tests/tools/crucible_check.py --update
  ```
- **Footgun Warning:** `crucible_check.py` handles the local venvs correctly. Do not hand-build venvs and assume `LANGUAGE_CRUCIBLE_PATH` works, as reusing a venv across worktrees causes the editable install (`pip install -e .`) to point to the wrong checkout, producing false positives. 

## 4. Testing Conventions

- There are no `__init__.py` files in `tests/`. 
- **Rule:** Never use dotted imports for test sibling modules (e.g., `tests.x.y.some_module`). Instead, append the sibling's directory to `sys.path` and import the top-level module.
- **Verification:** To reproduce the CI environment locally, run `pytest <file>` directly from an unrelated working directory instead of `python -m pytest <file>` to ensure imports don't accidentally resolve via CWD prepending.

## 5. Working Token Efficiently

As Antigravity, adhere to these practices to manage context and tokens efficiently:
- **Subagent Tiering:** Use `invoke_subagent` for targeted tasks.
  - Default to `inherit` unless asked otherwise, or use `flash` / `flash_lite` for simple, read-heavy, or repetitive lookups (like triage and CI checking).
  - Use `pro` strictly for high-complexity architecture design or deep multi-step planning.
- **No Polling:** Never poll subagents or background tasks. Stop calling tools and let the system wake you up reactively.
- **Transcript Utilization:** Instead of cluttering your context with long command outputs or past agent logs, search your `transcript.jsonl` using efficient `grep` shell commands to recall past steps.
- **Precision Tooling:** Prefer specific API tools (`view_file`, `grep_search`, `list_dir`) over arbitrary bash commands (`cat`, `grep`, `ls`) to avoid unnecessarily large outputs and context bloat.

## 6. Leveraging Self-Scan Telemetry for Intelligent Changes

GitGalaxy scans itself and outputs intelligence to `/docs/gitgalaxy_architecture_brief.md` and `/docs/self_scan/gitgalaxy_master.db`. Before making architectural changes or deep refactors, consume this data token-efficiently:

- **The Architecture Brief (`docs/gitgalaxy_architecture_brief.md`):** Use this to identify structural pillars, I/O latency bottlenecks, and heavy impact functions.
  - E.g., `gitgalaxy/galaxyscope.py` and `gitgalaxy/standards/language_standards.py` are highly coupled orchestrators. Modifying them carries a huge blast radius. 
- **The SQLite Database (`docs/self_scan/gitgalaxy_master.db`):** Instead of reading an entire heavy file to figure out dependencies or function bounds, run targeted SQL queries.
  - *Example:* Find complexity and out-bound calls before touching a function: 
    ```bash
    sqlite3 docs/self_scan/gitgalaxy_master.db "SELECT complexity, calls_out_to FROM function_data WHERE func_name = 'execute_pipeline';"
    ```
  - *Example:* Check a file's risk exposure before adding features (e.g. `risk_cognitive_load`, `risk_state_flux`):
    ```bash
    sqlite3 docs/self_scan/gitgalaxy_master.db "SELECT risk_cognitive_load, risk_state_flux FROM file_data WHERE file_path LIKE '%galaxyscope.py%';"
    ```
- Use this telemetry to act defensively when modifying high-risk or structurally massive code, maintaining the codebase's integrity without needlessly reading massive chunks of code into context.
- **Freshness:** unlike the architecture brief (auto-committed to `docs/` on every merge to main), the self-scan DB is gitignored on purpose -- it's a cheap-to-regenerate (~6-8s), disposable index, not history. It may be missing or stale in your checkout.
  - Fastest path in an active session: `python tests/tools/self_scan.py` regenerates it in place.
  - If you'd rather not run a local scan, the `gitgalaxy.yml` workflow's "Full Report" job now publishes a fresh copy as a `gitgalaxy-self-scan-db` build artifact on every merge to main -- pull the latest one from that workflow's most recent run instead.

## 7. Tri-Comparison Chart & Ledger (GitGalaxy vs. tree-sitter vs. ctags)

Full protocol lives in `docs/self_scan/tri_comparison_README.md` -- **read it before touching**
`docs/self_scan/tri_comparison_chart.svg`, `tri_comparison_ledger.json`, or
`tri_comparison_points_of_interest.md`. It's the canonical regen doc for both agents (Claude reads
it via `CLAUDE.md`); this section exists because skipping it caused a real incident (PR #2111,
2026-08-22): a regen ran with no genuine `universal-ctags` binary on PATH, and every language
silently degraded to a 2-tool (GitGalaxy + tree-sitter) comparison instead of erroring -- reverting
cobol's already-validated full-precision badge, degrading fortran's, and dropping ctags data across
every ctags-covered language in the chart, with no error message at all.

- **Confirm ctags before you regenerate, every time:** `ctags --version` MUST print
  "Universal Ctags", not error and not print an Arduino banner. Ubuntu's `arduino-ctags` package
  installs a binary under the same name and lacks most kinds this system needs -- a silently
  degraded regen still runs and still writes a file, so a clean exit code proves nothing here.
  If there's no root/sudo available, build a local one without it:
  ```bash
  mkdir -p /tmp/gitgalaxy-scratch/ctags-local && cd /tmp/gitgalaxy-scratch/ctags-local
  apt-get download universal-ctags && dpkg -x universal-ctags*.deb extracted/
  mkdir -p bin && ln -sf "$PWD/extracted/usr/bin/ctags-universal" bin/ctags
  export PATH="/tmp/gitgalaxy-scratch/ctags-local/bin:$PATH"
  ```
- **Always regenerate with `--all --write`, never a partial `--languages` list with `--write`** --
  a partial write overwrites the WHOLE file with only those languages, silently deleting every
  other language's row.
  ```bash
  python tests/tools/tri_comparison_chart.py --all --write
  python tests/tools/tri_comparison_report.py --write   # regen the points-of-interest doc too
  ```
- **Never hand-edit `tri_comparison_ledger.json`'s `status`/`verdict`/`still_reproduces`.** Those
  are set by a human (or an agent standing in for one) reading real source per
  `docs/self_scan/how_to_investigate_a_discrepancy.md`, then left alone by every later regen.
  `still_reproduces` in particular is recomputed from a live gather, not something to hand-set to
  `false` just because part of a shape's root cause got fixed in the same PR -- a shape can have a
  permanent, structural cause (e.g. ctags mistagging COBOL scope terminators as paragraphs) that
  keeps reproducing even after a real GitGalaxy bug contributing to the same shape is fixed. This is
  exactly the second, smaller bug PR #2111 introduced alongside the missing-ctags one.
- After regenerating, diff the languages you actually touched and confirm ctags/tree-sitter bars
  and badges are still present, not just that the file changed -- a plausible-looking diff is not
  the same as a correct one when the failure mode is silent by design.

## 8. Extraction Hardening & Adversarial Testing

When tasked with "hardening extraction coverage" or similar testing epics, avoid **Self-Consistency Bias** (writing tests that merely pass against the *current implementation* instead of the *actual ground truth*). Do not cement implementation flaws by writing invalid tests just because the current regex fails. 

To ensure rigorous, adversarial testing, structure your work into a strict **5-stage agent pipeline**:

1. **The Linguist (Research Subagent)**: Spawn a `research` subagent to independently research the language's syntax variations, historical changes, and edge cases from official documentation. Define what syntax is "valid" from ground truth first.
2. **The Red Teamer (Testing Subagent)**: Spawn a secondary subagent to generate adversarial, "deviously evil" `pytest` cases based on the Linguist's research. Keep this agent isolated from the current implementation so they try to break the rules, not validate them.
3. **The Engineer (Implementation Subagent)**: Spawn a third subagent (or run this stage yourself) to iteratively modify regexes in `language_standards.py` until the Red Teamer's test suite passes. Keep this trial-and-error out of the main context window.
4. **The QA Auditor (Verification Subagent)**: Once tests pass, have a subagent or yourself run `crucible_check.py` against the real-world corpus. Crucially, **manually verify correctness** by opening source files in `language-crucible` and checking the reported functions/methods to ensure they match real boundaries and aren't just hallucinated noise.
5. **The Manager (Primary Agent)**: Manage the pipeline, review the final sign-off, handle deterministic CI checks (`ruff`, `mypy`), regenerate golden baselines if necessary, and open the Pull Request with thorough context.

*(Tip: You can use the `/teamwork-preview` slash command to help automate and visualize complex multi-agent teams for large projects).*

## 8b. The Repo Constellation & Skills

- GitGalaxy is the hub of several sibling repos (language-crucible, keyword-rosetta,
  gitgalaxy-raw-output, squid-telemetry, gitgalaxy-population-analyses) and local-only
  directories (the `gitgalaxy/data/` source pool; stale `v1`–`v5`/`temp/`/`threat_hunter/`
  copies — **only `gitgalaxy/v6` is the live engine checkout**, verify paths before trusting a
  grep hit). **`docs/ecosystem.md` is the canonical, agent-neutral map** — read it before any
  cross-repo work (crucible pin bumps, keyword-rosetta sweeps). Note especially:
  keyword-rosetta's CI checks out gitgalaxy **main**, so a rosetta corpus PR depending on new
  engine rules stays **draft** until the engine PR merges.
- **Skills** (step-by-step workflow docs any agent can follow) live at `.agents/skills/`
  (a symlink to `.claude/skills/`) in this repo, and the same layout in keyword-rosetta
  (`rosetta-language-sweep`) and language-crucible (`expand-language-coverage`). Before
  re-deriving a workflow (extraction hardening, tri-comparison sweeps, language status docs,
  CI push checklist, release notes), check the relevant repo's skills directory first —
  `docs/ecosystem.md` has the full inventory.

## 9. Submitting Pull Requests

When working in this repository, **you MUST ALWAYS work on a side branch and submit a PR to `main`. NEVER merge or push your changes directly to `main` without a PR.** This strict workflow ensures that tests and multi-agent pipelines are run in isolation.

Before submitting a Pull Request, you must run the following deterministic tools in your belt to test out and fix your changes, acting as your local CI pipeline:
1. **Unit Tests:** `venv/bin/python -m pytest tests/`
2. **Lint & Types (Ruff, Mypy):** `PATH="$PWD/venv/bin:$PATH" python tests/tools/audit_check.py` (run with `--regenerate` or run `ruff format .` if auto-fixes are needed).
3. **Golden Fixtures (Crucible):** `venv/bin/python tests/tools/crucible_check.py` (run with `--update --yes` if the output intentionally changed due to better parsing rules).

When generating or submitting a Pull Request for this repository, it is critical to provide comprehensive context for reviewers. 
- **Descriptive PR Title:** The title must be highly descriptive and directly summarize the core outcome of the PR (e.g., instead of "Fix extraction", use "Fix #855: Harden Fortran extraction rules against pathological syntax").
- **Thorough PR Description:** Outline all technical changes, the specific reasoning behind the choices, and any edge-cases solved. 
  - For extraction hardening specifically, detail the pipeline steps used (Linguist, Red Team, etc.), but **do NOT write generic descriptions of the agents**. You must explicitly detail **WHAT they found**. (e.g., instead of "Linguist researched syntax gaps", write "Linguist found that CSS `@media` queries can be nested and contain complex `calc()` functions"). Explain any structural boundaries or tests added, and definitively explain *why* any golden masters changed.
  - **Metrics & Limitations:** You must explicitly list: (1) How many adversarial tests were created, (2) How many errors/failures were initially found by these tests, and (3) Any known regex limitations or edge-cases that remain for this language.
  - **Do not leave the PR body blank, sparse, or lame.** A poor description will cause the PR to be rejected.
- **Add relevant labels:** Ensure the PR has descriptive labels attached so it integrates correctly into the project's tracking and CI processes.
- **Cross-repo note:** If the PR participates in a cross-repo workflow (see `docs/ecosystem.md`), the body MUST name the companion PR/issue in the other repo, which side merges first and why, and what must re-run after the other side lands.

## 10. Scratch Files & Working Directory

Throwaway scripts, reproduction cases, one-off debug output, and generated test artifacts that
aren't meant to become part of the repo do **not** belong in the repo tree, not even temporarily.
Repeated ad hoc file drops like this (`scratch_func.py`, `pr_groovy_body.txt`, `pr_body.txt`, and
~130 similar files across both agents) required two full manual cleanup passes (see #1091).

- **Use `/tmp/gitgalaxy-scratch/antigravity/`** (create it if missing) for anything throwaway.
  This is outside the git repo, so nothing written there ever risks a `git add`.
- Claude Code uses its own separate directory, `/tmp/gitgalaxy-scratch/claude/` (see `CLAUDE.md`)
  — keep to your own directory so concurrent sessions from the two models don't collide when
  working the same worktree.
- If a throwaway file genuinely must live inside the repo temporarily (e.g. something that only
  works via relative pytest discovery), prefix its name `scratch_` at minimum so the root
  `.gitignore` backstop patterns catch it, and delete it before opening the PR rather than leaving
  it for a future cleanup pass.

## CI Ruff Audit
The `ruff-audit.yml` CI job enforces a STRICT EXACT MATCH against `tests/ruff_audit_baseline.json`. 
This baseline uses the line number as part of the JSON keys (e.g. `"gitgalaxy/core/detector.py:1002: PERF401"`).
**Important**: Any code edits that add or remove lines will SHIFT the line numbers of subsequent lint violations, causing the ruff audit to fail even if you didn't introduce new violations.
To fix this, ALWAYS regenerate the baseline before committing if you've added/removed lines in files with pre-existing lint violations:
`python -c "from tests.ruff_audit import run_ruff_check; import json; json.dump(run_ruff_check(), open('tests/ruff_audit_baseline.json', 'w'), indent=2, sort_keys=True)"`

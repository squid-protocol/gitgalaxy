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
    sqlite3 docs/self_scan/gitgalaxy_master.db "SELECT db_complexity, is_recursive, calls_out_to FROM function_data WHERE func_name = 'execute_pipeline';"
    ```
  - *Example:* Check a file's risk exposure before adding features (e.g. `risk_cognitive_load`, `risk_state_flux`):
    ```bash
    sqlite3 docs/self_scan/gitgalaxy_master.db "SELECT risk_cognitive_load, risk_state_flux FROM file_data WHERE file_path LIKE '%galaxyscope.py%';"
    ```
- Use this telemetry to act defensively when modifying high-risk or structurally massive code, maintaining the codebase's integrity without needlessly reading massive chunks of code into context.
- **Freshness:** unlike the architecture brief (auto-committed to `docs/` on every merge to main), the self-scan DB is gitignored on purpose -- it's a cheap-to-regenerate (~6-8s), disposable index, not history. It may be missing or stale in your checkout.
  - Fastest path in an active session: `python tests/tools/self_scan.py` regenerates it in place.
  - If you'd rather not run a local scan, the `gitgalaxy.yml` workflow's "Full Report" job now publishes a fresh copy as a `gitgalaxy-self-scan-db` build artifact on every merge to main -- pull the latest one from that workflow's most recent run instead.

## 7. Extraction Hardening & Adversarial Testing

When tasked with "hardening extraction coverage" or similar testing epics, you must avoid **Self-Consistency Bias** (writing tests that merely pass against the *current implementation* instead of the *actual ground truth*). 

To ensure rigorous, adversarial testing:
1. **Define "Valid" from Ground Truth First**: Before looking at the current regex implementation, determine what syntax is valid by consulting official language documentation, a ground-truth corpus, or other established rules in the same file (e.g. cross-referencing `branch`, `safety`, and `state_mutation` rules to find missing opcodes).
2. **Do Not Cement Implementation Flaws**: If a structurally valid syntax does not match the current regex, the regex is buggy, NOT the syntax. Never write a negative/invalid test to "prove" the regex correctly ignores it.
3. **Cross-Rule Validation**: Actively check sibling rules in `language_standards.py`. If `args` extracts registers, make sure it covers the instructions listed in `state_mutation` that mutate those registers.
4. **Corpus Grepping**: When in doubt about whether a syntax exists or how common it is, `grep` the actual corpus (e.g. in `language-crucible`) to find empirical evidence of the shape and frequency of certain keywords or patterns.
5. **Multi-Round Adversarial Checks**: 
   - *Round 1 (Breadth)*: Gather keywords, opcodes, and structures from external docs and sibling rules.
   - *Round 2 (Regex)*: Check the regex against this gathered ground truth. Identify missing captures and false positives.
   - *Round 3 (Corpus)*: Verify fixes against real corpus data using `crucible_check.py` to ensure the modifications match reality.

## 8. Submitting Pull Requests

When working in this repository, **always work on a side branch and submit a PR to `main`. Do not merge or push directly to `main`.**

Before submitting a Pull Request, you must run the following deterministic tools in your belt to test out and fix your changes, acting as your local CI pipeline:
1. **Unit Tests:** `venv/bin/python -m pytest tests/`
2. **Lint & Types (Ruff, Mypy):** `PATH="$PWD/venv/bin:$PATH" python tests/tools/audit_check.py` (run with `--regenerate` or run `ruff format .` if auto-fixes are needed).
3. **Golden Fixtures (Crucible):** `venv/bin/python tests/tools/crucible_check.py` (run with `--update --yes` if the output intentionally changed due to better parsing rules).

When generating or submitting a Pull Request for this repository, it is critical to provide comprehensive context for reviewers. 
- **Always add a thorough description:** Outline the changes, the rationale, and any structural boundaries or tests added. Explain *why* any golden masters changed. Do not leave the PR body blank or sparse.
- **Add relevant labels:** Ensure the PR has descriptive labels attached so it integrates correctly into the project's tracking and CI processes.

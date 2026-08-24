---
name: ci-push-checklist
description: The required CI validation gauntlet for shipping a code fix to GitGalaxy's core engine (language_standards.py, detector.py, prism.py). Use when preparing to push an issue fix, generating a PR, or validating any change to core parsing logic.
---

When shipping a code fix or addressing a discrepancy in GitGalaxy, the following full validation chain MUST be executed before opening the PR. This ensures parsing accuracy is preserved and data-driven artifacts are synchronized.

## 0. Clean Working Directory
* **Untracked Files:** Before committing, ALWAYS run `git status` and review untracked files. Do not use `git add .` blindly. Accidentally committing local virtual environments (e.g. `venv/`, `venv_zero/`) or temporary Python scratch scripts will immediately trigger pipeline failures from the X-Ray Inspector (flagging checked-in binaries) or CodeQL (flagging dirty script code).
* **Explicit Adds:** Prefer `git add <file>` for specific files.

## 1. Local & Unit Validation
* **Standalone Regex Re-test:** Isolate the target regex (e.g., `func_start`) against the failing corpus file manually to ensure false positives and negatives are resolved without affecting real matches.
* **Extraction Gauntlet & Strict Tests:** Run `pytest tests/extraction/languages/test_<lang>.py` and `test_<lang>_strict.py` for the language you modified.

## 2. Static Analysis & Linting
* **Ruff Formatting & Linting:** `python tests/ruff_audit.py --ci`
* **Mypy Type Checking:** `python tests/mypy_audit.py --ci`

## 3. Global Golden Master Verification
* **Run the Crucible Check (Mandatory):** Execute `python tests/tools/crucible_check.py` against the full ~80-repo corpus.
* **Re-Bless Golden Masters:** If `crucible_check.py` shows expected, accurately traced diffs resulting from your fix, bless the new state:
  `python tests/tools/crucible_check.py --update --yes`
  * **CRITICAL CORPUS WARNING:** NEVER clone a fresh, temporary copy of `language-crucible` inside the `gitgalaxy` workspace just to bypass sandbox or path restrictions. A fresh internal clone alters absolute path metadata and Git footprints, which shifts the entire graph topology and generates massive, invalid diffs that fail in CI. Always point `LANGUAGE_CRUCIBLE_PATH` to the existing pristine sibling directory (e.g., `../language-crucible`) and run with bypass sandbox privileges if needed.

## 4. Discrepancy Ledgers & Tri-Comparison
* **CI now gates this automatically if you touched `detector.py`/`prism.py`/`language_standards.py`:**
  `tri-comparison-audit.yml` fails your PR if GitGalaxy's own *validated* precision
  (`func_precision`/`class_precision`, read after ledger verdicts are applied — never a raw
  disagreement count) regresses against the committed `tests/tri_comparison_baseline_<lang>.json`.
  Run it yourself before pushing to catch this early: `python tests/tools/tri_comparison_chart.py
  --all --ci` (needs real `ctags` on PATH and the language-crucible corpus — see the README's
  "Reproducing or updating this locally" section). If your fix intentionally improves a language's
  precision, lock it in with `python tests/tools/tri_comparison_chart.py --regenerate --languages
  <lang>` and commit the updated baseline file.
* **You no longer need to manually regenerate the chart/ledger/report before pushing.** A
  push-to-main companion workflow (`tri-comparison-history.yml`) does that automatically once your
  PR merges, opening its own auto-merged PR only if the numbers actually moved. Feel free to still
  run it locally for a sanity check, but it's no longer a required pre-push step the way it used
  to be:
  `python tests/tools/tri_comparison_chart.py --all --write`
  `python tests/tools/tri_comparison_report.py --write`
* **NEVER hand-edit `still_reproduces`:** it's automatically recomputed by the regen script (a
  shape might have multiple contributing causes, so a single fix doesn't guarantee it stops
  reproducing). If you've added a human verdict to an unvalidated shape, only update
  `"status": "validated"`, `"verdict"`, `"investigated_by"`, and `"investigated_at"` by hand.

## 5. Tree-Sitter AST & Accuracy Baseline
* **Audit AST Accuracy:** Run `python tests/tools/tree_sitter_accuracy_audit.py --ci --all`.
  * **Note on Ground Truth Drift:** GitGalaxy supplements tree-sitter ground truth inside blind spots. Improving GitGalaxy's regex precision can therefore cause `real_functions` or `real_classes` (the ground truth) to drop (as false positives are correctly eliminated).
* **Regenerate AST Accuracy Baseline (If needed):** If `tree_sitter_accuracy_audit.py` fails due to ground truth drifting for valid reasons, regenerate the baseline:
  `python tests/tools/tree_sitter_accuracy_audit.py --regenerate --lang <lang>`
* **Regenerate AST Accuracy History & Chart:**
  `python tests/tools/tree_sitter_accuracy_audit.py --history`
  `python tests/tools/tree_sitter_accuracy_audit.py --chart`
  *(Commit the resulting CSV, SVG, baseline JSON, and `language_standards.py` changes.)*

**Note:** Tools that scan the `language-crucible` corpus (such as `crucible_check.py`, `tri_comparison_chart.py`, and `tree_sitter_accuracy_audit.py`) require reading a sibling repository and should be executed using `BypassSandbox=true` or run with proper path resolution.

## 6. Resolving Merge Conflicts on Auto-Generated Files
If `main` advances and causes merge conflicts in `tri_comparison_ledger.json`, `tri_comparison_chart.svg`, or any golden master JSONs, **never attempt to manually resolve the conflict markers**.
1. Check out the upstream version of the files to clear the conflict markers:
   `git checkout origin/main -- docs/self_scan/tri_comparison_chart.svg docs/self_scan/tri_comparison_ledger.json`
   * **CRITICAL LEDGER WARNING**: `tri_comparison_ledger.json` contains *manual annotations* (`status`, `verdict`, `credit_tools`). If you manually validated shapes on your branch, checking out `origin/main` will erase your validations! You MUST back up your manual changes (e.g. write a short Python script to re-apply them), check out `origin/main`, run your script to re-apply your verdicts, and *then* regenerate.
2. Re-run the relevant regen scripts (`crucible_check.py --update --yes`, `tri_comparison_chart.py --all --write`, etc.). The scripts will cleanly recalculate and overwrite the files using your latest code and the upstream's latest ledger baseline.

## 7. Continuous Integration Monitoring (Agentic)
After pushing your branch and/or opening the PR, you MUST monitor the CI pipeline to ensure it passes.
1. Run `gh run watch` in the background (e.g., using your `run_command` tool with `WaitMsBeforeAsync` set so it detaches to the background). 
2. Do not wait in a polling loop. Once the background task finishes, the system will automatically wake you up with the results.
3. If the CI fails, read the logs, fix the issue, and push the update.

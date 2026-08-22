---
name: ci-push-checklist
description: The required CI validation gauntlet for shipping a code fix to GitGalaxy's core engine (language_standards.py, detector.py, prism.py). Use when preparing to push an issue fix, generating a PR, or validating any change to core parsing logic.
---

When shipping a code fix or addressing a discrepancy in GitGalaxy, the following full validation chain MUST be executed before opening the PR. This ensures parsing accuracy is preserved and data-driven artifacts are synchronized.

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

## 4. Discrepancy Ledgers & Tri-Comparison
If your fix resolves an open shape from the Tri-Comparison Ledger (`docs/self_scan/tri_comparison_ledger.json`):
* **Update the Ledger JSON:** Locate the shape key, set `"status": "validated"`, update the `"verdict"`, set `"investigated_by"`/`"investigated_at"`, and set `"still_reproduces": false` if it no longer occurs.
* **Regenerate the Chart:** Re-run the tri-comparison to update the SVG:
  `python tests/tools/tri_comparison_chart.py --all --write`

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

### Description
<!-- Describe your changes in detail -->

### Core Engine Modification Checklist
If your PR changes the core parsing engine (`language_standards.py`, `detector.py`, `prism.py`), you **MUST** complete the following validation gauntlet before merging:

- [ ] **Golden Master Verification**: Ran `crucible_check.py` to verify diffs, and ran `crucible_check.py --update --yes` if the baseline changed due to intentional parsing improvements.
- [ ] **Tri-Comparison Audit**: Handled by CI automatically, but you should run `python tests/tools/tri_comparison_chart.py --all --ci` locally first. If you intentionally improved precision, regenerate the baseline: `python tests/tools/tri_comparison_chart.py --regenerate --languages <lang>`.
- [ ] **Tree-Sitter Accuracy**: Ran `python tests/tools/tree_sitter_accuracy_audit.py --ci --all`. If ground truth drifted for valid reasons, regenerated the baseline with `python tests/tools/tree_sitter_accuracy_audit.py --regenerate --lang <lang>`.

> **Note for AI Agents**: If you are an AI agent generating this PR, you MUST invoke the `ci-push-checklist` skill to ensure these steps are completed properly.

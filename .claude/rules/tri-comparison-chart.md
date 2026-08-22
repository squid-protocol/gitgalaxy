---
name: regenerate-tri-comparison-chart-all
description: Ensure the tri-comparison chart is always regenerated for all languages instead of just the ones being modified.
---

# Always Regenerate Tri-Comparison Chart For All Languages

When regenerating the tri-comparison chart (`tests/tools/tri_comparison_chart.py`) and its ledger to verify fixes, you **MUST ALWAYS** regenerate it for ALL languages, not just the languages that were improved.

To do this, use the `--all` flag:
`python tests/tools/tri_comparison_chart.py --all --write`

This ensures that the final chart accurately reflects the global state of the engine rather than isolating metrics for a single language.

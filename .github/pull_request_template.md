## Summary

<!-- What does this change and why? Link the issue it closes, e.g. "Fixes #488." -->

## Type of change

- [ ] Bug fix
- [ ] New feature / language support
- [ ] Parsing or engine logic (`gitgalaxy/core/detector.py`, `language_standards.py`, `prism.py`, or a per-language rule)
- [ ] Docs, tooling, or CI only
- [ ] Other (describe above)

## CI checklist

Check only what applies to your change — CI enforces the rest, but running it locally first saves a review round-trip.

- [ ] `python tests/tools/audit_check.py` passes (bundles the ruff/mypy/dead-key baseline-gated audits + `ruff format --check`)
- [ ] `python -m pytest tests/` passes, or the specific test file(s) for this change (list them below)
- [ ] **Touches parsing/engine logic (see above)?** `python tests/tools/crucible_check.py` passes — this is the Differential Scan against the ~80-repo calibrated baseline (see `CONTRIBUTING.md`)
- [ ] **Touches parsing/engine logic (see above)?** `python tests/tools/tree_sitter_accuracy_audit.py --all --ci` passes — a *different* gate from the Differential Scan above: it checks per-language recall/precision against tree-sitter ground truth, and a corpus-wide golden-master diff passing does not mean this also passes (it catches regressions in files the ~80-repo baseline doesn't cover)
- [ ] **Changes the CLI's output JSON schema?** Verified on [GitGalaxy.io](https://gitgalaxy.io) or the local Airgap Observatory that 3D rendering still works

## Differential Scan target

<!-- Parsing/engine changes only: link the specific repo this PR is meant to fix or improve, so it runs
alongside the 80-repo baseline. Leave blank if not applicable. -->

## Verification

<!-- Paste the actual commands you ran and their result, e.g.:
$ python tests/tools/audit_check.py            -- clean
$ pytest tests/tools_recorders/test_llm_recorder.py -q   -- 12 passed
-->

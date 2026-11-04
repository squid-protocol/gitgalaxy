---
description: "Baseline-gated ruff, mypy and dead-key audit details: content-keyed baselines, audit_check.py regenerate semantics, and what regenerate accepts or rejects."
---
# Baseline-gated audits: details

Moved verbatim from CLAUDE.md (kept out of the always-loaded context). CLAUDE.md links here.

These are regression gates, not zero-tolerance floors: each has a committed baseline file
(`tests/ruff_audit_baseline.json` etc.) and `--ci` mode fails only on *new* findings beyond it.
This lets CI enforce "no new problems" without demanding the pre-existing backlog be fixed
first. If you fix backlog findings, regenerate the baseline with `--write-baseline`
(`python tests/ruff_audit.py --write-baseline`, same for `mypy_audit.py`). `ruff format
--check` is the one zero-tolerance exception (whole repo was reformatted once at adoption, so there's no backlog to carry).

Use `python tests/tools/audit_check.py` (add `--regenerate`) instead of running the three
`--ci` scripts separately and manually diffing each baseline by eye — it bundles all three plus
the format check. Since #3384 the ruff and mypy baseline keys are content-based --
`{file}: {code} @{hash of the whitespace-stripped flagged line}#{occurrence}` (`tests/lint_baseline.py`)
-- not line numbers, so an unrelated line shift elsewhere in a file changes nothing and can't
conflict on rebase. `--regenerate` only auto-accepts an *edited* baselined line (a new key that
pairs one-for-one with a now-stale entry of the same file/code/message); a new finding, or a new
duplicate of a baselined line (next `#occurrence`), still fails. Human-readable output still
prints each finding's current line number.

## Doc references (`tests/doc_refs_audit.py`)

The same regression gate for hand-written markdown: a backticked repo path, relative link or this repo's GitHub URL
whose target is gone, a script flag the script no longer spells, a bare Python file name no file is called, a skill
that does not exist, and a `gitgalaxy/**/README.md` that never names a public module beside it. It runs on every PR
(the "Small audits" job, before the plan's skip) and in `audit_check.py`.

* A finding your change caused: fix the doc in the same PR (a renamed path, a dropped flag, the new module's row).
* A finding that is wrong: narrow the check in the script (`GENERATED`, `FOREIGN`, `ABOUT_OTHERS`, `SIBLING_REPOS`,
  or `ALLOWED` with a reason), never `--write-baseline` to make it pass.
* After fixing baselined drift: `python tests/doc_refs_audit.py --write-baseline` shrinks the baseline (`--ci` lists
  the keys that no longer occur). Keys are `check | doc | target`, no line numbers.
* Generated pages are out of scope: fix their generator.

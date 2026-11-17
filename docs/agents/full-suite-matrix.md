---
description: "How to run the Full Suite Gate (All OS x Python) matrix on a PR head (shepherd:matrix label or a dispatch), when it runs on its own, and why there is no PR trigger."
---
# Running the OS x Python matrix on a PR head

Moved from CLAUDE.md (kept out of the always-loaded context). CLAUDE.md links here.

`full-suite-gate.yml` (the "Full Suite Gate (All OS x Python)" check) has **no `pull_request` trigger** (#4518:
`gh pr create --label` fired the matrix on every PR and starved the queue). It runs nightly, on `v*` tags, and when
`post-merge.yml` dispatches it on main (cadence-limited, #4825/#5136). So a PR head never goes through the matrix
unless you ask. Before #4518 it ran on `labeled` only, and #3207 merged a Windows-only fix the matrix never saw.

For a change that can break on one OS or Python version (Windows paths, 3.11 syntax, macOS fork safety), run it on
the head deliberately:

```bash
# preferred: the shepherd dispatches it on the PR branch (same-repo only); auto-merge waits for a green run on that head (docs/ci.md)
gh api repos/squid-protocol/gitgalaxy/issues/<n>/labels -f 'labels[]=shepherd:matrix'
# or by hand on a same-repo branch
gh workflow run "Full Suite Gate (All OS x Python)" --ref <branch>
gh run list --workflow full-suite-gate.yml --branch <branch> --limit 3   # find the run
```

The legs (parts, timeouts) come from `suite_shard_plan.py --gate` over the committed `.test_durations` (#5919), not
from YAML. Since Python 3.10 was dropped (#3322) the trimmed and untrimmed grids are equal; `-f full_matrix=true`
only matters on a main dispatch, where it keeps the ubuntu / 3.12 leg (otherwise dropped because `smoke-test.yml`
already runs it, #5953). Don't add a `pull_request` / `synchronize` trigger: that hands back the queue cost (#3209, #4518).

## Implied matrix (#8425)

A PR carrying `shepherd:merge` runs the matrix without the `shepherd:matrix` label when `tests/tools/matrix_plan.py`
selects it (the shepherd reads it in `gather()`: dispatch on the head, auto-merge waits for green, the digest names the
reason). Two rules, both narrow because the legs are expensive:

* the PR fixes a `ci-red-main` issue (`Closes` / `Fixes` / `Resolves` / `Part of #N`, N carrying the label): #8165 ->
  #8167 -> #8181 and #8185 -> #8195 each turned main red again on another platform;
* the PR adds or changes a `tests/**/*.py` file that shells out to a platform tool (rsync, sed, find, ...), links or
  chmods, with no platform guard in the added lines, or creates files under names differing only by case or reads path case.

Nothing unreadable selects (no file list, 300 or more files). Replay over merged PRs: `python tests/tools/matrix_plan.py
--replay 50`. A fork head still waits for a maintainer's by-hand run.

**Worker rule:** a test that shells out to a platform tool (rsync, sed, find, cp, chmod, ...) carries a platform guard
(`pytest.mark.skipif(sys.platform ...)` or `shutil.which`), and a fixture that creates files never relies on two names
differing only by case. The guard also keeps the PR off the implied matrix.

## Cap headroom (#5156)

Each `full-suite-gate.yml` leg's `timeout` is ~1.5x its expected part time (now planned from the measured durations, #5919). Re-measure when a leg passes ~80% of its cap
(`gh run view <id> --json jobs`, job `completedAt - startedAt`) and add a part rather than raise the cap.
Measured 2026-10-18 on two scheduled main runs (minutes, worst part / cap):

| OS | worst / cap | action |
|---|---|---|
| ubuntu | 15 / 20 | none |
| macOS | 17 / 22 | none |
| windows (2 parts) | 22 / 25 | owner: 3 parts, cap 25 (workflow edit, #5156) |

Not yet surveyed (fixed caps in other workflows): cics-crucible 45, blocker-baseline 60, evidence-refresh 90,
java-compile 40, ports-compile 40, the 30-min audits (tri-comparison, tree-sitter, call-graph, unicode-gauntlet).
The 40-240 s evidence tests that drive the growth need marking or trimming, not caps.

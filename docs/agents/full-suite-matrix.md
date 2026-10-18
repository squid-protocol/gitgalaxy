---
description: "How to re-run the Full Suite Gate (All OS x Python) matrix on a labelled PR after pushing new commits, trimmed vs full grid, and why synchronize is not used."
---
# Re-running the OS x Python matrix on a PR head

Moved verbatim from CLAUDE.md (kept out of the always-loaded context). CLAUDE.md links here.

`full-suite-gate.yml` (the "Full Suite Gate (All OS x Python)" check) triggers on
`pull_request: types: [labeled]`, not on `synchronize`. That was deliberate — per-label runs had
put 48 jobs on one SHA and pushed the queue to 23-65 minutes — but it means **the matrix runs
once, against the SHA that carried the label, and a commit pushed afterwards never goes through
it.** #3207 merged a Windows-only fix that way: it was correct and test-covered, but the matrix
never saw it.

So after pushing to a PR that has already been labelled, re-run it deliberately:

```bash
gh workflow run "Full Suite Gate (All OS x Python)" --ref <branch>       # trimmed PR grid
gh workflow run "Full Suite Gate (All OS x Python)" --ref <branch> -f full_matrix=true   # 12-way
gh run list --workflow full-suite-gate.yml --branch <branch> --limit 3   # find the run
```

The trimmed grid is what a label gives you; since Python 3.10 was dropped (#3322) the supported
Pythons are only the floor (3.11) and ceiling (3.12), so it is the same 12 legs as `full_matrix=true`,
the untrimmed grid a `v*` tag gets. Removing and
re-adding a label still works and is equivalent to the first form. Don't reach for `synchronize`
as a fix — that hands back the queue cost the label-only rule bought (#3209).

## Cap headroom (#5156)

Each `full-suite-gate.yml` leg's `timeout` is ~1.5x its expected part time. Re-measure when a leg passes ~80% of its cap
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

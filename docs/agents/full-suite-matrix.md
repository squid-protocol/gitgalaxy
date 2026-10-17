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

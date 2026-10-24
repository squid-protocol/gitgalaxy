---
description: "Guidelines and traps to avoid when updating golden masters"
globs: "tests/golden_master_audit/**, tests/golden_master_zero_dep_audit/**, tests/golden_store.py, tests/tools/update_golden_master.py, gitgalaxy/galaxyscope.py"
---
# Golden Master Generation Guidelines

**CRITICAL INSTRUCTION: Bless only via `tests/tools/box/golden-lock.sh python tests/tools/crucible_check.py --update --yes`** (both legs, CI-matched venvs). Never run `update_golden_master.py` from a personal venv (py3.12 vs the CI pin gave ~2.9k phantom diffs, #4258).

### 1. Untracked File Poisoning
`GalaxyScope` scans the local filesystem. Untracked scratch files or shadow clones (an internal `language-crucible/` checkout) get baked into the local `golden_master_audit/` fixture, and the clean CI checkout then mismatches by hundreds of lines.
* **Rule:** Keep scratch files outside the repo (`/tmp/gitgalaxy-scratch/`) and bless in a clean worktree. Never `git clean -fdx` in the primary checkout: it deletes `.crucible_venvs/` (the CI-matched bless venvs).

### 2. Environment Symmetry & Local Bypasses (The Timeout Trap)
`GalaxyScope` uses a hardcoded 15-second `SIGALRM` ReDoS fuse. Slower CI runners may timeout on large files (like `frames.ts`) even if your local CPU doesn't, yielding `0` results on CI versus your locally generated master. Temporarily editing the local fuse to bypass the timeout locally guarantees a CI mismatch.
* **Rule:** NEVER bypass test configurations, timeouts, or constraints locally. If an execution timeout is tripping, you must increase the timeout in the committed codebase (e.g., `gitgalaxy/galaxyscope.py`) so the CI and local environments behave symmetrically.

### 3. Ghost Clones (Language Crucible Location)
The test scripts resolve the `LANGUAGE_CRUCIBLE_PATH` corpus relative to the repo. If cloned inside the repo directory, it becomes untracked and poisons the scanner.
* **Rule:** Ensure the `language-crucible` corpus is cloned as a **sibling** directory (e.g., `../language-crucible`) to the repo, never inside the repository root.

### 4. Worktree env for the bless
* `golden-lock.sh` and `heavy-run.sh` exec `python` by name: put the selfscan venv's bin dir on PATH (re-export it in EVERY Bash call: a worker shell loses it between calls) or they fail with
  `python: No such file` (#5426, #5528). `audit_check.py` shells out to `mypy` the same way (FileNotFoundError 'mypy').
* `crucible_check.py` from a worktree needs `LANGUAGE_CRUCIBLE_PATH`, `CICS_CRUCIBLE_PATH` and `ESTATE_CRUCIBLE_PATH` set
  to the sibling checkouts (`/srv/storage_16tb/projects/gitgalaxy/<name>` on the owner's box; run `sync-pins.sh` first).
  A background shell loses them: pass them explicitly (#5426, #5435, #5471).
* An aperture change can move a pinned corpus's ground truth with the pin unchanged: check the language baseline when an
  aperture PR merges (#5481, #5504).
* A fast lane that skips the detector on an ambiguous-extension `.h` file gets the file banished by
  `statistical_auditor`; skip only the Security Lens (#5441).
* `crucible_check.py` on pristine HEAD can show ~11k differences when box load is above 6: compare against an
  unchanged-engine control before reading drift as yours (#6298). `doom_speedrun.py scan` reuses `<work>/scans/<engine-sha>`
  at the same HEAD: `rm -rf` it to rescan after an engine edit (#6298).

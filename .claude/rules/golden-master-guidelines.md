---
description: "Guidelines and traps to avoid when updating golden masters"
globs: "tests/golden_master*.json, tests/tools/update_golden_master.py, gitgalaxy/galaxyscope.py"
---
# Golden Master Generation Guidelines

**CRITICAL INSTRUCTION: Read these rules before running `update_golden_master.py`.**

### 1. Untracked File Poisoning (The Clean State Rule)
`GalaxyScope` aggressively scans the local filesystem. Untracked scratch files (`fix_strategy.md`, `.venv`, etc.) or internal shadow clones (like an internal `language-crucible/` checkout) will be ingested and baked into the local `golden_master_audit.json`. When pushed, the pristine CI environment won't have these files, resulting in hundreds of mismatched lines on GitHub Actions.
* **Rule:** You MUST run `git clean -fd` to completely wipe out any untracked files, scratch artifacts, or ghost directories from the repository root BEFORE running `update_golden_master.py`.

### 2. Environment Symmetry & Local Bypasses (The Timeout Trap)
`GalaxyScope` uses a hardcoded 15-second `SIGALRM` ReDoS fuse. Slower CI runners may timeout on large files (like `frames.ts`) even if your local CPU doesn't, yielding `0` results on CI versus your locally generated master. Temporarily editing the local fuse to bypass the timeout locally guarantees a CI mismatch.
* **Rule:** NEVER bypass test configurations, timeouts, or constraints locally. If an execution timeout is tripping, you must increase the timeout in the committed codebase (e.g., `gitgalaxy/galaxyscope.py`) so the CI and local environments behave symmetrically.

### 3. Ghost Clones (Language Crucible Location)
The test scripts resolve the `LANGUAGE_CRUCIBLE_PATH` corpus relative to the repo. If cloned inside the repo directory, it becomes untracked and poisons the scanner.
* **Rule:** Ensure the `language-crucible` corpus is cloned as a **sibling** directory (e.g., `../language-crucible`) to the repo, or enforce its deletion from within the repository root during `git clean -fd`.

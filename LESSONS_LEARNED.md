# Lessons Learned

## CI/CD Hardening & Workflow

### 1. The Golden Crucible Trap
When running `crucible_check.py --update --yes`, it generates TWO modified JSON files in the working directory:
* `tests/golden_master_audit.json`
* `tests/golden_master_zero_dep_audit.json`

**MISTAKE TO AVOID**: Do NOT run `git add tests/golden_master*.json` **before** running the script! If you do, git will track the unmodified versions, and your subsequent `git commit` will commit the old versions, leading to mysterious CI failures (Golden Crucible Resilience Test).
**SOLUTION**: 
Always run `scripts/update_golden_masters.sh` which automates this safely: it tests the regexes, regenerates the files, and stages them precisely.

### 2. Resolving Golden Master Merge Conflicts
When `main` updates the golden masters while you are on a side branch, you will encounter merge conflicts.
**Do NOT manually resolve the JSON merge conflicts**.
Instead, strictly follow this pattern:
1. `git merge origin/main` (this will pause with conflicts)
2. `git checkout --theirs tests/golden_master_audit.json tests/golden_master_zero_dep_audit.json`
3. Resolve any Python regex file conflicts and ensure `EXTRACTION_CASES` dicts are syntactically valid (watch for missing commas and syntax errors when stipping markers).
4. Run `venv/bin/pytest tests/core_engine/ tests/extraction/` to ensure syntax is valid (strict structural-signature tests now live under `tests/core_engine/languages/`, not just `test_language_standards_strict.py`).
5. Run `scripts/update_golden_masters.sh` to fuse the changes from `main` with your side-branch changes.

### 3. Verification & Hook Timers
Do not fire-and-forget PR pushes.
Whenever pushing a PR, use the `/schedule` tool or `gh pr checks` to set a 5-minute timer to wake up and check if the PR passed CI. If it failed, fix it immediately. Do not assume local successful execution implies CI success, as Python versioning, uncommitted local artifacts, and stale test baselines can cause discrepancies.

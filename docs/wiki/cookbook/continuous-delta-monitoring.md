---
description: "Enterprise DevSecOps requires continuous monitoring. Every pull request must be audited for architectural drift, security leaks, and cognitive load..."
---
# How to Enable 24/7 Continuous Delta Monitoring

Enterprise DevSecOps requires continuous monitoring. Every pull request must be audited for architectural drift, security leaks, and cognitive load expansion. However, running a full structural scan on a massive repository for every commit wastes massive amounts of compute and paralyzes CI/CD pipelines.

GitGalaxy solves this O(N) scaling problem using the **Delta Engine**. By leveraging the native SQLite **Record Keeper** and the **State Rehydrator**, GitGalaxy can monitor thousands of repositories 24/7 by only processing the exact files that changed, while accurately recalculating the systemic blast radius for the entire ecosystem.

## The Architecture of the Delta Engine

The Delta Engine operates on a cycle of Freezing (SQLite) and Thawing (RAM Rehydration).

### 1. The Baseline "Cold" Scan (Record Keeper)
When GitGalaxy first encounters a repository, it performs a full extraction and routes the output to the `Record Keeper`. This module bypasses intermediate JSON files and dumps the multi-dimensional RAM state (the `cryolink` dictionary) directly into a highly relational SQLite database.

```bash
galaxyscope /path/to/repo --db-only
```
*Result: Generates `<repo>_galaxy_master.db` (`<stem>_master.db`, see the [CLI reference](../01-02-galaxyscope-cli-reference.md)) containing the baseline topological physics.*

### 2. The CI/CD Webhook Trigger
When a developer pushes a new commit, your CI/CD pipeline (e.g., GitHub Actions, Jenkins) runs a delta scan against the baseline database. GalaxyScope computes the file delta itself, with `git diff --name-status <baseline-commit>` (working tree against the baseline, so staged and unstaged edits count; untracked files do not):

```bash
galaxyscope /path/to/repo --incremental /path/to/repo_galaxy_master.db
# optional: pick the baseline commit instead of the latest by date
galaxyscope /path/to/repo --incremental /path/to/repo_galaxy_master.db --baseline <COMMIT_SHA>
```

If rehydration or the diff fails, it logs a warning and falls back to a full scan.

### 3. The Warm Boot (State Rehydrator)
Instead of booting the heavy optical scanners, the orchestrator triggers the `StateRehydrator`. It queries the SQLite database for the baseline commit (the latest by date unless `--baseline` names one) and rebuilds the RAM dictionary.

### 4. Surgical Splicing & The Ripple Effect
GitGalaxy uses the Git delta to execute a surgical strike:
1. **Eviction:** It instantly deletes the `DELETED` files from the RAM dictionary.
2. **Optical Scan:** It spins up the CPU workers to scan *only* the `ADDED` and `MODIFIED` files (often just 1 or 2 files, taking milliseconds).
3. **The Ripple Effect (Graph Recalculation):** Because a single changed file can alter the PageRank (Blast Radius) of 100 downstream dependencies, GitGalaxy recalculates the global Network Topology using the newly patched RAM dictionary.
4. **Database Seal:** The updated universe is appended to SQLite under the new commit hash, creating a perfect time-series ledger of architectural drift.

## Executing the Delta Mission

The supported entry point is the CLI's `--incremental` flag above. Under the hood, `main()` in `gitgalaxy/galaxyscope.py` does the equivalent of:

```python
from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.galaxyscope import Orchestrator

# 1. Thaw the previous universe (commit_hash=None means latest by date)
rehydrator = StateRehydrator("repo_galaxy_master.db")
baseline = rehydrator.load_state("my_enterprise_repo", commit_hash=None)

# 2. Ignite the Delta Engine (config: the resolved GalaxyScope config dict main() builds)
scope = Orchestrator("/path/to/repo", config)
scope.execute_incremental_scan(
    baseline["ram_cache"],
    added=["src/api/new_route.py"],
    modified=["src/core/auth.py"],
    deleted=["src/legacy/old_auth.py"],
    db_output_path="repo_galaxy_master.db",
)
```

`config` is not a public API: build it the way `main()` does, or use the CLI.

By shifting from O(N) full scans to O(1) delta updates, a single central GitGalaxy server can monitor thousands of active enterprise repositories simultaneously with zero pipeline latency.

> **Read the full technical specification:** [State Rehydrator](../02-22-state-rehydrator.md)

---

**[⬅️ Back to Master Index](../index.md)**

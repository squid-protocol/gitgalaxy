---
description: "> **File Reference:** [`gitgalaxy/metrics/chronometer.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/metrics/chronometer.py)"
---
# Chronometer (Git History Analysis)

> **File Reference:** [`gitgalaxy/metrics/chronometer.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/metrics/chronometer.py)

The Chronometer component measures code churn (frequency of changes) and file stability by analyzing Git history. While the rest of the pipeline performs static analysis on the codebase at a single point in time, the Chronometer provides the historical context required by the Signal Processor to calculate risk exposure metrics.

## Batch Processing Strategy

If the engine queried Git history for every individual file during parallel multiprocessing, it would create a massive I/O bottleneck. 

To ensure high performance, the Chronometer utilizes a **batch caching strategy**. It performs a bulk metadata sweep during initialization, caching the results in internal state maps (`churn_map`, `mtime_map`, `author_map`). When worker threads later request temporal data for a specific file, the retrieval is a fast $O(1)$ memory lookup.

## Commit Boundaries & Historical Sweep

To accurately calculate the age and stability of files, the engine must first establish the boundaries of the repository.

* **Boundary Discovery:** The component queries `git rev-list` and `git log` to find the timestamps of the first commit and the latest commit across the entire project.
* **Cosmetic Commit Filtering:** The Chronometer automatically loads `.git-blame-ignore-revs` (if available), filtering out cosmetic commits (e.g., mass code-formatting by Prettier or Black) from the churn calculations.
* **1-Year Sweep:** Rather than parsing the entire history of older repositories, the component limits its churn scan to the past 12 months. This guarantees that metrics reflect recent development activity without wasting resources on older, stable code.
* **Dynamic Halting:** To conserve RAM and CPU, the scanner dynamically halts once it has mapped 50% of the active repository, or hits a hard cap of 5,000 files. In the code the 50% rule applies only to repositories of more than 200 files (a smaller one is read to the end), and the stream also stops after a 15-second timeout (`STREAM_TIMEOUT_SECONDS`), so on a large repository some files have no history in the sweep even when they changed.

## Process Management & Fallbacks

Streaming large Git logs via `subprocess.Popen` can be resource-intensive. If the stream hangs, it can create zombie processes that leak file descriptors. The Chronometer enforces strict resource management:

* **Timeout Controls:** The Git streaming process is bound by two limits: a hard compute timeout (defaulting to 15.0 seconds) and the dynamic file coverage target mentioned above. If either is reached, the loop breaks early.
* **Zombie Process Prevention:** If the stream exits early, the Chronometer terminates the `Popen` process and explicitly clears out `stdout`/`stderr` buffers to prevent OS-level zombie processes. (For example, `stderr` is routed to `DEVNULL` to prevent deadlocks from noisy Git warnings).
* **OS-Level Fallback:** If the repository is not tracked by Git or if `git ls-files` fails, the Chronometer gracefully falls back to standard operating system `stat` calls to check file modification times (`mtime`). This fallback is capped at 25,000 files to protect disk I/O performance.

## Output Metrics

The Chronometer acts as a raw data collection layer. It extracts the following data for the `SignalProcessor` to use in final metric calculations:

* **Stability (Age):** The exact modification time (`mtime`) of each file, along with the repository's minimum and maximum timestamps. This is the time of the file's **last** modification, not its creation (see [File Stability](08-10-file-stability.md)).
* **Raw Churn Frequency:** The total commit count for each file within the historical sweep window (12 months).
* **Ownership Mapping:** A dictionary mapping every author who modified a file to their respective commit counts. This powers downstream ownership entropy and silo risk calculations.

<br><br>

---

### 🌌 Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* 🪐 **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* 🔭 **[Visualize your own repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

## Scans of Historical Commits (As-Of Mode)

Two things decide whether a scan of an old commit carries history values at all:

* **The directory must be a git work tree.** An exported tree (for example a tarball of a commit) has no `.git`, so the Chronometer falls back to neutral values (stability `50.0`, churn `0.0`). Scan a detached `git worktree` of the commit instead.
* **The window must be anchored to the commit, not to today.** The default sweep is "one year before now", which is empty for any commit older than a year. `GITGALAXY_HISTORY_ASOF=1` anchors the window to the checked-out commit's date, streams the whole window and dates out-of-window files by their last ancestor commit, so every history field becomes a deterministic function of the checked-out commit.

## Measured Behavior (exploratory, 2026-11)
> **Research notes:** temporal-crucible, branch `sensor-overhaul`, `docs/sensor-overhaul/` (guide, `sensors/activity.md`, `sensors/tech_debt.md`) and `docs/turn_surface_area.md`. Measurements are exploratory (13 repositories; a 580-repository population sample confirms the descriptive results).

On the history-aware scans of 7 repositories (143 scans, each from a detached worktree with `GITGALAXY_HISTORY_ASOF=1`) the two persisted values reduce to two plain quantities: churn is rank-equivalent to the file's commits in the last 365 days (Spearman 0.96) and stability to the days since the file's last commit (0.97), and the two correlate -0.86 with each other. Details and limits (renames, mechanical sweeps, the 12-month window and the early-halt rules above): [Deep Churn](08-06-deep-churn.md) and [File Stability](08-10-file-stability.md).

## The activity readings (plain units)
Beside the churn and stability inputs, the Chronometer makes a second, complete pass over the year before HEAD's commit time and stores per file the commits in 365 and 90 days, the days since the last change, the number of authors and the top author's share (`file_data.commits_365d`, `commits_90d`, `days_since_last_change`, `authors_365d`, `top_author_share_365d`; NULL = not measured). Unlike the churn pass it has no coverage or time halting, only a commit count (`ACTIVITY_MAX_COMMITS`, `ACTIVITY_DATING_MAX_COMMITS` in `CHRONOMETER_CONFIG`), so it never depends on machine speed. See [Activity Sensor](08-27-activity-sensor.md).

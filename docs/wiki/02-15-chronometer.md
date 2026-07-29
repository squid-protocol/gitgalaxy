# Chronometer (Git History Analysis)

> **File Reference:** [`gitgalaxy/metrics/chronometer.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/chronometer.py)

The Chronometer component measures code churn (frequency of changes) and file stability by analyzing Git history. While the rest of the pipeline performs static analysis on the codebase at a single point in time, the Chronometer provides the historical context required by the Signal Processor to calculate risk exposure metrics.

## Batch Processing Strategy

If the engine queried Git history for every individual file during parallel multiprocessing, it would create a massive I/O bottleneck. 

To ensure high performance, the Chronometer utilizes a **batch caching strategy**. It performs a bulk metadata sweep during initialization, caching the results in internal state maps (`churn_map`, `mtime_map`, `author_map`). When worker threads later request temporal data for a specific file, the retrieval is a fast $O(1)$ memory lookup.

## Commit Boundaries & Historical Sweep

To accurately calculate the age and stability of files, the engine must first establish the boundaries of the repository.

* **Boundary Discovery:** The component queries `git rev-list` and `git log` to find the timestamps of the first commit and the latest commit across the entire project.
* **Cosmetic Commit Filtering:** The Chronometer automatically loads `.git-blame-ignore-revs` (if available), filtering out cosmetic commits (e.g., mass code-formatting by Prettier or Black) from the churn calculations.
* **1-Year Sweep:** Rather than parsing the entire history of older repositories, the component limits its churn scan to the past 12 months. This guarantees that metrics reflect recent development activity without wasting resources on older, stable code.
* **Dynamic Halting:** To conserve RAM and CPU, the scanner dynamically halts once it has mapped 50% of the active repository, or hits a hard cap of 5,000 files.

## Process Management & Fallbacks

Streaming large Git logs via `subprocess.Popen` can be resource-intensive. If the stream hangs, it can create zombie processes that leak file descriptors. The Chronometer enforces strict resource management:

* **Timeout Controls:** The Git streaming process is bound by two limits: a hard compute timeout (defaulting to 15.0 seconds) and the dynamic file coverage target mentioned above. If either is reached, the loop breaks early.
* **Zombie Process Prevention:** If the stream exits early, the Chronometer terminates the `Popen` process and explicitly clears out `stdout`/`stderr` buffers to prevent OS-level zombie processes. (For example, `stderr` is routed to `DEVNULL` to prevent deadlocks from noisy Git warnings).
* **OS-Level Fallback:** If the repository is not tracked by Git or if `git ls-files` fails, the Chronometer gracefully falls back to standard operating system `stat` calls to check file modification times (`mtime`). This fallback is capped at 25,000 files to protect disk I/O performance.

## Output Metrics

The Chronometer acts as a raw data collection layer. It extracts the following data for the `SignalProcessor` to use in final metric calculations:

* **Stability (Age):** The exact modification time (`mtime`) of each file, along with the repository's minimum and maximum timestamps.
* **Raw Churn Frequency:** The total commit count for each file within the historical sweep window.
* **Ownership Mapping:** A dictionary mapping every author who modified a file to their respective commit counts. This powers downstream ownership entropy and silo risk calculations.

<br><br>

---

### 🌌 Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* 🪐 **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* 🔭 **[Visualize your own repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

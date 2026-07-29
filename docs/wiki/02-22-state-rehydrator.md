# The State Rehydrator (Incremental State Restoration)

> **File Reference:** [`gitgalaxy/core/state_rehydrator.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/state_rehydrator.py)

The State Rehydrator (`state_rehydrator.py`) enables efficient incremental scans within Continuous Integration/Continuous Deployment (CI/CD) pipelines. 

Performing full static analysis across large codebases (e.g., 10,000 files) on every single commit introduces unnecessary compute overhead when a pull request only modifies a few files. The State Rehydrator addresses this by loading previously analyzed state from the SQLite database (`_galaxy_graph.sqlite`) into memory (`ram_cache`), restoring the repository baseline without re-parsing unchanged source files.

---

## State Extraction (SQLite to Memory)

When an incremental scan (Delta Scan) is triggered, the Rehydrator bypasses full filesystem ingestion and connects to `_galaxy_graph.sqlite`:

* **Commit Baseline Lookup:** Queries the database to identify the SHA-1 commit hash of the most recent complete analysis.
* **State Reconstruction:** Pulls file telemetry, structural metrics (`file_impact`, `total_loc`, `control_flow_ratio`, `ai_threat_score`), and signature counts from database tables.
* **Memory State Population:** Maps stored database records into an in-memory dictionary (`ram_cache`) structured identically to the full pipeline scan state.

---

## Incremental Analysis Workflow

State rehydration establishes the foundation for high-speed incremental analysis:

1. **Delta Target Identification:** Queries Git to identify files added, modified, or deleted in the target commit. Executes regex parsing and signature extraction exclusively on modified files.
2. **State Dictionary Merge:** Overwrites updated file records inside the rehydrated `ram_cache` dictionary.
3. **Graph Topology Recalculation:** Triggers graph analysis modules (`NetworkRiskSensor`, `SecurityAuditor`) across the merged state. Because network topology (PageRank, blast radius) is globally interconnected, modifying key files recalculates global centrality metrics without re-parsing unmodified source code.

---

## Structural Delta Reporting in CI/CD

Comparing baseline state (restored from SQLite) against modified commit state enables automated CI/CD quality gates based on **Structural Deltas**:

* **Technical Debt Progression:** Measures percentage changes in cumulative risk scores across commits.
* **Blast Radius Escalations:** Identifies changes that shift a module into a system choke point.
* **Security Vulnerability Delta:** Flags newly introduced vulnerabilities (such as unsanitized LLM command execution funnels or malware signature triggers).

CI/CD pipelines enforce automated pull request gates based on objective metric deltas rather than subjective code review.

---

### Powered by GitGalaxy

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic static analysis engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for source code and tools.
* **[Visualize your codebase at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**
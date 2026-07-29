# GitGalaxy Configuration Registry

> **File Reference:** [`gitgalaxy/standards/gitgalaxy_config.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/standards/gitgalaxy_config.py)

The `gitgalaxy_config.py` module serves as the centralized configuration registry for the GitGalaxy static analysis engine. Rather than hardcoding analysis thresholds, stream timeouts, and project-specific parsing rules within individual modules, all global constants and dynamic overrides are centrally defined here.

Centralizing configuration parameters allows engineers to adjust performance, tune security alert sensitivity, and modify Git history evaluation windows without altering the core parsing and analysis pipeline.

## Git History Analysis Configuration (`CHRONOMETER_CONFIG`)

To maintain high throughput during Git history parsing, the configuration defines temporal boundaries and execution limits:

* **`DYNAMIC_WINDOW_MIN_DAYS` (30):** The minimum lookback window in days. Ensures newly created or low-activity repositories establish a baseline volatility metric.
* **`DYNAMIC_WINDOW_MAX_DAYS` (365):** The maximum historical scan limit in days. Prevents performance bottlenecks when parsing extensive commit histories on legacy codebases.
* **`DORMANT_FALLBACK_COMMITS` (500):** The fallback commit count used when no commit events are detected within the dynamic time window.
* **`STREAM_TIMEOUT_SECONDS` (15.0 - 60.0):** The execution timeout for Git log subprocess streams (`Popen`), preventing process hangs and resource leaks.
* **`FALLBACK_SCAN_LIMIT` (25000):** The maximum number of files to process when falling back to filesystem modification time (`mtime`) scans in non-Git environments.

## Repository Overrides (`PROJECT_OVERRIDES`)

Because programming languages and repository structures vary across domains, the `PROJECT_OVERRIDES` registry acts as a dynamic override mechanism for specific codebases.

When scanning customized or non-standard repositories (e.g., low-level OS kernels, build system repositories, or specific frameworks), the analysis pipeline inspects the `PROJECT_OVERRIDES` dictionary prior to execution. It patches the active `LANGUAGE_DEFINITIONS` in memory, allowing regular expression heuristics to accurately parse project-specific patterns without mutating global default rules.

## Metadata and Narrative Context (`PROJECT_STORIES`)

GitGalaxy attaches high-level project metadata and architectural context to analysis outputs. The `PROJECT_STORIES` registry maps repository identifiers to structured metadata definitions.

During output serialization (e.g., via `GPURecorder` or `LLMRecorder`), the engine injects these configuration parameters:
* **Status & Purpose:** High-level project objectives and current health metrics.
* **Architectural Significance:** Context regarding the repository's role within an enterprise ecosystem.
* **Target Artifacts:** Specific files or modules highlighted for primary inspection (e.g., core event loops, key controller classes, or sensitive security boundaries).

## File and Directory Exclusion Filters (`APERTURE_CONFIG`)

While `.gitignore` rules specify version control exclusions, `APERTURE_CONFIG` defines directory and file patterns that should be completely excluded from static analysis. 

The `BLACK_HOLES` set defines standard excluded directories (`node_modules`, `.venv`, `dist`, `__pycache__`, build artifacts) that are skipped during filesystem traversal, dependency resolution, and historical fallbacks to preserve performance and memory efficiency.

---

### Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

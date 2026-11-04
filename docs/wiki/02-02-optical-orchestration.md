---
description: "> **File Reference:** [`gitgalaxy/galaxyscope.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/galaxyscope.py)"
---
# Pipeline Orchestration Framework

> **File Reference:** [`gitgalaxy/galaxyscope.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/galaxyscope.py)

## Engineering Summary
This subsystem is the primary execution engine and process manager for the static analysis framework. It solves the problem of coordinating data ingestion, multi-pass metric evaluations, worker process pools, and serialization exporters in a deterministic sequence. It exists to ensure that all pipeline phases execute reliably, aggregating global repository properties and eliminating non-code noise early. Within the broader system, it functions as the central controller orchestrating GitGalaxy.

## Purpose
To control the flow of codebase artifacts through multi-stage sequential passes, applying dynamic configuration and runtime execution overrides.

## Problem Being Solved
Managing a complex data pipeline requiring parallel execution, dependency resolution, and multi-format serialization requires a robust coordinator to prevent race conditions, memory bloat, and uncontrolled execution times.

## Design
The orchestrator (`Orchestrator.execute_pipeline()` in `galaxyscope.py`) executes a fixed sequence of phases, numbered as in the code:

0. Radar & pre-flight: project config (GuideStar) and the file census (Git index checking, quotas).
1. Workers & IPC extraction: parallel lexical extraction in a process pool (bypassing the GIL).
2. Dependency resolution: the import graph (using an $O(1)$ pre-computed suffix hash map).
3. Structural impact analysis: risk exposures from token counts and Git history.
4. Network topology: import edges, cross-file call and mainframe invocation resolution, then PageRank and Betweenness.
5. Zero-trust guardrails (AI & AppSec): opt-in, runs only with `--ai-guardrails`.
6. Spectral audit: statistical quality audit (50/0 rule, Z-score).
7. Spatial layout (ray-casting Fibonacci packing).
8. Metrics synthesis & forensics.
9. ML threat inference (XGBoost).
10. Ecosystem security audits (X-Ray, supply-chain firewall, API mapper), then threat suppression (10.5) and the CI/CD policy gate (10.6).
11. Global telemetry & metadata locking.
12. Archival & export routing (SQLite, JSON, Markdown, WebGL, SARIF, SBOM).

Dynamic overrides like dialect pre-flight patching and runtime security switches (Zero-Trust Mode) modify policies dynamically.

## Pipeline Integration
Inputs: Codebase artifacts, dynamic configuration overrides, runtime flags.
Outputs: Processed graph state, metadata-locked artifacts, multi-format serialization.
Dependencies: Downstream modules like `aperture.py`, `prism.py`, `detector.py`, `NetworkRiskSensor`.

```mermaid
flowchart LR
    A[Configuration & Git Index] --> B[Orchestrator]
    B --> C[Worker Processes]
    C --> D[Multi-Format Exporters]
```

## Tradeoffs
- **In-Memory Delta Scans**: Chose to rehydrate state into memory for incremental scans to maximize speed, sacrificing memory footprint for rapid re-computation of graph metrics.
- **Timeout Guards vs Completeness**: Enforces a 60-second per-file timeout (a `SIGALRM` fuse, POSIX only) in the worker processes. This sacrifices full completeness on massive or complex files to ensure pipeline liveness and avoid ReDoS.

## Limitations
- Scaling limits based on available memory for graph aggregation phases.
- Heuristic mapping of dependencies may miss dynamic imports.
- ReDoS timeouts will result in skipped files.

## Performance Notes
Utilizes an $O(1)$ pre-computed suffix hash map to resolve import strings to physical paths rapidly. Bypasses the GIL using a `ProcessPoolExecutor`. Pre-warms regex caches to eliminate compilation overhead during map-reduce.

## Future Work
Enhancing the spatial layout algorithms for larger scale codebases and optimizing memory usage during delta rehydration.

## Related Components
- [Pipeline Overview](02-01-pipeline-overview.md)
- [Aperture Filter](02-03-aperture-filter.md)


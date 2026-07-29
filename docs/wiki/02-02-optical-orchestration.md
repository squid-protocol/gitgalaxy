# Pipeline Orchestration Framework

> **File Reference:** [`gitgalaxy/galaxyscope.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/galaxyscope.py)

## Engineering Summary
This subsystem is the primary execution engine and process manager for the static analysis framework. It solves the problem of coordinating data ingestion, multi-pass metric evaluations, worker process pools, and serialization exporters in a deterministic sequence. It exists to ensure that all pipeline phases execute reliably, aggregating global repository properties and eliminating non-code noise early. Within the broader system, it functions as the central controller orchestrating GitGalaxy.

## Purpose
To control the flow of codebase artifacts through multi-stage sequential passes, applying dynamic configuration and runtime execution overrides.

## Problem Being Solved
Managing a complex data pipeline requiring parallel execution, dependency resolution, and multi-format serialization requires a robust coordinator to prevent race conditions, memory bloat, and uncontrolled execution times.

## Design
The orchestrator executes a sequence of operations:
1. Census & validation (Git index checking, quotas).
2. Parallel map-reduce for lexical extraction (bypassing GIL).
3. Dependency graph resolution (using an $O(1)$ pre-computed suffix hash map).
4. Relational aggregation (directory ecosystems, test umbrella).
5. Directed graph topology (PageRank, Betweenness).
6. AI guardrails & AppSec assessment.
7. Statistical quality audit (50/0 rule, Z-score).
8. Spatial layout (ray-casting Fibonacci packing).
9. Metrics synthesis, ML inference, and serialization.

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
- **Timeout Guards vs Completeness**: Enforces a 15-second timeout on worker processes. This sacrifices full completeness on massive or complex files to ensure pipeline liveness and avoid ReDoS.

## Limitations
- Scaling limits based on available memory for graph aggregation phases.
- Heuristic mapping of dependencies may miss dynamic imports.
- ReDoS timeouts will result in skipped files.

## Performance Notes
Utilizes an $O(1)$ pre-computed suffix hash map to resolve import strings to physical paths rapidly. Bypasses the GIL using a `ProcessPoolExecutor`. Pre-warms regex caches to eliminate compilation overhead during map-reduce.

## Future Work
Enhancing the spatial layout algorithms for larger scale codebases and optimizing memory usage during delta rehydration.

## Related Components
- [Pipeline Overview](file:///home/joe/nyx_projects/gitgalaxy/docs/wiki/02-01-pipeline-overview.md)
- [Aperture Filter](file:///home/joe/nyx_projects/gitgalaxy/docs/wiki/02-03-aperture-filter.md)


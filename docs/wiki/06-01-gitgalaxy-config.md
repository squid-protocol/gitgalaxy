# GitGalaxy Configuration Registry

> **File Reference:** [`gitgalaxy/standards/gitgalaxy_config.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/standards/gitgalaxy_config.py)

## Engineering Summary
A centralized configuration module manages global constants and dynamic overrides for static analysis. It solves the problem of hardcoded configuration drift by decoupling analysis thresholds, stream timeouts, and project-specific parsing rules from the core execution logic. This subsystem provides a single source of truth for tuning execution parameters without mutating the underlying analysis pipeline, operating as the `gitgalaxy_config` within GitGalaxy.

## Purpose
To provide a centralized configuration interface for static analysis parameters, ensuring consistent execution across diverse repository structures.

## Problem Being Solved
Hardcoding parameters like lookback windows or timeout limits directly within parsing functions creates brittle architectures that fail on non-standard repositories. This registry prevents configuration fragmentation and allows environment-specific tuning.

## Design
The configuration is structured into distinct registries:
- `CHRONOMETER_CONFIG`: Sets temporal boundaries for Git history parsing (e.g., 30-day minimum, 365-day maximum lookback).
- `PROJECT_OVERRIDES`: Patches `LANGUAGE_DEFINITIONS` in memory for domain-specific codebases (e.g., OS kernels).
- `PROJECT_STORIES`: Maps repository identifiers to architectural metadata.
- `APERTURE_CONFIG`: Defines file and directory exclusion patterns (e.g., `node_modules`).

## Pipeline Integration
- **Inputs**: Environment variables or runtime flags defining the target repository.
- **Outputs**: In-memory configuration dictionaries used by the analysis engine.
- **Dependencies**: Relies on Python dictionary structures; consumed by the Git parser, AST heuristics, and metadata exporters.
```text
Runtime Environment -> GitGalaxy Configuration Registry -> Parsing and Analysis Pipeline
```

## Tradeoffs
Centralized configuration requires loading all potential overrides into memory at startup, increasing initial memory footprint marginally. This was chosen over file-based config parsing (like YAML) to avoid I/O bottlenecks during high-throughput analysis passes.

## Limitations
- Changes to configuration require restarting the analysis engine.
- `PROJECT_OVERRIDES` rely on predefined keys and cannot infer structural exceptions dynamically.

## Performance Notes
Startup initialization is $O(1)$ memory lookup since configurations are evaluated as static Python dictionaries, avoiding runtime disk reads.

## Future Work
- Implement hot-reloading for configurations during long-running streaming analysis.
- Migrate static dictionary overrides to a validated data-class schema.

## Related Components
- [Language Standards Registry](06-02-language-standards.md)
- [Analysis Lens & Schema Registry](06-03-analysis-lens.md)

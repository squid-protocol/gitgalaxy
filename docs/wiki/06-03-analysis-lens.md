# Analysis Lens & Schema Registry

> **File Reference:** [`gitgalaxy/standards/analysis_lens.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/standards/analysis_lens.py)

## Engineering Summary
Mathematical schemas and normalization formulas for extracted source code metrics form the core of this module. It solves the problem of standardizing disparate telemetry data by flattening object-oriented syntax counts into contiguous numerical arrays. This subsystem transforms raw syntax hits into calculated risk vectors and visual attributes, acting as the mathematical normalization layer for GitGalaxy.

## Purpose
To enforce strict schema layouts for metric vectors and apply standardized mathematical thresholds for security and risk evaluation.

## Problem Being Solved
Exporting raw syntax counts directly to visualization or audit tools creates inconsistent payload structures. This registry normalizes data into contiguous arrays to ensure predictable ingestion by WebGL buffers and reporting systems.

## Design
The module defines three core schemas:
- `SIGNAL_SCHEMA`: A 60-point vector aggregating raw syntax heuristics (e.g., branching, memory allocation).
- `RISK_SCHEMA`: An 18-point vector representing normalized risk exposure (e.g., tech debt, secrets risk) on a 0-100 scale.
- `SAT_SCHEMA`: A 10-element array for individual function metadata (e.g., LOC, complexity).
It also includes string translation maps and security thresholds.

## Pipeline Integration
- **Inputs**: Raw syntax counts extracted by the language parser.
- **Outputs**: Flattened schema arrays (60-point, 18-point, 10-point) and mapped UI strings.
- **Dependencies**: Consumes data from `language_standards`; outputs are passed to UI renderers and audit loggers.
```text
Raw Syntax Counts -> Analysis Lens & Schema Registry -> Normalized Risk and Signal Vectors
```

## Tradeoffs
Using contiguous flat arrays for schemas discards hierarchical metadata present in the original source code. This structural loss was accepted to optimize data serialization speed and minimize memory allocation overhead during bulk array processing.

## Limitations
- Fixed-size schemas mean that adding a new metric requires a global schema update and pipeline restart.
- Normalization formulas use static thresholds which may not suit all project risk profiles equally.

## Performance Notes
Contiguous numerical arrays align perfectly with WebGL memory buffers, enabling zero-copy or minimal-copy data transfers to the GPU renderer.

## Future Work
- Enable dynamic schema extensions without requiring core engine restarts.
- Implement machine-learning weights for risk normalization instead of static thresholding.

## Related Components
- [Language Standards Registry](06-02-language-standards.md)
- [GitGalaxy Configuration Registry](06-01-gitgalaxy-config.md)

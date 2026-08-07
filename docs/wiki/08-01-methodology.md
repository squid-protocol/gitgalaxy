# Overview of Methodology & Risk Exposure Index

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/metrics/signal_processor.py)

## Engineering Summary
This subsystem forms the analytical core that translates raw regex heuristic counts into structured risk exposure ratings. It solves the problem of converting massive volumes of static analysis data into actionable, normalized health indicators without manual inspection. It exists to objectively map structural anomalies to a universal risk spectrum. Within GitGalaxy, it processes data across five architectural scopes to generate the primary knowledge graph attributes.

## Purpose
To evaluate source code components against 50+ heuristic metrics and aggregate them into a 5-tier Universal Risk Spectrum across function, class, file, directory, and repository scopes.

## Problem Being Solved
Subjective code quality scores lack consistency and traceability. This subsystem replaces subjective heuristics with deterministic, objective Risk Exposures, enabling engineering teams to identify architectural drift and technical debt algorithmically.

## Design
Evaluates metrics mapping to a 5-tier spectrum (Blue, Cyan, Yellow, Orange, Red). It calculates specific risk domains like Cognitive Load, State Flux, Technical Debt, and Concurrency Exposure. Aggregations use distinct mathematical normalization techniques depending on scope: Count-based (Levels 1-2), Sigmoid Normalized (Level 3), and Mass-Weighted Averages (Levels 4-5). Custom topological scales are employed for structural formatting indicators (e.g., Indentation Consistency).

## Pipeline Integration
- **Inputs:** Raw text parsing heuristic hits and regex counts.
- **Outputs:** Normalized risk scores across five architectural levels.
- **Dependencies:** Integrates downstream from the raw source parser and upstream of the final visualization dataset generation.

Raw Source Parser -> Risk Processor -> Knowledge Graph Database

## Tradeoffs
Relying on deterministic regex patterns instead of deep semantic AST analysis sacrifices deep context awareness for blazing fast processing speeds and broad language support. Mass-weighted averaging at directory levels can occasionally dilute extreme risk spikes from small utility files.

## Limitations
- Regex heuristics cannot detect logic errors or runtime context.
- Aggregation across directory scopes may mask isolated critical vulnerabilities if the overall directory mass is heavily defended.

## Performance Notes
The signal processor utilizes vectorized numpy operations to normalize millions of data points, ensuring near-instant metric tiering scaling at $O(N)$ efficiency for repository size.

## Future Work
- Integration with language server protocols (LSP) to complement heuristic regex data with semantic type awareness.
- Dynamic weighting adjustments based on temporal commit frequency.

## Related Components
- [Sub-Equations](08-02-sub-equations.md)
- [Transforming Regex Counts](08-03-transforming-regex-counts.md)

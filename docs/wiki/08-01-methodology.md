# Overview of Methodology & the Structural Surface Profile

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/metrics/signal_processor.py)

> **⚠️ Naming update ([#2991](https://github.com/squid-protocol/gitgalaxy/issues/2991)).** These 13 per-file vectors were formerly called **"Risk Exposures."** The `risk_` framing claimed a higher value means a higher chance of a defect. The temporal-crucible validation program ([#2982](https://github.com/squid-protocol/gitgalaxy/issues/2982) — ~3,550 pre-registered snapshots across curl and nDPI) tested that claim to exhaustion and found the structural vectors **reduce to file size and do not predict defects** (the size-confound wall, independently reported by [repowise-bench](https://github.com/repowise-dev/repowise)). They have therefore been renamed to the **Structural Surface Profile**: they measure structural **surface area and activity**, which is real and useful for *describing, explaining, and localizing* code — but is **not** a risk score. The legacy `risk_*` names remain as deprecated schema aliases. Full name table and evidence: [`vectors.md`](../vectors.md).

## Engineering Summary
This subsystem forms the analytical core that translates raw regex heuristic counts into a structured **surface profile**. It solves the problem of converting massive volumes of static analysis data into normalized, comparable structural indicators without manual inspection. It exists to objectively map structural constructs to a universal surface-area spectrum. Within GitGalaxy, it processes data across five architectural scopes to generate the primary knowledge graph attributes.

## Purpose
To evaluate source code components against 50+ heuristic metrics and aggregate them into a 5-tier Universal Surface Spectrum across function, class, file, directory, and repository scopes — a description of what each component *contains and does*, not a prediction of where defects are.

## Problem Being Solved
Subjective code descriptions lack consistency and traceability. This subsystem replaces subjective heuristics with deterministic, objective structural-surface measures, enabling engineering teams to characterize architecture, activity, and technical-debt markers algorithmically. (What it deliberately does **not** claim: that a high surface score predicts defects — see the validation note above.)

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

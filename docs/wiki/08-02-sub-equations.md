# Sub-Equations & Scanner Variables

> **File Reference:** [`gitgalaxy/core/detector.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/core/detector.py)

## Engineering Summary
This static analysis extraction subsystem defines the raw regular expression inputs used by the metrics engine. It solves the problem of extracting standardized structural and behavioral indicators from diverse programming languages. It exists to provide a language-agnostic data foundation for risk assessment. In GitGalaxy, this process runs over a strict 5-phase extraction sequence to generate core variables.

## Purpose
To extract a standardized set of regular expression variables (e.g., structural footprints, risk indicators) from raw source files to compute reliable risk and complexity metrics.

## Problem Being Solved
Extracting analytical data from raw text requires a standardized taxonomy. This subsystem categorizes hundreds of regex patterns into unified output variables (like `branch_hits` or `safety_hits`), bridging the gap between raw text and mathematical evaluation.

## Design
Variables are extracted in five phases:
1. **Code Structure:** `branch_hits`, `args_hits`, `linear_hits`, `func_start_hits`.
2. **Risk Indicators:** `safety_hits`, `danger_hits`, `io_hits`, `api_hits`, `flux_hits`.
3. **Domain Identifiers:** `concurrency_hits`, `closures_hits`, `globals_hits`, `import_hits`.
4. **Specialized Debt:** `planned_debt_hits`, `fragile_debt_hits`, `private_info_hits`, `memory_alloc_hits`.
5. **Contextual Counter-Weights:** `telemetry_hits`, `sync_locks_hits`, `encapsulation_hits`, `cleanup_hits`.
All output count variables utilize a `_hits` suffix.

## Pipeline Integration
- **Inputs:** Raw source code strings.
- **Outputs:** Categorized integer counts (scanner variables) per file and function.
- **Dependencies:** Operates as the initial data ingestion layer, feeding directly into the signal processing models.

Source Text -> Scanner Extraction Phase -> Signal Processing Engine

## Tradeoffs
Employing regex for token extraction is significantly faster than lexing and parsing full ASTs, but sacrifices precision. It may count keywords located within comments or strings unless pre-filtered, which is accepted in favor of high-throughput analysis.

## Limitations
- Unable to trace variable scope or lexical lifetime bounds.
- Custom domain-specific macros or aliases will not register against standard regex sets.

## Performance Notes
The extraction uses optimized compiled regex engines running concurrently, achieving $O(L)$ parsing time where $L$ is the number of lines of code.

## Future Work
- Multi-pass string and comment stripping before regex evaluation to eliminate false positives.
- Extensible user-defined regex rulesets for internal corporate standards.

## Related Components
- [Overview of Methodology](08-01-methodology.md)
- [Transforming Regex Counts](08-03-transforming-regex-counts.md)

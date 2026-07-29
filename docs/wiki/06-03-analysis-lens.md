# Analysis Lens & Schema Registry

> **File Reference:** [`gitgalaxy/standards/analysis_lens.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/standards/analysis_lens.py)

The `analysis_lens.py` module defines the mathematical schemas, metric vectors, string translation maps, and security policy thresholds utilized throughout the GitGalaxy static analysis engine. 

While `language_standards.py` defines how to parse syntax across different languages, `analysis_lens.py` defines the mathematical meaning, array schemas, and risk normalization formulas applied to the extracted data.

## Metric Schemas (`RECORDING_SCHEMAS`)

To flatten object-oriented analysis data into contiguous arrays for efficient processing, storage, and WebGL rendering, `analysis_lens.py` defines three primary vector schemas:

### 1. `SIGNAL_SCHEMA` (60-Point Heuristic Vector)
Defines the layout of raw syntax telemetry extracted during file parsing. Extracted regular expression hits are aggregated into this 60-element array, representing raw measures of active logic (e.g., `branch`, `memory_alloc`), structural indicators (e.g., `doc`, dead code markers), and security signals (e.g., `sec_danger`, `sec_io`).

### 2. `RISK_SCHEMA` (18-Point Risk Exposure Vector)
Defines the structure of processed risk exposure metrics computed by `SignalProcessor`. Raw 60-point signal vectors are transformed into 18 standardized risk metrics (e.g., `cognitive_load`, `tech_debt`, `secrets_risk`, `memory_corruption`), with each evaluated file receiving normalized risk scores from 0.0 to 100.0.

### 3. `SAT_SCHEMA` (Function Metadata Array)
Defines the 10-element array structure used to represent individual function definitions within visualization payloads. Encodes function metrics such as Lines of Code (LOC), Control Flow Ratio, estimated algorithmic complexity, and parameter counts.

## Translation Dictionaries

For reporting tools, JSON audits, and LLM integrations, `analysis_lens.py` provides translation mappings from internal telemetry keys to human-readable strings and rendering codes:

* **`FRIENDLY_MAP`:** Translates raw metric keys into human-readable descriptions (e.g., mapping `sec_bitwise_hits` to "Bitwise Operations & Custom XOR Logic").
* **`EXPOSURE_LABELS`:** Formats keys in the 18-point risk vector for audit output (e.g., mapping `secrets_risk` to "Secrets Risk Exposure").
* **`GPU_TEXTURE_LOOKUPS`:** String-interning dictionary that maps functional archetypes (e.g., `io`, `mutation`, `event`, `logic`) to integer identifiers for WebGL shader material rendering.

## Mathematical Constants and Risk Policies

`analysis_lens.py` houses global numerical constants used across risk scoring and network centrality calculations:

* **Dynamic Language Uncertainty Factors:** Weight multipliers applied to dynamically typed or shell scripting languages to reflect runtime unpredictability.
* **Network Centrality Weights:** Defines PageRank and Betweenness Centrality coefficients used to calculate systemic risk and dependency exposure.
* **Security Alert Thresholds:** Defines floating-point cutoff levels (e.g., > 60.0%) that trigger `ELEVATED_SURFACE_RISK` and `CRITICAL_THREATS_DETECTED` status flags in generated security reports.

## Maintainability & Schema Integrity

Centralizing schemas in `analysis_lens.py` ensures consistency across the pipeline. Adding a new analysis metric requires updating the schema definitions in this module, which automatically propagates through the parser, signal processor, export recorders, and visualization components.

---

### Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**


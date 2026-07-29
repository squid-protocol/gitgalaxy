# Overview of Methodology & Risk Exposure Index

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)

> **Core Philosophy: From Raw Source Text to Structural Knowledge Graph**
>
> GitGalaxy measures objective **Risk Exposures** rather than subjective quality scores.
>
> Using deterministic keyword heuristics and regular expression patterns, the analysis engine parses raw source code to construct a comprehensive knowledge graph of the repository. Structural indicators extracted from code files are converted into visual risk heatmaps, enabling engineering teams to identify high-risk modules, architectural drift, and technical debt without manual line-by-line inspection.
>
> **Structural Metric Taxonomy**
>
> GitGalaxy evaluates code components against 50+ individual metrics, aggregating results across function, class, file, directory, and repository scopes.

## The Universal Risk Spectrum

All risk exposure metrics map to a standardized 5-tier color scale:

* 🟦 **Blue:** Very Low Risk Exposure
* 🩵 **Cyan:** Low Risk Exposure
* 🟨 **Yellow:** Moderate Risk Exposure
* 🟧 **Orange:** High Risk Exposure
* 🟥 **Bright Red:** Critical Risk Exposure

## Primary Risk Exposures

The metrics table below details the unified risk exposure calculations applied across each architectural scope:

| Metric | Level 1: Function<br>([Count-based](08-02-sub-equations.md)) | Level 2: Class<br>([Count-based](08-02-sub-equations.md)) | Level 3: File<br>([Sigmoid Normalized](08-03-transforming-regex-counts.md)) | Level 4: Directory<br>(Weighted Avg) | Level 5: Repository<br>(Weighted Avg) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[Cognitive Load](08-05-cognitive-load.md)** | Branch count, state mutations, risk triggers | Sum of function counts + Gini index | Sigmoid normalization + security guardrail filter | Mass-Weighted Avg | Mass-Weighted Avg |
| **[State Flux](08-16-state-flux-exposure.md)** | Variable mutation count, adjusted | Sum of function counts + LCOM | Sigmoid normalization | Mass-Weighted Avg | Mass-Weighted Avg |
| **[Concurrency](08-15-concurrency-exposure.md)** | Async/thread calls minus lock protections | Sum of function counts | Sigmoid normalization | Mass-Weighted Avg | Mass-Weighted Avg |
| **[Technical Debt](08-08-technical-debt.md)** | Engineer inline comments (`TODO`, `HACK`) | Sum of function counts | Sigmoid normalization | Mass-Weighted Avg | Mass-Weighted Avg |
| **[Structural Fortification](08-07-structural-fortification.md)**| Defensive vs attack surface markers | Sum of function counts | Sigmoid normalization with breach floor | Mass-Weighted Avg | Mass-Weighted Avg |
| **[Graveyard](08-13-graveyard-detector.md)** | N/A | N/A | Commented-out dead code lines | Mass-Weighted Avg | Mass-Weighted Avg |
| **[Specification Alignment](08-18-specification-alignment.md)**| Spec-tagged function markers | Sum of spec-tagged function counts | Percentage of entities lacking spec tags | Mass-Weighted Avg | Mass-Weighted Avg |
| **[Indentation Consistency](08-12-civil-war.md)** | N/A | N/A | Ratio of tab vs. space indented lines | Mass-Weighted Avg | Mass-Weighted Avg |
| **[Ownership Entropy](08-04-ownership-entropy.md)** | N/A | N/A | Git author contribution share via Shannon entropy | Mass-Weighted Avg | Mass-Weighted Avg |
| **[Deep Churn](08-06-deep-churn.md)** | N/A | N/A | Commit volume over time via logarithmic scaling | Mass-Weighted Avg | Mass-Weighted Avg |
| **[File Recency Heat](08-10-file-stability.md)**| N/A | N/A | Time delta since last commit | Mass-Weighted Avg | Mass-Weighted Avg |
| **[Verification Risk](08-11-test-coverage.md)**| Unverified execution paths | Sum of function counts | Sigmoid normalization $\times$ test linkage | Mass-Weighted Avg | Mass-Weighted Avg |
| **[Documentation Risk](08-09-documentation-risk.md)**| Missing docstrings and inline docs | Sum of function counts | Sigmoid normalization $\times$ bus factor | Mass-Weighted Avg | Mass-Weighted Avg |
| **[API Exposure](08-14-api-exposure.md)** | Exported and public member count | Sum of public interface members | Export ratio $\times$ surface radius | Mass-Weighted Avg | Mass-Weighted Avg |
| **[Algorithmic DoS Exposure](08-24-Big-O-Detection.md)** | Nested loops with data/network I/O | Sum of function counts | Sigmoid normalization $\times$ blast radius | Mass-Weighted Avg | Mass-Weighted Avg |
| **[Logic Bomb Exposure](08-20-logic-bomb-exposure.md)** | Conditional checks tied to critical payloads | Sum of function counts | Sigmoid normalization $\times$ taint analysis | Mass-Weighted Avg | Mass-Weighted Avg |
| **[Injection Surface Exposure](08-21-injection-surface-exposure.md)**| Unsanitized input pathways | Sum of function counts | Sigmoid normalization $\times$ taint analysis | Mass-Weighted Avg | Mass-Weighted Avg |
| **[Memory Corruption Exposure](08-22-memory-corruption-exposure.md)**| Allocation counts minus deallocations | Sum of function counts | Sigmoid normalization $\times$ static analysis model | Mass-Weighted Avg | Mass-Weighted Avg |
| **[Obscured Payload Exposure](08-19-obscured-payload-exposure.md)**| Obfuscated strings and dynamic execution | Sum of function counts | Sigmoid normalization $\times$ entropy drift | Mass-Weighted Avg | Mass-Weighted Avg |
| **[Hardcoded Secrets Exposure](08-23-hardcoded-secrets-exposure.md)**| N/A | N/A | Hardcoded credential patterns | Mass-Weighted Avg | Mass-Weighted Avg |

## Custom Topological Scales

Certain metrics measure structural formatting styles rather than risk progression. These bypass the standard risk spectrum and use custom indicator palettes:

* **Indentation Consistency (Tabs vs. Spaces):**
  * 🟩 **Green:** Strict Tab Indentation
  * 🟨 **Yellow:** Strict Space Indentation
  * 🟦 **Blue:** Mixed Indentation Patterns ("Inconsistent Whitespace")

---

## Static Analysis Framework Reference

The following documents define the extracted variables and mathematical normalization pipelines powering these metrics:

* [08-02: Sub-Equations & Scanner Variables](08-02-sub-equations.md)
* [08-03: Transforming Regex Counts (Universal Exposure Framework)](08-03-transforming-regex-counts.md)

<br><br>

---

### Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**
️ Back to Master Index](index.md)**
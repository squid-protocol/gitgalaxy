# Verification Risk Exposure (Test Coverage)

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)
>
> **Metric:** Logic Complexity vs. Defensive Test Verification
>
> **Summary:** Measures verification risk by assessing code complexity and structural impact against internal assertions and external test coverage. Rather than relying on simple line-count coverage, GitGalaxy computes residual **Untested Impact** at the function, class, file, directory, and repository levels.
>
> **Effect:** Maps directly to the GitGalaxy Universal Risk Spectrum:
> * 🟦 **VERY LOW (Score 0-19):** High Verification. Functions are heavily covered by targeted unit tests or snapshot assertions.
> * 🟨 **INTERMEDIATE (Score 40-59):** Moderate Exposure. Core paths have basic tests, but some functions lack sufficient defensive assertions.
> * 🟥 **VERY HIGH (Score 80-100+):** Unverified Execution. Complex functions and files operate with minimal or zero test verification.

## Multi-Level Verification Hierarchy

Verification risk is calculated across five structural levels:

### Level 1: Function Level (Untested Impact)

Starting with the raw structural impact score of a function, the engine reduces risk based on defensive assertions targeting that function:

#### Step A: Base Impact Calculation
Internal defenses within the function boundary are evaluated using three schema elements:
* **Verification (`test`):** Inline assertions (`assert()`, `expect()`).
* **Safety Controls (`safety`):** Guard clauses and type guards (`require()`).
* **Bypassed Tests (`test_skip`):** Negative modifier subtracting defensive mass for explicitly skipped tests (`it.skip`).

$$\text{BaseImpact} = \max(\text{FunctionImpact} - ((\text{Verification} + \text{Safety} - (\text{Bypassed} \times 2.0)) \times Fc), 0.0)$$

#### Step B: Defensive Ratio & Test Impact
External test suites targeting the function contribute to `EffectiveTestImpact`. External tests must contain active assertions (zero assertion tests yield zero defensive weight) and must not be marked as skipped. The defensive ratio dilutes integration tests targeting multiple functions:

$$\text{DefensiveRatio} = \frac{\sum (\text{EffectiveTestImpact} / \text{TargetCount})}{\text{FunctionImpact}}$$

#### Step C: Asymptotic Risk Decay
The `DefensiveRatio` feeds into an inverse decay formula to calculate residual **Untested Impact**:

$$\text{UntestedImpact} = \text{BaseImpact} \times \left( \frac{1}{1 + (C_t \times \text{DefensiveRatio})} \right)$$

---

### Level 2: Class Level (Aggregation Boundary)

Classes act as containment boundaries. The class score sums residual Untested Impact from all encapsulated methods:

$$\text{ClassUntestedImpact} = \sum \text{FunctionUntestedImpact}$$

---

### Level 3: File Level (Normalized Risk Score: 0 - 100)

File-level calculations normalize untested impact per executable line of code, applying ecosystem modifiers and a Sigmoidal curve:

#### Step A: Executable Density Normalization
Total untested impact is divided by `CodingLOC` (total lines minus comments and whitespace) and scaled by the language Opacity Tax ($Ot$):

$$\text{RawDensity} = \left( \frac{\sum \text{ClassUntestedImpact}}{\max(\text{CodingLOC}, 1)} \right) \times Ot$$

#### Step B: Ecosystem Modifiers
Density is adjusted based on directory-level snapshot test dampeners (`DirectoryTestDampener`) and PageRank centrality (`BlastRadius`):

$$\text{AdjustedDensity} = (\text{RawDensity} \times \text{DirectoryTestDampener}) \times \text{BlastRadius}$$

#### Step C: Sigmoidal Normalization
Adjusted density maps to a 0–100 score using a logistic Sigmoid function:

$$\text{BaseScore} = \min\left( \frac{100.0}{1 + e^{-\text{Slope} \times (\text{AdjustedDensity} - \text{Threshold})}}, 100.0 \right)$$

#### Step D: Path Modifiers & Breach Floor
Test files (`.spec.js`, `tests/`) receive $Mp = 0.0$ to zero out risk. For production code ($Mp = 1.0$), a Breach Floor ensures heavily untested complex files maintain a minimum risk rating.

$$\text{FinalFileScore} = \text{BaseScore} \times Mp$$

---

### Level 4: Directory Level (Mass-Weighted Aggregation)

Directory verification risk is calculated as a mass-weighted average using `CodingLOC` of each child file. A large, complex module scoring 95 will pull the folder aggregate significantly, whereas a tiny untested 15-line script will not distort local metrics.

---

### Level 5: Repository Level (Global System Risk)

Repository verification risk is computed as a mass-weighted average across all top-level directories. Highly complex core modules drag down global verification scores, whereas lightweight experimental folders are absorbed proportionally.

---

### Powered by GitGalaxy Engine

This documentation is part of the [GitGalaxy Project](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free static analysis engine for automated codebase risk auditing.

**[⬅️ Back to Master Index](index.md)**
# Cognitive Load Exposure

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)
>
> **Metric:** Density of Decision-Making & Logic Complexity
>
> **Summary:** Measures the mental overhead required for a developer to understand a source file. Unlike raw line count (which measures volume), Cognitive Load evaluates decision density, state mutations, temporal complexity, reflection, and unsafe execution markers per line of code. High cognitive load highlights complex or tangled logic requiring focus, while clear documentation acts as a mitigating factor.
>
> **Effect:** Maps directly to the GitGalaxy Universal Risk Spectrum, scaling from 🟦 **Deep Blue** (linear, straightforward code) to 🟥 **Intense Red** (dense, multi-state async logic).

## Architectural Overview

Human working memory has finite capacity. When reading source code, nested conditionals, dynamic state mutations, concurrency, and reflection require developers to mentally track multiple states simultaneously.

In GitGalaxy, cognitive load measures logic friction while treating structured documentation as mitigation:

* **Low Cognitive Load (0 - 39):** Linear, predictable execution paths with low mental overhead.
* **Moderate Cognitive Load (40 - 59):** Standard business or algorithmic logic operating within normal parameters.
* **High Cognitive Load (60 - 100):** Dense, multi-branch or asynchronous logic requiring intensive focus and careful review.

## Metric Inputs & Heuristics

The Signal Processor evaluates pre-calculated heuristic counts from the static analysis engine, weighting them based on mental tax:

| Input Variable | Metric Focus | Multiplier | Clamp Limit | Description |
| :--- | :--- | :--- | :--- | :--- |
| `branch` | Decision Density | 1.0x | 0.5 / line | Baseline conditional branching (`if`/`else`, `switch`). Clamped to handle flat switch blocks smoothly. |
| `state_mutation` | State Flux | 2.0x | 0.75 / line | Variable mutations and state reassignment taxing short-term memory. |
| `concurrency` | Temporal Complexity | 3.0x | None | Asynchronous code, promises, and goroutines that create non-linear control flow. |
| `reflection_metaprogramming` | Abstraction Penalty | 5.0x | None | Dynamic dispatch, reflection, macros, and metaprogramming hiding explicit logic paths. |
| `high_risk_execution` | Unsafe Operations | 5.0x | None | Unsafe memory access, `eval`, or dynamic code execution forcing manual verification. |
| `doc` | Documentation Mitigation | 10.0x | None | Structured inline comments and docstrings providing context (acts as a cooling factor). |

## Universal Framework Integration

Standard environmental parameters adjust the metric across language families and project paths:

* **$Irc$ (Implicit Risk Correction):** Added to total density to account for baseline syntactical opacity in implicit languages (e.g., Shell, Perl).
* **$Fc$ (Fidelity Coefficient):** Scales the documentation mitigation factor based on language type expliciteness (e.g., trusting Java docstrings over implicit scripting comments).
* **$Mp$ (Path Modifier):** Contextual multiplier based on directory location (e.g., dampening UI framework load, amplifying core database logic).

## Mathematical Formulation

Cognitive load calculation follows four primary steps:

### Step 1: Calculate Clamped Line Densities
Per-line densities for branches and state mutations are computed and clamped:

$$\text{BranchDensity} = \min\left(\frac{\text{branch}}{\text{LOC}}, 0.5\right)$$
$$\text{FluxDensity} = \min\left(\frac{\text{state\_mutation}}{\text{LOC}} \times 2.0, 0.75\right)$$

### Step 2: Sum Heavy Logic & Apply Gini Coefficient
Heavy logic multipliers (concurrency, reflection, unsafe code) and baseline opacity ($Irc$) are aggregated. If function complexity is heavily concentrated in a single function (high Gini coefficient $> 0.7$), a Gini penalty multiplier is applied:

$$\text{HeavyLogic} = (\text{concurrency} \times 3.0) + (\text{reflection} \times 5.0) + (\text{unsafe} \times 5.0)$$
$$\text{TotalDensity} = \left(\text{BranchDensity} + \text{FluxDensity} + \frac{\text{HeavyLogic}}{\text{LOC}} + \frac{Irc}{\text{LOC}}\right) \times \text{GiniMultiplier}$$

### Step 3: Map Through Sigmoid Curve
The total density is mapped onto a 0–100 scale using a logistic Sigmoid function (offset $= 0.75$, slope $= 4.0$):

$$\text{RawScore} = \frac{100}{1 + e^{-4.0 \times (\text{TotalDensity} - 0.75)}}$$

### Step 4: Apply Documentation Mitigation & Path Modifier
Documentation coverage reduces the raw risk score by up to 50%, scaled by the Fidelity Coefficient ($Fc$) and Path Modifier ($Mp$):

$$\text{DocCoverage} = \frac{\text{doc} \times 10.0}{\text{LOC}}$$
$$\text{CoolingFactor} = \max\left(0.5, 1.0 - (\text{DocCoverage} \times Fc)\right)$$
$$\text{FinalScore} = \min(\text{RawScore} \times \text{CoolingFactor} \times Mp, 100)$$

## Risk Level Interpretation

| Score Range | Color Code | Risk Rating | Architectural Description |
| :--- | :--- | :--- | :--- |
| **0 - 19** | 🟦 **Deep Blue** | **Very Low** | Flat data structures, configuration files, and simple linear code. |
| **20 - 39** | 🩵 **Cyan** | **Low** | Standard UI components or simple utility functions with minimal branching. |
| **40 - 59** | 🟨 **Yellow** | **Moderate** | Standard application logic and core algorithms operating within expected parameters. |
| **60 - 89** | 🟧 **Orange** | **High** | Complex operational code featuring nested branching and state mutations. |
| **90 - 100** | 🟥 **Bright Red** | **Very High** | Highly complex metaprogramming, async pipelines, or unsafe execution blocks. |

---

### Powered by GitGalaxy Engine

This documentation is part of the [GitGalaxy Project](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free static analysis engine for automated codebase risk auditing.

**[⬅️ Back to Master Index](index.md)**

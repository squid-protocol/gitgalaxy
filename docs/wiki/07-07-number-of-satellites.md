# 2.1.F. Child Component Density & Function Complexity

> **File Reference:** [`gitgalaxy/core/detector.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/detector.py)

> **Metric: Extended Cyclomatic Complexity**
>
> **Purpose:** Measures and visualizes logic complexity within individual functions. High cognitive load manifests as elevated structural branching and child component density.
> 
> **Input:** $C$ (Composite Complexity Score).
> 
> **Effect:** Determines the number of child function nodes rendered around a primary module in 3D layout space.

## 2.1.F.1. Cognitive Friction in Static Analysis

Compilers process nested conditional branches and error handling rapidly, but humans face strict limits on working memory. Every `if` condition, loop, or try-catch block introduces cognitive overhead by requiring developers to track multiple execution branches in parallel.

In GitGalaxy, this cognitive friction is mapped directly to structural visual density. A linear sequence of calls forms a streamlined path, whereas a highly nested, defensive function creates a dense cluster of child nodes.

## 2.1.F.2. Input Metrics: Structural vs. Defensive Logic

The parser calculates function complexity by examining two primary categories of code patterns:

**A. Structural Complexity (Decision Points)**
* **Definition:** Direct branching points in program execution. Each split increases cyclomatic complexity.
* **Source Metric:** `BranchHits` (extracted by the static analyzer).
* **Triggers:** `if`, `else`, `for`, `while`, `switch`, logical operators (`&&`, `||`), and ternary expressions (`?`).

**B. Defensive Overhead (Guard Logic)**
* **Definition:** Code dedicated to exception handling, assertion checks, and input validation. Defensive logic increases code volume and reading friction even when execution pathways remain stable.
* **Source Metric:** `SafetyHits`.
* **Triggers:** `try`, `catch`, `finally`, `assert`, `guard`, `validate`.

## 2.1.F.3. Mathematical Formulation: Composite Score ($C$)

The **Composite Complexity Score ($C$)** combines structural decision points with weighted defensive overhead. Defensive hits carry a 0.5 weight factor because guard conditions consume roughly half the cognitive overhead of full control flow forks.

**Step 1: Structural Component**
$$\text{Structural} = \text{BranchHits}$$

**Step 2: Defensive Component**
$$\text{Defensive} = \text{SafetyHits} \times 0.5$$

**Step 3: Composite Summation**
$$C = \text{Structural} + \text{Defensive}$$

## 2.1.F.4. Complexity Tiers and Visual Mapping

The composite complexity score $C$ is mapped to structural Tiers and child node counts in the 3D visualization plane:

| Complexity Score ($C$) | Structural Depth Tier | Classification | Visual Mapping | Code Characteristics |
| :--- | :--- | :--- | :--- | :--- |
| **$\le 2$** | **0** | **Linear** | Single node with 0–1 child nodes | Sequential instructions with minimal branching. |
| **> 2** | **1** | **Simple Branch** | Primary node with 1–2 child nodes | Basic function with simple conditional checks. |
| **> 8** | **2** | **Nested Tree** | Branching structure with 3–4 child nodes | Standard business logic containing nested loops and conditions. |
| **> 15** | **3** | **High Density** | Dense cluster of child nodes | Complex algorithmic routines, state machines, or legacy parsers. |
| **> 25** | **4** | **Monolithic Thicket** | Heavy multi-node cluster | High-risk components, large switch statements, or deep recursion. |

<br><br>

---

### Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**


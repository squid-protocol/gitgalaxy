# 2.1.H. Function Component Node Scaling

> **File Reference:** [`gitgalaxy/core/detector.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/detector.py)

> **Metric: Parameter Count (`Args`)**
>
> **Purpose:** Visualizes parameter mass and I/O signature complexity of individual functions.
>
> **Rationale:** Functions accepting numerous arguments frequently carry high state complexity or tight parameter coupling. Compact utility functions typically require 1–2 parameters, whereas legacy controllers or un-factored methods often accept 8 or more parameters. Modulating component scale highlights parameter footprint visually across the codebase graph.
>
> **Effect:** Controls the physical render scale (Radius) of function nodes in 3D layout space.

## 2.1.H.1. Parameter Mass and Coupling Density

The parser evaluates parameter signatures as input context vectors:

* **Compact Signatures (0–2 parameters):** Highly encapsulated, modular, and easy to isolate or test.
* **Complex Signatures (5+ parameters):** Heavy parameter coupling, high context overhead, and potential candidates for refactoring into parameter objects or configuration options.

## 2.1.H.2. Input Metrics

* **`Args`:** The total count of positional and keyword parameters detected in the function definition header by the static analyzer.
* **Range:** $0$ to $20+$ parameters.

## 2.1.H.3. Logarithmic Scaling Formulation

To prevent functions with exceptionally high parameter counts (e.g., 20+ args) from generating oversized, viewport-cluttering visual nodes, the layout engine applies logarithmic scaling. Logarithmic compression highlights meaningful variations between 0 and 5 parameters while dampening size growth across higher values.

$$\text{Scale} = 1.0 + \left( \log_2(\max(\text{Args}, 1)) \times 0.2 \right)$$

* **Base Scale:** $1.0$ (Standard visual unit).
* **Scaling Multiplier:** $0.2$ (Controlled logarithmic growth factor).

## 2.1.H.4. Visual Output and Node Scale Tiers

The calculated scale factor directly adjusts the 3D geometry bounds of rendered function components:

| Parameter Count (`Args`) | Calculated Scale | Node Category | Software Architecture Implication |
| :--- | :--- | :--- | :--- |
| **0 – 1 Args** | $1.00$ | **Compact Node** | Minimal parameter overhead; modular utility function. |
| **2 – 4 Args** | $\sim 1.20 - 1.40$ | **Standard Node** | Standard business logic with expected operational state. |
| **5 – 10 Args** | $\sim 1.46 - 1.66$ | **Heavy Node** | Elevated parameter mass; high I/O binding. |
| **15+ Args** | $\sim 1.78+$ | **Monolithic Node** | Excessive parameter coupling; high refactoring priority. |

<br><br>

---

### Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**


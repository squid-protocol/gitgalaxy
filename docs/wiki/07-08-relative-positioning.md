# 2.1.G. Angular Positioning of Child Nodes in Function Units

> **File Reference:** [`gitgalaxy/core/spatial_mapper.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/spatial_mapper.py)

> **Metric: Control Flow Ratio ($R_L$)**
>
> **Purpose:** Configures the spatial angular distribution of sub-nodes within a function unit based on its ratio of control flow logic statements to declarative statements.
>
> **Rationale:** Providing uniform visual spacing across all code blocks obscures structural behavioral differences. By modulating layout angles based on code composition, the visualization engine allows developers to quickly differentiate algorithmic routing logic from declarative structures.
>
> **Effect:** Controls the divergence angles of child nodes in the 3D rendering space.

## 2.1.G.1. Categorization: Algorithmic Logic vs. Declarative Structure

Source code statements are divided into two fundamental operational categories:

* **Algorithmic Logic (Conditional Branching):** Operations that direct execution paths based on dynamic states (e.g., conditional checks and iteration loops). Functions dominated by algorithmic logic split into tighter, acute visual divergence angles.
* **Declarative Structure (Data & Configuration):** Statements that define static data, import references, or assign constants. Functions dominated by declarative declarations split into wide, right-angle layout grids.

## 2.1.G.2. Linear Interpolation (Lerp) Mapping

The static analysis engine computes the Control Flow Ratio ($R_L$) as:

$$R_L = \frac{\text{BranchHits}}{\text{BranchHits} + \text{LinearHits}}$$

The 3D layout engine maps $R_L$ to an angular divergence range between $22.5^\circ$ (sharp divergence) and $90.0^\circ$ (orthogonal layout) using linear interpolation:

$$\text{Angle} = 22.5^\circ + \left( (1.0 - R_L) \times (90.0^\circ - 22.5^\circ) \right)$$

## 2.1.G.3. Structural Archetypes

The resulting divergence angle determines the visual arrangement of child nodes in 3D space:

| Control Flow Ratio ($R_L$) | Divergence Angle | Layout Pattern | Visual Characteristics | Code Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **High Logic** ($R_L \approx 1.0$) | $\approx 22.5^\circ$ | **Acute Branching** | Tightly grouped, acute divergence pathways | Heavy decision logic, complex routing algorithms, state evaluation routines. |
| **High Structure** ($R_L \approx 0.0$) | $\approx 90.0^\circ$ | **Orthogonal Grid** | Standard right-angle grid layout | Declarative data structures, configuration maps, constant definitions. |

<br><br>

---

### Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**


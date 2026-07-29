# 2.1.K Component Layout Clearance Formulas

> **File Reference:** [`gitgalaxy/core/spatial_mapper.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/spatial_mapper.py)

> **Metric: Component Orbital Clearance Radius**
>
> **Purpose:** Dynamically computes child node orbital distances relative to parent file size.
>
> **Rationale:** High-LOC modules occupy larger visual bounds in 3D space. Calculating a dynamic clearance boundary prevents child component nodes from colliding with or rendering inside parent file nodes.
>
> **Effect:** Maintains structural visibility across large modules in the 3D graph view.

## 2.1.K.1 Dynamic Clearance Formulation

The spatial mapper calculates the child node orbit radius ($\text{OrbitRadius}$) as a function of the parent module's lines of code ($\text{LOC}$):

$$\text{OrbitRadius} = 40 + \left( \log_2(\text{LOC}) \times 10 \right)$$

* **Base Radius:** $40$ units (Minimum clearance radius for small files).
* **LOC Scaling:** $\log_2(\text{LOC}) \times 10$ (Logarithmic expansion ensuring large monoliths expand spatial clearance without pushing child nodes out of view).

<br><br>

---

### Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**


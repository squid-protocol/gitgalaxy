# Function Sub-Node Units & Impact Ranking

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)

In GitGalaxy's 3D visualization, individual function declarations (e.g., `def`, `function`, class methods, arrow functions) are materialized as child sub-nodes orbiting their parent file node. This provides an instant visual inventory of a file's internal modularity and function count.

## Default Sub-Node Rendering Attributes

Each function sub-node initializes with the following default properties before complexity and line-count metrics are applied:

| Render Property | Default Setting | Technical Purpose |
| :--- | :--- | :--- |
| **Geometry Primitive** | `SphereGeometry(2, 4, 4)` | Renders as a low-polygon spherical mesh. |
| **Base Radius** | 2 Units | Establishes uniform baseline dimensions. |
| **Color Palette** | Inherits Parent Node Color | Maintains visual cohesion with the enclosing file module. |
| **Material Opacity** | 0.8 | Subtly translucent to denote child-to-parent hierarchy. |
| **Orbital Path** | Uniform Angular Velocity | Rotates smoothly around the parent node center. |

## Function Impact Ranking and Display Capping

Files frequently contain dozens or hundreds of internal functions. To maintain rendering performance and prevent visual clutter, the 3D visualizer caps rendering at a maximum sample of 12 child sub-nodes per file, prioritizing functions with the highest **Function Impact Score**.

The engine combines decision density (`BranchHits`), parameter coupling (`Args`), and line length (`LOC`) into a single weighted score:

$$\text{Impact Score} = \left( (\text{BranchHits} + 1) \times (\text{Args} + 1) + (0.05 \times \text{LOC}) \right) \times 10$$

### Metric Components:
* **`BranchHits`:** Decision points (`if`, `switch`, loops) within the function boundary.
* **`Args`:** Function parameter count, measuring input coupling.
* **`LOC`:** Physical line count of the function (scaled by $0.05$ to prioritize branching logic over verbose formatting).
* **Multiplier (10):** Integer scaling factor for storage efficiency in vectorized output buffers.

---

### Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**


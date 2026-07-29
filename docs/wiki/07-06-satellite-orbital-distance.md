# Sub-Node Orbital Distance & Logarithmic Scaling

> **File Reference:** [`gitgalaxy/recorders/gpu_recorder.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/recorders/gpu_recorder.py)

In GitGalaxy's WebGL visualization engine, the **Orbital Radius** (3D distance of a function sub-node from its parent file node) is determined by the function's physical line count (Lines of Code / LOC). 

Visualizing function length through orbital distance allows developers to identify oversized or bloated methods at a glance without expanding text views.

## Logarithmic Distance Scaling

Functions within a repository vary widely in length, ranging from concise 5-line accessors to multi-thousand-line legacy methods. 

Linear mapping of line count to 3D spatial distance would push long functions far outside the camera's viewport frustum. To maintain a coherent scene layout while representing broad metric ranges, the engine applies base-2 logarithmic scaling.

A baseline clearance distance of 60 units prevents child sub-nodes from intersecting the parent node's mesh geometry.

## Mathematical Distance Formula

$$\text{Orbital Radius} = 60 + \left( \log_2(\max(\text{LOC}, 1)) \times 30 \right)$$

* **Base Clearance Offset (60 Units):** Minimum spatial clearance to ensure sub-node geometry clears the parent node mesh.
* **Logarithmic Term ($\log_2(\text{LOC})$):** Compresses line count variation into manageable spatial increments.
* **Spread Multiplier (30 Units):** Scales log-compressed values across renderable 3D coordinate space.

## Distance Scale Representative Thresholds

| Function Length (LOC) | Computed Orbital Radius | Visual Representation |
| :--- | :--- | :--- |
| **10 LOC** | ~160 units | **Concise Function / Stub:** Orbits close to parent node surface. |
| **100 LOC** | ~260 units | **Standard Method:** Maintains standard orbital distance. |
| **1,000 LOC** | ~360 units | **Large Method:** Orbits at a noticeably extended distance. |
| **100,000 LOC** | ~560 units | **Monolithic Function:** Extended distance capped near viewport limit. |

---

### Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**


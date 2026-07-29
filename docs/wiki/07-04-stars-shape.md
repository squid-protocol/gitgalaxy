# Node Geometry & Control Flow Ratio Mapping

> **File Reference:** [`gitgalaxy/recorders/gpu_recorder.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/recorders/gpu_recorder.py)

GitGalaxy morphs node mesh geometry in the 3D visualizer based on a file's **Control Flow Ratio** ($R_L$). This geometric transformation distinguishes declarative, data-structure code (smooth sphere primitives) from complex algorithmic code (sharp polyhedral wireframes) at a glance.

## Heuristic Inputs and Categorization

Extracted regular expression hits are classified into two structural buckets:

1. **Branch Hits (`BranchHits`):** Measures decision points and control flow complexity. Matches keywords such as `if`, `else`, `switch`, `case`, `for`, `while`, `catch`, logical operators (`&&`, `||`), and ternary operators (`?`).
2. **Linear Hits (`LinearHits`):** Measures structural declarations and data definitions. Matches keywords such as `const`, `let`, `return`, `import`, `export`, `class`, `interface`, and `type`.

## Control Flow Ratio Formula

The **Control Flow Ratio** ($R_L$) represents the proportion of total syntax hits dedicated to decision branching:

$$\text{TotalFlow} = \text{BranchHits} + \text{LinearHits}$$

$$R_L = \frac{\text{BranchHits}}{\text{TotalFlow}}$$

* **$R_L = 0.0$:** Purely declarative code (e.g., JSON schemas, TypeScript interfaces, configuration files).
* **$R_L = 0.5$:** Balanced application business logic (e.g., standard controllers and services).
* **$R_L = 1.0$:** Pure decision-dense logic (e.g., parsing state machines, mathematical utilities, or recursive algorithms).

## Geometric Morphing Thresholds

Based on $R_L$, the WebGL visualizer selects one of five `BufferGeometry` mesh primitives:

| Control Flow Ratio ($R_L$) | 3D Mesh Geometry | Rendering Style | Code Structural Archetype |
| :--- | :--- | :--- | :--- |
| **0.00 - 0.59** | **Sphere** | Solid Emissive Surface | Data structures, schemas, and static configuration files. |
| **0.60 - 0.69** | **Icosahedron** | 20-Faceted Wireframe Mesh | Mostly declarative class modules and lightweight utilities. |
| **0.70 - 0.79** | **Dodecahedron** | 12-Faceted Wireframe Mesh | Balanced application business logic. |
| **0.80 - 0.89** | **Octahedron** | 8-Faceted Wireframe Mesh | Algorithmic modules with high decision density. |
| **0.90 - 1.00** | **Tetrahedron** | 4-Faceted Sharp Wireframe | Complex control flow, recursive routines, and state machines. |

## Material & Shading Behavior

* **Declarative Code ($R_L < 0.60$):** Rendered with smooth emissive shading, representing stable, non-branching data structures.
* **Algorithmic Code ($R_L \ge 0.60$):** Rendered as polyhedral wireframe meshes. Facets and sharp edges become visible, visually highlighting high decision complexity and control-flow density.

---

### Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**


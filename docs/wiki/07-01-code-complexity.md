# Visual Code Complexity Mapping Specifications

> **File Reference:** [`gitgalaxy/recorders/gpu_recorder.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/recorders/gpu_recorder.py)

GitGalaxy maps static code metrics directly to 3D visual parameters in WebGL/WebGPU. Rather than relying exclusively on color coding, the visualization engine converts code complexity, file size, dependency relationships, and control flow density into distinct geometric shapes, spatial positioning, and orbital sub-node layouts.

| Visual Attribute | Source Metric (Heuristic) | Visual Output & Rendering Behavior |
| :--- | :--- | :--- |
| **File Node Scale** | Lines of Code (LOC) & Structural Mass | Logarithmic scaling maps file size and complexity to physical 3D node radius. Large core modules appear as prominent parent nodes, while small utilities remain compact nodes. |
| **Emissive Intensity** | Inbound Reference Count (Graph In-Degree) | Frequently imported core modules emit high-intensity bloom, visually highlighting central architectural bottlenecks. Unreferenced files remain dim and static. |
| **Node Mesh Geometry** | File Control Flow Ratio ($R_L$) | Morphs node geometry from smooth spheres (declarative data files and configs) to sharp polyhedral wireframes (highly complex algorithmic code). |
| **Function Sub-Nodes** | Function / Method Declarations | Discrete functions within a file are rendered as child nodes orbiting the main file node. |
| **Orbital Distance** | Function Lines of Code (LOC) | Function length determines orbital radius. Long functions orbit at a larger radius from the parent node, while concise functions remain tightly bound. |
| **Sub-Node Quantity** | Function Count & Complexity | Reflects the total number and structural density of discrete functions contained within the parent file. |
| **Sub-Node Position** | Function Control Flow Ratio | Branching angles and angular positions reflect the relative decision complexity of individual functions. |
| **Sub-Node Scale** | Function Parameter Count | Functions with large parameter lists and high input coupling render with larger sub-node radii. |
| **Dependency Rings** | External Library Imports | Files with heavy third-party dependencies are rendered with concentric rings surrounding the parent node. |
| **Spatial Clustering** | Directory Path & Module Structure | Files are grouped into 3D spatial sectors based on directory hierarchy (e.g., `auth/`, `ui/`, `api/` modules). |

---

### Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**


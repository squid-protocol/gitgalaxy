# 2.1.J. Spatial Layout & Directory Sector Clustering

> **File Reference:** [`gitgalaxy/core/spatial_mapper.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/spatial_mapper.py)

> **Metric: Semantic Affinity (Directory Hierarchy + Module Type + Coupling Impact)**
>
> **Purpose:** Clusters related source files into distinct 3D directory sectors to produce an intuitive, navigable codebase topology map.
>
> **Rationale:** Ordering nodes purely by sequential discovery or file list order places unrelated modules (e.g., test helpers next to auth controllers) arbitrarily. By sorting and offsetting nodes using folder metadata and architectural role, the layout engine creates clear spatial neighborhoods where components cluster deterministically by directory and file type.
>
> **Effect:** Determines 3D Cartesian coordinates ($X, Y, Z$) for all repository file nodes using a tri-phase layout pipeline.

## 2.1.J.1. The Tri-Phase Spatial Layout Pipeline

Rather than relying on iterative $O(N^2)$ force-directed physics simulations, the spatial engine executes a deterministic **3-Pass Sort & Offset** algorithm. This guarantees that identical repository inputs yield identical, reproducible 3D graph topologies while maintaining clear visual separation between directory clusters.

## 2.1.J.2. Phase 1: Structural Priority Sorting (Impact & Hierarchy)

Before assigning spatial coordinates, the engine re-indexes the module list to position central infrastructure components at the origin of the 3D map:

1. **Primary Key: Inbound Reference Count (Descending)**
   * High-impact central modules and core utilities (modules referenced by many dependents) are positioned closest to the layout origin $(0,0,0)$.
2. **Secondary Key: Directory Path**
   * Files residing within the same directory path (e.g., `src/auth/`) remain adjacent in the sorted sequence, ensuring they render together as a unified directory sector.

## 2.1.J.3. Phase 2: Golden Angle Radial Packing and Sector Gaps

The layout engine places nodes along a radial Golden Angle spiral, introducing explicit spatial clearance buffers when transitioning across directory boundaries:

$$\text{Angle} \mathrel{+}= 0.5 \text{ rad}$$

**Directory Boundary Check:** If `CurrentFile.directory !== PreviousFile.directory`:
* A radial clearance step is injected: $\text{Radius} \mathrel{+}= 150.0$
* **Layout Result:** Creates distinct visual clearance zones between directory sectors (e.g., separating `src/auth/` from `src/ui/`), forming isolated module clusters across the layout plane.

**Intra-Directory Packing:** If the directory path is unchanged:
* Dense node packing is applied: $\text{Radius} \mathrel{+}= 12.0$

## 2.1.J.4. Phase 3: Vertical Stratification (Y-Axis Elevation by File Type)

The vertical axis ($Y$-axis in WebGL/WebGPU coordinate systems) separates file roles into layered horizontal planes, preventing visual overlap between different software artifacts:

| Elevation Layer | Y-Offset | File Types | Structural Role |
| :--- | :--- | :--- | :--- |
| **Asset Plane** | $+60$ units | `.css`, `.png`, `.svg`, `.html` | User interface assets and presentation templates float above application logic. |
| **Logic Plane** | $0$ units | `.js`, `.ts`, `.py`, `.go`, `.rs` | Core executable source modules form the central, dense layer. |
| **Configuration Plane** | $-60$ units | `.json`, `.yml`, `.dockerfile`, `.md` | Configuration manifests and documentation sink below source code as foundational layers. |

*(Note: Deterministic pseudo-random jitter is added across all axes to maintain organic 3D volume while avoiding rigid coplanar clipping).*

<br><br>

---

### Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**


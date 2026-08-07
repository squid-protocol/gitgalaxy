# Node Geometry & Control Flow Ratio Mapping

> **File Reference:** [`gitgalaxy/recorders/gpu_recorder.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/recorders/gpu_recorder.py)

## Engineering Summary
A geometric classification system alters 3D mesh primitives based on the ratio of decision-making logic to structural data declarations within a file. It solves the problem of visually differentiating between data-heavy files and algorithmic routines. By morphing mesh shapes, this subsystem explicitly defines the functional archetype of code modules, known as the node geometry mapping in GitGalaxy.

## Purpose
To visually classify files into structural archetypes (e.g., data models, controllers, algorithms) based on internal logic density.

## Problem Being Solved
File size and popularity do not indicate the actual nature of the code. A massive JSON configuration and a mathematical parser might share similar sizes, but they require entirely different maintenance approaches.

## Design
The system calculates a Control Flow Ratio ($R_L$):
$$R_L = \frac{BranchHits}{BranchHits + LinearHits}$$
Based on $R_L$, the node is assigned a specific geometric primitive:
- `< 0.60`: Smooth Sphere (Declarative data)
- `0.60 - 0.69`: 20-Facet Icosahedron (Lightweight utilities)
- `0.70 - 0.79`: 12-Facet Dodecahedron (Business logic)
- `0.80 - 0.89`: 8-Facet Octahedron (Algorithmic logic)
- `>= 0.90`: 4-Facet Tetrahedron (Dense control flow, state machines)

## Pipeline Integration
- **Inputs**: `BranchHits` and `LinearHits` extracted during syntax parsing.
- **Outputs**: Selection of a WebGL `BufferGeometry` type.
- **Dependencies**: Relies on metrics from `language_standards`; outputs are passed to the 3D instanced mesh renderer.
```text
Syntax Heuristic Counts -> Control Flow Ratio Calculation -> 3D Mesh Assignment
```

## Tradeoffs
Using discrete geometry bins creates hard boundaries for continuous data. This was chosen over procedural mesh deformation to allow the use of efficient, pre-calculated geometry instancing in WebGL.

## Limitations
- Languages that merge declarations with control flow (e.g., functional languages) may generate skewed $R_L$ values.
- Wireframe rendering for high-$R_L$ files can cause visual aliasing on low-resolution displays.

## Performance Notes
Reusing five static `BufferGeometry` definitions via Instanced Mesh rendering minimizes draw calls and GPU memory overhead, enabling the display of hundreds of thousands of files.

## Future Work
- Implement smooth procedural mesh blending in the vertex shader for continuous visual transitions.
- Normalize $R_L$ baselines dynamically based on the specific programming language paradigm.

## Related Components
- [Visual Code Complexity Mapping](07-01-code-complexity.md)
- [File Node Scaling & Structural Mass](07-02-stars-size.md)

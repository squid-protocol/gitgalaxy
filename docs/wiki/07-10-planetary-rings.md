# External Dependency Rings

> **File Reference:** [`gitgalaxy/core/detector.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/detector.py)

## Engineering Summary
This visualization module generates dependency indicators around file nodes based on external import volumes. It solves the problem of identifying heavy integration modules and dependency coupling risks. It exists to separate self-contained utilities from orchestration layers visually. Within GitGalaxy, this subsystem renders translucent dependency rings in 3D space.

## Purpose
To highlight modules with high external dependency counts by rendering surround rings whose opacity and thickness scale with import volume.

## Problem Being Solved
Integration points and heavy controllers often pull in numerous external packages, creating hidden coupling risks. Visualizing dependency load as surround rings allows developers to spot these heavy integration points instantly.

## Design
A threshold of >5 imports activates the rings.
Opacity and tube radius scale dynamically:
$$\text{Opacity} = \min\left( \left(\frac{\text{ImportHits}}{26}\right) \times 0.6,\ 0.6 \right)$$
$$\text{TubeRadius} = \text{BaseWidth} + (\text{ImportHits} \times 0.1)$$
Rings use `TorusGeometry` and are tilted across randomized Euler axes to avoid coplanar clipping.

## Pipeline Integration
- **Inputs:** `ImportHits` from the static analysis engine.
- **Outputs:** Torus geometry parameters (radius, opacity, rotation).
- **Dependencies:** Relies on import detection and feeds into the WebGPU render loop.

Static Analyzer -> Ring Geometry Subsystem -> WebGPU Renderer

## Tradeoffs
The arbitrary >5 threshold prevents visual noise but sacrifices visibility for files with 3-4 heavy dependencies. Capping opacity at 0.6 prevents overlapping rings from becoming visually opaque solids, preserving depth perception at the cost of true linear scaling.

## Limitations
- Does not distinguish between standard library imports and heavy third-party framework imports.
- Dynamic require statements inside execution blocks may not be captured.

## Performance Notes
Instanced rendering is used for the torus meshes, scaling efficiently on the GPU. Mathematical parameter derivation is $O(1)$ per file.

## Future Work
- Integration with package manager lockfiles to weight imports by transitive dependency size.
- Color coding rings based on external vs. internal mono-repo imports.

## Related Components
- [Spatial Layout](07-11-sequence-affinity.md)
- [Node Size Scaling](07-09-node-size.md)

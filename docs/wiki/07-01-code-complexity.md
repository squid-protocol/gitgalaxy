# Visual Code Complexity Mapping Specifications

> **File Reference:** [`gitgalaxy/recorders/gpu_recorder.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/recorders/gpu_recorder.py)

## Engineering Summary
A rendering configuration translates static analysis metrics into 3D geometric attributes. It solves the challenge of interpreting complex codebase structures by converting multidimensional data (size, dependencies, complexity) into spatial and physical properties. This subsystem acts as the translation layer between calculated numerical metrics and WebGL rendering buffers, operating as the visual code complexity mapping system in GitGalaxy.

## Purpose
To provide a structured specification for how code metrics are visually represented through shape, scale, position, and intensity.

## Problem Being Solved
Standard 2D code dashboards fail to represent the interconnected nature of large repositories. By mapping metrics to 3D geometry, this system allows engineers to visually identify structural patterns and architectural bottlenecks without parsing numerical tables.

## Design
The mapping system converts distinct metrics to visual attributes:
- File Node Scale: Uses Logarithmic scaling of Lines of Code (LOC) and Structural Mass.
- Emissive Intensity: Maps to Inbound Reference Count to highlight highly-imported modules.
- Node Mesh Geometry: Changes from smooth spheres to polyhedrons based on the File Control Flow Ratio.
- Orbital Elements: Maps function count to sub-node quantity, function length to orbital distance, and parameter count to sub-node scale.
- Spatial Clustering: Groups nodes into 3D sectors based on directory paths.

## Pipeline Integration
- **Inputs**: Processed signal vectors, risk schemas, and dependency graphs.
- **Outputs**: Instanced rendering properties (position, scale, geometry type) for the WebGL pipeline.
- **Dependencies**: Depends on metrics from the `SignalProcessor`; consumed by the frontend 3D rendering engine.
```text
Normalized Risk Vectors -> Visual Code Complexity Mapping -> WebGL Rendering Buffers
```

## Tradeoffs
Using geometric complexity and bloom intensity to represent code metrics can introduce visual clutter in repositories with extreme coupling. This approach sacrifices precise, table-based readability for high-density spatial pattern recognition.

## Limitations
- Visual encoding is constrained by WebGL rendering limits; extremely dense repositories may overwhelm the visual field.
- Users with visual impairments may struggle to differentiate subtle changes in emissive intensity or mesh facets.

## Performance Notes
Mapping metrics directly to shader properties avoids expensive CPU-side geometry generation, offloading visual updates to the GPU.

## Future Work
- Implement variable Level-of-Detail (LOD) mappings to dynamically reduce geometric complexity at far camera distances.
- Allow user-configurable mappings to adapt visual attributes to different analysis priorities.

## Related Components
- [File Node Scaling & Structural Mass](07-02-stars-size.md)
- [Node Emissive Intensity](07-03-stars-pulse-rate.md)

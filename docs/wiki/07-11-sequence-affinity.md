# Spatial Layout & Directory Sector Clustering

> **File Reference:** [`gitgalaxy/core/spatial_mapper.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/spatial_mapper.py)

## Engineering Summary
This spatial engine subsystem clusters related source files into 3D directory sectors using a deterministic sorting algorithm. It solves the problem of arbitrary file placement producing chaotic, unreadable topology maps. It exists to create clear spatial neighborhoods driven by directory metadata and architectural role. In GitGalaxy, it generates the final $X, Y, Z$ Cartesian coordinates for the entire repository.

## Purpose
To calculate deterministic 3D layout coordinates for codebase components, grouping them by semantic affinity, directory hierarchy, and file type.

## Problem Being Solved
Iterative physics simulations for graph layout are computationally expensive and produce non-deterministic results. Ordering nodes purely by sequential discovery places unrelated modules arbitrarily. This subsystem guarantees reproducible topologies while explicitly separating directory sectors.

## Design
Uses a Tri-Phase Spatial Layout Pipeline:
1. **Structural Priority Sorting:** Sorts by Inbound Reference Count (descending) placing core utilities at the origin, then by Directory Path to group files.
2. **Radial Packing:** Places nodes along a Golden Angle spiral ($\text{Angle} \mathrel{+}= 0.5 \text{ rad}$). Injects a 150.0 radius clearance step for directory boundaries, or 12.0 for intra-directory nodes.
3. **Vertical Stratification:** Offsets the $Y$-axis based on file type: Asset Plane ($+60$), Logic Plane ($0$), Configuration Plane ($-60$).

## Pipeline Integration
- **Inputs:** Sorted file nodes, dependency reference counts, directory metadata.
- **Outputs:** Absolute $X, Y, Z$ positions for all layout nodes.
- **Dependencies:** Relies on the entire dependency graph resolution phase before execution.

Graph Resolver -> Spatial Engine -> Coordinate Matrix Buffer

## Tradeoffs
Using a deterministic Golden Angle spiral instead of force-directed graphs sacrifices organic clustering capabilities for immense speed improvements and deterministic topology generation. The fixed 150.0 boundary clearance is an rigid heuristic that may look sparse for very small directories.

## Limitations
- Deeply nested directories may eventually spread too far along the radial axis, creating large empty voids.
- Pseudo-random jitter used to prevent clipping makes exact coordinate tests difficult.

## Performance Notes
The 3-pass sort and offset algorithm operates in $O(N \log N)$ time for sorting and $O(N)$ for layout assignment, making it significantly faster than $O(N^2)$ force-based physics models.

## Future Work
- Implementing hierarchical bounding volume hierarchies (BVH) for tighter cluster packing.
- Dynamic clearance scaling based on the total mass of the directory.

## Related Components
- [Component Layout Clearance Formulas](07-12-misc-equations.md)
- [Angular Positioning](07-08-relative-positioning.md)

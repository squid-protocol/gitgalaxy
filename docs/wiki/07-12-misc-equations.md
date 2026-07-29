# Component Layout Clearance Formulas

> **File Reference:** [`gitgalaxy/core/spatial_mapper.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/spatial_mapper.py)

## Engineering Summary
This collision management subsystem calculates the orbital clearance radius for child nodes based on their parent's code volume. It solves the problem of child geometries colliding with or rendering inside oversized parent file nodes. It exists to maintain structural visibility across massively varying file sizes in the 3D view. In GitGalaxy, this equation is a foundational utility for spatial orchestration.

## Purpose
To dynamically compute child node orbital distances relative to parent file size (LOC) to prevent geometric intersection.

## Problem Being Solved
High-LOC modules occupy larger visual bounds. Without dynamic clearance, child components orbiting these massive parent nodes would render inside the parent mesh, completely obscuring their presence and breaking visual topology.

## Design
The orbit radius ($\text{OrbitRadius}$) is formulated as a logarithmic function of the parent's lines of code ($\text{LOC}$):
$$\text{OrbitRadius} = 40 + \left( \log_2(\text{LOC}) \times 10 \right)$$
This establishes a 40-unit base radius, expanding logarithmically to ensure large monoliths provide sufficient clearance without pushing child nodes entirely out of view.

## Pipeline Integration
- **Inputs:** Parent file `LOC` (lines of code).
- **Outputs:** A floating-point offset distance.
- **Dependencies:** Operates during the spatial layout phase, combining with angular positioning logic.

File Volume Metric -> Clearance Subsystem -> Layout Engine

## Tradeoffs
The logarithmic expansion limits the maximum clearance distance, which prevents child nodes from drifting too far but sacrifices strict boundary guarantees if the parent node's radius scales linearly rather than logarithmically.

## Limitations
- Does not account for the actual rendered bounding box of the parent, only its raw LOC.
- May produce insufficient clearance if the parent node scale multiplier is overridden by other visual metrics.

## Performance Notes
Calculated using a fast logarithmic evaluation, achieving $O(1)$ constant time complexity per relationship edge during layout generation.

## Future Work
- Switching to exact bounding box (AABB) intersection tests for precise clearance guarantees.
- Supporting elliptical orbits for non-uniform parent node shapes.

## Related Components
- [Spatial Layout](07-11-sequence-affinity.md)
- [Angular Positioning](07-08-relative-positioning.md)

# Sub-Node Orbital Distance & Logarithmic Scaling

> **File Reference:** [`gitgalaxy/recorders/gpu_recorder.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/recorders/gpu_recorder.py)

## Engineering Summary
A spatial sorting mechanism determines the 3D distance between a child function and its parent file node based on physical line count. It solves the challenge of visually identifying bloated functions by correlating spatial displacement with length. This subsystem explicitly visualizes code bloat by pushing large functions further out into space, operating as the sub-node orbital distance mapping in GitGalaxy.

## Purpose
To explicitly visualize function length and code bloat by pushing large functions further out into space, away from the parent file node.

## Problem Being Solved
Without expanding text views, it is difficult to identify oversized legacy methods buried inside standard modules. Mapping line count to orbital distance instantly flags monolithic functions as outliers positioned far from the file core.

## Design
The orbital radius utilizes a base-2 logarithmic scaling formula:
$$Orbital Radius = 60 + (\log_2(\max(LOC, 1)) \times 30)$$
- 60: Baseline clearance to prevent intersecting the parent node mesh.
- 30: Spatial multiplier to ensure adequate separation between sub-nodes of varying lengths.
A 10 LOC function orbits near 160 units, while a 1,000 LOC method orbits around 360 units.

## Pipeline Integration
- **Inputs**: The physical Lines of Code (LOC) for a specific extracted function.
- **Outputs**: A scalar radial distance used for 3D placement.
- **Dependencies**: Depends on data from the function extraction engine; output consumed by the orbital placement calculations.
```text
Function LOC -> Logarithmic Distance Formula -> 3D Radial Coordinate
```

## Tradeoffs
Logarithmic scaling compresses massive differences in function length into relatively small spatial adjustments. We chose this over linear scaling to keep all child nodes within the camera's readable viewport frustum.

## Limitations
- Extremely small differences in function length produce indistinguishable orbital distances.
- Does not account for code formatting styles which can skew the LOC metric.

## Performance Notes
Applying a baseline clearance (60 units) prevents Z-fighting and mesh collision between the parent node and the child geometries, maintaining clean pixel shader execution.

## Future Work
- Replace raw LOC with calculated AST tokens to eliminate formatting inconsistencies.
- Allow dynamic adjustment of the spread multiplier based on the zoom level of the camera.

## Related Components
- [Function Sub-Node Units](07-05-satellite-unit.md)
- [Visual Code Complexity Mapping](07-01-code-complexity.md)

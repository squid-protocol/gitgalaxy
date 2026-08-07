# Angular Positioning of Child Nodes

> **File Reference:** [`gitgalaxy/core/spatial_mapper.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/core/spatial_mapper.py)

## Engineering Summary
This spatial configuration subsystem distributes sub-nodes within a function unit based on its control flow ratio. It solves the problem of visual uniformity obscuring code behavior differences. It exists to differentiate algorithmic routing logic from declarative structures through physical divergence angles. Within GitGalaxy, this process scales visual node spreading dynamically.

## Purpose
To configure the spatial angular distribution of sub-nodes within a function unit based on its ratio of control flow to declarative statements.

## Problem Being Solved
Providing uniform visual spacing across all code blocks obscures structural behavioral differences. By modulating layout angles, developers can quickly distinguish algorithmic logic from static configuration data.

## Design
Statements are divided into Algorithmic Logic (branches, loops) and Declarative Structure (data, imports).
The Control Flow Ratio ($R_L$) is calculated as:
$$R_L = \frac{\text{BranchHits}}{\text{BranchHits} + \text{LinearHits}}$$

The layout angle is mapped via linear interpolation between $22.5^\circ$ (high logic) and $90.0^\circ$ (high structure):
$$\text{Angle} = 22.5^\circ + \left( (1.0 - R_L) \times (90.0^\circ - 22.5^\circ) \right)$$

## Pipeline Integration
- **Inputs:** `BranchHits` and `LinearHits` extracted by the static analyzer.
- **Outputs:** An angular divergence value in degrees/radians.
- **Dependencies:** Relies on upstream metric extraction and feeds into the 3D scene graph generator.

Metrics Engine -> Angular Positioning -> Scene Graph Generator

## Tradeoffs
Interpolating between fixed $22.5^\circ$ and $90.0^\circ$ limits the visualization space but ensures rendering stability. Rejecting force-directed algorithms in favor of deterministic linear interpolation sacrifices organic aesthetics for rendering speed and predictability.

## Limitations
- Does not account for multiline string blocks that may skew declarative statement counts.
- The fixed angle bounds may cause overlap in exceptionally dense code clusters.

## Performance Notes
The linear interpolation step operates in $O(1)$ time per node, ensuring zero physics simulation overhead during layout generation.

## Future Work
- Adjustable angle boundaries based on parent node density.
- Collision detection integration to prevent overlapping acute branches.

## Related Components
- [Function Node Scaling](07-09-node-size.md)
- [Child Component Density](07-07-number-of-satellites.md)

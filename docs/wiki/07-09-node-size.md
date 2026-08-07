# Function Component Node Scaling

> **File Reference:** [`gitgalaxy/core/detector.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/core/detector.py)

## Engineering Summary
This geometry processing subsystem calculates the visual scale of function nodes based on their input parameter count. It solves the problem of identifying high-coupling or high-state-complexity methods. It exists to create a visual footprint hierarchy that mirrors I/O signature weight. In GitGalaxy, this component dictates the 3D radius bounds of function meshes.

## Purpose
To visualize parameter mass and I/O signature complexity by controlling the physical render scale (Radius) of function nodes.

## Problem Being Solved
Functions with excessive parameters (5+) often carry high state complexity or tight parameter coupling, which is hard to spot in a file list. Modulating scale visually highlights these refactoring targets across the codebase graph.

## Design
The subsystem evaluates parameter signatures (`Args`). It applies a logarithmic scaling formulation to prevent oversized nodes from cluttering the viewport:
$$\text{Scale} = 1.0 + \left( \log_2(\max(\text{Args}, 1)) \times 0.2 \right)$$

Scale tiers range from 1.00 (0-1 args) to ~1.78+ (15+ args), dynamically resizing the mesh bounds.

## Pipeline Integration
- **Inputs:** `Args` (parameter count) from the function definition parser.
- **Outputs:** A floating-point scale multiplier.
- **Dependencies:** Requires function parameter extraction and feeds into WebGL geometry generation.

Parser -> Node Scaling Subsystem -> WebGL Renderer

## Tradeoffs
Logarithmic scaling was chosen over linear scaling to preserve viewport space for extreme outliers, sacrificing linear proportionality. This prevents a function with 30 parameters from occluding entire directories.

## Limitations
- Treats all parameters equally regardless of type complexity (e.g., a primitive int vs. a complex object pointer).
- Does not inspect `**kwargs` or object destructuring depth in dynamic languages.

## Performance Notes
The metric uses a standard base-2 logarithm, evaluating in $O(1)$ time per function, allowing near-instant layout calculations for thousands of nodes.

## Future Work
- Type-aware parameter weighting (e.g., increasing weight for complex generic types).
- Adjusting scale based on local variable declarations in addition to parameters.

## Related Components
- [Planetary Rings](07-10-planetary-rings.md)
- [Misc Equations](07-12-misc-equations.md)

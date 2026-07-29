# Node Emissive Intensity & Pulse Rate Mapping

> **File Reference:** [`gitgalaxy/recorders/gpu_recorder.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/recorders/gpu_recorder.py)

## Engineering Summary
A mapping system converts a file's dependency in-degree into shader animation parameters. It solves the challenge of identifying structural bottlenecks in large systems by translating inbound reference counts into visual brightness and pulse frequencies. This subsystem allows architects to instantly locate core dependencies and popular modules, operating as the node emissive intensity mapping within GitGalaxy.

## Purpose
To visually encode the architectural centrality of a module using dynamic shader effects rather than static geometry.

## Problem Being Solved
In dense dependency graphs, drawing hundreds of edge lines between nodes creates unreadable visual fields. Modulating emissive intensity removes the need for explicit edge rendering while clearly conveying node centrality.

## Design
The mapping converts inbound reference counts into normalized popularity ($P$), which then drives shader uniforms:
- Pulse Frequency: Ranges from 0.5 Hz to 1.5 Hz.
- Emissive Floor: Sets the minimum intensity ($0.2 + P \times 0.8$).
- Emissive Ceiling: Sets the peak intensity ($1.5 + P \times 2.5$).
A sinusoidal function in the shader uses these bounds to evaluate the final per-frame intensity.

## Pipeline Integration
- **Inputs**: Calculated in-degree dependency counts for each file.
- **Outputs**: Shader uniform values (frequency, min/max intensity).
- **Dependencies**: Requires dependency graph resolution; outputs consumed directly by the WebGL fragment shader.
```text
Dependency Graph In-Degree -> Emissive Mapping Formulas -> WebGL Shader Uniforms
```

## Tradeoffs
Representing dependencies via emissive pulsing obscures the exact source of the inbound references. We chose this to maintain a clean visual field, sacrificing explicit point-to-point traceability for high-level systemic comprehension.

## Limitations
- Emissive bloom can wash out adjacent nodes in densely packed spatial clusters.
- The normalization ceiling can skew results if a single outlier module is imported thousands of times.

## Performance Notes
Offloading the sinusoidal pulse calculation to the GPU fragment shader ensures zero CPU overhead during animation cycles, maintaining consistent 60 FPS rendering.

## Future Work
- Implement local neighborhood normalization to prevent global outliers from compressing the emissive range.
- Introduce pulse phase offsetting to prevent synchronized flashing when multiple central hubs are viewed.

## Related Components
- [Visual Code Complexity Mapping](07-01-code-complexity.md)
- [Node Geometry & Control Flow](07-04-stars-shape.md)

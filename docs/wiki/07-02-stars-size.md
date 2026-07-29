# File Node Scaling & Structural Mass Calculation

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)

## Engineering Summary
A composite metric determines the 3D radius of file nodes. It solves the problem of relying solely on line counts, which misrepresent the architectural weight of dense algorithmic files compared to verbose configuration files. This subsystem ensures that complex, tightly coupled components are visually prominent, functioning as the structural mass calculation within GitGalaxy.

## Purpose
To generate a single, normalized scalar value that accurately reflects a file's complexity, coupling, and size for rendering purposes.

## Problem Being Solved
Lines of Code (LOC) is a poor indicator of cognitive load and architectural risk. A 50-line recursive algorithm is significantly more impactful than a 200-line JSON file, but raw LOC would incorrectly prioritize the JSON file.

## Design
The Structural Mass calculation operates in three stages:
1. Function Impact Score: Evaluates each function based on decision points, parameter counts, and scaled LOC:
   $$Impact = ((BranchHits + 1) \times (Args + 1) + (0.05 \times LOC)) \times 10$$
2. Total Structural Mass: Sums all function impacts with system-level metrics (API exposure, Concurrency, State Mutation, and scaled base LOC).
3. Visual Render Radius: Applies a base-2 logarithmic transformation to compress the mass into a 10 to 50 unit scale:
   $$Radius = 10 + (\log_2(\max(Total Mass, 1)) \times 2)$$

## Pipeline Integration
- **Inputs**: Extracted heuristics, function metrics, and baseline LOC.
- **Outputs**: A continuous scalar radius value.
- **Dependencies**: Relies on metrics aggregated by `language_standards`; consumed by the visual mapping configuration.
```text
Raw Function Heuristics -> Structural Mass Calculation -> 3D Node Radius Attribute
```

## Tradeoffs
The calculation relies on arbitrary weighting factors (e.g., multiplying LOC by 0.05) to balance different paradigms. This heuristic tuning trades absolute mathematical rigor for improved visual categorization across diverse codebases.

## Limitations
- Highly verbose, auto-generated code can still skew the mass calculation despite fractional LOC weighting.
- Does not account for indirect complexity derived from inherited classes or deeply nested generic types.

## Performance Notes
Applying a logarithmic transformation ensures that the final rendering radius remains within hardware limits, preventing occlusion or rendering failure on massive monolithic files.

## Future Work
- Tune the weighting multipliers dynamically based on repository-wide statistical distributions.
- Incorporate cyclomatic complexity derived from ASTs to replace the heuristic approximations.

## Related Components
- [Visual Code Complexity Mapping](07-01-code-complexity.md)
- [Node Geometry & Control Flow](07-04-stars-shape.md)

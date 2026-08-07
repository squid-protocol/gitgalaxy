# Child Component Density & Function Complexity

> **File Reference:** [`gitgalaxy/core/detector.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/core/detector.py)

## Engineering Summary
This subsystem measures and visualizes logic complexity within individual functions by calculating a composite complexity score. It solves the problem of developers needing to quickly assess the cognitive load of code modules during codebase exploration. It exists to map textual code complexity into physical object density within a 3D visualization. Within GitGalaxy, this subsystem defines the child satellite node count for function components.

## Purpose
To calculate the structural and defensive overhead of function logic and determine the number of child satellite nodes rendered in the 3D plane.

## Problem Being Solved
Developers struggle to identify high-friction, deeply nested functions in large codebases. While compilers handle branches easily, humans face cognitive limits. This component maps the cognitive friction of conditional branching and error handling directly to visual density.

## Design
Function complexity is computed from two code patterns:
1. **Structural Complexity:** Decision points (`BranchHits` from `if`, `for`, `switch`).
2. **Defensive Overhead:** Guard logic (`SafetyHits` from `try`, `catch`, `assert`).

**Composite Complexity Score ($C$):**
$$C = \text{BranchHits} + (\text{SafetyHits} \times 0.5)$$
Defensive logic is weighted at 0.5 since guard conditions consume roughly half the cognitive overhead of full control flow forks. 
Score tiers determine the node count: $\le 2$ (0-1 nodes), $> 2$ (1-2 nodes), $> 8$ (3-4 nodes), $> 15$ (dense cluster), $> 25$ (heavy cluster).

## Pipeline Integration
- **Inputs:** `BranchHits` and `SafetyHits` from the static analyzer.
- **Outputs:** An integer child node count.
- **Dependencies:** Relies on upstream static analysis counts and drives downstream 3D layout rendering.

Static Analyzer -> Density Subsystem -> 3D Layout Engine

## Tradeoffs
Regex-based heuristics are chosen over full AST parsing for processing speed, sacrificing exact scope awareness. The 0.5 weight for defensive hits is a subjective heuristic that balances risk visibility without penalizing safe coding practices.

## Limitations
- Unsupported languages or non-standard macros will not trigger branch counters.
- Large switch statements can artificially inflate structural complexity scores.

## Performance Notes
The composite calculation is $O(1)$ per function since it performs basic arithmetic on pre-computed heuristic variables.

## Future Work
- Context-aware weighting to differentiate deep nesting from linear conditional branches.
- Dynamic adjustments for language-specific idioms.

## Related Components
- [Relative Positioning](07-08-relative-positioning.md)
- [Node Size Scaling](07-09-node-size.md)

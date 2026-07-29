import os

docs = {
    "07-07-number-of-satellites.md": r"""# Child Component Density & Function Complexity

> **File Reference:** [`gitgalaxy/core/detector.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/detector.py)

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
""",
    "07-08-relative-positioning.md": r"""# Angular Positioning of Child Nodes

> **File Reference:** [`gitgalaxy/core/spatial_mapper.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/spatial_mapper.py)

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
""",
    "07-09-node-size.md": r"""# Function Component Node Scaling

> **File Reference:** [`gitgalaxy/core/detector.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/detector.py)

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
""",
    "07-10-planetary-rings.md": r"""# External Dependency Rings

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
""",
    "07-11-sequence-affinity.md": r"""# Spatial Layout & Directory Sector Clustering

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
""",
    "07-12-misc-equations.md": r"""# Component Layout Clearance Formulas

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
""",
    "08-01-methodology.md": r"""# Overview of Methodology & Risk Exposure Index

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)

## Engineering Summary
This subsystem forms the analytical core that translates raw regex heuristic counts into structured risk exposure ratings. It solves the problem of converting massive volumes of static analysis data into actionable, normalized health indicators without manual inspection. It exists to objectively map structural anomalies to a universal risk spectrum. Within GitGalaxy, it processes data across five architectural scopes to generate the primary knowledge graph attributes.

## Purpose
To evaluate source code components against 50+ heuristic metrics and aggregate them into a 5-tier Universal Risk Spectrum across function, class, file, directory, and repository scopes.

## Problem Being Solved
Subjective code quality scores lack consistency and traceability. This subsystem replaces subjective heuristics with deterministic, objective Risk Exposures, enabling engineering teams to identify architectural drift and technical debt algorithmically.

## Design
Evaluates metrics mapping to a 5-tier spectrum (Blue, Cyan, Yellow, Orange, Red). It calculates specific risk domains like Cognitive Load, State Flux, Technical Debt, and Concurrency Exposure. Aggregations use distinct mathematical normalization techniques depending on scope: Count-based (Levels 1-2), Sigmoid Normalized (Level 3), and Mass-Weighted Averages (Levels 4-5). Custom topological scales are employed for structural formatting indicators (e.g., Indentation Consistency).

## Pipeline Integration
- **Inputs:** Raw text parsing heuristic hits and regex counts.
- **Outputs:** Normalized risk scores across five architectural levels.
- **Dependencies:** Integrates downstream from the raw source parser and upstream of the final visualization dataset generation.

Raw Source Parser -> Risk Processor -> Knowledge Graph Database

## Tradeoffs
Relying on deterministic regex patterns instead of deep semantic AST analysis sacrifices deep context awareness for blazing fast processing speeds and broad language support. Mass-weighted averaging at directory levels can occasionally dilute extreme risk spikes from small utility files.

## Limitations
- Regex heuristics cannot detect logic errors or runtime context.
- Aggregation across directory scopes may mask isolated critical vulnerabilities if the overall directory mass is heavily defended.

## Performance Notes
The signal processor utilizes vectorized numpy operations to normalize millions of data points, ensuring near-instant metric tiering scaling at $O(N)$ efficiency for repository size.

## Future Work
- Integration with language server protocols (LSP) to complement heuristic regex data with semantic type awareness.
- Dynamic weighting adjustments based on temporal commit frequency.

## Related Components
- [Sub-Equations](08-02-sub-equations.md)
- [Transforming Regex Counts](08-03-transforming-regex-counts.md)
""",
    "08-02-sub-equations.md": r"""# Sub-Equations & Scanner Variables

> **File Reference:** [`gitgalaxy/core/detector.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/detector.py)

## Engineering Summary
This static analysis extraction subsystem defines the raw regular expression inputs used by the metrics engine. It solves the problem of extracting standardized structural and behavioral indicators from diverse programming languages. It exists to provide a language-agnostic data foundation for risk assessment. In GitGalaxy, this process runs over a strict 5-phase extraction sequence to generate core variables.

## Purpose
To extract a standardized set of regular expression variables (e.g., structural footprints, risk indicators) from raw source files to compute reliable risk and complexity metrics.

## Problem Being Solved
Extracting analytical data from raw text requires a standardized taxonomy. This subsystem categorizes hundreds of regex patterns into unified output variables (like `branch_hits` or `safety_hits`), bridging the gap between raw text and mathematical evaluation.

## Design
Variables are extracted in five phases:
1. **Code Structure:** `branch_hits`, `args_hits`, `linear_hits`, `func_start_hits`.
2. **Risk Indicators:** `safety_hits`, `danger_hits`, `io_hits`, `api_hits`, `flux_hits`.
3. **Domain Identifiers:** `concurrency_hits`, `closures_hits`, `globals_hits`, `import_hits`.
4. **Specialized Debt:** `planned_debt_hits`, `fragile_debt_hits`, `private_info_hits`, `memory_alloc_hits`.
5. **Contextual Counter-Weights:** `telemetry_hits`, `sync_locks_hits`, `encapsulation_hits`, `cleanup_hits`.
All output count variables utilize a `_hits` suffix.

## Pipeline Integration
- **Inputs:** Raw source code strings.
- **Outputs:** Categorized integer counts (scanner variables) per file and function.
- **Dependencies:** Operates as the initial data ingestion layer, feeding directly into the signal processing models.

Source Text -> Scanner Extraction Phase -> Signal Processing Engine

## Tradeoffs
Employing regex for token extraction is significantly faster than lexing and parsing full ASTs, but sacrifices precision. It may count keywords located within comments or strings unless pre-filtered, which is accepted in favor of high-throughput analysis.

## Limitations
- Unable to trace variable scope or lexical lifetime bounds.
- Custom domain-specific macros or aliases will not register against standard regex sets.

## Performance Notes
The extraction uses optimized compiled regex engines running concurrently, achieving $O(L)$ parsing time where $L$ is the number of lines of code.

## Future Work
- Multi-pass string and comment stripping before regex evaluation to eliminate false positives.
- Extensible user-defined regex rulesets for internal corporate standards.

## Related Components
- [Overview of Methodology](08-01-methodology.md)
- [Transforming Regex Counts](08-03-transforming-regex-counts.md)
""",
    "08-03-transforming-regex-counts.md": r"""# Transforming Regex Counts (Universal Exposure Framework)

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)

## Engineering Summary
This metric normalization subsystem, known as the Universal Exposure Framework (UEF), recalibrates raw static regex counts into stable architectural indicators. It solves the problem of raw hit counts being noisy, misleading, or skewed by codebase size. It exists to provide deterministic, language-aware filtering of heuristic signals. Within GitGalaxy, the UEF calculates final, tiered risk outputs from raw data variables.

## Purpose
To process raw occurrence counts through deterministic normalization transformations, stabilizing signals and eliminating false positives across different language paradigms.

## Problem Being Solved
Uncalibrated static regex counts penalize large files for minor issues and treat structural risk and defensive logic as a flawed 1:1 offset. The UEF stabilizes these signals into actionable, normalized intelligence.

## Design
Applies four stabilizing principles:
1. **Weighted Asymmetry:** Defensive hits receive a 2.5x multiplier to demand strong defensive density.
2. **The Breach Cap:** If raw risk hits exceed guardrail hits, the safety rating is severely capped, bypassing averages.
3. **Sigmoid Gating:** Uses a logistic sigmoid function to filter low-density noise (0-5%) and scale exponentially as risk crosses thresholds.
4. **Quantized Tiering:** Scores are binned into qualitative tiers (Unshielded to Fortified).

Language Confidence Tiers (1 to 3) apply Fidelity Coefficients ($Fc$) and Implicit Risk Corrections ($Irc$) based on language strictness.
General Risk Equation:
$$RiskExposure = \left( \frac{((RiskHits + Irc) \times Weight) - (DefenseHits \times Fc)}{LOC} \right) \times Mp$$

## Pipeline Integration
- **Inputs:** Raw regex counts, LOC, language metadata.
- **Outputs:** Normalized, quantized risk tiers (1-5).
- **Dependencies:** Receives input from the scanner extraction module and feeds into the knowledge graph and visual mapping layers.

Scanner Extraction -> Universal Exposure Framework -> Quantized Tier Output

## Tradeoffs
The sigmoid gating principle aggressively suppresses minor risks in large files, intentionally sacrificing micro-level visibility to prevent "alert fatigue" on the macro level. Language confidence tiers generalize thousands of languages into three buckets, reducing precision for niche languages.

## Limitations
- The 2.5x defensive multiplier is empirically derived and may not perfectly align with specific internal security postures.
- Path Multipliers ($Mp$) rely on standard directory naming conventions (`src/`, `test/`) which may fail in non-standard repositories.

## Performance Notes
Processing utilizes constant-time floating-point math per file component, resulting in $O(1)$ metric transformation time per unit post-extraction.

## Future Work
- Machine learning parameter tuning for Fidelity Coefficients based on historical vulnerability tracking.
- Configurable Breach Cap thresholds per repository.

## Related Components
- [Overview of Methodology](08-01-methodology.md)
- [Sub-Equations](08-02-sub-equations.md)
""",
    "08-04-ownership-entropy.md": r"""# Authorship Distribution (Ownership Entropy)

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)

## Engineering Summary
This statistical analysis component calculates the Shannon Entropy of Git blame data to measure contribution dispersion across modules. It solves the problem of identifying knowledge silos and bus-factor risks hidden behind simple contributor headcounts. It exists to map authorship concentration to the Universal Risk Spectrum. Within GitGalaxy, it highlights whether a module is a single-author bottleneck or a highly distributed community effort.

## Purpose
To measure the distribution of commit contributions across authors within a module using Shannon Entropy, highlighting knowledge siloing versus shared maintenance.

## Problem Being Solved
Simple contributor headcounts fail to capture distribution. A file with 1 primary author (90%) and 10 minor contributors (1% each) has 11 authors but remains a knowledge silo. Shannon entropy correctly identifies this imbalance and penalizes high operational noise.

## Design
Evaluates authorship structure:
- **Low Entropy:** High concentration, individual ownership, high bus factor.
- **High Entropy:** Shared maintenance, high diffusion.

Calculation:
$$p_i = \frac{\text{Commits}_i}{\text{TotalCommits}}$$
$$H = -\sum \left( p_i \times \log_2(p_i) \right)$$
$$\text{OwnershipScore} = \min(H \times 32.0, 100.0)$$

Scores map to tiers: 0-20 (Single Owner), 21-60 (Team Collaboration), 61-100 (High Diffusion).

## Pipeline Integration
- **Inputs:** Git blame contribution maps and commit counts.
- **Outputs:** A normalized scalar entropy score (0-100) and color classification.
- **Dependencies:** Relies on upstream Git history extraction and feeds directly into the visualization shaders.

Git Blame Extractor -> Entropy Calculation Engine -> Visual Render Attributes

## Tradeoffs
Using commit counts as the basis for entropy assumes all commits have equal weight. A massive refactoring commit is weighed identically to a one-line typo fix, sacrificing granular impact analysis for fast, aggregate historical processing.

## Limitations
- Git author email aliases (e.g., user@local vs user@company) will skew entropy unless deduplicated prior to analysis.
- Extremely old legacy code may have high entropy from long-gone contributors, artificially inflating the diffusion score for the current active team.

## Performance Notes
Normalizing authorship into a scalar score ensures constant WebGPU rendering efficiency regardless of the number of unique contributors, guaranteeing 60 FPS performance on massive enterprise codebases.

## Future Work
- Time-decayed entropy weighting, prioritizing recent commit distribution over historical legacy authors.
- Commit size weighting (lines changed) integrated into the probability $p_i$ variable.

## Related Components
- [Overview of Methodology](08-01-methodology.md)
""",
}

for filename, content in docs.items():
    filepath = os.path.join("/home/joe/nyx_projects/gitgalaxy/docs/wiki", filename)
    with open(filepath, "w") as f:
        f.write(content)

print("Files rewritten successfully without escape sequences.")

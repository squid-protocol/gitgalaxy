# The Network Risk Sensor (Graph Topology & Blast Radius)

> **File Reference:** [`gitgalaxy/core/network_risk_sensor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/network_risk_sensor.py)

The Network Risk Sensor (`network_risk_sensor.py`) constructs an $N$-dimensional Directed Graph (`nx.DiGraph`) from raw import statements extracted across all scanned files. By mapping inter-file module dependencies, the sensor transforms isolated file metrics into a systemic dependency analysis engine. It computes blast radius values, classifies component roles, and evaluates repo-wide network resilience.

---

## Directed Graph Construction

The sensor ingests raw import string declarations extracted during parsing and resolves them into a NetworkX Directed Graph (`nx.DiGraph`):

* **Fast Target Path Resolution:** Uses a pre-computed lookup resolution map matching raw import strings (e.g., `import utils`) to target source file paths (e.g., `src/core/utils.py`).
* **Weighted Coupling Edges:** Assigns weighted edges based on dependency specificity. Imports targeting specific class or function symbols increase edge weight by 1.5x to reflect tight logical coupling.

---

## Graph Centrality & Blast Radius Metrics

Once the graph topology is resolved, the sensor computes network centrality metrics to determine module impact:

* **PageRank (Normalized Blast Radius):** Measures structural dependency weight based on the number and importance of importing modules. Scaled by 1000 to produce the **Normalized Blast Radius**. Modifying high blast radius modules introduces substantial regression risk.
* **Betweenness Centrality (Architectural Choke Points):** Measures how frequently a module sits along shortest dependency paths between distinct functional domains. For repositories exceeding 5,000 nodes, betweenness computation uses randomized sampling ($k=50$) to maintain $O(N)$ execution speed.
* **Closeness Centrality (Ripple Effect Distance):** Evaluates average topological distance to all other files in the graph, indicating how rapidly runtime failures propagate across the application.

---

## Ecosystem Component Roles

The sensor evaluates the ratio of inbound dependency edges (`in_degree`) to total connected edges, categorizing every module into an operational role:

* **Producer (Foundation):** $>80\%$ inbound edges. Core utility modules, base classes, or data schemas relied upon by the rest of the application.
* **Consumer (Orchestrator):** $<20\%$ inbound edges. Controllers, entry points, or CLI scripts that import multiple downstream packages to execute application flows.
* **Transceiver (Middle Tier):** $20\% - 80\%$ inbound edges. Intermediate business logic and service handlers passing data between consumers and producers.
* **Isolated / Orphan:** 0 connected edges. Unused modules, standalone utilities, or dynamically loaded scripts.

---

## Systemic Risk & Performance Bottleneck Analysis

Local code quality issues present higher risk when located inside core foundational modules:

* **Systemic Threat Vector:** Cross-multiplies local risk scores with the module's Normalized Blast Radius to highlight files that are both high-risk and heavily depended upon.
* **Algorithmic Complexity Bottlenecks:** Flags modules with a Normalized Blast Radius $> 1.0$ combined with an algorithmic complexity of $O(N^3)$ or higher (or active recursion). These represent key candidates for performance optimization.

---

## Global Repository Topology Metrics

The sensor computes structural health metrics across the overall graph:

* **Modularity:** Measures functional separation between modules versus monolithic coupling density.
* **Assortativity:** Evaluates whether high-impact modules connect primarily to other robust modules (resilient architecture) or to fragile scripts (single points of failure).
* **Cyclic Density:** Measures the percentage of files participating in circular dependency loops.
* **Average Path Length:** Calculates the average dependency distance between any two files in the repository.
* **Articulation Points:** Identifies single files whose removal breaks the graph into disconnected sub-components.

---

### Zero-Dependency Fallback Mode
If `networkx` is unavailable in the environment, the sensor degrades gracefully into Zero-Dependency Mode. It calculates basic in/out degree ratios to determine component roles and heuristic blast radius metrics without throwing runtime errors.

---

### Powered by GitGalaxy

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic static analysis engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for source code and tools.
* **[Visualize your codebase at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**


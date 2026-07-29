# File Node Scaling & Structural Mass Calculation

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)

In source code visualization, line count alone is an inadequate indicator of architectural impact. A 200-line configuration file requires minimal cognitive overhead, whereas a 50-line recursive algorithm with high branching density and security implications represents significant architectural risk. 

GitGalaxy computes a composite metric called **Structural Mass** to scale 3D node radii in the WebGL interface, ensuring complex and heavily coupled files visually anchor their architectural sectors.

## Mass Input Dimensions

The Structural Mass calculation combines five distinct dimensions of code structure:

1. **Function Impact:** Aggregated decision density, argument coupling, and size of internal functions.
2. **API Exposure:** Degree of public interface exposure and external integration.
3. **Concurrency Exposure:** Density of multithreading, asynchronous execution, and process synchronization constructs.
4. **State Mutation Density (Flux):** Frequency of variable mutations and state side-effects.
5. **Lines of Code (LOC):** Physical line volume, scaled down to serve as a baseline substrate.

## Mathematical Model

The engine calculates mass through a multi-stage summation. Structural complexity acts as a multiplier, while file length acts as a linear base. A base-2 logarithmic transformation compresses the resulting range into renderable 3D scale units:

### Step 1: Function Impact Score
For each function within a file, an impact score is derived from decision points (`BranchHits`), parameter counts (`Args`), and line count (`LOC`):

$$\text{Function Impact} = \left( (\text{BranchHits} + 1) \times (\text{Args} + 1) + (0.05 \times \text{LOC}) \right) \times 10$$

### Step 2: Total Structural Mass
The total structural mass of a file sums its internal function impacts alongside system-level risk exposure metrics:

$$\text{Total Mass} = \sum(\text{Function Impacts}) + \text{API} + \text{Concurrency} + \text{Flux} + \left( \frac{\text{LOC}}{50} \right)$$

### Step 3: Visual Render Radius
To map wide variance in raw mass (ranging from 10 to over 1,000,000) into a balanced visual viewport (10 to 50 scale units), a logarithmic scaling formula is applied:

$$\text{Radius} = 10 + \left( \log_2(\max(\text{Total Mass}, 1)) \times 2 \right)$$

## Visual Classification Scale

| Classification | Structural Mass Range | Render Radius | Architectural Context |
| :--- | :--- | :--- | :--- |
| **Minor Utility** | < 100 | ~16 units | Simple DTOs, interface definitions, or small configuration files. Compact visual footprint. |
| **Standard Module** | 100 - 1,000 | ~20 - 26 units | Standard business logic components and standard application modules. |
| **Major Controller** | 1,000 - 20,000 | ~27 - 38 units | Core application utilities, primary controllers, or complex data processing pipelines. |
| **Critical Monolith** | 20,000+ | ~40+ units | Large monolithic files or central state managers requiring refactoring consideration. |

---

### Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**


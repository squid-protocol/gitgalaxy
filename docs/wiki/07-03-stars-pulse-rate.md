# Node Emissive Intensity & Pulse Rate Mapping

> **File Reference:** [`gitgalaxy/recorders/gpu_recorder.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/recorders/gpu_recorder.py)

To highlight central architectural dependencies, GitGalaxy maps a file's **Inbound Reference Count** (graph in-degree or popularity) directly to node emissive shader intensity and pulse frequency in the WebGL renderer. 

Files imported by many downstream modules emit a high-brightness bloom effect, allowing system architects to instantly identify critical dependency hubs across the codebase.

## Metrics and Inputs

* **`Ref` (Inbound Reference Count):** The number of distinct repository files that import or reference the module.
* **`MaxRef` (Maximum Reference Ceiling):** The highest inbound reference count found across the repository, serving as the normalization cap.

## Mathematical Mapping Formulas

The popularity metric $P$ is first normalized into a continuous range from $0.0$ to $1.0$:

$$P = \min\left(\frac{\text{Ref}}{\text{MaxRef}}, 1.0\right)$$

Using normalized popularity $P$, the shader computes pulse frequency (speed) and emissive intensity bounds (floor and ceiling):

### 1. Pulse Frequency (Hz)
Maintains controlled pulse dynamics between 0.5 Hz and 1.5 Hz to ensure visual stability without excessive strobing:

$$\text{Speed} = 0.5 + (P \times 1.0)$$

### 2. Emissive Floor (Minimum Intensity)
Highly referenced modules retain a high baseline emissive glow and never dim completely:

$$\text{MinIntensity} = 0.2 + (P \times 0.8)$$

### 3. Emissive Ceiling (Maximum Intensity)
Peak emissive output scales up to 4.0 for heavily referenced hub modules:

$$\text{MaxIntensity} = 1.5 + (P \times 2.5)$$

### 4. Frame-Level Shader Intensity Calculation
In the WebGL shader, a sinusoidal function evaluates the final frame intensity:

$$\text{EmissiveIntensity} = \text{MinIntensity} + \left( \sin(\text{Time} \times \text{Speed}) \times (\text{MaxIntensity} - \text{MinIntensity}) \right)$$

## Visual Rendering Tiers

| Module Classification | Inbound Reference Range | Pulse Frequency | Dynamic Emissive Range | Visual Effect |
| :--- | :--- | :--- | :--- | :--- |
| **Standard Module / Leaf Node** | Low In-Degree | 0.5 Hz | 0.2 $\rightarrow$ 1.5 | Gentle rhythmic shimmer. Retains primary category color with soft intensity variations. |
| **Central Architectural Hub** | High In-Degree | 1.5 Hz | 1.0 $\rightarrow$ 4.0 | High-intensity bloom saturation. Central core remains continuously bright, highlighting critical dependency bottlenecks. |

---

### Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**


# 2.1.I. External Dependency Rings

> **File Reference:** [`gitgalaxy/core/detector.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/detector.py)

> **Metric: External Library Import Count (`ImportHits`)**
>
> **Purpose:** Highlights modules with high external dependency counts.
>
> **Rationale:** Standard utility modules maintain self-contained logic, whereas integration modules or framework controllers pull in multiple external packages. Visualizing dependency load as surround rings allows developers to spot heavy integration points and potential dependency coupling risks at a glance.
>
> **Effect:** Renders dependency rings around file nodes in 3D visualization space.

## 2.1.I.1. Dependency Weight Thresholds

Self-contained files render as clean single nodes without surround rings. As a file imports external libraries, its dependency weight increases. To prevent visual noise from routine single imports, a threshold is enforced: surround rings only activate for high-dependency modules ("heavy lifters" and orchestration layers).

## 2.1.I.2. Input Metrics

* **`ImportHits`:** Total count of `import`, `require`, `include`, or package import directives identified by the static analyzer.
* **Activation Threshold:** **> 5 Imports**. Modules with 5 or fewer imports do not spawn dependency rings.

## 2.1.I.3. Mathematical Formulation: Ring Opacity and Thickness

Dependency rings evolve dynamically in visual opacity and thickness as import counts rise:

**1. Visual Opacity (Transparency)**
Opacity scales linearly from $0.0$ to $0.6$ over the range of 6 to 26 imports, capping at a maximum value of $0.6$:

$$\text{Opacity} = \min\left( \left(\frac{\text{ImportHits}}{26}\right) \times 0.6,\ 0.6 \right)$$

**2. Ring Width (Geometry Thickness)**
Geometry radius expands progressively with additional imports to indicate cumulative external coupling:

$$\text{TubeRadius} = \text{BaseWidth} + (\text{ImportHits} \times 0.1)$$

## 2.1.I.4. WebGL/WebGPU Rendering Specifications

* **Geometry Class:** `TorusGeometry`.
* **Tube Radius:** Scaled linearly by `ImportHits`.
* **Material Properties:** Translucent mesh material with `opacity` capped at $0.6$.
* **Rotational Orientation:** Ring meshes are tilted across randomized Euler axes to prevent overlapping coplanar visual artifacting and ensure clear visibility from all 3D camera viewpoints.

<br><br>

---

### Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**


# Authorship Distribution (Ownership Entropy)

> **File Reference:** [`gitgalaxy/metrics/signal_processor.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/metrics/signal_processor.py)

> **Metric: Shannon Entropy of Git Blame Data**
>
> **Purpose:** Measures the distribution of commit contributions across authors within a module to identify knowledge siloing vs. shared maintenance.
>
> **Rationale:** Module ownership is not about blaming individual contributors; it quantifies developer contribution concentration. Rather than relying on simple contributor headcounts, GitGalaxy uses Shannon Entropy to measure contribution dispersion. This entropy score maps to the Universal Risk Spectrum, highlighting single-author knowledge silos ("Bus Factor" risks) vs. highly distributed team maintenance.

## Contributor Concentration Principles

Authorship structure is evaluated along a spectrum of architectural concentration versus multi-contributor diffusion:

* **Low Entropy (Individual Ownership):** Commit volume is heavily concentrated with a single author. This reflects unified design intent, but introduces knowledge silo risk if the primary maintainer leaves.
* **High Entropy (Shared / Team Diffusion):** Commit volume is distributed across many authors. As multiple developers modify a module, architectural knowledge becomes shared across the team, indicating high-traffic community code.

## Input Metrics

* **`Authors`:** A map of author identifiers to commit counts for the target module.
* **`TotalCommits`:** Aggregate count of all commits recorded for the module.
* **`GlobalAuthorCount`:** Total number of unique contributors across the entire repository.

## Mathematical Formulation: Shannon Entropy

First, the analysis engine computes the proportion of total commits ($p_i$) made by contributor $i$:

$$p_i = \frac{\text{Commits}_i}{\text{TotalCommits}}$$

The engine then computes the Shannon Entropy ($H$) of the author distribution:

$$H = -\sum \left( p_i \times \log_2(p_i) \right)$$

Finally, the entropy value is scaled into a normalized score ranging from $0$ to $100$:

$$\text{OwnershipScore} = \min(H \times 32.0, 100.0)$$

## Advantages of Entropy-Based Modeling

Shannon Entropy resolves the "long tail" contributor anomaly:
* A file with 1 primary author (90% commits) and 1 minor contributor (10% commits) exhibits low entropy and high ownership clarity.
* A file with 1 primary author (90% commits) and 10 minor contributors (1% each) exhibits higher entropy due to frequent minor edits.

Simple linear counters rate both scenarios identically based on headcount. The Shannon Entropy model correctly identifies the second file as experiencing higher operational noise by measuring uncertainty in authorship distribution.

## Visual Classification & Metric Tiers

GitGalaxy maps the normalized ownership score across the standard 5-stop Universal Risk Spectrum:

| Score Range | Classification | Indicator Color | Architectural Definition |
| :--- | :--- | :--- | :--- |
| **0 – 20** | **Single Owner** | 🟦 **Deep Blue** | High centralization. Logic is maintained by a single primary author. |
| **21 – 60** | **Team Collaboration** | 🩵 **Cyan** $\rightarrow$ 🟨 **Yellow** | Core team maintenance. Responsibility is distributed among a small squad of maintainers. |
| **61 – 100** | **High Diffusion** | 🟧 **Orange** $\rightarrow$ 🟥 **Red** | Collective maintenance. The module receives frequent commits from many contributors across the organization. |

## Renderer Performance Scaling

By normalizing authorship distribution into a single scalar score ($0.0 - 100.0$) in the backend metrics engine (`signal_processor.py`), frontend rendering efficiency remains constant. 

Whether a module has 2 contributors or 2,000 contributors, the WebGPU engine translates the floating-point value into a color gradient without requiring multi-pass shaders or expensive per-author hash lookups, maintaining 60 FPS rendering performance across enterprise codebases.

<br><br>

---

### Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

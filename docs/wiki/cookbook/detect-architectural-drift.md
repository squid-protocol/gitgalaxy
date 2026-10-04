---
description: "Codebases do not break overnight; they degrade slowly. Over years of development, a clean microservice architecture will naturally drift back into a..."
---
# How to Detect Architectural Drift and Trojan Files

Codebases do not break overnight; they degrade slowly. Over years of development, a clean microservice architecture will naturally drift back into a monolithic "Big Ball of Mud" as developers cut corners to meet deadlines. 

Furthermore, sophisticated attackers often hide malicious scripts inside files that appear entirely normal to human reviewers (e.g., hiding an orchestration script inside a file named `utils.js`).

GitGalaxy detects both structural decay and malicious camouflage using **Biaxial Anomaly Detection** and **Z-Score Mathematics**, comparing every file against the mathematical norms of its native programming language.

## The Spectral Auditor

GitGalaxy uses an unsupervised Machine Learning algorithm (K-Means Clustering) trained on millions of files to define standard "Archetypes" (e.g., *The God Node*, *Declarative Glue*, *Async Orchestrator*).

When a file is scanned, the Spectral Auditor places it into a Global Archetype and calculates its "Drift" (measured in Interquartile Ranges, or IQR) from the center of that cluster. 

### 1. The Chimeric Drift Check (Refactoring Targets)
If a file sits perfectly between two distinct archetypes (a Delta of <= 0.9 IQR), the Spectral Auditor flags it as a "Chimeric" file. 

This mathematically proves a violation of the Single Responsibility Principle. The file is trying to do two completely different things (e.g., acting as both a database schema and an active network router), making it the perfect target for a refactoring sprint.

### 2. The Biaxial Trojan Check (Malicious Camouflage)
To find "Trojan" files, GitGalaxy compares the file's Global Drift against its Local Drift (how much it deviates from standard patterns within its specific language). 

If a file blends in perfectly on a global scale but heavily violates the conventions of its native language, the Biaxial Ratio spikes. 

```text
## 13. BIAXIAL ANOMALY & ARCHITECTURAL DRIFT

### 🚨 Biaxial Anomalies (Severe Anti-Patterns / Language Violations)
- `src/utils/logger.js` (JAVASCRIPT) | Biaxial Ratio: 2.45x
  * Global Archetype: `Declarative Glue` (Drift: 0.2 IQR)
  * Local Reality: `Network Orchestrator` (Drift: 3.8 IQR)
```

In the example above, the file pretends to be a simple declarative logger globally, but locally, it utilizes structural syntax matching a heavy network orchestrator. This massive Biaxial Ratio (2.45x) alerts security teams that `logger.js` is likely camouflaging a malicious data-exfiltration script.

> **Read the full technical specification:** [Spectral Audit](../02-11-spectral-audit.md)

---

**[⬅️ Back to Master Index](../index.md)**

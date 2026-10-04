---
description: "The `cash-account-cobol` repository represents a highly localized, monolithic financial transaction processor. Composed predominantly of COBOL (75%),..."
---
# AGENTS.md: cash-account-cobol Architectural Context & Engagement Rules

## 1. Information Flow & Purpose (The Executive Summary)
The `cash-account-cobol` repository represents a highly localized, monolithic financial transaction processor. Composed predominantly of COBOL (75%), the system handles basic CRUD operations for cash accounts (Add, Update, Credit, Debit, Delete). The information flow is entirely centralized: `CASH00.cbl` acts as the primary execution engine, pulling in static data structures from copybooks (`DCLCASH.cpy` and `DCLFRANK.cpy`). The architecture is a "Cluster 3" macro-species, though its extremely small footprint (Modularity 0.0, Assortativity 0.0) indicates a tightly coupled, single-purpose procedural script rather than a distributed application.

## 2. Notable Structures & Architecture
The dependency graph is exceptionally flat and relies on a strict hub-and-spoke topology.
* **Foundational Load-Bearers:** The copybooks `DCLCASH.cpy` and `DCLFRANK.cpy` serve as the foundational data definitions. Changes to these file structures represent a high risk of cascading breaks into the orchestrator.
* **Fragile Orchestrator:** `COBOL/CASH00.cbl` is the sole orchestrator. It possesses the highest fragility index, carrying all outbound dependencies and housing all business logic (e.g., `CASH-ACCT-UPDATE`, `CASH-ACCT-CREDIT`).

## 3. Security & Vulnerabilities
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits confirm the repository is secure from recognized structural threats. No malicious artifacts, obfuscated payloads, or binary anomalies were detected. Furthermore, the repository exhibits 0.0% exposure for Exploit Generation Surfaces and Weaponizable Injection Vectors, reflecting the isolated nature of the COBOL execution environment.

## 4. Outliers & Extremes
* **The God Node (`CASH00.cbl`):** This file is an extreme statistical outlier. It accounts for almost the entirety of the repository's mass (129.08) and risk (Cumulative Risk: 491.02). 
* **Algorithmic Density:** The subroutines within `CASH00.cbl` exhibit high static time complexity (e.g., `CASH-ACCT-UPDATE` evaluated at O(N^6)), indicating deep nesting or dense control flow paths typical of legacy procedural COBOL.
* **Blind Bottleneck:** `CASH00.cbl` registers a 100% Documentation Risk alongside its high blast radius (Severity: 20618.6). Autonomous agents and human maintainers modifying this file are operating with high systemic risk and minimal contextual guidance.
* **Design Slop:** `CASH00.cbl` contains 6 orphaned functions, contributing to its Tech Debt Exposure of 67.6%.

## 5. Recommended Next Steps (Refactoring for Stability)
When deploying autonomous agents or planning engineering cycles, prioritize the following actions to stabilize the architecture:

1. **Mitigate the Blind Bottleneck:** Mandate the generation of comprehensive, inline documentation for `COBOL/CASH00.cbl`. Explain the input/output expectations for each major paragraph (`CASH-ACCT-ADD`, `CASH-ACCT-UPDATE`) to reduce the 100% Documentation Risk.
2. **Decompose the Orchestrator:** To reduce the extreme cognitive load and algorithmic density in `CASH00.cbl`, evaluate extracting distinct operations (e.g., database read/write logic vs. business validation) into separate subprograms or clearly delineated, isolated paragraphs.
3. **Prune Dead Logic:** Investigate and safely remove the 6 orphaned functions identified within `CASH00.cbl`. Eliminating this design slop will immediately reduce the file's state flux and technical debt exposure.


---

**[⬅️ Back to Master Index](../index.md)**

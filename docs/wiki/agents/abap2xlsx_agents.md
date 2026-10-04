---
description: "You are operating within `abap2xlsx`, a heavily coupled ecosystem designed for Excel document generation and parsing."
---
# AGENTS.md

## 1. System Context & Paradigm
You are operating within `abap2xlsx`, a heavily coupled ecosystem designed for Excel document generation and parsing. 
* **Language Composition:** The logic is primarily ABAP (26.5%) orchestrating underlying XML document structures (71.0%). 
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species but exhibits a critical Architectural Drift Z-Score of 6.854. This means standard MVC or modular design patterns DO NOT APPLY. The architecture relies on a highly unique, bespoke control flow driven by massive, centralized orchestrator classes. Do not attempt to force standard design patterns onto this codebase.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** The core reader and converter classes (`load_worksheet`, `change_cell_style`, `loop_subtotal`) already operate at extreme time complexities (O(N^6) and O(2^N) recursive loops). You MUST NOT introduce additional nested loops or O(N^2+) complexity when modifying styling, parsing, or I/O functions.
* **Orchestrator Fragility:** Classes such as `zcl_excel_drawings.clas.abap` and the `zcl_excel_converter_result_*.clas.abap` suite are highly fragile coordinators with heavy outbound dependencies. Any changes to data contracts within these files require immediate verification of downstream integration.
* **Tech Debt Preservation:** `src/zcl_excel_style_changer.clas.abap` contains 95 orphaned functions and a 99.8% Tech Debt Exposure score. DO NOT autonomously attempt to prune, clean, or refactor this file unless explicitly instructed by the user.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive blast radii, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures or public APIs of these files:
* `src/zcl_excel_reader_2007.clas.abap` (Primary Reader - Extreme Mass)
* `src/zcl_excel_worksheet.clas.abap` (Primary Data Model - Extreme Mass)
* `src/not_cloud/zcl_excel_ole.clas.abap` (Key Person Silo - Lars Hvam)
* `src/zcl_excel_common.clas.abap` (Key Person Silo - Lars Hvam)
* `src/not_cloud/zcl_excel_converter.clas.locals_def.abap` (Blind Bottleneck - 100% Documentation Risk)
* `src/not_cloud/zcl_excel_converter_alv_grid.clas.abap` (Blind Bottleneck - 100% Documentation Risk)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts, 0 Agentic RCE funnels, and 0 Prompt Injection vectors. No critical weaponizable surfaces or supply chain anomalies exist. You may operate freely without triggering external firewall or Zero-Trust isolation protocols, provided you do not introduce external dependencies.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized ABAP knowledge to determine blast radius. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.

---

**[⬅️ Back to Master Index](../index.md)**

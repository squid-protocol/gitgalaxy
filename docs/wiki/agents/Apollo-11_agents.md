---
description: "You are operating within `Apollo-11`, a historically significant repository containing the original Apollo Guidance Computer (AGC) source code for the..."
---
# AGENTS.md: Apollo-11 Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `Apollo-11`, a historically significant repository containing the original Apollo Guidance Computer (AGC) source code for the Command Module (Comanche055) and Lunar Module (Luminary099). The codebase is overwhelmingly composed of AGC Assembly (69.5%) and Markdown documentation (30.1%).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 5.435. The code is highly monolithic, procedural, and tightly coupled by design, reflecting the extreme hardware constraints of the 1960s AGC. Modularity and Assortativity are 0.0. **CRITICAL:** Do NOT attempt to apply modern software engineering principles (like object-oriented design, MVC, or decoupling) to this codebase. Its structure is historically immutable.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity & Hardware Constraints:** The AGC code utilizes custom interpretative logic (e.g., `OPJUMP3` in `INTERPRETER.agc`) and extreme recursive/looping structures (`SMODECHK`, `SNAPLOOP`, `EXDAP1`) to maximize limited ROM/RAM. You MUST NOT attempt to "optimize" or "refactor" these algorithms for Big-O improvements. Any modifications must strictly adhere to the exact cycle-timing and memory banks expected by the physical AGC hardware.
* **Orchestrator Fragility:** Central dispatch files such as `TAGS_FOR_RELATIVE_SETLOC.agc` (43 outbound dependencies), `P20-P25.agc` (39 outbound dependencies), and `PINBALL_GAME_BUTTONS_AND_LIGHTS.agc` are massive, fragile orchestrators. Altering label names, memory addresses, or jump targets here will catastrophically break the program state.
* **Avoid Dead Code Pruning:** Files such as `DISPLAY_INTERFACE_ROUTINES.agc` and `INTERPRETER.agc` contain dozens of functions that static analysis may identify as "orphaned." DO NOT autonomously attempt to prune, format, or clean up these files. The AGC relies heavily on implicit bank switching, interrupt vectors, and hardcoded ROM jumps that static tools misinterpret as dead code.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes" possessing extreme cumulative risk, massive structural mass, or historical significance. 

**MANDATORY RULE:** You require explicit human permission before modifying the structural signatures, assembly instructions, or comments of these files:
* `Comanche055/PINBALL_GAME_BUTTONS_AND_LIGHTS.agc` (Extreme Mass: 2143.32, 100% Silo Risk by Zachary Pedigo)
* `Luminary099/P20-P25.agc` (Extreme Mass: 2103.24, 32.2% Cognitive Load)
* `Comanche055/INTERPRETER.agc` & `Luminary099/INTERPRETER.agc` (The AGC virtual machine / dispatchers)
* `Comanche055/KALCMANU_STEERING.agc` (Highest Cumulative Risk: 494.03)
* `Luminary099/EXECUTIVE.agc` & `Comanche055/EXECUTIVE.agc` (The core task/job schedulers)
* `Luminary099/R31.agc` (House of Cards / Blind Bottleneck)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (HISTORICAL ARCHIVE).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Almost the entirely of the repository relies on raw memory manipulation, direct bank switching, and hardware-level register access (e.g., `PINBALL_NOUN_TABLES.agc` and `POWERED_FLIGHT_SUBROUTINES.agc`). Treat all variables as direct physical memory addresses.
2. **Exploit Generation Surface:** Files like `DISPLAY_INTERFACE_ROUTINES.agc` and `EXTENDED_VERBS.agc` parse DSKY (Display & Keyboard) input. While not an internet-facing "exploit" surface, incorrect formatting here causes physical hardware faults.
3. **Supply Chain:** The 5 "Binary Anomalies" flagged by X-Ray are likely historical binary artifacts, schematics, or compiled roms. Do not alter them.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized Assembly knowledge to determine blast radius. AGC Assembly is a highly specialized architecture.

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

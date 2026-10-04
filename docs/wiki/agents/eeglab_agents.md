---
description: "You are operating within `eeglab`, a widely used open-source environment for electrophysiological signal processing. The repository is overwhelmingly..."
---
# AGENTS.md: eeglab Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `eeglab`, a widely used open-source environment for electrophysiological signal processing. The repository is overwhelmingly composed of MATLAB scripts and functions (95.8%), focusing heavily on Independent Component Analysis (ICA), time/frequency analysis, and artifact rejection.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 9.022. The network topology demonstrates a completely flat Modularity (0.0) and Assortativity (0.0). This is characteristic of a traditional MATLAB architecture, relying on a massive global namespace of functions rather than deeply nested object-oriented hierarchies. 
* **Core Rule:** Do NOT attempt to introduce modern software paradigms (like heavy class-based encapsulation, dependency injection, or micro-services) into the core function libraries. The architecture is locked into MATLAB's path-based function resolution and relies on global data structures (e.g., the `EEG` and `ALLEEG` structs).

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core mathematical operations (`runica.m`, `topoplot.m`, `newcrossf.m`, and `eeg_eval.m`) exhibit extreme O(2^N) recursive time complexities in static analysis. This reflects heavy compute loads, tensor math, and deep recursive data validation. You MUST NOT introduce unbounded loops, inefficient memory reallocation (e.g., growing matrices inside loops), or blocking UI operations inside these hot paths. 
* **Orchestrator Fragility:** Central orchestrators like `eeglab.m` (354 DB Complexity) and `eeg_checkset.m` (273 DB Complexity) are highly fragile. Modifying how datasets are validated or how the main GUI state is synchronized requires extreme caution and extensive regression testing against diverse EEG data formats.
* **Avoid Dead Code Pruning:** Directories like `functions/@mmo/` and `functions/@memmapdata/` contain overloaded MATLAB class methods (`display.m`, `length.m`, `isnumeric.m`). Static analysis may flag these as "orphaned functions" or "dead code" because they are invoked dynamically via MATLAB's object-oriented method dispatch. DO NOT autonomously prune or restructure these files.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream mathematical verification before modifying the structural signatures, matrix operations, or public APIs of these files:
* `functions/sigprocfunc/runica.m` (Massive Structural Mass: 8715.36. Core ICA algorithm. Key Person Silo - 100% isolated ownership by Arnaud Delorme).
* `functions/adminfunc/eeg_checkset.m` (Highest data gravity and exploit surface due to dynamic evaluation. Validates core data structures).
* `functions/sigprocfunc/topoplot.m` (Core 2D/3D topographic mapping function. Extremely dense rendering logic).
* `functions/popfunc/pop_chanedit.m` (Key Person Silo - 100% isolated ownership by Arnaud Delorme. Critical for managing electrode coordinate metadata).
* `functions/@mmo/*` (Severe Blind Bottlenecks - High blast radius, 100% Documentation Risk. These files manage memory-mapped objects essential for handling datasets larger than system RAM).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH MATLAB `EVAL` CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Dynamic Execution Surface:** Files such as `functions/adminfunc/eeg_checkset.m` possess a 100% Exposure score for Exploit Generation. Because EEGLAB historically utilizes MATLAB's `eval()` and `evalin()` functions to execute dynamic pipeline history and GUI callbacks, you MUST ensure strict sanitization of any string inputs passed to execution contexts to prevent arbitrary code execution on the host machine.
2. **Hardcoded Payload Artifacts:** `functions/supportfiles/channel_location_files/neuroscan/cap128.asc` tripped hardcoded payload signatures (100% Exposure). DO NOT flag this as a leaked secret or exploit payload; it is a standard plaintext electrode coordinate template used for EEG channel mapping.
3. **Memory Management:** The `@mmo` (Memory Mapped Object) classes handle raw memory constraints. Modifications here must strictly respect MATLAB's memory boundaries to prevent out-of-memory (OOM) crashes during heavy compute.

## 5. Environmental Tooling (The Oracle)
Do not guess MATLAB path resolution, hallucinate tensor matrix dimensions, or rely on generalized OOP knowledge to determine blast radius within this 84k+ LOC signal processing framework. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

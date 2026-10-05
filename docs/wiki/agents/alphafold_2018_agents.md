---
description: "You are operating within `alphafold_2018`, a localized Machine Learning and heavy-compute ecosystem primarily composed of Python (42.4%) and massive..."
---
# AGENTS.md: alphafold_2018 Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `alphafold_2018`, a localized Machine Learning and heavy-compute ecosystem primarily composed of Python (42.4%) and massive binary checkpoint files (39.4%). 
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species with a high Architectural Drift Z-Score of 4.664. The architecture is defined by localized GPU memory allocation and isolated tensor math orchestration rather than standard web or application design patterns. Standard MVC, decoupling, or async web patterns DO NOT APPLY here. 

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core neural network construction and parsing files (`alphafold_casp13/contacts_network.py`, `alphafold_casp13/config_dict.py`, and `alphafold_casp13/two_dim_convnet.py`) inherently operate at extreme O(2^N) recursive time complexities to build computational graphs. You MUST NOT introduce additional nested loops or O(N^2+) complexity during graph construction or data processing steps.
* **Orchestrator Fragility:** Execution coordinators such as `alphafold_casp13/contacts.py` (9 outbound dependencies) and `alphafold_casp13/paste_contact_maps.py` (6 outbound dependencies) are highly fragile orchestrators. Any changes to data contracts, tensor shapes, or hyperparameter schemas within these files require immediate, comprehensive verification.
* **Binary Artifact Avoidance:** This repository contains heavy "Dark Matter" in the form of TensorFlow saved models (`.pb`) and motion capture data (`.h5`). You MUST NOT attempt to read, parse, or autonomously modify these binary files. 
* **Avoid Tech Debt Pruning:** Files such as `alphafold_casp13/config_dict.py` and `alphafold_casp13/secstruct.py` exhibit 99%+ Tech Debt Exposure scores. DO NOT autonomously attempt to prune or "clean up" these files unless explicitly instructed, as the model evaluation scripts depend tightly on their current exact state.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, or act as "Blind Bottlenecks" (deeply embedded logic with high documentation risk). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, tensor dimensions, or public APIs of these files:
* `alphafold_casp13/run_eval.sh` (Highest Cumulative Risk: 489.81, 100% Cognitive Load Exposure)
* `alphafold_casp13/contacts_experiment.py` (Blind Bottleneck - Severity 3030.3, 100% Doc Risk)
* `alphafold_casp13/contacts.py` (Blind Bottleneck - 100% Doc Risk)
* `alphafold_casp13/contacts_network.py` (Heavy Mass: 680.36, 100% Doc Risk)
* `alphafold_casp13/contacts_dataset.py` (High Risk and core I/O latency)
* `alphafold_casp13/two_dim_resnet.py` (Blind Bottleneck)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts, 0 Agentic RCE funnels, and 0 Prompt Injection vectors. 

**CRITICAL WARNINGS:** 1. **Systemic Risk (High):** The AI components inside this repository are deeply embedded with a massive Blast Radius (PageRank: 30.303). Hallucinations or incorrect tensor dimension adjustments here will cascade catastrophically across the computational graph, leading to Out-Of-Memory (OOM) errors or silent gradient failures.
2. **Raw Memory / Compute:** While no explicit raw memory manipulation (like C-pointers) is present in the Python layer, you must treat all array resizing, reshaping, and broadcasting operations as highly sensitive memory operations.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized Python/TensorFlow knowledge to determine blast radius. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

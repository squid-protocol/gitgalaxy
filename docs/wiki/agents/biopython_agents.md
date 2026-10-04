---
description: "You are operating within `biopython`, a massive computational biology and bioinformatics framework composed primarily of Python (60.6%) backed by..."
---
# AGENTS.md: biopython Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `biopython`, a massive computational biology and bioinformatics framework composed primarily of Python (60.6%) backed by highly optimized C extensions (2.0% by file count, but structurally load-bearing).
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species with a high Architectural Drift Z-Score of 5.142. The network topology demonstrates excellent Modularity (0.7089), meaning packages (e.g., `Bio.PDB`, `Bio.Align`) are cleanly separated. However, it exhibits negative assortativity (-0.3021), indicating that within those modules, the architecture relies on fragile, highly connected hub nodes (`__init__.py` files and core parsers). Do not attempt to force deep hierarchical dependencies across distinct biological domains.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core alignment algorithms (`Bio/Align/_pairwisealigner.c`) and clustering logic (`Bio/Cluster/cluster.c`) contain deep recursive structures and extreme database complexities (e.g., the `svd` function has a DB Complexity of 372). You MUST NOT attempt to "optimize" or introduce O(N^2+) complexity into these C extensions or the Python alignment/substitution matrix initialization steps.
* **Orchestrator Fragility:** Module initializers such as `Bio/PDB/__init__.py` (22 outbound dependencies) and `Bio/Align/__init__.py` (16 outbound dependencies) act as central coordinators. Any changes to data contracts, exported methods, or lazy-loading strategies within these files require immediate, comprehensive verification of downstream integration.
* **Avoid Dead Code Pruning:** Parsers and test suites such as `Bio/Blast/_parser.py` (170 orphaned functions) and `Tests/test_SeqIO.py` (166 orphaned functions) contain a high volume of unreferenced logic. DO NOT autonomously attempt to prune, format, or clean up these files. Bioinformatics format parsers rely on dynamic dispatch, reflection, and exhaustive state machine cases that static analysis tools misinterpret as dead code.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, C-bindings, or public APIs of these files:
* `Bio/Align/_pairwisealigner.c` (Massive Structural Mass: 10178.54, Key Person Silo - 100% isolated ownership by `mdehoon`)
* `Bio/PDB/internal_coords.py` (Extreme Mass: 3935.86, Key Person Silo - 100% isolated ownership by `Peter J. A. Cock`)
* `Bio/SeqIO/InsdcIO.py` (Key Person Silo - 100% isolated ownership by `Peter J. A. Cock`)
* `Bio/Nexus/Nexus.py` (Highest Cumulative Risk: 552.78)
* `Tests/test_SeqIO.py` (Severe Blind Bottleneck - High Blast Radius with 100% Documentation Risk)
* `Bio/PDB/vectors.py` (Extreme Volatility Hotspot - 54.09% Churn, 99.4% Tech Debt)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH PARSER CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:** 1. **Exploit Generation Surface:** Files such as `Bio/Affy/CelFile.py`, `Bio/AlignIO/EmbossIO.py`, and `Bio/Align/bigbed.py` possess a 100% Exposure score for Exploit Generation Surface. Because Biopython is tasked with parsing untrusted, external biological data formats (which are notoriously complex and poorly specified), you MUST ensure strict input sanitization, buffer boundary checking (especially in C extensions), and safe XML/Regex parsing to prevent arbitrary code execution or denial-of-service via malformed files.
2. **Hardcoded Payload Artifacts:** `Tests/test_Entrez_online.py` and `Tests/test_Entrez.py` contain hardcoded payloads. DO NOT flag these as leaked secrets or attempt to remove them; they are likely dummy NCBI Entrez API keys or test email addresses required for the CI pipeline.
3. **Supply Chain:** There are 26 binary anomalies identified by X-Ray. Given the domain, these are almost certainly binary test fixtures (e.g., `.sff`, `.bgz`, or compressed archives). Do not alter or attempt to scan these blobs.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized Python knowledge to determine blast radius within this 288k+ LOC scientific codebase. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

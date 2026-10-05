---
description: "You are operating within `blast`, the NCBI Basic Local Alignment Search Tool repository, primarily composed of C++ (40.1%) and C (11.6%)."
---
# AGENTS.md: blast Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `blast`, the NCBI Basic Local Alignment Search Tool repository, primarily composed of C++ (40.1%) and C (11.6%).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 5.971. The network topology demonstrates excellent Modularity (0.7297), indicating distinct boundaries between the algorithmic core (`src/algo/blast/core`), the C++ API wrapper (`src/algo/blast/api`), and application-level scripts. However, Assortativity is negative (-0.0679), meaning these modules rely heavily on a few central "hub" headers. Do not attempt to refactor the core C structs into C++ objects; the C core must remain isolated and ABI-stable.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core alignment heuristics (`Blast_RedoAlignmentCore_MT` in `blast_kappa.c` and `alp_sim::calculate_main_parameters2m`) operate at extreme O(N^6) recursive time complexities with massive Database Complexities. You MUST NOT introduce additional nested loops, dynamic memory allocations, or O(N^2+) complexity inside the core sequence scanning or gap alignment routines (`blast_gapalign.c`, `blast_nascan.c`).
* **Orchestrator Fragility:** Unit tests and API wrappers such as `traceback_unit_test.cpp` (44 outbound dependencies) and `blast_options_builder.cpp` act as highly fragile orchestrators. Any changes to data contracts, parameter defaults, or memory ownership within the C API will cause cascading breakages in the C++ wrappers and testing pipelines.
* **Avoid Dead Code Pruning:** The `blast_options_cxx.cpp` and `blast_options_local_priv.hpp` files contain hundreds of orphaned functions. DO NOT autonomously attempt to prune, format, or clean up these files. The BLAST API maintains extensive backwards-compatibility layers and deprecated option getters/setters that must remain intact.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream test/benchmark verification before modifying the structural signatures, `void*` casts, or public APIs of these files:
* `src/algo/blast/core/hspfilter_mapper.c` (Extreme Mass: 5271.32, Key Person Silo - 100% isolated ownership by Grzegorz Boratyn)
* `src/algo/blast/core/blast_stat.c` (Key Person Silo - 100% isolated ownership by Christiam Camacho)
* `src/app/blast/update_blastdb.pl` (Highest Cumulative Risk: 606.01, 100% Exploit Generation Surface due to raw parsing)
* `src/algo/blast/api/remote_blast.cpp` (Key Person Silo - 100% isolated ownership by Amelia Fong, extreme API integration risk)
* `src/algo/blast/api/blast_node.cpp` (Extreme Volatility Hotspot: 100% Churn)
* `src/algo/blast/gumbel_params/sls_alp_data.hpp` (Severe Blind Bottleneck - High Blast Radius with 100% Documentation Risk)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Files within `src/algo/blast/api/` (e.g., `magicblast.cpp`, `split_query_cxx.cpp`) and `src/algo/blast/gumbel_params/` rely heavily on raw pointer manipulation (`10.0% Exposure`). Any `memcpy`, pointer arithmetic, or buffer logic here must be rigorously scrutinized for out-of-bounds access or segmentation faults.
2. **Exploit Generation Surface:** The Perl script `src/app/blast/update_blastdb.pl` and several C lookup files (`blast_nalookup.c`, `blast_nascan.c`) possess a 20-100% Exploit Generation Surface score. Because this code parses untrusted, external biological sequence databases and metadata, you must ensure strict input sanitization and boundary checking to prevent buffer overflows or malicious payload execution.
3. **Hardcoded Payload Artifacts:** `src/app/pubseq_gateway/server/test/ssl/psg.crt` and `.key` contain hardcoded SSL payloads. DO NOT flag these as leaked secrets; they are explicit test fixtures for the PubSeq Gateway server.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate include paths, or rely on generalized C/C++ knowledge to determine blast radius within this 169k+ LOC repository. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

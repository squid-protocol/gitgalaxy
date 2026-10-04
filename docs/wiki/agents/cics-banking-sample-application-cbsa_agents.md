---
description: "You are operating within `cics-banking-sample-application-cbsa`, a heterogeneous CICS banking application combining a legacy COBOL backend (17.3%) with..."
---
# AGENTS.md: cics-banking-sample-application-cbsa Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `cics-banking-sample-application-cbsa`, a heterogeneous CICS banking application combining a legacy COBOL backend (17.3%) with a modern Java SpringBoot/Liberty API layer (21.3%) and a web frontend.
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 4.814. The network topology demonstrates a Hub-and-Spoke model with a negative Assortativity (-0.4931). This indicates a highly centralized structure where the Java API layer acts as fragile orchestrators directly coupling to massive, isolated COBOL programs and copybooks (the hubs). Do not attempt to force deep object-oriented abstractions onto the COBOL layer or bypass the defined data interfaces (`src/webui/src/main/java/com/ibm/cics/cip/bankliberty/datainterfaces/`).

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core COBOL logic blocks (`GCD010` in `BNK1CCA.cbl`, `SM010` in `BNK1CCS.cbl`) operate at extremely high recursive time complexities in static analysis due to deep legacy control flows and database/transaction handling. You MUST NOT introduce additional nested loops or alter the existing `PERFORM` and `GO TO` structures without strict verification against CICS transaction timeout constraints.
* **Orchestrator Fragility:** Java orchestrators like `Customer.java` (37 outbound dependencies) and `WebController.java` (36 outbound dependencies) are highly fragile. Any changes to JSON data contracts or SpringBoot annotations within these files require immediate verification of both the frontend UI and the downstream CICS/COBOL linkage.
* **Avoid Dead Code Pruning:** The Java JSON payload definitions (e.g., `DelaccJson.java`, `CreaccJson.java`) and specific COBOL logic blocks contain functions flagged as "orphaned." DO NOT autonomously attempt to prune, format, or clean up these files. These are data-transfer objects (DTOs) and copybook includes serialized automatically by the framework; static analysis misinterprets them as dead code.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream CICS integration testing before modifying the structural signatures, database queries (SQLCA/DB2), or public interfaces of these files:
* `src/base/cobol_src/BNK1DCS.cbl` and `BNK1CCS.cbl` (Massive Structural Mass, Key Person Silos - 100% isolated ownership by JAMOGRAD)
* `src/base/cobol_src/CRECUST.cbl` (Highest Cumulative Risk: 573.96, handles critical customer creation logic)
* `src/base/cobol_copy/ABNDINFO.cpy` (Severe Blind Bottleneck - 26 inbound connections, flying blind with 87.9% Doc Risk; changes here shatter abend handling globally)
* `src/base/cobol_copy/RESPSTR.cpy` (High State Flux: 35.5%, core CICS response string mapping)
* `src/Z-OS-Connect-Customer-Services-Interface/src/main/java/com/ibm/cics/cip/bank/springboot/customerservices/controllers/WebController.java` (Primary Java Orchestrator)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH ENVIRONMENT CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Hardcoded Payload Artifacts:** `src/bank-application-frontend/.env` possesses a 100% Exposure score for Hardcoded Payload Artifacts. Be extremely careful not to commit real credentials, API keys, or production endpoints to this file.
2. **Data Gravity & Database Complexity:** COBOL programs handling data (`BANKDATA.cbl`, `RESPSTR.cpy`) exhibit massive database complexity. When modifying SQL queries or VSAM file reads/writes, ensure strict parameter validation to prevent data corruption.
3. **Supply Chain:** There are 72 unknown dependencies bypassing the Zero-Trust whitelist (likely Maven/NPM packages). Do not add or bump external dependencies (`pom.xml` or `package.json`) without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess CICS channel formats, hallucinate COBOL copybook layouts, or rely on generalized Java knowledge to determine blast radius within this cross-language mainframe application. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

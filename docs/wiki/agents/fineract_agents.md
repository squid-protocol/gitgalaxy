---
description: "You are operating within `fineract`, an open-source core banking platform. The repository is massively dominated by Java (91.6%), structured around..."
---
# AGENTS.md: fineract Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `fineract`, an open-source core banking platform. The repository is massively dominated by Java (91.6%), structured around Spring Framework concepts, JPA repositories, and complex financial business logic.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 7.998. The network topology demonstrates a completely flat Modularity (0.0) and Assortativity (0.0). This indicates an extremely monolithic, "hub-and-spoke" architecture where financial entities (loans, savings) are deeply coupled to central god-classes and orchestrator services. 
* **Core Rule:** Maintain strict adherence to the existing domain-driven boundaries (e.g., `portfolio.loanaccount`, `portfolio.savings`). Do NOT attempt to decouple foundational orchestrators or introduce asynchronous messaging into synchronous transaction paths unless explicitly directed; the architecture requires atomic, ACID-compliant database operations for financial integrity.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core scheduling and utility functions (`update` and `constructRecurrence` in `Calendar.java`, `decode` in `FineractErrorDecoder.java`, `processCommand` in `CommandSourceService.java`) operate at extreme O(2^N) recursive time complexities in static analysis. You MUST NOT introduce unbounded recursive loops, heavy synchronous iterations, or N+1 queries when calculating amortization schedules, interest accruals, or progressive loan configurations.
* **Orchestrator Fragility:** Central orchestrators such as `LoanWritePlatformServiceJpaRepositoryImpl.java` (207 outbound dependencies), `LoanAccountConfiguration.java` (170 outbound), and `LoansApiResource.java` (168 outbound) are highly fragile. Any changes to loan lifecycle state machines, API contracts, or repository wiring require immediate, comprehensive verification via the integration test suite.
* **Avoid Dead Code Pruning:** Files like `CommandWrapperBuilder.java` (224 orphaned functions), `LoanStepDef.java` (176 orphaned functions), and `FineractFeignClient.java` contain logic flagged as "dead code." DO NOT autonomously attempt to prune, format, or clean up these files. Fineract heavily utilizes dynamic Spring bean wiring, reflection, and Cucumber BDD step definitions that bypass static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream integration testing before modifying the structural signatures, financial formulas, or public APIs of these files:
* `LoanRepaymentScheduleInstallment.java` (Highest Cumulative Risk: 634.57. Manages critical repayment math).
* `ProgressiveEMICalculator.java` (Extreme Volatility Hotspot: 83.6% Churn. Core math for progressive loan EMIs).
* `Loan.java` & `SavingsAccount.java` (Massive Structural Mass and Data Gravity. These entities act as the foundational pillars of the database schema).
* `SavingsAccountWritePlatformServiceJpaRepositoryImpl.java` (Key Person Silo - 100% isolated ownership by Juan-Pablo-Alvarez).
* `BatchHelper.java` (Key Person Silo - 100% isolated ownership by Adam Saghy in the test suite).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Weaponizable Injection Vectors:** Test and infrastructure utilities like `LocalContentStorageUtil.java` and `ReportsTest.java` possess 100% Exposure for Injection Vectors. Because Fineract handles bulk imports (e.g., CSV/Excel) and dynamic reporting, you MUST ensure strict input validation and parameterized queries to prevent SQL Injection, Path Traversal, or arbitrary file writes.
2. **Hardcoded Payload Artifacts:** `fineract-provider/src/main/resources/keystore.jks` tripped hardcoded payload signatures. DO NOT flag this as a leaked secret; it is an explicit cryptographic fixture required for local development and testing.
3. **Data Gravity:** SQL migration files (e.g., `0003-mifosx-permissions-and-authorisation-utf8.sql` and `load_sample_data.sql`) exhibit massive database complexity. Do not alter historical Liquibase/Flyway migrations; append new changes as strictly sequential migration scripts.

## 5. Environmental Tooling (The Oracle)
Do not guess Spring Data JPA entity mappings, hallucinate Loan/Savings interest calculations, or rely on generalized Java knowledge to determine blast radius within this 500k+ LOC financial system. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

---
description: "You are operating within `gradle`, a highly complex build automation tool. The repository is massive (1.48M+ LOC) and is primarily composed of Java..."
---
# AGENTS.md: gradle Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `gradle`, a highly complex build automation tool. The repository is massive (1.48M+ LOC) and is primarily composed of Java (56.2%), Groovy (33.7%), and Kotlin (7.3%). 
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 6.859. The network topology demonstrates high Modularity (0.6598) but neutral Assortativity (0.0). This indicates a highly modular but monolithic "hub-and-spoke" architecture where discrete subprojects (e.g., `platforms/core-configuration`, `platforms/software/dependency-management`) are heavily reliant on core orchestration services and registry models.
* **AI & Machine Learning Topology:** The repository contains a "Local Sovereignty" integration representing isolated, heavy compute tasks. Do not modify these components without rigorous verification.
* **Core Rule:** Maintain strict adherence to Gradle's internal API boundaries. Do NOT introduce standard direct instantiations where dependency injection, convention mapping (`ConventionAwareHelper`), or service scopes (`BuildScopeServices`) are expected. 

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core file system traversal and collection mechanics (`ReproducibleDirectoryWalker.java`, `AntFileCollectionMatchingTaskBuilder.java`, and `DuplicateHandlingCopyActionDecorator.java`) operate at extreme recursive time complexities (O(2^N) in static analysis) due to deep directory graph resolution and transformation chains. You MUST NOT introduce unbounded recursive loops, synchronous blocking operations, or excessive object allocations on the critical path of file collections or dependency graph resolution.
* **Orchestrator Fragility:** Central orchestrators such as `BuildProgressListenerAdapter.java` (261 outbound dependencies), `BuildScopeServices.java` (245 outbound), and `DefaultProject.java` are highly fragile. Modifying tooling API progress listeners, core service registries, or project configuration lifecycles requires immediate, comprehensive verification via the integration test suites (`integTest`).
* **Avoid Dead Code Pruning:** The repository contains massive volumes of logic flagged as "dead code" or "orphaned functions" (e.g., `AsmBackedClassGeneratorTest.java`, `StartParameter.java`, `DefaultProject.java`). DO NOT autonomously attempt to prune, format, or clean up these files. Gradle relies heavily on bytecode generation (ASM), Groovy metaprogramming, and dynamic Kotlin DSL resolution that completely bypasses static dependency analysis.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or represent 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream integration testing before modifying the structural signatures, build lifecycles, or public APIs of these files:
* `subprojects/core/src/test/groovy/org/gradle/api/internal/tasks/DefaultTaskContainerTest.groovy` (Highest Cumulative Risk: 625.41. Validates core task resolution logic).
* `platforms/software/dependency-management/src/integTest/groovy/org/gradle/integtests/resolve/catalog/VersionCatalogExtensionIntegrationTest.groovy` (Key Person Silo - 100% isolated ownership by Octavia Togami. Critical for dependency version catalog resolution).
* `platforms/software/dependency-management/src/integTest/groovy/org/gradle/integtests/resolve/verification/DependencyVerificationSignatureCheckIntegTest.groovy` (Key Person Silo - 100% isolated ownership by József Bartók. Critical for supply chain security and signature verification).
* `platforms/ide/tooling-api/src/crossVersionTestModels/java/org/gradle/integtests/tooling/r930/FetchCustomModelPerProjectAction.java` (High Logic Bomb & Injection Surface risk. Used for backward compatibility testing of the Tooling API).
* `platforms/software/build-init/src/main/java/org/gradle/buildinit/tasks/InitBuild.java` (Extreme Volatility Hotspot: 72.4% Churn).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface & Injection Vectors:** Files related to the Tooling API cross-version tests (`FetchGradleBuildAction.java`, `FetchUnknownModelAction.java`) and file access tracking (`SingleDepthFileAccessTracker.java`) possess 100% Exposure for Injection Vectors. Ensure any modifications to file path resolution, custom model fetching, or build arguments strictly sanitize inputs to prevent Directory Traversal or Command Injection.
2. **Hardcoded Payload Artifacts:** Several `.gpg` and `.asc` files in documentation snippets and dependency verification tests (e.g., `secKeyRingFile.gpg`, `pubring.gpg`) tripped hardcoded payload signatures. DO NOT flag these as leaked secrets; they are explicit cryptographic fixtures required for testing Gradle's artifact signing and verification features.
3. **Supply Chain:** There are 21 binary anomalies identified by X-Ray (primarily test fixture archives and native binaries). Do not alter or attempt to scan these binary blobs without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess configuration cache serialization mechanics (`ConfigurationCacheCodecs.kt`), hallucinate Groovy AST visitor behaviors (`RestrictiveCodeVisitor.java`), or rely on generalized Java knowledge to determine blast radius within this 1.4M+ LOC build system. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

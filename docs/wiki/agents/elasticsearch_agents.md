---
description: "You are operating within `elasticsearch`, a highly complex, distributed search and analytics engine. The repository is massively scaled (4.4M+ LOC) and..."
---
# AGENTS.md: elasticsearch Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `elasticsearch`, a highly complex, distributed search and analytics engine. The repository is massively scaled (4.4M+ LOC) and heavily dominated by Java (85.7%), supported by robust build tooling and testing frameworks.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 7.14. The network topology demonstrates a completely flat Modularity (0.0) and negative Assortativity (-0.3591). This indicates a highly coupled, monolithic core (hub-and-spoke model) where centralized orchestration nodes control isolated plugins and modules. 
* **AI & Machine Learning Topology:** The repository integrates "Tool-Augmented LLM (Level 3)" patterns. While these AI integrations act as isolated components, they possess a high blast radius if prompt injection occurs. Do NOT bypass established LLM tool-binding safeguards.
* **Core Rule:** Maintain strict boundaries between the core server execution paths and the `x-pack` plugins. Do NOT attempt to decouple foundational orchestrators or introduce unverified dependencies; the architecture relies heavily on tightly synchronized execution, strict classloading rules, and internal networking instrumentation.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Several evaluation operators (`evaluator` in `EvalBenchmark.java`, `score` in `VectorScorerOSQBenchmark.java`) and Gradle build plugins (`ElasticsearchJavaModulePathPlugin.java`) operate at O(2^N) recursive time complexities in static analysis. You MUST NOT introduce unbounded recursive loops, heavy synchronous blocking operations, or massive object allocations on the critical path of query execution, indexing, or the build chain.
* **Orchestrator Fragility:** Central orchestrators such as `Security.java` (468 outbound dependencies), `MachineLearning.java` (464 outbound dependencies), and `ActionModule.java` are highly fragile. Modifying plugin registration, security bootstrapping, or query compilation stages requires immediate, comprehensive verification via the massive integration test suite.
* **Avoid Dead Code Pruning:** The `x-pack` testing suites (e.g., `FieldNameUtilsTests.java` with 247 orphaned functions, `AnalyzerTests.java` with 231) contain logic flagged as "dead code." DO NOT autonomously attempt to prune or format these files. Elasticsearch testing utilizes extensive reflection, dynamic test case generation, and JUnit runners that bypass static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream integration/performance testing before modifying the structural signatures, I/O handling, or public APIs of these files:
* `build-tools/src/main/java/org/elasticsearch/gradle/testclusters/ElasticsearchNode.java` (Highest Cumulative Risk: 734.32, 100% Logic Bomb and Injection Surface exposure. Controls the testing cluster lifecycle).
* `libs/entitlement/src/main/java/org/elasticsearch/entitlement/config/FileInstrumentation.java` & `NetworkInstrumentation.java` (Key Person Silos - 100% isolated ownership by Jack Conradson. Highest Data Gravity. Modifying these directly impacts the security manager and network isolation capabilities).
* `server/src/main/java/org/elasticsearch/index/shard/IndexShard.java` (Massive Structural Mass and Key Person Silo. Core shard lifecycle management).
* `server/src/test/java/org/elasticsearch/cluster/ClusterStateTests.java` (Key Person Silo - 100% isolated ownership by David Turner. Heavily verifies cluster state replication).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Obfuscation & Evasion Surface:** The repository utilizes ANTLR-generated lexers and parsers (`PainlessLexer.java`, `PromqlBaseLexer.java`, `EqlBaseLexer.java`) which flag for high obfuscation exposure. Do NOT modify these generated files directly; any changes to the query languages (Painless, ES|QL, EQL, KQL) must be made in the grammar (`.g4`) files.
2. **Exploit Generation Surface & Injection Vectors:** Build tooling (`ElasticsearchTestBasePlugin.java`), CLI actions (`InstallPluginActionTests.java`), and node orchestrators (`ElasticsearchNode.java`) possess 100% Exposure for Injection Vectors. Because Elasticsearch manages distributed processes and file system access, ensure any modifications to CLI arguments or process spawning strictly sanitize inputs to prevent Command Injection.
3. **Hardcoded Payload Artifacts:** Files such as `private-ca.key`, `private-cert1.p12`, and `test-client.crt` in `build-tools-internal` tripped hardcoded payload signatures. DO NOT flag these as leaked secrets; they are explicit cryptographic test fixtures required for verifying TLS/SSL transport behavior.
4. **Supply Chain:** There are 56 binary anomalies identified by X-Ray and 9 unknown dependencies bypassing the Zero-Trust whitelist. Do not alter binary test artifacts or bump external Gradle dependencies without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess Lucene indexing mechanics, hallucinate Painless scripting compilation stages, or rely on generalized Java knowledge to determine blast radius within this 4M+ LOC distributed system. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

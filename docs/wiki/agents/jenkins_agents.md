---
description: "You are operating within `jenkins`, a massive (1.25M+ LOC), highly mature continuous integration and delivery server. The repository is heavily..."
---
# AGENTS.md: jenkins Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `jenkins`, a massive (1.25M+ LOC), highly mature continuous integration and delivery server. The repository is heavily dominated by Java (66.5%), supported by a massive volume of HTML (20.3%) and XML (15.3%) which comprise the Stapler/Jelly UI rendering layer.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 8.081. The network topology demonstrates a completely flat Modularity (0.0) and Assortativity (0.0). This indicates a quintessential "hub-and-spoke" monolith where almost all extension points, jobs, and configurations converge on a central set of God Classes within the `hudson.model.*` and `jenkins.model.*` namespaces.
* **Core Rule:** Maintain strict adherence to Jenkins' established Extension Point and Plugin architectures. Do NOT attempt to decouple foundational orchestrators (`Jenkins.java`, `PluginManager.java`) or introduce asynchronous messaging into synchronous initialization/configuration paths. The system heavily relies on Stapler for URL-to-object routing via reflection.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core lifecycle and routing functions (`configure` and `updateNodeList` in `Jenkins.java`, `doConfigSubmit` in `Job.java`, `get` in `User.java`) operate at extreme recursive time complexities (O(2^N) in static analysis). You MUST NOT introduce unbounded recursive loops, heavy synchronous disk I/O, or massive object allocations on the critical path of HTTP request handling, job scheduling, or node management.
* **Orchestrator Fragility:** Central orchestrators such as `ExtensionList.java` (41 outbound dependencies), `Jenkins.java` (36 outbound), and `Job.java` (34 outbound) are extremely fragile. Modifying extension discovery, global configuration injection, or the core Job hierarchy requires immediate, comprehensive verification via the integration test suites.
* **Avoid Dead Code Pruning:** The repository contains massive volumes of logic flagged as "dead code" or "orphaned functions" (e.g., `PluginManager.java` with 64 orphans, `Computer.java` with 60). DO NOT autonomously attempt to prune, format, or clean up these files. Jenkins relies entirely on Stapler reflection to bind HTTP endpoints to methods (often named `do*` or `get*`), which static dependency analysis tools interpret as unused.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or represent severe choke points. 

**MANDATORY RULE:** You require explicit human permission and downstream integration testing before modifying the structural signatures, Stapler routing, or public APIs of these files:
* `core/src/main/java/jenkins/model/Jenkins.java` (Highest Cumulative Risk: 644.25, Massive Structural Mass, 100% Injection Risk. The absolute root of the application).
* `core/src/main/java/hudson/model/Run.java` & `Job.java` (Massive Data Gravity and Tech Debt. Core build execution state machines).
* `core/src/main/java/hudson/model/Computer.java` (100% Exploit Generation Surface. Manages node/agent execution boundaries).
* `core/src/main/java/hudson/ExtensionList.java` (The fragile orchestrator for the entire Jenkins plugin ecosystem).
* `core/src/main/resources/hudson/model/View/index.jelly` (Severe Blind Bottleneck - extremely high inbound connections from the UI layer).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH CRITICAL RCE/INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface & Weaponizable Injection:** Files managing file system access and process execution (`Computer.java`, `DirectoryBrowserSupport.java`, `Job.java`, `Jenkins.java`) possess 100% Exposure for Exploit Generation and Weaponizable Injection. Because Jenkins inherently executes arbitrary code (build scripts) by design, you MUST ensure that administrative boundaries are never breached. Any modifications to form submissions (`doConfigSubmit`), workspace browsers, or CLI endpoints must rigorously sanitize paths to prevent Path Traversal, and strictly validate permissions (e.g., `checkPermission(Jenkins.ADMINISTER)`) to prevent unauthenticated Remote Code Execution (RCE) or Cross-Site Scripting (XSS).
2. **State Flux:** Test reporting files (`hudson/tasks/junit/CaseResult.java`) exhibit high state mutation. Ensure mutations during XML test report parsing do not lead to memory leaks or XML External Entity (XXE) vulnerabilities.
3. **Supply Chain:** There are over 10,000 unknown dependencies bypassing the Zero-Trust whitelist (expected in a Maven/Java ecosystem of this size). Do not add or bump external packages in `pom.xml` files without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess Stapler request routing, hallucinate Jelly UI bindings, or rely on generalized Java web framework knowledge to determine blast radius within this 1.2M+ LOC CI/CD engine. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

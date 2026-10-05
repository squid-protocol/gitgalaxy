---
description: "You are operating within `apex-recipes`, a demonstration and best-practices repository primarily composed of XML metadata (47.6%), Apex backend logic..."
---
# AGENTS.md: apex-recipes Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `apex-recipes`, a demonstration and best-practices repository primarily composed of XML metadata (47.6%), Apex backend logic (17.9%), and Lightning Web Components (LWC / JavaScript).
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species with an Architectural Drift Z-Score of 4.842. The network topology demonstrates 0.0 Modularity and 0.0 Assortativity, which is highly typical for a Salesforce project where components are loosely coupled but structurally flat (many independent "recipes" rather than a deeply integrated monolithic application). Do not attempt to force deep hierarchical dependencies or generic MVC frameworks onto these isolated recipe files.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Several LWC components (`recipeTreeView.js`) and test factories (`TestFactory.cls`, `HttpCalloutMockFactory.cls`) operate with O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops or O(N^2+) complexity when modifying the LWC tree rendering logic or Apex SObject factory generation.
* **Orchestrator Fragility:** LWC components such as `formattedDocsViewer.js`, `errorPanel.js`, and `formattedRecipeDisplay.js` act as frontend orchestrators. Any changes to data contracts, DOM manipulation, or `@api` exposed properties within these JavaScript files require immediate verification against their corresponding HTML templates and Apex controllers.
* **Avoid Dead Code Pruning:** Test files such as `SOQLRecipes_Tests.cls` (20 orphaned functions), `CustomRestEndpointRecipes_Tests.cls` (19 orphaned functions), and `Safely_Tests.cls` (16 orphaned functions) contain unreferenced test methods. DO NOT autonomously attempt to prune or clean up these methods, as the Salesforce testing framework relies on the `@isTest` annotation for dynamic execution, bypassing static dependency trees.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or act as "Blind Bottlenecks" (deeply embedded with high documentation risk). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, LWC controllers, or public APIs of these files:
* `force-app/main/default/lwc/recipeTreeView/recipeTreeView.js` (Highest Cumulative Risk: 548.19, 100% Cognitive Load, Blind Bottleneck)
* `force-app/main/default/lwc/formattedRecipeDisplay/formattedRecipeDisplay.js` (High Cumulative Risk: 495.91, Blind Bottleneck)
* `force-app/main/default/staticresources/highlight/prism.js` (Massive structural mass: 813.74, 100% Exploit Generation Surface due to raw execution)
* `force-app/main/default/lwc/formattedDocsViewer/formattedDocsViewer.js` (Blind Bottleneck, 100% Cognitive Load)
* `bin/install-scratch.sh` (High Tech Debt: 96.8%)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:** 1. **Weaponizable Injection Vectors:** `force-app/tests/Integration Recipes/CustomRestEndpointRecipes_Tests.cls` possesses a 100% Exposure score for Injection Surfaces. When modifying custom REST endpoints or their tests, you MUST ensure strict input sanitization, enforce `WITH SECURITY_ENFORCED` on SOQL queries, and validate CRUD/FLS permissions.
2. **Exploit Generation Surface:** `prism.js` (a static resource) has a 100% Exploit Generation Surface score. If updating static resources, ensure no unsanitized user input is evaluated as code.
3. **Supply Chain:** There are 32 unknown dependencies bypassing the Zero-Trust whitelist. Do not add external JS libraries without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized Salesforce knowledge to determine blast radius. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

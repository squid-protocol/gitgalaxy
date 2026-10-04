---
description: "You are operating within `canvas-lms`, a massive Learning Management System monolith comprising over 1 million lines of code. The architecture is a..."
---
# AGENTS.md: canvas-lms Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `canvas-lms`, a massive Learning Management System monolith comprising over 1 million lines of code. The architecture is a deeply intertwined hybrid of a Ruby on Rails backend (18.3% Ruby, heavily concentrated in models/controllers) and a modern frontend ecosystem (33.9% TypeScript, 23.1% JavaScript).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a severe Architectural Drift Z-Score of 7.911. The network topology demonstrates high Modularity (0.8704) indicative of separated frontend packages and backend domains, but significant negative assortativity (-0.3589). This means the architecture relies on massive, highly connected hub nodes (ActiveRecord models and core UI orchestrators) acting as fragile single-points-of-failure. 

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core backend controllers (`Accessibility`, `GradingSchemesJsonController`, `LiveAssessments`) and initialization routines operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops, complex Active Record callbacks, or O(N^2+) complexity when modifying the request lifecycle or assessment processing logic.
* **Orchestrator Fragility:** Frontend orchestrators such as `ui/featureBundles.ts` (212 outbound dependencies) and `ui/features/gradebook/react/default_gradebook/Gradebook.tsx` are highly fragile. Any changes to data contracts, routing, or state management within these files require immediate, comprehensive verification of downstream UI components.
* **Avoid Dead Code Pruning:** Backend models such as `app/models/user.rb` (154 orphaned functions), `app/models/course.rb` (148 orphans), and `app/models/abstract_assignment.rb` contain high volumes of logic flagged as "dead code." DO NOT autonomously attempt to prune or format these files. The Rails framework relies heavily on dynamic dispatch, metaprogramming, and implicit callbacks that static analysis tools misinterpret as unused logic.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, database queries, or public APIs of these files:
* `ui/features/gradebook/react/default_gradebook/Gradebook.tsx` (Highest Cumulative Risk: 667.85, 100% Logic Bomb Exposure)
* `app/controllers/application_controller.rb` (Extreme Volatility Hotspot: 100% Churn, massive request interceptor)
* `app/models/account.rb`, `app/models/course.rb`, and `app/models/user.rb` (Massive Data Gravity, High Volatility, Core Domain Models)
* `config/initializers/active_record.rb` (Key Person Silo - 100% isolated ownership by Cody Cutrer)
* `script/common/utils/common.sh` (Severe Blind Bottleneck - High Blast Radius with 100% Documentation Risk)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Files such as `app/controllers/developer_keys_controller.rb` and `app/controllers/accounts_controller.rb` possess a 100% Exposure score for Exploit Generation. Because this LMS manages sensitive educational data and LTI (Learning Tools Interoperability) integrations, you MUST ensure strict input sanitization, CSRF protection, and permission validation on all controller endpoints.
2. **Weaponizable Injection Vectors:** Frontend plugins like `packages/canvas-rce/src/rce/plugins/instructure_icon_maker/` have tripped injection signatures. Ensure that any modifications to the Rich Content Editor (RCE) strictly sanitize HTML to prevent Cross-Site Scripting (XSS).
3. **Hardcoded Payload Artifacts:** Files like `config/saml/inc-md-cert-mdq.pem` and `ukfederation.pem` tripped hardcoded payload signatures. DO NOT flag these as leaked secrets or attempt to remove them; they are explicit SAML trust anchors required for federated authentication.
4. **Supply Chain:** There are 6,177 unknown dependencies bypassing the Zero-Trust whitelist and 83 binary anomalies. Do not add or bump external NPM or RubyGems dependencies without explicit cross-referencing against internal security manifests.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized Rails/React knowledge to determine blast radius within this 1+ million LOC monolith. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

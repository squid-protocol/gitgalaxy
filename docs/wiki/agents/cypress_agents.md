---
description: "You are operating within the `cypress` monorepo, a massive End-to-End (E2E) testing framework composed of dozens of interdependent packages. The..."
---
# AGENTS.md: cypress Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within the `cypress` monorepo, a massive End-to-End (E2E) testing framework composed of dozens of interdependent packages. The codebase is a complex mix of TypeScript (35.6%), JavaScript (26.3%), and HTML/UI components (14.2%).
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species. The network topology demonstrates relatively high Modularity (0.6584) but negative Assortativity (-0.0793), indicating a hub-and-spoke model. While individual packages (like `driver`, `data-context`, `app`) are well-segmented internally, they rely heavily on core foundational files (`lodash.ts`, `cypress.js`, `debug.js`) that bind the execution environments together.
* **Core Rule:** Respect package boundaries. Do NOT introduce cross-package imports outside of established API surfaces. The boundary between the Node.js backend (Data Context/GraphQL) and the browser execution environment (Driver/App) is absolute.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Test specification blocks (e.g., `describe` and `it` blocks within `packages/driver/cypress/e2e/**/*.cy.js`) often exhibit O(2^N) recursive time complexity in static analysis due to deeply nested closures and asynchronous Cypress chainables. You MUST NOT introduce deep recursion or synchronous blocking loops inside Cypress commands (`cy.ts`, `packages/driver/src/cy/commands/*`).
* **Orchestrator Fragility:** Central orchestrators like `packages/driver/src/cypress.ts` (45 outbound dependencies) and `packages/data-context/graphql/schemaTypes/objectTypes/index.ts` are highly fragile. Altering event dispatchers, runner configurations, or GraphQL schemas requires immediate, comprehensive verification via the monorepo's internal test suites.
* **Avoid Dead Code Pruning:** The `packages/errors/src/errors.ts` file contains 125 functions flagged as "orphaned," and `error_messages.ts` contains 63. DO NOT autonomously attempt to prune, format, or clean up these files. These are dictionary mappings for user-facing errors that are dynamically referenced via string keys at runtime; static analysis misinterprets them as dead code.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream E2E pipeline verification before modifying the structural signatures, event handlers, or public APIs of these files:
* `packages/frontend-shared/cypress/e2e/e2ePluginSetup.ts` (Highest Cumulative Risk: 713.67, 100% Logic Bomb & Injection Surface exposure due to dynamic hook evaluation).
* `packages/driver/cypress/e2e/commands/assertions.cy.js` & `waiting.cy.js` (Massive Structural Mass and Key Person Silos - 100% isolated ownership by specific engineers).
* `packages/app/src/runner/event-manager.ts` (Extreme Volatility Hotspot: 80.0% Churn, handles critical browser-to-server messaging).
* `scripts/cypress.js` & `scripts/debug.js` (Severe House of Cards/Blind Bottlenecks - deeply embedded execution wrappers with high Error Risk).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface / Injection Vectors:** Because Cypress fundamentally acts as a proxy and executes code within the context of a User Under Test (AUT), files like `packages/data-context/graphql/makeGraphQLServer.ts`, `RemoteRequestDataSource.ts`, and `webpack.config.base.ts` possess 100% Exposure for Exploit Generation and Injection. You MUST ensure strict validation of paths, origin policies, and GraphQL inputs to prevent arbitrary code execution or cross-origin leakage on the host machine.
2. **Hardcoded Payload Artifacts:** Numerous `.npmrc` files and `cafile.pem` are flagged with 100% exposure for hardcoded payloads. These are required configurations and certificate fixtures for the proxy tests. Do not flag them as leaked secrets.
3. **Supply Chain:** There are over 5,500 unknown dependencies bypassing the Zero-Trust whitelist (expected in a sprawling Node.js monorepo). Do not add or bump external packages in root or workspace `package.json` files without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess GraphQL resolver schemas, hallucinate Cypress command chain yields, or rely on generalized TypeScript knowledge to determine blast radius within this 300k+ LOC monorepo. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

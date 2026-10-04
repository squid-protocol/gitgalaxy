---
description: "You are operating within the `trpc` repository, an end-to-end typesafe API framework. The codebase is heavily dominated by TypeScript (70.1%),..."
---
# AGENTS.md: trpc Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within the `trpc` repository, an end-to-end typesafe API framework. The codebase is heavily dominated by TypeScript (70.1%), supported by Markdown documentation and JSON configurations, structured as a monorepo containing client, server, and React-Query integrations.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species. The network topology demonstrates high Modularity (0.5862) but negative Assortativity (-0.0308). This indicates a cleanly segregated package architecture (e.g., `@trpc/server`, `@trpc/client`, `@trpc/react-query`) that nonetheless relies heavily on fragile, central single-points-of-failure (`unstable-core-do-not-import.ts`, `next.ts`, `ws.ts`).
* **Information Flow:** Types and execution flow from the server-side router definitions through the core adapters (`next.ts`, `express.ts`, `ws.ts`) out to the client links (`httpBatchStreamLink.ts`, `wsClient.ts`) and React hooks wrapper.
* **Core Rule:** Maintain strict adherence to the monorepo's package boundaries. Do NOT attempt to import internal core logic across package boundaries (explicitly bypassing `unstable-core-do-not-import.ts`), as this breaks the strict TypeScript encapsulation and modularity the framework relies on.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core stream parsing, OpenAPI schema extraction (`getProcedureTypeName`), and client link batching (`httpBatchStreamLink.ts`, `httpSubscriptionLink.ts`) operate at high recursive time complexities (O(2^N) in static analysis) due to deep AST traversal and object unwrapping. You MUST NOT introduce unbounded loops, deep recursive type inferences, or synchronous blocking operations within the data serialization/deserialization hot paths.
* **Orchestrator Fragility:** Central orchestrators such as `packages/server/src/unstable-core-do-not-import.ts` (36 outbound dependencies) and `packages/react-query/src/shared/hooks/createHooksInternal.tsx` (14 outbound) are highly fragile. Modifying core TRPC behavior, proxy creation, or React hook instantiation requires immediate, comprehensive verification across the monorepo's testing matrix.
* **Avoid Dead Code Pruning:** Files like `examples/openapi-codegen/src/client/generated/client/utils.gen.ts` and `packages/client/src/links/wsLink/wsClient/requestManager.ts` contain logic flagged as "dead code." DO NOT autonomously attempt to prune these. These are often generated SDKs or internal utilities intended for downstream consumer use, bypassing static dependency resolution within the repository itself.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or represent 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream integration testing before modifying the structural signatures, proxy logic, or public APIs of these files:
* `packages/server/src/adapters/next.ts` & `packages/server/src/adapters/ws.ts` (Severe Blind Bottlenecks & House of Cards - High inbound connections combined with extreme documentation risk and error risk. A failure here breaks the primary transport layers).
* `packages/react-query/src/shared/hooks/createHooksInternal.tsx` (Key Person Silo - 100% isolated ownership by Julius Marminge. Core React-Query proxy generation).
* `packages/openapi/src/generate.ts` (Key Person Silo - 100% isolated ownership by Nick Lucas. Core OpenAPI schema generation).
* `packages/server/src/unstable-core-do-not-import/stream/utils/timerResource.ts` (Highest Cumulative Risk: 519.72. Critical streaming utility).
* `packages/client/src/links/wsLink/wsClient/wsClient.ts` (Highest WebSocket client risk and race condition exposure).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH SHADOW API CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts.

**CRITICAL WARNINGS:**
1. **API Network Mapper:** The perimeter scan detected 1 undocumented Shadow API actively listening and 3 Ghost APIs (documented but missing). Ensure any newly added endpoints or examples explicitly map to the TRPC OpenAPI specification and are documented. Known shadow route: `GET /`.
2. **Exploit Generation Surface:** Server resource fetching (`packages/server/src/__tests__/trpcServerResource.ts`) and HTTP incoming message handlers (`incomingMessageToRequest.ts`) possess minor exposure for Exploit Generation. Ensure request body parsing limits and content-type validations are strictly enforced to prevent DoS or SSRF.
3. **Hardcoded Payload Artifacts:** Multiple `.env` and `.npmrc` files inside the `examples/` directory are flagged for hardcoded payloads. These are boilerplate configurations. DO NOT insert real credentials into these files during automated modifications.
4. **Supply Chain:** There are 1167 unknown dependencies bypassing the Zero-Trust whitelist (expected in a heavily integrated TypeScript monorepo). Do not add or bump external packages in `package.json` workspaces without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess TRPC proxy state transitions, hallucinate React-Query integration boundaries, or rely on generalized TypeScript knowledge to determine blast radius within this highly genericized API framework. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

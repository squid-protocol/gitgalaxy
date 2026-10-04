---
description: "You are operating within the `react` repository (`facebook/react`), the foundational library for building user interfaces. The codebase encompasses the..."
---
# AGENTS.md: react Architectural Context & Engagement Rules

## 1. Information Flow & Purpose (The Executive Summary)
You are operating within the `react` repository (`facebook/react`), the foundational library for building user interfaces. The codebase encompasses the core React APIs, the Fiber reconciler, DOM and Native bindings, Server Components (Flight), and the React Compiler. It is predominantly JavaScript (58.1%) with an increasing adoption of TypeScript (7.9%) for compiler and tooling packages.

* **Architectural Paradigm:** The system maps to a "Cluster 4" macro-species and exhibits a severe Architectural Drift Z-Score of 7.066. The network topology demonstrates low Modularity (0.2525) and highly negative Assortativity (-0.7088). This indicates a tightly coupled, monolithic architecture characterized by fragile single-points-of-failure. The various packages (DOM, Native, Reconciler) are deeply interconnected through shared internal modules and configuration injectors.
* **Information Flow:** Execution flows from user-space component declarations through the React element factory, into the scheduling and reconciliation phases (`ReactFiberWorkLoop.js`, `ReactFiberBeginWork.js`), and finally delegates to platform-specific renderers (like `ReactDOMComponent.js` for web). In the server-side rendering (SSR) and React Server Components (RSC) models, data flows through the Flight protocol serializers and streaming architecture.
* **Core Rule:** Maintain absolute adherence to the Fiber reconciliation phases (Render vs. Commit) and immutability constraints. Do NOT attempt to introduce synchronous blocking state mutations or decouple platform-agnostic reconciler logic from the highly specialized renderer injection interfaces.

## 2. Notable Structures & Architecture
* **Foundational Load-Bearers:** `compiler/packages/snap/src/sprout/shared-runtime.ts` acts as a massive structural pillar (549 inbound connections), forming the bedrock for the compiler's execution testing environments. Similarly, shared DevTools configurations (`shared.js`, `styles.css`) carry disproportionate blast radii across the tooling ecosystem.
* **Fragile Orchestrators:** The core execution loop is extremely fragile. `ReactFiberWorkLoop.js` (59 outbound dependencies) and `ReactFiberBeginWork.js` (45 outbound dependencies) dictate the synchronous and concurrent rendering lifecycles. Modifying these orchestrators carries the highest risk of cascading regressions across the entire library.
* **Algorithmic Complexity:** Core AST transformations in the React Compiler (`lowerStatement`, `lowerExpression` in `BuildHIR.ts`) and React DevTools inspection hooks operate at extreme recursive time complexities (O(2^N) in static analysis) due to deep tree traversal.

## 3. Security & Vulnerabilities
**Status: SECURE PERIMETER (WITH SERIALIZATION CAVEATS).** Structural Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface (RSC & Flight):** The React Server Components infrastructure—specifically `ReactFlightClient.js`, `ReactFlightReplyClient.js`, and `ReactFlightServer.js`—exhibits 100% Exploit Generation Surface exposure. These modules handle complex AST parsing, JSON streaming, and client-server deserialization boundaries. Strict validation must be maintained here to prevent prototype pollution or XSS during stream hydration.
2. **Weaponizable Injection Vectors:** Test environments for partial hydration and server rendering (`ReactDOMServerPartialHydration-test.internal.js`) flag high injection risks. Ensure any test harnesses simulating DOM payloads strictly sanitize inputs to prevent arbitrary execution within the Node/JSDOM test runners.
3. **Supply Chain:** The repository imports over 6,300 unknown dependencies bypassing the Zero-Trust whitelist. This is expected for a monorepo containing extensive compiler, Babel, and ESLint tooling, but new dependencies must undergo strict architectural review to prevent supply chain compromise.

## 4. Outliers & Extremes
* **The Hotspot Matrix (Volatility + Risk):** The Fiber work loop (`ReactFiberWorkLoop.js`) is the ultimate hotspot (81.45% Churn, 60.18% Tech Debt), representing constant iteration on React's scheduling algorithms. The Server Components implementation (`ReactDOMFizzServer-test.js`) follows closely behind in both churn and cognitive load.
* **Key Person Silos:** Severe "Bus Factor" risks exist around foundational rendering boundaries. Sebastian Markbåge maintains 100% isolated ownership over critical components like `ReactDOMComponent.js` (8,534 Mass) and `ReactChildFiber.js`. 
* **Cumulative Risk Extremes:** The React DevTools `renderer.js` represents the highest cumulative risk (655.85) due to its deep integration with the Fiber tree and high documentation risk. The Flight client/server modules (`ReactFlightServer.js`, `ReactFlightClient.js`) tightly follow, driven by logic complexity and specification strictness.
* **Design Slop:** Files such as `ReactFiberConfigART.js`, `ReactFiberConfigNative.js`, and `ReactFiberConfigTestHost.js` contain high counts of orphaned functions (60+). Do not prune these; they act as interface implementations for alternative renderers that bypass traditional static dependency resolution.

## 5. Recommended Next Steps (Refactoring for Stability)
To stabilize the architecture and reduce cognitive load for ongoing maintenance, prioritize the following pragmatic actions:

1. **De-silo Core Reconciler Knowledge:** Address the 100% isolated ownership of `ReactDOMComponent.js` and `ReactChildFiber.js`. Introduce rigorous architectural documentation and pairing to distribute domain knowledge regarding DOM property updates and child reconciliation algorithms.
2. **Harden React Flight Serialization Boundaries:** Given the high cumulative risk and exploit generation exposure in the Flight (RSC) clients and servers, isolate the serialization and stream-parsing logic into strictly typed, independent modules. This will limit the blast radius and allow for more targeted security fuzzing of the hydration payloads.
3. **Document the `shared-runtime.ts` Blind Bottleneck:** `shared-runtime.ts` holds a massive blast radius for the React Compiler (549 inbound connections) but suffers from high documentation risk (74%). Formalize the API contracts and usage constraints via TSDoc to prevent downstream compiler pipeline breakages and reduce "House of Cards" fragility.


---

**[⬅️ Back to Master Index](../index.md)**

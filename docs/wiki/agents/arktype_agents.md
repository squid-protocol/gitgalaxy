---
description: "You are operating within `arktype`, a highly specialized TypeScript runtime validation and schema inference library (82.7% TypeScript)."
---
# AGENTS.md: arktype Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `arktype`, a highly specialized TypeScript runtime validation and schema inference library (82.7% TypeScript).
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species with a significant Architectural Drift Z-Score of 6.312. The network topology demonstrates 0.0 Modularity and 0.0 Assortativity, typical of heavily inter-dependent type-system compilers and recursive parsers. 
* **Core Rule:** Do NOT attempt to apply standard MVC or asynchronous web application patterns. This codebase operates like a compiler, relying heavily on recursive structural transformations, generic type inference, and AST (Abstract Syntax Tree) traversal.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core schema parsers (`ark/schema/generic.ts`), regular expression engines (`ark/regex/regex.ts`), and arbitrary generators (`ark/fast-check/arbitraries/domain.ts`) inherently operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops or recursive execution paths within the schema parser or intersection/union logic (`ark/schema/roots/union.ts`).
* **Orchestrator Fragility:** Central index files (`ark/schema/index.ts`, `ark/schema/roots/root.ts`, and `ark/schema/kinds.ts`) act as fragile orchestrators with high outbound dependencies. Any changes to data contracts, exported types, or Node implementation traits within these files require immediate verification of downstream integration.
* **Avoid Dead Code Pruning:** The AST/Node structures (`ark/schema/roots/root.ts`, `ark/schema/node.ts`, and `ark/type/parser/reduce/dynamic.ts`) contain functions that static analysis incorrectly flags as "orphaned." DO NOT autonomously attempt to prune, format, or clean up these files. The schema engine relies on dynamic evaluation, polymorphism, and generic type resolution that bypasses static dependency trees.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos: David Blass). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, generic type constraints, or public APIs of these files:
* `ark/type/parser/reduce/dynamic.ts` (Highest Cumulative Risk: 612.42)
* `ark/schema/shared/traversal.ts` (Extreme Volatility Hotspot: 88.5% Churn, High Cognitive Load)
* `ark/schema/structure/sequence.ts` (High Structural Mass and Logic Implementation)
* `ark/schema/roots/union.ts` (Blind Bottleneck - 100% Documentation Risk)
* `ark/regex/group.ts` (Key Person Silo - 100% isolated ownership by David Blass)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts, 0 Agentic RCE funnels, and 0 Prompt Injection vectors. 

**CRITICAL WARNINGS:** 1. **Supply Chain:** There are 673 unknown dependencies bypassing the Zero-Trust whitelist. Do not add or bump external packages (especially testing or fast-check libraries) without explicit architectural review.
2. **Schema Compilation:** The library dynamically compiles schemas into runtime checks (`ark/schema/shared/compile.ts`). If modifying the compilation step, you must ensure that generated functions do not create unintended arbitrary code execution vectors (e.g., unsanitized `new Function()` equivalents if applicable).

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized TypeScript knowledge to determine blast radius within this highly recursive generic type system. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

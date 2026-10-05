---
description: "You are operating within `assemblyscript`, a compiler toolchain that compiles a strict variant of TypeScript to WebAssembly. The repository is..."
---
# AGENTS.md: assemblyscript Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `assemblyscript`, a compiler toolchain that compiles a strict variant of TypeScript to WebAssembly. The repository is predominantly TypeScript (64.8%) with significant JavaScript (8.5%) wrapper logic and JSON configuration schemas.
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 4.93. The network topology demonstrates a clean modularity (0.292) but high positive assortativity (0.4833). This indicates a resilient, densely connected core typical of a multi-pass compiler. Standard application MVC or asynchronous web application patterns DO NOT APPLY here. Expect deep recursion, complex AST (Abstract Syntax Tree) manipulation, and rigid parsing logic.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core compiler methods such as `compileBinaryExpression` in `src/compiler.ts`, `finishResolveClass` in `src/resolver.ts`, and `parseExpression` in `src/parser.ts` currently operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested loops or O(N^2+) complexity when modifying the compiler pipeline or the AST tokenizers.
* **Orchestrator Fragility:** Central orchestrators like `src/compiler.ts` (14 outbound dependencies) and `tests/compiler.js` (15 outbound dependencies) are highly fragile. Any changes to data contracts, type resolution, or emitted WebAssembly payloads within these files require immediate, comprehensive verification of downstream integration tests.
* **Avoid Dead Code Pruning:** The AST and compilation layers (`src/module.ts`, `src/ast.ts`, `src/program.ts`, and `src/glue/wasm/i64.ts`) contain hundreds of orphaned (dead) functions. DO NOT autonomously attempt to prune, format, or clean up these files. The compiler utilizes these functions dynamically during specific AST traversal passes or WebAssembly emission phases that static analysis cannot reliably track.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream test verification before modifying the structural signatures, recursive parsing logic, or public APIs of these files:
* `src/compiler.ts` (Highest Cumulative Risk: 692.45, Extreme Volatility Hotspot: 100% Churn)
* `src/program.ts` (Massive AST orchestrator, High Cumulative Risk: 667.06)
* `src/flow.ts` (High Logic Bomb Exposure, critical control-flow graph component)
* `tests/compiler/bindings/esm.debug.js` & `tests/compiler/bindings/esm.release.js` (Key Person Silos - 100% isolated ownership by CountBleck)
* `util/browser/path.js` (Blind Bottleneck - 100% Documentation Risk with high error exposure)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH EXPLOIT GENERATION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:** 1. **Exploit Generation Surface:** Files such as `src/flow.ts`, `src/passes/pass.ts`, `src/tokenizer.ts`, and `src/parser.ts` possess a 100% Exposure score for Exploit Generation Surface due to the nature of parsing and compiling raw input code into executables. When modifying the parser or tokenizer, you MUST ensure strict input validation and boundary checking to prevent compiler panics or malicious payload injections.
2. **Obfuscation Surface:** The `std/assembly/` directory (e.g., `date.ts`, `string-casemapping.ts`) handles low-level WebAssembly memory operations and String encoding, flagging high obfuscation. Ensure any modifications to Standard Library memory management remain well-documented.
3. **Supply Chain:** There are 127 unknown dependencies bypassing the Zero-Trust whitelist. Do not add or bump external packages without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess dependencies, hallucinate import paths, or rely on generalized TypeScript knowledge to determine blast radius within this 91k+ LOC compiler. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

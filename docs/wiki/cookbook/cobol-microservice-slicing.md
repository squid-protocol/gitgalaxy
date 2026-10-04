---
description: "The primary goal of enterprise legacy modernization is rarely a direct 1-to-1 lift-and-shift; it is the decomposition of monolithic COBOL applications..."
---
# Cookbook: Microservice Slicing via Deterministic RAG Pipelines

## 1. The Microservice Extraction Challenge

The primary goal of enterprise legacy modernization is rarely a direct 1-to-1 lift-and-shift; it is the decomposition of monolithic COBOL applications into cohesive, domain-driven microservices. However, COBOL inherently lacks modern encapsulation boundaries. Business logic, data access, and presentation layers are heavily intertwined in "spaghetti code."

When engineers attempt to use Large Language Models (LLMs) to extract a specific domain (e.g., "isolate the interest calculation logic"), the results are highly erratic. LLMs struggle with long-range dependencies across massive context windows. They frequently hallucinate connections, miss chained variable aliases, or inadvertently translate dead code that happened to share semantic similarities with the target domain.

To successfully decompose a mainframe monolith, you must abandon probabilistic guessing in favor of deterministic mathematics. 

The GitGalaxy ecosystem utilizes a deterministic function-level knowledge graph engine. Instead of asking an LLM to find the logic, the blAST (Bypassing LLMs and ASTs) engine uses syntactic heuristics to perform strict, recursive taint-tracking. It mathematically maps exactly which variables mutate a target state and slices out only the lines of code that execute those mutations. In a Retrieval-Augmented Generation (RAG) pipeline, this deterministic "slice" becomes the perfect, noise-free payload, allowing the LLM to translate highly specific business rules into modern Java or C# microservices with absolute structural integrity.

## 2. The Microservice Slicer

The `cobol_microservice_slicer.py` script is the surgical extraction spoke of the GitGalaxy ecosystem. It is designed to trace a single target variable (the "taint") through the AST-free string representation of the COBOL program.

Because legacy variables are frequently reassigned (aliased) throughout their lifecycle, the Slicer executes a multi-pass evaluation to track the entire algebraic lineage. To ensure absolute accuracy and prevent the translation of technical debt, the Slicer integrates with the broader knowledge graph to actively deflect "ghost dependencies" residing in dead memory or unreachable paragraphs.

### 2.1 Information Flow & Processing Pipeline

The pipeline executes a highly specialized deterministic extraction to trace state flux and isolate business rules.

| Processing Stage | Syntactic Heuristic | Architectural Purpose | Legacy Modernization Value |
| :--- | :--- | :--- | :--- |
| **Orphaned Memory Abort** | IR State Query (`orphaned_vars`) | Verifies the target variable against the global graph of dead memory prior to execution. | Instantly halts the pipeline if the target domain is dead, saving compute resources and preventing the translation of deprecated systems. |
| **The Alias Engine** | `MOVE\|ADD\|SUBTRACT\|COMPUTE` | Recursively maps state mutations, flagging any secondary variable that intersects with the primary taint. | Captures the true scope of a business rule, ensuring the LLM receives all chained calculations required for accurate microservice translation. |
| **Ghost Deflection** | IR State Query (`dead_paras`) | Silently drops execution blocks that the graph has mathematically proven to be unreachable. | Prevents false-positive taints where a dead paragraph aliases a variable, ensuring the final slice contains only active production logic. |
| **Extraction Shield** | Line-by-line Taint Intersection | Slices out only the specific statements and paragraphs containing the mathematically verified taints. | Drastically reduces the token payload for the RAG engine, providing a pristine, highly cohesive logic block for the LLM to translate. |

## 3. Notable Structures & Architecture

The script operates on two primary structural mechanisms tuned for precise state tracking:

### Recursive Taint Mapping (Pass 1)
This mechanism acts as the dependency resolver. Legacy COBOL logic is rarely confined to a single variable; an `ACCOUNT-BALANCE` might be moved to `WS-TEMP-BAL`, which is then computed against `WS-INTEREST-RATE`. The script executes a multi-pass loop across the active `PROCEDURE DIVISION`. It uses precise regular expressions to evaluate assignments and mathematical operations, dynamically expanding the `tainted_vars` set every time a new alias intersects with an existing taint. The Ghost Deflector ensures this operation ignores any calculations residing in dead code.

### Logic Extraction (Pass 2)
Once the complete alias network is mapped, the script performs a secondary pass to extract the physical architecture. It iterates through the active code, evaluating every line against the fully populated taint set. If a line contains a tainted variable, it is extracted along with its parent paragraph context. This effectively collapses thousands of lines of monolithic COBOL down to a few dozen lines of pure, highly cohesive business logic.

## 4. Execution Interface

The Slicer is executed via a headless CLI, designed to be called programmatically by modernization orchestrators feeding downstream LLM translation agents.

```bash
# Extract all active business logic mutating the ACCT-BALANCE variable
python3 cobol_microservice_slicer.py src/legacy/FINANCE.cbl --var ACCT-BALANCE
```

## 5. Recommended Next Steps (Refactoring for Enterprise Scale)

To optimize this component for a fully automated, enterprise-scale microservice factory, implement the following architectural enhancements:

1. **Graph-Driven State Injection:** The `dead_paras` and `orphaned_vars` parameters currently default to empty sets in standalone mode. Refactor the script to automatically query the central GitGalaxy SQLite database via a local API call. This guarantees the Slicer always operates with real-time, repository-wide context regarding technical debt.
2. **Cross-Program Taint Tracking:** The current implementation tracks taints within a single file. Extend the Alias Engine to intercept `CALL` statements. If a tainted variable is passed as a parameter to an external sub-program, the Slicer should seamlessly traverse the file boundary and continue mapping the business logic across the distributed mainframe architecture.
3. **Automated RAG Payload Assembly:** Rather than printing the extracted logic to the standard output, modify the artifact generation to output a structured JSON or prompt-ready Markdown file. This payload should automatically append the necessary instructions and schema definitions, providing a complete, zero-touch injection package for the downstream translation LLM.

- - - -
this was accomplished by the blAST engine - - - -🌌 Powered by the blAST Engine
This documentation is part of the GitGalaxy Ecosystem, an AST-free, LLM-free heuristic knowledge graph engine.

🪐 Explore the GitHub Repository for code, tools, and updates.
🔭 Visualize your own repository at GitGalaxy.io using our interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](../index.md)**

# 2.2.B. Sub-Equations & Scanner Variables

> **File Reference:** [`gitgalaxy/core/detector.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/core/detector.py)

> **Purpose: Defining Raw Inputs of the Analysis Engine**
>
> To calculate reliable risk and complexity metrics, the static analysis engine extracts a standardized set of regular expression variables from raw source files. Parsing occurs across a strict 5-phase extraction sequence.
> 
> *(Note: The scanner appends a `_hits` suffix to output count variables. For instance, the `branch` regex rule outputs its final occurrence count as `branch_hits`)*.

## Phase 1: Code Structure & Volume Metrics

These variables define the structural footprint and code volume of each file in the repository graph.

| Variable | Structural Definition |
| :--- | :--- |
| `branch_hits` | Decision points forcing control flow splits or jumps (conditionals, loops, short-circuits). Excludes unrecoverable exceptions. |
| `args_hits` | Parameter counts in function signatures defining input interface mass. |
| `linear_hits` | Declarative statements defining module structure (imports, returns, package declarations). |
| `func_start_hits` | Syntactic anchors identifying executable function, method, or subroutine declarations. |
| `class_start_hits` | Identifiers defining object-oriented entities or structured data definitions (classes, interfaces, structs). |

## Phase 2: Risk & Exposure Indicators

These variables track defensive guard patterns against potential vulnerability triggers.

| Variable | Structural Definition |
| :--- | :--- |
| `safety_hits` | Defensive programming indicators such as explicit error handling, boundary checks, and strict type equality (`try/catch`). |
| `safety_neg_hits` | Explicit type safety bypasses, error suppression, or unsafe pointer operations (`any`, `unsafe`). |
| `danger_hits` | Dynamic execution risks, raw process triggers, or unsanitized evaluation calls (`eval`, `process.exit`). |
| `io_hits` | I/O operations interacting with external systems (disk, network, database). |
| `api_hits` | Public surface area exposed to external callers (exported members, public interfaces). |
| `flux_hits` | Direct state mutations, variable reassignments, and side-effect triggers. |
| `graveyard_hits` | Commented-out execution blocks indicating dead or abandoned code features. |
| `doc_hits` | Structured documentation annotations intended for developers or parsers (e.g., JSDoc, docstrings). |
| `test_hits` | Indicators of automated test framework presence or assertions (`describe`, `it`, `assert`). |

## Phase 3: Domain & Paradigm Identifiers

These variables categorize specific architectural patterns and language features used across the module.

| Variable | Structural Definition |
| :--- | :--- |
| `concurrency_hits` | Asynchronous execution primitives, coroutines, and thread management routines. |
| `ui_framework_hits` | Density of visual layout components or UI binding elements (e.g., JSX components). |
| `closures_hits` | Anonymous functions, lambda expressions, and inline callback blocks. |
| `globals_hits` | References to global state registries, environment variables, or singleton instances. |
| `decorators_hits` | Metadata annotations modifying class or method behavior. |
| `generics_hits` | Generic type parameters, template signatures, and type abstraction contracts. |
| `comprehensions_hits` | Functional data transformations (map, filter, list comprehensions) acting as inline pipelines. |
| `scientific_hits` | Mathematical operations, tensor calls, and linear algebra routines. |
| `heat_triggers_hits` | Metaprogramming reflection, dynamic property binding, or eval triggers. |
| `import_hits` | External dependency declarations, package loading, and module includes. |
| `ownership_hits` | Author or maintainer metadata identified in file header comments (`@author`, `Maintainer:`). |

## Phase 4: Specialized Technical Debt & Risk Factors

These variables capture targeted execution contexts and technical debt indicators.

| Variable | Structural Definition |
| :--- | :--- |
| `planned_debt_hits` | Standard inline engineering task trackers (`TODO`, `WIP`). |
| `fragile_debt_hits` | Explicit inline warnings of temporary workarounds or legacy workarounds (`FIXME`, `HACK`). |
| `private_info_hits` | Hardcoded secrets, API keys, or credentials assigned directly in code text. |
| `spec_exposure_hits` | Inline traceability tags linking code blocks to requirements or RFC specs. |
| `ssr_boundaries_hits` | Server-side rendering hydration boundaries or template rendering markers. |
| `events_hits` | Event dispatch calls, message publishing, and signal emissions. |
| `dependency_injection_hits` | Dependency injection containers, service wiring, and inversion-of-control signatures. |
| `macros_hits` | Compile-time code generation macros and metaprogramming hooks. |
| `pointers_hits` | Low-level memory address operations and explicit pointer dereferencing. |
| `memory_alloc_hits` | Manual memory allocation and heap management calls (`malloc`, `new`). |
| `inline_asm_hits` | Direct assembly language instructions embedded in source files. |

## Phase 5: Contextual Mitigation Counter-Weights

These variables act as mathematical counter-weights to balance risk signals against standard architectural idioms.

| Variable | Structural Definition |
| :--- | :--- |
| `telemetry_hits` | Structured logging, metrics, and tracing instrumentation. |
| `print_hits` | Ad-hoc console dumps used for temporary debugging (`console.log`). |
| `cast_hits` | Explicit type casting operations. |
| `bailout_hits` | Hard execution aborts and unrecoverable panic triggers (`panic!`, `abort`). |
| `halt_hits` | Thread sleep or pause calls that may signal concurrency bottlenecks. |
| `bitwise_hits` | Low-level bitwise operations and binary data manipulation. |
| `sync_locks_hits` | Mutex locks and synchronization primitives (mitigating concurrency risk). |
| `freeze_hits` | Explicit object or memory immutability markers (mitigating state flux risk). |
| `cleanup_hits` | Explicit resource destruction or stream closing routines (mitigating memory/resource leak risk). |
| `encapsulation_hits` | Private/protected member access modifiers (mitigating public API exposure risk). |
| `listeners_hits` | Event subscriber bindings listening for broadcasts (mitigating unhandled event risks). |
| `test_skip_hits` | Automated test suite skip annotations (`it.skip`). |

<br><br>

---

### Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic knowledge graph engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using our interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**


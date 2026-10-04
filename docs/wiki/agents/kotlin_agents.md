---
description: "You are operating within the `kotlin` repository, the core compiler, standard library, and multi-platform tooling for the Kotlin programming language...."
---
# AGENTS.md: kotlin Architectural Context & Engagement Rules

## 1. Information Flow & Purpose (The Executive Summary)
You are operating within the `kotlin` repository, the core compiler, standard library, and multi-platform tooling for the Kotlin programming language. The codebase is immense (2M+ LOC) and heavily dominated by Kotlin (55.1%), supplemented by Java (3.4%) for legacy frontend/backend support, and C/C++/Swift for the Kotlin/Native and Kotlin/Multiplatform ecosystems.

* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 3.421. The network topology demonstrates a highly modular structure (Modularity: 0.6033) with slight negative Assortativity (-0.0249). This signifies a cleanly segregated compiler pipeline (e.g., PSI parsing -> FIR frontend -> IR backend -> JVM/Native/JS generation) that nevertheless funnels down into a few highly concentrated orchestrators and native runtime headers.
* **Information Flow:** Data typically flows from the syntax tree (PSI) into the Frontend Intermediate Representation (FIR) component (`compiler/fir`), undergoes semantic analysis and resolution, and translates to Backend IR (`compiler/ir`), which is finally lowered into platform-specific targets (JVM bytecode, JS, or Native binaries).
* **Core Rule:** Maintain strict adherence to the compiler pipeline phases. Do NOT attempt to leak FIR (Frontend IR) resolution logic into Backend IR lowering phases, and respect the explicit memory and platform boundaries established in the Kotlin/Native (`kotlin-native/runtime`) interop layers.

## 2. Notable Structures & Architecture (Dependency Graph)
* **Foundational Load-Bearers (High Blast Radius):** The Native and Multiplatform ecosystems form the bedrock of the dependency graph. Headers like `Memory.h`, `Utils.hpp`, `Types.h`, and `KotlinRuntimeSupport.swift` are universally imported across the native runtime. Modifying these C++ and Swift primitives carries a severe risk of triggering ABI breakages or cross-compilation failures across iOS, macOS, and Linux targets.
* **Fragile Orchestrators (High Coupling):** The frontend diagnostics and analysis APIs are highly coupled. Files such as `FirErrorsDefaultMessages.kt` (934 outbound dependencies), `loadInterpreter.kt` (328 outbound), and `KaFirCompilerFacility.kt` act as massive routing hubs for compiler warnings, errors, and plugin facilitation.
* **Algorithmic Complexity:** Core resolution paths such as `computeExpectedType`, `createSignature`, and AST patching algorithms (`PartiallyLinkedIrTreePatcher.kt`) operate at extreme recursive time complexities (O(2^N)). Modifications to the AST or FIR resolution trees must carefully avoid unbounded recursion or deep object graph allocations.

## 3. Security & Vulnerabilities
**Status: SECURE PERIMETER (WITH NATIVE MEMORY CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Operations within the `kotlin-native/runtime/src/libbacktrace/c/` directory (e.g., `mmap.c`, `dwarf.c`, `elf.c`) and embedded SQLite headers inherently rely on raw memory manipulation and pointer arithmetic (10% Exposure). Any modifications to stack unrolling, DWARF parsing, or garbage collection (GC) tracing must be rigorously bounded to prevent Use-After-Free (UAF), buffer overflows, or segmentation faults during Native execution.
2. **Exploit Generation Surface:** Interoperability layers (`KaFe10JavaInteroperabilityComponent.kt`, `KaFirExpressionTypeProvider.kt`) possess high exposure for Exploit Generation. Ensure any modifications handling cross-language type mapping or dynamic code loading strictly validate signatures to prevent arbitrary code execution during the compilation phase.
3. **Hardcoded Payload Artifacts:** Files such as `debug.keystore` and SwiftPM integration test files are flagged for hardcoded payloads. DO NOT flag these as leaked secrets; they are explicit test fixtures required for verifying Android build pipelines and Apple framework imports.

## 4. Outliers & Extremes
Focus strictly on statistical anomalies that represent severe structural fragility:
* **Massive Structural Nodes:** `ComposableFunctionBodyTransformer.kt` (8566.4 Mass, 100% Silo Risk by Derek Xu) is a colossal orchestrator for the Compose compiler plugin. Modifying IR lowering for Compose functions is extremely high risk.
* **High Volatility & Churn:** `FirCallCompletionResultsWriterTransformer.kt` exhibits a 94.6% churn rate combined with high cognitive load. This is a primary source of developer friction in the FIR resolution phase.
* **Severe Silo Risk:** The compiler FIR to IR transition (`Fir2IrVisitor.kt`, `FirExpressionsResolveTransformer.kt`, `KaFirResolver.kt`) is almost entirely governed by a single key contributor (Denis Zharkov). These files possess extreme cognitive load and high technical debt.
* **Blind Bottlenecks:** Native runtime components like `KotlinRuntimeSupport.swift` and `Memory.h` are "God Nodes" (high blast radius) lacking sufficient human intent, documentation, or ownership metadata (near 100% Doc Risk).

## 5. Recommended Next Steps (Refactoring for Stability)
To stabilize the system's architecture and reduce technical debt, prioritize the following pragmatic refactoring efforts:

1. **Decouple Diagnostic Orchestrators:** Break down `FirErrorsDefaultMessages.kt` and `FirJvmErrorsDefaultMessages.kt` using a registry or service-loader pattern. Distributing these massive outbound dependency hubs will reduce recompilation bottlenecks and fragility in the FIR analyzer.
2. **Mitigate Compose Lowering Silo:** Refactor `ComposableFunctionBodyTransformer.kt` to extract specific IR transformations (e.g., state hoisting, slot management) into distinct, testable visitor classes. This will reduce its 8500+ Structural Mass and alleviate the 100% single-person silo risk.
3. **Document Native Runtime Boundaries:** Aggressively add architectural documentation to `Memory.h`, `Types.h`, and `KotlinRuntimeSupport.swift`. These files represent severe blind bottlenecks; establishing explicit ABI and memory management contracts will lower the risk of cross-platform segmentation faults during Native runtime updates.


---

**[⬅️ Back to Master Index](../index.md)**

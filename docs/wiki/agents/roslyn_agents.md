---
description: "You are operating within the `roslyn` repository, the core .NET compiler platform containing the C# and Visual Basic compilers, alongside robust APIs..."
---
# AGENTS.md: roslyn Architectural Context & Engagement Rules

## 1. Information Flow & Purpose (The Executive Summary)
You are operating within the `roslyn` repository, the core .NET compiler platform containing the C# and Visual Basic compilers, alongside robust APIs for code analysis, refactoring, and workspace management. The codebase is heavily dominated by C# (96.5%) and represents a massive enterprise-scale architecture (4.6M+ LOC).
* **Architectural Paradigm:** The system maps to a "Cluster 4" macro-species with a severe Architectural Drift Z-Score of 7.565. The network topology demonstrates completely flat Modularity (0.0) and negative Assortativity (-0.2859). This indicates a highly centralized, "hub-and-spoke" monolith where a vast array of specialized analyzers and language features are tightly coupled to a small set of foundational syntax and semantic models.
* **Information Flow:** Execution stems from the command line (`CSharpCommandLineParser.cs`) or IDE host (`VisualStudioWorkspaceImpl.cs`), flowing through the parser/lexer, into semantic binding (`Binder_Expressions.cs`), and ultimately through diagnostic analyzers or emitters (`CodeGenerator`). Test suites exert immense gravitational pull, often dominating the structural mass.
* **Core Rule:** Maintain strict adherence to the Roslyn immutable syntax tree and semantic model paradigms. Do NOT attempt to introduce state mutations (`flux`) into syntax nodes or bypass the `Workspace` API boundaries when dealing with text documents or symbol resolution.

## 2. Notable Structures & Architecture
* **Foundational Load-Bearers:** Reference assembly text files (`System.Collections.Immutable.txt`, `System.Linq.txt`) act as massive structural pillars (4360 and 3575 inbound connections, respectively). These are critical for the Semantic Search tooling and test fixtures to resolve symbols without pulling in the entire .NET framework.
* **Fragile Orchestrators:** Test suites and IDE integration points act as heavy orchestrators. `OrganizeUsingsTests.cs` (93 outbound) and `VisualStudioWorkspaceImpl.cs` (47 outbound) pull in vast amounts of the compiler API to verify refactoring behaviors and coordinate workspace synchronization.
* **Algorithmic Complexity:** Code Fix Providers (e.g., `ConvertToRecordEngine.cs`, `CSharpUseAutoPropertyCodeFixProvider.cs`) frequently operate at O(2^N) complexity due to recursive AST traversal and syntax trivia resolution (finding exterior newlines, balancing brackets). Modifying these paths requires careful attention to stack depth and allocation overhead during trivia modification.

## 3. Security & Vulnerabilities
**Status: SECURE PERIMETER (WITH EXPLOIT GENERATION CAVEATS).** Structural Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Diagnostic analyzers handling local functions, collection expressions, and read-only modifiers (`CSharpUseLocalFunctionDiagnosticAnalyzer.cs`, `CSharpMakeStructMemberReadOnlyAnalyzer.cs`) possess 100% Exposure for Exploit Generation. Because the compiler processes arbitrary, untrusted source code, ensure recursive AST traversals in analyzers contain depth limits or cancellation token support to prevent Denial of Service (DoS) during IDE compilation.
2. **Weaponizable Injection Vectors:** Code analysis test fixtures and symbol key tests (`CompilerResolverTests.cs`, `SymbolKeyTests.cs`) exhibit 100% Weaponizable Injection Exposure. Ensure any test harnesses executing dynamically compiled code or resolving strong names strictly sandbox their outputs to prevent arbitrary code execution on the host machine.
3. **Supply Chain:** There are 60 binary anomalies identified by X-Ray. These are typically expected within the Roslyn test suites (e.g., PE metadata binaries, localized satellite assemblies), but should not be modified without explicit architectural review.

## 4. Outliers & Extremes
* **Test Suite Gravity:** The structural mass of `roslyn` is heavily skewed by massive, generated, or exhaustive test files. `MergeNestedIfStatementsTests_WithOuter.cs` (132k Mass) and `CSharpRegexParserTests_ReferenceTests.cs` (96k Mass) are structural leviathans. Do not attempt to refactor these to reduce cognitive load; they are designed for comprehensive coverage, not human readability.
* **The Hotspot Matrix (Volatility + Risk):** Core compiler and language server integration points are highly volatile. `ErrorFacts.cs` (72.9% Churn), `FileBasedProgramsProjectSystem.cs` (71.8% Churn), and `LanguageServerProjectSystem.cs` are active battlegrounds. Changes to semantic diagnostics or LSP (Language Server Protocol) synchronization carry high operational risk.
* **Key Person Silos:** Several massive embedded language test suites (e.g., Regex parsing) and structural refactorings are 100% isolated to single developers (Cyrus Najmabadi, David Barbet). 
* **Design Slop:** Files like `InlineArrayTests.cs` and `ImplicitObjectCreationTests.cs` contain hundreds of orphaned functions. These are explicit test methods invoked via reflection by the xUnit runner and should not be pruned.

## 5. Recommended Next Steps (Refactoring for Stability)
To stabilize the architecture and reduce cognitive load for ongoing maintenance, prioritize the following pragmatic actions:

1. **Document Blind Bottlenecks in the Syntax Factory:** Address the 100% documentation risk in `src/Compilers/CSharp/Portable/Syntax/SyntaxFactory.cs`. As this is a critical "God Node" with a massive blast radius, ensuring all node generation APIs are fully documented will reduce the "House of Cards" error risk for downstream diagnostic analyzers.
2. **De-Silo the Language Server Protocol (LSP) Implementation:** Given the extreme volatility and cognitive load in `LanguageServerProjectSystem.cs` and `AbstractLanguageServerProtocolTests.cs`, distribute domain knowledge regarding workspace synchronization to reduce the reliance on single contributors.
3. **Modularize the Semantic Binder:** `Binder_Expressions.cs` is a monolithic orchestrator containing nearly 12k LOC. While rewriting the binder is unfeasible, establish stricter logical boundaries within the partial class for discrete expression types to lower the cognitive load required during semantic analysis debugging.


---

**[⬅️ Back to Master Index](../index.md)**

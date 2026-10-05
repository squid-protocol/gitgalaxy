---
description: "You are operating within `vscode_cobol`, a Visual Studio Code extension designed for COBOL language support. The codebase is primarily composed of..."
---
# AGENTS.md: vscode_cobol Architectural Context & Engagement Rules

## 1. Information Flow & Purpose (The Executive Summary)
You are operating within `vscode_cobol`, a Visual Studio Code extension designed for COBOL language support. The codebase is primarily composed of TypeScript (48.8%) and JSON configuration files (29.4%), which is standard for the VS Code extension ecosystem.
* **Architectural Paradigm:** The repository functions as a "Cluster 3" macro-species with a high Architectural Drift Z-Score of 4.988. The network topology demonstrates completely flat Modularity (0.0) and Assortativity (0.0). This indicates a highly monolithic, "hub-and-spoke" architecture where all features converge on a few massive orchestrator files (like `extension.ts` and `cobolsourcescanner.ts`).
* **Information Flow:** Execution flows from VS Code extension activation points (`src/extension.ts`, `src/web/extension.ts`) down into language service providers (completion, symbols, hover) which overwhelmingly rely on the central `cobolsourcescanner.ts` to parse and tokenize COBOL source files.
* **Core Rule:** Adhere strictly to the VS Code Extension API boundaries and the existing tokenization paradigms. Do NOT attempt to deeply couple discrete language features (e.g., formatting, definitions, folding) together; they must remain isolated providers that query the central scanner state.

## 2. Notable Structures & Architecture
* **Fragile Orchestrators (High Coupling):** The primary orchestrators are `src/extension.ts` (51 outbound dependencies) and `src/vscommon_commands.ts` (21 outbound dependencies). These files bind the extension's lifecycle and command palette to the underlying logic. Modifying these registries carries a high risk of breaking extension activation.
* **Foundational Load-Bearers:** `src/cobolsourcescanner.ts` acts as the structural and operational core of the repository. It has extreme Data Gravity (Database Complexity: 200 on `processToken`) and acts as the source of truth for AST/token resolution.
* **Algorithmic Complexity:** The source scanning mechanisms (`processToken`, `relaxedParseLineByLine` in `src/cobolsourcescanner.ts`, and `getCachedObject` in `vscobolscanner.ts`) operate at extreme recursive time complexities (O(2^N) in static analysis). You MUST NOT introduce unbounded recursive loops, heavy synchronous blocking operations, or excessive object allocations on the critical path of text document parsing, as this will directly degrade the responsiveness of the editor.

## 3. Security & Vulnerabilities
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Weaponizable Injection Vectors:** Build and configuration files (`webpack.config.js`) exhibit 100% Weaponizable Injection Exposure. Ensure any modifications to build scripts strictly sanitize environment variables or dynamic path resolutions to prevent command injection.
2. **Exploit Generation Surface:** Code handling language syntax parsing and external API definitions (`src/keywords/mf_cbl_apis.ts`) possesses 100% Exposure for Exploit Generation. Because this extension parses arbitrary, untrusted COBOL text files provided by the user, ensure all Regex patterns are heavily vetted against Regular Expression Denial of Service (ReDoS) attacks.
3. **Supply Chain:** There are 129 unknown dependencies bypassing the Zero-Trust whitelist. Given the npm ecosystem, do not add or bump external packages in `package.json` without explicit architectural review.

## 4. Outliers & Extremes
* **The Hotspot Matrix (High Volatility + Risk):** `src/cobolsourcescanner.ts` is the single most critical friction point in the repository. It exhibits 100% Churn, 85% Cognitive Load, and the highest Cumulative Risk (628.36).
* **Extreme Key Person Silos:** The repository has a severe "Bus Factor" risk. The absolute most critical files—`src/cobolsourcescanner.ts`, `src/vscobolutils.ts`, `src/vscommon_commands.ts`, `src/extension.ts`, and `src/vsformatconverter.ts`—are maintained almost entirely by a single developer (`spgennard` has ~100% isolated ownership).
* **Design Slop:** Files such as `src/vscobolutils.ts` and `src/filesourcehandler.ts` reflect high orphaned function counts. Do not autonomously prune this logic, as it often represents public API surface area intended for VS Code dynamic invocation or future feature development.
* **Blind Bottlenecks:** Shell scripts supporting the CI/CD pipeline and publishing (`gen_changelog.sh`, `publish.sh`, `publishit2gitonly.sh`) exhibit 100% Documentation Risk paired with high blast radii for the delivery mechanism.

## 5. Recommended Next Steps (Refactoring for Stability)
To stabilize the architecture and reduce cognitive load for ongoing maintenance, prioritize the following pragmatic actions:

1. **Decompose the Scanner Monolith:** `src/cobolsourcescanner.ts` is a massive God Node with 3400+ LOC, O(2^N) complexity, and 100% isolated ownership. Begin extracting specific parsing domains (e.g., token classification, copybook resolution) into isolated, testable modules. This will lower the cognitive load and isolate churn.
2. **Mitigate Key Person Dependency (Bus Factor):** The entire extension heavily relies on `spgennard`. Introduce rigorous architectural documentation and JSDoc/TSDoc type annotations to `src/vscobolutils.ts` and `src/vscommon_commands.ts` to democratize understanding of the extension's initialization and utility flows.
3. **Document CI/CD Blind Bottlenecks:** Add explicit inline documentation to `publish.sh` and `gen_changelog.sh`. Because these files govern the release process and are currently "flying blind," establishing documented contracts will prevent accidental deployment failures.


---

**[⬅️ Back to Master Index](../index.md)**

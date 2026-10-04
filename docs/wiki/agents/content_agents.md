---
description: "You are operating within the `content` repository (MDN Web Docs), which is fundamentally a massive static content hub. The repository is overwhelmingly..."
---
# AGENTS.md: content Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within the `content` repository (MDN Web Docs), which is fundamentally a massive static content hub. The repository is overwhelmingly composed of Markdown files (99.5%), serving as the single source of truth for web documentation. 
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species. Because it is primarily a data repository rather than a traditional application, it exhibits a perfectly flat network topology (Modularity 0.0, Assortativity 0.0). The true engineering architecture lies not in the content itself, but in the Node.js toolchain (`scripts/`) responsible for continuous integration (CI), pull request analysis, and front-matter validation. 
* **Core Rule:** Maintain a strict boundary between content and automation. Do NOT attempt to introduce application logic or execution context into the Markdown files. All structural changes to the CI/CD pipeline must be constrained to the `scripts/` directory.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Several core file-system traversal and parsing scripts (`walkSync` in `scripts/utils.js`, `yargs` in `scripts/analyze-pr-build.js`, and `checkFrontMatter` in `scripts/front-matter_utils.js`) exhibit O(2^N) recursive time complexities in static analysis. Given the immense volume of files (~14,000+), you MUST NOT introduce unbounded recursion or synchronous, blocking I/O loops that iterate over the entire content tree.
* **Orchestrator Fragility:** The Node.js scripts act as the fragile orchestrators of this repository. Tools like `scripts/filecheck/checker.js` (19 outbound dependencies) and `scripts/analyze-pr-build.js` govern the repository's integrity. Modifying the AST validation, markdown linters, or URL checkers requires immediate verification against a local content build.
* **Front-Matter Integrity:** `scripts/front-matter_utils.js` enforces the schema for the documentation. Any automated edits to front-matter must strictly align with the established JSON/YAML schemas, as downstream consumers (like the MDN platform renderer) depend on this deterministic structure.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes" within the automation layer. They possess high cumulative risk, handle complex state, or represent Key Person Silos. 

**MANDATORY RULE:** You require explicit human permission and local build verification before modifying the structural signatures, I/O handling, or public APIs of these files:
* `scripts/analyze-pr-build.js` (Massive Structural Mass: 718.96, Key Person Silo - 100% isolated ownership by Claas Augner. This dictates PR gating logic.)
* `scripts/front-matter_utils.js` (Highest Cumulative Risk: 542.78, governs all content schema validation.)
* `scripts/filecheck/checker.js` (Core asset and compression validator, high I/O latency risk.)
* `scripts/content/release-firefox.js` (Key Person Silo - 100% isolated ownership by Vadim Makeev.)
* `scripts/update-moved-file-links.js` (High state flux; orchestrates link resolution across the 14k+ file corpus.)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH CI/CD CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **CI/CD Execution Surface:** While the markdown files are inert, the scripts in the `scripts/` directory execute in a CI/CD environment with elevated permissions. You MUST ensure that scripts like `analyze-pr-build.js` safely sanitize and parse inputs (such as branch names or PR titles) to prevent command injection vulnerabilities during the GitHub Actions workflow.
2. **Hardcoded Payload Artifacts:** The `.npmrc` file is flagged with a 100% exposure for hardcoded payloads. This is a standard configuration file for the Node package manager; do NOT flag this as a leaked secret unless it contains plain-text authentication tokens.
3. **Supply Chain:** There are 32 unknown dependencies bypassing the Zero-Trust whitelist. Do not add or bump external NPM packages in `package.json` without explicit architectural review to mitigate supply chain risks.

## 5. Environmental Tooling (The Oracle)
Do not guess front-matter schema constraints, hallucinate script dependency trees, or rely on generalized Node.js knowledge to determine blast radius within this automation layer. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target script.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

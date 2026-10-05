---
description: "You are operating within the `laravel/laravel` repository. It is critical to understand that this is the **application scaffolding** repository, not..."
---
# AGENTS.md: laravel Architectural Context & Engagement Rules

## 1. Information Flow & Purpose (The Executive Summary)
You are operating within the `laravel/laravel` repository. It is critical to understand that this is the **application scaffolding** repository, not the core `laravel/framework`. Comprising roughly 300 lines of code, it is heavily dominated by PHP (71.4%) and serves as the initial skeleton for new Laravel projects. 

* **Architectural Paradigm:** The system maps to a "Cluster 3" macro-species with a high Architectural Drift Z-Score of 5.215. The network topology demonstrates a completely flat structure (Modularity: 0.0, Assortativity: 0.0). This indicates an uncoupled, highly localized architecture where files exist primarily to configure or bootstrap the underlying `Illuminate` framework rather than interact with one another.
* **Information Flow:** Information flows unilaterally from HTTP entry points (`public/index.php`) or CLI commands (`artisan`) through the bootstrapping phase (`bootstrap/app.php`, `bootstrap/providers.php`) and into the core framework.
* **Core Rule:** Adhere strictly to Laravel's convention-over-configuration paradigms. Do NOT attempt to deeply couple these scaffolding files together; they are meant to remain isolated configuration and bootstrapping endpoints.

## 2. Notable Structures & Architecture (Dependency Graph)
Because this is a scaffolding repository, the dependency graph is intentionally sparse. 
* **Fragile Orchestrators (High Coupling):** The primary orchestrators are configuration and bootstrapping files that pull in framework dependencies. `app/Models/User.php` (7 outbound dependencies), `config/logging.php` (4 outbound), and `bootstrap/app.php` (3 outbound) act as the primary routing hubs for framework instantiation and initial data modeling.
* **Foundational Load-Bearers:** There are virtually no highly depended-upon files within the scaffolding itself. Files like `Controller.php` and `providers.php` exhibit 0 inbound connections within this specific repository scope, as they are meant to be extended by future user-written code.

## 3. Security & Vulnerabilities
**Status: SECURE PERIMETER.** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Hardcoded Payload Artifacts:** The `.npmrc` file triggered a 100% Exposure warning for hardcoded payloads. This is a common false-positive in scaffolding repositories where package manager configurations are pre-populated, but you MUST ensure no actual authentication tokens are inadvertently committed here during development.
2. **Ecosystem Security:** The repository relies on 3 unknown dependencies that bypass the Zero-Trust whitelist, and 1 binary anomaly was detected. Ensure any additions to `composer.json` or `package.json` are strictly vetted against authorized package registries.

## 4. Outliers & Extremes
Given the minimal scale of the repository, statistical outliers highlight minor structural debt rather than catastrophic failure points.
* **Tech Debt & Cognitive Load:** `app/Models/User.php` and `database/factories/UserFactory.php` represent the highest Cumulative Risk (325.2 and 318.39, respectively). This is driven by high relative Tech Debt and Verification exposure due to their role as boilerplate templates requiring downstream modification.
* **State Flux:** The `artisan` console executable exhibits the highest state mutation rate (8.7% exposure). Modification of this file should be avoided unless explicitly required for low-level CLI bootstrapping changes.
* **Blind Bottlenecks:** `vite.config.js`, `bootstrap/app.php`, and `bootstrap/providers.php` act as "God Nodes" for asset compilation and application lifecycle, yet exhibit near 100% Documentation Risk. They are "flying blind" and rely entirely on external framework knowledge.

## 5. Recommended Next Steps (Refactoring for Stability)
To stabilize the scaffolding for downstream autonomous agents or developers, prioritize the following actions:

1. **Mitigate Blind Bottlenecks:** Add explicit, structured documentation (JSDoc/PHPDoc) to `vite.config.js` and `bootstrap/app.php`. Explaining their exact role in the asset pipeline and framework bootstrapping will reduce their severity as undocumented choke points.
2. **Resolve Design Slop in Providers:** The `app/Providers/AppServiceProvider.php` file contains functions (`boot`, `register`) flagged as "orphaned" because they are invoked dynamically by the framework, not directly by local code. Add inline architectural comments clarifying their framework-driven lifecycle to suppress static analysis warnings and guide future agents.


---

**[⬅️ Back to Master Index](../index.md)**

---
description: "You are operating within `jellyfin`, a sprawling, high-performance media server ecosystem. The repository is overwhelmingly dominated by C# (91.2%) and..."
---
# AGENTS.md: jellyfin Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `jellyfin`, a sprawling, high-performance media server ecosystem. The repository is overwhelmingly dominated by C# (91.2%) and relies heavily on ASP.NET Core idioms, Dependency Injection (DI), and reflection.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a severe Architectural Drift Z-Score of 7.137. The network topology demonstrates completely flat Modularity (0.0) and Assortativity (0.0). This indicates a highly coupled, monolithic architecture where nearly all execution logic converges on a few massive God Nodes (like `BaseItem.cs`, `ApplicationHost.cs`). 
* **Core Rule:** Maintain strict adherence to the existing Dependency Injection and interface contracts. Do NOT attempt to decouple foundational orchestrators or introduce asynchronous messaging into synchronous initialization paths; the architecture relies on tightly synchronized execution during application startup and plugin loading.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core parsing and resolution mechanics (`Parse` in `EpisodePathParser.cs`, `Resolve` in `VideoListResolver.cs`) and file I/O operations (`GetDrives` in `ManagedFileSystem.cs`) operate at extreme recursive time complexities (O(2^N) in static analysis). You MUST NOT introduce unbounded recursive loops, unbounded regex evaluations, or synchronous blocking disk I/O in the hot paths of library scanning or media probing.
* **Orchestrator Fragility:** Central orchestrators such as `ApplicationHost.cs` (100 outbound dependencies), `LibraryController.cs`, and `SessionManager.cs` are highly fragile. Modifying plugin registration, session tracking, or core API routing requires immediate, comprehensive verification via the integration test suite.
* **Avoid Dead Code Pruning:** The repository contains massive volumes of logic flagged as "dead code" (e.g., `BaseItem.cs` with 46 orphaned functions, `BaseItemRepository.cs` with 25). DO NOT autonomously attempt to prune, format, or clean up these files. Jellyfin relies heavily on Entity Framework/ORM reflection, implicit JSON serialization binding, and DI container wiring that bypasses static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream integration testing before modifying the structural signatures, database queries, or public APIs of these files:
* `MediaBrowser.Controller/Entities/BaseItem.cs` (Massive Structural Mass: 2692.2, 85.1% Churn. The absolute core of the media domain model).
* `Jellyfin.Api/Controllers/ImageController.cs` (Key Person Silo - 100% isolated ownership by JPVenson. High logic bomb and exploit generation risk).
* `MediaBrowser.Providers/Manager/ProviderManager.cs` (Core metadata orchestration; high concurrency and caching risk).
* `src/Jellyfin.Database/Jellyfin.Database.Implementations/Entities/BaseItemEntity.cs` (Critical data gravity; dictates the SQLite/EF Core schema).
* `Jellyfin.Server/Extensions/ApiServiceCollectionExtensions.cs` (Extreme fragility; dictates the entire DI container and middleware pipeline).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH INJECTION CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Files handling web server routing and dynamic streams (`ApplicationHost.cs`, `DynamicHlsController.cs`, `AuthorizationContext.cs`) possess 100% Exposure for Exploit Generation. You MUST ensure strict input validation and authorization checks, particularly around session tokens and streaming parameters.
2. **Weaponizable Injection Vectors:** String parsing utilities (`src/Jellyfin.Extensions/StringExtensions.cs`) and path resolvers (`AudioBookResolverTests.cs`) exhibit 100% Injection Surface risk. Ensure all dynamic SQL queries (if any) are strictly parameterized and file path inputs are rigorously sanitized against Directory Traversal attacks.
3. **Obfuscation / XML Parsing:** NFO metadata parsers (`MovieNfoParserTests.cs`, `BaseNfoParser.cs`) handle untrusted XML inputs from the file system. Modifications here must enforce secure XML parsing settings to prevent XXE (XML External Entity) injection attacks.

## 5. Environmental Tooling (The Oracle)
Do not guess Entity Framework associations, hallucinate FFmpeg CLI arguments (`MediaEncoder.cs`), or rely on generalized C# knowledge to determine blast radius within this 594k+ LOC system. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

---
description: "You are operating within `curl`, the ubiquitous command-line tool and library for transferring data with URLs. The repository is primarily composed of..."
---
# AGENTS.md: curl Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `curl`, the ubiquitous command-line tool and library for transferring data with URLs. The repository is primarily composed of C (45.6%) for the core libcurl library and CLI tool, heavily supported by Perl (16.8%), Python (10.7%), and Shell (6.8%) for testing, build automation, and documentation generation.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 6.778. The network topology demonstrates moderate Modularity (0.4337) but highly negative Assortativity (-0.2987). This indicates a fragile "hub-and-spoke" model where a few highly connected foundational headers (e.g., `src/tool_setup.h`, `src/tool_cfgable.h`) act as single points of failure for a wide array of execution logic. Do not attempt to introduce deep object-oriented abstractions or modernize the C-ABI; the system relies on flat, procedurally-driven C coupled via global configuration structs.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Test infrastructure and build scripts (`startnew` in `tests/servers.pm`, `render` in `scripts/managen`, `nostrings` in `scripts/checksrc.pl`) operate at extreme O(2^N) recursive time complexities. Similarly, core CLI parsing (`tool2curlparts` in `src/tool_formparse.c`) exhibits deep algorithmic density. You MUST NOT introduce additional nested recursion or unbounded loops in the HTTP/FTP test server implementations or the CLI argument parsing routines.
* **Orchestrator Fragility:** Central orchestrators such as `src/tool_operate.c` (39 outbound dependencies) and `tests/runtests.pl` are highly fragile. Any changes to CLI state operations, configuration loading, or the test harness require immediate, comprehensive verification across the entire test suite.
* **Avoid Dead Code Pruning:** Files like `tests/http/testenv/env.py` (42 orphaned functions) and OS-specific implementations (`projects/OS400/ccsidcurl.c`) contain high volumes of logic flagged as "dead code." DO NOT autonomously attempt to prune, format, or clean up these files. Curl utilizes extensive platform-specific conditional compilation (`#ifdef`) and dynamic test scaffolding that static analysis tools misinterpret as unused logic.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream cross-platform testing before modifying the structural signatures, raw memory mapping, or public APIs of these files:
* `scripts/checksrc.pl` & `scripts/managen` (Massive Structural Mass and Key Person Silos - 100% isolated ownership by Viktor Szakats)
* `src/tool_getparam.c` (High Cognitive Load: 90.2%, core CLI argument processor)
* `tests/testcurl.pl` & `tests/servers.pm` (Key Person Silos - Viktor Szakats. Highly complex, legacy test infrastructure)
* `src/tool_cfgable.h` (Severe Blind Bottleneck - 1282.4 Severity, flying blind with 92.6% Doc Risk)
* `src/tool_setup.h` (Foundational Load-Bearer - 80 inbound connections)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH SCRIPTING CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Operations inside `src/tool_cb_hdr.c`, `src/config2setopts.c`, and `src/tool_operate.c` rely heavily on raw memory manipulation and pointer arithmetic (10% Exposure). Any `malloc`, buffer parsing, or struct casting here must be rigorously scrutinized for out-of-bounds access or memory leaks, especially when parsing arbitrary server responses.
2. **Exploit Generation Surface:** CI/CD and documentation scripts (`scripts/completion.pl`, `scripts/mdlinkcheck`) possess a 100% Exposure score for Exploit Generation. Ensure that any modifications to automation scripts strictly validate inputs to prevent command injection during the build process.
3. **Hardcoded Payload Artifacts:** `scripts/mk-ca-bundle.pl` tripped hardcoded payload signatures. DO NOT flag this as a leaked secret; it is an explicit script designed to download and generate Certificate Authority (CA) bundles.
4. **Supply Chain / Binary Data:** There are 18 binary anomalies identified by X-Ray (likely protocol fuzzing seeds or compiled test fixtures). Do not alter or attempt to scan these binary blobs without explicit architectural review.

## 5. Environmental Tooling (The Oracle)
Do not guess configuration struct mappings, hallucinate C macro definitions, or rely on generalized POSIX knowledge to determine blast radius within this highly cross-platform tool. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

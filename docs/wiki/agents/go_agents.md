---
description: "You are operating within the `go` repository, the core compiler, runtime, and standard library for the Go programming language. The codebase is..."
---
# AGENTS.md: go Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within the `go` repository, the core compiler, runtime, and standard library for the Go programming language. The codebase is massively scaled (1.2M+ LOC) and dominated by Go (69.5%), supplemented by assembly (5.9%) for architecture-specific optimizations and a large volume of test data/plaintext.
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 5.343. The network topology demonstrates moderate Modularity (0.3526) but significant negative Assortativity (-0.2811). This indicates a highly organized, layered architecture where isolated sub-packages (e.g., `net/http`, `crypto/tls`) are strictly coupled to central, pervasive core packages (`fmt.go`, `testing.go`, `unsafe.go`).
* **AI & Machine Learning Topology:** The repository contains a "Local Sovereignty" integration. The AI components act as a 'Pure Producer' with a massive blast radius. Do NOT modify these foundation models without rigorous verification, as hallucinations here cascade catastrophically.
* **Core Rule:** Maintain strict adherence to Go's established package boundaries and dependency injection principles. Do NOT introduce circular dependencies or break the standard library's rigorous backward compatibility guarantees (Go 1 compatibility promise).

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core compiler passes (`regalloc` in `ssa/regalloc.go`, `rewriteNewPhis`), cryptographic assembly select loops, and garbage collection routines operate at extreme recursive time complexities (O(2^N) in static analysis) due to deep graph traversal and state management. You MUST NOT introduce unbounded recursion, heavy synchronous blocking operations, or excessive object allocations on the critical path of the compiler, runtime, or standard library networking (`net/http`).
* **Orchestrator Fragility:** Central orchestrators such as `mldsa_test.go` (466 outbound dependencies), `xml.go` (275 outbound), and `arshal_test.go` (167 outbound) are highly fragile. Modifying XML/JSON serialization logic, FIPS cryptographic boundaries, or the SSA compiler requires immediate, comprehensive verification via the massive `all.bash` test suite.
* **Avoid Dead Code Pruning:** The extensive `testdata/` directories and reflection testing suites (e.g., `src/reflect/all_test.go` with 172 orphaned functions) contain massive volumes of logic flagged as "dead code." DO NOT autonomously attempt to prune, format, or clean up these files. The Go compiler and reflection tests utilize dynamic test case generation and AST parsing that bypass static dependency resolution.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream `all.bash` verification before modifying the structural signatures, concurrency models, or public APIs of these files:
* `src/cmd/compile/internal/ssagen/ssa.go` (Massive Structural Mass: 8483.7. The core bridge between the AST and the SSA compiler backend).
* `src/net/http/internal/http2/server_test.go` & `transport_test.go` (Highest Cumulative Risk. Key Person Silos - overwhelmingly owned by Damien Neil. Critical HTTP/2 infrastructure).
* `src/cmd/go/internal/fmtcmd/fmt.go` (Severe House of Cards/Blind Bottleneck - 1591 inbound connections with high Error/Doc Risk).
* `src/runtime/mheap.go` & `src/runtime/malloc.go` (Extreme Volatility Hotspots: >80% Churn. Core memory allocator logic).
* `src/debug/elf/elf.go` & `src/cmd/compile/internal/syntax/parser.go` (Key Person Silos - 100% isolated ownership by specific maintainers).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY & EXPLOIT CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Operations within the `runtime/cgo/` and `syscall/` directories inherently rely on raw memory manipulation and pointer arithmetic (e.g., `libcgo.h`). Any `unsafe.Pointer` casting, CGO boundary calls, or assembly modifications must be mathematically proven to prevent Use-After-Free (UAF), buffer overflows, or runtime panics.
2. **Exploit Generation Surface:** Files handling archive extraction (`archive/zip/reader.go`) and buffer manipulation (`bytes/buffer_test.go`) possess 100% Exposure for Exploit Generation. You MUST ensure strict bounds checking, canonical path resolution, and zip-slip protections when handling untrusted compressed payloads.
3. **Weaponizable Injection Vectors:** The `html/template` package and module loading logic (`cmd/go/internal/modload/build.go`) are flagged for injection vectors. Ensure strict contextual escaping in templates and sanitize all module paths to prevent arbitrary code execution or cross-site scripting (XSS).
4. **Hardcoded Payload Artifacts:** Files such as `example-cert.pem` and `platform_root_cert.pem` tripped hardcoded payload signatures. DO NOT flag these as leaked secrets; they are explicit cryptographic test fixtures required for verifying TLS and X.509 certificate chains.

## 5. Environmental Tooling (The Oracle)
Do not guess SSA pass behaviors, hallucinate CGO boundary marshaling, or rely on generalized Go knowledge to determine blast radius within this foundational compiler and runtime. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

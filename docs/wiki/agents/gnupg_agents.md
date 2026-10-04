---
description: "You are operating within `gnupg`, the GNU Privacy Guard, a complete and free implementation of the OpenPGP standard. The execution logic is heavily..."
---
# AGENTS.md: gnupg Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `gnupg`, the GNU Privacy Guard, a complete and free implementation of the OpenPGP standard. The execution logic is heavily dominated by C (47.6% of files, but containing the vast majority of execution mass), supplemented by Scheme (11.3%) for the test suite (`gpgscm`). 
* **Architectural Paradigm:** This repository functions as a "Cluster 4" macro-species and exhibits a high Architectural Drift Z-Score of 6.174. The network topology demonstrates unusually high Modularity (0.7544) combined with positive Assortativity (0.2122). This indicates a highly organized, domain-segregated architecture (e.g., separating `g10` for OpenPGP, `sm` for S/MIME, `agent` for key management, and `dirmngr` for networking) where core cryptographic utilities interact cleanly, but rely on densely packed structural headers.
* **Core Rule:** Maintain strict adherence to the existing subsystem boundaries. Do NOT introduce cross-coupling between `g10` (OpenPGP), `sm` (S/MIME), and `dirmngr` (network operations) outside of their established IPC (Assuan) interfaces. 

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core data streaming, caching, and parsing routines (`agent_get_cache` in `agent/cache.c`, `block_filter` and `direct_open` in `common/iobuf.c`) operate at extreme recursive time complexities (O(2^N) in static analysis) due to nested memory buffering and ASN.1/TLV parsing. You MUST NOT introduce unbounded recursive loops, dynamic memory allocations on the hot path, or heavy synchronous blocking operations into the core I/O loops.
* **Orchestrator Fragility:** Central orchestrators such as `g10/gpg.c` (42 outbound dependencies) and `dirmngr/dns.c` (35 outbound) are highly fragile. Modifying the main event loops, argument parsing, or Assuan command dispatchers requires immediate, comprehensive verification against the `gpgscm` test suite.
* **Avoid Dead Code Pruning:** Files like `g10/gpgv.c` (55 orphaned functions) and `common/stringhelp.c` (45 orphaned functions) contain logic flagged as "dead code." DO NOT autonomously attempt to prune, format, or clean up these files. GnuPG heavily utilizes conditional compilation macros, platform-specific shims, and shared common objects that bypass static dependency resolution for specific build targets (e.g., Windows vs. POSIX).

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream cryptographic test verification before modifying the structural signatures, key parsing logic, or public APIs of these files:
* `g10/gpg.c` & `g10/keyedit.c` (Massive Structural Mass and Key Person Silos - overwhelmingly owned by Werner Koch. The absolute core of the OpenPGP implementation).
* `g10/export.c` (Highest Cumulative Risk: 580.28, 100% Silo Risk. Critical data serialization boundary).
* `dirmngr/dns.c` (Key Person Silo - 100% isolated ownership by NIIBE Yutaka. Core networking and DNS resolution logic).
* `tools/gpg-card.c` (High Secrets Risk and Cognitive Load. Manages smartcard interactions).
* `agent/agent.h` & `g10/main.h` (Severe Blind Bottlenecks - Huge blast radius with high Documentation Risk. Modifications here cascade across the entire compilation unit).

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH RAW MEMORY & EXPLOIT CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts. 

**CRITICAL WARNINGS:**
1. **Raw Memory Manipulation:** Operations within the `common/` and `agent/` directories (`iobuf.c`, `tlv-parser.c`, `agent.h`) inherently rely on raw memory manipulation and pointer arithmetic (10% Exposure). Because this software processes untrusted, adversarial cryptographic payloads, any modifications to parsing (e.g., OpenPGP packets, X.509 certs) must be mathematically proven to prevent Buffer Overflows, Use-After-Free (UAF), or out-of-bounds reads.
2. **Exploit Generation Surface:** Network-facing daemons and input handlers (`dirmngr/dirmngr.c`, `common/ksba-io-support.c`) possess a 20% Exposure score for Exploit Generation. You MUST ensure strict input sanitization, safe integer arithmetic for length fields, and robust error handling to prevent Denial of Service (DoS) or RCE vulnerabilities.
3. **Hardcoded Payload Artifacts:** Files such as `dirmngr/sks-keyservers.netCA.pem` and `doc/com-certs.pem` are flagged for hardcoded payloads. DO NOT flag these as leaked secrets; they are explicit cryptographic trust anchors and test fixtures required for verifying network security.

## 5. Environmental Tooling (The Oracle)
Do not guess Assuan IPC protocol behaviors, hallucinate OpenPGP packet structures, or rely on generalized C knowledge to determine blast radius within this mature cryptographic utility. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**

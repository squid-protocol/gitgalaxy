# How to Map and Refactor Legacy COBOL Monoliths

Enterprise migrations from legacy IBM Mainframes to the cloud are notoriously dangerous. Decades of technical debt result in millions of lines of code where no one knows what is actually executing, what is dead "Graveyard" memory, and how data physically flows between batch jobs.

Traditional lift-and-shift tools just move the bloat to the cloud. GitGalaxy solves this using the **COBOL Refractor Controller**, a hybrid-memory orchestration engine that mathematically isolates dead code, maps deterministic data lineage, and generates a "Clean-Room" environment. 

The outputs of this engine provide a dual guarantee: the sanitized code natively compiles against raw MVS 3.8j operating systems (1974 Hercules Mainframe), while simultaneously scaffolding modern cloud environments (PostgreSQL DDLs and JSON schemas).

## The Orchestration Engine

Because enterprise mainframes can contain terabytes of source code, the Refractor Controller uses a dynamic scale sensor. It defaults to a high-speed RAM dictionary for standard repos, but automatically shifts to a SQLite3 Storage Engine if the codebase hits critical mass, preventing Out-Of-Memory (OOM) crashes.

### 1. Execute the Refraction Pipeline
Point the controller at your legacy COBOL directory. You can optionally pass a specific target variable (`--var`) to trigger the Microservice Slicer to recursively taint-track business logic across the AST.

```bash
python gitgalaxy/cobol_refractor_controller.py /path/to/cics-banking-sample-application-cbsa --var WS-ACCOUNT-BALANCE
```

### 2. Era-Aware Mainframe Compiler Forge
Before code is migrated, it must be validated. The GitGalaxy **Compiler Forge** guarantees the sanitized legacy code will still compile. 

Because enterprises mix decades of code, the Forge utilizes a **Dialect Sensor**. It scans the AST for post-1974 structural keywords (like `EVALUATE` or `END-IF`). 
* If it detects COBOL-85, it dynamically routes the build JCL to modern enterprise compilers (`IGYWCL`). 
* If it detects COBOL-74, it routes to legacy OS/VS compilers (`COBUCL`) to prevent catastrophic compiler strokes.

Simultaneously, the Forge recursively flattens and inlines all `COPY` statements (with a hard failsafe depth of 10 to prevent infinite RAM loops from cyclic copybooks).

### 3. Analyze the Master Audit Report
The Controller spins up a timestamped `_gitgalaxy_clean` directory containing 6 distinct artifact pipelines. It expands copybooks inline, drops orphaned variables, strips away unreachable "Phantom Paragraphs," and maps the true I/O intent of the system.

It outputs a `master_refraction_audit.txt` report proving the exact code bloat reduction:

```text
==========================================================
 GITGALAXY MODERNIZATION REPORT
==========================================================

[1] EXECUTIVE METRICS & NECROSIS REDUCTION
----------------------------------------------------------
  • Files Scanned           : 29
  • State Manager Mode      : RAM
  • Unused Memory Addresses : 817 orphaned variables
  • Unreachable Logic Blocks: 590 phantom paragraphs
  ✂️ Estimated Bloat Removed: ~6717 Lines of Code

[2] ZERO-TRUST JCL ARCHITECTURE
----------------------------------------------------------
  • Programs Audited           : 29
  • Original Legacy LOC        : 18,450 lines
  • GitGalaxy Zero-Trust LOC   : 11,733 lines
  📉 Total Code Bloat Removed  : 36.4%
  🛡️ Over-Permissioned I/O     : 14 physical files secured

[3] GENERATED CLOUD SCAFFOLDING
----------------------------------------------------------
  • PostgreSQL DDLs & JSON Schemas Forged : 29
  • Zero-Trust Emulator JCLs Generated    : 29
  • Isolated Microservice Slices Extracted: 1 (Target: WS-ACCOUNT-BALANCE)

[4] ⚠️ MANUAL INTERVENTION AUDIT (HONESTY PROTOCOL)
----------------------------------------------------------
  • AI Agent Job Tickets Generated : 5
  The following files contain structural anomalies that require architectural review:
  [!] [XFRFUN.cbl : Line 0128] HIGH LIMIT - Macro substitution detected. AST math may drift.
  [!] [CREACC.cbl : Line 0260] HIGH LIMIT - Macro substitution detected. AST math may drift.
  [!] [INQACC.cbl : Line 0199] HIGH LIMIT - Macro substitution detected. AST math may drift.
  [!] [DELACC.cbl : Line 0200] HIGH LIMIT - Macro substitution detected. AST math may drift.
  [!] [GETSCODE.cbl : Line 0028] HIGH LIMIT - Macro substitution detected. AST math may drift.
```

### 4. AI Agent Task Forge & The Honesty Protocol
COBOL contains "Ancient Dragons"—structural commands like `ALTER`, `COPY REPLACING`, or `CICS ASYNC JUMPS` that dynamically rewrite the execution flow at runtime. These break deterministic mathematical mapping.

GitGalaxy enforces an **Honesty Protocol**. When the System Limits Reporter detects one of these anomalies, it triggers the **Autonomous Agent Task Forge**.

Instead of letting an LLM guess how to fix the file (which leads to catastrophic hallucinations), the Forge bounds the AI. It generates a strict JSON job ticket (`06_ai_agent_jobs/XYZ_agent_job.json`) that explicitly defines the extracted lineage (required inputs, outputs, and external calls). 

The LLM is dispatched as a deterministic Systems Architect, tasked solely with resolving the specific structural anomaly without altering the core business logic.

### 5. From the map to a proven port
A flag in the audit above is a reason for review, not a reason the program cannot be ported. Three of the CBSA programs it flags (XFRFUN, INQACC and DELACC, each with `COPY REPLACING`) now have deterministic Java ports proven against the original COBOL on a real Db2, with no model involved. CREACC is not proven yet, for a different reason: its COMMAREA carries data after a POINTER, and a POINTER is 8 bytes under the test oracle but 4 on z/OS (register entry C9). See [Proven COBOL-to-Java Ports](../05-19-proven-cobol-to-java-ports.md).

> **Read the full technical specification:** [Legacy Refraction Controller](../05-01-legacy-refraction-controller.md)
> **And:** [Proven COBOL-to-Java Ports](../05-19-proven-cobol-to-java-ports.md)

---

**[⬅️ Back to Master Index](../index.md)**

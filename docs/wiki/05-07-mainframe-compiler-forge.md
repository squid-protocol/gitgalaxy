# Mainframe Compiler Generator

> **File Reference:** [`gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py)

> **Architecture: Dialect Detection, Copybook Resolution, & JCL Compilation Scaffolding**
>
> **Summary:** The Mainframe Compiler Generator (`cobol_compiler_forge.py`) dynamically produces Job Control Language (JCL) build scripts required to compile legacy COBOL modules on MVS mainframe platforms. It inspects source code constructs to detect language standard dialects (COBOL-74 vs. COBOL-85) and automatically routes build jobs to the compatible compiler utility (`COBUCL` or `IGYWCL`).

## Language Dialect Detection

Mainframe compilers enforce strict syntax rules based on language standards. Attempting to compile post-1985 syntax features using a legacy 1974 compiler results in compilation failures.

The generator inspects source text for modern COBOL signatures (`detect_cobol_dialect`):
* **Signatures:** Scans for keywords such as `EVALUATE`, `INITIALIZE`, explicit scope terminators (`END-IF`, `END-PERFORM`, `END-READ`), and inline comments (`*>`).
* **Compiler Routing:** If modern signatures are detected, the build step targets the Enterprise COBOL compiler procedure (`IGYWCL`). If absent, the job defaults to the OS/VS COBOL compiler procedure (`COBUCL`).

## Recursive Copybook Flattening

Legacy COBOL codebases separate record definitions into external copybook files (`COPY` statements). To build self-contained compilation payloads, the generator recursively resolves and inlines copybook contents (`flatten_copybooks`):

* **Cyclic Dependency Guard:** Mainframe projects occasionally contain circular copybook references. The flattener enforces a maximum recursion depth (`MAX_RECURSION_DEPTH = 10`). If recursion exceeds this threshold, the branch is truncated to prevent stack overflow or memory exhaustion.

## Dataset Allocation & Build JCL Scaffolding

The generator extracts structural declarations to build the complete JCL compilation job (`generate_build_jcl`):
1. **Program Identity:** Extracts `PROGRAM-ID` definitions to assign job names and load module output locations (`HERC01.LOADLIB`).
2. **Dataset Provisioning:** Parses `SELECT ... ASSIGN TO` statements to construct Phase 1 dataset allocation steps using `IEFBR14`.
3. **Linkage Editing:** Configures linkage editor steps (`LKED`) to resolve standard system libraries (`SYS1.COBLIB`) and output binary load modules.

---

### Powered by GitGalaxy

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), a static analysis and knowledge graph engine for software modernization.

* [Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy) for code, tools, and updates.
* [Visualize your repository](https://gitgalaxy.io/) using our interactive WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**


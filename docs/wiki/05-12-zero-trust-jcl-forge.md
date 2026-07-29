# Job Control Language (JCL) Generator

> **File Reference:** [gitgalaxy/tools/cobol_to_cobol/cobol_jcl_forge.py](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/cobol_to_cobol/cobol_jcl_forge.py)

## Engineering Summary
This subsystem converts physical file requirements and execution intent extracted from COBOL source code into streamlined Job Control Language (JCL) scripts. It solves the problem of manually writing execution scripts by automatically provisioning only the exact dataset permissions required for a given program. It exists to enforce least-privilege resource access and modernize mainframe execution workflows. It fits into GitGalaxy by taking static analysis results and outputting operational execution environments. This subsystem is known as the Zero-Trust JCL Generator.

## Purpose
The purpose of this component is to parse COBOL source code for file bindings and subsystem usage, and generate standardized, single-step JCL scripts that map directly to the program's actual data access patterns.

## Problem Being Solved
Legacy JCL scripts are frequently over-permissioned, granting access to datasets the program never uses, and contain accumulated bloat from decades of manual edits. Manually auditing and rewriting these scripts is error-prone. This subsystem automates the creation of minimal-access scripts.

## Design
### Current Behavior
**Source Code Normalization & Intent Parsing**
The format normalizer strips 6-column sequence numbers and column 7 comment indicators (`*`, `/`) to consolidate 80-column punch card code into a continuous text stream. It extracts the program name from `PROGRAM-ID` (falling back to the source file name). It parses `SELECT ... ASSIGN TO` statements to extract internal file names and Data Definition (DD) target identifiers, stripping system prefixes like `UT-S-` or `UR-S-`. It scans for `EXEC CICS` (transactional engine) and `EXEC SQL` (database access) blocks, recording invocation counts and adding necessary operational flags (`CICS`, `DB2`).

**Execution Provisioning & Least Privilege Disposition**
Extracted file bindings are mapped to Data Set Parameters (`DISP`). Output datasets are assigned `DISP=(NEW,CATLG,DELETE)` with storage parameters appended (`SPACE=(CYL,(5,1),RLSE)`, `DCB=(LRECL=80,RECFM=FB,BLKSIZE=800)`). Input datasets receive `DISP=SHR` (Shared Read). If a dataset is declared in the file section but static lineage analysis shows no explicit open operations (`OPEN INPUT` / `OPEN OUTPUT`), it receives read-only access and an appended warning comment (`//* WARNING: NO EXPLICIT OPEN INTENT FOR ...`). The generator creates standardized job headers (`JOB`, `EXEC PGM=`, `STEPLIB`, `SYSOUT`, `SYSPRINT`, `SYSUDUMP`) and embeds custom corporate compliance headers.

## Pipeline Integration
**Inputs received:** Raw COBOL source files.
**Outputs produced:** Streamlined, modernized JCL scripts enforcing minimal access.
**Dependencies:** Upstream relies on the core static analysis engine to identify file and subsystem usage. Downstream, the output is consumed by the mainframe execution environment and verified by the JCL Security & Reduction Auditor.

```mermaid
flowchart LR
    A[COBOL Source Files] --> B[Zero-Trust JCL Generator]
    B --> C[Modernized JCL Scripts]
    C --> D[JCL Security Auditor]
```

## Tradeoffs
The design chooses to assign read-only access (`DISP=SHR`) to datasets that are declared but lack explicit `OPEN` operations. This choice ensures jobs won't fail catastrophically if dynamic logic opens the file, while preventing dangerous implicit write access. The rejected alternative was to omit unreferenced files entirely, which was sacrificed because hidden dynamic calls could crash the system. 

## Limitations
* Unrecognized third-party database or subsystem calls outside of standard `CICS` and `SQL` are not currently automatically provisioned.
* Standardized storage parameters (`SPACE`, `DCB`) for output files are hardcoded and may not match precise capacity requirements.

## Performance Notes
Using regex parsing on a normalized text stream allows the extraction of file bindings in a single pass without needing to instantiate a full AST, providing fast processing of large COBOL applications.

## Future Work
* **Planned Improvements:** Add dynamic calculation for `SPACE` parameter allocation based on upstream table definitions.
* Enhance support for dynamic or external file allocations injected at runtime.

## Related Components
* [JCL Security & Reduction Auditor](05-11-jcl-meta-auditor.md)

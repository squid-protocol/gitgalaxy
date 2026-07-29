# Job Control Language (JCL) Generator

> **File Reference:** [gitgalaxy/tools/cobol_to_cobol/cobol_jcl_forge.py](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/cobol_to_cobol/cobol_jcl_forge.py)
>
> **Architecture: Intent Extraction & Minimal Access Execution Provisioning**
>
> **Summary:** The Zero-Trust JCL Generator converts physical file requirements and execution intent extracted from COBOL source code into streamlined Job Control Language (JCL) scripts. It ensures generated execution scripts provision only the exact dataset permissions required for execution.

## Source Code Normalization & Intent Parsing

Legacy COBOL files format code across 80-column punch cards, causing file assignments to break across multiple lines or contain legacy margin indicators.

* **Format Normalizer:** Strips 6-column sequence numbers and column 7 comment indicators (`*`, `/`), consolidating source code into a normalized text stream.
* **Program Identifier Extraction:** Extracts the program name from `PROGRAM-ID` statements (falling back to the source file name if absent).
* **Batch File Assignments:** Parses `SELECT ... ASSIGN TO` statements to extract internal file names and Data Definition (DD) target identifiers, stripping system prefixes like `UT-S-` or `UR-S-`.
* **Subsystem Usage Scans:** Scans for `EXEC CICS` (transactional engine) and `EXEC SQL` (database access) blocks, recording invocation counts and adding necessary operational flags (`CICS`, `DB2`).

## Execution Provisioning & Least Privilege Disposition

The generator maps extracted file bindings to Data Set Parameters (`DISP`) to enforce least-privilege resource access:

* **Output File Allocations:** Assigns `DISP=(NEW,CATLG,DELETE)` to output datasets, appending storage parameters (`SPACE=(CYL,(5,1),RLSE)`, `DCB=(LRECL=80,RECFM=FB,BLKSIZE=800)`).
* **Input File Allocations:** Assigns `DISP=SHR` (Shared Read) to input datasets.
* **Unreferenced Binding Safeguard:** If a dataset is declared in the file section but static lineage analysis shows no explicit open operations (`OPEN INPUT` / `OPEN OUTPUT`), the generator assigns read-only access and appends a warning comment (`//* WARNING: NO EXPLICIT OPEN INTENT FOR ...`) for developer review.
* **Corporate Header & Job Cards:** Generates standardized job headers (`JOB`, `EXEC PGM=`, `STEPLIB`, `SYSOUT`, `SYSPRINT`, `SYSUDUMP`) and embeds custom corporate compliance headers when supplied.

<br><br>

---

### Ecosystem Integration

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), a static analysis and heuristic dependency mapping engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive dashboard.

---

**[⬅️ Back to Master Index](index.md)**


# JCL (IBM z/OS JCL)

## 1. At a glance

| Metric | Value |
| :--- | :--- |
| **Status** | production |
| **Target Version** | IBM z/OS JCL |
| **Lexical Family** | line_exclusive |
| **Rules Wired** | 11 / 24 |
| **Extraction tests** | 41 |
| **Strict tests** | 51 |

## 2. Identification surface

- **Extensions**: `.jcl`, `.prc`, `.bms`
- **Exact matches**: (none)
- **Discriminators**: `.cbl`, `.cob`, `.cpy`
- **Shebangs**: (none)

## 3. What GitGalaxy detects

**Topology & Structure**
- `branch`: Matches conditional structures like `IF`, `ELSE`, `ENDIF`.
- `args`: Matches step parameters (`PARM=`) and proc arguments (`PROC ...`).
- `structural_boundaries`: Matches structural statements and commands (`DD`, `INCLUDE`, `SET`, `PROC`, `PEND`).
- `func_start`: Matches JCL EXEC steps.
- `class_start`: Matches JCL JOB cards.

**Safety & Risk**
- `high_risk_execution`: Matches execution of specific programs via `PGM=`.

**Resource Management**
- `io`: Matches dataset definitions and I/O routing such as `DSN`, `DSNAME`, `SYSOUT`, `SYSPRINT`, `DISP=`.

**State Mutation**
- `state_mutation`: Matches JCL symbolic variable assignments via `SET`.

**Architecture & Domain Sensors**
- `import`: Matches JCL includes (`INCLUDE`).
- `_dependency_capture`: Captures the `MEMBER=` name for the dependency graph, as well as dataset names in `DD` statements and `JCLLIB` orders.
- `ownership`: Matches ownership/maintainer comments like `//* Author:`.

## 4. What GitGalaxy explicitly does not track

- `safety`: None (JCL doesn't have traditional code equivalents for these, kept null to prevent crashes).
- `api`: None (JCL doesn't have traditional code equivalents for these, kept null to prevent crashes).
- `concurrency`: None.
- `ui_framework`: None.
- `closures`: None.
- `globals`: None.
- `decorators`: None.
- `generics`: None.
- `comprehensions`: None.
- `scientific`: None.
- `reflection_metaprogramming`: None.
- `telemetry`: None.
- `debug_prints`: None.

## 5. Known limitations (accepted, not fixed)

None identified in the current test suite.

## 6. Test depth

- **Extraction-gauntlet tests**: 41 cases in `tests/extraction/languages/test_jcl.py`
- **Strict-signature tests**: 51 cases in `tests/extraction/languages/test_jcl_strict.py`

## 7. Relevant closed work

- **Epic-level hardening passes vs real bugs**:
  - [#850](https://github.com/squid-protocol/gitgalaxy/issues/850): Extraction hardening: jcl
  - [#590](https://github.com/squid-protocol/gitgalaxy/issues/590): Strict parsing tests: `jcl` structural signatures
- **Cross-language fixes**:
  - [#1975](https://github.com/squid-protocol/gitgalaxy/issues/1975): jcl and m4 (and possibly makefile) have the same Mode B brace-search func_start recall bug as dockerfile/abap/scheme

## 8. Real-world evidence

- [`jcl-assess`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/jcl-assess/jcl-assess_galaxy_llm.md) - A dedicated assessment project demonstrating pure JCL scanning.
- [`cics-genapp`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/cics-genapp/cics-genapp_galaxy_llm.md) - IBM's standard CICS General Insurance Application sample, showcasing JCL operating alongside COBOL in a larger mainframe system.
## 9. Manual verification (No comparison tool)

JCL has no tree-sitter or ctags parser available for the tri-comparison tool, so its precision and recall are verified manually.

The initial manual verification run across the 3 JCL corpus files (`cics-genapp/base/cntl/wsavp01.jcl`, `cpsmde2.jcl`, and `itpentr.jcl`) revealed a bug where JCL was missing from `_CLASS_START_NAMED_EXTRACTION_LANGS`, which caused JCL classes (JOB cards) to fall back to a brace-sliced extraction that failed to parse. After adding JCL to the list, the pipeline perfectly matched the regex matches.

- **Classes (JOB cards)**: 3/3 detected successfully across the 3 corpus files.
- **Functions (EXEC steps)**: 3/3 detected successfully. JCL is appropriately routed to Mode A (greedy-to-next) slicing because it does not use brace-delimited blocks.
- **Args**: 1/1 detected successfully. The one `args` matched is `PARM='NTWRK=GENAPP'` from `//RUNSIM EXEC PGM=ITPENTER,PARM='NTWRK=GENAPP'`. Note that `args` extraction is implemented as a proxy metric because JCL EXEC statements don't take a standard parenthesized parameter list.

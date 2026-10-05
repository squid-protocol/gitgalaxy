---
description: "`python tests/tools/det_survey.py --work DIR` translates every COBOL program of each corpus (not only those with an"
---
# Deterministic translation survey: every program of the six mainframe corpora

`python tests/tools/det_survey.py --work DIR` translates every COBOL program of each corpus (not only those with an
equivalence case) onto the service GitGalaxy generates for it, and compiles each port against the built estate.
**This measures translation, not correctness**: a port is proven only by its equivalence case
(`tests/tools/det_port.py`): 48 programs are proven, 27 from CardDemo, 8 from CBSA and 13 from GenApp
([det_port_design.md](det_port_design.md)).

## Result (2026-10-02, after the Db2, counter and CICS work)

| corpus | programs | translated whole | with holes | refused | statements | translated | compiles |
|---|---|---|---|---|---|---|---|
| aws-mainframe-modernization-carddemo | 44 | 29 | 5 | 10 | 7,231 | 7,200 (99.6%) | 31 |
| cics-banking-sample-application-cbsa | 31 | 11 | 19 | 1 | 6,241 | 6,145 (98.5%) | 22 |
| cics-genapp | 31 | 20 | 10 | 1 | 2,210 | 2,077 (94.0%) | 30 |
| dsf | 7 | 1 | 2 | 4 | 73 | 41 (56.2%) | 3 |
| zecs | 5 | 0 | 4 | 1 | 834 | 768 (92.1%) | 0 |
| zopeneditor-sample | 5 | 2 | 3 | 0 | 635 | 613 (96.5%) | 0 |
| **all** | **123** | **63** | **43** | **17** | **17,224** | **16,844 (97.8%)** | **86** |

*Translated whole*: no statement left as a `Hole`. *With holes*: the port is written, the statements it could not
translate each throw `Hole("line N: why")`. *Refused*: no port at all (below).

### How the number moved

| pass | statements reached | translated | refused programs | ports compiling |
|---|---|---|---|---|
| 1. as built for CardDemo | 7,457 | 96.4% | 65 | 29 |
| 2. source handling | 12,977 | 95.4% | 44 | 62 |
| 3. Db2 / older source forms | 14,981 | 93.3% | 18 | 81 |
| 4. data names, CICS LINK / ASSIGN / TS, UNSTRING (A1-A3) | 16,798 | 96.8% | 18 | 87 |
| 5. Db2 (EXEC SQL onto `DetSql`), GET COUNTER, ASSIGN PROGRAM / INVOKINGPROG, DELAY, ENQ / DEQ, stored-only pointers, SQLDA | 17,224 | 97.8% | 17 | 86 |

The fixes between passes were in reading source, not in translating it:

- a copybook named like the program that COPYs it (`COPY GETCOMPY` in GETCOMPY.cbl) resolved to the program itself;
- `PROCESS` / `CBL` compiler-option lines before the program;
- symbolic maps generated from BMS for estates that do not check them in (`gitgalaxy.core.bms_symbolic`, the layout
  verified byte-for-byte against CardDemo's own);
- `EXEC SQL INCLUDE member` expanded as a COPY (SQLCA in IBM's documented layout), `EXEC SQL DECLARE` and
  obsolete IDENTIFICATION paragraphs (REMARKS, DATE-COMPILED) skipped by the record parser, an empty section header;
- a CICS-only estate (no generated batch package): a standalone DISPLAY / abend runtime.

The percentage falls as more is reached because the newly reachable code is harder (CICS LINK, Db2 programs): it is
the same translator measured on more of each estate.

## What is left

| statements | category | kind |
|---|---|---|
| 123 | other CICS: WEB, DOCUMENT, SEND CONTROL, INQUIRE, SET, BIF DEEDIT, GET / PUT CONTAINER, DELETEQ TS, START, HANDLE AID, ASSIGN STARTCODE ... | not modelled yet |
| 111 | CICS named counters: DEFINE / DELETE / QUERY COUNTER (GET COUNTER is modelled) | not modelled yet |
| 38 | FUNCTION RANDOM | declared: an implementation's own sequence (GnuCOBOL's is not IBM's) |
| 37 | file I/O with no store in the generated project | generator / estate |
| 21 | IMS (EXEC DLI, DIBSTAT) | out of scope: stays a hole |
| 21 | WRITE ... ADVANCING (print files) | declared: no case proves a print file yet |
| 19 | pointers (SET ADDRESS OF, SET to NULL, data after a POINTER in a COMMAREA) | out of scope for byte storage today; a POINTER only stored and passed on is translated |
| 4 | dynamic CALL | judgment |
| 6 | other: ACCEPT FROM SYSIN, CALLs to routines no estate holds (COBDATFT, MVSWAIT, CEEGMT, CEEDATM) | no model |

No EXEC SQL statement is a hole any more: the translator ports embedded SQL onto the runtime's `DetSql`, and 17
equivalence cases prove it against IBM Db2 Community Edition ([det_port_design.md](det_port_design.md#db2-embedded-sql)).

Programs refused (17): 8 COPY members that are not in the corpora (DCLGEN members, MQ's CMQGMOV / CMQODV, LE's
CEEIGZCT, AUTHFRDS), 6 DATA DIVISION and 3 PROCEDURE DIVISION forms the grammar does not take.

## Reading it

- CardDemo, whose programs the translator was built against, translates at 99.6%; CBSA 98.5%, GenApp 94.0%, zECS
  92.1%. What is left is mostly CICS the runtime does not model yet, or out of scope (IMS, pointer arithmetic).
- IMS and pointer code stay holes. Each such statement is named, by line, in the port.
- Outside CardDemo, 21 programs have equivalence cases and all 21 prove (CBSA 8, GenApp 13; 14 of them on Db2).
  The rest of those estates is translated, not proven.
- "Compiles" counts ports compiled with `javac --release 17` against the built estate. This run left two javac
  plugin jars that another project had put in `~/.m2` (Error Prone, SemanticDB) off the classpath: `det_survey.py`
  puts every `~/.m2` jar on it, and javac loads any plugin it finds there.

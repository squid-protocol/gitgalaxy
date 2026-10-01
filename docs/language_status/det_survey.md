# Deterministic translation survey: every program of the six mainframe corpora

`python tests/tools/det_survey.py --work DIR` translates every COBOL program of each corpus (not only those with an
equivalence case) onto the service GitGalaxy generates for it, and compiles each port against the built estate.
**This measures translation, not correctness**: a port is proven only by its equivalence case
(`tests/tools/det_port.py`; on CardDemo, 23 of 23 cases prove).

## Result (2026-10-01)

| corpus | programs | translated whole | with holes | refused | statements | translated | compiles |
|---|---|---|---|---|---|---|---|
| aws-mainframe-modernization-carddemo | 44 | 29 | 5 | 10 | 7,231 | 7,200 (99.6%) | 31 |
| cics-banking-sample-application-cbsa | 31 | 3 | 26 | 2 | 4,007 | 3,495 (87.2%) | 17 |
| cics-genapp | 31 | 0 | 30 | 1 | 2,210 | 1,897 (85.8%) | 30 |
| dsf | 7 | 1 | 2 | 4 | 73 | 41 (56.2%) | 3 |
| zecs | 5 | 0 | 4 | 1 | 825 | 727 (88.1%) | 0 |
| zopeneditor-sample | 5 | 2 | 3 | 0 | 635 | 613 (96.5%) | 0 |
| **all** | **123** | **35** | **70** | **18** | **14,981** | **13,973 (93.3%)** | **81** |

*Translated whole*: no statement left as a `Hole`. *With holes*: the port is written, the statements it could not
translate each throw `Hole("line N: why")`. *Refused*: no port at all (below).

### How the number moved

| pass | statements reached | translated | refused programs | ports compiling |
|---|---|---|---|---|
| 1. as built for CardDemo | 7,457 | 96.4% | 65 | 29 |
| 2. source handling | 12,977 | 95.4% | 44 | 62 |
| 3. Db2 / older source forms | 14,981 | 93.3% | 18 | 81 |

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

Holes by category (statements):

| statements | category | kind |
|---|---|---|
| 288 | a data reference not resolved: an ambiguous unqualified name, a name only a precompiler defines (DFHVALUE, a DCLGEN host variable not in the corpus) | translator gap |
| 169 | EXEC CICS LINK | CICS command not modelled yet |
| 82 | EXEC CICS ASSIGN options beyond APPLID / SYSID (PROGRAM, INVOKINGPROG, ABCODE, RESP ...) | CICS, not modelled yet |
| 37 + 36 | EXEC CICS DEFINE / QUERY (channels and containers, security) | CICS, not modelled yet |
| 37 | a CICS file command naming its file other than by DATASET / FILE | translator gap |
| 13 + 6 + 5 | temporary storage (WRITEQ / DELETEQ / READQ TS) | CICS, not modelled yet |
| 53 | Db2 (EXEC SQL statements) | out of scope: stays a hole |
| 42 | pointers (SET ADDRESS OF, POINTER items) | out of scope for byte storage today |
| 30 | file I/O in an estate with no generated batch package | generator / estate |
| 21 | IMS (EXEC DLI, DIBSTAT) | out of scope: stays a hole |
| 21 | WRITE ... ADVANCING (print files) | translator gap |
| 17 | FUNCTION RANDOM | translator gap (needs GnuCOBOL's generator) |
| 10 | UNSTRING (the runtime has it; the statement parser does not yet) | translator gap |
| ~60 | other CICS: WEB, DOCUMENT, DELAY, START, GET / PUT, SEND CONTROL, HANDLE AID, BIF DEEDIT ... | not modelled yet |

Programs refused (18): 9 COPY members that are not in the corpora (DCLGEN members, MQ's CMQGMOV / CMQODV, LE's
CEEIGZCT, SQLDA, AUTHFRDS), 3 DATA DIVISION and 2 PROCEDURE DIVISION forms the grammar does not take, 1 scope error.

## Reading it

- CardDemo, whose programs the translator was built against, translates at 99.6%; the other estates at 56-97%.
  Most of the difference is CICS the translator does not model yet (LINK above all) and data references it does not
  resolve -- both translator work, not limits of the approach.
- Db2, IMS and pointer code will stay holes: a deterministic port of embedded SQL needs a Db2 target, which is not
  this translator's. Each such statement is named, by line, in the port.
- Nothing here is proven outside CardDemo: the other estates have no equivalence cases yet.

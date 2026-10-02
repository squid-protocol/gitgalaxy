# Deterministic translation survey: every program of the six mainframe corpora

`python tests/tools/det_survey.py --work DIR` translates every COBOL program of each corpus (not only those with an
equivalence case) onto the service GitGalaxy generates for it, and compiles each port against the built estate.
**This measures translation, not correctness**: a port is proven only by its equivalence case
(`tests/tools/det_port.py`): 31 programs are proven, 24 from CardDemo, 5 from GenApp and 2 from CBSA
([det_port_design.md](det_port_design.md)).

## Result (2026-10-02)

| corpus | programs | translated whole | with holes | refused | statements | translated | compiles |
|---|---|---|---|---|---|---|---|
| aws-mainframe-modernization-carddemo | 44 | 29 | 5 | 10 | 7,231 | 7,200 (99.6%) | 31 |
| cics-banking-sample-application-cbsa | 31 | 4 | 25 | 2 | 5,815 | 5,640 (97.0%) | 23 |
| cics-genapp | 31 | 5 | 25 | 1 | 2,210 | 2,003 (90.6%) | 30 |
| dsf | 7 | 1 | 2 | 4 | 73 | 41 (56.2%) | 3 |
| zecs | 5 | 0 | 4 | 1 | 834 | 766 (91.8%) | 0 |
| zopeneditor-sample | 5 | 2 | 3 | 0 | 635 | 613 (96.5%) | 0 |
| **all** | **123** | **41** | **64** | **18** | **16,798** | **16,263 (96.8%)** | **87** |

*Translated whole*: no statement left as a `Hole`. *With holes*: the port is written, the statements it could not
translate each throw `Hole("line N: why")`. *Refused*: no port at all (below).

### How the number moved

| pass | statements reached | translated | refused programs | ports compiling |
|---|---|---|---|---|
| 1. as built for CardDemo | 7,457 | 96.4% | 65 | 29 |
| 2. source handling | 12,977 | 95.4% | 44 | 62 |
| 3. Db2 / older source forms | 14,981 | 93.3% | 18 | 81 |
| 4. data names, CICS LINK / ASSIGN / TS, UNSTRING (A1-A3) | 16,798 | 96.8% | 18 | 87 |

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
| 113 | CICS named counters (DEFINE / GET / DELETE COUNTER) | neither the runtime nor the harness models them yet |
| 75 | pointers (SET ADDRESS OF, POINTER items, NULL) | out of scope for byte storage today |
| 66 | Db2 (EXEC SQL statements) | out of scope: stays a hole |
| 38 | FUNCTION RANDOM | declared: an implementation's own sequence (GnuCOBOL's is not IBM's) |
| 30 | file I/O in an estate with no generated batch package | generator / estate |
| 21 | IMS (EXEC DLI, DIBSTAT) | out of scope: stays a hole |
| 21 | WRITE ... ADVANCING (print files) | declared: no case proves a print file yet |
| ~110 | other CICS: DELAY, WEB, DOCUMENT, SEND CONTROL, INQUIRE, SET, BIF DEEDIT, GET / PUT, DELETEQ TS, START, HANDLE AID ... | not modelled yet |

Programs refused (18): 9 COPY members that are not in the corpora (DCLGEN members, MQ's CMQGMOV / CMQODV, LE's
CEEIGZCT, SQLDA, AUTHFRDS), 6 DATA DIVISION and 2 PROCEDURE DIVISION forms the grammar does not take, 1 scope error.

## Reading it

- CardDemo, whose programs the translator was built against, translates at 99.6%; CBSA 97.0%, GenApp 90.6%, zECS
  91.8%. What is left is mostly out of scope (Db2, IMS, pointers) or CICS the runtime does not model yet.
- Db2, IMS and pointer code will stay holes: a deterministic port of embedded SQL needs a Db2 target, which is not
  this translator's. Each such statement is named, by line, in the port.
- Outside CardDemo, 7 programs have equivalence cases and all 7 prove (GenApp: LGACVS01, LGAPVS01, LGDPVS01,
  LGUCVS01, LGUPVS01; CBSA: UPDCUST, ABNDPROC). The rest of those estates is translated, not proven.

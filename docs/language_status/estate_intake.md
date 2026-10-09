---
description: "Estate-intake checklist (#4709): what to ask a customer for so an estate's compile, runtime, Db2 and CICS options are found rather than assumed, why each matters, and what we assume if it is missing."
---
# Estate intake: what to request from a customer (#4709)

> Part of the readiness-scanner epic (#4721). The [definition of done](definition_of_done.md) (section 3, item 3) says an
> estate is not done while any option is `assumed: IBM default`: the customer confirms each assumed option in writing.
> This page is the request list; `tests/tools/estate_intake.py <corpus>` turns an estate's options file into the
> confirmation list to send.

## How it is used

Every estate has an options file, `tests/equivalence/estate_options/<estate>.json` (resolver:
`gitgalaxy/core/estate_options.py`, #4704). Each value carries a `source`: `<file>:<line>` when the estate's own files
state it, or `assumed: IBM default` / `assumed: owner decision` / `assumed: not stated in the corpus` when they do not.
The [evidence report](evidence_report/README.md) shows each program's options with that provenance (#4708).

```
python tests/tools/estate_intake.py cics-banking-sample-application-cbsa > intake.md
```

The output lists every assumed value (with the section below that says what to send) and every copybook the committed
evidence report says is missing. The customer sends the files, or ticks each value and signs. Precedence of compile
options is IBM's: installation defaults, then the compile step's PARM, then the program's CBL / PROCESS cards.

"If missing" below is what the estate options file records today as the assumption. It is a stated guess, never a
finding about the customer's system.

## 1. Compile JCL, PARMs, CBL / PROCESS conventions

Request: the compile and bind JCL or procedures (every distinct compile step, including CICS-, Db2- and batch-flavoured
ones), any OPTFILE / SYSOPTF member the step reads, and the shop's convention for `CBL` / `PROCESS` cards.

- **Why:** the PARM decides TRUNC, NUMPROC, ARITH, INTDATE, CICS / SQL coprocessor use and more (register C1, C5). A
  program built by a different step has a different PARM.
- **If missing:** the installation defaults of section 2 apply, with no PARM layer. Programs' own `CBL` cards are still read from source.

## 2. Compiler product and version, installation defaults (IGYCDOPT)

Request: the compiler STEPLIB (library names show the release, for example `IGY630` is Enterprise COBOL 6.3), the
product and PTF level, and the **IGYCDOPT** listing (the installation-defaults module) or the compile listing's option summary.

- **Why:** a program with no PARM gets the installation defaults. TRUNC, NUMPROC, ARITH, INTDATE, CODEPAGE, ZONEDATA, DISPSIGN, NSYMBOL, SSRANGE
  and OPTIMIZE change arithmetic and data results (register C1-C5, C10, C11); the version bounds which options exist.
- **If missing:** `assumed: IBM default` - IBM's shipped defaults for the stated version (for example TRUNC(STD), NUMPROC(NOPFD), ARITH(COMPAT), INTDATE(ANSI), CODEPAGE 1140).

## 3. Language Environment runtime options

Request: the CEEOPTS (SYSIN / DD) members, CEEUOPT (user-linked options), CEEDOPT (installation defaults) and CEEROPT
(CICS region options) in force, and any `RPTOPTS(ON)` output from a real run.

- **Why:** STORAGE decides what WORKING-STORAGE without VALUE holds (register L3); TRAP and ABTERMENC decide how an abend ends.
- **If missing:** `assumed: IBM default`: for example STORAGE(NONE,NONE,NONE,0K), TRAP(ON,SPIE), ABTERMENC(ABEND). No burned corpus supplied a CEEOPTS.

## 4. Db2 precompile and bind

Request: the precompile / coprocessor options and the **BIND PACKAGE / PLAN** cards, plus the installation's
**DSNHDECP** (application programming defaults): DATE and TIME formats, DEC (15 / 31) and DECPT, the application
encoding scheme and CCSIDs (SQLCCSID), and ISOLATION, CURRENTDATA, ACTION.

- **Why:** date and time text format (register Q6), decimal precision and point, and the CCSID of character columns (Q7) change values the program sees; ISOLATION is recorded with the estate, but Db2 for Linux runs the SQL in the oracle (Q1).
- **If missing:** `assumed: IBM default`: DATE ISO, TIME ISO, DEC 15, DECPT `.`, SQLCCSID NO. No burned corpus supplied a DSNHDECP.

## 5. CICS region

Request, **SIT**: the SIT overrides (SYSIN / DFHSIT) - LOCALCCSID, DB2CONN, and the region's code page. **CSD**: the
program definitions (CONCURRENCY, EXECKEY), TYPETERM definitions (UCTRAN), URIMAP definitions, named-counter
pool definitions, and TS queue definitions (recoverability, location).

- **Why:** LOCALCCSID is the region's EBCDIC page for DEEDIT, containers and terminal data (register X17, X26); UCTRAN decides terminal upper-casing (X26); named counters (X9, X30) and TS queues (X6, X29) are modelled from the definitions the case states. URIMAP serves the `EXEC CICS WEB` family, which is not modelled today (#4767).
- **If missing:** `assumed: IBM default`: LOCALCCSID 037, and what the case states for terminal and counter facts; anything IBM leaves open is refused by name, not guessed.

## 6. BMS sources

Request: the BMS map source (DFHMSD / DFHMDF) for every mapset, and the generated symbolic-map copybooks if they are stored separately.

- **Why:** screens are compared as the symbolic map (register X2, X31); a map the mapset does not hold is refused.
- **If missing:** the symbolic map copybook is used if present; otherwise the program using it is refused with the missing copybook named.

## 7. Copybook libraries

Request: every COPY library on the compile's SYSLIB concatenation, **including vendor members**: IBM MQ (`CMQ*`), Language Environment (`CEE*`, for example CEEIGZCT), CICS (`DFH*`), Db2 (SQLCA), and any third-party product copybooks.

- **Why:** a program whose COPY member is not in the estate cannot be translated: it is refused whole (definition of done, section 2) and stays at L0.
- **If missing:** refused by name, listed per program in the confirmation list; no member is invented.

## 8. Data samples and test inputs

Request: representative input files (with copybooks and RECFM / LRECL), Db2 table DDL and sample rows, terminal
transcripts or screen inputs, and expected outputs from a real run where they exist.

- **Why:** scenarios drive the levels L2-L4; real data shows which paths run in production (the report's coverage bars). Data with non-digits in numeric fields or odd signs decides register C11 / D3 cases.
- **If missing:** scenarios are authored from the source; the levels say so ("scenarios authored", not "production-representative").

## 9. z/OS calibration permission

Request: written permission, and a contact, to run a small calibration set of programs on the customer's z/OS (or an IBM Z development system) and send back outputs.

- **Why:** the oracle is GnuCOBOL, not z/OS (register, and definition of done section 4); a z/OS run is the only way a DIFFERS or ASSUMED entry becomes MATCHED for this estate.
- **If missing:** no calibration; every ASSUMED / DIFFERS entry stays disclosed, and no claim is made about z/OS.

## What the burned corpora lacked (slice 1 of #4704)

No CEEOPTS anywhere, no IGYCDOPT, no DSNHDECP. The blind fourth estate gets the same assumptions unless the customer supplies these.

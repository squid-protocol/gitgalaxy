---
description: "A proof here says one thing: **on these scenarios, the Java port gave the same outputs as the COBOL program run by"
---
# The oracle and its assumptions: where our COBOL side may differ from IBM z/OS

A proof here says one thing: **on these scenarios, the Java port gave the same outputs as the COBOL program run by
our oracle.** The oracle is GnuCOBOL 3.1.2 (`cobc -std=ibm -fsign=EBCDIC`), plus our own models of what GnuCOBOL
lacks: CICS (`tests/equivalence/cics/ggcics.c`), Db2's precompiler (`tests/tools/equivalence_sql.py`, over a real
Db2), Language Environment services (`tests/equivalence/le/`) and IBM's DISPLAY text (`tests/equivalence/faults/ggdisplay.c`).

So every claim rests on three links:

1. **IBM z/OS ≈ our oracle.** This document.
2. **Our oracle = the Java port**, on the scenarios run. The proofs.
3. **The scenarios exercise the program.** The coverage figures quoted with every proof.

Link 1 is the only one that no run of ours checks. This page lists every place we know or suspect it does not
hold, so that a claim can be quoted with its limits. A run on real z/OS would settle most entries; until then each
one is either made to match IBM's documentation, refused by name, or written down here.

## The oracle is pinned and recorded (#4309)

`tests/equivalence/gnucobol.Dockerfile` pins the oracle, so every proof names the same GnuCOBOL:

| pinned | value |
|---|---|
| base image | `debian:bookworm-slim@sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251` |
| `gnucobol3` / `libcob4` (Debian package) | `3.1.2-5+b1` |
| `cobc --version` | `cobc (GnuCOBOL) 3.1.2.0` (the build fails if the installed compiler prints anything else) |

The image carries the three values as labels (`org.gitgalaxy.oracle.*`). `tests/tools/equivalence_oracle.py` reads
the image a run uses -- its id, labels, `cobc --version` and the installed package -- and compares it with the pin.
Every proof report (`equivalence.py run`, the CALL and CICS harnesses, `cics_crucible.py` results and
`--report-dir` proofs) records that fingerprint under `oracle`, with `matches_pin` and any `mismatches`. A
mismatch (an image built before the pin, a `--build-arg` override) is a warning locally and stops the run under
`GITGALAXY_ORACLE_STRICT=1`, which the CICS crucible workflow sets. `gnucobol-db2.Dockerfile` builds `FROM` the
oracle image, so a Db2 case's image inherits the pin and its labels; it is built once and kept, so after the oracle
moves, `docker rmi gitgalaxy-gnucobol-db2:3` before the next Db2 run.

Moving the oracle is a deliberate change: bump the three `ARG`s together, rebuild, and re-prove (a changed oracle
makes every proof's evidence stale). If Debian drops the pinned package from `deb.debian.org` at a point release,
the pinned build fails (the weekly CICS crucible run notices); restore it from `snapshot.debian.org` rather than
taking whatever version is current.

## Status key

| status | meaning |
|---|---|
| **MATCHED** | The oracle is made to behave as IBM documents it (a flag, a model or a shim), and a test pins it. |
| **REFUSED** | IBM's behaviour is not settled by its documentation, so the harness stops by name ("not modelled") and no proof rests on a guess. |
| **DIFFERS** | A known difference between the oracle and z/OS. The entry says whether any proven program reaches it. |
| **ASSUMED** | Believed to match, and not measured on z/OS. |

"Reached" means a proven program's scenarios execute the behaviour. An unreached difference cannot have changed a
verdict, but it limits what the proof says about inputs outside the scenarios.

## Summary

| id | area | entry | status | reached by a proof? |
|---|---|---|---|---|
| C1 | compiler | Binary truncation: `TRUNC(STD)` (IBM's default) on both sides (#4102, fixed) | MATCHED | reachable (GenApp LGICDB01) |
| C2 | compiler | Arithmetic intermediates: the oracle truncates them (ARITHMETIC-OSVS), the det runtime the same way (#4287); where GnuCOBOL departs from IBM's decimal places | MATCHED (det runtime = oracle) / DIFFERS (oracle, GnuCOBOL's departures) | yes (INTCALC, POSTTRAN …); a departure: not known to be |
| C3 | compiler | An integer literal truncated to zero keeps no sign | DIFFERS | no |
| C4 | compiler | An unsigned binary taken below zero by ADD/SUBTRACT wraps | DIFFERS | no |
| C5 | compiler | `NUMPROC(MIG)` as Enterprise COBOL 5+ compiles it (NOPFD), `NUMPROC(PFD)` with preferred signs (#4271); `INTDATE(LILIAN)`, `ARITH(EXTEND)`, `TRUNC(OPT)` | MATCHED (NUMPROC) / REFUSED (the rest) | NUMPROC: no |
| C6 | compiler | COMP-1 / COMP-2: IBM hexadecimal floating point, and float-mode evaluation of the whole expression | MODELLED in the det runtime (HFP, #4271 slice 1); the oracle DIFFERS (IEEE, decimal evaluation): proven by IBM-cited vectors and on exact values; what the oracle cannot decide REFUSED by name | no (DBB EPSMPMT: its float `**` is a hole) |
| C7 | compiler | COMP-5 byte order: little-endian vs z/OS big-endian | DIFFERS | read as numbers only (a VALUE beyond the PICTURE: fixed, #4501) |
| C8 | compiler | DISPLAY of signed zoned, binary and packed items | MATCHED | yes |
| C9 | compiler | POINTER is 8 bytes in GnuCOBOL (x86-64), 4 on z/OS | DIFFERS | only NULL, trailing (CBSA) |
| C10 | compiler | INITIALIZE / VALUE ZERO zoned items: unsigned F zone (GnuCOBOL) vs preferred C sign (z/OS) | DIFFERS (tolerated where a case declares it) | yes (CardDemo READACCT ARRYFILE) |
| C11 | compiler | MOVE of an alphanumeric item holding a non-digit to a numeric DISPLAY item (#4049) | DIFFERS (inputs kept out of the cases) | yes (COMEN01C option `1!`) |
| C12 | compiler | FUNCTION RANDOM: the oracle's generator (glibc via GnuCOBOL), not IBM's unpublished one; a seed IBM does not allow refused | DIFFERS (the numbers) / ASSUMED (the interface) | translated, no proof yet (CBSA CRDTAGY1-5, INQCUST; GenApp LGICVS01) |
| C14 | compiler | Size errors without ON SIZE ERROR: a zero divisor leaves the receivers unchanged in the oracle (libcob's NaN), the det runtime the same (#4655); z/OS's result is undefined (a decimal-divide exception); 0 ** a negative is 0 in the oracle, a size error on z/OS | MATCHED (det runtime = oracle) / DIFFERS (oracle vs z/OS) | not known to be: no proven scenario divides by zero |
| D1 | data | Text order is ASCII (Latin-1), not EBCDIC | DIFFERS | keys: no; comparisons: not audited |
| D2 | data | Hex literals that name EBCDIC characters (`X'40'`) | DIFFERS | no |
| D3 | data | Zoned signs in ASCII data (`{`, `}`, A–R overpunch) | MATCHED | yes |
| D4 | data | An alphanumeric literal holding a character no single-byte code page holds (a UTF-8 em dash): the statement is a hole by name, the program translates; in a VALUE, a national / DBCS literal or a name the program stays refused (#4272) | REFUSED (the statement) | no |
| F1 | files | Natural FILE STATUS values come from GnuCOBOL's BDB files | ASSUMED | yes (00, 10, 23, 22) |
| F2 | files | Fault FILE STATUS values are injected on both sides | MATCHED | yes |
| F3 | files | RECFM=VB: records compared by content, framed as GnuCOBOL frames them, not as a z/OS RDW | ASSUMED | yes (CardDemo READACCT VBRCFILE) |
| F4 | files | JCL utility steps (SORT, IDCAMS, IEBGENER) are not run; the COBOL SORT / MERGE verbs are translated (#4268) | REFUSED (utility steps) | — |
| X1 | CICS | Commands, RESP/RESP2 and EIB from IBM's API reference | ASSUMED | yes |
| X2 | CICS | Screens compared as the symbolic map, not the 3270 stream | ASSUMED | yes |
| X3 | CICS | Backout: recoverable files and Db2 undone, RECOVERY(NONE) files kept | MATCHED | yes (CBSA INQACC) |
| X4 | CICS | A task takes no time (ASKTIME = dispatch time) | ASSUMED | yes |
| X5 | CICS | Options and conditions IBM leaves open are refused | REFUSED | — |
| X6 | CICS | WRITEQ with a LENGTH past its FROM item (GenApp LGSTSQ): the task is judged up to the refused WRITEQ (owner decision on #4607); not settled on z/OS (#4050) | REFUSED (the WRITEQ) / judged up to it | yes (GenApp LGACDB01, LGACDB02, LGDPDB01, LGIPDB01, LGUCDB01 error paths) |
| X7 | CICS | ASSIGN INVOKINGPROG / PROGRAM; LINKed programs run in one task | MATCHED | yes (GenApp LGUPDB01) |
| X8 | compiler | A reference modification past its item (no SSRANGE): a storage overlay | not run | no |
| X9 | CICS | Named counters (GET COUNTER) | MATCHED | yes (GenApp LGACDB01) |
| X10 | CICS | A LINK target's COMMAREA bytes past the end of the caller's record | DIFFERS | no |
| X11 | CICS | ASKTIME ABSTIME into a field narrower than S9(15) COMP-3 (GenApp's WS-ABSTIME) | DIFFERS | yes (GenApp error paths, #4173) |
| X12 | CICS | A task with no COMMAREA that MOVEs DFHCOMMAREA anyway | UNDEFINED, masked | yes (DBB EPSCMORT) |
| X13 | CICS | An ESDS browsed by RBA: fixed-length records, a record's RBA its byte offset; RBAs that address no record refused | ASSUMED (REFUSED where IBM is silent) | yes (DBB EPSMLIST) |
| X14 | CICS | READ ... INTO LENGTH: in-out, truncation and LENGERR; a VSAM file's LENGTH need not equal its record length; LENGERR on READ UPDATE refused | ASSUMED (REFUSED where IBM is silent) | yes, NORMAL only (GenApp LGUCVS01 / LGUPVS01) |
| X15 | CICS | Terminal RECEIVE (INTO / SET, LENGTH, MAXLENGTH, NOTRUNCATE; LENGERR, EOC on an LUTYPE2 terminal) and SEND CONTROL | ASSUMED (REFUSED where IBM is silent) | yes (cics-crucible hc-terminal-receive, hc-terminal-eoc) |
| X16 | CICS | HANDLE AID, IGNORE CONDITION, PUSH / POP HANDLE and HANDLE CONDITION ERROR on the det port | MATCHED (REFUSED where IBM is silent) | yes (cics-crucible hc-handle-aid, hc-ignore-error, hc-eoc-error) |
| X17 | CICS | Channels and containers: PUT / GET / DELETE CONTAINER, LINK / XCTL CHANNEL, ASSIGN CHANNEL; bytes never converted; CCSID options, SET, BYTEOFFSET, RETURN CHANNEL, MOVE and browse refused | ASSUMED (REFUSED where IBM is silent) | yes (cics-crucible ca-channel-containers, unreleased) |
| X18 | CICS | Interval control on the det port: START (INTERVAL / TIME / AFTER / AT, TERMID, REQID, PROTECT, FROM, RTRANSID / RTERMID / QUEUE), RETRIEVE (INTO / LENGTH, the data options, ENVDEFERR), CANCEL REQID, RUN TRANSID CHILD; TIME RESP2 and the order of out-of-range checks assumed; FETCH, RUN / START CHANNEL, RETRIEVE SET / WAIT refused | ASSUMED (REFUSED where IBM is silent) | yes (cics-crucible gt-start-retrieve, gt-terminal-coalesce, gt-start-options, unreleased) |
| X19 | CICS | ASSIGN on the det port: STARTCODE (TD / S / SD), USERID (the default user), FACILITY / SCRNHT / SCRNWD (INVREQ RESP2 5 without a terminal) from facts the harness states; no data area written when ASSIGN raises INVREQ; OPID, NETNAME, TERMCODE, FCI, the other screen sizes, work-area lengths and the rest refused | ASSUMED (REFUSED where the harness cannot decide) | yes (cics-crucible gt-assign-startcode, unreleased) |
| X20 | CICS | SEND TEXT on the det port and the stub: TERMINAL accepted as the default output disposition (the principal facility; the event is that of SEND TEXT without it); ACCUM, PAGING, SET, REQID, HEADER, TRAILER, JUSTIFY / JUSFIRST / JUSLAST, the printer, partition and LDC options, MSR, FMHPARM, DEFAULT / ALTERNATE refused | MATCHED (REFUSED where the region cannot decide) | yes (cics-crucible gt-send-text-terminal, unreleased) |
| X21 | CICS | EIBTASKN: the task's number is a stated fact of the run (`$GGCICS_TASKN` / `CicsTask.withTaskNumber`, a case's or scenario's `"taskn"`, default 0), not the number CICS assigns; a value outside 0 to 9,999,999 refused | DIFFERS (the value) / MATCHED (both sides) | yes (every CICS task; read by CBSA's Db2 programs, GenApp LGICDB01) |
| X22 | CICS | READ GTEQ / GENERIC on a KSDS: the first record whose key (or its first KEYLENGTH bytes) equals RIDFLD's or, with GTEQ, is greater, in the browse's key order (D1); NOTFND RESP2 80; READ UPDATE holds the record found; RIDFLD not updated; a GENERIC KEYLENGTH not shorter than the key or not above zero, a non-constant KEYLENGTH and a RIDFLD shorter than the key searched refused | ASSUMED (REFUSED where IBM is silent or the layout decides) | yes (GenApp LGICVS01 genapp-lgicvs01) |
| X23 | CICS | A COMMAREA of a stated length (a scenario's `commarea_length`, EIBCALEN shorter than the record): the program is given exactly those bytes; a reference past EIBCALEN refused on both sides, the task judged up to it | ASSUMED (REFUSED past EIBCALEN) | yes (GenApp LGACDB01, LGACDB02, LGDPDB01, LGIPDB01) |
| X24 | CICS | A task started with a channel (a scenario's `channel`: what a RUN TRANSID CHANNEL parent or a LINK CHANNEL caller passed), made its first program's current channel; the containers left on that channel compared at the task's end (dropped on an abend), byte for byte; RUN TRANSID children not run | ASSUMED | yes (async credit-card CRDTCHK, CSSTATS2, CSSTATUS, GETADDR, GETNAME) |
| X25 | COBOL layout | SYNCHRONIZED slack bytes in the layout model (GalaxyIR `record_layout`, `_storage_spans`): IBM Enterprise COBOL boundaries (halfword up to 4 digits, fullword above, the 8-byte binary S9(10)-S9(18) included; COMP-1 / INDEX / pointers fullword; COMP-2 doubleword) counted from the record, the table slack of IBM's rule; GnuCOBOL / Micro Focus may align an 8-byte binary on a doubleword | ASSUMED (IBM's fullword; z/OS is the target) | no (no committed case reaches an 8-byte SYNC binary) |
| L1 | LE | CEEDAYS: documented pictures only | MATCHED / REFUSED | yes |
| L2 | LE | CEE3ABD abend codes | MATCHED | yes |
| L3 | LE | WORKING-STORAGE with no VALUE clause: GnuCOBOL's spaces vs LE's STORAGE option on z/OS | ASSUMED | yes (CardDemo READACCT OUTFILE, 2 bytes) |
| A1 | assembler | CardDemo's COBDATFT, translated instruction for instruction; load-module-dependent paths refused | MATCHED / REFUSED | yes (CardDemo READACCT) |
| Q1 | Db2 | Db2 for Linux runs the SQL, not Db2 for z/OS | ASSUMED | yes |
| Q2 | Db2 | EXEC SQL keeps RETURN-CODE | ASSUMED | yes |
| Q3 | Db2 | The Java side's unit of work: one per CICS task; batch commits each statement | MATCHED (CICS) / DIFFERS (batch) | CICS: yes (CBSA XFRFUN); batch: no |
| Q4 | Db2 | WHENEVER, dynamic SQL, CONNECT, CALL, SCROLL cursors, host-variable arrays | REFUSED | — |
| Q5 | Db2 | DSNTIAC / DSNTIAR message formatting | REFUSED | no |
| Q6 | Db2 | Date and time text in ISO form; DDL adapted from z/OS jobs | ASSUMED | yes (CBSA, GenApp) |
| Q7 | Db2 | `CCSID EBCDIC` tables hold Unicode text: string order differs | DIFFERS | no |
| Q8 | Db2 | Positioned UPDATE / DELETE: the Java side by row id | MATCHED | yes (GenApp LGUPDB01) |
| Q9 | Db2 | More host variables than columns: SQLWARN3, the rest untouched | MATCHED | yes (GenApp LGUPDB01) |
| J1 | Java | VSAM files on H2, not the target database | ASSUMED | — |
| M1 | method | The scenarios are ours, not production traffic | — | — |
| M2 | method | SQL faults: injected on both sides at a statement (#4173), the SQLCA as the stub sets it | MATCHED (ASSUMED SQLCA) | yes (17 Db2 cases) |
| M3 | method | A LINKed program's COMMAREA result was not compared before 2026-10-02 | fixed | 7 cases re-proven |
| M4 | method | Clock fields: a value the run takes from the system clock | declared | yes (GenApp LGUPDB01) |

## Compiler: GnuCOBOL 3.1.2 `-std=ibm` vs IBM Enterprise COBOL

### C1. Binary truncation — MATCHED (fixed 2026-10-02, #4102)
- **What.** Under `TRUNC(STD)`, IBM's default, a binary item (COMP, COMP-4, BINARY) holds only its PICTURE's digits:
  `MOVE 99999` to `PIC S9(4) COMP` stores 9999, and `ADD 1` to 9999 raises ON SIZE ERROR. COMP-5 keeps its bytes.
- **Was.** `cobc -std=ibm` alone behaves as `TRUNC(BIN)`, and the harness passed no flag for STD; the det runtime ran
  BIN too. Both sides agreed, both differed from IBM.
- **Now.** The harness applies IBM's defaults for options nothing names: STD is GnuCOBOL's `-fbinary-truncate` (measured:
  +09999, SIZE ERROR, +02345). The det port sets each entry's TRUNC from the program's CBL / PROCESS cards, else the
  case's `compiler_options`, else STD, and restores the caller's on exit. Every det and model port was re-proven under
  it; nothing moved (no proven scenario puts more digits in a binary item than its PICTURE).
- **Reach.** GenApp's LGICDB01 moves the 10-digit CA-CUSTOMER-NUM into an `S9(9) COMP`: a customer number of 10 digits
  would now behave as on z/OS.

### C2. Arithmetic intermediates — the det runtime MATCHES the oracle (#4287); the oracle DIFFERS where GnuCOBOL departs from IBM
- **IBM's rule.** Enterprise COBOL keeps each intermediate result to a number of decimal places (6.4 Programming
  Guide, SC27-8714-03, Appendix A, "Fixed-point data and intermediate results"): `+ -` the larger of d1, d2; `*`
  d1 + d2; `/` the larger of the operands' difference and dmax, the most decimal places of any operand or receiver;
  at most 30 digits under `ARITH(COMPAT)`.
- **The oracle.** `cobc -std=ibm` turns on GnuCOBOL's `arithmetic-osvs` (`ibm-strict.conf`), so cobc truncates
  intermediates (`cob_decimal_align`) with decimal places it works out at compile time from those rules. The
  reproducer of #4287 is IBM's own: `COMPUTE R = A / B * C` with A = 1, B = 3, C = 300 and R `PIC 999V99` gives
  099.00 (A / B kept to 2 places). The 30-digit limit GnuCOBOL does not apply: ASSUMED that no proven intermediate
  is that long.
- **The det runtime (since #4287)** makes the same truncations: the translator replays cobc's decision
  (`det/osvs.py`, from GnuCOBOL 3.1.2's `cobc/typeck.c` and `cobc/tree.c`) and emits `Cobol.align(value, places)`
  where cobc emits `cob_decimal_align`; a literal on the right of an operation is libcob's decimal constant
  (`Cobol.Dc`); `Cobol.divide` keeps cob_decimal_div's 38 + max(d1 - d2, 0) places and `Cobol.power`
  cob_decimal_pow's trimming. COMPUTE, ADD / SUBTRACT / MULTIPLY / DIVIDE with an expression, and the relations of
  IF, PERFORM UNTIL, SEARCH WHEN and EVALUATE are planned; floating-point statements keep their HFP model (C6).
  Proven by `tests/cobol_mainframe/test_det_osvs.py` and by a randomized differential run (2026-10-07: over 100
  random programs, about 25,000 COMPUTE, ADD, SUBTRACT, IF and EVALUATE statements over zoned, packed and binary
  items, every output equal to the oracle's; on the earlier runtime about one line in six differed).
- **Where GnuCOBOL departs from IBM's rule** (each measured on the oracle; the det port does what the oracle does,
  so a proof cannot see them, and z/OS may not do them):
  - the stack of decimal places pairs an operation with its own operands only when every operand pushes its
    places; a binary item of scale 0, a short integer literal, ZERO and a literal on the right push nothing, and the
    operation then takes dmax or a neighbour's places: `COMPUTE R = XB + YB + Z` with two `PIC 9(4) COMP` items and
    R `PIC 999V99` aligns XB + YB to 2 places;
  - `cob_decimal_align` with fewer places than the target shifts the wrong way: the value loses as many low-order
    digits (579 aligned to 2 places is 500, so that COMPUTE gives 501.00 for 123 + 456 + 1; `- A + B` aligns 0 - A
    and loses A);
  - a literal's decimal constant takes the places of every intermediate it is added to or subtracted from, for the
    rest of the run, and an exponent literal loses its trailing zeros;
  - an EVALUATE leaves its dmax and stack to the next statements of the same sentence (a period, a COMPUTE or an IF
    resets them), and an IF's folded literal pair keeps it from walking its condition;
  - a relation of two literals with decimals compares wrongly (`100 > 1.25` is false), a separate GnuCOBOL matter:
    no case compares two literals.
- **Not replayed by the det translator** (refused by name, or exact as before): a negative literal exponent (libcob
  overwrites the constant: refused); an arithmetic expression in a PERFORM VARYING FROM / BY, a SEARCH ALL key or a
  subscript (cobc computes those otherwise); an EVALUATE whose last WHEN ends with a statement that leaves the state
  dirty (refused); statements inside ON SIZE ERROR phrases, which cobc parses before their statement's expression (their
  size-error semantics are C14's).
- **Reached.** Every COMPUTE with more than one operation, among them INTCALC's interest computation. Across the
  det sweep's ports (2026-10-07) the only truncation emitted is POSTTRAN's `ACCT-CURR-CYC-CREDIT -
  ACCT-CURR-CYC-DEBIT` to 2 places, a value of 2 places (no change); none of GnuCOBOL's departures is reached.
- **To settle.** A table of division, multiply-then-divide and binary-sum cases on z/OS against
  `tests/equivalence/rounding/RND.cbl` (and the departures above).

### C3. An integer literal truncated to zero — DIFFERS
- **What.** GnuCOBOL folds `MOVE -1000 TO PIC S9(3)` at compile time to +0 (`00{`). Every other truncating MOVE keeps
  the sign (`00}`). The translator matches GnuCOBOL (`gen.literal_moved`).
- **IBM's behaviour** is not measured. No proven program reaches it.

### C4. An unsigned binary below zero — DIFFERS
- **What.** GnuCOBOL wraps `PIC 9(4) COMP`, so 0 − 3 by SUBTRACT is 65533. Its own COMPUTE and MOVE, IBM's
  compilers and the det runtime store the absolute value, 3.
- **Reached.** No case reaches it. `test_det_programs.py` keeps its unsigned item above zero.

### C5. Compiler options: NUMPROC MATCHED where IBM pins it (#4271); INTDATE(LILIAN), ARITH(EXTEND), TRUNC(OPT) REFUSED
- **NUMPROC(MIG): MATCHED for Enterprise COBOL 5 and later.** "Enterprise COBOL 5 and 6 does not support the
  NUMPROC(MIG) option. If NUMPROC(MIG) is specified, Enterprise COBOL 5 or 6 issues a warning message and the
  compilation will get the default setting for NUMPROC. This is either the user-customized default or the IBM default,
  which is NUMPROC(NOPFD)" (Enterprise COBOL for z/OS 6.4 Migration Guide, GC27-8715-03, Table 18; the same in the 5.2
  Migration Guide, GC14-7383-03). A case states the compiler its estate builds with (`"compiler": {"product":
  "Enterprise COBOL", "version": "6.1", "evidence": ...}`); MIG then compiles as NOPFD on both sides
  (`equivalence_common.numproc_mig`; the det translator's `program.numproc_pfd`). The installation default is ASSUMED
  to be IBM's. **Refused:** MIG for a case that states no compiler or one before version 5, whose MIG was OS/VS
  COBOL's sign processing, documented only as "similar to" it.
  - IBM DBB MortgageApplication's EPSMPMT and EPSCSMRT carry `CBL NUMPROC(MIG)`, and the estate's build JCL
    (`Migration/jclToZBuilder/samples/BLDMORT.jcl`) compiles them with `IGY.V6R1M0.SIGYCOMP`, Enterprise COBOL 6.1.
    `mortgage-mpmt` states it. Its proof still waits on C6, not on NUMPROC.
- **NUMPROC(PFD): MATCHED with preferred signs, REFUSED otherwise.** Under PFD "the compiler assumes that the sign in
  your data is one of three preferred signs": C signed positive or zero, D signed negative, F unsigned; "the compiler
  uses whatever sign it is given to process data. The preferred sign is generated only where necessary". NOPFD
  "accepts any valid sign configuration. The preferred sign is always generated in the receiver" (6.4 Programming
  Guide, SC27-8714-03, "Sign representation of zoned and packed-decimal data"). With preferred signs in every value
  read, the two compute the same, so:
  - the oracle compiles PFD as GnuCOBOL's own sign processing (no flag);
  - each det entry point runs with its program's NUMPROC (`Cobol.swapNumprocPfd`, the caller's restored, as TRUNC);
    under PFD the runtime reads a zoned or packed value only with a preferred sign and stops by name ("NUMPROC(PFD):
    ... non-preferred sign ... is not modelled") on any other: F in a signed item, C or D in an unsigned one, D on
    zero. The class test of a signed item with an F sign stops too: Table 7 (NUMCLS(PRIM)) takes C, D, F under NOPFD
    and C, D, "+0" under PFD;
  - a PFD program is proven only through a det port (`equivalence_common.numproc_guard`): a model port or the
    generated service has no such guard and is refused.
  - GnuCOBOL leaves an F sign in a signed item after VALUE ZERO and INITIALIZE (C10) where z/OS writes C, so a PFD
    program that reads one is refused, never misjudged.
  - **Reached.** No case compiles with PFD. Pinned by `tests/cobol_mainframe/test_numproc.py`.
- **REFUSED:** `INTDATE(LILIAN)`, `ARITH(EXTEND)` and `TRUNC(OPT)`, from a CBL/PROCESS card or a case's
  `compiler_options`, stop the run (`UnsupportedOption`).
  - `TRUNC(OPT)` is undefined for out-of-range values by IBM's own description, so no oracle could be faithful to it.
    CBSA's build JCL passes `TRUNC(OPT)`, but its programs' PROCESS cards override it with `TRUNC(STD)` (C1).
  - `ARITH(EXTEND)` changes only intermediates past 30 digits (31 instead) and float-mode precision (extended instead
    of long). GnuCOBOL caps neither (C2), so the oracle would compute COMPAT and EXTEND the same; a model needs a
    guard on both sides that stops an intermediate past 30 digits.
  - `INTDATE(LILIAN)` is pinned by IBM (day 1 is 15 October 1582 instead of 1 January 1601), and could be modelled
    by the documented offset of the integer-date functions. Dates before 1601 cannot run on GnuCOBOL and would be
    refused. No case needs it yet.

### C6. Floating point — MODELLED in the det runtime as HFP (#4271 slice 1); the oracle DIFFERS
- **What z/OS does.** COMP-1 and COMP-2 are IBM hexadecimal floating point (HFP): a sign bit, a 7-bit characteristic
  (the exponent of 16, excess 64) and 6 (COMP-1) or 14 (COMP-2) hexadecimal fraction digits, big-endian: between 21
  and 24 bits of precision for a short item against IEEE single's 24 (z/Architecture Principles of Operation,
  SA22-7832, "Hexadecimal-Floating-Point Number Representation"). "If any operation in an arithmetic expression is
  computed in floating-point arithmetic, the entire expression is computed as if all operands were converted to
  floating point", when "a receiver or operand is COMP-1, COMP-2, external floating point, or a floating-point
  literal" or "an exponent contains decimal places". Under ARITH(COMPAT) "single precision is used if all receivers
  and operands are COMP-1 data items and the expression contains no multiplication or exponentiation operations",
  long otherwise; a comparison is floating point "if either comparand is a floating-point value" (6.4 Programming
  Guide, SC27-8714-03, Appendix A, "Floating-point data and intermediate results"; "Fixed-point contrasted with
  floating-point arithmetic").
- **What the oracle does.** GnuCOBOL stores IEEE binary floats in machine (little-endian) order. It evaluates the
  expression in decimal: each float is read exactly (`cob_decimal_set_double`), each intermediate is truncated by
  ARITHMETIC-OSVS as fixed point (C2), and the result is stored through a truncation to double and a rounding to
  float. It truncates a float MOVEd to a fixed-point item (0.1 COMP-2 to `V9(4)` is 0.0999; IBM rounds: 0.1000).
  Measured on GnuCOBOL 3.1.2 (2026-10-06): `COMPUTE L2 = (L1 - N3) / N4` gives 0, `COMPUTE L2 = L1 / N4 + S1 * 2`
  drops the second term, and `IF S1 + 1 > 2` is false for S1 = 6.25 -- a float expression with a multiplication,
  a parenthesised division or in a comparison is not decided by the oracle at all.
- **The det runtime (since #4271 slice 1)** models HFP: `cobolrt/Hfp.java`, the translator's own model
  `det/hfp.py`.
  - Storage: `Field.hfp`, the bytes as z/OS holds them; a VALUE is encoded at translation (`layout._put_value`).
  - Arithmetic (`Hfp.add / subtract / multiply / divide`): ADD / SUBTRACT NORMALIZED with one hexadecimal guard
    digit, then normalized and truncated; MULTIPLY and DIVIDE truncate the exact result (Principles of Operation,
    "Hexadecimal-Floating-Point Instructions"). The translator picks each statement's mode by IBM's rule: fixed point,
    short (all COMP-1, no multiplication) or long, every operand converted.
  - Conversions: a COMP-2 to a COMP-1 is rounded (LOAD ROUNDED: IBM, "if a USAGE COMP-2 data item is moved to a
    USAGE COMP-1 data item, rounding occurs"); a float to a fixed-point or numeric-edited item is rounded in the
    receiver's low-order position, with at most 9 (COMP-1) or 18 (COMP-2) significant digits (6.4 Programming
    Guide, "Conversions and precision"). Comparisons are long, unless both comparands are COMP-1.
  - DISPLAY: "A COMP-1 item will display as if it had an external floating-point PICTURE clause of -.9(8)E-99"
    (COMP-2: -.9(17)E-99; 6.4 Language Reference, DISPLAY statement): ` .12500000E 02`.
  - **ASSUMED** (IBM does not document them): a fixed-point value converted to float is truncated to long (then
    rounded to short for a COMP-1); the mantissa of DISPLAY is rounded half away from zero; an arithmetic statement
    that stores a float result in a fixed-point receiver truncates unless ROUNDED (the COBOL rule), and a statement
    with several receivers is one mode for all of them.
- **How it is proven** (the oracle cannot run HFP):
  - the byte layout and the arithmetic by hand-computed vectors from IBM's examples (1.0 = `41100000`, -118.625 =
    `C276A000`, 0.1 = `4019999A`, the range ends `7FFFFFFF` / `00100000`, "1 - 16**-8 = 1" through the guard
    digit), and the runtime against `det/hfp.py` bit for bit over a vector table (`test_det_hfp.py`);
  - the behaviour against GnuCOBOL where both formats are exact (`test_det_programs.py` FLOAT, in byte, typed and
    typed-groups modes): every MOVE direction, the four verbs with and without GIVING, COMPUTE, IF / 88 / EVALUATE
    / sign conditions, SET TO TRUE, PERFORM VARYING, INITIALIZE of a group holding a float.
- **REFUSED by name** (a Hole: "... IBM hexadecimal floating point on z/OS, IEEE on the oracle:
  oracle_assumptions.md C6"): a float's bytes or those of an item over it (a group MOVE, a REDEFINES, a reference
  modification, STRING, a CALL argument, a record written, a COMMAREA); a float MOVEd to or from a nonnumeric item;
  a comparison with a nonnumeric operand; exponentiation in a floating-point expression (a run-time routine IBM does
  not document bit for bit); an intrinsic function in one (IBM's floating-point functions); ON SIZE ERROR and
  ROUNDED into a float, DIVIDE ... REMAINDER in floating point. In the runtime: an HFP exponent overflow or
  underflow (what z/OS does depends on the program mask and Language Environment). `ggdisplay.c` still refuses the
  DISPLAY of a float on the COBOL side (C8), so no proof compares one.
- **Waiting on it.**
  - `mortgage-mpmt` (EPSMPMT): its interest rate is now computed in long HFP, but the payment's `(1 + C) ** N`, N
    with decimal places, is a floating-point exponentiation: the one hole, so the case stays in the det sweep's
    baseline (KNOWN_UNPROVEN). It would also round where GnuCOBOL truncates.
  - CBSA's CRECUST, BANKDATA, BNK1CAC, BNK1CRA, BNK1TFN and BNK1UAC are not cases.
- **What would settle it.** A z/OS run of EPSMPMT's scenarios (#4050): the exponentiation, and the ASSUMED
  conversions above, checked where the oracle cannot.
- **Later slices of #4271** (left as they are): `NUMPROC(PFD)` with non-preferred signs (refused by name, C5),
  `ARITH(EXTEND)`, `TRUNC(OPT)` and `INTDATE(LILIAN)` (detected from CBL / PROCESS cards and refused, C5), COMP-5's
  z/OS byte order where bytes are observable (C7).

### C7. COMP-5 byte order — DIFFERS
- **What.** GnuCOBOL stores COMP-5 in the machine's order, little-endian on x86; z/OS is big-endian. COMP, COMP-4
  and BINARY are big-endian on both.
- **Visible only** when a COMP-5 item's bytes are read as bytes: a REDEFINES, a group MOVE, or a record written to a
  file.
- **Reached.** The harness's SQLCA declares its binary fields COMP-5, as IBM's does, and programs read them only as
  numbers. In the corpora, only CardDemo's IMSFUNCS.cpy declares COMP-5.
- **A VALUE beyond the PICTURE (#4501, fixed).** COMP-5 holds up to its 2, 4 or 8 bytes' capacity, not the value
  its 9s imply. The det translator wrote a COMP-5 VALUE truncated to the PICTURE and big-endian while its runtime
  reads COMP-5 little-endian: `S9(4) COMP-5 VALUE 32767` read back as -12534 (cics-crucible `ca-xctl-versions`,
  XCTL LENGTH). The image now holds the whole value in the runtime's (GnuCOBOL's) order; pinned by
  `test_det_programs.py` COMP5 against GnuCOBOL.

### C9. POINTER size — DIFFERS
- **What.** A POINTER is 8 bytes in GnuCOBOL on x86-64 and 4 on z/OS (31-bit), so every offset after one differs.
- **Reach.** CBSA passes IMS-era PCB pointers at the end of its COMMAREAs, always NULL. The port carries a POINTER in a
  COMMAREA DTO as NULL only (DetCics.pointerIn / pointerOut stop by name on an address) and refuses a DTO with data
  after a POINTER: the task stops by name when it gets one.
- **Waiting on it.** CBSA's INQACCCU, DELCUS and CREACC pass COMMAREAs with data after a POINTER. They need the COBOL
  side on 4-byte pointers (a 32-bit GnuCOBOL build) before they can be proven.
- **Procedure and function pointers** (#4462): the det translator lays out USAGE PROCEDURE-POINTER and
  FUNCTION-POINTER as it lays out POINTER, 8 bytes (GnuCOBOL's `sizeof(void *)` for both). IBM's procedure pointer
  is 8 bytes and its function pointer 4 (Enterprise COBOL Language Reference, USAGE clause), so offsets after a
  FUNCTION-POINTER differ the way they do after a POINTER. What is set into either (SET ... TO ENTRY) and a CALL
  through one are not modelled.

### C10. Zoned signs written by INITIALIZE and VALUE ZERO — DIFFERS (tolerated where declared)
- **What.** GnuCOBOL's INITIALIZE and VALUE ZERO leave a signed zoned item's last byte with the unsigned `F` zone;
  Enterprise COBOL writes the preferred sign, `C`. Both are the same positive value; the bytes differ.
- **Where it shows.** CardDemo's CBACT01C writes ARRYFILE entries that INITIALIZE leaves untouched.
- **Tolerance, scoped.** A case lists the datasets it applies to in `"zoned_sign_equivalent"` (only
  `carddemo-readacct`'s ARRYFILE today). In those datasets, and only there, a byte is taken as equal when it is a
  plain digit on one side and the same digit with the positive overpunch on the other (`{`, `A`–`I`: the ASCII
  data's form of an F zone against a C zone; `equivalence.accept_unsigned_positive`). The check is by byte value,
  not by field position, which is why it is declared per dataset rather than applied everywhere. Every such byte is
  counted in the run's summary (`C10: ARRYFILE n sign bytes F/C`), so the tolerance is visible, never silent.
  Everywhere else, signs are compared byte for byte.
- **Not tolerated.** A negative overpunch (`}`, `J`–`R`) against either form, a different digit, or any byte in an
  undeclared dataset.

### C11. A non-digit moved to a numeric DISPLAY item — DIFFERS (inputs kept out of the cases)
- **What.** COMEN01C moves the typed option (`WS-OPTION-X`, PIC X(2) JUST RIGHT) to `WS-OPTION` (PIC 9(2)) and then
  tests `WS-OPTION IS NOT NUMERIC`. With a non-digit typed, GnuCOBOL 3 (`-std=ibm`) gives `1!` -> `01` and `!1` ->
  `00`, both NUMERIC (measured 2026-10-03), so `1!` is option 1 and XCTLs. IBM treats an alphanumeric sender of a
  numeric MOVE as an unsigned integer and moves its bytes; a non-digit's digit nibble (`!` is X'5A') is not a digit,
  so on z/OS the item is not NUMERIC and the menu says the option is invalid -- IBM documents no result for such
  data.
- **Found by.** The test-strengthening loop (#4049): the model-written port treats `1!` and `!1` as invalid options,
  GnuCOBOL does not; the proofs differ on both inputs.
- **Now.** Those inputs are not in the case, so the three COMEN01C survivors in the port's own digit test stay case
  gaps. A z/OS run (#4050) settles which side is right.

### C12. FUNCTION RANDOM — the numbers DIFFER from z/OS, the interface ASSUMED; refused where IBM does not allow the seed
- **IBM** (Enterprise COBOL 6.4 Language Reference, RANDOM,
  https://www.ibm.com/docs/en/cobol-zos/6.4.0?topic=functions-random): argument-1, if given, "must be zero or a
  positive integer", and only 0 to 2,147,483,645 "yield a distinct sequence"; "if the first reference to this function
  in the run unit does not specify argument-1, the seed value used will be zero"; later references with no argument
  "return the next number in the current sequence"; the value is "exclusively between zero and one". The generator
  itself is not published: the same seed gives z/OS's sequence, which nobody outside IBM can reproduce.
- **The oracle.** GnuCOBOL 3.1.2 (`libcob/intrinsic.c`, `cob_intr_random`) calls glibc's `srand(seed)` (a negative
  seed is 0; glibc makes seed 0 seed 1, so an unseeded process starts as seed 0) and returns `rand() / RAND_MAX` as a
  double, which a COMPUTE takes at its exact binary value. The state is the process's: a CICS task (one process in
  the stub, #4004) shares it across LINK levels.
- **The det runtime** (`Funcs.Random`) reproduces that sequence exactly (glibc's TYPE_3 generator: seeding by
  16807 LCG, 310 numbers discarded) and its double. One sequence per translated program, reset by each entry point
  (`runProgram`, `runBatch`, `runTask`: a run unit begins; IBM's seed zero). A seed that is negative or not an
  integer (IBM does not allow it) or past 2,147,483,647 (the oracle's `cob_get_int`) is refused at run time
  (`IllegalArgumentException`, "not modelled"), never guessed.
- **So a proof says:** given the numbers the oracle draws for the run's seed, the port does what the COBOL does with
  them -- the arithmetic, its truncation into the receiving item, and every output computed from it. It does NOT say
  the port draws z/OS's numbers: a credit score (CBSA CRDTAGY1-5), a customer number (INQCUST, GenApp LGICVS01) or a
  DELAY interval computed from RANDOM differs from z/OS's for the same seed, and is equal across the two sides only
  because both use the oracle's generator. That equality is a stated fact of the harness run, as the clock is (M4):
  the seed these programs use is `EIBTASKN`, which the harness states on both sides (X21: 0 unless a case or scenario
  states its `"taskn"`), so every task draws RANDOM(0)'s sequence by default, and RANDOM(n)'s for a stated n.
- **Known differences, unreached.** The oracle can return exactly 0 or 1 (`rand()` of 0 or `RAND_MAX`, about once in
  2^31 draws), IBM never does; the port follows the oracle. A LINKed program is a new run unit on z/OS (its own
  sequence from seed zero) but shares the task's process state in the oracle; the port gives each program its own
  sequence, so a task whose caller and LINK target both draw unseeded numbers would differ. A CALLed program shares
  its caller's run unit on z/OS; the port keeps the CALLed program's own sequence. No translated program reaches
  these: each one's first reference is seeded.
- **Reached.** No proof yet: no equivalence or crucible case runs CRDTAGY1-5, INQCUST or LGICVS01. Pinned against
  GnuCOBOL by `tests/cobol_mainframe/test_det_programs.py` (`RANDOM`: an unseeded first reference, seeds 0,
  42, 1,234,567 and 2,147,483,647, CRDTAGY's and LGICVS01's COMPUTEs) and against glibc's own numbers by
  `test_det_funcs.py`.
- **To settle.** Only a z/OS run can give IBM's numbers; even then they would be data for a declared difference, not
  a model, since the generator is unpublished.

### C14. Size errors (a zero divisor, an exponent, overflow) — the det runtime MATCHES the oracle (#4655); the oracle DIFFERS from z/OS where IBM leaves the result undefined
- **IBM** (Enterprise COBOL for z/OS Language Reference, "SIZE ERROR phrases"; the wording below is paraphrased
  from the 6.x manual and not re-fetched for this entry -- confirm it against
  https://www.ibm.com/docs/en/cobol-zos/6.4.0?topic=statements-size-error-phrases before quoting it): a size error
  condition is a result whose absolute value, after decimal-point alignment, exceeds the receiver; a division by
  zero; and, in an exponentiation, zero raised to the zero power, zero raised to a negative power, or a negative
  number raised to a fractional power. It applies to final results only. With ON SIZE ERROR the receivers keep
  their values and the imperative statement runs. Without it, an overflow is truncated (the receiver's high-order
  digits are lost) and the result of the other cases is undefined; on z/OS a packed-decimal divide by zero is a
  decimal-divide exception (S0CB abend) unless the compiler checks first.
- **The oracle** (GnuCOBOL 3.1.2 `-std=ibm`, measured 2026-10-07): a zero divisor makes libcob's NaN intermediate
  (`cob_decimal_div` sets scale COB_DECIMAL_NAN and EC-SIZE-ZERO-DIVIDE); an operation with a NaN operand gives NaN;
  storing a NaN (`cob_decimal_get_field`) leaves the receiver unchanged. So, with or without ON SIZE ERROR:
  `COMPUTE R R2 = A / Z` changes neither receiver; `COMPUTE R = A / Z + 1` and `(A / Z) * 0 + 7` change nothing;
  `DIVIDE Z INTO R R2` leaves each receiver; `DIVIDE A BY Z GIVING Q REMAINDER RM` leaves Q and RM; `0 / 0` is the
  same. Where cobc truncates an intermediate (ARITHMETIC-OSVS, C2), `cob_decimal_align` turns the NaN into 0:
  `COMPUTE R = A / Z * C` stores 0, and `(A / Z) + (A / B)` stores A / B; in a condition an aligned quotient is 0
  (`A / Z = 0` is true) while an unaligned one compares as its dividend scaled by 10^32768 (`0 = A / Z` is false).
  An intrinsic function's argument divided by zero is 0 (`cob_intr_binop`), and FUNCTION MOD / REM by zero are 0
  with no size error. `0 ** 0` is 1 with the size error raised; `0 ** -1` is 0 with no size error; a negative base
  with a fractional exponent, or an exponent past a double's range, leaves the receiver unchanged with the size
  error raised. An overflow without ON SIZE ERROR is truncated (IBM's rule). With ON SIZE ERROR the phrase runs
  whenever the statement raised a size error, even if a receiver changed (the aligned 0, 0 ** 0's 1); the
  exception code is cleared when the statement starts.
- **The det runtime (since #4655)** does the same: `Cobol.divide` returns libcob's NaN (the dividend's digits at
  scale -32768) for a zero divisor, `Cobol.add / subtract / multiply / negate / power` carry it where the translator
  sees that an operand can be one (a division or an exponent below it), `Cobol.store` and `storeChecked` leave the
  receiver (a lifted receiver is guarded with `Cobol.isNan`), `Cobol.align` truncates it to 0 as libcob does, and a
  comparison sees its scaled value as cob_decimal_cmp does. A division inside a function's argument is
  `Cobol.divideIntr` (0). A statement with ON SIZE ERROR and a division or exponent clears and reads the size-error
  state (`Cobol.sizeClear` / `sizeRaised`, per thread). `Cobol.remainder` computes DIVIDE's REMAINDER from the
  quotient truncated to the quotient receiver's places, as cob_div_quotient does (before, the stored quotient was
  used: a quotient too big for its receiver, or ROUNDED up, gave a wrong remainder). Pinned by
  `tests/cobol_mainframe/test_det_size_error.py` (every shape above, both port modes) and a randomized differential
  run (2026-10-07: 56 random programs with zero divisors, DIVIDE and ON SIZE ERROR / NOT ON SIZE ERROR phrases,
  every output equal to the oracle's).
- **Not modelled.** A zero divisor in floating point (COMP-1 / COMP-2, `Hfp.divide`) still stops the run with an
  ArithmeticException, a named stop rather than a guess.
- **So a proof says:** for a scenario that divides by zero without ON SIZE ERROR, the port does what the oracle
  does (receivers unchanged), which z/OS does not promise: IBM leaves the result undefined and a z/OS run may
  abend. With ON SIZE ERROR both sides agree with IBM (receivers unchanged, the phrase runs), except `0 ** -n`,
  which IBM calls a size error and the oracle (and so the port) computes as 0.
- **Reached.** Not known to be: no proven scenario divides by zero or raises a size error from an exponent.
- **To settle.** A z/OS run of the shapes in `test_det_size_error.py` without ON SIZE ERROR.

### C8. DISPLAY text — MATCHED
- **What.** GnuCOBOL writes a signed zoned item as `012-` and a binary item as `-00007`. IBM writes their external
  decimal form with the sign overpunched (`01K`, `000P`). `ggdisplay.c` (LD_PRELOAD) rewrites each such operand as
  IBM does.
- **Refused.** An operand outside the model (floating point, more than 32 operands) writes `GGDISPLAY-NOT-MODELLED`,
  and that run's SYSOUT is not compared.

## Data and encoding

### D1. Text order is ASCII — DIFFERS
- **What.** Proofs run with ISO-8859-1 data on both sides, so every alphanumeric comparison (`IF A > B`, a THRU range,
  a key's order) uses ASCII order. EBCDIC order differs:
  - lower case sorts before upper case;
  - letters sort before digits;
  - space sorts before both.
- **Keys.** Indexed files are browsed in ASCII order on both sides (`equivalence.COLLATION`). CardDemo's keys sort the
  same either way. Keys mixing letters and digits would not.
- **SORT / MERGE under an alphabet (#4268).** `ALPHABET ... IS EBCDIC` orders by code page 037 on z/OS (the default
  CODEPAGE(1140)'s order); GnuCOBOL uses its own ASCII-to-EBCDIC table, which agrees for every 7-bit character but
  `[ ] ^ |` and for no byte above X'7F'. A literal alphabet's THRU ranges and its unnamed characters follow the
  native set: EBCDIC on z/OS, the data's bytes in GnuCOBOL. The det runtime (`Sort.Collating`) keeps both orders,
  sorts by IBM's, and stops by name on a pair of keys the two order differently, so a proven sort is IBM's. A key
  under an alphabet must hold characters only (a packed or binary byte is the same byte in both code pages).
- **In-program comparisons.** `Cobol.compare` is byte order in the data's code page. No audit has counted the
  relational comparisons whose result could change between ASCII and EBCDIC.
- **PROGRAM COLLATING SEQUENCE in relation conditions (#4539).** Under an EBCDIC or a literal alphabet, the
  nonnumeric comparisons of IF, EVALUATE (conditions and THRU ranges), PERFORM UNTIL and condition-names (88 THRU
  ranges) go through `Sort.Collating` as SORT keys do: the shorter operand padded with spaces, IBM's order taken,
  a pair of operands the two order differently stopped by name. Numeric comparisons stay by value; national data
  is refused by the translator. An equality consults the alphabet only when it has ALSO (otherwise each character
  has a position of its own). Refused by name: HIGH-VALUE / LOW-VALUE under a literal alphabet (the characters of
  its highest / lowest position; GnuCOBOL's LOW-VALUE is the alphabet's first character), an ordering of an item
  holding packed / binary / signed items, and an ordinal alphabet. Under EBCDIC,
  HIGH-VALUE is X'FF' on both sides, but the harness's byte X'FF' is 'ÿ' (cp037 X'DF'): an ordering of HIGH-VALUE
  against a character cp037 places above X'DF' (S-Z, digits) stops the run by name. SEARCH is not translated.
- **A migration decision as much as an oracle gap.** A port that will run on ASCII data either keeps ASCII order (a
  declared difference, #4051) or compares in cp037 order.
- **To settle.**
  1. Count the alphanumeric relational conditions per proven program.
  2. Run the proofs with `data_encoding: cp037` where the program's literals allow it.

### D2. Hex literals that name EBCDIC characters — DIFFERS
- **What.** `X'40'` is a space on z/OS and `@` in ASCII.
- **Corpora.**
  - GenApp's LGTESTC1 uses `x'40'` and `x'00'`; it is not a proven case.
  - CardDemo's CSUTLDTC compares LE feedback tokens (`X'...C3C5C5'`, "CEE" in EBCDIC). The CEEDAYS model writes
    those same bytes.
  - CBSA's PROCTRAN.cpy uses `X'FF'`, which is the same byte in both.
- **Screen attributes.** The DFHBMSCA stand-in holds the EBCDIC byte values, as the program's symbolic map expects
  them.

### D3. Zoned signs in ASCII data — MATCHED
- `-fsign=EBCDIC` reads the corpora's ASCII data with EBCDIC-style overpunch (`{` = +0, A–I positive, `}` J–R
  negative), as the data was unloaded from z/OS.

### D4. A character no single-byte code page holds, in an alphanumeric literal — REFUSED (the statement, #4272)
- **What.** A UTF-8 source with an em dash (U+2014) in `MOVE 'Conto bloccato — operazione negata' TO WS-MSG` (a
  census estate's CICS messages, 2026-10-06). Enterprise COBOL reads its source in the single-byte EBCDIC code page
  of its CODEPAGE option, and an alphanumeric literal's length is its bytes in that page (Enterprise COBOL for z/OS
  Language Reference, "Alphanumeric literals"; DBCS characters only as a mixed literal
  between shift-out / shift-in under the DBCS option). No SBCS EBCDIC page (037, 1140, 280 / 1144 ...) and not
  Latin-1, the det runtime's record charset, holds U+2014.
- **Why refused.** COBOL does not decide what the literal is: the transfer of the source to the compiler does. A
  transcoding transfer substitutes one byte (SUB, X'3F') or fails; a binary one keeps three bytes (X'E28094', read as
  EBCDIC characters); GnuCOBOL takes the three UTF-8 bytes as written. The literal's bytes and its length (so the
  receiver's padding or truncation) differ between them; guessing one would make a port agree with one toolchain and
  not the estate's. Even column 72 moves: the translator counts a character a column, a compiler reading the UTF-8
  bytes counts the em dash as three.
- **What the translator does.** `source.narrowed` hands the grammar a stand-in (U+001D) for the character, column
  for column, and the statement holding the literal (a MOVE, an IF's or a WHEN's condition, an EXEC block) is
  `throw new Hole(...)` with gen.WIDE_WHY; the rest of the program translates. The literal never reaches Java.
- **Still refused whole** (`source.unmodelled`): the character in a VALUE (it lays the program's storage out), in a
  national / DBCS literal (N'…', G'…', NX'…', U'…': national data is not modelled, #4272) or in a name. In a `*>`
  comment it is read (no parser reads a comment).
- **To settle.** An estate that states how its source reached the compiler (its transfer code page, or GnuCOBOL with
  UTF-8 source) decides the bytes; then the literal can be translated to them.

## Files

### F1. FILE STATUS from GnuCOBOL's indexed files — ASSUMED
- **What.** The statuses a run meets naturally (00, 02, 10, 22, 23, 35 …) come from GnuCOBOL's Berkeley DB files.
- **Assumed** to match VSAM for these common codes.
- **Not modelled.** VSAM's OPEN-time checks: 39 (attributes conflict), 04 (record length) and 97 (verified open).

### F2. Injected faults — MATCHED
- Fault runs (`ggfault.c`, CICS `faults.cfg`) give a statement the same status or RESP on both sides, and say which
  faults fired.
- The values are the ones IBM documents for the condition. What a real device failure would give is not modelled.
- **CICS commands beyond files (#4049).** XCTL, WRITEQ TS, START, RETRIEVE and CANCEL take a plan too (named by the
  program, queue, TRANSID, `-` and REQID), in the equivalence harness and in the CICS crucible's strengthened
  scenarios. A planned command does nothing but return its RESP / RESP2: the XCTL does not transfer, the WRITEQ TS
  writes no item, the START schedules nothing, the RETRIEVE moves no data, the CANCEL cancels nothing. IBM's
  descriptions of these conditions say the request was not performed; a partial effect is not modelled. Only
  conditions IBM lists for the command are planned (CICS TS, each command's "Conditions"): XCTL PGMIDERR (RESP2 3,
  the program could not be loaded); WRITEQ TS INVREQ; START INVREQ (RESP2 17); RETRIEVE IOERR. An unhandled one
  abends with the code the stub and CicsTask already give it (AEI0, AEIP). CANCEL has no INVREQ, so a port's
  `INVREQ` branch after CANCEL stays unreachable.

### F3. Record formats — ASSUMED
- Most cases' datasets are fixed-length records.
- **Variable-length records (RECFM=VB)** are exercised since `carddemo-readacct` (CBACT01C's VBRCFILE: a 12-byte and
  a 39-byte record per account, `RECORD VARYING DEPENDING ON`). Records are compared by content and length, framed
  as GnuCOBOL writes a variable sequential file: a 2-byte big-endian length, two zero bytes, then the data
  (`equivalence_common.split_varseq`). Unlike a z/OS RDW, that length does not count the 4-byte header.
- **Assumed.** That a record's content and length are what z/OS would write; block descriptors (BDW) and spanned
  records are not modelled. The det translator writes the same framing (`DetFiles`); before this it wrote VB records
  padded to the maximum length, which no case had exercised.

### F4. JCL utility steps — out of scope
- A batch case runs one program step.
- SORT, IDCAMS, IEBGENER and DFSORT steps are not run. The generated batch job refuses a utility step by name
  (`JclSteps.utility`: the job fails on its TODO, or with `gitgalaxy.batch.skip-unimplemented` the step is logged as
  skipped; never a silent success).
  Next slice of #4268: DFSORT / ICETOOL control cards (SORT FIELDS, INCLUDE / OMIT, OUTREC / INREC, SUM), IEBGENER
  and an IDCAMS REPRO / DEFINE subset in the oracle, and a multi-step job case.
- The COBOL SORT / MERGE / RELEASE / RETURN verbs and the SD entry are translated (#4286), onto `cobolrt/Sort`:
  - Keys compare as a relation condition compares their items: a numeric key (zoned, packed, binary, signed or
    not) by value, any other byte by byte. WITH DUPLICATES IN ORDER is a stable sort; without it, records with
    equal keys and different bytes stop the run by name (IBM: their order is undefined). A MERGE input out of key
    order stops the run by name.
  - USING / GIVING files are opened, read or written and closed implicitly; their FILE STATUS items are left as
    they were (GnuCOBOL does not set them; IBM's depends on FASTSRT).
  - COLLATING SEQUENCE (or PROGRAM COLLATING SEQUENCE): NATIVE, STANDARD-1 and STANDARD-2 are the data's byte order
    (D1). EBCDIC and literal alphabets (#4268) order the alphanumeric keys; see D1 for where IBM and GnuCOBOL
    differ.
  - Refused by name: SORT of a table (format 2), a key under OCCURS, an SD whose records differ in length, a USING /
    GIVING file whose records are not the SD record's length, SORT-RETURN set by the program (16 ends a sort), an
    alphabet ordinal (a numeric literal names a native code: EBCDIC on z/OS), HIGH-VALUE / LOW-VALUE in an
    alphabet, and a group key holding numeric items under an alphabet.

## CICS (`ggcics.c`)

### X1. Commands from IBM's documentation — ASSUMED
- **Source.** Each command's RESP/RESP2, length handling and EIB fields follow the IBM CICS TS for z/OS 6.x API
  reference, cited in the code.
- **Checked against.** The cics-crucible (210 doc-cited cells passing, v0.5.0). Not checked against a CICS region.

### X2. Screens are compared as the symbolic map — ASSUMED
- **Compared.** Each SEND MAP's symbolic map: the data, the attribute, colour and highlight subfields, and the cursor
  (length -1).
- **Not modelled.** What a 3270 shows after BMS merges the physical map, MAPONLY, DATAONLY, ERASE and FRSET. Two
  ports with equal symbolic maps could differ on a terminal only if BMS itself differed.

### X3. Backout and recoverable files — MATCHED
- **What.** SYNCPOINT ROLLBACK, or an abend that terminates the task, backs out the unit of work: the recoverable files'
  changes and the task's Db2 changes. A file the CSD defines RECOVERY(NONE) keeps its changes (CBSA's ABNDFILE: the
  abend log a backout must not undo).
- **How.** A case states a dataset's RECOVERY(NONE) (`"recovery": "NONE"`, with a `recovery_why` citing the CSD: the
  engine's facts do not carry the attribute). The COBOL model does not save such a file for backout; the Java side
  makes its changes outside the task's transaction (REQUIRES_NEW).
- **Fixed 2026-10-02.** Until then the COBOL model backed out every file, and the Java side backed out nothing on an
  abend that terminated the task (only on SYNCPOINT ROLLBACK). No proven scenario had changed a file and then abended.
- **Not modelled.** Temporary storage is not backed out (CICS backs out recoverable TS queues).
- **SYNCPOINT's response (#4437).** Both sides answer SYNCPOINT and SYNCPOINT ROLLBACK with NORMAL (RESP 0,
  RESP2 0, EIBRESP too); the det port writes it where it used to leave RESP / RESP2 as they were. IBM documents
  INVREQ (RESP2 200: a program LINKed from a remote system without SYNCONRETURN, or one defined
  EXECUTIONSET(DPLSUBSET)) and, for SYNCPOINT only, ROLLEDBACK (a remote system cannot commit). In the modelled
  region a LINK is local and no remote system takes part. A program LINKed from outside the region (CicsTask's DPL
  server, `LocalRegion.linked`) refuses SYNCPOINT, since the region does not know whether its client gave
  SYNCONRETURN. EXECUTIONSET is not read: CBSA's CSD defines its programs FULLAPI (`BANK.csd`).

### X4. Time — ASSUMED
- **What.** EIBDATE and EIBTIME are the case's clock at dispatch. ASKTIME leaves them unchanged (a task takes no time),
  and FORMATTIME formats from that clock.
- A DELAY takes no time either (CBSA's INQCUST and credit agencies retry after one); ENQ and DEQ are NORMAL, one
  task being the region's only one.

### X5. What IBM leaves open — REFUSED
Refused by name (`equivalence_cics.Unsupported`):
- HANDLE ABEND PROGRAM;
- START with interval options;
- READQ TS with SET or SYSID;
- an option the stub does not know.

The length READQ TS returns on ITEMERR or QIDERR is not documented, so it is not set.

### X6. A WRITEQ LENGTH past its FROM item — REFUSED, the task judged up to it
- **What.** GenApp's LGSTSQ (the error logger every GenApp program LINKs on its error paths) writes
  `LENGTH(WS-RECV-LEN)`, the caller's COMMAREA length + 5. That is more than `FROM(WRITE-MSG)` holds (95 bytes) when the
  caller passes more than 90 bytes -- WRITE-ERROR-MESSAGE's second LINK passes the 99-byte CA-ERROR-MSG, so LGSTSQ
  writes 104 bytes -- and CICS copies the bytes that follow WRITE-MSG in storage.
- **Why the WRITEQ is not judged.** Those bytes depend on how the compiler lays out WORKING-STORAGE; GnuCOBOL's layout
  is not IBM's, so no oracle here can say what z/OS writes. **Not settled on z/OS (#4050).**
- **Refused, both sides.** The translated WRITEQ TD / TS checks its LENGTH against the FROM item and stops the run (98,
  "WRITEQ TD LENGTH > FROM: not modelled"); the det port refuses at the same statement (`DetCics.within` throws
  `DetCics.PastFrom`, #4607). START / PUT CONTAINER / GET CONTAINER past their area stay refused whole.
- **Judged up to the refused WRITEQ** (owner decision on #4607, 2026-10-07). A task that reaches it -- a scenario or a
  derived SQL-fault task -- is compared up to that statement, the way #4173 judges a task up to a LINK not run:
  every event before it (the LINKs, the WRITEQ TD / TS records of the first, short LGSTSQ call, RETURNs) field by
  field, and it passes only when BOTH sides stopped at it (the report's `x6`; `judged_to` names the refusal). Its end
  state -- files, tables, the COMMAREA it leaves -- is not compared. The branch outcomes it ran before the refusal
  count as executed (the COBOL trace stops at the refusal). A proof that leans on such a task lists X6 among its
  assumptions: what the task would have done after the WRITEQ on z/OS is not claimed.
- **#4173.** An SQL-fault task (M2) that reaches a LINK to a program the case does not run is judged up to and
  including that LINK -- its events and the COMMAREA's bytes as LINKed, byte for byte. With LGSTSQ in a case's
  `"programs"` (GenApp's Db2 cases, #4607) the task runs on to the X6 refusal instead.
- **Reached since (#4270, X23):** WRITE-ERROR-MESSAGE's `IF EIBCALEN < 91` true side in LGACDB02, LGDPDB01 and
  LGIPDB01, by scenarios that state a COMMAREA shorter than 91 bytes (`commarea_length`). LGACDB01's and LGUCDB01's
  need a failing statement whose host variables lie past EIBCALEN (X23).

### X7. ASSIGN INVOKINGPROG / PROGRAM, and several programs in one task — MATCHED
- ASSIGN PROGRAM is the running program, INVOKINGPROG the program that LINKed or XCTLed to it (blanks for a task's
  first program), as IBM's ASSIGN documents.
- A case's `"programs"` run in the same task on both sides: the COBOL side's dispatcher (as the cics-crucible's) and
  the Java side's `CicsTask.Programs`, each a port. A LINK is compared by its target; what the target did is compared
  through its files, tables, queue writes and the COMMAREA it leaves.
- **Queue writes (#4607).** A WRITEQ TD is an event (queue, record text) and so is a WRITEQ TS (queue, the item as
  text, RESP, item number), on both sides as CicsTask records them. Before #4607 the COBOL side dropped the stub's
  WRITEQ-TS line, so any task that wrote TS differed. The item is read in each side's page: the stub's storage page,
  and the det port's region page (CCSID 037 by default, #4528); a port in another region page shows as a difference.

### X8. A reference modification past its item — not run
- **What.** GenApp's LGAPDB01 MOVEs into `WS-VARY-CHAR(1:WS-VARY-LEN)`, the COMMAREA's length less the request's:
  with the 32500 bytes its caller LGAPOL01 passes, about 28K past WS-VARY-CHAR's 3900. Compiled without SSRANGE (IBM's
  default) that overwrites whatever follows in storage; GnuCOBOL's layout is not IBM's.
- **Effect.** The det port stops (an index error), so such a scenario can never be proven by accident; the case leaves
  it out and says so. A COBOL-side check (GnuCOBOL's EC-BOUND-REF-MOD) would turn it into a refusal by name.
- **A subscript past its table is the same** (#4463): CardDemo COMEN01C rejects an option above 11, then still reads
  `CDEMO-MENU-OPT-USRTYPE(WS-OPTION)`; option 99 reads 4K past the record. carddemo-menu's `option-12-typed-over` sent
  99 from #4049 on, and its det port stopped there (an index error) -- the case now sends 12, inside the 12-entry
  table. GnuCOBOL's EC-BOUND-SUBSCRIPT would make the COBOL side refuse such a scenario by name.

### X9. Named counters — MATCHED
- GET COUNTER returns the counter's value and then adds one (IBM CICS TS, GET COUNTER); a counter the region does not
  have is NOTFND. A case (or a scenario) states the region's counters (`"counters": {"POOL/NAME": next}`); both sides
  read the same. Other counter options (INCREMENT, WRAP, MINIMUM / MAXIMUM, RESP2 ...) are refused by name.

### X10. A LINK target's COMMAREA past the caller's record — DIFFERS (#4181)
- **What.** A LINK passes the COMMAREA by reference: the target sees the caller's storage from the area's first byte,
  for as long as its own DFHCOMMAREA (or the contract DTO it is typed with) reaches. When that is longer than the
  caller's record (GenApp's 71-byte ERROR-MSG LINKed to LGSTSQ, typed as the 99-byte CA-ERROR-MSG), z/OS shows the
  target whatever storage follows the record; so does GnuCOBOL, in its own layout.
- **The det port.** Gives the target the caller's bytes up to the end of the caller's record and LOW-VALUES past it
  (`Cobol.commarea`), and writes back as far (`Cobol.commareaBack`); it never reads past the record (before #4181 it
  failed there). A det caller passes the bytes themselves too (`CicsTask.link(..., area)`), so a det target sees every
  byte, the ones its contract DTO does not name included (CA-ERROR-MSG's leading FILLER).
- **Reached.** Not by a proof: no case runs a target that reads past its caller's record.

### X11. ASKTIME ABSTIME into a narrow field — DIFFERS
- **What.** ABSTIME is an 8-byte packed value (IBM: `PIC S9(15) COMP-3`). GenApp declares `WS-ABSTIME PIC S9(8) COMP`
  (4 bytes), so on z/OS ASKTIME writes past it into the next item, and FORMATTIME reads 8 bytes back from there.
- **Here.** Both sides store into the declared 4-byte field and agree (GenApp's error message dates come out as
  `01011900`); z/OS would not give that. Equal on both sides, so no verdict changes, but the date in GenApp's error
  messages is not z/OS's.
- **Reached.** Yes, by GenApp's SQL-fault tasks (M2).

### X12. DFHCOMMAREA referenced with EIBCALEN = 0 — UNDEFINED, masked
- **What.** IBM DBB EPSCMORT does `MOVE DFHCOMMAREA TO W-COMMUNICATION-AREA` before it tests EIBCALEN, so its first
  task (no COMMAREA) copies storage it was never given. On z/OS that is undefined: CICS establishes no addressability
  for an absent COMMAREA, and what the MOVE reads (or whether it abends) depends on the region.
- **Harness.** The CICS model gives LOW-VALUES there. A numeric field the task then returns still holding all
  LOW-VALUES was set by nothing (a MOVE leaves digits, never X'00'), and the Java side's COMMAREA DTO cannot hold an
  invalid number. In a scenario with `"commarea": null` only, such a field is left out of the comparison on both
  sides and counted (`undefined_commarea_fields` in the report): `equivalence_cics.mask_absent_commarea`. Every other
  field of that COMMAREA, and every field of every other scenario, is compared as usual.

### X13. An ESDS browsed by relative byte address — ASSUMED, REFUSED where IBM is silent (#4213)
- **What IBM documents** (CICS TS 6.x, EXEC CICS STARTBR / READNEXT / READPREV, and "Sequential reading (browsing)"):
  with RBA, RIDFLD "contains a relative byte address"; RBA on the STARTBR "applies to every READNEXT or READPREV command
  in the browse, and causes CICS to return the relative byte address of each retrieved record"; EQUAL "is the default
  for a direct ESDS browse" and GTEQ "is not valid for directly browsing an ESDS"; a RIDFLD of X'FF' characters, with
  RBA, positions at the end for READPREV; READPREV right after STARTBR needs the STARTBR's record to exist; to
  reposition, RIDFLD is set "in the same form as on the previous STARTBR" (an RBA). Both sides model that, with the
  keyed browse's rules for changing direction (`ggcics.c` rba_startbr / rba_read, `CicsTask.startbrRba` /
  `readnextRba` / `readprevRba`; the det translator emits them).
- **Assumed.** An ESDS of fixed-length records in arrival order whose RBA is the record's byte offset (record *n* at
  *n* × reclen), RIDFLD a big-endian fullword. On z/OS a record's RBA is its offset within the data set's control
  intervals, so where records do not fill a CI exactly (free space, the CIDF and RDFs at each CI's end) the RBAs after
  the first CI are larger than *n* × reclen. A program that only starts at RBA 0 or X'FFFFFFFF' and passes back the RBAs
  READNEXT returned (IBM DBB EPSMLIST) never sees the difference; one that computes an RBA would. A case may state an
  ESDS the estate never defines (`datasets.<name>.csd`: organization ESDS, reclen, why), as MortgageApplication needs
  for EPSMORTF; an IDCAMS `NONINDEXED` DEFINE with RECORDSIZE(n n) is read as one.
- **Refused by name** (exit 98 / `UnsupportedOperationException`, "... not modelled"): an RBA at which no record
  starts (IBM does not say whether VSAM answers NOTFND, INVREQ or ILLOGIC; past the end of the data included); RBA on a
  file that is not an ESDS (a KSDS by RBA); a keyed command on an ESDS; a browse that mixes RBA and keys; an RBA RIDFLD
  shorter than a fullword. By the translators: XRBA, RRN, READ / WRITE / DELETE by RBA, GTEQ or KEYLENGTH with RBA.
- **Reached.** Yes: mortgage-mlist (IBM DBB EPSMLIST) browses its ESDS from RBA 0 to ENDFILE.

### X14. READ ... INTO LENGTH — ASSUMED, REFUSED where IBM is silent (#4436)
- **What IBM documents** (CICS TS 6.x, EXEC CICS READ): LENGTH "specifies the length, as a halfword binary value, of
  the data area where the record is to be put. On completion of the READ command, the LENGTH parameter contains the
  actual length of the record"; a record longer than LENGTH is truncated to it, with LENGERR RESP2 11 ("the record is
  truncated, and the data area supplied in the LENGTH option is set to the actual length of the record"). Both sides
  model that for a keyed READ (`ggcics.c` GGCREAD with LENGTH in GG-LEN and set back on NORMAL / LENGERR;
  `DetCics.readInto` in the det port). Without LENGTH it is LENGTH OF INTO, as the CICS translator supplies it.
- **Assumed.** LENGERR RESP2 13 ("an incorrect length is specified for a file with fixed-length records") is not
  raised for a LENGTH other than the record's length: the cases' files are VSAM KSDSs, and GenApp itself reads its
  225- and 64-byte records with LENGTH set from EIBCALEN. The length set back is stored as a COBOL MOVE of a fullword
  into the program's item (CICS stores a halfword): the same below 10,000 bytes in a four-digit item, as every record
  here is.
- **Refused by name** (exit 98 / `UnsupportedOperationException`, "... not modelled"): a negative LENGTH; a record
  moved past the end of INTO (CICS writes the storage that follows INTO, which GnuCOBOL lays out unlike IBM's
  compiler, as X6); LENGERR on READ UPDATE (IBM does not say whether the record is then held for the REWRITE). The
  det translator still refuses LENGTH on READNEXT / READPREV and an RBA browse unless it is INTO's own length.
- **Reached.** NORMAL only: GenApp LGUPVS01 (LINKed by LGUPDB01 with LENGTH 225: a 64-byte record into a 1024-byte
  area, LENGTH set back to 64) and LGUCVS01. LENGERR is not reached by a proven scenario: every non-NORMAL READ in
  GenApp goes to LGSTSQ (X6), and both GenApp READs are UPDATE.

### X15. Terminal RECEIVE and SEND CONTROL — ASSUMED, REFUSED where IBM is silent (#4413)
- **What IBM documents** (CICS TS, EXEC CICS RECEIVE (3270 logical) and (LUTYPE2/LUTYPE3)): with INTO and no
  MAXLENGTH, LENGTH is "the maximum length that the program accepts" (below zero, zero); MAXLENGTH overrides it;
  longer data is truncated with LENGERR and LENGTH "set to the original length of data", or, under NOTRUNCATE, "CICS
  retains the remaining data and uses it to satisfy subsequent RECEIVE commands" with LENGTH the length returned.
  On an LUTYPE2 terminal EOC "occurs when a request/response unit (RU) is received with end-of-chain-indicator set",
  default action: ignore it (the 3270 logical unit's RECEIVE has no EOC). HANDLE CONDITION ERROR takes only a
  condition whose default action is an abend, so not EOC. SEND CONTROL sends device controls; none of its
  conditions can arise without a BMS logical message, partitions, LDCs or REQID. Both sides model it: `ggcics.c`
  GGCRECT / GGCRECS / GGCSCTL, and CicsTask.receive / sendControl with `DetCics.received` / `receivedSet`.
- **Assumed.** The terminal is the reference region's 3270 logical unit unless the case CSD defines it with a
  TYPETERM `DEVICE(LUTYPE2)` (cics-crucible SPEC section 2): then the input message is one chain, its single RU
  carries end-of-chain, and the RECEIVE returning its last byte raises EOC. RECEIVE INTO moves the data into INTO's
  first bytes and leaves the rest as it was. RECEIVE SET(ADDRESS OF record): the port's LINKAGE record keeps its own
  storage, so the data is copied into it and the bytes past the data are X'00' (on CICS they are storage IBM does not
  describe; a program reading past LENGTH reads undefined bytes).
- **Refused by name** (`Unsupported` / CicsError, "... not modelled"): SET of anything but ADDRESS OF a LINKAGE 01
  record; SET without MAXLENGTH (IBM's "the value indicated in the LENGTH option is assumed" would read the LENGTH
  that SET only sets) or without LENGTH(data-area); ASIS, BUFFER and the APPC / partition options; SEND CONTROL CURSOR
  without a value, PRINT, FORMFEED, ALTERNATE / DEFAULT, MSR, partitions, LDC, ACCUM / PAGING / SET / REQID. At run
  time: a RECEIVE with nothing retained (it would wait for the operator), and on an LUTYPE2 terminal a NOTRUNCATE
  RECEIVE that leaves data retained (IBM does not say whether it raises EOC).
- **Reached.** cics-crucible hc-terminal-receive (7 scenarios: LENGERR by RESP, by HANDLE CONDITION and by default,
  NOTRUNCATE pieces, SET, SEND CONTROL with CURSOR) and hc-terminal-eoc (3: EOC by RESP, HANDLE CONDITION, ignored by
  default), cobol-stub and the det port both passing the hand-written logs.

### X16. HANDLE AID, IGNORE CONDITION, PUSH / POP HANDLE, HANDLE CONDITION ERROR — MATCHED, REFUSED where IBM is silent (#4414, #4502)
- **What IBM documents** (CICS TS, EXEC CICS HANDLE AID, IGNORE CONDITION, HANDLE CONDITION, PUSH HANDLE, POP
  HANDLE; RESP and RESP2 options). HANDLE AID: a key's label, taken "after the input command is completed; that is,
  after any data received in addition to the AID has been passed to the application program"; ANYKEY is "any PA key,
  any PF key, or the CLEAR key, but not ENTER"; a key named without a label is deactivated; a task an AID started
  gets its input buffer on the first RECEIVE "(even if the length of the data is zero)"; RESP implies NOHANDLE, which
  "overrides both the HANDLE AID and the HANDLE CONDITION command". IGNORE CONDITION: control returns after the
  command with the EIB set; the last HANDLE or IGNORE for a condition wins. HANDLE CONDITION ERROR: "if the default
  action for such a condition terminates the task abnormally, and the condition ERROR has been specified, the action
  for ERROR is taken" (so not for EOC, ignored by default). PUSH HANDLE suspends the IGNORE CONDITION, HANDLE ABEND,
  HANDLE AID and HANDLE CONDITION state; POP HANDLE restores it, INVREQ when no PUSH HANDLE was executed at the
  current link level. Both sides model it: `ggcics.c` GGCHCND / GGCHAID / GGCAID / GGCPUSH / GGCPOP / GGCCOND (#4003,
  #4007), and the det port's `handlers` (-1: IGNORE), `aids` and `pushed` with `condition()` / `aid()` and
  DetCics.aidLabel / Handlers (#4414; the ERROR step of `condition()`, #4502).
- **Refused by name** (`CicsError` / `Unsupported` at translation, a DRIVER-ERROR or IllegalStateException at run
  time): IGNORE CONDITION ERROR (IBM does not say whether ERROR's action can be to ignore); a condition name IBM does
  not document; a HANDLE AID key that is no attention key, or RESP / NOHANDLE on it; at run time, a HANDLE AID label
  that applies to the key of an input command that also raised a condition (IBM does not say which CICS acts on
  first: MAPFAIL on a RECEIVE MAP after CLEAR or a PA key is the common case), and a key deactivated while ANYKEY
  has a label (IBM does not say whether ANYKEY then takes it). The stub took the condition first and gave the
  deactivated key to ANYKEY before #4414; both are refused on both sides now.
- **Reached.** cics-crucible hc-handle-aid (9: a key's own label, ANYKEY not ENTER, a deactivated key, RESP, PUSH /
  POP HANDLE, CLEAR and PA1 with no data), hc-ignore-error (9: IGNORE, ERROR, a condition's own HANDLE or IGNORE
  before ERROR, IGNORE overriding HANDLE, PUSH suspending IGNORE and ERROR, POP restoring, POP with nothing pushed)
  and hc-eoc-error (2: ERROR does not take EOC), cobol-stub and the det port both passing the hand-written logs.

### X17. Channels and containers — ASSUMED, REFUSED where IBM is silent (#4270 slice 1)
- **What IBM documents** (CICS TS, EXEC CICS PUT / GET / DELETE CONTAINER (CHANNEL), LINK, XCTL, ASSIGN, "The current
  channel", "The scope of a channel"). PUT: "If the channel does not exist, it is created"; with no CHANNEL "the
  current channel is implied"; APPEND appends, otherwise the data is overwritten; a new container's data type is BIT
  "unless FROMCCSID or FROMCODEPAGE option is specified"; FLENGTH below zero is LENGERR RESP2 1; no CHANNEL and no
  current channel is INVREQ RESP2 4 (1 with DATATYPE). GET: FLENGTH in, "the length of the data to be read", and out,
  "the length of the data in the container"; a shorter area is truncated with LENGERR RESP2 11; NODATA reads only the
  length; CHANNELERR RESP2 2, CONTAINERERR RESP2 10, INVREQ RESP2 4; "If INTOCCSID and INTOCODEPAGE are not
  specified, the value for conversion defaults to the CCSID of the region". DELETE: CHANNELERR 2, CONTAINERERR 10,
  INVREQ 4. LINK / XCTL CHANNEL: the channel (created empty if absent) is the target's current channel; a LINKed
  program "can also return containers to the calling program". ASSIGN CHANNEL: the current channel's name, blanks
  without one. CONTAINERERR (110) and CHANNELERR (122) abend AEZJ / AEZV by default. Both sides model it: `ggcics.c`
  GGCPUTC / GGCGETC / GGCDELC / GGCASCH and GGCLINK / GGCXCTL with GG-CHAN, and CicsTask putContainer / getContainer
  / deleteContainer / linkChannel / xctlChannel / assignChannel.
- **Assumed.** A container holds the program's bytes. A BIT container is never converted; a CHAR one put and got
  with no CCSID option is in the region's CCSID both ways, so it is not converted either -- the port keeps the bytes
  in its storage's page and the stub in its own, as each side keeps every other area. A channel is in the scope of
  the level that created it and of a level it is LINKed or XCTLed to; the LINKed program's channels die with its
  level. A GET's data goes into INTO's first bytes and leaves the rest as it was; FLENGTH is set back on NORMAL and
  LENGERR only (on another condition IBM does not say).
- **Refused by name** (`CicsError` / `Unsupported` at translation, exit 98 / UnsupportedOperationException at run
  time): FROMCCSID, FROMCODEPAGE, INTOCCSID, INTOCODEPAGE, CONVERTST, CCSID (code-page conversion of a CHAR
  container); GET SET (a pointer to CICS's copy); BYTEOFFSET and PREPEND (no corpus program uses them); RETURN
  CHANNEL (the next task's channel: neither harness carries it, and no corpus program uses it); MOVE CONTAINER and
  STARTBROWSE / GETNEXT / ENDBROWSE CONTAINER (later #4270 slices); LINK / XCTL with both CHANNEL and COMMAREA. At run
  time: a PUT naming the other data type for an existing container (IBM says DATATYPE "applies only to new
  containers" and also lists INVREQ RESP2 33 for "an attempt ... to change the data-type"); a channel an XCTL left
  behind (IBM's scope tables do not say); an FLENGTH past FROM / INTO, or a negative one on GET; a name that is
  blank or has an embedded blank (IBM's "illegal character" rules are not modelled).
- **Reached.** cics-crucible ca-channel-containers (2 scenarios: CHAR / BIT / APPEND, LINK and XCTL CHANNEL, the
  current channel, truncation and LENGERR, NODATA, CONTAINERERR / CHANNELERR / INVREQ by RESP and by HANDLE
  CONDITION, AEZJ by default), cobol-stub and the det port both passing the hand-written logs (crucible branch
  `cases/channel-containers`, not yet released or pinned).

### X18. Interval control: START / RETRIEVE / CANCEL / RUN TRANSID — ASSUMED, REFUSED where IBM is silent (#4270 slice 2)
- **What IBM documents** (CICS TS, EXEC CICS START, RETRIEVE, CANCEL, RUN TRANSID, "Expiration times"). START: INTERVAL
  "the expiration time as an interval of time that is to elapse from the time at which the START command is issued"
  ("The mm and ss are each in the range 0 - 59"); TIME / AT a time of day, "If you specify a time with an hours
  component that is greater than 23, you are specifying a time on a day following the current one", and "If you
  specify a task to start at any time within the previous six hours, it starts immediately"; AFTER / AT as "A
  combination of at least two of HOURS(0 - 99), MINUTES(0 - 59), and SECONDS(0 - 59)" or "one of HOURS(0 - 99),
  MINUTES(0 - 5999), or SECONDS(0 - 359999)"; INVREQ RESP2 4 / 5 / 6 for HOURS / hh, MINUTES / mm, SECONDS / ss out of
  range; LENGERR "if LENGTH is not greater than zero"; TRANSIDERR, TERMIDERR; IOERR when "A START operation uses a
  REQID name that exists. This condition occurs only when the FROM option is also used". RETRIEVE: the data and the
  RTRANSID / RTERMID / QUEUE values, LENGERR with "the data area is set to the original length of the data", ENDDATA
  (also for a START "that did not specify any of the data options FROM, RTRANSID, RTERMID, or QUEUE"), ENVDEFERR when
  "a RETRIEVE command specifies an option not specified by the corresponding START command"; "Tasks without
  terminals access only a single data record". RUN TRANSID: a child task that "runs asynchronously with the starting
  task", its token in CHILD's 16-character area, TRANSIDERR RESP2 1. Both sides model it: `ggcics.c` GGCSTRT /
  GGCRTRV / GGCCNCL / GGCRUNT and CicsTask startRequest / retrieve / cancel / runTransid; the det translator ports the
  commands onto CicsTask (`Cics.start`, `retrieve`, `cancel`, `run_transid`) and sets EIBTRMID from the task.
- **Assumed.** A TIME whose mm / ss is out of range is INVREQ with RESP2 5 / 6, as INTERVAL's (IBM names RESP2 for
  INTERVAL / AFTER / AT only); several values out of range on one START report the first of hours, minutes, seconds;
  the RTRANSID / RTERMID / QUEUE values come back on LENGERR too; a RUN child runs once its parent has ended (a parent
  that never FETCHes it cannot tell, SPEC 4); the child token's bytes are the harness's own, the same on both sides.
  A START's FROM bytes travel in the region's page, as a TS item's (#4528).
- **Refused by name** (`CicsError` / `Unsupported` at translation, exit 98 / UnsupportedOperationException at run
  time): FETCH CHILD / ANY and FREE CHILD (a parent waiting for its child: a later #4270 slice); RUN / START CHANNEL
  (the child's copy of a channel); START USERID / SYSID / NOCHECK / ATTACH / BREXIT / FMH; RETRIEVE SET (a pointer)
  and WAIT; CANCEL of anything but a REQID. At run time: a START LENGTH past FROM's end (X6); a REQID that exists
  other than this task's own with FROM, reused with FROM; RETRIEVE INTO for a record whose START gave no FROM
  (whether that is ENVDEFERR); any RETRIEVE after ENVDEFERR (whether the record was used up); a RETRIEVE in a RUN
  child. The default abend codes of TRANSIDERR / TERMIDERR / IOERR / ENVDEFERR are not modelled: a program reaching
  one unhandled stops.
- **Reached.** cics-crucible gt-start-retrieve (6) and gt-terminal-coalesce (4) on the det port as on cobol-stub, and
  gt-start-options (7: data options, ENVDEFERR, RETRIEVE with no INTO, AFTER / AT and TIME(250000), INVREQ RESP2 6 / 5
  / 6 / 4, REQID IOERR, RUN TRANSID and its TRANSIDERR), cobol-stub and the det port both passing the hand-written
  logs (crucible branch `cases/start-retrieve-4270`, squid-protocol/cics-crucible#7, not yet released or pinned).

### X19. ASSIGN: STARTCODE / USERID / FACILITY / SCRNHT / SCRNWD — ASSUMED, REFUSED where the harness cannot decide (#4270 slice 3)
- **What IBM documents** (CICS TS 6.x, EXEC CICS ASSIGN, https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-assign).
  STARTCODE "returns a 2-character value that indicates how the transaction that issued the request was started": `D`
  / `DS` a distributed program link, `QD` "Transient data trigger level", `S` "START command that did not pass data in
  the FROM option", `SD` "START command that passed data in the FROM option", `SZ` FEPI, `TD` "Terminal input or
  permanent transid", `U` "User-attached task". USERID: "If no user is explicitly signed on, CICS returns the default
  user ID" (DFLTUSER, default `CICSUSER`). FACILITY "returns a 4-byte identifier of the principal facility ... If this
  option is specified, and no facility is allocated, INVREQ occurs"; SCRNHT / SCRNWD "the height / width of the 3270
  screen defined for the current task. If the task is not initiated from a terminal, INVREQ occurs". INVREQ RESP2 5:
  "The task is not associated with a terminal; or the task has no principal facility"; "Default action: terminate the
  task abnormally" (AEIP).
- **The harness's facts.** Each is stated by whoever runs the task, never derived inside the runtime:
  CicsTask `withStartcode` / `withUserid` / `withScreen` and the stub's `$GGCICS_STARTCODE` / `$GGCICS_USERID` /
  `$GGCICS_FACILITY` / `$GGCICS_SCREEN`. The crucible runner states them from its scheduler and the reference region
  (cics-crucible SPEC 2): `TD` for a task a terminal step starts (typed input, or a pseudo-conversational RETURN
  TRANSID's next input), `SD` / `S` for a START-triggered task by whether its request(s) passed FROM, user `CICSUSER`
  (no security, nobody signs on), FACILITY the task's terminal, screen 24 x 80. Unstated (the equivalence harness's
  one-task scenarios), the option is refused at run time, not guessed.
- **Assumed.** An ASSIGN that raises INVREQ writes none of its data areas, the other options' included (IBM does not
  say; a crucible case never reads one after INVREQ). A START that passes RTRANSID / RTERMID / QUEUE but no FROM is
  `S` (IBM's codes are worded by FROM alone).
- **Refused by name** (`CicsError` / `Unsupported` at translation with the reason; exit 98 /
  UnsupportedOperationException / IllegalStateException at run time): OPID, OPCLASS, OPSECURITY, USERNAME (RACF
  facts; the region has no security); NETNAME (the harness's terminal has no network name); TERMCODE (a device type /
  model code); FCI (its code for a task with no terminal); DEFSCRNHT / DEFSCRNWD / ALTSCRNHT / ALTSCRNWD (only the one
  screen size is modelled); TWALENG, TCTUALENG, CWALENG (the work areas are not modelled); TASKPRIORITY; RETURNPROG;
  PRINSYSID; QNAME; and every other ASSIGN option (BMS, BTS, DPL and partner facts; no corpus program uses them). At
  run time: STARTCODE in a RUN TRANSID child (IBM lists no code for one), and in a terminal task started for several
  START requests (SPEC 4 coalescing) some with FROM and some without (which code it gets is undocumented).
- **Reached.** cics-crucible gt-assign-startcode (3: a terminal task, STARTs with and without FROM, a terminal START,
  a pseudo-conversational next task, an unhandled INVREQ abending AEIP), cobol-stub and the det port both passing the
  hand-written logs (crucible branch `cases/assign-4270`, not yet released or pinned).

### X20. SEND TEXT: TERMINAL, the default disposition — MATCHED, REFUSED where the region cannot decide (#4270 slice 4)
- **What IBM documents** (CICS TS 6.x, EXEC CICS SEND TEXT, https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-send-text;
  Output disposition options: TERMINAL, SET, and PAGING,
  https://www.ibm.com/docs/en/cics-ts/6.x?topic=command-output-disposition-options-terminal-set-paging). TERMINAL
  "specifies that data is to be sent to the terminal that originated the transaction"; "The disposition option TERMINAL
  sends the output to the principal facility of your task"; "TERMINAL is the default value that you get if you do not
  specify another disposition"; "TERMINAL is the only disposition available in minimum and standard BMS".
- **Modelled.** TERMINAL is accepted with no code of its own (det.cics.OPTIONS says why; the stub's GGCSTXT call is
  unchanged): SEND TEXT TERMINAL sends what SEND TEXT sends, to the same place, and records the same SEND-TEXT event.
  cics-crucible SPEC 6.2 now says so (additive: the event's options are a sorted subset of ERASE FREEKB ALARM CURSOR
  WAIT LAST, and TERMINAL is never one). WAIT, FREEKB and ERASE are recorded as before.
- **Avoided.** SEND TEXT in a task with no principal facility (the SEND TEXT page lists no condition for it): the
  crucible case's started task tests for a terminal with ASSIGN FACILITY first, as SEQPNT / ASYNCPNT do.
- **Refused by name** (`CicsError` in the det port and `Unsupported` in the stub, both with the reason of the CICS command spec's SEND TEXT entry, `gitgalaxy/standards/cics`):
  ACCUM, PAGING, SET, REQID, HEADER, TRAILER, JUSTIFY, JUSFIRST, JUSLAST (a BMS logical message, completed by SEND
  PAGE, or the pages returned to the program, is not modelled); NLEOM, FORMFEED, HONEOM, L40, L64, L80 (printer
  formatting; the region's terminal is a 3270 display); LDC, OUTPARTN, ACTPARTN (partitions / logical device codes);
  MSR; FMHPARM; DEFAULT / ALTERNATE (only the one screen size is modelled). In the census only PL/I programs (dsf, a
  burned estate, outside the COBOL det translator) use ACCUM / PAGING / JUSTIFY / L80 / PRINT.
- **Reached.** cics-crucible gt-send-text-terminal (1 scenario: SEND TEXT with and without TERMINAL, a START TERMID
  task sending to the terminal the START named, a task with no terminal sending nothing), cobol-stub and the det port
  both passing the hand-written log (crucible branch `cases/send-text-4270`, not yet released or pinned).

### X21. EIBTASKN, a stated fact of the run — the value DIFFERS from z/OS, both sides MATCHED (#4270)
- **What IBM documents** (CICS TS 6.x, EIB fields including EIBRESP and EIBRESP2,
  https://www.ibm.com/docs/en/cics-ts/6.x?topic=reference-eib-fields): EIBTASKN "Contains the task number assigned to
  the task by CICS. This number appears in trace table entries generated while the task is in control. The format of
  the field is packed decimal. COBOL: PIC S9(7) COMP-3." Which number a task gets depends on the region's history
  (every task attached before it), so no program-level model can derive it.
- **The harness's fact.** EIBTASKN is stated by whoever runs the task, never derived inside a runtime, as the clock is
  (M4) and ASSIGN's facts are (X19). The CICS spec holds it (`gitgalaxy/standards/cics/eib.py`, `EIB_FACTS`); the stub
  gives `$GGCICS_TASKN` (`GGCTASKN`, which both drivers CALL after INITIALIZE DFHEIBLK, then MOVE to EIBTASKN), the
  Java side `CicsTask.withTaskNumber` (the det port's `runTask` stores `task.taskNumber()` into its EIB; the same at
  every LINK / XCTL level). The equivalence harness states, for each task, the scenario's `"taskn"`, else the case's,
  else 0, on both sides. 0 is the value every task had before it was stated (both sides' EIB is INITIALIZEd), and
  the one C12's RANDOM seed assumes.
- **So a proof says:** given the task number the case states, the port does what the COBOL does with it (CBSA's Db2
  programs write it into PROCTRAN's reference and their abend records; GenApp LGICDB01 moves it into a debug header).
  It does NOT say the value is z/OS's: no CICS region gives a task number 0, and a program whose behaviour depends on
  which number it gets (a key built from it colliding, a RANDOM seeded with it) is proven for the stated number only.
- **Refused by name.** A `"taskn"` that is not an integer from 0 to 9,999,999 (the field's PIC S9(7) COMP-3):
  `Unsupported` in the harness, exit 98 in the stub ("EIBTASKN: $GGCICS_TASKN is not a task number"),
  `IllegalArgumentException` in `withTaskNumber`.
- **Not stated yet.** The cics-crucible runner states no task number (its frames carry none; both sides read 0), so
  `proof_blockers.py` still counts `fact: EIBTASKN` for a crucible case's program. EIBRCODE, EIBCPOSN and the other
  EIB fields no command or driver sets stay zero / spaces on both sides and remain fact gaps.
- **Reached.** Every CICS task of every equivalence case (stated 0 unless the case says otherwise). Pinned by
  `tests/cics_crucible/test_cics_runtimes.py` (the stub and CicsTask, stated, unstated and refused) and
  `tests/cobol_mainframe/test_equivalence_cics.py` (the drivers, the scenario / case / default order).

### X22. READ GTEQ / GENERIC — ASSUMED, REFUSED where IBM is silent or the layout decides (#4270)
- **What IBM documents** (CICS TS 6.x, EXEC CICS READ, https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-read):
  GENERIC "specifies that the search key is a generic key whose length is specified in the KEYLENGTH option"; GTEQ
  "specifies that, if the search for a record that has the same key (complete or generic) as that specified in the
  RIDFLD option is unsuccessful, the first record that has a greater key is retrieved"; EQUAL "specifies that the
  search is satisfied only by a record having the same key (complete or generic)". NOTFND RESP2 80: "An attempt to
  retrieve a record based on the search argument provided is unsuccessful." INVREQ RESP2 25: "The KEYLENGTH and
  GENERIC options are specified, and the length specified in the KEYLENGTH option is greater than or equal to the
  length of a full key"; 42: "... less than zero"; 26: KEYLENGTH without GENERIC "does not equal the length defined
  for the data set".
- **Modelled, on both sides.** The search key is RIDFLD's first KEYLENGTH bytes (GENERIC) or the whole key; the record
  read is the first, in key order, whose key starts with it or (GTEQ) is greater; none is NOTFND with RESP2 80 (the
  full-key READ still records 0 until spec PR 6 states IBM's RESP2 for every file command). READ UPDATE holds the
  record found (its own key). The stub: `GGCREAD` with GG-FLAGS `GTEQ` / `GENERIC` (`read_search`); the det port:
  `CicsTask.readSearch` over `DetCics.Store.search`.
- **ASSUMED.** RIDFLD is left as the program set it: IBM documents RIDFLD being set to the record's key for READNEXT /
  READPREV, not for READ (GenApp LGICVS01 MOVEs the found key itself). Key order is the browse's (D1: the stub's byte
  order, the det port's cp037 order); keys mixing letters and digits in one position would order differently.
- **Refused by name.** GTEQ with EQUAL and GENERIC without KEYLENGTH (the spec's option rules; both sides); a GENERIC
  KEYLENGTH not shorter than the key (INVREQ 25) or not above zero (42; zero is undocumented): the translator when it
  is a known constant, the stub at run time ("READ GENERIC KEYLENGTH ..."); a KEYLENGTH the translator cannot read as
  a constant, or a partial one without GENERIC (INVREQ 26, as before); a RIDFLD shorter than the bytes searched (CICS
  would read the storage after it, which GnuCOBOL lays out unlike IBM's compiler, X6).
- **Reached.** GenApp LGICVS01 (READ ... KEYLENGTH(10) GTEQ on KSDSCUST): equivalence case genapp-lgicvs01 -- the
  key on file, the next greater key, none past the end (NOTFND) and a RANDOM key in range, all PROVED. To run that
  terminal transaction the equivalence harness now states, as the cics-crucible runner does, a case's or scenario's
  `"startcode"` (ASSIGN STARTCODE, X19: `$GGCICS_STARTCODE` / `CicsTask.withStartcode`), `"terminal"` (an unformatted
  RECEIVE's input: `terminal.in` / `withTerminalInput`) and `"ts"` (the TS queues the task starts with: the stub's
  queue directory / `withTempStorage`, items in the region's page on the Java side, #4528), and compares READQ-TS and
  RECEIVE events on both sides. Its SEND TEXT FROM(WRITE-MSG-H) LENGTH(24) runs past FROM inside its record: the det
  port now sends those bytes (`DetCics.withinRecord`; past the record, refused as X6) where it cut the text at FROM's
  end. GenApp LGIPVS01's READ GENERIC GTEQ translates; no case runs it yet. No cics-crucible case: its runner models
  no file control yet (its files.cfg is empty), so the READ semantics are pinned by the runtime tests below. Pinned
  by `tests/cobol_mainframe/test_det_translate.py` (`test_read_gteq_*`) and `test_equivalence_cics.py`
  (`test_a_read_gteq_generic_search_is_named_to_the_stub`).

### X23. A COMMAREA of a stated length — ASSUMED, a reference past EIBCALEN REFUSED (#4270)
- **What IBM documents** (CICS TS 6.x, LINK: "COMMAREA(data-area) specifies a communication area that is to be made
  available to the invoked program ... LENGTH(data-value) specifies the length (halfword binary value) in bytes of the
  COMMAREA"; the invoked program's EIBCALEN is that length). A caller may pass fewer bytes than the invoked program's
  DFHCOMMAREA declares, and GenApp's services test for it: `IF EIBCALEN IS LESS THAN WS-REQUIRED-CA-LEN` -> '98', and
  WRITE-ERROR-MESSAGE's `IF EIBCALEN < 91`. What a program sees past EIBCALEN is the caller's storage after the area
  (a local LINK passes its address) or nothing CICS defines -- either way not the program's to read.
- **The harness's model.** A scenario states `"commarea_length": N` (1 to the record's length; never on a scenario
  with no COMMAREA): the caller passed the record's first N bytes and no more. Both sides give the program exactly N:
  the stub's driver hands the program the area GGCAREA chose -- the N bytes at the end of a page before an
  inaccessible one (`commarea.exact`) -- and the Java side states it (`CicsTask` with EIBCALEN N and
  `withExactCommarea()`): the det port's DFHCOMMAREA storage holds those N bytes for the task. The COMMAREA a LINKed
  program leaves is compared over the fields within the N bytes.
- **Refused, both sides; judged up to it.** A reference past EIBCALEN, read or write, stops the stub at that
  statement (the guard page faults: 98, "COMMAREA past EIBCALEN: not modelled") and the det port at the same one
  (`DetCics.PastFrom`, "COMMAREA past EIBCALEN (N bytes): not modelled"). As X6, the task is compared up to it and
  passes only when both sides refused there (the report's `x6` with `assumes: "X23"`); its end state is not compared.
  What z/OS shows there is not claimed.
- **Not covered.** A model port reads its COMMAREA DTO, which holds the whole record: it cannot refuse a reference past
  EIBCALEN, so a scenario that makes one fails against a model port (one side refused). Only the level-1 COMMAREA is
  exact: a LINK's or an XCTL's COMMAREA keeps the existing models (X10, and the stub's copy of an XCTL's LENGTH bytes),
  and a det port LINKing its own DFHCOMMAREA with a LENGTH past N passes what it has (`Cobol.commarea` clamps) where the
  stub stops. A guard page needs POSIX (mmap / mprotect): on Windows the stub refuses a stated length.
- **A failing SQL statement's host variables.** The det port binds a statement's input host variables before
  DetSql decides whether a planned SQL fault fires; the stub's injected fault reads none. A faulted statement whose
  host variables lie past EIBCALEN therefore stops the det port there (X23) and not the stub -- the task fails as
  "not the same refusal", never passes. GenApp LGACDB01 (EIBCALEN 90, its INSERT failing) and LGUCDB01 (under 91, its
  UPDATE failing) would reach `IF EIBCALEN < 91` that way; on z/OS the statement would read the caller's storage past
  the area, so those outcomes stay unreached.
- **Reached.** GenApp's Db2 services: LGACDB01 line 165 ('98', 60 bytes); LGDPDB01 line 143 ('98', 20 bytes) and
  WRITE-ERROR-MESSAGE's `EIBCALEN < 91` (40 bytes, the DELETE failing); LGIPDB01's five '98' returns (40 bytes) and
  `< 91` (the SELECT failing); LGACDB02 `< 91` (60 bytes, the INSERT failing). Each `< 91` task then LINKs LGSTSQ with
  CA-ERROR-MSG and is judged up to X6. Pinned by
  `tests/cobol_mainframe/test_equivalence_cics.py` (the guard page, the driver, the length's checks) and
  `tests/cobol_mainframe/test_det_translate.py` (the det port's cut storage).
### X24. A task started with a channel; the containers it leaves compared — ASSUMED (#4270)
- **What IBM documents** (CICS TS 6.x, "Scope of a channel"; RUN TRANSID CHANNEL: "the name of the channel that is
  to be passed to the child task"; FETCH CHILD CHANNEL: "the channel returned by the child task"; LINK CHANNEL: the
  called program's current channel, "what it puts there, the caller sees"). A service started by RUN TRANSID CHANNEL,
  or LINKed with CHANNEL, finds its input in containers on its current channel and leaves its result there for the
  parent to FETCH, or for the caller.
- **The harness's model.** A scenario states `"channel": {"name", "containers": {NAME: {"text" | "hex",
  "datatype"}}}`: the channel the caller passed (text in the case's data page; BIT unless CHAR, as PUT CONTAINER's
  default). Both sides build it before the program runs and make it the first program's current channel, the only
  one in its scope: the stub's `GGCCHIN` (channel.cfg), and the Java side's `CicsTask.withChannel` (with the new
  `Channel.with`). Unstated, the task has no current channel, as before (GET CONTAINER INVREQ RESP2 4).
- **What is compared.** At the task's end, the containers on that channel -- every one, by name, byte for byte, and
  the channel's name -- as a last CONTAINERS event (the stub's `containers.out`, written by GGCEND; the Java test reads
  `task.currentChannel()`), what the parent or caller sees. Dropped when the task abended (as a LINKed program's
  COMMAREA is) and for a task judged up to a refusal (X6, X23). The data type is not compared: no conversion is
  modelled (X17), so a parent sees the same bytes either way. Other channels the task made die with it and are not
  compared.
- **RUN TRANSID children.** The equivalence harness runs one task: a RUN TRANSID CHILD is compared as the command
  (TRANSID, RESP; `"transactions"` states the region's transaction definitions, else every one is defined), and the
  child is not run. Sound for a parent that never FETCHes it (CSSTATS2): nothing the child does can reach the parent.
  A FETCH CHILD / FETCH ANY is refused by the translator and the stub (X18).
- **A channel program's facade.** The generator gives a channel program `handleLink(XChannelIn)`, which no task
  facade carries yet (#4343): the java-facade side runs such a program through runTask, and its `entries` say so.
- **Reached.** The async credit-card services CRDTCHK, GETADDR, GETNAME, CSSTATUS (which LINKs GETPOL and GETSPND)
  and CSSTATS2 (RUN TRANSID GETP / SPND): their '0001' and other-account branches, and the containers they PUT.
  Pinned by `tests/cobol_mainframe/test_equivalence_cics.py` (the stub's channel in and containers out, the
  comparison, the drop on abend).

### X25. SYNCHRONIZED slack bytes -- 8-byte binary alignment ASSUMED to be IBM's fullword (#4266)

- **The rule the layout model follows.** IBM Enterprise COBOL aligns a SYNCHRONIZED binary item of up to 4 digits on a
  halfword and one of 5 to 18 digits (the 8-byte S9(10)-S9(18) included) on a fullword, COMP-1 / INDEX / pointers on a
  fullword and COMP-2 on a doubleword, counted from the start of the record, which is doubleword-aligned
  (<https://www.ibm.com/docs/en/cobol-zos/6.4?topic=entry-synchronized-clause>). The slack bytes count toward the
  group that holds the item.
- **Between the occurrences of a table** (an OCCURS group that holds SYNC items): the group's size, with the slack inside it,
  is divided by the largest boundary any elementary item in it needs; when the remainder r is not zero, the compiler adds
  m - r slack bytes at the end of each occurrence
  (<https://www.ibm.com/docs/en/cobol-zos/6.4?topic=clause-slack-bytes-within-records>). `record_layout` and
  `_storage_spans` do this. The rule is read from IBM's text; it was not run on z/OS.
- **The assumption.** The 8-byte binary stays on IBM's fullword because z/OS is the target. GnuCOBOL and Micro Focus may
  align an 8-byte binary on a doubleword. If the GnuCOBOL oracle ever compares slack bytes (offsets after such an item,
  or a record's length), the two can differ.
- **Reach today.** No committed case reaches it: no committed oracle case or answer-key layout holds an 8-byte binary
  with SYNC after an off-boundary item. Status: ASSUMED.

## Language Environment

### L1. CEEDAYS — MATCHED where documented, REFUSED otherwise
- **Modelled.** Pictures `YYYY-MM-DD` (and its `/` and `.` forms) only.
- **Refused (exit 98).** A picture inside a longer field (CardDemo's `'YYYYMMDD  '`) and a numeric month outside
  1–12, because IBM documents neither 2508 vs 2517 nor how trailing blanks are read.
- COACTUPC's cursor placement after its date fields is unreached until z/OS settles it.

### L2. CEE3ABD — MATCHED
- `ggabend.c` records `ABEND Unnnn`, and the Java side's CobolAbend gives the same.

### L3. WORKING-STORAGE with no VALUE clause — ASSUMED
- **What.** GnuCOBOL initialises such an alphanumeric item to spaces. On z/OS its first contents follow the LE
  runtime option STORAGE (commonly binary zeros, or whatever the storage held): the program's source does not say.
- **Where it shows.** CBACT01C moves the 10-byte `CODATECN-0UT-DATE` to `OUT-ACCT-REISSUE-DATE`, but COBDATFT (A1)
  writes only its first 8 bytes and `CODATECN-REC` has no VALUE clause. The last 2 bytes of each OUTFILE record's
  reissue date are GnuCOBOL's spaces, and the Java side writes the same.
- **Assumed** to be spaces. A z/OS run with STORAGE(00) would give X'0000' there.

## Assembler routines

### A1. COBDATFT — MATCHED where the source decides, REFUSED otherwise
- **What.** CardDemo's date routine `app/asm/COBDATFT.asm` (S/370 assembler), CALLed by CBACT01C. GnuCOBOL cannot run
  it, so the harness runs a translation of it, instruction for instruction: `tests/equivalence/le/cobdatft.c` for the
  COBOL side and the det runtime's `Cobdatft.java` for the Java side, the same bytes on both.
- **Modelled.** Input type `'2'` (YYYY-MM-DD) to output type `'2'` (YYYYMMDD): `COOUTDT(4) = COINPDT(4)`,
  `COOUTDT+4(2) = COINPDT+5(2)`, `COOUTDT+6(2) = COINPDT+8(2)`; every other byte is left as it was (see L3); R15 = 0.
- **Refused (exit 98).** Input type `'1'`: its `CLC COINPDT+4,=C'-'` has no explicit length, so it compares 20
  bytes against a 1-byte literal and whatever the literal pool holds after it. The error path: an `MVC` of 38 bytes
  from a 13-byte literal. What both do depends on the load module, not the source, so no proof rests on them.
  CBACT01C never takes either.

## Db2 (`equivalence_sql.py`, `ggsql.c`, `DetSql`)

### Q1. Db2 for Linux, not z/OS — ASSUMED
- **What.** Both sides run their SQL on Db2 Community Edition (Db2 for LUW). The SQLCODEs these programs meet from Db2 (0, +100,
  -803, -811, -532) are the same codes on z/OS. SQLERRMC tokens come from Db2 itself.
- **Not compared to z/OS.** SQLSTATE subclasses, SQLERRD values beyond the row count, SQLERRP, and the dialect
  differences of other statements.

### Q1a. A binary host variable takes what its bytes hold — MATCHED (#4579)
- **What.** SELECT INTO / FETCH INTO a COMP / COMP-4 / BINARY / COMP-5 host variable gives SQLCODE -304 only for a value
  outside its halfword / fullword / doubleword (Db2 types the host variable by its data type: S9(9) COMP is INTEGER), not
  beyond its PICTURE's digits: 2147483647 into `S9(9) COMP` is assigned. That holds under TRUNC(STD) too; STD limits
  COBOL's own MOVE / arithmetic (C1), not the SQL assignment. ggsql.c `num_store` and DetSql (`Cobol.storeHostChecked`) agree.

### Q2. EXEC SQL keeps RETURN-CODE — ASSUMED
- The precompiled CALL preserves RETURN-CODE around the stub. Whether IBM's DSNHLI call resets it is not documented.

### Q3. The Java side's Db2 unit of work — MATCHED for CICS tasks, DIFFERS for batch
- **CICS.** The equivalence test runs each task's SQL in one Db2 transaction, as CICS's Db2 thread does: committed when
  the task ends, rolled back with the task's recoverable files by SYNCPOINT ROLLBACK or an abend (X3). The transaction
  is the harness's (`equivalence_cics.py`, a `TransactionTemplate` around the task); a deployment must give each task
  the same unit of work. Reached: CBSA XFRFUN's four ROLLBACK paths are proven.
- **Batch.** The generated Db2 repositories autocommit, so a batch program's ROLLBACK is a hole. No proven batch
  scenario reaches one (COBTUPDT has no ROLLBACK path).

### Q4. Unsupported embedded SQL — REFUSED
- **Refused.** WHENEVER, dynamic SQL (PREPARE / EXECUTE / DESCRIBE), CONNECT, CALL, ALLOCATE / ASSOCIATE, SCROLL
  cursors and host-variable arrays stop the precompiler by name, as does an undeclared host variable or a `WHERE
  CURRENT OF` a cursor the program does not declare. A positioned UPDATE / DELETE on a declared cursor runs (Q8).

### Q5. DSNTIAC / DSNTIAR — REFUSED
- **What.** IBM's message formatter is not modelled. COTRTLIC's call to it, on the Db2-error path, is its one
  untranslated statement.
- **Reached.** No scenario reaches it.

### Q6. Date text and DDL from z/OS jobs — ASSUMED
- **Date text.** A DATE column read into a character host variable comes back as `YYYY-MM-DD` on both sides: Db2's
  CLI and IBM's JDBC driver convert dates to ISO text. On z/OS the form is the bind's `DATE` option, else the
  installation default (ISO as IBM ships it). CBSA's bind names none; a site with `DATE(EUR)` or `DATE(USA)` would
  hand CBSA's `YYYY-MM-DD` slicing other text.
- **In SQL text, not ISO.** The harness database's own default is USA: `CHAR(date)` inside a statement gives
  `10/01/2026`. No proven statement formats a date in SQL.
- **Input.** `DD.MM.YYYY` (CBSA's PROCTRAN dates) is accepted on input by both, whatever the option.
- **DDL from a job.** `equivalence_db2.ddl_text` runs a z/OS job's in-stream SQL with the placement and audit clauses
  removed (`IN db.ts`, `USING STOGROUP`, `AUDIT`, `[NOT] VOLATILE CARDINALITY`, `SET CURRENT SQLID`, CREATE
  DATABASE / STOGROUP / TABLESPACE). None changes what a query returns. The bind's `QUALIFIER` is each side's
  current schema.

### Q7. `CCSID EBCDIC` tables — DIFFERS
- **What.** GenApp's DDL creates its tables `CCSID EBCDIC`; Db2 for Linux has no such clause, and the harness
  database is Unicode. A table's text then sorts in Unicode order, not EBCDIC order, so `ORDER BY` on text and text
  ranges (`BETWEEN`, `>`) can differ from z/OS for mixed letters and digits (as D1 for the programs).
- **Reached.** No proven statement orders or ranges on text that mixes letters and digits.

### Q8. Positioned UPDATE / DELETE — MATCHED
- **COBOL side.** The statement runs as written: the CLI names each cursor at OPEN (`SQLSetCursorName`).
- **Java side.** A generated repository has no live cursor, so a `FOR UPDATE` cursor's query also returns each row's
  `RID_BIT` (as `GG_RID`, never assigned to a host variable), and the positioned statement updates `WHERE
  RID_BIT(table) = :ggRid` for the row FETCH last returned; no current row is -508, as Db2 gives.
- `RID_BIT` is Db2 for Linux's; a production target on Db2 for z/OS would use `RID()` or the table's key.

### Q9. More host variables than columns — MATCHED
- GenApp's LGUPDB01 FETCHes six host variables from a five-column cursor (a GenApp defect). Db2 sets SQLWARN3 and
  leaves the sixth as it was; both sides now do the same (the COBOL stub had reported an error, the Java side a
  NULL).

## The Java side

### J1. Files on H2 — ASSUMED
- **What.** The proofs run the generated project's `h2` target: VSAM files become H2 tables read through the entities'
  record codecs, and Db2 repositories run on the real Db2.
- **Not proven.** Another target database (Postgres, Oracle) brings its own collation and type behaviour.

## Method

### M1. The scenarios are ours — limits every claim
- **Sources.** The inputs come from the corpora's data, from `@generate` (records built from each copybook's layout,
  edge values per PICTURE) and from scenarios written by us or by a model reading the COBOL, then strengthened from
  mutation survivors (`tests/tools/strengthen.py`).
- **What a proof covers.** The paths its coverage figure reports, and nothing else. CardDemo, CBSA and GenApp are
  public development estates; a fresh estate is measured through `tests/tools/trial.py`.

### M2. SQL faults — injected since #4173 (the SQLCA ASSUMED)
- **How.** A statement is named by its program and the line of its EXEC SQL in the file it is written in (an INCLUDEd
  member's own line); the det port's DetSql calls carry the same key. A fault plan (`PROGRAM LINE NTH SQLCODE
  SQLSTATE`) makes that execution skip Db2 on both sides (ggsql.c, DetSql) with that SQLCODE and SQLSTATE, and both
  log it; a run is proven only if the same faults fired on both sides. A scenario declares `sql_faults` (by `line`, or
  by `table` and `verb`); `equivalence.py run --sql-faults auto` (the default) adds one task per statement the case's
  tasks executed, its first execution failing: -803 for an INSERT, +100 for a SELECT INTO, -913 for an UPDATE, DELETE,
  OPEN or FETCH. COMMIT, CLOSE and `SET :H = VALUES` get none.
- **Assumed.** The SQLCA a fault leaves is reset's: SQLCODE and SQLSTATE set, SQLERRMC empty (SQLERRML 0), SQLERRD
  zero, no warnings. z/OS sets message tokens (-803's index, -913's resource) a program could DISPLAY. -913 rolls back
  the statement only; -911's unit-of-work rollback is not used. Nothing else changes: no row, no host variable, a
  cursor where it was.
- **Not judged.** A fault task that LINKs to a program the case does not run is judged up to that LINK (X6). One whose
  path reaches a det port's named hole (COTRTLIC's dynamic CALL) is recorded "not judged" and left out of the proof
  and of the coverage figure. A port without DetSql (a model port) cannot take a planned SQL fault: such a task is
  recorded "not judged" (no SQL fault hook), never run unfaulted.
- **Effect.** Coverage of the 17 Db2 cases before and after is in the #4173 PR, e.g. GenApp LGACDB01 6/14 → 8/14
  branches, LGUPDB01 17/38 → 26/38, CBSA DELACC 10/14 → 13/14.

### M3. A LINKed program's COMMAREA — fixed 2026-10-02
- A LINKed program answers through the COMMAREA it leaves in its caller's storage. Until 2026-10-02 the harness
  compared such a program's files and tables but not that COMMAREA, so CBSA's and GenApp's result codes (COMM-SUCCESS,
  CA-RETURN-CODE) went unchecked.
- A case marked `"linked": true` now compares it after every task that does not abend. All 7 earlier LINKed cases
  re-proved with it.

### M4. Clock fields — declared
- **What.** A value the program takes from the system clock (Db2's `CURRENT TIMESTAMP`: GenApp LGUPDB01 sets
  `POLICY.LASTCHANGED` and reads it back into its COMMAREA) cannot be equal across two runs made at different times.
- **The rule.** A case names its clock fields (`"clock_fields"`: table columns, COMMAREA fields or slices of them).
  Such a value is compared as what it is -- a well-formed timestamp the run wrote, within the last day -- not by its
  digits. A value from the seed or the scenario is still compared exactly. Every masked value is counted in the
  report (`clock_masked`).
- This is the first declared difference (#4051) of its kind: narrow, named in the case, and reported where used.

## What would settle most of this

**One session on a z/OS system** with Enterprise COBOL 6.x, LE, CICS TS and Db2 for z/OS, running:

- a binary-truncation and arithmetic-intermediate table (C1, C2, C3, C4);
- a collation probe (D1);
- CEEDAYS with the refused inputs (L1);
- a DSNHLI RETURN-CODE check (Q2);
- one CardDemo transaction's 3270 stream (X2).

Each answer becomes either a model that matches (MATCHED) or a declared difference with a person's approval (#4051).

## Keeping this page true

- **A new model** (a stub, a shim, an LE service) adds its entry here in the same PR, with its status.
- **A refusal or a declared difference** found in the code (`not modelled`, `Unsupported`, `UnsupportedOption`) has
  an entry here.
- **A change of status** (a z/OS run, a new flag) edits the entry and its date. The summary table follows.

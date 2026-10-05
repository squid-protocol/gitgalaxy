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
| C2 | compiler | Arithmetic intermediates: the oracle truncates them (ARITHMETIC-OSVS, IBM's decimal places), the det runtime does not (#4287) | DIFFERS (det runtime) / ASSUMED (oracle) | yes (INTCALC, POSTTRAN …); the difference: not by a proof |
| C3 | compiler | An integer literal truncated to zero keeps no sign | DIFFERS | no |
| C4 | compiler | An unsigned binary taken below zero by ADD/SUBTRACT wraps | DIFFERS | no |
| C5 | compiler | `NUMPROC(MIG)` as Enterprise COBOL 5+ compiles it (NOPFD), `NUMPROC(PFD)` with preferred signs (#4271); `INTDATE(LILIAN)`, `ARITH(EXTEND)`, `TRUNC(OPT)` | MATCHED (NUMPROC) / REFUSED (the rest) | NUMPROC: no |
| C6 | compiler | COMP-1 / COMP-2: IBM hexadecimal floating point, and float-mode evaluation of the whole expression | DIFFERS; the det translator refuses float items (#4271) | no (CBSA, DBB EPSMPMT use them) |
| C7 | compiler | COMP-5 byte order: little-endian vs z/OS big-endian | DIFFERS | read as numbers only |
| C8 | compiler | DISPLAY of signed zoned, binary and packed items | MATCHED | yes |
| C9 | compiler | POINTER is 8 bytes in GnuCOBOL (x86-64), 4 on z/OS | DIFFERS | only NULL, trailing (CBSA) |
| C10 | compiler | INITIALIZE / VALUE ZERO zoned items: unsigned F zone (GnuCOBOL) vs preferred C sign (z/OS) | DIFFERS (tolerated where a case declares it) | yes (CardDemo READACCT ARRYFILE) |
| C11 | compiler | MOVE of an alphanumeric item holding a non-digit to a numeric DISPLAY item (#4049) | DIFFERS (inputs kept out of the cases) | yes (COMEN01C option `1!`) |
| D1 | data | Text order is ASCII (Latin-1), not EBCDIC | DIFFERS | keys: no; comparisons: not audited |
| D2 | data | Hex literals that name EBCDIC characters (`X'40'`) | DIFFERS | no |
| D3 | data | Zoned signs in ASCII data (`{`, `}`, A–R overpunch) | MATCHED | yes |
| F1 | files | Natural FILE STATUS values come from GnuCOBOL's BDB files | ASSUMED | yes (00, 10, 23, 22) |
| F2 | files | Fault FILE STATUS values are injected on both sides | MATCHED | yes |
| F3 | files | RECFM=VB: records compared by content, framed as GnuCOBOL frames them, not as a z/OS RDW | ASSUMED | yes (CardDemo READACCT VBRCFILE) |
| F4 | files | JCL utility steps (SORT, IDCAMS, IEBGENER) are not run | — | — |
| X1 | CICS | Commands, RESP/RESP2 and EIB from IBM's API reference | ASSUMED | yes |
| X2 | CICS | Screens compared as the symbolic map, not the 3270 stream | ASSUMED | yes |
| X3 | CICS | Backout: recoverable files and Db2 undone, RECOVERY(NONE) files kept | MATCHED | yes (CBSA INQACC) |
| X4 | CICS | A task takes no time (ASKTIME = dispatch time) | ASSUMED | yes |
| X5 | CICS | Options and conditions IBM leaves open are refused | REFUSED | — |
| X6 | CICS | WRITEQ with a LENGTH past its FROM item (GenApp LGSTSQ) | REFUSED | — |
| X7 | CICS | ASSIGN INVOKINGPROG / PROGRAM; LINKed programs run in one task | MATCHED | yes (GenApp LGUPDB01) |
| X8 | compiler | A reference modification past its item (no SSRANGE): a storage overlay | not run | no |
| X9 | CICS | Named counters (GET COUNTER) | MATCHED | yes (GenApp LGACDB01) |
| X10 | CICS | A LINK target's COMMAREA bytes past the end of the caller's record | DIFFERS | no |
| X11 | CICS | ASKTIME ABSTIME into a field narrower than S9(15) COMP-3 (GenApp's WS-ABSTIME) | DIFFERS | yes (GenApp error paths, #4173) |
| X12 | CICS | A task with no COMMAREA that MOVEs DFHCOMMAREA anyway | UNDEFINED, masked | yes (DBB EPSCMORT) |
| X13 | CICS | An ESDS browsed by RBA: fixed-length records, a record's RBA its byte offset; RBAs that address no record refused | ASSUMED (REFUSED where IBM is silent) | yes (DBB EPSMLIST) |
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

### C2. Arithmetic intermediates — the oracle ASSUMED, the det runtime DIFFERS (#4287)
- **The oracle.** `cobc -std=ibm` turns on GnuCOBOL's `arithmetic-osvs` (`ibm-strict.conf`), so cobc truncates each
  intermediate result to a number of decimal places (`cob_decimal_align`): IBM's fixed-point rules (Enterprise COBOL
  6.4 Programming Guide, SC27-8714-03, Appendix A, "Fixed-point data and intermediate results": `+ -` the larger of
  d1, d2; `*` d1 + d2; `/` the larger of the operands' difference and dmax, the most decimal places of any operand or
  receiver). DIVIDE's quotient follows `cob_decimal_div` (the dividend shifted 38 digits, truncated). IBM's other
  limit, at most 30 digits for an intermediate under `ARITH(COMPAT)`, GnuCOBOL does not apply: ASSUMED that no
  proven intermediate is that long.
- **The det runtime** computes in exact `BigDecimal` and does not truncate intermediates: `COMPUTE R = A / B * C` with
  A = 1, B = 3, C = 300 and R `PIC 999V99` gives 099.00 on the oracle (and by IBM's rule) and 099.99 on the det port
  (measured 2026-10-03, #4287). No proven scenario reaches such an expression; IBM DBB EPSMPMT's would.
- **Reached.** Every COMPUTE with a division or a multiplication of large items, among them INTCALC's interest
  computation; the det runtime's difference: not by a proof.
- **To settle.** #4287 (model the aligns in the det translator), then a table of division and multiply-then-divide
  cases on z/OS against `tests/equivalence/rounding/RND.cbl`.

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
    guard on both sides that stops an intermediate past 30 digits, after #4287.
  - `INTDATE(LILIAN)` is pinned by IBM (day 1 is 15 October 1582 instead of 1 January 1601), and could be modelled
    by the documented offset of the integer-date functions. Dates before 1601 cannot run on GnuCOBOL and would be
    refused. No case needs it yet.

### C6. Floating point — DIFFERS; the det translator refuses float items (#4271)
- **What z/OS does.** COMP-1 and COMP-2 are IBM hexadecimal floating point (HFP): a short item keeps 6 hexadecimal
  digits, so between 21 and 24 bits of precision against IEEE single's 24. More important, "If any operation in an
  arithmetic expression is computed in floating-point arithmetic, the entire expression is computed as if all
  operands were converted to floating point", and that happens when "a receiver or operand is COMP-1, COMP-2,
  external floating point, or a floating-point literal" or "an exponent contains decimal places". Under ARITH(COMPAT)
  this is long precision unless every item is COMP-1 with no multiplication or exponentiation (6.4 Programming
  Guide, SC27-8714-03, Appendix A, "Floating-point data and intermediate results"; Chapter 3, "Fixed-point contrasted
  with floating-point arithmetic").
- **What the oracle does.** GnuCOBOL stores IEEE binary floats in machine (little-endian) order. It still evaluates the
  expression in decimal: each float is read exactly (`cob_decimal_set_double`), each intermediate is truncated by
  ARITHMETIC-OSVS as fixed point (C2), and the result is stored through a truncation to double and a rounding to float
  (`cob_decimal_get_double`, then `(float)`). The oracle departs from z/OS in the evaluation mode, not only in the
  low-order bits.
- **Measured on IBM DBB EPSMPMT** (the payment `P * (C * (1 + C) ** N) / (((1 + C) ** N) - 1)`, C COMP-1, N
  `9(9)V99 COMP`): GnuCOBOL's payment for a principal of 100,000,000.01 at 5.25% over 30 years is 599,550.79. The same
  expression evaluated in exact arithmetic on the same IEEE C gives 599,550.51, which long HFP (about 16 digits) would
  approach. The other five computed scenarios agree. On z/OS, N's decimal places also make the exponentiation a
  floating-point one (Appendix A), computed by a run-time routine IBM does not specify bit for bit.
- **Decision (2026-10-03, #4271): a declared difference, not an emulation.**
  - HFP add, multiply and divide are architected (z/Architecture Principles of Operation), but four things are not
    documented at the level a proof needs: which conversions the compiler generates between fixed point and HFP
    (rounding or truncation), the exponentiation routine, and the floating-point intrinsic functions.
  - No oracle here runs HFP: GnuCOBOL has none. An HFP Java port could be checked only against captured z/OS outputs
    (#4050), and an IEEE one that copies GnuCOBOL's decimal evaluation would prove agreement with an evaluation IBM
    documents differently.
  - So the det translator refuses a COMP-1 / COMP-2 item by name: each statement that names one is a Hole ("COMP-1
    floating point (IBM hexadecimal on z/OS, oracle_assumptions.md C6)"). Before #4271 it emitted a reference to a
    Field it never declared, and the port did not compile.
  - Model ports are not changed. No proven program uses floats.
- **Waiting on it.**
  - `mortgage-mpmt` (EPSMPMT: both of its COMPUTEs involve its COMP-1 item; KNOWN_UNPROVEN).
  - CBSA's CRECUST, BANKDATA, BNK1CAC, BNK1CRA, BNK1TFN and BNK1UAC.
  - DISPLAY of a float is refused by `ggdisplay.c` too (C8).
- **What would settle it.** A z/OS run of EPSMPMT's scenarios (#4050). With those outputs, an HFP model of the
  runtime could be checked where the oracle cannot.

### C7. COMP-5 byte order — DIFFERS
- **What.** GnuCOBOL stores COMP-5 in the machine's order, little-endian on x86; z/OS is big-endian. COMP, COMP-4
  and BINARY are big-endian on both.
- **Visible only** when a COMP-5 item's bytes are read as bytes: a REDEFINES, a group MOVE, or a record written to a
  file.
- **Reached.** The harness's SQLCA declares its binary fields COMP-5, as IBM's does, and programs read them only as
  numbers. In the corpora, only CardDemo's IMSFUNCS.cpy declares COMP-5.

### C9. POINTER size — DIFFERS
- **What.** A POINTER is 8 bytes in GnuCOBOL on x86-64 and 4 on z/OS (31-bit), so every offset after one differs.
- **Reach.** CBSA passes IMS-era PCB pointers at the end of its COMMAREAs, always NULL. The port carries a POINTER in a
  COMMAREA DTO as NULL only (DetCics.pointerIn / pointerOut stop by name on an address) and refuses a DTO with data
  after a POINTER: the task stops by name when it gets one.
- **Waiting on it.** CBSA's INQACCCU, DELCUS and CREACC pass COMMAREAs with data after a POINTER. They need the COBOL
  side on 4-byte pointers (a 32-bit GnuCOBOL build) before they can be proven.

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
- **In-program comparisons.** `Cobol.compare` is byte order in the data's code page. No audit has counted the
  relational comparisons whose result could change between ASCII and EBCDIC.
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
- SORT, IDCAMS, IEBGENER and DFSORT steps are not run. The COBOL SORT verb is not translated by the det port (a
  hole).

## CICS (`ggcics.c`)

### X1. Commands from IBM's documentation — ASSUMED
- **Source.** Each command's RESP/RESP2, length handling and EIB fields follow the IBM CICS TS for z/OS 6.x API
  reference, cited in the code.
- **Checked against.** The cics-crucible (152 doc-cited cells, v0.2.0). Not checked against a CICS region.

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

### X6. A WRITEQ LENGTH past its FROM item — REFUSED
- **What.** GenApp's LGSTSQ (the error logger every GenApp program LINKs on its error paths) writes
  `LENGTH(WS-RECV-LEN)`, the caller's COMMAREA length + 5. That is more than `FROM(WRITE-MSG)` holds (95 bytes), so
  CICS copies the bytes that follow WRITE-MSG in storage.
- **Why it is not judged.** Those bytes depend on how the compiler lays out WORKING-STORAGE; GnuCOBOL's layout is not
  IBM's, so no oracle here can say what z/OS writes.
- **Refused.** The translated WRITEQ TD / TS checks its LENGTH against the FROM item and stops the run (98,
  "WRITEQ TD LENGTH > FROM: not modelled"); the case is refused by name, never reported as a difference. GenApp's
  error paths (every GenApp program LINKs LGSTSQ on them) stay out of their cases until z/OS settles it.
- **#4173.** An SQL-fault task (M2) that reaches the LINK to LGSTSQ is judged up to and including that LINK -- its
  events and the COMMAREA's bytes as LINKed, byte for byte -- and its end state (tables, files, the final COMMAREA) is
  not compared: LGSTSQ is not run on either side.

### X7. ASSIGN INVOKINGPROG / PROGRAM, and several programs in one task — MATCHED
- ASSIGN PROGRAM is the running program, INVOKINGPROG the program that LINKed or XCTLed to it (blanks for a task's
  first program), as IBM's ASSIGN documents.
- A case's `"programs"` run in the same task on both sides: the COBOL side's dispatcher (as the cics-crucible's) and
  the Java side's `CicsTask.Programs`, each a port. A LINK is compared by its target; what the target did is compared
  through its files, tables, queue writes and the COMMAREA it leaves.

### X8. A reference modification past its item — not run
- **What.** GenApp's LGAPDB01 MOVEs into `WS-VARY-CHAR(1:WS-VARY-LEN)`, the COMMAREA's length less the request's:
  with the 32500 bytes its caller LGAPOL01 passes, about 28K past WS-VARY-CHAR's 3900. Compiled without SSRANGE (IBM's
  default) that overwrites whatever follows in storage; GnuCOBOL's layout is not IBM's.
- **Effect.** The det port stops (an index error), so such a scenario can never be proven by accident; the case leaves
  it out and says so. A COBOL-side check (GnuCOBOL's EC-BOUND-REF-MOD) would turn it into a refusal by name.

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

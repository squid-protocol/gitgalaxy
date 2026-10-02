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
| C2 | compiler | Arithmetic intermediates: exact decimal vs IBM's precision rules | ASSUMED | yes (INTCALC, POSTTRAN …) |
| C3 | compiler | An integer literal truncated to zero keeps no sign | DIFFERS | no |
| C4 | compiler | An unsigned binary taken below zero by ADD/SUBTRACT wraps | DIFFERS | no |
| C5 | compiler | `INTDATE(LILIAN)`, `ARITH(EXTEND)`, `NUMPROC(PFD)`, `TRUNC(OPT)` | REFUSED | — |
| C6 | compiler | COMP-1 / COMP-2: IEEE vs IBM hexadecimal floating point | DIFFERS | no (CBSA uses them) |
| C7 | compiler | COMP-5 byte order: little-endian vs z/OS big-endian | DIFFERS | read as numbers only |
| C8 | compiler | DISPLAY of signed zoned, binary and packed items | MATCHED | yes |
| C9 | compiler | POINTER is 8 bytes in GnuCOBOL (x86-64), 4 on z/OS | DIFFERS | only NULL, trailing (CBSA) |
| D1 | data | Text order is ASCII (Latin-1), not EBCDIC | DIFFERS | keys: no; comparisons: not audited |
| D2 | data | Hex literals that name EBCDIC characters (`X'40'`) | DIFFERS | no |
| D3 | data | Zoned signs in ASCII data (`{`, `}`, A–R overpunch) | MATCHED | yes |
| F1 | files | Natural FILE STATUS values come from GnuCOBOL's BDB files | ASSUMED | yes (00, 10, 23, 22) |
| F2 | files | Fault FILE STATUS values are injected on both sides | MATCHED | yes |
| F3 | files | Fixed-length records only; RECFM=VB/RDW not exercised | ASSUMED | — |
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
| L1 | LE | CEEDAYS: documented pictures only | MATCHED / REFUSED | yes |
| L2 | LE | CEE3ABD abend codes | MATCHED | yes |
| Q1 | Db2 | Db2 for Linux runs the SQL, not Db2 for z/OS | ASSUMED | yes |
| Q2 | Db2 | EXEC SQL keeps RETURN-CODE | ASSUMED | yes |
| Q3 | Db2 | The Java side commits each statement | DIFFERS | no |
| Q4 | Db2 | WHENEVER, dynamic SQL, positioned UPDATE/DELETE | REFUSED | — |
| Q5 | Db2 | DSNTIAC / DSNTIAR message formatting | REFUSED | no |
| Q6 | Db2 | Date and time text in ISO form; DDL adapted from z/OS jobs | ASSUMED | yes (CBSA, GenApp) |
| Q7 | Db2 | `CCSID EBCDIC` tables hold Unicode text: string order differs | DIFFERS | no |
| Q8 | Db2 | Positioned UPDATE / DELETE: the Java side by row id | MATCHED | yes (GenApp LGUPDB01) |
| Q9 | Db2 | More host variables than columns: SQLWARN3, the rest untouched | MATCHED | yes (GenApp LGUPDB01) |
| J1 | Java | VSAM files on H2, not the target database | ASSUMED | — |
| M1 | method | The scenarios are ours, not production traffic | — | — |
| M2 | method | A Db2 error after a successful statement cannot be injected yet | — | yes (UPDACC 5/6 branches) |
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

### C2. Arithmetic intermediates — ASSUMED
- **What.** GnuCOBOL computes arithmetic in exact decimal, and DIVIDE follows `cob_decimal_div` (the dividend
  shifted 38 digits, truncated). The det runtime does the same in `BigDecimal`. IBM sizes each intermediate result
  by compile-time rules from the operands' digits (`ARITH(COMPAT)`: at most 30 digits). Those rules can truncate an
  intermediate that GnuCOBOL keeps.
- **Reached.** Yes: every COMPUTE with a division or a multiplication of large items, among them INTCALC's interest
  computation.
- **To settle.** Run a table of division and multiply-then-divide cases on z/OS, then compare against
  `tests/equivalence/rounding/RND.cbl`.

### C3. An integer literal truncated to zero — DIFFERS
- **What.** GnuCOBOL folds `MOVE -1000 TO PIC S9(3)` at compile time to +0 (`00{`). Every other truncating MOVE keeps
  the sign (`00}`). The translator matches GnuCOBOL (`gen.literal_moved`).
- **IBM's behaviour** is not measured. No proven program reaches it.

### C4. An unsigned binary below zero — DIFFERS
- **What.** GnuCOBOL wraps `PIC 9(4) COMP`, so 0 − 3 by SUBTRACT is 65533. Its own COMPUTE and MOVE, IBM's
  compilers and the det runtime store the absolute value, 3.
- **Reached.** No case reaches it. `test_det_programs.py` keeps its unsigned item above zero.

### C5. Options GnuCOBOL cannot honour — REFUSED
- **What.** `INTDATE(LILIAN)`, `ARITH(EXTEND)`, `NUMPROC(PFD)` and `TRUNC(OPT)`, from a CBL/PROCESS card or a case's
  `compiler_options`, stop the run (`UnsupportedOption`).
- **Note.** CBSA's build JCL passes `TRUNC(OPT)`, but its programs' PROCESS cards override it with `TRUNC(STD)` (C1).
- `TRUNC(OPT)` is undefined for out-of-range values by IBM's own description, so no oracle could be faithful to it.

### C6. Floating point — DIFFERS
- **What.** COMP-1 and COMP-2 are IEEE binary floating point in GnuCOBOL. On z/OS they are IBM hexadecimal floating
  point by default, so results differ in the low digits.
- **Reach.** The det translator does not lift float items, and DISPLAY of a float is refused (C8). No proven program
  uses floats. CBSA uses them in 6 programs (CRECUST, BANKDATA, BNK1CAC, BNK1CRA, BNK1TFN, BNK1UAC).

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

### F3. Record formats — ASSUMED
- The cases' datasets are fixed-length records. Variable-length records (RECFM=VB, the RDW) are not exercised.

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

## Language Environment

### L1. CEEDAYS — MATCHED where documented, REFUSED otherwise
- **Modelled.** Pictures `YYYY-MM-DD` (and its `/` and `.` forms) only.
- **Refused (exit 98).** A picture inside a longer field (CardDemo's `'YYYYMMDD  '`) and a numeric month outside
  1–12, because IBM documents neither 2508 vs 2517 nor how trailing blanks are read.
- COACTUPC's cursor placement after its date fields is unreached until z/OS settles it.

### L2. CEE3ABD — MATCHED
- `ggabend.c` records `ABEND Unnnn`, and the Java side's CobolAbend gives the same.

## Db2 (`equivalence_sql.py`, `ggsql.c`, `DetSql`)

### Q1. Db2 for Linux, not z/OS — ASSUMED
- **What.** Both sides run their SQL on Db2 Community Edition (Db2 for LUW). The SQLCODEs these programs meet from Db2 (0, +100,
  -803, -811, -532) are the same codes on z/OS. SQLERRMC tokens come from Db2 itself.
- **Not compared to z/OS.** SQLSTATE subclasses, SQLERRD values beyond the row count, SQLERRP, and the dialect
  differences of other statements.

### Q2. EXEC SQL keeps RETURN-CODE — ASSUMED
- The precompiled CALL preserves RETURN-CODE around the stub. Whether IBM's DSNHLI call resets it is not documented.

### Q3. Java commits each statement — DIFFERS
- **What.** The generated Db2 repositories autocommit, so a ROLLBACK is a hole. A CICS backout after a Db2 change would
  show as a difference, never as a proof.
- **Reached.** No proven scenario reaches it.

### Q4. Unsupported embedded SQL — REFUSED
- **Refused.** WHENEVER, PREPARE/EXECUTE (dynamic SQL) and `WHERE CURRENT OF` stop the precompiler by name, as does an
  undeclared host variable.

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

### M2. Db2 errors after a successful statement — not injectable yet
- File statuses and CICS conditions can be injected (F2). A Db2 error cannot: a scenario reaches an SQLCODE only
  through data that makes Db2 return it (+100, -803, -305, -532 ...).
- An error that no data can cause on demand stays uncovered, e.g. UPDACC's UPDATE failing after its SELECT succeeded,
  or DBCRFUN's PROCTRAN INSERT failing (its SYNCPOINT ROLLBACK path).
- **To settle.** An SQL fault plan for both sides (ggsql.c and DetSql), as ggfault.c does for files.

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

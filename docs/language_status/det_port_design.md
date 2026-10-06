---
description: "**Status (2026-10-02): 48 programs are translated with no model and proven.** That is 27 from CardDemo, 8 from"
---
# Deterministic port (det-port): design and the runtime contract

**Status (2026-10-02): 48 programs are translated with no model and proven.** That is 27 from CardDemo, 8 from
CBSA and 13 from GenApp, over 50 equivalence cases; 17 of those cases run embedded SQL on a real Db2. Two cases are
not proven on purpose, each with its reason (`KNOWN_UNPROVEN` in `tests/tools/proof_sweep.py`): COCRDUPC writes
blanks into a `PIC 9(3)` field a typed DTO cannot hold (#4085), and `carddemo-intcalc-generated` depends on
ASCII vs EBCDIC key order (register D1; the same program, CBACT04C, proves on its other case). All 24 CardDemo programs also prove in the structured, typed style. A model has refactored the largest of
them, COACTUPC, one method at a time; every rewrite was proven and kept.

## The method in brief

Porting a COBOL program has three steps. Behaviour is decided once, by the translator. A model may only change how
the code reads, and the proof is the gate.

```
COBOL program ──(1) det_port.py: translate, no model──► Java port, faithful by construction
                                                              │
                                     (2) equivalence harness: GnuCOBOL vs Java, every scenario, faults on
                                                              │  proven
                                                              ▼
                    (3) det_refine.py: the customer's model rewrites one method ──► proven again? keep : revert
                                                              │
                                                              ▼
                                    a person reviews and approves (port_runner review)
```

| step | tool | what it guarantees | measured |
|---|---|---|---|
| translate | `port_runner run --backend det [--style structured] [--typed]` (or `tests/tools/det_port.py run CASE ...` for the equivalence cases) | the same port from the same source every time; an untranslatable statement is a named `Hole`, never a guess | 97.8% of 17,224 statements across six estates ([survey](det_survey.md), 2026-10-02) |
| prove | `tests/tools/equivalence.py run CASE --port DIR --faults all` | equal events (screens, COMMAREAs, XCTL / LINK / RETURN), files and RETURN-CODE against GnuCOBOL, field by field, on every scenario and injected fault | 48 programs proven (50 cases, 2 not proven on purpose) |
| make readable, no model | `--style structured` (B1), `--typed` (B3) | named methods and fields; typed Java fields where every use allows | 24 of 24 proven typed; batch runtime calls −36% |
| make readable, with a model | `port_runner refine --prove-command ...` (or `tests/tools/det_refine.py run CASE --port DIR`) (B2) | each rewrite is proven, else retried once, else reverted: the port is proven after every step | COACTUPC 109 of 109 methods kept, runtime calls −63% |

**What "proven" means here.** The port and the COBOL agree on every scenario the case defines, and on its injected
faults. It is not a proof for all inputs: coverage is reported per case (COACTUPC: 89 of 95 paragraphs, 310 of 397
branches, from 256 before generated per-field scenarios; the rest sit mostly behind CEEDAYS, below). The oracle is GnuCOBOL in IBM mode, not an IBM compiler. Where the two are known to differ, the
difference is declared below; every oracle assumption, with its status, is in [oracle_assumptions.md](oracle_assumptions.md).

**Why this order.** When a model writes the whole port, the proof has to catch its mistakes in behaviour as well
as in style. Here a model never decides behaviour. The translator fixes it, and the model's only freedom is
readability, where any change in behaviour fails the proof and is undone. Model-written ports remain possible
([the porting loop](../cobol_to_java_porting_loop.md)); the combined method is the default for a program the
translator takes whole.

## Shape

The translator (Python, `gitgalaxy/tools/cobol_to_java/det/`) turns one COBOL program into one Java service that
runs on the generated project like a model's port (same entry points: `runBatch`, `runTask(CicsTask)`, a CALL
entry), proven by the same harness. It is *faithful by construction*, not idiomatic:

- **Storage is bytes.** WORKING-STORAGE, LINKAGE, each FD record and each symbolic map is a `Storage` (a `byte[]`)
  laid out exactly as COBOL lays it out; its initial image (VALUE clauses) is computed at translation time and
  embedded. A data item is a `Field` over a storage: offset, length, category, digits, scale, sign, picture.
- **Statements call the runtime.** `MOVE A TO B` becomes `Cobol.move(A, B)`; COBOL's rules (truncation, padding,
  justification, numeric de-/editing, sign handling, group moves) live once, in the runtime.
- **Paragraphs are numbered methods.** Each returns the index of the paragraph to run next (fall-through = its
  own index + 1; GO TO = the target; GOBACK / STOP RUN throw). PERFORM / PERFORM THRU run a range through one
  dispatcher, so GO TO and THRU behave as COBOL's control flow does.
- **Boundaries convert.** Where the program meets the generated project -- a file READ / WRITE (entities'
  `fromRecord` / `toRecord`), a CICS command (`CicsTask`), DISPLAY (`Sysout`), an abend (`CobolAbend`) -- the
  translator emits the conversion between storage bytes and the generated classes.
- **Items are declared where they are bound.** Each data item's `Field` is one line,
  `private final Field acctId = Field.zoned(s_ACCOUNT_RECORD, 0, 11, 0, false, false, false);`, in record order after
  its storage (until 2026-10 a declaration list plus `fields0()..fieldsN()` init chunks: two lines per item; merging
  them took 20.7% of the code lines off the 50 cases' ports; the largest constructor, COACTUPC's 1,332 items, is well
  inside the JVM's 64 KB method limit).
- **Only the items the program names get a `Field`.** A `Field` is a view of its storage, built with no side effect,
  so one that nothing in the class names is dead code and is not emitted (`program.drop_unused_fields`). The storage
  keeps every byte -- its VALUE image, its length, every group move, record I/O and REDEFINES -- so the proof sees the
  same bytes. On the 54 cases 10,083 of 17,436 `Field`s were never named (mostly copybook and screen-map items:
  a map's `L` / `F` / `A` / `I` / `O` views, record fields only moved whole); dropping them took 14.0% of the code
  lines off the service files (2026-10). The remaining `Field`s keep their item numbers (`f25_APPL_RESULT`), so the
  numbering shows where unused items were, and the COBOL layout stays in the copybook.
- **Condition-names are named methods.** An 88's test (without subscripts) is emitted once as
  `private boolean isApplAok()`, documented with its lineage (`/** 88 APPL-AOK of APPL-RESULT. */`), and called at each
  use. It is the same expression the use site held, so behaviour does not change; it is a readability rule, not a size
  one (+0.4% code lines on its own: each test was already one expression). `det_parity.py` counts paragraph methods
  only, so these do not count as methods.
- **One initial state.** Every entry point (`runProgram`, `runBatch`, `runTask`, the CALL entry) starts from
  `initialState()`: the storages' VALUE images copied in and, with `--typed`, each typed field's initial value. Until
  2026-10 each entry repeated them (3,538 typed-init lines over 150 entry methods): −2.3% code lines on the default
  output, −4.7% with `--typed`.
- **Holes are explicit.** A statement the translator does not handle becomes
  `throw new Hole("line N: <statement>")`; the measurement counts it as untranslated.

## The runtime contract (`{pkg}.cobolrt`, plain Java 17, no Spring)

Charset: every text conversion takes the record charset (`CobolRecords.charset()` in the generated project; the
equivalence harness runs ISO-8859-1 data under GnuCOBOL `-std=ibm -fsign=EBCDIC`, so a signed zoned digit is
overpunched with `{ A-I` (+0..+9) and `} J-R` (-0..-9) in ASCII).

```java
public final class Storage {
    public final byte[] bytes;
    public Storage(int size);                       // all spaces? no: all zero bytes; the image sets every byte
    public static Storage image(String base64);     // the initial image computed by the translator
}

public final class Field {
    public enum Kind { GROUP, ALPHANUMERIC, ALPHABETIC, NUMERIC_DISPLAY, NUMERIC_PACKED, NUMERIC_BINARY,
                       NUMERIC_EDITED, ALPHANUMERIC_EDITED }
    // factories (offset 0-based in the storage)
    public static Field group(Storage s, int offset, int length);
    public static Field alphanumeric(Storage s, int offset, int length, boolean justifiedRight);
    public static Field alphabetic(Storage s, int offset, int length, boolean justifiedRight);
    public static Field zoned(Storage s, int offset, int digits, int scale, boolean signed,
                              boolean signLeading, boolean signSeparate);   // PIC S9(n)V9(m) DISPLAY
    public static Field packed(Storage s, int offset, int digits, int scale, boolean signed);   // COMP-3
    public static Field binary(Storage s, int offset, int digits, int scale, boolean signed,
                               boolean native_);                           // COMP / COMP-4 / BINARY; COMP-5 native
    public static Field numericEdited(Storage s, int offset, int length, String picture, boolean blankWhenZero);
    public static Field alphanumericEdited(Storage s, int offset, int length, String picture);
    public Field at(int index, int stride);          // a subscript, 1-based: offset + (index - 1) * stride
    public Field ref(int start, Integer length);     // reference modification, 1-based; an ALPHANUMERIC view
    public int length();
}

public final class Cobol {
    // MOVE (IBM Enterprise COBOL Language Reference, MOVE statement; elementary and group moves)
    public static void move(Field from, Field to, Charset cs);
    public static void move(String nonnumericLiteral, Field to, Charset cs);
    public static void move(BigDecimal numericLiteral, Field to, Charset cs);
    public static void moveFigurative(Figurative f, Field to, Charset cs);     // SPACES ZEROS LOW-VALUES HIGH-VALUES QUOTES
    public static void moveAll(String allLiteral, Field to, Charset cs);       // MOVE ALL 'x' TO ...
    // values
    public static BigDecimal num(Field f, Charset cs);          // a numeric item's value (numeric-edited: de-edited)
    public static String text(Field f, Charset cs);             // the item's bytes as text
    // arithmetic results (ADD / SUBTRACT / MULTIPLY / DIVIDE / COMPUTE): `value` exact, then stored
    public static void store(Field to, BigDecimal value, boolean rounded, Charset cs);           // no ON SIZE ERROR: truncated
    public static boolean storeChecked(Field to, BigDecimal value, boolean rounded, Charset cs);  // ON SIZE ERROR: true and `to` unchanged when the value does not fit
    // comparisons: <0, 0, >0 by COBOL's rules (numeric: by value; nonnumeric: shorter padded with spaces, by the
    // charset's collating sequence -- the harness's ASCII; group: nonnumeric)
    public static int compare(Field a, Field b, Charset cs);
    public static int compare(Field a, String nonnumericLiteral, Charset cs);
    public static int compare(Field a, BigDecimal numericLiteral, Charset cs);
    public static int compareFigurative(Field a, Figurative f, Charset cs);
    // class conditions
    public static boolean isNumeric(Field f, Charset cs);
    public static boolean isAlphabetic(Field f, Charset cs);
    public static boolean isAlphabeticUpper(Field f, Charset cs);
    public static boolean isAlphabeticLower(Field f, Charset cs);
    // DISPLAY: the operand's external representation as IBM DISPLAY writes it (tests/equivalence/faults/ggdisplay.c
    // is the model the harness applies to GnuCOBOL: zoned and packed / binary shown as zoned digits, sign
    // overpunched; groups and alphanumerics as their bytes)
    public static String displayText(Field f, Charset cs);
    // STRING / UNSTRING / INSPECT: operands are built with the nested StringPart / Delim / Into / Clause
    public static boolean string(Field into, Field pointerOrNull, Charset cs, StringPart... parts);   // true = OVERFLOW
    //   StringPart.size(Field | String, cs) = DELIMITED BY SIZE; StringPart.delimited(Field | String src, Field | String delim, cs)
    public static boolean unstring(Field src, Field pointerOrNull, Field tallyingOrNull, List<Delim> delims,
                                   Charset cs, Into... intos);                                        // true = OVERFLOW
    //   Delim.of(String | Field, all[, cs]); Into.of(target).delimiterIn(f).countIn(f)
    public static void inspect(Field target, Charset cs, Clause... clauses);
    //   Clause.tally(counter, Mode.CHARACTERS | ALL | LEADING, pattern|null[, cs]); Clause.replace(Mode.CHARACTERS | ALL |
    //   LEADING | FIRST, pattern|null, by[, cs]); Clause.converting(from, to[, cs]); each .before(x) / .after(x) (INITIAL)
    public static void setTruncBinary(boolean on);   // TRUNC(STD) for binary items; default off, see below
    public static boolean swapNumprocPfd(boolean pfd); // NUMPROC(PFD) for a program's run (#4271), see below
}
```

Arithmetic intermediates: exact `BigDecimal`. `cobc -std=ibm` instead truncates them to IBM's fixed-point decimal places
(ARITHMETIC-OSVS), which the runtime does not model yet (#4287, register C2); no proven scenario reaches the
difference. `store` truncates high-order digits beyond the PICTURE and low-order digits beyond the scale (or rounds half
away from zero with ROUNDED).

What GnuCOBOL (`-std=ibm`) does, which the runtime follows (each is a case in `tests/cobol_mainframe/test_cobolrt.py`):

- **Binary items follow the program's TRUNC option** (#4102). Under IBM's default `TRUNC(STD)` a binary item keeps
  only its PICTURE's digits (MOVE 99999 to `S9(4) COMP` stores 9999; ADD past 9999 is a size error); under
  `TRUNC(BIN)` it holds anything its bytes hold (99999 wraps to X'869F'). The translator reads the option from the
  program's CBL / PROCESS cards and the case's compile options, else IBM's default STD (`det/program.py`
  `trunc_std`), and each entry point runs with it (`Cobol.swapTruncBinary`, restored on return, so a LINK into a
  program compiled otherwise keeps the caller's). The harness compiles the COBOL side to match: `TRUNC(STD)` is
  `cobc -fbinary-truncate`, `TRUNC(BIN)` is `-fnotrunc` (`equivalence_common.py`; register C1, MATCHED).
- **Zoned and packed signs follow the program's NUMPROC option** (#4271). Each entry point runs with it too
  (`Cobol.swapNumprocPfd`; `det/program.py` `numproc_pfd`). IBM's default NOPFD reads any sign; MIG compiles as NOPFD
  under Enterprise COBOL 5 and later. Under PFD the runtime reads a zoned or packed value only with a preferred sign
  (C / D signed, F unsigned, never D on zero) and stops by name on any other, because IBM leaves that to the generated
  code (register C5).
- **COMP-1 / COMP-2 are refused** (#4271): a statement that names a float item is a Hole. z/OS evaluates such an
  expression in hexadecimal floating point, which no oracle here runs (register C6).
- **COMP-5 is native little-endian**; COMP / COMP-4 / BINARY are big-endian; 1-4 digits 2 bytes, 5-9 4, 10-18 8.
- A MOVE keeps the sending sign through truncation (a `-0.05` into `S9(3)` is X"30307D", negative zero).
- `MOVE SPACES` to a numeric or numeric-edited item does not compile (cobc error); the runtime fills it with spaces.
- `MOVE ALL "12"` to `PIC 9(5)` gives 21212 (the pattern ends at the right edge).
- `INSPECT ... TALLYING ... REPLACING ...` runs as two passes (tallying does not take characters from replacing).
- `UNSTRING` without DELIMITED BY cuts by the receivers' sizes; an alphanumeric item compared with a numeric
  literal is compared as text with the literal's digits.

## Proof of the runtime

Every construct is checked against GnuCOBOL (`gitgalaxy-gnucobol:3`, `cobc -x -std=ibm -fsign=EBCDIC`): a COBOL
test program performs the construct and DISPLAYs or WRITEs the bytes; the same construct through the runtime must
give the same bytes.

## Results (CardDemo, the 23 programs with model-written proven ports)

This table is the first comparison, on the programs that also have model-written ports. Every case is re-proven
with `det_port.py run --all-cases`, or with every model port as well by `proof_sweep.py`.

`python tests/tools/det_port.py run --all-proven --work DIR` translates each program onto its generated service and
proves the result with the same harness as the model-written ports (every case's scenarios and fault runs).

| | programs | statements | translated | holes | proven |
|---|---|---|---|---|---|
| batch (runBatch) | 7 | 1,355 | 1,355 | 0 | 7 |
| CALL (handleCall) | 1 | 27 | 27 | 0 | 1 |
| CICS (runTask) | 15 | 3,024 | 3,024 | 0 | 15 |
| CICS: COACTUPC (no model-written port: too large for one) | 1 | 1,415 | 1,415 | 0 | 1 |
| **all** | **24** | **5,821** | **5,821** | **0** | **24** |

COACTUPC, the 4,200-line account update a model could not port in one pass, is proven on all 54 of its scenarios.

No model is involved anywhere: the port is a function of the COBOL source and the generated project.

### Structural parity: a warning before the proof

Each translated program is also measured by GitGalaxy's own single-file extraction (`tests/tools/det_parity.py`):
COBOL paragraphs and branch points against the port's methods and branch points. On the 49 programs ported across
CardDemo, CBSA and GenApp (2026-10-02) the port keeps a fixed overhead plus a slope, by kind (Theil-Sen fits):

| | batch | CICS | proven ports, port / prediction | warning band |
|---|---|---|---|---|
| methods | 11.4 + 1.12 × paragraphs | 20.8 + 1.13 × paragraphs | 0.88 .. 1.21 | outside 0.6 .. 1.6 |
| branch points | 12.6 + 1.30 × branches | 51.8 + 2.33 × branches | 0.73 .. 1.58 | outside 0.5 .. 2.5 |

The fixed overhead is why a small program reads as a huge ratio of raw counts (ABNDPROC: 1 branch in COBOL, 47 in
Java): response checks, abend paths and storage setup every port carries. Against the fit it sits at ×0.87.

The branch row was refit when Java's `branch` rule stopped counting a `?` or `:` inside a string literal and a
ternary twice (branch_rule_contract.md, "Literals"; issue #4170). Same 49 programs, same Theil-Sen method: the
det ports' median branch count fell from 159 to 127, CICS's overhead from 70.8 to 51.8 and its slope from 2.77 to
2.33, batch's from 15.0 + 1.62 to 12.6 + 1.30. The methods row did not move.
None of the 49 warns. A warning (`det_port.py run` and `check` print it; `summary.json` / `check.json` carry
`parity_warnings`) says a translation dropped or duplicated paragraphs or expanded a construct far beyond the
estate's norm. It is a place to look, never a failed proof or an exit code. When the emitter's shape moves on
purpose (a readability layer), refit `MODEL` in `det_parity.py` from a fresh `run --all-cases --translate-only`.

### Where the boundary comes from

Only generator output, never a test case:

- **Batch files.** The stub's per-file methods ("... as BATCH SELECT <name>") name the repository; the FD record and
  RECORD KEY come from the source. A program no generated job runs (CBTRN01C) is bound by the estate: the DD's
  dataset in the job configs, that dataset's repository in the other stubs -- written into the port's header as
  *Inferred*. A file the program only OPENs and CLOSEs with no store bound (CBTRN01C's TRANSACT-FILE) is `Unbound`:
  its statuses are exact, a record operation would be a Hole.
- **CICS files.** "... as CICS file <NAME>" over the repository method; `findBy<Property>` marks an alternate index
  (its key offset from the entity's field comment). A file the program's own stub does not map (COUSR01C only WRITEs
  USRSEC) takes the repository every other stub binds that name to -- *Inferred* in the header.
- **COMMAREA.** The contract DTOs' property comments (COBOL name, PICTURE, offset; composite parts with their offsets)
  give each DTO's byte codec; XCTL targets travel as the stub's `xctl<Program>(Type)` type.
- **Screens.** `fromValues` / `screenValues` by BMS field name; the symbolic map's `<f>O`, `<f>I`, `<f>L`, `<f>A`/`F`,
  `<f>C`, `<f>H` items from the program's own copybook. A MAP named by a data item is a constant (VALUE, never
  written) or fixed by its FROM / INTO record, checked at run time (a different name is a Hole, never a wrong screen).
- **Library routines.** CEEDAYS is the twin of the harness's own model (tests/equivalence/le/ceedays.c), refusing
  what that model refuses.

### Declared differences (not covered by the proofs)

- Indexed files are read in the key's EBCDIC (cp037) order, as the generator orders them; the harness's files are in
  ASCII order (equivalence.py COLLATION). CardDemo's keys sort the same either way; keys mixing letters and digits
  would not.
- Indexed records are found by scanning the repository (`findAll`) and comparing key bytes: exact for any key
  (alternate ones included), slow for large files. A production port would use the generated finders.
- An integer literal (no decimal point) MOVEd to a zoned item with no decimal places, truncated to zero: GnuCOBOL
  folds it at compile time to +0 (`MOVE -1000 TO S9(3)` is `00{`), while every other truncating MOVE keeps the sign
  (`-1000.0`, `-0.05`, a scaled or COMP-3 target, a field sender: `00}`). The translator matches GnuCOBOL
  (`gen.literal_moved`; probed in `NEGZERO`); IBM's behaviour is not measured. No proven program reaches it.
- **Library models that stop rather than guess.** The harness's CEEDAYS model (`tests/equivalence/le/ceedays.c`)
  does not model a picture in a longer field. CardDemo's CSUTLDTC passes `'YYYYMMDD  '` in 10 bytes, and IBM does
  not document how the trailing blanks are read. A scenario that reaches such a call is now refused by name ("not
  modelled") rather than reported as a difference. COACTUPC's cursor placement for the 34 fields after its dates
  needs a valid date, so it is unreached until IBM's behaviour is measured.
- An unsigned binary item taken below zero by ADD / SUBTRACT: GnuCOBOL (`-std=ibm`) wraps it (`PIC 9(4) COMP`, 0 - 3
  is 65533) while its own COMPUTE and MOVE, IBM's compilers and this runtime store the absolute value (3). No case
  reaches it; test_det_programs.py keeps its unsigned item above zero.

### What the proofs found in the translator and runtime

- A numeric literal MOVEd to a group carried an overpunched sign (`23` -> `2C`): a literal without a sign is unsigned.
- `A NOT = B AND C` lost the NOT on `C`; a data-name object (`EIBAID NOT = DFHENTER AND DFHPF7`) was read as a
  condition-name.
- A numeric DISPLAY item MOVEd to an alphanumeric one is its digit bytes as they are -- invalid data included, the
  sign de-punched (GnuCOBOL, checked): the runtime had decoded `ABC` as `123`.
- DIVIDE's intermediate follows GnuCOBOL's cob_decimal_div (the dividend shifted 38 digits, truncated).
- #4501 (found proving #4413 through cics-crucible): a COMP-5 VALUE was written truncated to its PICTURE and
  big-endian while the runtime reads COMP-5 little-endian, so CAXA's `S9(4) COMP-5 VALUE 32767` reached XCTL LENGTH
  as -12534. The image now holds the whole value in the runtime's order (register C7).
- #4271 slice 1: COMP-1 / COMP-2 are IBM hexadecimal floating point in the runtime (`Hfp`, `Field.hfp`); the
  translator picks each statement's floating-point mode by IBM's rule and refuses a float's bytes by name (register
  C6). Writing the oracle test found GnuCOBOL 3.1.2 dropping terms of float expressions with a multiplication or a
  parenthesised division, and misjudging a comparison of a float expression: the oracle decides floats only on
  simple statements.
- PERFORM: when control falls off a paragraph, the innermost active PERFORM whose range ends there returns,
  abandoning those inside it. COACTUPC GOes TO the end of its caller's range from inside a nested PERFORM; the port
  looped where COBOL returned (GOTOOUT in test_det_programs.py).
- FUNCTION TRIM of an all-space argument is zero-length, and TRIM removes spaces only (COACTUPC's alphabetic-field
  check); SYNCPOINT ROLLBACK was emitted as a SYNCPOINT.
- The harness itself: `equivalence_cics.alphanumeric` read the 9 of `PIC X(09)` as a digit position, so COACTUPC's
  ACUP-OLD-CUST-SSN-X `017590544` reached the Java side as 17590544 -- another record than COBOL's. Fixed; the 15
  model-written CICS ports re-prove with the fix.
- #4213: the translator dropped RBA (and XRBA / RRN) from a browse and browsed by key: IBM DBB EPSMLIST's
  `STARTBR ... RIDFLD(RID-LENGTH) RBA` "translated" 51/51 into a keyed browse of a store the project does not have.
  An ESDS browse by RBA is now CicsTask's RBA browse (`startbrRba` / `readnextRba` / `readprevRba`, register X13);
  XRBA, RRN and READ / WRITE / DELETE by RBA are holes by name.
- #4467 (interim for #4459-#4461, found by the #4273 cross-check): the translator resolves COPY by a first-hit
  directory search of its own. A program whose own COPY resolves otherwise than the engine resolved it (the port
  ticket's copybooks, or GalaxyIR's copy_deps), whose member the engine reports as a collision or (in the estate) a
  gap, or which leaves unexpanded a member the engine resolved, is refused by name (`source.CopyDisagrees`). No
  equivalence case moves; on the corpora at a1ec00d84 it newly refuses zopeneditor-sample SAM1 / SAM2 and 19 of
  estate-crucible's 40 programs (9 collisions, 6 COPYs not expanded, 4 other files).
- #4468 (the real fix after #4467; the engine owns COPY resolution, `fact_ownership.md`): the translator no longer
  searches directories for an estate member. Every COPY in an estate file (the program's own and its copybooks')
  takes the file the engine resolved (`GalaxyIR.copy_resolution`: copy_deps and their library-names per importer,
  SYSLIB order, `COPY ... IN`), read from the port ticket (the skeleton's `copy_edges`) or GalaxyIR, so the two
  resolutions cannot diverge and `CopyDisagrees` is gone. Refused by name (`source.CopyUnresolved`): a member the
  engine reports as a collision or a gap, one it resolved to several files, one it resolved nothing for that the
  estate holds (#4460), and a member it resolved that the translator never expands (#4459). Members outside the
  estate (DFHAID, SQLCA, BMS symbolic maps) are still found in the translator's own directories. Text expansion
  (REPLACING, continuation) and layout arithmetic are unchanged. Newly translating: estate-crucible ACCTPOST and
  CUSTINQ (the wrong library before); SHPINQ / SHPINQO now refuse on their real defect (COPY SHPRATE: a gap the
  estate fills only with a program source) instead of the library.
- #4486 (owner decision: translate): a SYSLIB collision -- an unqualified COPY whose member sits in more than one
  library of the program's search order -- is no error on z/OS: the compiler takes the first library's member, and
  the engine resolves it the same way. The translator now takes the engine's member and records a warning per
  collision (the member, the library chosen, the other libraries in search order: the skeleton's `copy_collisions`
  rows carry them) in the translation's `stats["warnings"]`, which `port_runner run --backend det` logs and prints
  and `det_port.py` reports. Strict mode refuses every collision by name as before (`program.translate(...,
  strict_copy=True)`, `port_runner --strict-copy`, a case's `"strict_copy": true`). A gap, and a collision whose
  first library holds several files, stay refused in both modes; `COPY x IN lib` is never a collision. Newly
  translating on estate-crucible, each agreeing with the engine on every channel: ORDPRICE, ORDV#OLD, ORDVAL,
  ORDVALV2, ORDVOLD, TAXCALC, TAXCALC2 and PAYMAIN (with its nested PAYCALC and batch-compiled PAYRPT, after the
  layout learned to skip an I-O-CONTROL `APPLY WRITE-ONLY` hint); ORDMAIN now refuses on its real defect, COPY
  ORDPRICE (a gap only a program source fills, H-0053, #4460).
- #4436 (after #4411 refused it): `READ ... INTO LENGTH(x)` was accepted and ignored by the translator, and the
  harness's stub was handed LENGTH OF INTO in its place -- both sides agreed, so GenApp LGUCVS01 / LGUPVS01 "proved"
  without either honouring LENGTH. A keyed READ's LENGTH is now in-out on both sides (`DetCics.readInto`, GGCREAD:
  truncation, LENGERR RESP2 11, the record's length set back; register X14).
- #4413: `SEND CONTROL` and plain terminal `RECEIVE` (INTO / SET(ADDRESS OF) / LENGTH / FLENGTH / MAXLENGTH /
  MAXFLENGTH / NOTRUNCATE) were refused whole. They now run on CicsTask (`sendControl`, `receive`: NOTRUNCATE keeps
  the rest for the task's next RECEIVE; LENGERR; EOC on an LUTYPE2 terminal) and the stub (GGCSCTL, GGCRECT /
  GGCRECS), with EOC's default action -- ignore it -- in the port's `condition()` (`DetCics.ignoredByDefault`;
  register X15). A CICS port of an estate with no screens / contracts / repositories no longer imports those
  packages. Proven through cics-crucible hc-terminal-receive (7) and hc-terminal-eoc (3): the cobol-stub side and
  the det port both pass the hand-written logs.
- #4414 / #4502: `HANDLE AID` (71 PL/I + 5 COBOL programs) and `IGNORE CONDITION` were refused, and `PUSH` / `POP
  HANDLE` with them; `HANDLE CONDITION ERROR(label)` was accepted but never taken -- a condition with no handler of its
  own abended the port where CICS goes to the ERROR label. All now run on the port (`handlers` with -1 for IGNORE,
  `aids`, a `pushed` stack of DetCics.Handlers beside CicsTask's own HANDLE ABEND stack; `condition()` takes the
  condition's HANDLE / IGNORE, then a default of ignore, then ERROR, then the abend; `aid()` after RECEIVE MAP and
  terminal RECEIVE). What IBM does not say is refused by name on both sides (register X16): an AID label beside a
  condition on one input command, a key deactivated under ANYKEY, IGNORE CONDITION ERROR. Proven through
  cics-crucible hc-handle-aid (9), hc-ignore-error (9) and hc-eoc-error (2) on the cobol-stub side and the det port.
- #4270 slice 1: channels and containers were refused whole -- `GET` / `PUT CONTAINER` in 23 census programs (16
  outside the burned estates), `LINK CHANNEL` in 3. `PUT` / `GET` / `DELETE CONTAINER`, `LINK` / `XCTL CHANNEL` and
  `ASSIGN CHANNEL` now run on CicsTask's channels (`putContainer`, `getContainer`, `deleteContainer`, `linkChannel`,
  `xctlChannel`, `assignChannel`) and the stub (GGCPUTC / GGCGETC / GGCDELC / GGCASCH, GG-CHAN), container data
  byte for byte, CONTAINERERR / CHANNELERR / LENGERR / INVREQ with IBM's RESP2 through `condition()` (AEZJ / AEZV by
  default). Code-page conversion, SET, BYTEOFFSET, RETURN CHANNEL, MOVE and the container browse are refused by name
  (register X17). Proven through cics-crucible ca-channel-containers (2) on the cobol-stub side and the det port.
- #4270 slice 2: interval control was refused whole -- START / RETRIEVE / RUN / FETCH in 10 census programs (3 outside
  the burned estates, all RUN / FETCH). `START` (INTERVAL / TIME / AFTER / AT, TERMID, REQID, PROTECT, FROM / LENGTH,
  RTRANSID / RTERMID / QUEUE), `RETRIEVE` (INTO / LENGTH, the data options), `CANCEL REQID` and `RUN TRANSID CHILD` now
  run on CicsTask (`startRequest`, `retrieve`, `cancel`, `runTransid`) and the stub (GGCSTRT / GGCRTRV / GGCCNCL /
  GGCRUNT), with INVREQ RESP2 4 / 5 / 6, IOERR, ENDDATA and ENVDEFERR through `condition()`; the det port sets EIBTRMID.
  FETCH, RUN / START CHANNEL and RETRIEVE SET / WAIT are refused by name (register X18). Proven through cics-crucible
  gt-start-retrieve (6), gt-terminal-coalesce (4) and gt-start-options (7) on the cobol-stub side and the det port.
- #4270 slice 3: ASSIGN refused every option but APPLID / SYSID / ABCODE / PROGRAM / INVOKINGPROG / CHANNEL. The census
  (131 CICS programs) uses APPLID (27 programs), PROGRAM (23), ABCODE (6), SYSID (4), STARTCODE (4, 2 outside the
  burned estates), INVOKINGPROG (3), CHANNEL (2) and USERID (1, outside). `STARTCODE`, `USERID`, `FACILITY`, `SCRNHT`
  and `SCRNWD` now run on CicsTask (`assignStartcode`, `assignUserid`, `assignTerminalResp`, `assignFacility`,
  `assignScreen`) and the stub (GGCASGN), from facts the harness states, with INVREQ RESP2 5 for a task with no terminal
  through `condition()`. The other options are refused with a reason (register X19). Proven through cics-crucible
  gt-assign-startcode (3) on the cobol-stub side and the det port.
- #4463: four det ports stopped proving on 2026-10-04 and no CI ran the det sweep. carddemo-menu: a #4049 scenario
  sent option 99, which COMEN01C still uses as a subscript of its 12-entry table, 4K past the record (X8: the det
  port stops; the case now sends 12). mortgage-cmort / mlist / nbrvl: #4245 read every program of EPSCSMRD's
  multi-program source, and its field CASE became the Java field `case` (the generator's keyword list was partial).
  `.github/workflows/det-sweep.yml` now runs the sweep (no Db2) on translator / harness / case changes and nightly.
- #4462 (found by the #4273 cross-check): what the translator reads before it parses, decided per cause.
  *Code pages* are modelled: the program and each member are decoded with the code page the estate declares for that
  file, the one the engine decoded it with (`--source-encoding`; `GalaxyIR.copy_pages`, the skeleton's and port
  ticket's `copy_pages`, `source.EngineCopies.pages`), so a raw EBCDIC source (cp037, cp273, cp277 ...) is read as
  the scan read it (it was a cp1252 guess with no IDENTIFICATION DIVISION in it), and a COPY member's name may hold
  national letters (`COPY 'KUNDEÅ'`). *Free format* is modelled: after `>>SOURCE FORMAT FREE` (until `... FIXED`)
  a line is code from column 1, of any length, up to a `*>` comment. *Refused by name* (`source.unmodelled`, a
  LayoutError / ExprError naming the file, line and character): national / DBCS text, any character beyond Latin-1
  in a name or a literal (estate-crucible KYUY: Kanji names, PIC G, ideographic spaces; KYUYJP had raised
  UnicodeEncodeError), because the translator lays records out and hands the grammar its text one byte a character;
  a national letter in a name (`BETRÄGE`: the grammar reads ASCII words only); DECIMAL-POINT IS COMMA (`1000,00`,
  `0,5` must never be read as integers). A national letter inside a literal or a comment is read. Still refused, with
  a cause in the cross-check ledger: several programs in one source (PAYMAIN), IDMS (LNIDMS01), and the grammar gaps
  the ledger lists (`translator-refuses-grammar`). `PROGRAM-ID LNCALC.` without its period is read since #4523
  (`source.logical_lines` puts the period back, as Enterprise COBOL tolerates it). DECIMAL-POINT IS COMMA stays
  refused: it needs a comma-aware numeric tokenizer in the statement grammar (`MOVE 0,5 TO X` against `A, B`), the
  layout's VALUE parsing and edited PICTUREs with `.` and `,` swapped, and the runtime's edited moves and DISPLAY;
  its one program (estate-crucible ZINSBER) would still be refused for its national-letter name `BETRÄGE`.
- #4523: the grammar continues a literal only in quotation marks (`'...` at column 72 with `-    '...` on the next
  row did not parse), and reads `""` inside one as two literals (`VALUE "IT""S"` was two values, `MOVE "IT""S"` did
  not parse), though it reads `'IT''S'` whole. `source.as_fixed_rows` now hands the grammar every literal of a
  re-wrapped line in quotation marks (same value: `''` undoubled) and every `""` as U+001E (`QQ`), which `unwrap`
  turns back into `""`; a source holding U+001E is refused by name. An EXEC block's lines keep their own text (in
  SQL an apostrophe is a string, a quotation mark a name; the grammar never reads them). When column 72 of a
  re-wrapped row would split a doubled quote, the row ends a column early. Newly translating: CardDemo CBSTM03A, DSF
  FO04F1X1, estate-crucible RPTHDR and LNCALC; CBSTM03A's cross-check found the engine's group USAGE gap (#4525).
- #4462 slice 2. *Hex literals*: the grammar continues no `X'...'` (in either quote style), so a re-wrapped line's
  hex literal is handed to it as an alphanumeric literal `"<U+001F>C1C2..."`, which it continues; `unwrap` restores
  `X"C1C2..."` (a source holding U+001F is refused by name). A lower-case `x'00'` is handed over as `X'00'` (GenApp
  lgtestc1). *IDMS* is refused by name, "IDMS DML not supported" (an IDMS-CONTROL or SCHEMA SECTION: estate-crucible
  LNIDMS01); modelling its DML and subschema records is #4532. *Multi-program sources* are modelled as units:
  `source.program_units` cuts an expanded source into its programs (a program beginning while another is open is
  nested in it; END PROGRAM closes the innermost and must name it), each with its own lines; `layout.parse` and
  `stmt.parse` refuse a source holding several by name (before, they silently read the first program's records and
  paragraphs), and `program.translate(..., unit=)` translates one program (default: the first) as its own class. A
  nested program whose container declares GLOBAL items is refused (`UnitRefused`): its view of them is not modelled.
  The cross-check reads every unit, each paragraph's extent ending with its program. estate-crucible PAYMAIN, refused
  first by its COPY DATEWS collision until #4486, now translates. *Grammar gaps*: `ENTRY 'DLITCBL' USING pcb ...` (IMS DL/I batch)
  is read as a statement (a placeholder CALL, as SORT); as the program's first statement with no PROCEDURE DIVISION
  USING it is the program's entry, its USING the program's parameters; elsewhere it translates as a hole. A reference
  modification of an intrinsic function (`FUNCTION CURRENT-DATE (1:4)`, `FUNCTION UPPER-CASE(A) (2:3)`) is handed to
  the grammar as an argument list of the same length; expr reads it as the reference modification, and gen takes the
  substring of an alphanumeric function's text (it had dropped the modification). Newly read: CardDemo DBUNLDGS,
  PAUDBLOD, PAUDBUNL, CBIMPORT; GenApp lgtestc1; estate-crucible KØBREG. Still refused: SEARCH ALL's WHEN (CardDemo
  COPAUS1C), DSF's `IDIOT IS 'ABC...'` alphabet without ALPHABET (PLUKKFR, PLUKKFRN), `LABEL RECORD ARE` (FO04D1X1),
  OS/VS `EXHIBIT NAMED` (R001BYDL), and GenApp polloo2.cpy's missing period after `03 CA-CUSPOL-REQUEST` (a source
  defect).
- #4462 slice 3. *SEARCH / SEARCH ALL*: an OCCURS item keeps its ASCENDING / DESCENDING KEYs and INDEXED BY names
  (`Item.keys`, `Item.indexed_by`); each index name is an item of its own holding the occurrence number (initially
  1, as GnuCOBOL; IBM leaves it undefined). The statement builder opens a SEARCH frame for its AT END and WHENs (a
  SEARCH ALL takes one WHEN; the next belongs to the EVALUATE around it); END-SEARCH or the period closes it. A serial
  SEARCH walks the table from the index's value; SEARCH ALL is a binary search whose WHEN must be `key = value` (or
  a key's condition-name) for the leading keys, subscripted by the first index, joined by AND (else a hole by name),
  stepping on the first unequal key in KEY order -- GnuCOBOL's loop (head 0, tail size + 1, index (head + tail) / 2).
  SEARCH VARYING a counter or another table's index is refused by name: IBM steps it with the index, GnuCOBOL sets
  it to the index's value. *OS/VS forms*: an alphabet clause without ALPHABET (`IDIOT IS 'ABC...ÆØÅ'`) gets the
  keyword (`source.alphabet_keywords`) for the grammar and for `program.alphabets`, the model SORT and comparisons
  read; `LABEL RECORD ARE` / `LABEL RECORDS IS` drop the optional word (`source.label_records`); `EXHIBIT NAMED a
  'lit' b` is one DISPLAY line `A = value lit B = value` (GnuCOBOL's spelling) for plain names and nonnumeric
  literals, a qualified or subscripted name and EXHIBIT CHANGED (GnuCOBOL does not implement it) are holes by name.
  *Source defects*: a data entry with no period before the next level number is refused by name ("source defect",
  GenApp polloo2.cpy). Newly read: CardDemo COPAUS1C, DSF PLUKKFR, PLUKKFRN, FO04D1X1, R001BYDL; the cross-check
  ledger's `translator-refuses-grammar` cause is empty and gone.
- #4528: a TS item is the bytes the program wrote "in the region's code page" (CicsTask), and the COBOL side's
  region keeps it in CCSID 037 (cics-crucible SPEC 2; the stub transcodes its Latin-1 storage at the boundary). The
  det port handed CicsTask its storage's bytes (CS, CobolRecords.charset()) as they were: WS-ONE VALUE 'W' reached
  the queue as X'57' ('ï'), an item 'A' came back as 'Á'. WRITEQ / READQ TS now move each byte between CS and
  `REGION` (`DetCics.toRegion` / `fromRegion`): the estate's declared code page for the program when it is EBCDIC
  (`EngineCopies.page`, #4462), else CCSID 037; the system property `gitgalaxy.cics.charset` names another. NL is
  NEL (X'15') and LF X'25' as in CDRA and Python's cp037, not the JDK's LF for both; a byte one page cannot carry
  stops the run by name. TD (`Cobol.text(.., CS)`), SEND TEXT, terminal RECEIVE and the COMMAREA DTO codecs already
  went through characters. `Cics.declared` reads a DTO's copybook in its declared page too (it read Latin-1).
  Newly passing on the det port (cics-crucible): hc-perform-range 4/4 (`length-trap` byte for byte), hc-abend-link
  push-pop, pushed-abend, sub-own-exit, sub-resp, ca-link-lengths no-commarea.

### Keyed reads

A base cluster's keyed READ / WRITE / REWRITE / DELETE goes through the repository's `findById`, the id decoded
from the key bytes by `det/entity.py` from the entity's `@Id` / `@EmbeddedId` comments; the record found must have
exactly the key bytes asked for (a loosely decoded key -- non-digits in a numeric key -- finds nothing, as VSAM).
Alternate indexes and browses keep the ordered scan, as does an id whose comment's PICTURE and USAGE do not give the
byte count it states.

## Beyond CardDemo (A5)

Equivalence cases for programs of two more estates, the COBOL run by GnuCOBOL as the oracle
(`tests/equivalence/genapp-*`, `tests/equivalence/cbsa-*`). These are the first seven, all VSAM / CICS; the 14 CBSA and GenApp Db2
cases that followed are under [Db2](#db2-embedded-sql):

| case | program | det port |
|---|---|---|
| genapp-lgapvs01 | GenApp: WRITE a policy (KSDSPOLY), every policy type | **proven** |
| genapp-lgdpvs01 | GenApp: DELETE a policy | **proven** |
| genapp-lgupvs01 | GenApp: READ UPDATE / REWRITE a policy | **proven** |
| cbsa-updcust | CBSA: update a customer (READ UPDATE / REWRITE, title validation, I/O faults) -- 23 scenarios | **proven** |
| genapp-lgacvs01 | GenApp: WRITE a customer (KSDSCUST, `FROM(CA-CUSTOMER-NUM) LENGTH(225)`) | **proven** |
| genapp-lgucvs01 | GenApp: REWRITE a customer | **proven** |
| cbsa-abndproc | CBSA: WRITE an abend record (ABNDFILE): new keys, a duplicate key, negative codes, NOSPACE / NOTOPEN faults -- 8 scenarios | **proven** |

The last three were blocked at first. Getting them to prove found six defects, none of them in the COBOL:

| where | defect | fix |
|---|---|---|
| generator | KEYS and RECORDSIZE coded inside IDCAMS `DATA(...)` were ignored, so the store had no key and no record size | read from the cluster, then DATA, then INDEX (`gitgalaxy/core/file_control.py`) |
| generator | a WRITE's record was taken as its FROM item alone, ignoring `LENGTH`: GenApp's customer entity held a 10-byte key instead of the 225-byte record | the record is the LENGTH bytes from the FROM item, inside its 01 (`galaxy_ir.vsam_stores`) |
| generator | a CICS WRITE stub was `repo.save(...)`, which silently replaced an existing record where CICS raises DUPREC | the stub checks the key and raises `DuplicateKeyException("DUPREC")`; CardDemo's three model ports that write re-prove with it |
| generator | `SIGN LEADING / TRAILING SEPARATE` reached the entity codec as an embedded sign (`+00000017` written back as `0000000{ `); a bare `SIGN SEPARATE` was not recognised at all | the sign's place is recorded (`record_data.sign_separate`: 1 trailing, 2 leading) and the codec has `zonedSeparate` / `putZonedSeparate` |
| generator | entity comments gave the PICTURE without the USAGE, so the det-port decoded a COMP-3 key as zoned and a duplicate key went unseen | comments say `PIC S9(15) COMP-3`; `det/entity.py` refuses a comment whose PICTURE does not give its byte count, and the exact key-byte scan stays |
| translator and harness | `WRITE` / `REWRITE` / `WRITEQ TS ... FROM(x) LENGTH(n)` used x's own length on both sides | n bytes from x's first byte, as CICS reads them |

The harness also stopped dropping data without saying so. A scenario's COMMAREA field that the contract DTO has no
property for used to reach the port as nothing. It is now refused by name. ABNDPROC's DTO is its callers'
`ABNDINFO-REC` (`ABND-*`), not its own `COMM-*` names, and the case now describes it that way. All 23 other CICS
cases were checked: none drops a field.

GenApp's error paths (DUPREC, NOTFND, injected faults) all LINK to LGSTSQ first, which the one-program cases do
not run. A case scenario that reaches such a LINK is refused. Since #4173 an SQL-fault task that reaches it is judged
up to and including the LINK (its events and the COMMAREA bytes it passes, byte for byte), its end state not compared
(register X6, M2). The CBSA cases cover
their error paths, ABNDPROC's DUPREC among them. No case here browses, so EBCDIC vs ASCII key order is still not
exercised.

### Estate 4: IBM DBB MortgageApplication (2026-10-03)

A fourth estate, from a different IBM team: [estate4_dbb_mortgage.md](estate4_dbb_mortgage.md). 99.0% of its 204
statements translate. EPSNBRVL (a CALL with a group USING item; 22/22 branches) and EPSCMORT (CICS, a generated BMS map,
Db2) are proven. EPSMPMT is not proven on purpose: its payment is computed in floating point (C6; its `NUMPROC(MIG)` is modelled since #4271, C5). EPSMLIST waits for ESDS browse by RBA
(#4213). Onboarding it needed general fixes: compiler cards from column 1, `ID DIVISION`, group USING items across a
CALL as contract DTOs, and nested COPY in a copybook's record (the IR).

## The combined method (B): deterministic first, a model refactors under proof

**B1 -- structured style** (`det_port.py --style structured`, no model). A program with no GO TO, no EXEC CICS HANDLE
and no SECTION has paragraphs as named methods called directly (`p1000CardfileGetNext()`), fields by their COBOL
names (`endOfFile`), constants by value (`D16`): PERFORM a THRU b is a, ..., b in turn and the entry calls every
paragraph in order -- COBOL's flow exactly, no dispatcher. 18 of the 24 CardDemo programs; all 24 prove in this style
(the other 6 keep the dispatcher).

**B2 -- a model refactors, every step proven** (`tests/tools/det_refine.py`). The customer's model (port_runner's
backends) rewrites one paragraph method at a time for a reader, under fixed rules; the case is proven again and
the rewrite kept only if it proves, retried once with the proof's feedback, else reverted -- the port is proven after
every step.

| program | methods | kept | time | Cobol.* calls | lines |
|---|---|---|---|---|---|
| CBACT02C (structured) | 7 | 7 (2 on the retry) | 259 s | 47 → 45 | 302 → 353 (Javadoc, helpers) |
| COACTUPC (dispatcher, 66 GO TOs), every paragraph | 109 | **109** (11 on the retry, 0 reverted) | 3,543 s | 3,614 → **1,347** | 6,816 → 6,843 |
| COTRN02C (structured **and typed**), every paragraph | 19 | **19** (1 on the retry) | 518 s | 494 untyped → 442 typed → **319** | 2,165 → 2,247 |

The model adds a Javadoc per paragraph, else-if chains, the 88-level conditions as named predicates, and extracted
helpers. It removes `if (true)` scaffolding (COACTUPC: 77 → 0). The `Cobol.*` count is of call sites: part of its fall
is helpers that collapse repeated calls (`moveSpaces(a, b, c, ...)`), the runtime doing the same work. COTRN02C
is the first program with all three layers -- structured, typed, refined -- and its refined port proves from
scratch on 31 scenarios, 88 of 88 events ([benchmark](../benchmarks/det-refine-cotrn02c/README.md)). The fully refined COACTUPC was then proven again from
scratch, with no build reused: 54 scenarios, 156 of 156 events equal. Examples: `docs/benchmarks/det-refine-cbact02c/`,
`docs/benchmarks/det-refine-coactupc/`.

**B3 -- typed state** (`det_port.py --typed`, no model). WORKING-STORAGE items become Java fields of their own type
instead of views on byte storage: PIC X(n) a `String` of n characters, a binary integer a `long`, a zoned or packed
number a `BigDecimal`. Candidates are named elementary items under no OCCURS, no REDEFINES at, above or over them,
not JUSTIFIED, their name unique. Every use then has a typed form or none:

- typed forms: MOVE (a literal or figurative is computed at generation, padded or truncated; any other sender through
  the runtime's own MOVE: `Cobol.moveText`), comparisons (`name.equals("Y  ")`, `Cobol.compareText` -- space-padded,
  in the record charset's order), 88-level tests and SET TRUE, arithmetic stored through the item's own rules
  (`Cobol.binary` / `zoned` / `packed`: truncation, ROUNDED, the byte width's wrap), INITIALIZE, DISPLAY of a String,
  RESP / RESP2;
- no typed form: a reference modification, a subscript, a use of the group holding the item (a group MOVE, a file
  record, a commarea), STRING / UNSTRING / INSPECT, DISPLAY of a number (its external form), arithmetic ON SIZE ERROR;
- **negative zero:** a MOVE into a signed number when the MOVE could leave negative zero.
  - A MOVE keeps the sending sign through truncation (`MOVE -0.05` or `-1000.0` into `S9(3)` gives `00}`), and a
    `BigDecimal` cannot hold negative zero.
  - So the MOVE is a typed form only from a literal that doesn't truncate to negative zero, or from a typed
    sender whose digits all fit.
  - An arithmetic result is +0 (GnuCOBOL), so it is always a typed form.
  - Found by `NEGZERO` in `test_det_programs.py`, after B3 shipped. No CardDemo item was exposed: all 24 typed
    ports keep the same typed fields.

A use with no typed form is a lift violation: translation is repeated without lifting that item (a fixpoint, at most
one pass per violating item), so typing an item never changes what the program does -- the item is either typed
everywhere or byte storage everywhere. Without `--typed` the output is byte for byte what it was.

| | typed fields | Cobol.* calls |
|---|---|---|
| 24 CardDemo programs (structured style), all proven typed | 532 | 10,298 → 9,490 |
| batch (CBTRN01C, CBACT04C, CBTRN02C, CBTRN03C, CBACT02C/03C, CBCUS01C) | 82 | 990 → 636 |

The batch programs' state is flags, counters and amounts: a third of the runtime calls go. The CICS programs' state
is mostly the screen map, the commarea and file records -- groups, which stay byte storage (their typed form is a
DTO, not a lifted field; next). test_det_programs.py runs every program both ways against GnuCOBOL, TYPED among them
(each kind and each fallback).

**Typed values and size (2026-10, measured on all 51 cases, translate-only).** Typed fields are a readability rule,
not a size rule. Counting the emitted lines by kind showed why: a typed field's declaration replaces its byte
`Field` one for one (1,427 each way), byte MOVEs drop by only ~500 lines, and the items that dominate the port --
records, COMMAREAs, screen maps -- are exactly the ones whose bytes the proof needs (record I/O, group moves,
REDEFINES). Prediction before the change: `--typed` ≈ +0.9% code lines once its initial values are set once
(`initialState()`); measured +1.0%. `--typed --groups` costs +10.7% (pack / unpack around whole-group uses).
SENTINEL's ×0.44 comes from dropping byte storage altogether, which a byte-level proof does not allow.

**Typed is the default** (`det_port.py` and `port_runner`, since 2026-10; `--no-typed` for the byte form). It
proves every case the byte form proves -- all 51 cases translated `--typed`: 49 proven, the 2 KNOWN_UNPROVEN differ
as before -- across CardDemo, CBSA and GenApp, Db2 included. 1,427 items become plain `String` / `long` /
`BigDecimal` fields, each with its COBOL name and picture as a comment (`private long f97_APPL_RESULT;  // APPL-RESULT
PIC S9(9) BINARY`), at +1.0% code lines. `--groups` stays opt-in (+10.7%).

| 49 programs, each program's service file | COBOL | before #4202 | #4202 | + `initialState()` |
|---|---|---|---|---|
| code lines | 23,598 | 81,206 | 64,215 | 62,803 |
| code lines ÷ COBOL, median (range) | 1 | ×4.28 (1.9–9.3) | ×3.32 (1.6–7.2) | ×3.18 (1.6–7.0) |
| token mass | 323 K | 2,617 K | 2,502 K | 2,452 K |
| max function complexity, median / max | 8 / 97 | 26 / 172 | 26 / 172 | 26 / 172 |

The large programs are ×1.6–2.0 of their COBOL; the ratio is high only for small programs, where the fixed
service overhead dominates. Token mass and complexity barely move: the removed lines were short boilerplate.

**Unused items (2026-10, measured on all 54 cases, translate-only, typed default).** Counting the lines by kind again
(main, 53 programs' service files, 65,990 code lines): statements in paragraphs 34.5%, byte `Field` declarations
24.6%, entry points 11.8%, storage image data 8.9%, PERFORM / GOBACK scaffolding 5.7%. 10,083 of the 17,436 `Field`s
were named nowhere else in the class. Dropping them is the largest saving that leaves every stored byte in place:

| 53 programs, each program's service file | COBOL | main (typed default) | + unused `Field`s dropped |
|---|---|---|---|
| code lines | 24,424 | 65,990 | 56,764 (−14.0%) |
| code lines ÷ COBOL, median (range) | 1 | ×3.21 (1.6–7.3) | ×2.65 (1.4–6.6) |
| token mass | 334 K | 2,503 K | 2,243 K (−10.4%) |
| max function complexity, median / max | 8 / 97 | 25 / 172 | 25 / 172 |

(53 programs: the 49 above plus four merged since, three of them IBM DBB MortgageApplication's.) The
port-invariance readings do not move (53 pairs: function_count 0.916, struct_branch 0.805, state_flux 0.729, arch_io
0.884, arch_ipc 0.857, the same as main), and no parity warning appears. Next by size, measured the same way: storage
images deflated before base64 (~5,000 lines: the image data lines go to about one per storage), the PERFORM /
GOBACK / PerformExit scaffolding moved into `cobolrt` (~2,600), the CICS EIBAID switch as a runtime table (~700),
a storage that owns its image (`reset()` for the `arraycopy` line, ~900).

**Typed groups** (`--typed --groups`, no model). B3 types only items whose groups are never used whole, so a
COMMAREA or a record read INTO stayed byte storage. With `--groups` the items inside such a group are typed too,
and the group's bytes stay for its whole-group uses:

- **Before a statement uses the group whole,** the typed fields are packed into its bytes, once, before the
  statement. A second pack inside it would undo its own writes (INITIALIZE's element moves).
- **In a condition** (IF, EVALUATE, PERFORM UNTIL), the pack happens where the condition is evaluated, every time,
  because a loop body may change the typed fields between evaluations.
- **After a statement may have written the group,** the typed fields are unpacked: `String` and `long` round-trip
  exactly.
- **What stays byte storage** (violations, by the same fixpoint as B3):
  - a typed number in a group that is written whole (the bytes may be no number, such as `MOVE SPACES`);
  - a write by a statement that can transfer control before the unpack;
  - a write by a statement with phrases of its own (`READ ... INVALID KEY`, `ON OVERFLOW`, ...). Those phrases run
    before the statement ends, so they would read stale typed fields. The first proof run caught this on CBTRN02C,
    and TGROUPS in `test_det_programs.py` now fails without the rule.

| 24 CardDemo programs (structured), all proven | typed fields | business-logic `Cobol.*` call sites | sync methods' call sites |
|---|---|---|---|
| `--typed` | 532 | 9,490 | 0 |
| `--typed --groups` | **1,346** | **8,204** (−13.6%) | 1,769 |

The business logic gets more typed fields and 14% fewer runtime calls, but the generated pack / unpack methods add
calls of their own: in total, runtime call sites rise about 5%. It is a readability trade, so it is opt-in.

**Screens are not covered.** A BMS symbolic map declares its output map as a `REDEFINES` of its input map, so
every screen field overlaps another, and overlapping items are never typed. Typing them needs aliasing (one Java
field for `TRNAMTI` and `TRNAMTO`). That is the next step.

## Db2 (embedded SQL)

**Proven on real Db2.** Both sides of a Db2 case run their SQL on one IBM Db2 (Db2 Community Edition, in a container,
`tests/tools/equivalence_db2.py`). The tables are created from the corpus's DDL, reset to the case's seed before every
run, and compared row by row after it. Each value is compared in its character form, trailing blanks included, and
NULL is distinct.

- **COBOL side (the oracle).** GnuCOBOL has no Db2 precompiler, so the harness has one (`tests/tools/equivalence_sql.py`):
  - each `EXEC SQL` becomes a `CALL 'GGSQL'`, and the stub (`tests/equivalence/db2/ggsql.c`) runs the statement on Db2
    through IBM's CLI driver;
  - host variables are bound as the Db2 precompiler declares them for COBOL: `PIC X(n)` CHAR(n) with all its bytes,
    a 49-level pair VARCHAR, zoned and packed DECIMAL(p,s), binary SMALLINT / INTEGER / BIGINT;
  - SQLCODE, SQLSTATE, the warnings and SQLERRD(3) come from Db2 itself;
  - `SET :hv = expr` runs as a one-row `VALUES` into the host variables; a positioned UPDATE / DELETE (`WHERE
    CURRENT OF`) runs as written, ggsql.c naming each cursor at its OPEN;
  - forms it does not model are refused by name: WHENEVER, dynamic SQL (PREPARE / EXECUTE / DESCRIBE), CONNECT,
    CALL, ALLOCATE / ASSOCIATE, SCROLL cursors and host-variable arrays.
- **Java side (the det port).** Each statement calls the generated Db2 repository's method for it. The generator writes
  one method per statement, with the SQL as written and its Javadoc naming the source line and each parameter's host
  variable, so the boundary is again the generator's. `cobolrt/sql/DetSql` turns host-variable bytes into JDBC values
  and back by the same Db2 rules. It turns outcomes into the SQLCA: +100 for a searched UPDATE / DELETE with no row,
  +100 / -811 for SELECT INTO, Db2's own SQLCODE otherwise. Cursors run their query at OPEN; for a positioned UPDATE /
  DELETE the generated repository addresses the cursor's current row by its `RID_BIT`.
- **Proven: all three of CardDemo's Db2 programs, six of CBSA's and all eight of GenApp's**, translated with no model.

  | case | program | scenarios | paragraphs | branches | translated |
  |---|---|---|---|---|---|
  | `carddemo-cobtupdt` | COBTUPDT, batch add / update / delete | 1 run | 9/9 | 14/20 | 58/58 |
  | `carddemo-cotrtupc` | COTRTUPC, CICS update screen | 34 | 62/63 | 124/166 | 436/436 |
  | `carddemo-cotrtlic` | COTRTLIC, CICS list screen with cursors | 27 | 56/59 | 165/230 | 631/632 |
  | `cbsa-updacc` | CBSA UPDACC, LINKed account update (CBSA's own DDL) | 10 | 7/7 | 5/6 | 58/58 |
  | `cbsa-dbcrfun` | CBSA DBCRFUN, debit / credit + PROCTRAN | 22 | 16/22 | 22/35 | 148/148 |
  | `cbsa-inqacc` | CBSA INQACC, inquire account (cursor; ABNDPROC in the task) | 14 | 22/25 | 13/25 | 240/240 |
  | `cbsa-delacc` | CBSA DELACC, delete account + PROCTRAN | 11 | 19/19 | 10/14 | 134/134 |
  | `cbsa-xfrfun` | CBSA XFRFUN, transfer funds (four SYNCPOINT ROLLBACK paths) | 22 | 27/28 | 44/81 | 439/439 |
  | `cbsa-custctrl` | CBSA CUSTCTRL, customer control record | 6 | 7/7 | 3/4 | 21/21 |
  | `genapp-lgicdb01` | GenApp LGICDB01, inquire customer | 12 | 3/4 | 4/12 | 44/44 |
  | `genapp-lgipdb01` | GenApp LGIPDB01, inquire policy (cursors) | 29 | 11/12 | 46/74 | 238/238 |
  | `genapp-lgacdb02` | GenApp LGACDB02, add customer password | 8 | 2/3 | 4/10 | 39/39 |
  | `genapp-lgdpdb01` | GenApp LGDPDB01 + LGDPVS01, delete policy (cascade) | 8 | 2/3 | 5/12 | 73/73 |
  | `genapp-lgupdb01` | GenApp LGUPDB01 + LGUPVS01, update policy (positioned UPDATE) | 5 | 8/9 | 17/38 | 171/171 |
  | `genapp-lgacdb01` | GenApp LGACDB01 + LGACVS01 + LGACDB02, add customer (named counter or identity) | 4 | 3/4 | 6/14 | 125/125 |
  | `genapp-lgapdb01` | GenApp LGAPDB01 + LGAPVS01, add policy (identity, clock fields) | 4 | 5/7 | 13/31 | 171/171 |
  | `genapp-lgucdb01` | GenApp LGUCDB01 + LGUCVS01, update customer | 4 | 3/4 | 2/10 | 71/71 |

  - COBTUPDT matches on RETURN-CODE 4, the table's 9/9 rows and SYSOUT's 32/32 lines. Its case covers a duplicate
    key (-803), +100 updates and deletes, and a 50-character description: a `PIC X(50)` host variable keeps its
    trailing blanks in the VARCHAR(50) column, as Db2 stores it.
  - The CICS cases cover SELECT INTO, INSERT after an UPDATE of no row, a delete refused by the foreign key (-532,
    shown with SQLERRMC's tokens), +100, SYNCPOINT, and cursors forward and backward with paging, filters (LIKE)
    and a look-ahead FETCH.
  - COTRTLIC's one untranslated statement is a dynamic CALL of IBM's DSNTIAC, on the Db2-error path, which no
    scenario reaches; the COBOL side cannot run DSNTIAC either.
- **CICS.** The COBOL side runs every scenario in one container, so a small CLI tool (`tests/equivalence/db2/ggsqlrun.c`)
  resets the tables before each task and dumps them after it. The Java side's test does the same over JDBC.
  A SYNCPOINT, a SYNCPOINT ROLLBACK or an abend's backout (ggcics.c) ends the Db2 unit of work with it.
- **Side by side.** Db2 cases run in parallel on a pool of databases in the one Db2 instance (GGDB, GGDB1 ..;
  `$GITGALAXY_DB2_POOL`, default 4), one case a database for its whole run (a lock file each). Each database has
  its own catalog, schemas and identity counters, so every name the SQL uses stays as written and no case sees
  another's rows. A pool database is created as GGDB is (code set, territory, collation, page size); the rest of
  its configuration differs only in self-tuned memory sizes and logging. The harness keeps each database active:
  one nothing holds is activated by every connect, about a second each time.
- **Declared, not measured:**
  - Db2 for Linux, not z/OS, runs the SQL. Its SQLCODEs for these statements are the same codes.
  - EXEC SQL keeps RETURN-CODE. Whether IBM's precompiled call to DSNHLI resets it is not known.
  - A run that ends normally commits.
  - A CICS task's SQL is one Db2 unit of work, as under CICS's Db2 thread: a SYNCPOINT ROLLBACK or an abend backs out
    the task's SQL with its recoverable file changes (XFRFUN's four ROLLBACK paths are proven). The transaction is
    the equivalence test's, around each task; a deployment must give each task the same unit of work. A batch
    program's repositories autocommit, so a batch ROLLBACK is a hole (register Q3). A file defined `RECOVERY(NONE)`
    in the CSD keeps its changes through a backout on both sides.
  - SQL faults (#4173, register M2): each statement is keyed `PROGRAM:LINE` (its EXEC SQL's line in the file it is
    written in), the key every DetSql call carries; a fault plan skips that execution on both sides (ggsql.c,
    DetSql) with its SQLCODE. `equivalence.py run --sql-faults auto` (the default) adds a task per statement the
    case's tasks executed: -803 for an INSERT, +100 for a SELECT INTO, -913 for the rest. Branches covered rose on 14
    of the 17 Db2 cases (LGACDB01 6/14 → 8/14, LGUPDB01 17/38 → 26/38, DELACC 10/14 → 13/14).
  - What the proofs found (#4173): a LINK whose area is shorter than the target's contract DTO read past the caller's
    record (#4181: GenApp's 71-byte ERROR-MSG as LGSTSQ's 99-byte CA-ERROR-MSG); and a contract DTO typed from another
    caller's record dropped the bytes it does not name (ERROR-MSG's date, under CA-ERROR-MSG's FILLER). A LINK now
    reads to the end of the caller's record only (`Cobol.commarea`, register X10) and a det caller passes the bytes
    themselves (`CicsTask.link(..., area)`).

## In port_runner

The combined method runs in the porting loop like any other backend, and every event lands in
`ai_agent_jobs/ports/port_log.jsonl`:

- **`port_runner run --backend det --source-root ESTATE [--style structured] [--typed]`** proposes the translator's
  port. The overlay holds the service and its runtime (`cobolrt/`). The log's model is `det-port@<commit>`, with
  the translation's statement and hole counts.
- **`port_runner refine --backend ... --prove-command ...`** starts from the latest proven attempt.
  - Each method's rewrite is proven with the operator's own proof command, and each outcome is a `refine-step`
    event.
  - The result is a new attempt proposed by the refining model, and it is proven again from scratch.
  - `status` counts the translator's and the model's ports apart, and `review` is the person's decision as for
    any port.

## Limits and next steps

- **Screens stay byte storage.** COMMAREAs and records read INTO are typed with `--groups`, but a symbolic map's
  input and output maps overlap (`REDEFINES`), which typing does not do yet.
- **The oracle is GnuCOBOL.** [oracle_assumptions.md](oracle_assumptions.md) lists every known or suspected difference
  from z/OS, with its status; a z/OS session would settle most. Two bound what is proven today: **C9**, a POINTER is
  8 bytes under the harness's 64-bit GnuCOBOL and 4 on z/OS, so a COMMAREA that carries one (CBSA's INQACCCU, DELCUS,
  CREACC) cannot be compared byte for byte yet; **D1**, proofs compare text in ASCII order, z/OS in EBCDIC: indexed
  keys that mix letters and digits browse differently, and no audit has yet counted the in-program comparisons whose
  result could change.
- **Breadth outside CardDemo** is 21 programs in two estates (CBSA 8, GenApp 13), 14 of them on Db2. CBSA's other
  Db2 programs are blocked by C9 (INQACCCU, DELCUS, CREACC), by IBM's CEEIGZCT copybook (CRECUST), by FUNCTION
  RANDOM (BANKDATA) or by having only a Java caller (ACCTCTRL).
- **Out of scope for this translator:** IMS (EXEC DLI), MQ, pointer arithmetic, ALTER, ENTRY, dynamic CALL. Such
  statements stay named holes. A POINTER only stored and passed on (GenApp's prologue) is translated.
- **Re-proving everything** after a runtime, harness or oracle change: `tests/tools/proof_sweep.py --work DIR`
  re-proves every det and model port and compares the result with the cases not proven on purpose.


# Deterministic port (det-port): design and the runtime contract

**Status: 24 CardDemo programs translate with no hole and prove -- the 23 with model-written ports, and COACTUPC.** Question it answers: of the 23 CardDemo programs already proven with
model-written ports, how much can a deterministic translator port -- and does its port prove?

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
}
```

Arithmetic intermediates: exact `BigDecimal` (GnuCOBOL's default is exact decimal arithmetic for these programs'
sizes); `store` truncates high-order digits beyond the PICTURE and low-order digits beyond the scale (or rounds half
away from zero with ROUNDED).

What GnuCOBOL (`-std=ibm`) does, which the runtime follows (each is a case in `tests/cobol_mainframe/test_cobolrt.py`):

- **Binary items are not truncated to the PICTURE digits** (the harness's GnuCOBOL behaves as `TRUNC(BIN)`): an
  `S9(4) COMP` holds anything its two bytes hold (99999 MOVEd in wraps to X'869F'; ON SIZE ERROR fires only past the
  byte capacity). `Cobol.setTruncBinary(true)` selects `TRUNC(STD)` (digits) instead.
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
- PERFORM: when control falls off a paragraph, the innermost active PERFORM whose range ends there returns,
  abandoning those inside it. COACTUPC GOes TO the end of its caller's range from inside a nested PERFORM; the port
  looped where COBOL returned (GOTOOUT in test_det_programs.py).
- FUNCTION TRIM of an all-space argument is zero-length, and TRIM removes spaces only (COACTUPC's alphabetic-field
  check); SYNCPOINT ROLLBACK was emitted as a SYNCPOINT.
- The harness itself: `equivalence_cics.alphanumeric` read the 9 of `PIC X(09)` as a digit position, so COACTUPC's
  ACUP-OLD-CUST-SSN-X `017590544` reached the Java side as 17590544 -- another record than COBOL's. Fixed; the 15
  model-written CICS ports re-prove with the fix.

### Keyed reads

A base cluster's keyed READ / WRITE / REWRITE / DELETE goes through the repository's `findById`, the id decoded
from the key bytes by `det/entity.py` from the entity's `@Id` / `@EmbeddedId` comments; the record found must have
exactly the key bytes asked for (a loosely decoded key -- non-digits in a numeric key -- finds nothing, as VSAM).
Alternate indexes and browses keep the ordered scan.

## Beyond CardDemo (A5)

Equivalence cases for programs of two more estates, the COBOL run by GnuCOBOL as the oracle
(`tests/equivalence/genapp-*`, `tests/equivalence/cbsa-*`):

| case | program | det port |
|---|---|---|
| genapp-lgapvs01 | GenApp: WRITE a policy (KSDSPOLY), every policy type | **proven** |
| genapp-lgdpvs01 | GenApp: DELETE a policy | **proven** |
| genapp-lgupvs01 | GenApp: READ UPDATE / REWRITE a policy | **proven** |
| cbsa-updcust | CBSA: update a customer (READ UPDATE / REWRITE, title validation, I/O faults) -- 23 scenarios | **proven** |
| genapp-lgacvs01, genapp-lgucvs01 | GenApp: WRITE / REWRITE a customer (KSDSCUST) | differs: the generated KSDSCUST entity holds only the 10-byte key of the 225-byte record (the generator does not read KEYS / RECORDSIZE given inside IDCAMS DATA(...)) -- a generator gap |
| cbsa-abndproc | CBSA: WRITE an abend record (ABNDFILE) | fails: the generated project maps no store for ABNDFILE -- a generator gap |

GenApp's error paths (DUPREC, NOTFND, injected faults) all LINK to LGSTSQ first, which the one-program cases do
not run: they are not exercised (the harness refuses a scenario that reaches such a LINK). The CBSA cases cover
their error paths. No case here browses, so EBCDIC vs ASCII key order is still not exercised.

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
| COACTUPC (dispatcher, 66 GO TOs), its 10 largest paragraphs | 10 | 10 (1 on the retry) | 585 s | 3,614 → 2,419 | 6,816 → 6,104 |

The model adds a Javadoc per paragraph, else-if chains, the 88-level conditions as named predicates, extracted
helpers. Example: `docs/benchmarks/det-refine-cbact02c/`.

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
  record, a commarea), STRING / UNSTRING / INSPECT, DISPLAY of a number (its external form), arithmetic ON SIZE ERROR.

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

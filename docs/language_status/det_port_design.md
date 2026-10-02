# Deterministic port (det-port): design and the runtime contract

**Status: 31 programs are translated with no model and proven.** That is 24 from CardDemo, 5 from GenApp and 2 from
CBSA. All 24 CardDemo programs also prove in the structured, typed style. A model has refactored the largest of
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
| translate | `port_runner run --backend det [--style structured] [--typed]` (or `tests/tools/det_port.py run CASE ...` for the equivalence cases) | the same port from the same source every time; an untranslatable statement is a named `Hole`, never a guess | 96.8% of 16,798 statements across six estates ([survey](det_survey.md)) |
| prove | `tests/tools/equivalence.py run CASE --port DIR --faults all` | equal events (screens, COMMAREAs, XCTL / LINK / RETURN), files and RETURN-CODE against GnuCOBOL, field by field, on every scenario and injected fault | 31 programs proven |
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
Alternate indexes and browses keep the ordered scan, as does an id whose comment's PICTURE and USAGE do not give the
byte count it states.

## Beyond CardDemo (A5)

Equivalence cases for programs of two more estates, the COBOL run by GnuCOBOL as the oracle
(`tests/equivalence/genapp-*`, `tests/equivalence/cbsa-*`):

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
not run: they are not exercised (the harness refuses a scenario that reaches such a LINK). The CBSA cases cover
their error paths, ABNDPROC's DUPREC among them. No case here browses, so EBCDIC vs ASCII key order is still not
exercised.

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
  - forms it does not model are refused by name: WHENEVER, positioned UPDATE / DELETE, dynamic SQL, host-variable
    arrays, a program that shows SQLERRMC.
- **Java side (the det port).** Each statement calls the generated Db2 repository's method for it. The generator writes
  one method per statement, with the SQL as written and its Javadoc naming the source line and each parameter's host
  variable, so the boundary is again the generator's. `cobolrt/sql/DetSql` turns host-variable bytes into JDBC values
  and back by the same Db2 rules. It turns outcomes into the SQLCA: +100 for a searched UPDATE / DELETE with no row,
  +100 / -811 for SELECT INTO, Db2's own SQLCODE otherwise. Cursors run their query at OPEN.
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
  A SYNCPOINT, a SYNCPOINT ROLLBACK or an abend's backout (ggcics.c) ends the Db2 unit of work with it. Db2 cases
  run one at a time: they share the database, and the harness takes a lock.
- **Declared, not measured:**
  - Db2 for Linux, not z/OS, runs the SQL. Its SQLCODEs for these statements are the same codes.
  - EXEC SQL keeps RETURN-CODE. Whether IBM's precompiled call to DSNHLI resets it is not known.
  - A run that ends normally commits.
  - The Java side commits each statement as the repositories run it, so ROLLBACK is a hole. A CICS path that
    backs out after a Db2 change would show as a difference, never as a proof; no scenario here reaches one.

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
  from z/OS (C1: IBM's default TRUNC(STD) has been running as TRUNC(BIN) on both sides); a z/OS session would settle most.
- **Breadth outside CardDemo** is 7 cases in two estates. Db2 (EXEC SQL), IMS and pointer code are out of scope for
  this translator: such statements stay named holes.


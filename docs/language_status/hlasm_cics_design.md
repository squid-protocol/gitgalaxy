# HLASM + EXEC CICS: the assembler path (#5859)

zECS (burned estate `zecs`) holds two command-level CICS assembler programs, `Source/ZECSNC.asm` and
`Source/ZECS002.asm`. Before this path both were refused whole ("CICS Assembler not supported", #5121) and sat at L0
of the ladder. This page records how the det translator reads them, what it assumes, and what is left.

## Decision: a front end, not a per-program port

`gitgalaxy/tools/cobol_to_java/det/hlasm.py` **lowers** an assembler program to a fixed-format COBOL program.
`det/source.py` (`assembler_lowered`, called from `program_lines`) then hands that program to the translator like
any other. This follows the BLL precedent (X56, `bll.lower_text`): the COBOL program is the one both sides read. In
slice 2 the GnuCOBOL oracle will read it too. So every EXEC CICS command reuses the existing translation, stub and
Java runtime, and nothing in the translator learns assembler.

A program is lowered whole or refused whole. Anything outside the subset raises `hlasm.Refused`, which names the
construct and its line. `source.py` turns that into the #5121 refusal shape:
`<file>:<line>: CICS Assembler not supported (DFHEIENT): outside the HLASM lowering's subset (#5859): <construct> at line N`.
`refusal_map.json`, `cics_census.error_key` and the #5121 tests all match that shape.

## References (IBM is the reference)

- z/Architecture Principles of Operation, SA22-7832. Chapter 7 gives the instruction semantics and the condition
  code each instruction sets.
- HLASM Language Reference, SC26-4940. It covers DS / DC, boundary alignment, length attributes, EQU and
  continuation rules.
- CICS Application Programming Reference. It covers DFHEIENT, DFHEISTG, DFHEICAP, the DFHEIBLK fields, and the
  command options.

## Subset (slice 1: every construct ZECSNC uses)

| Area | Accepted | Lowered as |
|---|---|---|
| Entry | `DFHEIENT CODEREG= DATAREG= EIBREG=` | `PROGRAM-ID`; the named registers are reserved |
| Storage | `DSECT`, `DS` / `DC` of C, X, H, F (D as `DS` only); `0CLn` groups; `DS 0F/0H/0D`; `nCLm` / `nXLm` copies (one field of n elements) | see Storage below |
| Symbols | `EQU n`, `EQU *-sym` (a length) | a constant |
| Load / store | `L`, `ST`, `STH`, `LA` of a constant or of a symbol (below) | `MOVE`; `STH` is `MOD(r + 32768, 65536) - 32768`, the low halfword, signed |
| Move | `MVC` with a static symbol, `+disp` and `(len)`, or a `=C'..'` literal exactly the destination's length | `MOVE` with reference modification; an overlapping move is refused |
| Clear / count | `SR Rn,Rn`, `XC X,X` (also `XC X(n),X`), `BCT Rn,label` | `MOVE 0`; `MOVE LOW-VALUES`; a wrapping 32-bit decrement and `IF NOT = 0 GO TO`. None sets a CC a `BC` may read |
| Address model (3b) | `LA Rn,sym[+d]`, `LA Rn,d(,Rm)`; `d(Rm)` / `d(,Rm)` / `d(1,Rm)` and `SYM(Rx)` operands on `CLI`, one-byte `MVC`, `IC`, `STCM`, `TR`; `SLL Rn,k`, `SLDL Re,k` | an address is `region * 65536 + offset`; a dereference is `EVALUATE` on the region and reference modification (Address model below) |
| Compare | `CLC`, `CLI` (also through a register), `CH`, `OC X,X` | a condition on the next `BC` |
| Branch | `B`, `BC mask`, `BAS`, `BCR 15` | `GO TO`; `BAS`/`BCR` use return ids (below) |
| CICS | `EXEC CICS ...` with operands that are symbols, EIB fields, literals or numbers | `EXEC CICS ... END-EXEC` |
| Ignored | `AMODE`, `RMODE`, `PRINT`, `LTORG`, `END`, an unnamed branch-around `DC` | nothing |

Anything else is refused by name. That includes:

- any other instruction (`ICM`, `A`, `S`, ...);
- a base-displacement operand on any instruction other than the ones in the Address model row, a displacement past 4095,
  an index register on a non-SS operand, a shift count that is not an immediate;
- a duplication factor other than 0 on H, F or D (they need alignment and an array);
- arithmetic on an address (`A`, `S`, ... on a register that holds one), `LA` of a binary field, a store into a CSECT region;
- a store into a program constant or the EIB;
- a DSECT that no `USING` addresses;
- a constant reached by fall-through.

## Storage model

- Each DSECT is laid out with HLASM boundary alignment: H to 2 bytes, F to 4, D to 8. The bytes alignment skips
  become a `FILLER`, so offsets inside a group or the COMMAREA are HLASM's.
- Every symbol keeps its offset and its length attribute.
- A `0CLn` symbol is a group over the fields it covers. Fields that do not cover it exactly are refused.
- `DFHEISTG` becomes WORKING-STORAGE.
- The DSECT that a `USING` binds to the register loaded by `L Rn,DFHEICAP` becomes `LINKAGE DFHCOMMAREA`.
- EIB fields are DFHEIBLK's, supplied by the CICS translation (`EIBCALEN`, `EIBTRNID`, `EIBRESP`, ...).
- H becomes `S9(4) COMP-5`; F becomes `S9(9) COMP-5`. C and X become `PIC X(n)`.
- An `XL8` that a `DCOUNTER` option names is an unsigned doubleword, `9(18) COMP-5`. A value past 18 digits is refused.
- Registers are fullword binary cells `HL-Rn`. The entry registers and R13 are reserved: using one as a work
  register is refused.
- Code addresses are opaque return ids. `BAS` stores the id of its return point. `BCR 15,Rn` dispatches with
  `GO TO ... DEPENDING ON`. An id no `BAS` stored is a branch to an address the program never took, so it is a
  program check: `ABEND ABCODE('ASRA')`.

## Address model (slice 3b)

- Only a symbol whose address an `LA` takes becomes a region (found by a prescan); the region is its top-level unit: a
  01 of DFHEISTG or of the CSECT, or the whole COMMAREA. Region ids count from 1 in order of first use.
- An address is `region * 65536 + offset` in the register (a fullword). `LA Rn,d(,Rm)` is `MOD(Rm + d, 2**31)`, the
  31-bit address wrap (POPS, LOAD ADDRESS). No other arithmetic on an address is accepted (assumption 4).
- A dereference runs `DIVIDE Rm BY 65536 GIVING HL-RG REMAINDER HL-OF`, `EVALUATE HL-RG` over the regions, a range guard
  per region, then reference modification `REGION(HL-OF + 1:n)`. An address outside every region, past a region's end,
  or a store into a CSECT (constant) region is `EXEC CICS ABEND ABCODE('ASRA') NODUMP`: the program check on z/OS
  (assumption 5).
- A region holding a binary field (H, F, D) or a valued C constant is refused: its bytes differ between the COBOL cell
  and z/OS (little endian; ASCII vs EBCDIC). An X-valued table (`B64XLT`, 256 bytes) is accepted.
- A byte becomes a number through `HL-W2` / `HL-N` (a 2-byte big-endian binary over `HL-HI`, `HL-LO`): `FUNCTION ORD`
  is not in the det translator.
- `IC` replaces the low 8 bits of the register and keeps the rest. `STCM` takes the bytes the mask names (bit 8 is the
  high byte of the low 32 bits) and stores them side by side. `TR` replaces each byte by the table byte it indexes
  (up to 16 bytes). `SLL` is a wrapping 32-bit logical left shift; `SLDL` shifts the even/odd pair as one 64-bit value
  (an even register with a free odd partner, a count 1 to 31). `CLI` against a `C` literal compares the cp037 byte.
- Every generated line must end by column 72; a longer one is refused (it would be silently cut).

## Condition code

The condition code is resolved statically, with no CC cell. A conditional `BC` must directly follow the instruction
that sets the CC; otherwise it is refused. The POPS outcomes are:

| Setter | CC 0 | CC 1 | CC 2 |
|---|---|---|---|
| `CLC`, `CLI` (logical) | equal | first low | first high |
| `CH` (arithmetic) | equal | register low | register high |
| `OC X,X` | zero | nonzero | (none) |

- The mask's taken set (bits 8, 4, 2, 1 for CC 0 to 3), intersected with the CCs the setter can produce, becomes
  one COBOL relation.
- A logical compare whose high / low outcome the mask separates is **refused**. GnuCOBOL collates in ASCII while
  z/OS collates in EBCDIC, so only equal / not-equal is exact.
- Masks 0 and 15 are `CONTINUE` and `GO TO`.

Each lowered paragraph ends in a period. Without one, the det parser reads the next paragraph header as a `GO TO`
operand.

## Assumptions (stated, not proven)

1. **The oracle proves the det port, not the lowering.** GnuCOBOL plus the CICS stub runs the *lowered* program, the
   same common mode as X56. The lowering's fidelity rests on the per-instruction POPS unit tests
   (`tests/cobol_mainframe/test_hlasm_lowering_5859.py`). Slice 4 adds an independent interpreter cross-check (`tests/tools/hlasm_interp.py`, `tests/cobol_mainframe/test_hlasm_interp_5859.py`): it covers the branch conditions, ZECS002's end states and (slice 5) ZECSNC's 7 scenarios, not every instruction against GnuCOBOL (see slice 4 below; register X74).
2. **DFHEISTG initial contents.** IBM does not initialise DFHEISTG. The lowering leaves WORKING-STORAGE without
   `VALUE`, so its content is the runtime's initial fill. Slice 1 does not refuse a read before write. A case (slice 2)
   must state the fill it relies on.
3. **Character data is compared for equality only**, as for the COBOL cases: the EBCDIC vs ASCII question is not
   raised by `=` / `NOT =`.
4. **The address representation is opaque.** No program arithmetic on a code or data address is accepted.
5. **An address outside our storage abends `ASRA`.** On z/OS it may name other storage or take a different program check;
   a case must not rely on it. Which region numbers an address carries is not observable by the program.

## Status

- ZECSNC lowers whole. Since slice 2a it has 1 hole left, in `det/cics.py` option modelling:
  - `WRITE OPERATOR ... TEXTLENGTH ROUTECODES NUMROUTES EVENTUAL`.

  `ABEND ... NOHANDLE` is modelled (IBM lists no ABEND condition, so it suppresses nothing). ZECSNC is still L0.
- ZECS002 lowers whole since slice 3b (the address model), 1181 COBOL lines, and translates whole since slice 3c
  (`EXEC CICS VERIFY PASSWORD`, register X32; `det_survey` zecs: 7 of 7 whole, all compile). Since 3d it has the
  `zecs-zecs002` equivalence case (11 scenarios, the VERIFY verdict keyed by `userid_hex`) and is proved against GnuCOBOL
  plus the stub; ZECSNC has `zecs-zecsnc` (7 scenarios).
- Slice 4 (partial): `tests/tools/hlasm_interp.py` interprets the subset from the Principles of Operation alone (EBCDIC
  storage, 32-bit registers, a real condition code, EXEC CICS as recorded events) and shares nothing with `det/hlasm.py`.
  The test compares (a) every `CH` mask of the lowering's branch condition with the interpreter, over boundary operand
  pairs (masks 1 and 14 are refused by name), (b) per-instruction semantics the Base64 decoder leans on, and (c) ZECS002's
  end COMMAREA and CICS event sequence for all 11 scenarios with the GnuCOBOL run of the lowering. One difference
  surfaced: the lowering stores `MVC CA_RC,=C'00'` as ASCII text (z/OS stores EBCDIC `F0F0`); same characters, other
  encoding, the known cost of assumption 3. Everything else in the end COMMAREA is byte-identical.
- Slice 5: the same comparison for ZECSNC's 7 scenarios (events, payload text, counters created; ABEND codes for EIBCALEN
  1, 4, 9), plus the ROUTECODES / NUMROUTES the stub does not record. The interpreter gained DEFINE DCOUNTER name rules,
  the WRITE OPERATOR routecodes, a DFHEISTG fill fact, and two fixes (FORMATTIME, `D(L)` lengths). Register X74.
- Slice 6: the per-instruction differential against `cobc` (item 4 below): 71 snippets, 0 differences.
- Slice 7: the same differential over storage bytes: 97 more snippets (168 in all, 0 differences). `MVC` (lengths 1-8, offsets,
  the `=C` literal), `XC`, `OC X,X` (a halfword / fullword zero test), `CLC` / `CLI` (equal / not equal), `STCM` (all 15
  masks, and at an offset), `IC` (a byte, and `IC R,TBL(R)`), `TR` (1, 3, 8 bytes over a 256-byte table). The fields' bytes
  are compared raw for binary data, and as characters for text (the interpreter is EBCDIC, the lowering ASCII: assumption 3),
  so a text case keeps to letters. The lowering refuses `BC` high / low after `CLC` / `CLI` by name, because EBCDIC and ASCII
  collate differently; a test pins that refusal. No defect surfaced in the lowering or the interpreter.
- Slice 8: the branch-and-link and fullword instructions (13 more snippets, 181 in all, 0 differences). `BAS` / `BCR 15,R14`
  (one call, two calls, a nested call that saves R14 with `ST` and reloads it with `L`), `BCR 0` (no branch), `BC` masks 0 and 15,
  and an `ST` / `L` round trip over six words including the sign bit. R14 is never compared (an address in the interpreter, a
  return index in the lowering: assumption 4); the cases observe the path taken and the register `L` reloads. The bytes of a
  stored fullword are not compared: the lowering keeps `F` as a native binary item (other byte order), and it refuses every
  byte access to one (`MVC`, `STCM`, `IC`, `CLC` before a `BC`); a test pins those refusals. No defect surfaced.
- Slice 9: the estate census (`tests/cobol_mainframe/test_hlasm_estate_census_5859.py`). Every `.asm` in a burned estate is
  either lowered (ZECS002, ZECSNC: opcodes inside `hlasm.SUBSET`, no `MVI`, so the high / low refusal is never reached) or a
  named library model (CardDemo's `COBDATFT.asm` and `MVSWAIT.asm`: batch routines COBOL CALLs, modelled by runtime code,
  oracle A1 and `Mvswait.java`, not lowered). A new burned assembler file fails the test until it is placed. This closes the
  assembler path for the burned estates. Lowering COBDATFT / MVSWAIT would need `MVI`, `STM` / `LM` linkage and a batch
  entry convention: frontier, and only if the library models are ever to be replaced by the source.
- The ladder report keeps both programs in the fixed 129-program denominator. ZECS002 is listed apart in the "refused
  whole: not COBOL" row of the progress page (`tests/tools/ladder_exclusions.py`, #5280), so it is not read as COBOL
  translator work; the page reports the entry as stale once it leaves L0. ZECSNC has no entry: it lowers and
  translates, so it is core work counted in the reachable denominator.

## Remaining slices

1. **2a-2:** `WRITE OPERATOR` `TEXTLENGTH`, `ROUTECODES` + `NUMROUTES`, `EVENTUAL`: the registry, `det/cics.py`, `CicsTask`, the stub
   (`ggcics.c` `GGCWTO`) and a register X32 entry. This takes ZECSNC to L1.
2. **2b (done) and 2c (done):** an untyped COMMAREA for a case with no layout: a scenario's `"commarea_hex"` is the exact
   bytes the caller passed (EIBCALEN is their count; `commarea.exact` on the stub side, a `byte[]` on the port's).
   ZECSNC scenarios: EIBCALEN 0 (terminal), 8 (non-terminal start), and 1, 4 and 9 (ABEND). The end-state COMMAREA of a
   non-linked program is not compared (nothing observes it). The case is `tests/equivalence/zecs-zecsnc/`; the X register
   entry for assumption 1 is X74 (slice 5, done).
3. **3a (done):** duplicated `C` / `X` storage, `SR Rn,Rn`, `XC X,X`, `BCT`, the `=C'..'` literal move.
   **3b (done):** the address model (above). **3c (done):** `EXEC CICS VERIFY PASSWORD` (registry, `det/cics.py`,
   `CicsTask.verifyPassword`; a column-15 EXEC CICS continuation in the front end). **3d:** the stub's `GGCVER` in `ggcics.c`, the
   fault-plan validation in `equivalence_cics_faults.py`, and the `zecs-zecs002` equivalence case.
4. **4 (done, above):** the interpreter cross-checks ZECS002 and ZECSNC (slices 4, 5). Slice 6 adds the per-instruction
   differential: `tests/tools/hlasm_diff.py` runs 71 boundary snippets (LA, SLL, SLDL, SR, BCT, STH, CH with eight masks
   branch masks) through the interpreter and, lowered, through `cobc` in the pinned oracle image (one container);
   registers agree on all 71, zero differences. Slice 7 (done) adds the storage-byte instructions and slice 8 (done) the linkage and fullword ones (above).
   Not built, on purpose: `MVI` (outside the subset), high / low collation after `CLC` / `CLI` (refused by name), and a general
   assembler path for non-zECS programs. No burned program needs them (slice 9 pins that).

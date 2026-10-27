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
| Storage | `DSECT`, `DS` / `DC` of C, X, H, F (D as `DS` only); `0CLn` groups; `DS 0F/0H/0D` | see Storage below |
| Symbols | `EQU n`, `EQU *-sym` (a length) | a constant |
| Load / store | `L`, `ST`, `STH`, `LA` of a constant | `MOVE`; `STH` is `MOD(r + 32768, 65536) - 32768`, the low halfword, signed |
| Move | `MVC` with a static symbol, `+disp` and `(len)` | `MOVE` with reference modification; an overlapping move is refused |
| Compare | `CLC`, `CLI`, `CH`, `OC X,X` | a condition on the next `BC` |
| Branch | `B`, `BC mask`, `BAS`, `BCR 15` | `GO TO`; `BAS`/`BCR` use return ids (below) |
| CICS | `EXEC CICS ...` with operands that are symbols, EIB fields, literals or numbers | `EXEC CICS ... END-EXEC` |
| Ignored | `AMODE`, `RMODE`, `PRINT`, `LTORG`, `END`, an unnamed branch-around `DC` | nothing |

Anything else is refused by name. That includes:

- any other instruction (`IC`, `SR`, `BCT`, `SLL`, `TR`, `XC`, ...);
- base-displacement operands (`0(1,R6)`);
- a duplication factor other than 0;
- `LA` of an address;
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
   (`tests/cobol_mainframe/test_hlasm_lowering_5859.py`). An independent interpreter cross-check is slice 4.
2. **DFHEISTG initial contents.** IBM does not initialise DFHEISTG. The lowering leaves WORKING-STORAGE without
   `VALUE`, so its content is the runtime's initial fill. Slice 1 does not refuse a read before write. A case (slice 2)
   must state the fill it relies on.
3. **Character data is compared for equality only**, as for the COBOL cases: the EBCDIC vs ASCII question is not
   raised by `=` / `NOT =`.
4. **The address representation is opaque.** No program arithmetic on a code or data address is accepted.

## Status

- ZECSNC lowers whole. Translated, it has 2 holes left, both in `det/cics.py` option modelling:
  - `ABEND ... NOHANDLE`;
  - `WRITE OPERATOR ... TEXTLENGTH ROUTECODES NUMROUTES EVENTUAL`.

  So ZECSNC is still L0, but the reason changes from "refused whole" to "2 holes left".
- ZECS002 is refused at its first construct outside the subset: `DC 08XL01'40'`.

## Remaining slices

1. **2a:** `det/cics.py`, the stub and a register entry for `ABEND NOHANDLE` and the `WRITE OPERATOR` routing
   options. This takes ZECSNC to L1.
2. **2b:** an equivalence case `tests/equivalence/zecs-zecsnc/`. It needs:
   - a lowering hook in `tests/tools/equivalence_cics.py`, beside `bll.lower_text`;
   - an X register entry for assumption 1.

   This takes ZECSNC to L2.
3. **3:** ZECS002. It needs:
   - base-displacement addressing;
   - `IC`, `SR`, `BCT`, `SLL`, `SLDL`, `STCM`, `TR`, `XC`;
   - duplicated `X'40'` data (the EBCDIC storage question);
   - `EXEC CICS VERIFY`.
4. **4:** an independent S/390-subset interpreter that cross-checks the lowering instruction by instruction.

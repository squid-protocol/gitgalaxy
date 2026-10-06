---
description: "*2026-10-03. A fourth public COBOL/CICS estate, from a different IBM team than CBSA and GenApp, onboarded to test how"
---
# Estate 4: IBM DBB MortgageApplication

*2026-10-03. A fourth public COBOL/CICS estate, from a different IBM team than CBSA and GenApp, onboarded to test how
far the deterministic translator and the equivalence harness generalise.*

## Why this estate

| candidate | licence | COBOL | verdict |
|---|---|---|---|
| **IBM DBB MortgageApplication** (`IBM/dbb`, `zBuilder/MortgageApplication`) | Apache-2.0 | 6 sources: CALLed subprograms, a CICS/BMS/Db2 screen, a VSAM browse, a generated web-service wrapper | **chosen** |
| Galasa SimBank (`galasa-dev/simplatform`) | EPL-2.0 | no COBOL source in the repository (a simulator; one JCL skeleton) | nothing to translate |
| Rocket / Micro Focus BankDemo | Rocket EULA ("internal demonstration purposes with other Rocket products") | 81 sources | licence does not allow redistributing results or fixtures |

MortgageApplication is small but different in kind: lower-case members, `CBL` cards starting in the sequence area,
`ID DIVISION`, a `PROGRAM-ID` without its period, group USING items, copybooks that COPY other copybooks, a symbolic map
the repository does not ship, Db2's own `SYSIBM.SYSDUMMY1`, an ESDS browsed by RBA, and one source holding nine
programs. Corpus `dbb-mortgage-application` (`tests/cobol_mainframe/corpora.json`), pinned at `ce2c1be5`.

## Ground truth

The answer key (`tests/cobol_mainframe/answer_key/dbb-mortgage-application.json`) covers 5 programs. A blind second
model (Gemini, via `agy`, given only the brief: paths in the public corpus, no key) answered all 45 census questions
the same way as the key (`cross_verify.py census`). EPSCSMRD is left out: nine sibling programs in one source, which
the key cannot yet represent (#4206). The ground-truth ledger triages the engine's 13 disagreements: 10 are the
deliberate unreferenced-by-name census (#2806), and 3 are engine defects, now filed: a qualified MOVE source's
truncation (#4204) and `MOVE ALL X'..'` (#4205).

## Translation survey

`tests/tools/det_survey.py --corpus dbb-mortgage-application`: **202 of 204 statements (99.0%) translate
deterministically.** Of 6 programs, 3 translate whole and 2 with one hole each: EPSCSMRT's dynamic `CALL
WS-CALLED-PROGRAM` and EPSMPMT's `FUNCTION ANNUITY`, in A300-TRY2, which is dead code. EPSCSMRD is refused: its
DATA DIVISION is nine programs'. Before the fixes below, all 6 were refused.

## Cases

| case | program | kind | result | coverage |
|---|---|---|---|---|
| `mortgage-nbrvl` | EPSNBRVL, number validator | CALL, group USING item | **proven**, 15 calls | 3/3 paragraphs, 22/22 branches |
| `mortgage-cmort` | EPSCMORT, mortgage screen | CICS, BMS (generated map), Db2 `SYSIBM.SYSDUMMY1`, CALL EPSNBRVL, LINK EPSMLIST (#4213) | **proven**, 9 scenarios (8 written, plus the automatic SQL-fault task on its SELECT, #4200) | 3/6 paragraphs, 15/21 branches |
| `mortgage-mlist` | EPSMLIST, company list | CICS, BMS (generated map), an ESDS browsed by RBA (STARTBR / READNEXT ... RBA, #4213), the dataset stated by the case | **proven**, 9 scenarios (2 with injected STARTBR / READNEXT conditions) | 5/6 paragraphs, 14/15 branches |
| `mortgage-mpmt` | EPSMPMT, payment calculator | CALL, binary arguments as field values | **not proven on purpose**: the payment is computed through a COMP-1 item, in hexadecimal floating point on z/OS and in truncated decimal on GnuCOBOL. Since #4271 slice 1 the det runtime models HFP and the interest COMPUTE translates, but the payment's `(1 + C) ** N` (N with decimal places) is a floating-point exponentiation IBM does not document bit for bit: a named hole (C6). Its `CBL NUMPROC(MIG)` compiles as NUMPROC(NOPFD) under the estate's Enterprise COBOL 6.1 (C5, #4271) | — |

**Not reached, and why:**
- EPSCMORT's ENTER (indicator '3') and WHEN OTHER paths LINK EPSCSMRT. EPSCSMRT CALLs EPSMPMT through a data
  name the engine does not resolve (`CALL WS-CALLED-PROGRAM`, its value from a REDEFINES table), and EPSMPMT's
  payment is computed in floating point (C6). Its `NUMPROC(MIG)` is no longer the obstacle (C5, #4271).
- A company EPSMLIST lists LINKs EPSCSMRT for its payment (the same reasons), so no scenario lists one: EPSMLIST's
  A600 and the branch into it are not reached, and no record's contents reach an output. The RBA browse is judged by
  its outcomes there, and pinned rule by rule on both sides by `tests/cics_crucible/test_cics_runtimes.py`
  (oracle_assumptions.md X13).
- EPSCSMRD has no case: nine programs in one source, LE condition handlers, channels and containers.

## What it took

**Det translator:**
- Compiler-option cards are read by the engine's own card reader. A card may start in any column from 1:
  `   CBL NUMPROC(MIG)` sits in columns 4–6.
- `ID DIVISION.` reads as IDENTIFICATION DIVISION.
- A group USING item crosses a CALL as the call forge's contract DTO, through the COMMAREA codec a LINK uses: the
  callee's `handleCall(EpsNumberValidation)`, and the caller's CALL site builds the DTO from its storage and writes the
  filled object back (BY REFERENCE). `CobolRef` is imported only where a CALL passes text.

**IR:** a COPY that follows a copied elementary root inside its copybook expands as that root's siblings. EPSMTCOM
is `10 PROCESS-INDICATOR` then `COPY EPSMTINP.` and `COPY EPSMTOUT.`; the COMMAREA DTO was 1 byte and is now the whole
106-byte record.

**Harness (CICS):** the generator emits the CICS exception package only when some program throws or handles one,
and this estate has none. The CICS equivalence test now catches `CicsAbendException` only when the project has it.

**Harness:**
- A CALL case may declare a group USING item's `record`. The Java side gets a DTO built field by field and returns
  it, compared by value as a LINKed COMMAREA is. An argument may be given as field values (binary and packed inputs),
  set on the COBOL side with hexadecimal MOVEs.
- Copybooks are staged under their member names, so `COPY EPSNBRPM` finds `epsnbrpm.cpy`.
- IBM's compiler assumes the period after a `PROGRAM-ID` name; GnuCOBOL does not, so the harness supplies it.
- A screen may name a symbolic map generated from the corpus's BMS (`@bms/EPSMORT.cpy`), on both sides.
- X12 (register): EPSCMORT copies DFHCOMMAREA before it tests EIBCALEN. In its first task, the COMMAREA fields that
  came from nowhere are undefined, so they are left out and counted: 1 field.

## Issues filed

- #4204: engine MOVE truncation misses a qualified source.
- #4205: engine data moves miss `MOVE ALL X'..'`.
- #4206: the answer key can't hold multi-program sources.
- #4213: ESDS browse by RBA, which blocked EPSMLIST (modelled on both sides; mortgage-mlist proven).

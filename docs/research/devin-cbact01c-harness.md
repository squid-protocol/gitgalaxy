---
description: "*Run 2026-10-03 with `tests/tools/devin_port.py`, against our new case `carddemo-readacct` (CardDemo's CBACT01C)."
---
# Devin's CBACT01C ports through the equivalence harness

*Run 2026-10-03 with `tests/tools/devin_port.py`, against our new case `carddemo-readacct` (CardDemo's CBACT01C).
Part of the observational study: `cobol-java-translation-observational-study.md`. Survey and pinned commits:
`devin-carddemo-survey.md` / `devin-carddemo-inventory.json`. The ports are Apache-2.0 workshop exercises; each is
judged against what it attempted, unmodified, through a thin adapter.*

## The case

CBACT01C reads CardDemo's account master and writes three files per account: OUTFILE (107-byte records with a
COMP-3 field and a date reformatted by the assembler routine COBDATFT), ARRYFILE (110 bytes, a table INITIALIZE
partly fills) and VBRCFILE (variable-length: a 12-byte and a 39-byte record per account). Until this case the harness
could not run it: COBDATFT is S/370 assembler. It now runs against a translation of that routine
(`oracle_assumptions.md` A1), with variable-length records (F3), GnuCOBOL's spaces in two bytes COBDATFT never
writes (L3), and a declared tolerance for INITIALIZE's unsigned zero (C10).

**Our det port proves on it:** 13 runs (base plus fault injection), 16/16 paragraphs, 41/44 branches. Translated
three times with the cache off, its 14 Java files are byte-identical each time.

## Results (base run, 6 JVM locale environments)

"Data" = OUTFILE, ARRYFILE, VBRCFILE and RETURN-CODE. "Log" = SYSOUT (the DISPLAY lines). Base-run coverage for
every port: 14/16 paragraphs, 24/44 branches (no port has a seam for the case's fault runs).

| Port (pinned) | Data | Log | Verdict | Root cause of differences |
|---|---|---|---|---|
| codev #13 (and #14, identical Java) | equal, all 6 | equal, all 6 | **PROVEN** | — (VBRCFILE written with a z/OS RDW; re-framed, see adapter) |
| eval arm A | equal, all 6 | 250/752 lines differ | data equal | signed numbers DISPLAYed with a trailing sign (`000000019400+`) where COBOL shows the overpunch (`00000001940{`) |
| eval arm B (+ AWS Transform analysis) | equal, all 6 | same as arm A | data equal | same as arm A |
| #229 (its own GnuCOBOL parity run) | equal, all 6 | 250 differ | data equal | signed numbers DISPLAYed edited (`+0000000194.00`) |
| #168 | equal, all 6 | 750 differ | data equal | DISPLAYs whole raw records, not the program's field lines |
| #214 | equal in 4; **differ under ar-EG / th-TH** | 717 differ | data equal (default locales) | `String.format("%0"+n+"d")` without a locale (`CobolFieldParser.java:94`); edited numbers in the log (`194.00`) |
| #167 | OUTFILE, ARRYFILE equal in 4; differ under ar-EG / th-TH; **VBRCFILE unframed** | 724 differ | partial | VB records written back to back, no length (`vb-unframed`); `String.format` without a locale (`CobolDecimalUtils.java:158`) |
| #220 | none written | none | **crashes** (RC 1) | `new BigDecimal(...)` on a field holding the overpunched sign `{` (`AccountRecord.java:87`) |

ARRYFILE: under C10, several ports (like GnuCOBOL) leave INITIALIZE's zeros unsigned; 100 such bytes per run are
counted and reported, never hidden.

**In short:** of 9 byte-comparable runs (8 distinct programs), 1 is proven end to end, 4 more write every data file
byte for byte (in default locales), 1 is partial, 1 crashes. Every log difference is a choice of how to show a
signed number or what to DISPLAY; the program's DISPLAY lines are part of its observable behaviour, so they count.

## Adapter scope

As #4190: their code unmodified, fetched at pinned SHAs; the case's inputs fed in each port's declared form; outputs
decoded only where the port writes the same bytes in another framing, declared per port (`DECODERS`):
- `vb-lines` (#168: newline-separated VB records), `vb-len2` (2-byte length, no header), `vb-rdw` (codev: a z/OS RDW,
  whose length counts the 4-byte header) — each re-framed as GnuCOBOL frames VB records;
- `lines-hex-packed` (#214: COMP-3 fields written as hex digits) — the hex turned back into the packed bytes.
- `vb-unframed` (#167): nothing marks where a record ends, so it is compared as written and reported as a framing
  error.

A decoder never changes content; a record of the wrong length after decoding is compared as written. During this
run a bug in our `lines-hex-packed` decoder (it did not advance past the text before a packed field) made #214's
OUTFILE look wrong; it was fixed and tested before the results above.

## Structure against verdict

The 26 CBACT01C attempts (scanned with GitGalaxy after #4193), grouped by what the harness found:

| Group | n (distinct) | files | code lines | functions | branches | I/O | guards | codec roles present |
|---|---|---|---|---|---|---|---|---|
| Byte-proven (codev) | 2 (1) | 20 | 970 | 101 | 88 | 21 | 18 | charset, packed, zoned, record codec |
| Data equal, log differs (#229, #168, #214) | 3 | 6 | 406 | 29 | 33 | 19 | 4 | packed, zoned, record codec in 1 of 3 |
| Partial (#167) | 1 | 6 | 403 | 22 | 36 | 27 | 2 | record codec |
| Crash (#220) | 1 | 7 | 541 | 92 | 42 | 17 | 13 | none |
| Text output, not byte-comparable by design | 19 | 9 | 371 | 30 | 29 | 20 | 3 | zoned in 5, record codec in 1 |

(Medians. The eval arms port three programs in one project and are not in this set.)

**What can be stated, carefully (n is tiny):**
- The one fully proven program is also the largest and the only one carrying a complete, explicit codec kit (EBCDIC
  charset, packed, zoned, record framing) and the most guards. Its 970 lines are close to our det port's 1,047-line
  service for the same program: the only Devin attempt that reproduces CBACT01C byte for byte converged on roughly
  the det port's size.
- It is also the attempt built around an independent oracle (codev #14 adds a Python program that derives the
  expected bytes). The two other attempts that ran GnuCOBOL or a golden harness (#229, the eval arms) also get
  every data file right.
- Size alone does not predict correctness: the crashing attempt (#220) is the second-largest by functions.
- Structure does not separate "data equal" from "partial": #167 and #168 are near-identical in size and shape; one
  frames its VB records and one does not. That is a byte-level property only execution sees.

## Caveats

Base runs only (24/44 branches); GnuCOBOL is the oracle (`oracle_assumptions.md`), and L3's two bytes are GnuCOBOL's
spaces; the survey's 8 fixed-width ports (a field-by-field tier) were not run in this pass.

## Reproducing

```sh
python tests/tools/det_port.py run carddemo-readacct --faults all --work <scratch>
python tests/tools/devin_port.py --work <scratch> --case carddemo-readacct --jdk21 <a JDK 21>
```

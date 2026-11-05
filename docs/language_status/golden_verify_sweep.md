# Golden-verify sweep: killed mutants vs the generated regression suite (#4052, slice 5)

`golden_export.py prove-mutant` (slice 4) runs the det port and chosen mutants on a batch case's inputs and checks each
against the exported COBOL golden files, by the Python `check` and by the generated `GoldenCheck.java`. It accepts only
mutants the det-mutation ledger records as KILLED by the equivalence proof. This page records the sweep over burned
CardDemo batch cases (2026-11-05, ports translated at origin/main `7e88adfa3`, up to 4 killed ids per case sampled evenly
across the ledger's `killed` list, all fault runs unless noted).

| Case | Program | Unmutated port | Sampled killed mutants | Result |
|---|---|---|---|---|
| carddemo-readcard | CBACT02C | 0 problems | 4 | all 4 fail; two (DEL) fail only on fault runs (a `--faults none` run passes them, as the proof also needs its fault runs) |
| carddemo-readcust | CBCUS01C | 0 problems | 4 | all 4 fail |
| carddemo-readxref | CBACT03C | 0 problems | 4 | all 4 fail |
| carddemo-intcalc | CBACT04C | 0 problems | 4 | all 4 fail |
| carddemo-dailyval | CBTRN01C | 0 problems | 4 | all 4 fail |
| carddemo-cbstm03a | CBSTM03A (calls CBSTM03B) | 0 problems | 4 (`00888e3a98`, `38d1809c60`, `79a44b39b4`, `adad250a69`) | all 4 fail; the LIT mutant fails on the main run only (HTMLFILE byte 3800), the other three on fault runs (and `adad250a69` on SYSOUT only) |
| carddemo-sort-combtran | DFSORTST (sort step) | 0 problems | 4 (`0338a9a201`, `5d30145e45`, `b284e01e99`, `feb2c1c210`) | all 4 fail, on the main run and on `fault-sortin1-eof` (a `--faults none` run fails them too): each makes the port abend with an `ArrayIndexOutOfBoundsException`, golden has return code 0 |
| carddemo-sort-tranrept | DFSORTST (sort step) | not reached (port PROVED) | 4 tried (`24cf703bd4`, `6245c07f62`, `b6a26a34d2`, `dee3a1ad0b`) | not judged: `prove-mutant` printed no verdict in 1100 s and was stopped |
| carddemo-readacct | CBACT01C | **2 problems** (ARRYFILE byte 79, SYSOUT) | 4 tried | not judged: the unmutated port already fails the byte check |

Python and generated-Java checks agreed on every port in the five passing cases.

## carddemo-readacct: a declared difference the byte check does not know

The case declares `zoned_sign_equivalent: ["ARRYFILE"]` (register C10: INITIALIZE's zeros are unsigned under GnuCOBOL,
the preferred C sign on z/OS). The port writes byte `0x7B` (`{`, the C sign) where the golden file has `0x30`; SYSOUT also differs (Java 41998 bytes, golden 42230), cause not
examined here. The equivalence proof accepts this; `check` is byte-exact by design (stricter, never
looser), so the suite reports a difference on a correct port. Nothing was loosened here: the regression suite for such a
case needs the harness's declared differences, which is the field-level comparison slice of #4052.

## Not covered

Only a sample of each case's killed ids was run (not every killed mutant); only seven passing cases (the five above plus cbstm03a and sort-combtran, ports translated at `31f8cba79`) plus readacct were
swept of the 27 CardDemo cases with a det-mutation ledger. Cases with `kind` not batch, `db2` or `ims` are refused by the tool.

carddemo-cobswait (CBL wait program, 16 killed ids) was tried and not judged: its `prove-mutant` run produced no output in 20 minutes and was stopped; a `det_port.py run` proved the port (4/4 translated, PROVED), so the time is in the mutant runs, not the translation.

2026-11-05, slice 10: carddemo-cobswait re-run with `--faults none` (main run only; the port was freshly translated by `det_port.py run --faults none`, 4/4 translated, PROVED, because the case has no committed port directory). The unmutated port passes (0 problems) and all 4 sampled killed mutants (chosen evenly from 16: `0626e19446`, `2d3dfcc0b2`, `a338a4e0fc`, `fa005480d7`) fail, by the Python and the generated Java check alike. All four are constant edits to the 8-byte `PARM-VALUE` or 2-byte return-code fields that abend the port with `ArrayIndexOutOfBoundsException` against golden return code 0, so they are the easy class. The earlier no-verdict was therefore the fault runs, not the main run; fault runs were not retried here, so a mutant only a fault run would catch is outside this result, and the ledger's survivors are untouched.

carddemo-sort-combtran (2026-11-05, port translated at `16108a109`, 2/2 statements, PROVED; 4 of 68 killed ids sampled evenly): the unmutated port and the generated Java check agreed. All four sampled mutants are constant or index edits that crash the port, so they are the easy class; the ledger also records 126 survivors, which this sweep does not touch.

2026-11-05, slice 8 (ports translated at `3bddfcb09`): carddemo-cbstm03b (CBSTM03B, the subprogram CBSTM03A calls) and carddemo-codate01 (CICS) are refused by `prove-mutant` ("only a plain batch case is wired in this slice"; case kinds `call` and `cics`), so neither was judged, and carddemo-dateutil is also kind `call`. carddemo-sort-tranrept (batch, 19/19 statements, PROVED by `det_port.py run`) was tried on 4 of its killed ids chosen evenly; the run generated the Java project for each mutant and was stopped at 1100 s without a verdict, so it is not judged (the same shape as cobswait; the translation itself finished, so the time is in the mutant runs, not measured further).

2026-11-05, slice 9: carddemo-sort-tranrept re-run with `--faults none` (the main run only; the committed port `tests/equivalence/carddemo-sort-tranrept/port` at `94b586851`, not a fresh translation). The unmutated port passes (0 problems) and all 4 sampled killed mutants fail, by the Python and the generated Java check alike: `24cf703bd4` (NEG, SORTOUT differs at byte 350, Java 350 bytes vs golden 8750), `6245c07f62` (CON, SORTOUT byte 9), `b6a26a34d2` (CON, abends with `ArrayIndexOutOfBoundsException`, golden return code 0), `dee3a1ad0b` (CON, SORTOUT byte 7). This judges the case on its main run only: the slice-8 run with all fault runs produced no verdict in 1100 s, and the fault runs were not retried, so a mutant that only a fault run would catch is out of this result. All other plain-batch CardDemo cases with a det-mutation ledger are now swept or recorded above except carddemo-cobswait (not judged); carddemo-paudblod and carddemo-paudbunl are IMS cases and `golden_export.py` refuses them.

2026-11-05, slice 11: carddemo-sort-tranrept re-run with ALL fault runs (the case's one fault, `sortin-eof`) using the new `--one-jvm --mutant-timeout 180` path, in 6 min 6 s (the same run without them gave no verdict: 1100 s in slice 8, and 21 min then an abort in this slice). The committed port at `94b586851` passes (0 problems) and all 4 sampled killed mutants fail, by the Python and the generated Java check alike: `6245c07f62` (CON, SORTOUT byte 9, main run), `dee3a1ad0b` (CON, SORTOUT byte 7, main run), `b6a26a34d2` (CON, abends with `ArrayIndexOutOfBoundsException` on `fault-sortin-eof`, golden return code 0) and `24cf703bd4` (NEG, line 365: its `fault-sortin-eof` Java run loops until the 180 s bound, so it fails by "did not finish", not by a compared output; slice 9 saw it differ on the main run at SORTOUT byte 350). The hang is counted as a failure on the harness's own reading (a run that gives no outputs cannot match golden); the 180 s bound applies to mutants only. The ledger's survivors are untouched.

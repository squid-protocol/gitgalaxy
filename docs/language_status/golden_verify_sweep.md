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
| carddemo-readacct | CBACT01C | **2 problems** (ARRYFILE byte 79, SYSOUT) | 4 tried | not judged: the unmutated port already fails the byte check |

Python and generated-Java checks agreed on every port in the five passing cases.

## carddemo-readacct: a declared difference the byte check does not know

The case declares `zoned_sign_equivalent: ["ARRYFILE"]` (register C10: INITIALIZE's zeros are unsigned under GnuCOBOL,
the preferred C sign on z/OS). The port writes byte `0x7B` (`{`, the C sign) where the golden file has `0x30`; SYSOUT also differs (Java 41998 bytes, golden 42230), cause not
examined here. The equivalence proof accepts this; `check` is byte-exact by design (stricter, never
looser), so the suite reports a difference on a correct port. Nothing was loosened here: the regression suite for such a
case needs the harness's declared differences, which is the field-level comparison slice of #4052.

## Not covered

Only a sample of each case's killed ids was run (not every killed mutant); only the five passing cases plus readacct were
swept of the 27 CardDemo cases with a det-mutation ledger. Cases with `kind` not batch, `db2` or `ims` are refused by the tool.

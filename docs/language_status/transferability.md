# Transferability: burned estates vs. code the translator was not built on

> Dated historical snapshot (2026-10-22). Live numbers: [progress](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/progress.md).
> The non-burned rate is a scheduled, counts-only series (#6064, `docs/agents/census-nightly.md`):
> `python tests/tools/cics_census.py history show --generated --series census`. Nothing below is a current rate.

An honest record of how far the translator built on the six burned estates carries over to code it was not built on
(owner framing, 2026-10-22: the first six estates did not fully transfer to a seventh; we have depth on six, not yet
breadth). It exists so the next first-contact scan has a baseline and burned-estate numbers are not read as general
capability.

## The peek

On 2026-10-22 the orchestrator ran `det_survey.py --no-compile` (translation only, counts only) over the nine census
repos and the two pinned non-burned corpora `dsf` and `zopeneditor-sample`, and grepped `dsf`'s PL/I files for the era
tells of `era_tags.py` (counts only). It built no case and changed no code. A decision to burn `dsf` was reversed the
same evening: `dsf` and `zopeneditor-sample` stay non-burned, and no fix derived from them lands before their real
first-contact scan. Their hole reasons have been seen, so that scan is not fully blind; report it with that caveat.

## Numbers (main `082aba881`)

| set | programs | translated whole | statements translated |
|---|---|---|---|
| Burned, 6 estates (evidence report) | 129 | 123 (95%) | n/a |
| Burned, CICS programs (census baseline) | 106 | 103 (97%) | n/a |
| Non-burned, 9 census repos | 40 | 8 (20%) | 568 / 647 (87.8%) |
| census, translatable as supplied (a) | 19 | 8 (42%) | n/a |
| `zopeneditor-sample` (batch COBOL) | 5 | 2 | 595 / 632 (94.1%) |
| `dsf` COBOL (batch) | 7 | 0 | 231 / 318 (72.6%) |
| `dsf` PL/I (575 EXEC CICS files) | 1,473 | 0 (COBOL-only translator) | 0 |

(a) Excludes 3 non-programs (screen captures, a copy member), 9 source defects (text past column 72) and 9 missing
inputs (an absent user copybook; a vendor copybook never shipped).

Over time the non-burned whole-rate went from 24% on 2026-10-07 (5 of 21, CICS programs only) to 20% on 2026-10-22
(8 of 40, all COBOL), while burned CICS went from 70% to 97%. The denominators differ, but nothing shows the
burned-estate gains carrying over.

## Gaps, in order of size

| # | gap | status (pointer, check before relying) | burned-estate need |
|---|---|---|---|
| 1 | Language breadth: a production estate that is ~99% PL/I is ~0.5% covered; CICS capability is COBOL CICS | #6066 | none (frontier) |
| 2 | Batch outside the JCL-driven shape: the batch runtime is emitted only when the estate holds an application JCL job | #6065 | none (all six ship JCL) |
| 3 | Statement families the six never used: `WRITE ... ADVANCING`, JSON GENERATE/PARSE, `WEB WRITE HTTPHEADER SESSTOKEN`, SQL ROLLBACK inside CICS, variable-length records without RECORD VARYING | #6065 (first), rest unfiled | none |
| 4 | Input completeness: about half of census refusals are missing copybooks or source defects. We refuse correctly; the first-contact rate pays for it | none: policy (refuse by name) | none |
| 5 | Era profile: burned estates lean era 2-4; the PL/I CICS seen is era 1 (`HANDLE CONDITION`, DL/I, `HANDLE AID`) | #5856-class for COBOL; PL/I untouched | none |
| 6 | What does transfer: the statement core. Where a program translates at all, 82-94% of statements come through, and holes are named | n/a | n/a |

## Update 2026-10-24 (main `7bdf81d93`): #6065 landed, so `dsf` is no longer a blind first contact

The statement above that no fix derived from these corpora lands before their first-contact scan no longer holds.
#6065 (batch file I/O without an application JCL job, `WRITE ... ADVANCING`) was written from the peek, was parked on
2026-10-22, and was closed as completed on 2026-10-23 by #6111 (slice 1). Its own `det_survey.py --no-compile` run on
the pinned corpora, as recorded on the issue (counts only, no commit named there; the fix is #6111):

| corpus | before (peek, `082aba881`) | after #6111 (2026-10-23) |
|---|---|---|
| `dsf` COBOL (batch) | 0 / 7 whole, 231 / 318 statements | 0 / 7 whole, 309 / 334 statements |
| `zopeneditor-sample` | 2 / 5 whole, 595 / 632 statements | unchanged |

Read this as: the `dsf` batch statement rate moved from 72.6% to 92.5% (309 / 334) with no program becoming whole, and
the statement denominator changed (318 to 334) because the translator now emits more of the file. Both corpora have now
been looked at twice with their hole reasons in hand, so any later scan of them is a re-measurement, not a first
contact. The honest first-contact number for a seventh estate still has to come from an estate nobody has read
(the blind estate draw). The table in "Numbers" is unchanged and stays the 2026-10-22 baseline.

## Update 2026-10-25 (main `a3f1ac8ca`): burned side re-read, non-burned side still unmeasured

Burned estates only. From the generated progress page (evidence reports of the six burned estates; the oracle is
GnuCOBOL plus IBM documentation, not z/OS):

| burned estates | programs | translated whole | L2+ (executed equal) | L4+ (every net branch) | L5 |
|---|---|---|---|---|---|
| 6 estates | 129 | 123 | 120 (93.0%) | 83 (64.3%) | 0 |

The six programs that are not whole each have a non-translator blocker: two source defects IBM rejects (#5866), two
CICS Assembler members the COBOL translator refuses (#5859), two held by an owner ruling or by a need for captured
z/OS results (#5106, #5867). The 123 of 129 matches the 2026-10-22 row, so the burned side did not move in the
whole-translation count; it moved up the ladder (proof depth), which is depth on six estates, not transfer.

Gap pointers re-checked on 2026-10-25: #6065 closed, #5856 closed, #6066 open (frontier), #6064 open. No burned
program needs any gap in the table above. The non-burned rate is still the 2026-10-22 peek: the first scheduled census
run (#6064) has not run, so no newer non-burned number exists and none is claimed here.

## Going forward

- `dsf` and `zopeneditor-sample`: their next scan is a re-measurement (see the 2026-10-24 update), not a first contact.
  Record it here, then decide on #6066.
- Breadth is the fix for transfer: more estates scanned at first contact (the blind estate draw), not more depth on the six.

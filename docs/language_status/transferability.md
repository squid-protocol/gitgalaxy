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

## Update 2026-11-16: the first-contact rows this record was waiting for

Two measurements of code the translator was not built on have closed since the 2026-10-22 peek. Neither changes the
"Numbers" table above, which stays the 2026-10-22 baseline. Both are counts only; the oracle is GnuCOBOL plus IBM
documentation, not z/OS.

| measurement | what it is | first contact | at close-out |
|---|---|---|---|
| Census mock trial (#7709, closed 2026-11-07, final write-up on the issue) | the 40 census programs (39 after the inventory fix #7901), tools only, L1 | 8 of 40 whole at T0 (frozen prediction: 25 of 40) | **13 of 39 whole (33%)**, 37 of 39 accounted (the ceiling); the 2 unaccounted are the z/OS Connect BAQ programs by owner ruling (#7900) |
| Blind estate trial 1 (#8073, `ibm/example-health-apis`, drawn blind, closed 2026-11-12) | 29 programs, L1 then L2 then proof | **0 of 29 whole** (1 of 29 accounted, in hindsight) | 25 of 29 whole (86%), 28 of 28 eligible cased (L2); **first-try det proof 23 of 28 (82%)** at frozen engine `5e4575d77` |

What they say about transfer, stated plainly:

- **Burned-estate tuning did not lift unseen code.** The census trial scored 0 programs of lift between 2026-10-24 and
  its T0, while burned CICS sat at 97%. Blind 1 translated 0 of 29 whole at first contact.
- **Plumbing, not semantics, decided first contact.** On Blind 1, 28 of the 29 first-contact failures were copybook
  resolution, none was unmodelled semantics, and all 17 real SQL statements translated. On the census trial, most of the
  gain in "accounted" came from naming source defects, not from translating.
- **Our measurement was wrong in both directions, twice.** Blind 1's "10 EXEC SQL programs" were duplicates carrying
  listing line numbers, and 6 of 7 "missing copybook" labels were our resolver bug (#8074). The census trial's
  inventory counted a copy member as a program (#7901). Report first contact and close-out together: 86% alone
  misrepresents what a cold estate does to the system.
- **The remediation loop works fast; the first try does not.** Blind 1 went from 0 to 86% whole in about a day of
  tools-only work (25 of 29 at 2026-11-08), and the census trial from 8 to 13 of 39 in about three days (104 PRs).
- **The proof number is n=1 and det-only.** 23 of 28 is one estate at one engine version (Run B, harness at current
  main, Amendment 4). Run A on the frozen harness proved 5 and left 23 unjudged by a harness defect, so it is not a
  rate. The 5 misses were two engine bugs, both since fixed (#8225, #8246, #8269); the current engine proves 28 of 28.
  The det-then-model companion figure is still owed (#8372). The estate is now a development estate (#8157).

Gaps 1 to 3 in the table above are unchanged: `dsf` and `zopeneditor-sample` are still re-measurements, not first
contacts, and PL/I (#6066) is untouched. The scheduled non-burned series (#6064, now census nightly) is the
continuing number; no rate below is current.

## Going forward

- `dsf` and `zopeneditor-sample`: their next scan is a re-measurement (see the 2026-10-24 update), not a first contact.
  Record it here, then decide on #6066.
- Breadth is the fix for transfer: more estates scanned at first contact, not more depth on the six. Blind 1 is done and
  can never be drawn again; the next draw is gated by the prep issues #8111-#8113 and #8412, with its forecast frozen after
  eligibility is applied (#8321).

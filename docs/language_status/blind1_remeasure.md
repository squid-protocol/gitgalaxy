# Blind trial 1: re-measure after the COPY resolver fixes (#8074)

Counts only. Nobody read, copied or edited the estate's source; the survey tool ran over the pinned clone as it is.
This is a dated measurement. For the state of the trial, read #8073.

## Measurement

| | |
|---|---|
| Engine commit | `4c50947dd` (after #8108, #8110, #8118, #8112 / #8115) |
| Command | `cics_census.py survey --baseline --blind-root <clone> --sha HEAD --no-fetch --force` |
| Programs (the basis, owner restatement 2026-11-08) | 29 |
| Rows that are not programs (compile listings, copies) | 29, listed and not counted |
| **Translates whole (L1)** | **25 / 29** (86%) |
| Refused whole | 1 / 29 |
| One gap away from whole | 3 / 29 |
| Rows with an unresolved COPY although the estate holds the member | 0 |

The first report counted 58 rows, of which 29 were compile-listing copies. That basis no longer exists in the tool:
the inventory excludes the copies (#8112), so a "whole / 58" cannot be measured at this commit. Per program: T0 was
0 / 29, the L1 close-out at `3b5c59556` was 25 / 29, and this commit is 25 / 29 (no change from #8115 or #8118, as expected:
they fix inventory and add a test matrix).

## What is left at L1 (aggregate)

| Gap | Programs |
|---|---|
| EXEC CICS class property the port cannot convert (COMP-1 / COMP-2 to Double / Float; #8076, #8088) | 3 |
| A copybook the estate does not hold | 1 |

## Independent check of the copybook rows

The resolver is not its own witness (lesson of #8073). A plain file-name search over the clone, case-insensitive and
with any extension, finds 0 members for the one refused program's copybook, so the refusal is a clone fault and not a
search miss. No `CopyUnresolved` row remains.

## Burned estates

No burned-estate program needs the three DTO programs' gap: the survey lists 0 burned programs under it
(`only_burned: 0`).

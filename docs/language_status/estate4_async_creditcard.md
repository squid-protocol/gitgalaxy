---
description: "*2026-10-07. cicsdev's CICS asynchronous API credit-card example, promoted from a counts-only census clone to a pinned development (burned) estate."
---
# Development estate: cicsdev async credit-card application

*2026-10-07. The repository `cicsdev/cics-async-api-credit-card-application-example` (Apache-2.0, IBM Corp. 2016 sources)
was a counts-only census clone of #4270 (never a blind-estate candidate: it sat on `estate4_draw.INELIGIBLE_LIST`).
The owner promoted it to a pinned corpus so its eight CICS service programs and two front ends can be proven as a
development estate. It is BURNED: it is read, ported and committed from now on.*

## What it is

Pinned corpus `cics-async-api-credit-card-application-example` (`tests/cobol_mainframe/corpora.json`) at
`c32c52fcfd8d587b352f67959a5dfb0d11dbd8bb`. Ten COBOL sources in `src/`: ASYNCPNT (the front end that starts the
services in parallel with `EXEC CICS RUN TRANSID`, then `FETCH`es them) and SEQPNT (the same flow with `LINK`), plus the
services CRDTCHK, GETNAME, GETADDR, CSSTATUS (which LINKs GETPOL and GETSPND), CSSTATS2, GETPOL, GETSPND and UPDCSDB.
Channels and containers carry the data. The repository ships no copybooks, BMS maps, JCL or CSD deck: the CICS resources
are Eclipse bundle definitions (`etc/CICS_bundles`), which no reader here takes. Sources use CRLF line ends, one-digit
level numbers (`1 PROG-NAMES.` / `2 GETPOL PIC X(8) VALUE 'GETPOL  '.`), `LOCAL-STORAGE`, and end `END PROGRAM 'NAME'.`

## Burned, and the census

`estate4_draw.BURNED_NAMES` now holds the repository name, so `cics_census.py` counts its programs as burned and
`equivalence_env.census_repos` (INELIGIBLE_LIST minus burned) stops cloning it. The name stays on INELIGIBLE_LIST (the
frozen draw excludes it either way; the draw seed hashes only `estate4_candidates.json`, which this PR does not touch).
Survey totals before and after are in the PR body: the program total is unchanged, eight programs move from non-burned to
burned.

## Ground truth

The answer key (`tests/cobol_mainframe/answer_key/cics-async-api-credit-card-application-example.json`) covers the 10
programs: units and extents (`llm_verified`, checked against the source by the drafting model), program ids, calls,
and a blind census of every program by a second model family (Gemini via `agy`; 14/14 units, 10/10 calls, 0
disagreements), so the programs are `cross_verified`. Every other channel section (CICS resources, task control, units of
work, data moves, dynamic targets) is drafted and left unsigned (`draft` in the scoreboard).

Two key-reader defects surfaced and were fixed (key errors are not logged as product defects): a one-digit-level `VALUE`
was not read, so a `LINK PROGRAM(NAME)` through `1 PROG-NAMES` stayed unresolved, and a lone program's last unit extent
ran over its `END PROGRAM 'X'.` line.

## Ledger

The ground-truth ledger triages 20 disagreements: the deliberate unreferenced-by-name census (#2806; every
`MAINLINE SECTION` is named nowhere else). The 158 forge disagreements and the 166 refraction `schema_column` deltas
were one forge defect, #4626 (`cobol_schema_forge` read no record fields from one-digit level numbers); fixed, the forge
reads all 158 and both ledgers lost them. The fact cross-check's 20 translator extent disagreements (the last unit ran
over `END PROGRAM 'X'.`, #4630) were the referee adapter's, fixed the same way.

## Not here

Translation and equivalence cases for these programs are a separate change (the equivalence harness needs the
`RUN` / `FETCH` and channel features first); this PR pins and keys the estate only.

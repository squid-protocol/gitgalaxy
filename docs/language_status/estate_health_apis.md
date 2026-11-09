---
description: "*2026-11-09. IBM example-health-apis, the first blind estate (trial-001), promoted to a pinned development (burned) estate after trial start."
---
# Development estate: IBM example-health-apis

*2026-11-09. The repository `ibm/example-health-apis` (Apache-2.0) was the first blind estate: trial-001 of #8073 started
on it (#8119, PR #8154), so its first-contact numbers are measured and recorded. Under Amendment 3 of the pre-registration
(#8141) it is now promoted to a pinned corpus and BURNED: it is read, keyed and may carry cases from here on. The
first-contact numbers stay as measured; nothing here edits them.*

## What it is

Pinned corpus `example-health-apis` (`tests/cobol_mainframe/corpora.json`) at
`9cfe321e2028f4f91a780bbb7d4cbb8393565f76`. 29 COBOL CICS programs under `HCAZ_Source/IBMUSER.ZMOBILE.COBOL/` (the
health-care patient, medication, visit and threshold APIs, DB2 access programs and the BMS menu front end), with their
copybooks and the BMS maps (HCMAPS). The excerpt (`refraction_excerpts/example-health-apis/`) carries 7 files.

## Burned, and the census

`estate4_draw.BURNED_NAMES` holds the repository name, so `cics_census.py` counts its programs as burned. The frozen draw
is untouched (`estate4_candidates.json` is not edited). Program totals before and after are in the PR body, counts only.

## Ground truth

The answer key (`tests/cobol_mainframe/answer_key/example-health-apis.json`) covers the 29 programs: units, extents,
program ids and calls, checked against source and then by a two-batch blind census (Task A agreed on all 186 units; the
only disagreements were the SQLCA convention, each ruled with a written reason). Every other section (SQL access, data
moves, commarea, CICS resources, BMS, JCL) is drafted and left unsigned.

The repository ships `COPYLIB/SQLCA.cpy`; the engine reads the shipped copy while the key treats SQLCA as
system-supplied. Both readings are recorded (ledger cause `system_copybook_resolved_to_shipped_copy`).

## Ledger

61 ground-truth mismatches are triaged in `ground_truth_ledger.json`. One engine defect surfaced: a MOVE whose source is
followed by a comma is missed (D057 in `field_testing.json`, draft tier, not fixed here).

## Not here

Equivalence cases and translation for these programs are separate changes.

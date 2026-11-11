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

## Equivalence cases (#8121)

*2026-11-11.* The L2 goal is the 28 eligible programs (owner ruling 2026-11-08: HCP1BU01 COPYs `LGCMAREA`, which the
clone does not ship, so it is out of scope by the missing-source rule). Each program has a case under
`tests/equivalence/health-<program>/`, landed one family per PR. Levels are read from the evidence report on the
`generated` branch, never from this page. Read it with:
`python tests/tools/generated_branch.py show docs/language_status/evidence_report/example-health-apis/report.md`.

| family | programs (cases) | PRs |
|---|---|---|
| Menu and errors | HCAZMENU, HCAZERRS | #8191 |
| Visit | HCAVDB01, HCV1BA01 | #8217 |
| Threshold add | HCATDB01, HCT1BA01 | #8220 |
| Patient add | HCAPDB01, HCAPDB02, HCP1BA01 | #8222 |
| Medication add | HCMADB01, HCMADB02, HCMABA01 | #8224 |
| Inquire (patient, visit) | HCIVDB01, HCIPDB01, HCV1BI01, HCP1BI01 | #8227 |
| Medication inquire | HCIMDB01, HCM1BI01 | #8233 |
| Threshold inquire | HCITDB01, HCT1BI01 | #8254, #8270 |
| Screen front ends | HCMAPL01, HCM1PL01, HCP1PL01, HCT1PL01, HCV1PL01 | #8229, #8235, #8238, #8231, #8247 |
| REST wrappers (validation and abend paths) | HCPRESTW, HCTRESTW, HCMRESTW | #8264 |

## Not here

* **HCP1BU01** (patient update): out of scope, `LGCMAREA` absent from the clone.
* **REST wrapper success paths** (HCPRESTW, HCTRESTW, HCMRESTW): the three cases stop before any LINK or PUT of
  `DFHWS-DATA` / `DFHRESPONSE`. A PUT of a DFH container other than `DFHREQUEST` / `DFH-BODY` / `DFH-DATA` is refused by
  name (register X42), and the LINK targets HCP1BU01 and its siblings are not in the estate. Finishing them needs code or
  an owner ruling (question o261); this page does not decide it.
* L3 and L4 work (paragraph and branch coverage) for these programs is a later slice of #8121. HCT1PL01 gained PF3,
  PF12, CLEAR and MAPFAIL scenarios and now runs every paragraph; its one open branch (`EIBCALEN > 0`) is a harness
  limit (a `layout_only` COMMAREA cannot state an incoming COMMAREA), not an infeasible outcome. HCM1PL01's medication
  list cannot be run by the oracle: `HCIMDB01` stores `CA-MEDICATIONS (n)` while the `OCCURS 0 TO 50 DEPENDING ON`
  count is still 0, which GnuCOBOL refuses (register X8). Levels are read from the generated report, not this page.
* **The grouping is closed.** Every eligible program sits in one family above and every family has landed. What is
  left of #8121 is not case data: the REST success paths (code or the owner ruling), `det/hfp.py` for the DTO
  Double / Float programs (#8076), and the L3 / L4 climb.

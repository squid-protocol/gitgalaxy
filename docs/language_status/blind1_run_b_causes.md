# Blind 1, Run B: why five programs were not proven (#8322, part of #8073)

Run B proved the det port's first attempt for 28 eligible programs with the harness at main: 23 proven, 5 not proven. This page
assigns each of the five a cause, with the commit that fixed it. Attempt 1 is unchanged and stays the measurement: nothing
below re-books a first try, and the trial ledger is not touched (the registered system is the `anthropic` backend, so a det run is not
one of its attempts).

The frozen engine is `5e4575d77` (v2.12.0). The five fail for one reason: the det translator or runtime at that engine had a defect
that main has since fixed. Cause for all five: **`engine`** (ours, a fix commit exists; not the model, the ticket, the generator or the harness).

| program | what the frozen engine did | fix on main (after `5e4575d77`) | blocker row |
|---|---|---|---|
| `HCIPDB01` | IBM's `SQLCA` (SQLCODE `PIC S9(9) COMP`) written little-endian: +100 read back as 1677721600, so `EVALUATE SQLCODE WHEN 100` took `WHEN OTHER` (the Java LINKed `HCAZERRS` where the COBOL RETURNed) | `c81d13379` (#8225) | P126 |
| `HCIMDB01` | same | `c81d13379` (#8225) | P126 |
| `HCIVDB01` | same | `c81d13379` (#8225) | P126 |
| `HCITDB01` | same, and the standalone `Sysout` ignored `gitgalaxy.sysout`, so the DISPLAY bytes never reached the compared file | `c81d13379` (#8225), `a6726f5a4` (#8246) | P126 |
| `HCMADB02` | `MOVE 08000000 TO WS-START-NUM-TIME` lost its leading zero (hour 80): H2 rolled the date over where GnuCOBOL kept 08:00:00 | `34f19ce25` (#8269) | P127 |

SQLCODE 0 reads the same in either byte order and the 904 scenario takes `WHEN OTHER` in the COBOL too, so those scenarios matched; the
not-found, deadlock-913 and SQL-error scenarios were the ones that differed.

## Evidence

Reruns on a scratch copy, one attempt each, the harness at main (the same instrument as Run B), `det_port.py run`:

| engine | proven | not proven |
|---|---|---|
| main | 5 | 0 |
| frozen `5e4575d77` + `c81d13379` + `34f19ce25` (the fix patches applied, nothing else from main) | 4 (`HCIPDB01`, `HCIMDB01`, `HCIVDB01`, `HCMADB02`) | 1 (`HCITDB01`, differs) |
| the same + `a6726f5a4` | 5 | 0 |

The `HCITDB01` row is why its cause names two fixes: the first two alone left it differing, the third closed it.

## What this is not

* Not a re-proof of the trial: these reruns used an engine that is not the frozen one, so they are cause evidence, not a measurement.
* `HCMABA01` shares P127 but was proven in Run B: its case has no arm that reaches the literal.
* No ledger close, no `Trial-Cause:` trailer: the fixes landed before this page and carry other issue numbers. The det-then-model
  figure and the #8073 post are open.

# Blind 1: the det port's first-try proof run (#8322, part of #8073)

One attempt per eligible program (28; `HCP1BU01` is out of scope, source missing). The translator is the deterministic
COBOL-to-Java port (`--backend det`) at the **frozen engine** `5e4575d77`, tickets regenerated from it (`trial.py tickets`).
Nothing was changed after the first run: attempt 1 is the measurement. The model backend the trial registered
(`anthropic`, `claude-sonnet-5-5`) was **not** run: that figure needs an API key and spend, and is not in this record.

The same ports were proved twice, each on its own copy of the project (one log never holds two verdicts of one attempt):

| run | instrument | why it is reported |
|---|---|---|
| A | frozen harness `c58cb3a69` (the harness files restored from it onto main; the 28 cases did not exist at that commit and are taken as they are) | the registered system, reported first (Amendment 4) |
| B | harness at current main | the measuring instrument as repaired since |

## Run A (frozen harness)

| group | programs |
|---|---|
| proven first try | 5: `HCAZERRS`, `HCAZMENU`, `HCMRESTW`, `HCPRESTW`, `HCTRESTW` |
| not proven (the oracle compiled and judged) | 0 |
| not judged (cause `harness`) | 23: the proof command exited 1 and wrote no report |
| flagged (oracle compiled although `inline_exec_copies` #8217 changes its reference) | 0 |

All 23 stop at the same line before any COBOL or Java runs: `RuntimeError: Db2: SQL0104N An unexpected token "DSN SYSTEM(DB1S)
RUN  PROGRA" was found`, the frozen harness's Db2 DDL step reading the estate's DSN run card as DDL. Checked per program
(the 23 listed in `run_summary.json`). These 23 are **not port failures** and not a proof rate: nothing judged them.
The 18 programs whose compiled reference differs without #8217 (measured, not listed by hand) sit among them; none of the
18 was judged by an oracle that compiled, so the flagged group is empty.
**n=1 caveat:** the 5 are the programs with no Db2; three are the REST wrappers, which have error-path scenarios only, so
they say little about the happy path.

## Run B (harness at main)

| group | programs |
|---|---|
| proven first try | 23 |
| not proven (oracle compiled) | 5: `HCIMDB01`, `HCIPDB01`, `HCITDB01`, `HCIVDB01`, `HCMADB02` |

23 of 28 (82%), one attempt each, det port only. The four `HCI*DB01` programs share one shape: on `not-found`, the
SELECT-deadlock-913 and the SQL-error scenarios the Java LINKs and writes the error queues where the COBOL RETURNs
(0/10 events equal), while the 904 scenario matches. `HCMADB02` matches every event (`twice-a-day`, `three-times-a-day`,
`four-times-a-day` 2/2) but its java-facade pass reports `differs`. A cause is **not assigned**: that needs reading the
translator, and a cause other than `model` needs a fix commit (`Trial-Cause:` trailer). Candidates: the det runtime's
SQLCODE +100 handling (generator or engine).

## Headline and det-then-model (status 2026-11-12)

Reported in this order (Amendment 4), never as a bare rate:

| | proven first try | not proven (oracle judged) | not judged (cause `harness`) | flagged |
|---|---|---|---|---|
| Run A, frozen harness (first) | 5 of 28 | 0 | 23 | 0 |
| Run B, harness at main | 23 of 28 | 5 | 0 | 0 |

* **det-translator-only** (the registered headline, prereg line 88): Run A says the frozen instrument could judge 5 of 28;
  Run B says the det port is proven first try on 23 of 28 (82%) once the instrument can judge them.
* **det-then-model: not measured.** The model backend (`anthropic`, `claude-sonnet-5-5`) on the 5 Run B programs the det
  port does not prove (and a model first attempt on the rest, were the registered metric the model's) needs
  `ANTHROPIC_API_KEY` and spend, which only the owner can grant. Until then the figure is open, not zero.
* The 18 programs whose compiled reference differs without #8217 (measured with `inlined_by_harness`): `HCAPDB01 HCAPDB02
  HCATDB01 HCAVDB01 HCIMDB01 HCIPDB01 HCITDB01 HCIVDB01 HCM1BI01 HCMABA01 HCMADB01 HCMADB02 HCP1BA01 HCP1BI01 HCT1BA01
  HCT1BI01 HCV1BA01 HCV1BI01`. None compiled at the oracle under Run A, so the flagged group is empty.
* **Candidate causes for the 5 (unassigned, read-only):** the four `HCI*DB01` share one shape, error-path handling after a
  SQL outcome (SQLCODE +100 / -913 / error): `det/sql.py` emits the `NOT FOUND` branch as `code == 100`, and the Java
  continues to the error-queue writes where the COBOL RETURNs. `HCMADB02` matches every event and differs only in the
  java-facade pass. Both are candidate `generator` or `engine` causes; a cause needs a fix commit with `Trial-Cause:`,
  which would disqualify the program from first-try, so none was made.
* n=1: one estate, one attempt per program. `summary()` aggregates per engine version across trials for that reason.

Text for the #8073 post (to be posted by the owner or orchestrator, whatever the result): the table above, the 18 named,
the 5 not proven, "det-then-model not run: needs API key and spend", the n=1 caveat, and the three REST wrappers judged
on error paths only.

## What is not here

* **No ledger entry.** `trials.json` holds the registered system (`anthropic`); booking a det run as its attempt 1 would
  mix backends, and a non-model cause needs a fix commit. The ledger is untouched.
* The det-then-model figure is open (see above); the post on #8073 is not made by this record.
* Not a first-try rate for a model-written port; not a claim about z/OS (the oracle is GnuCOBOL plus our stub).

Reproduce: `trial.py tickets trial-001 --estate-path P --work W`, then `trial.py run trial-001 --estate-path P --work W`.

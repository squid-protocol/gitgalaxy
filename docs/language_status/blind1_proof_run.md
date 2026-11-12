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

## What is not here

* **No ledger entry.** `trials.json` holds the registered system (`anthropic`); booking a det run as its attempt 1 would
  mix backends, and a non-model cause needs a fix commit. The ledger is untouched.
* The det-then-model figure (model on the programs det does not prove) and the post on #8073 are open.
* Not a first-try rate for a model-written port; not a claim about z/OS (the oracle is GnuCOBOL plus our stub).

Reproduce: `trial.py tickets trial-001 --estate-path P --work W`, then `trial.py run trial-001 --estate-path P --work W`.

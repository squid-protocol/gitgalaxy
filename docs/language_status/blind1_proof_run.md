# Blind 1: the det port's first-try proof run (#8322, part of #8073)

One attempt per eligible program (28; `HCP1BU01` is out of scope, source missing). The translator is the deterministic
COBOL-to-Java port (`--backend det`) at the **frozen engine** `5e4575d77`, tickets regenerated from it (`trial.py tickets`).
Nothing was changed after the first run: attempt 1 is the measurement (booked in the ledger, see below). The model backend the trial registered
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

23 of 28 (82%), one attempt each, det port only. The five misses are two real engine bugs, since fixed
(`blind1_run_b_causes.md`): `HCIMDB01`, `HCIPDB01`, `HCITDB01`, `HCIVDB01` took `WHEN OTHER` after SQLCODE +100 because a
COMP-declared SQLCA was written little-endian (P126, #8225; `HCITDB01` also needed #8246 for its sysout), and `HCMADB02` lost the
leading zero of `MOVE 08000000` (P127, #8269).

## Headline and det-then-model (status 2026-11-12)

Reported in this order (Amendment 4), never as a bare rate:

| | proven first try | not proven (oracle judged) | not judged (cause `harness`) | flagged |
|---|---|---|---|---|
| Run A, frozen harness (first) | 5 of 28 | 0 | 23 | 0 |
| Run B, harness at main | 23 of 28 | 5 | 0 | 0 |

* **det-translator-only** (the registered headline, prereg line 88, so backend `det` is the legitimate reading of the
  registered metric): Run A says the frozen instrument could judge 5 of 28; Run B says the det port is proven first try on
  **23 of 28 (82%)**, the figure the ledger publishes.
* **82% is final for this trial.** Post-freeze fixes are never first-try (prereg line 110): the five misses are booked
  `proven@2(engine)`, each with its fix commit, and all 28 are eventually proven. The current engine proves 28 of 28, which is
  a different system and not a first-try rate.
* **det-then-model: not measured.** The model backend (`anthropic`, `claude-sonnet-5-5`) needs `ANTHROPIC_API_KEY` and
  spend, which only the owner can grant. The figure is open, not zero.
* The 18 programs whose compiled reference differs without #8217 (measured with `inlined_by_harness`): `HCAPDB01 HCAPDB02
  HCATDB01 HCAVDB01 HCIMDB01 HCIPDB01 HCITDB01 HCIVDB01 HCM1BI01 HCMABA01 HCMADB01 HCMADB02 HCP1BA01 HCP1BI01 HCT1BA01
  HCT1BI01 HCV1BA01 HCV1BI01`. None compiled at the oracle under Run A, so the flagged group is empty.
* n=1: one estate, one attempt per program. `summary()` aggregates per engine version across trials for that reason.

## Ledger

`tests/cobol_mainframe/trials.json` holds Run B only (never Run A, which the frozen harness could not judge): the Run B log was
not kept, so `trial.py record` booked the run from its `run_summary.json` and the fix commits (`HCI*DB01`: `c81d13379`, with
`a6726f5a4` for `HCITDB01`, whose ledger attempt names it; `HCMADB02`: `34f19ce25`). Attempt 2 is the post-fix rerun in
`blind1_run_b_causes.md`. Then `trial.py close` and `report --write`. The ledger's `backend` still reads `anthropic` (the
registered system); this page records that the booked run is the det backend.

## What is not here

* Not a first-try rate for a model-written port; not a claim about z/OS (the oracle is GnuCOBOL plus our stub).
* The #8073 post is made by the orchestrator, with this page's two runs and the 82% headline, n=1.

Reproduce: `trial.py tickets trial-001 --estate-path P --work W`, then `trial.py run trial-001 --estate-path P --work W`.

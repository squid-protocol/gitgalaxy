# CardDemo job-flow case (#7065, slice 3 of #4891)

Expected run / bypass answers for the CardDemo jobs that carry an EXEC `COND=`, in `scenarios.json`.

## Basis

IBM z/OS MVS JCL Reference (SA23-1385), EXEC `COND` parameter: the step is bypassed when `code op rc` is true; without a
stepname every preceding step is tested; a bypassed step tests false (assumption A1, named in `scenarios.json`). Each
scenario's `basis` says which rule decides it. The answers were written from that text and the job text before
`gitgalaxy/core/jcl_flow.py` ran on them (level-estate policy: data first). The IBM pages were not re-fetched when writing.

## Reading it

* `jobs[].scenarios[]`: `given` is each step's `{"rc": n}` or `{"abend": code}`; `expect` is `run` / `bypass` per step.
* Each member is pinned by `sha256`; the test reads it from the mainframe corpora (`GITGALAXY_MAINFRAME_CORPORA`) and
  skips when the corpus is absent. The shape checks need no corpus.
* `not_modelled` names every other COND member with its reason; the test sweeps the corpus so a new one cannot go unlisted.
* `refused` states `TYPRUN=SCAN` and the rc of a multi-step PROC call; they are not read.

## First-time result

2026-11-04, engine commit `dc9dbf10e`: `JclFlow` reproduced all 34 scenarios (8 jobs) on the first run; no disagreement.
Afterwards this is development data.

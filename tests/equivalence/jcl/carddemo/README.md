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

## The generated Spring Batch jobs (#4891 slice 1)

`tests/cobol_mainframe/test_jcl_forged_job_carddemo.py` runs the same 34 answers against `BatchForge`'s output: it forges
each job from the real `job_flow` rows, reads the step order and each step's COND back from the generated `<Job>JobConfig`,
and decides run / bypass with the forge's own `JclConditions` Java (compiled with javac) in `JclSteps.guarded`'s order; an
abend stops the job, as JCL's flush does with no EVEN / ONLY. First run, 2026-11-20: 34 of 34 agree, no disagreement.
Stand-in skeletons make each job an "application" job (the forge generates none otherwise); a PROC call is one step (A5), so
the forge's `CALL.PROCSTEP` splice is not exercised (proc slice). Not run: the Spring `guarded` body (pinned by text),
DD binding, gdg, restart.

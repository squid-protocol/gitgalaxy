# Env-gated tests (#5954)

A test gated on `EQUIVALENCE_E2E=1` or `CICS_CRUCIBLE_PATH` skips unless the pytest run that reaches it sets the
variable and provides what the test needs. Two workflows set `EQUIVALENCE_E2E`: `cics-crucible.yml` `runner-tests`
(`tests/cics_crucible -m e2e`) and `equivalence-e2e.yml` (`tests/cobol_mainframe` and `tests/tools/test_zos_probes.py`:
three shards, plus the `db2` job for the five files that need a Db2 container, #5954 slices 2-3). `CICS_CRUCIBLE_PATH` is
set by `runner-tests` for the four files that read it. No gated file is left unreached. `tests/tools/test_env_gated_tests_run_in_ci_5954.py`
fails when a gated file is reached by no workflow and is not listed in its shrink-only `UNCOVERED_*` sets (empty now; it
reads each shard's `--ignore` flags, so a file the shards ignore must be named by another pytest run), and reads each
listed file's needs from its skip reasons; this page carries one row per listed file with those needs.

`equivalence-e2e.yml` runs on a PR only when `tests/tools/equivalence_e2e_plan.py` (the #6278 change classifier) finds a
COBOL / mainframe / equivalence path in the diff; a push to main (post-merge) is planned the same way from the pushed files; the nightly and a manual run always run it. Its `equivalence-e2e` check
sums the run's job seconds into runner-minutes in the step summary. The `db2` job has its own, narrower gate (#6664): on a
PR it runs only when a changed file is an input of the five Db2 files (`equivalence_e2e_plan.db2_input`: their import
closure, the equivalence cases they name, shared harness data, a non-Python file under `gitgalaxy/`, or the job's own
files). Nightly and manual runs always run it, and a push is planned from the pushed files, and Main Watch watches the workflow on main.

## Which files the shards run (#6664)

`mainframe-ground-truth.yml` (a required check) runs all of `tests/cobol_mainframe` without `EQUIVALENCE_E2E`, the oracle
image or JDK 17 at the path the shards set up. The shards used to run the whole directory again; on one commit (junit of
runs 40225533892 and 40225536142, 2026-10-25) 7126 of the 7822 tests they ran also passed there (1810 s of shard test
time). `tests/tools/equivalence_e2e_select.py` now picks the files whose result can differ: those that read
`EQUIVALENCE_E2E`, plus those whose skip reasons name Docker / GnuCOBOL / the oracle image, a JDK, Maven or a jar (five
files skip in ground-truth for "no JDK 17" without reading the variable). That keeps all 696 tests that ran only in the
shards (3177 s) and 188 s of the duplicates. A new file that needs the shards' tools must say so in a skip reason, or
read the variable, to be selected.

The split weighs tests by `tests/equivalence_e2e_durations.json`, not `.test_durations` (ground-truth records the latter,
where these tests skip, so it weighs them about 0 s). Each shard uploads `test-times-equivalence-e2e-shard-N`; refresh the
file from a nightly run with `gh run download RUN --pattern 'test-times-equivalence-e2e-shard-*'` and
`python tests/tools/merge_test_durations.py tests/equivalence_e2e_durations.json test-times-equivalence-e2e-shard-*/times-shard-*.json`.

Needs: `docker` = the GnuCOBOL oracle image; `jdk_maven` = JDK 17 and Maven; `db2` = the Db2 container;
`crucible_checkout` = a cics-crucible checkout.

## What a workflow must provide

| Group | Provide | Host |
|---|---|---|
| `crucible_checkout` | `CICS_CRUCIBLE_PATH` = the pinned checkout `runner-tests` clones, and a pytest line that names the files | `cics-crucible.yml` `runner-tests` |
| `docker`, `jdk_maven` | `EQUIVALENCE_E2E=1`, the oracle image (cache + `equivalence_oracle.py --strict`), JDK 17, Maven cache | `equivalence-e2e.yml` `shard` (classifier-gated, owner decision: CI cost) |
| `db2` | the above plus the pinned Db2 image (the `db2-image-<digest>` cache entry det-sweep.yml's main runs save), the ODBC driver cache, `GITGALAXY_DB2_POOL=3` and `-n 3` | `equivalence-e2e.yml` `db2` (one runner; on a PR only when an input of the five files changed, #6664) |

## Db2 files (run by the `db2` job, not the shards)

The five files the shards `--ignore` and the `db2` job names: `test_equivalence_db2_rows`, `test_regional_options`,
`test_sql_dynamic`, `test_sql_unit_of_work`, `test_sql_whenever` (all under `tests/cobol_mainframe/`; needs: db2, docker,
jdk_maven). Retiring a test that can no longer run (step 3 of the issue) is still open.

## Deselected in the E2E shards (failed on their first CI run)

Two tests in files the shards run (and, below the table, two in the `db2` job) were never executed in CI before #5954 and fail on a pristine checkout, locally and on
the runner. The shard command `--deselect`s them by node id so the other tests in those files gate; each is a defect to fix
in the engine or the test, then drop its `--deselect`:

| Test | Failure |
|---|---|
| `test_equivalence_inputs.py::test_the_hand_written_ports_hold_on_generated_inputs[carddemo-acctview-generated-None]` | the report holds 63 outputs, the test expects 24 |
| `test_equivalence_cics.py::test_a_facade_that_builds_its_own_task_fails_the_java_facade_side` | the mutated COMEN01C port exits 0 (proven) where the test expects 1 |

The `db2` job `--deselect`s `test_equivalence_db2_rows.py::test_the_inqacccu_det_port_holds_on_generated_db2_rows` (the generated-row comparison reports a diff on a pristine checkout) and `test_sql_unit_of_work.py::test_uowdemo_det_port_proves_on_db2_against_the_hand_trace` (both
`[N]` and `[A]`): the det port's `DetMq.java` fails to compile on a pristine checkout (`package com.gitgalaxy.modernized.cics
does not exist`, `CicsTask` not found: the generated estate carries no `cics` package for a batch program that uses MQ
stubs). The other tests of the five files pass locally against Db2 (178 of 181 ran: 128 in four files, 50 in the rows file, 34 min serial).

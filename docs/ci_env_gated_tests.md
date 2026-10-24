# Env-gated tests (#5954)

A test gated on `EQUIVALENCE_E2E=1` or `CICS_CRUCIBLE_PATH` skips unless the pytest run that reaches it sets the
variable and provides what the test needs. Two workflows set `EQUIVALENCE_E2E`: `cics-crucible.yml` `runner-tests`
(`tests/cics_crucible -m e2e`) and `equivalence-e2e.yml` (`tests/cobol_mainframe` and `tests/tools/test_zos_probes.py`:
four shards, plus the `db2` job for the five files that need a Db2 container, #5954 slices 2-3). `CICS_CRUCIBLE_PATH` is
set by `runner-tests` for the four files that read it. No gated file is left unreached. `tests/tools/test_env_gated_tests_run_in_ci_5954.py`
fails when a gated file is reached by no workflow and is not listed in its shrink-only `UNCOVERED_*` sets (empty now; it
reads each shard's `--ignore` flags, so a file the shards ignore must be named by another pytest run), and reads each
listed file's needs from its skip reasons; this page carries one row per listed file with those needs.

`equivalence-e2e.yml` runs on a PR only when `tests/tools/equivalence_e2e_plan.py` (the #6278 change classifier) finds a
COBOL / mainframe / equivalence path in the diff; the nightly and a manual run always run it. Its `equivalence-e2e` check
sums the run's job seconds into runner-minutes in the step summary.

Needs: `docker` = the GnuCOBOL oracle image; `jdk_maven` = JDK 17 and Maven; `db2` = the Db2 container;
`crucible_checkout` = a cics-crucible checkout.

## What a workflow must provide

| Group | Provide | Host |
|---|---|---|
| `crucible_checkout` | `CICS_CRUCIBLE_PATH` = the pinned checkout `runner-tests` clones, and a pytest line that names the files | `cics-crucible.yml` `runner-tests` |
| `docker`, `jdk_maven` | `EQUIVALENCE_E2E=1`, the oracle image (cache + `equivalence_oracle.py --strict`), JDK 17, Maven cache | `equivalence-e2e.yml` `shard` (classifier-gated, owner decision: CI cost) |
| `db2` | the above plus the pinned Db2 image (the `db2-image-<digest>` cache entry det-sweep.yml's main runs save), the ODBC driver cache, `GITGALAXY_DB2_POOL=3` and `-n 3` | `equivalence-e2e.yml` `db2` (one runner, same gate) |

## Db2 files (run by the `db2` job, not the shards)

The five files the shards `--ignore` and the `db2` job names: `test_equivalence_db2_rows`, `test_regional_options`,
`test_sql_dynamic`, `test_sql_unit_of_work`, `test_sql_whenever` (all under `tests/cobol_mainframe/`; needs: db2, docker,
jdk_maven). Retiring a test that can no longer run (step 3 of the issue) is still open.

## Deselected in the E2E shards (failed on their first CI run)

Four tests in files the shards run (and, below the table, two in the `db2` job) were never executed in CI before #5954 and fail on a pristine checkout, locally and on
the runner. The shard command `--deselect`s them by node id so the other tests in those files gate; each is a defect to fix
in the engine or the test, then drop its `--deselect`:

| Test | Failure |
|---|---|
| `test_det_layout.py::test_the_initial_image_is_gnucobols[carddemo-cbstm03a]` | det layout of CBSTM03A's `TIOT-INDEX`: initial image `000020202020`, GnuCOBOL `000000000000` |
| `test_equivalence_inputs.py::test_the_intcalc_port_holds_on_generated_inputs` | CBACT04C `TRANSACT` 26/37 records equal (`TRAN-CARD-NUM` differs) |
| `test_equivalence_inputs.py::test_the_hand_written_ports_hold_on_generated_inputs[carddemo-acctview-generated-None]` | the report holds 63 outputs, the test expects 24 |
| `test_equivalence_cics.py::test_a_facade_that_builds_its_own_task_fails_the_java_facade_side` | the mutated COMEN01C port exits 0 (proven) where the test expects 1 |

The `db2` job `--deselect`s `test_equivalence_db2_rows.py::test_the_inqacccu_det_port_holds_on_generated_db2_rows` (the generated-row comparison reports a diff on a pristine checkout) and `test_sql_unit_of_work.py::test_uowdemo_det_port_proves_on_db2_against_the_hand_trace` (both
`[N]` and `[A]`): the det port's `DetMq.java` fails to compile on a pristine checkout (`package com.gitgalaxy.modernized.cics
does not exist`, `CicsTask` not found: the generated estate carries no `cics` package for a batch program that uses MQ
stubs). The other tests of the five files pass locally against Db2 (178 of 181 ran: 128 in four files, 50 in the rows file, 34 min serial).

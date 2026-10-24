# Env-gated tests no workflow runs (#5954)

A test gated on `EQUIVALENCE_E2E=1` or `CICS_CRUCIBLE_PATH` skips unless the pytest run that reaches it sets the
variable and provides what the test needs. Two workflows set `EQUIVALENCE_E2E`: `cics-crucible.yml` `runner-tests`
(`tests/cics_crucible -m e2e`) and `equivalence-e2e.yml` (`tests/cobol_mainframe` and `tests/tools/test_zos_probes.py`,
four shards, #5954 slice 2). `CICS_CRUCIBLE_PATH` is set by `runner-tests` for the four files that read it. The rows below
are the `EQUIVALENCE_E2E` files still no workflow reaches: the five that need a Db2 container, which the shards
`--ignore`. They count toward the suite and prove nothing in CI. `tests/tools/test_env_gated_tests_run_in_ci_5954.py`
pins the list below (shrink-only; it reads each shard's `--ignore` flags) and reads each file's needs from its skip reasons;
this page must carry one row per listed file with those needs.

`equivalence-e2e.yml` runs on a PR only when `tests/tools/equivalence_e2e_plan.py` (the #6278 change classifier) finds a
COBOL / mainframe / equivalence path in the diff; the nightly and a manual run always run it. Its `equivalence-e2e` check
sums the run's job seconds into runner-minutes in the step summary.

Needs: `docker` = the GnuCOBOL oracle image; `jdk_maven` = JDK 17 and Maven; `db2` = the Db2 container;
`crucible_checkout` = a cics-crucible checkout.

## What a workflow must provide

| Group | Provide | Natural host |
|---|---|---|
| `crucible_checkout` (done) | `CICS_CRUCIBLE_PATH` = the pinned checkout `runner-tests` clones, and a pytest line that names the files | `cics-crucible.yml` `runner-tests` |
| `docker`, `jdk_maven` (done) | `EQUIVALENCE_E2E=1`, the oracle image (cache + `equivalence_oracle.py --strict`), JDK 17, Maven cache | `equivalence-e2e.yml` (classifier-gated, owner decision: CI cost) |
| `db2` | the above plus a Db2 container | the Db2 shard plan (`db2_shard_plan.py`), or a Db2 service in `equivalence-e2e.yml` |

The Db2 files and retiring unrunnable tests (step 3) are the open part of #5954.

## Inventory

| Test file | Gated on | Needs |
|---|---|---|
| `tests/cobol_mainframe/test_equivalence_db2_rows.py` | EQUIVALENCE_E2E | db2, docker, jdk_maven |
| `tests/cobol_mainframe/test_regional_options.py` | EQUIVALENCE_E2E | db2, docker, jdk_maven |
| `tests/cobol_mainframe/test_sql_dynamic.py` | EQUIVALENCE_E2E | db2, docker, jdk_maven |
| `tests/cobol_mainframe/test_sql_unit_of_work.py` | EQUIVALENCE_E2E | db2, docker, jdk_maven |
| `tests/cobol_mainframe/test_sql_whenever.py` | EQUIVALENCE_E2E | db2, docker, jdk_maven |

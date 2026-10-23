# Env-gated tests no workflow runs (#5954)

A test gated on `EQUIVALENCE_E2E=1` or `CICS_CRUCIBLE_PATH` skips unless the pytest run that reaches it sets the
variable and provides what the test needs. Today only `cics-crucible.yml` `runner-tests` sets `EQUIVALENCE_E2E`
(running `tests/cics_crucible -m e2e`) and `CICS_CRUCIBLE_PATH` (its own pinned checkout; the four files that read it
run there, slice 2 of #5954, so they are no longer listed). The rows below are the `EQUIVALENCE_E2E` files no workflow reaches. These tests count toward the suite
and prove nothing in CI. `tests/tools/test_env_gated_tests_run_in_ci_5954.py` pins the list below (shrink-only) and
reads each file's needs from its skip reasons; this page must carry one row per listed file with those needs.

Needs: `docker` = the GnuCOBOL oracle image; `jdk_maven` = JDK 17 and Maven; `db2` = the Db2 container;
`crucible_checkout` = a cics-crucible checkout.

## What a workflow must provide

| Group | Provide | Natural host |
|---|---|---|
| `crucible_checkout` (done) | `CICS_CRUCIBLE_PATH` = the pinned checkout `runner-tests` clones, and a pytest line that names the files | `cics-crucible.yml` `runner-tests` |
| `docker`, `jdk_maven` | `EQUIVALENCE_E2E=1`, the oracle image (cache + `equivalence_oracle.py --strict`), JDK 17, Maven cache | a new sharded job over `tests/cobol_mainframe` (owner decision: CI cost) |
| `db2` | the above plus a Db2 container | the same job, or the Db2 shard plan (`db2_shard_plan.py`) |

The Docker/JDK job (step 2 for `EQUIVALENCE_E2E`) and retiring unrunnable tests (step 3) are the open part of #5954.

## Inventory

| Test file | Gated on | Needs |
|---|---|---|
| `tests/cobol_mainframe/test_address_e2e_5079.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_bll_cells_5119.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_cbstm03a_case_5856.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_cobolrt.py` | EQUIVALENCE_E2E | docker |
| `tests/cobol_mainframe/test_comp5_layout.py` | EQUIVALENCE_E2E | docker |
| `tests/cobol_mainframe/test_det_binary_store.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_det_bytes_4690.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_det_conditions.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_det_dli.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_det_dynamic_call_4736.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_det_funcs.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_det_layout.py` | EQUIVALENCE_E2E | docker |
| `tests/cobol_mainframe/test_det_nondigit_binary.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_det_nondigit_zoned.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_det_osvs.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_det_programs.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_det_size_error.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_det_whole_programs_4270.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_equivalence.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_equivalence_bmp_dli.py` | EQUIVALENCE_E2E | docker |
| `tests/cobol_mainframe/test_equivalence_cics.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_equivalence_cics_dli.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_equivalence_db2_rows.py` | EQUIVALENCE_E2E | db2, docker, jdk_maven |
| `tests/cobol_mainframe/test_equivalence_environments.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_equivalence_faults.py` | EQUIVALENCE_E2E | docker |
| `tests/cobol_mainframe/test_equivalence_inputs.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_equivalence_oracle.py` | EQUIVALENCE_E2E | docker |
| `tests/cobol_mainframe/test_equivalence_sysout_attrs.py` | EQUIVALENCE_E2E | docker |
| `tests/cobol_mainframe/test_lifted_binary_trunc.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_link_commarea_bytes_4806.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_link_xctl_commarea_4816.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_oracle_intermediate_cap.py` | EQUIVALENCE_E2E | docker |
| `tests/cobol_mainframe/test_pointer_commarea_4270.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_pointer_compare_5042.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_porting_loop_tooling.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_post_wait_converse_e2e_5079.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_regional_options.py` | EQUIVALENCE_E2E | db2, docker, jdk_maven |
| `tests/cobol_mainframe/test_rounding.py` | EQUIVALENCE_E2E | docker |
| `tests/cobol_mainframe/test_sql_dynamic.py` | EQUIVALENCE_E2E | db2, docker, jdk_maven |
| `tests/cobol_mainframe/test_sql_unit_of_work.py` | EQUIVALENCE_E2E | db2, docker, jdk_maven |
| `tests/cobol_mainframe/test_sql_whenever.py` | EQUIVALENCE_E2E | db2, docker, jdk_maven |
| `tests/cobol_mainframe/test_td_enablestatus_e2e_5168.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_td_openstatus_e2e_5168.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_td_queue_e2e_5079.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_td_queue_e2e_5168.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/cobol_mainframe/test_trunc_opt.py` | EQUIVALENCE_E2E | docker, jdk_maven |
| `tests/tools/test_zos_probes.py` | EQUIVALENCE_E2E | docker |

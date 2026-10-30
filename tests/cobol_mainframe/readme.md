<div align="center">

# COBOL & Mainframe Modernization Test Suite (`tests/cobol_mainframe`)

### Over 8,500 tests (collected 2026-10-29) pinning fact extraction, the CICS command spec, deterministic translation, equivalence proofs, mutation scores, and zero-leakage readiness reports.

This directory tests GitGalaxy's mainframe modernization and CICS-to-Java stack:
[`gitgalaxy/tools/cobol_to_java/`](../../gitgalaxy/tools/cobol_to_java/README.md),
[`gitgalaxy/tools/cobol_to_cobol/`](../../gitgalaxy/tools/cobol_to_cobol/README.md),
[`gitgalaxy/tools/readiness/`](../../gitgalaxy/tools/readiness/README.md), and
[`gitgalaxy/standards/cics/`](../../gitgalaxy/standards/cics/README.md).
It checks every layer from copybook byte offsets and OS/VS `BLL` pointer cells up to full
end-to-end equivalence runs against `cobc (GnuCOBOL) 3.1.2.0`, our CICS/LE/IMS/MQ models, and a
live IBM Db2 Community Edition container.

<table>
<tr>
<td align="center" width="190"><h2>8,573</h2></td>
<td align="center" width="190"><h2>369</h2></td>
<td align="center" width="190"><h2>6 + 1</h2></td>
<td align="center" width="190"><h2>9</h2></td>
</tr>
<tr>
<td align="center" valign="top"><sub><strong>tests collected (2026-10-29)</strong><br /><code>pytest --collect-only tests/cobol_mainframe/</code><br /><em><a href="#quickstart">run the suite</a> · unit, differential &amp; E2E</em></sub></td>
<td align="center" valign="top"><sub><strong>test modules in this directory</strong><br />covering extraction, <code>det</code>, CICS &amp; proofs<br /><em><a href="#test-index-by-subsystem">test index</a> · plus <code>tests/equivalence/</code></em></sub></td>
<td align="center" valign="top"><sub><strong>burned estates + CICS crucible</strong><br />estate programs on the <a href="https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/progress.md">progress page</a> + 63 crucible trap programs<br /><em><a href="#real-corpora-answer-keys-and-differential-gates">pinned corpora</a> · <code>crucible_pins.toml</code></em></sub></td>
<td align="center" valign="top"><sub><strong>CI ratchets in <code>pr_gates.py</code></strong><br />cics-spec, ports, port-surface, estate, fact-crosscheck, completeness, ground-truth, det-mutation, time<br /><em><a href="#ci-gates-and-ratchets">ratchets</a> · zero regressions</em></sub></td>
</tr>
</table>

<a href="#quickstart"><strong>Quickstart</strong></a> ·
<a href="#test-index-by-subsystem"><strong>Test index</strong></a> ·
<a href="#real-corpora-answer-keys-and-differential-gates"><strong>Corpora &amp; answer keys</strong></a> ·
<a href="#ci-gates-and-ratchets"><strong>CI gates &amp; ratchets</strong></a> ·
<a href="#end-to-end-equivalence-and-db2-sweeps"><strong>E2E proofs</strong></a>

</div>

---

<a id="quickstart"></a>

## Quickstart

```sh
# Run the fast unit and differential suite (no Docker / Db2 required)
python -m pytest tests/cobol_mainframe/ -v

# Run the pre-push fast gate and ratchets
python tests/tools/pr_gates.py --fast
python tests/tools/pr_gates.py --ratchets

# Run with end-to-end GnuCOBOL + JVM equivalence proofs enabled
EQUIVALENCE_E2E=1 python -m pytest tests/cobol_mainframe/ -v
```

See [`tests/README.md`](../README.md) for the repository-wide test index across all languages.

---

<a id="test-index-by-subsystem"></a>

## Test index by subsystem

### 1. Deterministic translator (`det/`) & Java runtime (`cobolrt`)
Tests pinning [`gitgalaxy/tools/cobol_to_java/det/`](../../gitgalaxy/tools/cobol_to_java/det/) and its byte-exact Java 17 runtime:
- **Core layout, storage & data moves:** `test_det_layout.py`, `test_det_translate.py`, `test_det_programs.py`, `test_det_parity.py`, `test_det_port_check.py`, `test_cobolrt.py`, `test_cobolrt_rules.py`, `test_det_binary_store.py`, `test_lifted_binary_trunc.py`, `test_det_nondigit_binary.py`, `test_det_nondigit_zoned.py`, `test_det_size_error.py`, `test_det_conditions.py`, `test_det_funcs.py`, `test_det_hfp.py`, `test_floating_insertion.py`, `test_currency_pictures.py`, `test_picture_symbol_precision.py`, `test_sign_separate.py`, `test_signed_value_4277.py`, `test_sync_renames_4266.py`, `test_sync_table_slack_4266.py`, `test_group_usage_4525.py`, `test_odo_qualifier_4282.py`.
- **OS/VS COBOL, `BLL` cells & pointers:** `test_det_osvs.py`, `test_bll_cells_5119.py`, `test_pointer_lane_4771.py`, `test_pointer_lane_5042.py`, `test_pointer_null_cond_5197.py`, `test_pointer_commarea_4270.py`, `test_address_5079.py`, `test_address_e2e_5079.py`.
- **Dynamic calls, intrinsic functions & LE services:** `test_det_dynamic_call_4736.py`, `test_det_ceedays.py`, `test_det_ceeigzct.py`, `test_det_le_time.py`, `test_det_length_of_element_5076.py`.
- **Source format, copybooks & compiler options:** `test_det_source_4462.py`, `test_det_source_defects_4735.py`, `test_det_inline_comment.py`, `test_section_copy_replacing_4457.py`, `test_record_layout_copy_placement_4278.py`, `test_record_layout_redefines_4280.py`, `test_values_and_copybook_comma.py`, `test_estate_options.py`, `test_option_table.py`, `test_numproc.py`, `test_trunc_opt.py`, `test_decimal_comma.py`, `test_data_moves_decimal_comma_4355.py`, `test_data_moves_national_4353.py`, `test_dbcs_items.py`, `test_dbcs_widths.py`, `test_declared_code_page_reads.py`, `test_record_charset.py`.
- **HLASM lowering (command-level CICS assembler, #5859):** `test_hlasm_lowering_5859.py`, `test_hlasm_interp_5859.py` (POPS interpreter), `test_hlasm_diff_5859.py` (per-instruction differential), `test_hlasm_estate_census_5859.py` (every burned assembler member placed).
- **SORT and DFSORT steps (#4268):** `test_dfsort_4268.py`.
- **IMS DL/I and IBM MQ:** `test_det_dli.py`, `test_cblt_dli_cics_5233.py`, `test_dli_uow_burned_5233.py`, `test_equivalence_bmp_dli.py`, `test_equivalence_cics_dli.py`, `test_det_mq.py`.
- **Survey & fast sweeps:** `test_det_survey.py`, `test_det_sweep_fast.py`, `test_det_whole_programs_4270.py`, `test_statement_inventory.py`.

### 2. CICS command spec, CICS translation & BMS screens
Tests pinning [`gitgalaxy/standards/cics/`](../../gitgalaxy/standards/cics/README.md) and CICS runtime semantics:
- **Unified CICS spec & macro refusals:** `test_cics_spec_equality.py` (alongside `tests/core_engine/test_cics_spec.py`), `test_det_cics_macro_refusal_5121.py`, `test_cics_resource_map.py`, `test_cics_transaction_reader.py`, `test_csd_resource_differential.py`.
- **BMS maps, terminal & conversational CICS:** `test_bms_screens.py`, `test_det_cics_map_names_4270.py`, `test_det_receive_map_justify_5082.py`, `test_cics_conversation_4427.py`, `test_post_wait_converse_5079.py`, `test_post_wait_converse_e2e_5079.py`, `test_equivalence_sysout_attrs.py`.
- **Program control (`LINK` / `XCTL` / `RETURN`) & `COMMAREA`s:** `test_linked_programs.py`, `test_link_commarea_bytes_4806.py`, `test_link_xctl_alias_4957.py`, `test_link_xctl_chain_4816.py`, `test_link_xctl_commarea_4816.py`, `test_model_link_xctl_4956.py`, `test_return_transid_commarea_bytes_4817.py`, `test_cics_opaque_commarea_4464.py`, `test_det_untyped_commarea_5053.py`, `test_facade_layout_4449.py`.
- **Files, queues & tokens:** `test_vsam_repositories.py`, `test_det_record_key_4804.py`, `test_update_token_translate_5078.py`, `test_td_openstatus_translate_5168.py`, `test_td_openstatus_e2e_5168.py`, `test_td_queue_e2e_5079.py`, `test_td_queue_e2e_5168.py`, `test_messaging.py`.

### 3. Readiness scanner (`gitgalaxy assess`), CICS eras & support matrix
Tests pinning [`gitgalaxy/tools/readiness/`](../../gitgalaxy/tools/readiness/README.md) and estate reporting:
- **Offline readiness & zero-leakage schema:** `test_assess.py` (socket guard, read-only estate check, schema validation, `--redact` keyed hashing, zero source-text leakage).
- **CICS era tagging & non-burned distribution:** `test_era_tags.py`, `test_era_distribution.py`.
- **Feature inventory & support matrix:** `test_feature_inventory.py`, `test_support_matrix.py`, `test_field_testing.py`.

### 4. Equivalence harness, Db2, coverage, mutation & evidence records
Tests pinning [`tests/tools/equivalence*.py`](../tools/equivalence.py) and the `L0–L5` / `E0–E4` ladders:
- **Equivalence harness & oracle:** `test_equivalence.py`, `test_equivalence_cics.py`, `test_equivalence_faults.py`, `test_equivalence_inputs.py`, `test_collation_boundary_inputs.py`, `test_equivalence_encodings.py`, `test_equivalence_environments.py`, `test_equivalence_oracle.py`, `test_equivalence_speed.py`, `test_call_compare_4778.py`, `test_occurs_compare_4765.py`, `test_input_dates.py`, `test_time_zones.py`, `test_locale_root.py`.
- **Embedded SQL & Db2 UOW:** `test_equivalence_sql.py`, `test_equivalence_db2_rows.py`, `test_db2_repositories.py`, `test_sql_faults.py`, `test_sql_reserved_names.py`, `test_sql_unit_of_work.py`, `test_db2_image_pin.py`, `test_db2_odbc_pin.py`.
- **Evidence records, mutation & proof reachability:** `test_evidence.py`, `test_evidence_components.py`, `test_mutation_tooling.py`, `test_mutation_scores.py`, `test_proof_reach.py`, `test_proof_reach_det_helpers_5082.py`, `test_proof_sweep.py`, `test_strengthen_loop.py`, `test_trials.py`, `test_estate4_dbb.py`, `test_estate4_draw.py`.
- **Third-party & model port evaluation:** `test_ibm_wca4z_port.py`, `test_devin_port.py`, `test_thirdparty_port.py`, `test_referee_score.py`, `test_port_invariance.py`.

### 5. Spring Boot skeleton forges, target matrix & porting loop
Tests pinning [`gitgalaxy/tools/cobol_to_java/`](../../gitgalaxy/tools/cobol_to_java/README.md):
- **Generated project & 17-config compile matrix:** `test_cobol_to_java_controller.py`, `test_java_target.py`, `test_java_matrix_gate.py`, `test_cics_endpoints.py`, `test_cics_region_4342.py`, `test_service_calls.py`, `test_batch_jobs.py`, `test_batch_runners.py`, `test_no_jcl_batch_controller.py`, `test_uow_transactional.py`, `test_generated_record_layer.py`, `test_cobol_records_digits.py`, `test_cobol_compare.py`, `test_key_collation.py`, `test_key_reader_4393.py`, `test_key_text.py`, `test_rounding.py`, `test_regional_options.py`, `test_culture_config.py`, `test_bidi_layout.py`, `test_generated_java_is_ascii.py`, `test_java_unicode_names.py`, `test_java_subprocess_utf8.py`, `test_migration_worklist.py`, `test_traceability.py`.
- **Porting tickets, runner & guardrails:** `test_port_tickets.py`, `test_port_order.py`, `test_port_ticket_references.py`, `test_port_ticket_budget.py`, `test_port_rules_culture.py`, `test_port_runner.py`, `test_porting_loop_tooling.py`, `test_agent_guardrail.py`, `test_adopt_tidy.py`.

### 6. Mainframe fact extraction (`cobol_to_cobol`) & PL/I
Tests pinning [`gitgalaxy/tools/cobol_to_cobol/`](../../gitgalaxy/tools/cobol_to_cobol/README.md):
- **GalaxyIR & skeleton export:** `test_galaxy_ir.py`, `test_ir_join_diff.py`, `test_refractor_engine_channels.py`, `test_skeleton_export.py`, `test_fact_crosscheck.py`, `test_multi_program_data_4245.py`, `test_sibling_call_same_member_4447.py`, `test_usage_leak_4329.py`, `test_varrec_cobdatft.py`.
- **Pre-processors, dead code, DAG & schemas:** `test_cobol_refractor_controller.py`, `test_cobol_lexical_patcher.py`, `test_cobol_graveyard_finder.py`, `test_cobol_graveyard_finder_right_margin.py`, `test_cobol_dag_architect.py`, `test_cobol_microservice_slicer.py`, `test_cobol_etl_unpacker.py`, `test_cobol_schema_forge.py`, `test_cobol_jcl_forge.py`, `test_cobol_jcl_auditor.py`, `test_jcl_dsn_differential.py`, `test_noscan_select_lineage.py`, `test_cobol_compiler_forge.py`, `test_cobol_system_limits_reporter.py`, `test_cobol_agent_task_forge.py`.
- **PL/I pipeline:** `test_pli_layouts.py`, `test_pli_pipeline.py`.

---

<a id="real-corpora-answer-keys-and-differential-gates"></a>

## Real corpora, answer keys, and differential gates

Beyond synthetic fixtures, the suite gates against pinned real mainframe estates (`corpora.json` and `tests/crucible_pins.toml`):

- **`corpora.json` & `test_mainframe_corpus.py`:** Manages local clones and committed CI excerpts (`refraction_excerpts/`) for `zopeneditor-sample`, `cics-banking-sample-application-cbsa`, and `aws-mainframe-modernization-carddemo`.
- **Answer keys (`answer_key/` & `test_cobol_answer_key.py`):** Hand-verified ground-truth manifests for `zopeneditor-sample` and `cbsa`.
- **Forge ↔ Engine differential (`test_refraction_differential.py`):** Runs `tests/tools/refraction_differential.py --ci` to verify that every difference between the `cobol_to_cobol` extractors and the core engine DB has an explained cause code and matches the answer keys (**0 unexplained deltas**).
- **Ground-truth & fact cross-check ledgers (`test_ground_truth_ledger.py`, `test_fact_crosscheck.py`):** Ensures `GalaxyIR` facts, `skeleton.json`, and the `det` parser agree across the burned estates (`ground_truth_ledger.json`, `fact_crosscheck_ledger.json`).
- **Clean-room output snapshot (`test_refraction_snapshot.py`):** Diffs the full generated clean-room and Spring Boot output on committed excerpts against `refraction_snapshot/excerpts/`.
- **ReDoS scaling sweep (`test_tool_regex_redos.py`):** Verifies that every regex across `cobol_to_cobol` and `cobol_to_java` scales linearly (`O(N)`).

---

<a id="ci-gates-and-ratchets"></a>

## CI gates and ratchets

Every PR touching the mainframe or translator stack must pass the gates in [`tests/tools/pr_gates.py`](../tools/pr_gates.py):
- **`det` sweep (`det-sweep.yml`):** Sharded across parallel runners sized from the measured case durations (at most `MAX_SHARDS=6`, slowest/fastest planned shard <= 1.3), verifying that no program regresses on translation holes or equivalence scenarios (`tests/equivalence/det_sweep_baseline.json`).
- **CICS spec ratchet:** `python -m gitgalaxy.standards.cics regen --check` and `python -m gitgalaxy.standards.cics check`.
- **Evidence record & report schema gates:** Verifies that every committed `evidence.json` in `tests/equivalence/` and `tests/cics_crucible/` validates against the schema and matches its recorded input digests.

---

<a id="end-to-end-equivalence-and-db2-sweeps"></a>

## End-to-end equivalence and Db2 sweeps

The proof cases themselves (inputs, scenarios, fault plans, `evidence.json` certificates, and committed ports) live in:
- [`tests/equivalence/`](../equivalence): 6 burned estates (`carddemo`, `cics-async-api`, `cbsa`, `cics-genapp`, `dbb-mortgage`, `zecs`), plus the CICS C stub (`tests/equivalence/cics/ggcics.c`) and LE models (`tests/equivalence/le/`).
- [`tests/cics_crucible/`](../cics_crucible): 63 hand-crafted CICS trap programs testing `COMMAREA` lengths, `XCTL` chains, `HANDLE ABEND` unwinding, `START`/`RETRIEVE`, terminal coalescing, BMS attributes, and immediate `RETURN`.

# CardDemo L3 programs: what is untaken and what closes it (#6967)

Four CardDemo programs sat at L3 (every live paragraph run); none has a net untaken outcome now. Net branch outcomes untaken, as of `5ceb58150`
(`tests/equivalence/<case>/evidence.json`, `det_sweep_coverage/`, `infeasible_outcomes/`); pinned by
`tests/cobol_mainframe/test_carddemo_l3_diagnosis_6967.py`.

| Program (case) | Untaken net outcomes | Closed by |
|---|---|---|
| CBPAUP0C (`carddemo-cbpaup0c`) | none. `6000-EXIT` and line 340 true are stated infeasible (family R, IMS DLET status DJ) | the declined arm: a fault with its own `ims_seed` (#6995, #7012) |
| COACCT01 (`carddemo-coacct01`) | none: 13/13 paragraphs, 33/33 branches in the sweep ledger | the MQCLOSE faults: register C20, `perform_stack_check` |
| CODATE01 (`carddemo-codate01`) | none: 13/13, 28/28 | the same |
| CSUTLDTC (`carddemo-dateutil`) | none. Line 128 `WHEN OTHER` is stated infeasible (family R, see below) | the reviewed entry in `infeasible_outcomes/carddemo-dateutil.json` |

The generated evidence report's L3 for COACCT01 and CODATE01 predates #6997 / #7039 and lags the ledger.

## Closed: CSUTLDTC `WHEN OTHER` (data only, no harness part)
The model never returns a feedback token outside the nine CSUTLDTC names, and IBM documents no other: the z/OS Language
Environment Programming Reference (V2R2 edition), CEEDAYS, "The following symbolic conditions can result from this service"
(p. 245), lists CEE000 and the eight severity-3 conditions CEE2EB, CEE2EC, CEE2ED, CEE2EH, CEE2EL, CEE2EM, CEE2EO and
CEE2EP, which are the program's nine 88-levels. The IBM i copy adds CEE0501, CEE0502 and CEE9902, argument-shape or
internal failures the fixed four-argument call cannot raise. The arm is stated infeasible, family R, an assumption that
CEEDAYS raises only its documented conditions (not a z/OS run). A scenario reaching it refutes the entry.

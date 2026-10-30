# CardDemo L3 programs: what is untaken and what closes it (#6967)

Four CardDemo programs sit at L3 (every live paragraph run). Net branch outcomes untaken, as of `5ceb58150`
(`tests/equivalence/<case>/evidence.json`, `det_sweep_coverage/`, `infeasible_outcomes/`); pinned by
`tests/cobol_mainframe/test_carddemo_l3_diagnosis_6967.py`.

| Program (case) | Untaken net outcomes | Closed by |
|---|---|---|
| CBPAUP0C (`carddemo-cbpaup0c`) | none. `6000-EXIT` and line 340 true are stated infeasible (family R, IMS DLET status DJ) | the declined arm: a fault with its own `ims_seed` (#6995, #7012) |
| COACCT01 (`carddemo-coacct01`) | none: 13/13 paragraphs, 33/33 branches in the sweep ledger | the MQCLOSE faults: register C20, `perform_stack_check` |
| CODATE01 (`carddemo-codate01`) | none: 13/13, 28/28 | the same |
| CSUTLDTC (`carddemo-dateutil`) | line 128 `WHEN OTHER` | open, see below |

The generated evidence report's L3 for COACCT01 and CODATE01 predates #6997 / #7039 and lags the ledger.

## Open: CSUTLDTC `WHEN OTHER` (data only, no harness part)
The model never returns a feedback token outside the nine CSUTLDTC names. Stating the arm infeasible needs an IBM z/OS
Language Environment source saying CEEDAYS cannot raise another condition (the IBM i page lists CEE0501, CEE0502 and
CEE9902) for these callers. None has been found, so it stays open (`OPEN_ON_PURPOSE` in
`test_carddemo_dateutil_outcomes_6967.py`). Owner question: is there a source to cite, or should the arm stay open?

---
description: "GitGalaxy reads COBOL and Java with the same rules, so a COBOL program and its deterministic Java port should"
---
# Port invariance contract

GitGalaxy reads COBOL and Java with the same rules, so a COBOL program and its deterministic Java port should
look alike on the readings that describe what a program does, and are allowed to differ on the ones that describe
how much text it takes to say it. A det port (`gitgalaxy/tools/cobol_to_java/det/`) is proven to behave as its
COBOL does, statement for statement, against GnuCOBOL (and the CICS and Db2 models), so when the scanner ranks
the COBOL programs one way and their ports another, the difference is the scanner's, not the code's.

Checked by `tests/tools/port_invariance.py` and `tests/cobol_mainframe/test_port_invariance.py`. The study the
contract comes from: [COBOL ↔ Java scan parity](wiki/05-18-cobol-java-scan-parity.md).

## Readings that must keep the programs' rank order

Tie-corrected Spearman ρ between each COBOL program's reading and its port's, over the pairs, must stay at or
above the floor. Measured 2026-10-02 with the scanner after #4163 and #4164:

| Reading (file_data) | Extraction key | ρ, 49 pairs | Floor | ρ, 12 committed pairs | Floor |
|---|---|---|---|---|---|
| `function_count` (paragraphs, methods) | `functions` | 0.937 | 0.85 | 0.778 | 0.70 |
| `struct_branch` | `branch` | 0.855 | 0.75 | 0.784 | 0.65 |
| `state_flux` | `state_mutation` | 0.762 | 0.65 | 0.708 | 0.55 |
| `arch_io` | `io` | 0.871 | 0.75 | 0.958 | 0.80 |
| `arch_ipc` | `ipc_rpc_bridges` | 0.835 | 0.70 | 0.757 | 0.60 |

The `struct_branch` row was re-measured after Java's branch rule stopped counting a `?` or `:` inside a string
literal (JDBC `?` placeholders, SQL `:host` variables) and a ternary twice (#4170; branch_rule_contract.md,
"Literals"). Before that fix it read 0.826 on the 49 pairs and 0.745 on the 12; the other four readings did not
move.

The 12-pair `function_count` row was re-measured on 2026-10-07 after the fixture was regenerated with the current
translator (#4444): 0.912 became 0.778, so its floor went from 0.80 to 0.70. The ports gained methods with no COBOL
paragraph behind them (named 88-condition methods #4202, `abended()` #4541, `caWhole()` #4642; fewer `executeX()`
#4342); no scanner reading changed. The 49-pair figure above has not been re-measured.

Each floor is the measurement less a margin of 0.08 to 0.15. On 12 pairs one pair changing places moves ρ by
about 0.05 to 0.1. Every fixture floor is above 0.50, the one-sided p < 0.05 critical value for 12 pairs, so a
passing fixture still shows a positive rank agreement that chance would rarely produce.

Two facts must also hold for every pair:

- the port has at least as many methods as the COBOL has paragraphs and sections (the det port emits one method
  per paragraph and adds its own);
- the port does file I/O exactly when the COBOL does (`arch_io` zero on both sides or on neither).

## Readings a port may change

Reported by the study, never asserted:

- **Size:** `coding_loc`, `token_mass`. A det port spells out storage, truncation and field access that COBOL
  leaves to the compiler; it is about 4× the COBOL's code lines as emitted.
- **The largest function:** `max_func_complexity`. The port's long compound conditions concentrate branches.
- **Risk scores** (`risk_*`): normalised within each scan, so they rank files within one language, not across two.
- **Archetype** (`file_archetype`, `composition_file_archetype`).

## Known divergence

COBOL's `ipc_rpc_bridges` counts `CALL 'CEE3ABD'` (Language Environment's abend service), which a batch program
uses to abend; the det port renders it as a runtime abend, which Java's rule does not count. Batch programs
therefore read IPC 1 in COBOL and 0 in Java. The rank floor absorbs it; the pair-level checks do not test IPC
presence for this reason.

## Running it

```sh
python -m pytest tests/cobol_mainframe/test_port_invariance.py            # the committed pairs (CI)
python tests/tools/port_invariance.py check                                # the same, printed
python tests/tools/port_invariance.py check --work <det sweep work dir>   # every swept port (local)
PORT_INVARIANCE_WORK=<det sweep work dir> python -m pytest tests/cobol_mainframe/test_port_invariance.py
```

The full check needs the pinned corpora (`$GITGALAXY_MAINFRAME_CORPORA`) and a det sweep's output
(`tests/tools/proof_sweep.py --det-only --work DIR`, or `det_port.py run --all-cases --translate-only`); it
takes about 15 seconds for 49 pairs.

Readings come from GitGalaxy's single-file extraction (`Prism.split_streams` + `StructuralExtractor.splice`).
On all 49 pairs its counts equal the ones a full `galaxyscope` scan records in `file_data`, so the check needs
neither git nor a full pipeline run.

## The committed pairs

`tests/cobol_mainframe/port_invariance/`: 12 programs (7 CardDemo, 4 CBSA, 1 GenApp; batch and CICS; with and
without file I/O), chosen so that each reading's ρ over them sits near its 49-pair value. The COBOL is vendored
unmodified at each corpus's pinned commit with its licence files; the Java is the det port's service class,
which carries the `// gitgalaxy-det-port:` header. Regenerate both after an emitter change with
`python tests/tools/port_invariance.py fixture --work <det sweep work dir>`, then re-measure the floors.

## When the check fails

- **A floor is broken:** a scanner change made a reading depend on the language. Compare the reading's rule for
  COBOL and for Java (`gitgalaxy/standards/language_standards/languages/`). If the change is right and the
  reading has legitimately stopped being comparable, move it to "Readings a port may change" in this document
  with the reason.
- **A pair-level fact fails after an emitter change:** check that the port is still proven. If it is, the
  emitter changed shape: regenerate the fixture and re-measure.

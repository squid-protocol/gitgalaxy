---
description: "> **File Reference:** [`gitgalaxy/tools/cobol_to_java/det/`](https://github.com/squid-protocol/gitgalaxy/tree/main/gitgalaxy/tools/cobol_to_java/det) ·..."
---
# Ported COBOL-to-Java Programs and Their Evidence

> **File Reference:** [`gitgalaxy/tools/cobol_to_java/det/`](https://github.com/squid-protocol/gitgalaxy/tree/main/gitgalaxy/tools/cobol_to_java/det) · [`tests/tools/det_port.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/tests/tools/det_port.py) · [`tests/tools/equivalence.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/tests/tools/equivalence.py) · [`tests/tools/proof_sweep.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/tests/tools/proof_sweep.py)

## Engineering Summary
The skeleton forges ([05-02](05-02-spring-boot-scaffolding.md) to [05-04](05-04-api-and-service-contracts.md)) generate the structure of the Java system. This page covers how each program's business logic is carried across, how each port is checked against the COBOL, and what evidence level it earns before a person approves it.

There are two ways to port a program, and both end in the same proof:

- **The deterministic translator ("det-port").** No model. Each COBOL statement becomes a call into a small runtime, `cobolrt`, that follows COBOL's rules byte for byte (storage as bytes, MOVE and arithmetic rules, TRUNC, signs, packed decimal, file status, CICS responses, the SQLCA). A statement it cannot translate becomes a named `Hole` that throws when reached, never a guess. The same source always gives the same port.
- **A model-written port.** A person or a model the customer chooses writes the service from a porting ticket ([05-05](05-05-autonomous-agent-tickets.md)), and the porting loop feeds a failed proof back to the next attempt.

A model may also make a det port that passes its proof readable, one method at a time. Each rewrite is re-proven, else retried once, else reverted, so the proof still passes after every step.

## What a proof compares
`tests/tools/equivalence.py` runs the COBOL under GnuCOBOL and the port on the JVM with the same inputs. Per case kind:

- **Batch:** every output record, field by field; the return code or abend; every DISPLAY line.
- **CICS:** every task event in order: each screen (text, attributes, cursor), SEND TEXT, the RETURN or XCTL with its COMMAREA, each LINK and the COMMAREA it returns, and an abend.
- **CALL:** every USING item after each call, and the return code.
- **Db2:** every compared table, row by row, after each run. Both sides run their SQL on one IBM Db2 Community Edition in a container. The COBOL side goes through the harness's own precompiler and IBM's CLI driver.
- **Faults:** file statuses and CICS responses injected at the same statement on both sides must end the same way.

Each proof reports the COBOL paragraphs and branches its runs covered, and [mutation testing](https://github.com/squid-protocol/gitgalaxy/blob/main/docs/language_status/mutation_testing.md) measures how many deliberately broken ports the proof still catches.

## Evidence so far (snapshot, 2026-10-02)

A port is reported by [evidence level](https://github.com/squid-protocol/gitgalaxy/blob/main/docs/language_status/definition_of_done.md), not as a blanket "proven": L1 translated whole (no hole), L2 equal to the COBOL oracle on every scenario of its case, L3 and L4 adding paragraph and branch coverage, L5 every surviving mutant accounted for. A caller is held at L1 while any program it CALLs or LINKs (transitively) has a hole. **The current counts per estate and level are on the generated [progress page](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/progress.md).** The public estates below are burned (development) estates the translator was built against; a first blind-estate trial began 2026-11-07 ([#8073](https://github.com/squid-protocol/gitgalaxy/issues/8073)).

The rest of this section is a **snapshot from 2026-10-02**, before evidence levels, kept for history.

Deterministic ports:

| Estate | Programs proven | Of them on Db2 | Runs / scenarios | COBOL paragraphs covered | COBOL branches covered |
|---|---:|---:|---:|---:|---:|
| CardDemo (AWS) | 27 | 3 | 615 | 557 / 570 | 1,748 / 2,100 |
| CBSA (IBM CICS Bank Sample) | 8 | 6 | 116 | 109 / 119 | 127 / 195 |
| GenApp (IBM CICS General Insurance) | 13 | 8 | 102 | 47 / 61 | 107 / 231 |

Model-written ports (2026-10-02): all 23 committed CardDemo ports passed their proofs, plus the 17 programs of the [CICS crucible](https://github.com/squid-protocol/gitgalaxy/blob/main/docs/language_status/cics_crucible.md).

What those programs contain includes:

- COACTUPC (4,236 lines), which no model ported in one answer, on 137 scenarios;
- several programs LINKed in one task, proven together;
- named counters (GET COUNTER, GenApp LGACDB01);
- DELAY and ASSIGN PROGRAM (CBSA);
- cursors, including positioned UPDATE;
- `EXEC SQL SET`;
- SYNCPOINT ROLLBACK and abend backout across recoverable files and Db2.

Coverage is lower in GenApp: its error paths LINK to LGSTSQ, which writes past its own data area (register X6). Since #6573 that WRITEQ is written padded on both sides and the task runs on, with X6 stated as an assumption (not settled on z/OS, #4050); only a LENGTH over 32767 is still refused, and a task that reaches that is judged up to the refusal.

**Not proven, on purpose** (2026-10-02; the current list, with reasons, is `proof_sweep.py`'s `KNOWN_UNPROVEN`):

- COCRDUPC writes blanks into a `PIC 9(3)` field that a typed Java field cannot hold (#4085).
- A second case of CBACT04C uses generated keys that mix letters and digits, so ASCII and EBCDIC order pick different records (D1). CBACT04C proves on its other case.

## Running it

| Task | Command |
|---|---|
| Port and prove equivalence cases | `python tests/tools/det_port.py run CASE ... --work DIR` (or `--all-cases`) |
| Which ports does my change move? | `python tests/tools/det_port.py check --work DIR` (against `origin/main`), then re-prove the ones that changed |
| Re-prove every det and model port | `python tests/tools/proof_sweep.py --work DIR` (exit 1 if anything unexpected is unproven, or a listed case now proves) |
| Port inside the porting loop | `port_runner run <project> --ticket KEY --backend det --source-root ESTATE [--style structured] [--typed]` |
| A model refactors a proven port | `port_runner refine <project> --ticket KEY --backend ... --prove-command ...` |

`det_port.py run` and `check` also print a structural parity warning when a port's method or branch-point count falls far from what its COBOL predicts. The warning never fails a proof ([COBOL ↔ Java scan parity](05-18-cobol-java-scan-parity.md)).

Each det port starts with a provenance header (`// gitgalaxy-det-port: COBOL <PROGRAM> (<source>), translated by rule, statement for statement`). GitGalaxy's scanner admits a file that declares it past the gates that would otherwise drop generated code ([Aperture Filter, Declared ports](02-03-aperture-filter.md)), so a det-ported estate scans like any other.

## Limits

- **The oracle is not z/OS.** It is GnuCOBOL 3.1.2 in IBM mode, plus models of CICS, Language Environment and IBM's DISPLAY text, and Db2 for Linux instead of Db2 for z/OS. Every known or suspected difference, and whether a proven program reaches it, is in the [oracle-assumptions register](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/oracle_assumptions.md). Notable entries:
  - **C9:** a POINTER is 8 bytes here and 4 on z/OS, so the offsets after one differ. Each side's COMMAREA is read by its own layout and compared field by field, by name; a POINTER is compared only as NULL or not (an address is not portable).
  - **D1:** text compares in ASCII order, not EBCDIC. Indexed keys that mix letters and digits browse differently, and in-program comparisons have not been audited.
  - **M2:** a Db2 error after a successful statement cannot be injected yet.
  - **Q3:** a CICS task's SQL is one Db2 unit of work in the equivalence test, and a deployment must provide the same. A batch program's repositories autocommit.
- **"Proven" means equal on the case's runs, against GnuCOBOL and GitGalaxy's CICS models.** Read it with the coverage figures, as the evidence level does. Translating a program is not migrating the system, and a port that compiles is not thereby equivalent.
- **Out of scope for the translator:** IMS (DL/I), MQ, pointer arithmetic, ALTER, ENTRY and dynamic CALL stay named holes. Named counters (including DEFINE / DELETE / QUERY COUNTER), channels and containers (`cics_task_containers.py`), CICS web support (WEB OPEN / CONVERSE / SEND / RECEIVE and related commands, `cics_task_web.py`) and DOCUMENT CREATE / RETRIEVE are now modelled in the `CicsTask` runtime, with named refusals where an option is not (for example the containers' CCSID options, or a DOCUMENT template with symbols). The [statement inventory](https://github.com/squid-protocol/gitgalaxy/blob/main/docs/language_status/statement_inventory.md) counts them per estate.
- **A person approves every port.** No tool marks a port approved.

## Further reading
- [det-port design and runtime contract](https://github.com/squid-protocol/gitgalaxy/blob/main/docs/language_status/det_port_design.md)
- [The porting loop](https://github.com/squid-protocol/gitgalaxy/blob/main/docs/language_status/porting_loop.md)
- [COBOL ↔ Java scan parity](05-18-cobol-java-scan-parity.md)
- [Translation survey across six estates](https://github.com/squid-protocol/gitgalaxy/blob/main/docs/language_status/det_survey.md)

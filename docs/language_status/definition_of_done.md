---
description: "Charter (#4722): what 'done' means for a COBOL/CICS/Db2 migration here -- scope, acceptable outcomes per program, done per estate, and what 'supported' means."
---
# Definition of done: what a finished migration means here (#4722)

> Each statement describes what the repository does today, with the page that holds the detail. Part of the readiness-scanner epic (#4721);
> the scanner (#4723-#4725) and the [evidence report](evidence_report/README.md) measure against this page.

## 1. Scope

**In scope:** COBOL programs, with the CICS commands and Db2 SQL they use, and batch file I/O, on IBM z/OS, under
the compile and runtime options recorded for each estate (`tests/equivalence/estate_options/<estate>.json`, #4704).
The COBOL `SORT` / `MERGE` verbs are translated. JCL **utility steps** (SORT, IDCAMS, IEBGENER, DFSORT) are *not* run
([register](oracle_assumptions.md) F4): the generated job refuses them by name.

**Out of scope or parked** (state of 2026-10-09; recheck before quoting):

- Other languages (PL/I, HLASM, REXX, JCL, BMS, Easytrieve): epic #4515 (open). One assembler routine is translated and proven (register A1), as a case, not a capability.
- IDMS DML (refused by name, support is #4532); IMS / DL/I (`EXEC DLI`, `ENTRY 'DLITCBL'`) and MQ ([det_port_design.md](det_port_design.md): "out of scope for this translator").
- `EXEC CICS WEB` family (#4767) and `DOCUMENT` (#4769): open, not modelled.
- National / DBCS data (`USAGE NATIONAL`, `PIC N`, DBCS literals): #4272, open. Refused by name.
- `COMP-1` / `COMP-2` are modelled as IBM hexadecimal floating point (register C6) but what the oracle cannot decide is refused; `INTDATE(LILIAN)` and `ARITH(EXTEND)` are refused (C5).
- Not measured at all by the evidence report: data migration, JCL streams, interfaces, performance, security, cutover (#4514). "Done" in this charter is about **program behaviour**, not the whole migration.

## 2. Per program: the acceptable outcomes

Exactly one of:

1. **Translated and shown equal to a stated level** (below). The level is reported with its numbers, never a bare "OK".
2. **Refused by name, with a reason the customer agrees to.** The translator stops on the construct and says which; the program is listed, not hidden. Refusal families today: IDMS; national / DBCS text; source defects (for example text past column 72, a missing period); a file that is not COBOL; COPY members not in the estate (vendor copybooks) or a COPY of a program member; CICS and Db2 options IBM leaves undefined (register status REFUSED: X5, X13-X30, Q4, Q5); COBOL features the det port does not model (float edge cases, SORT of a table, `CALL identifier` with names the source does not fix, ALTER, ENTRY). See the "refusals kept deliberately" table in [det_port_design.md](det_port_design.md).
3. **Never:** a program translated without proof, or with a construct silently guessed. A construct that cannot be translated is a *hole* by name; a hole keeps the program below L1.

**Levels** (cumulative; `tests/tools/evidence_report.py`, see any report's "How to read this report"):

| level | in one line |
|---|---|
| L0 inventoried | the program is in the estate's survey; nothing more is claimed |
| L1 translated whole | the translator leaves no hole and does not refuse it |
| L2 executed equivalent | a case runs it and the Java port is equal to the COBOL oracle on every scenario of that case |
| L3 paragraph coverage | L2, and the scenarios execute at least the report's bar of its live paragraphs |
| L4 branch coverage | L3, and at least the bar of branch outcomes, net of reviewed infeasible outcomes the program lists |
| L5 mutants accounted for | L4, and every surviving mutant of the port is accounted for |

A level marked `*` is **stale**: last measured against an earlier harness or oracle, not re-checked. It is not a regression and it is not current.

**Decided:** the default promise is **L3** for online (CICS) programs and **L4** for programs the customer marks critical. L2 ships only with explicit customer agreement; L5 on request.

## 3. Per estate: "done"

An estate is done when all of the following hold:

1. Every program the customer wants migrated is at its promised level, or on an agreed refusal list (section 2).
2. **Every oracle caveat the estate relies on is listed; DIFFERS entries it reaches are accepted by the customer, ASSUMED ones disclosed.** The register ([oracle_assumptions.md](oracle_assumptions.md)) has four statuses: MATCHED, REFUSED, DIFFERS, ASSUMED. For each program the report names the ASSUMED / DIFFERS entries its commands reach. Today the report does not measure which register entries a program *actually* reaches; it lists those its commands name. The estate's list is therefore an upper bound, and the charter says so.
3. **Options are recorded with provenance, and the customer confirms every assumed one in writing (#4709).** Compiler and runtime options per estate come from the estate's own build files where they exist and are marked `assumed: IBM default` where they do not (`estate_options/*.json`: each value carries `source`, `quote`, `note`). The evidence report shows each program's effective options and provenance (#4708, in review as PR #4775). What to request, and what is assumed when it is missing: [estate_intake.md](estate_intake.md); `tests/tools/estate_intake.py <estate>` writes the customer's confirmation list.
4. **Evidence is current at release.** The release job runs `evidence_report.py --check --live` (publish.yml); a tag fails while the committed report differs from the repo or any level is stale. The Evidence Refresh bot regenerates reports on main.
5. **Declared differences are listed and approved.** The machinery is #4051 (none exist yet). The owner approves the difference class; each one is listed in the customer's evidence report.

## 4. Policies that define correctness

- **IBM is the reference; GnuCOBOL is the instrument** (#4702). A proof says: on these scenarios the Java port equals the COBOL run by the pinned oracle (GnuCOBOL 3.1.2 `-std=ibm`, plus our CICS, Db2, LE and DISPLAY models). It is never a statement about z/OS. Where the oracle is known to differ from IBM, the register says so; where IBM is silent, the harness refuses by name rather than guess.
- **Options are a first-class input** (#4704). The same source under different options (`TRUNC`, `NUMPROC`, `ARITH`, ...) can behave differently; an estate's results are for its recorded options only, and a proof is invalidated when they change.
- **Fail loudly.** A construct that is not modelled stops the translator or the run by name. A utility step that is not run fails the job (or is logged as skipped on an explicit setting), never a silent success.
- **z/OS calibration is planned** (#4702 part 2, not built). Until it lands, every ASSUMED and DIFFERS entry is unconfirmed on z/OS and no result is calibrated. When it lands: entries that match are promoted, entries that differ become MATCHED by a model or stay declared, and each affected level is re-measured (the pinned oracle's fingerprint changes, so evidence goes stale and is re-proved).

## 5. What "supported" means for a feature (for the readiness scanner, #4723 / #4724)

A COBOL / CICS / SQL feature is **supported** only if all four hold, and the scanner prints which are missing:

1. **Modelled:** the translator and runtime implement it (not a hole, not refused).
2. **In the rule catalogue:** it has an entry with an ID, IBM reference, option dependencies and register status (#4711, **planned**; until it exists this condition cannot be checked and the scanner says "not yet catalogued").
3. **Proven on at least one case:** a case that runs it reaches at least L2.
4. **Calibration status:** MATCHED / ASSUMED / DIFFERS per the register, plus "calibrated on z/OS: no" until #4702 part 2.

A feature that is modelled and proven but ASSUMED is "supported, uncalibrated", not "supported".

## Decisions (owner, 2026-10-09)

1. **Default promised level.** L3 for online programs, L4 for critical programs. L2 ships only with explicit customer agreement.
2. **Assumed options.** An estate is not "done" with options marked `assumed: IBM default`: the customer confirms each assumed option in writing (intake checklist: #4709).
3. **Declared differences.** Owner approval of the difference class is enough; each one is listed in that customer's evidence report.
4. **Register entries.** DIFFERS entries an estate reaches need explicit customer acceptance; ASSUMED entries are disclosed. Until "reached" is measured, the upper-bound list (entries the commands name) is acceptable.
5. **Refusals.** Programs on a standing refusal family (for example IDMS, DL/I, national text) are excluded from an estate's scope by default and listed; any other refusal needs the customer's agreement.
6. **Stale levels.** An estate counts as done only at current levels (no `*`), matching the release gate.
7. **Burned vs blind.** The report labels burned estates (developed against) and blind estates; a blind-estate result is the stronger claim.
8. **Scope.** Data, JCL streams, interfaces, performance, security and cutover (#4514) stay outside this charter.
9. **Coverage bars.** L3 = 100% of paragraphs, L4 = 100% of branches, both net of reviewed infeasible outcomes (decided on #4601).

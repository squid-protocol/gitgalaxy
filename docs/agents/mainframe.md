---
description: "Mainframe ground-truth ledger, field-testing defect log, COBOL porting loop and deterministic port: CI gates, update commands, tiers, and skills to use."
---
# Mainframe / COBOL procedures

Moved verbatim from CLAUDE.md (kept out of the always-loaded context). CLAUDE.md links here.

### Mainframe ground-truth ledger

`tests/cobol_mainframe/ground_truth_ledger.json` lists every place the engine master DB or the
refraction forge disagrees with the hand-verified COBOL answer keys
(`tests/cobol_mainframe/answer_key/`) on the pinned real corpora. Each mismatch maps to a cause,
and each cause has a `kind` (`defect` to fix, `deliberate` by design) and an owning issue.
`mainframe-ground-truth.yml` runs `tests/tools/ground_truth_ledger.py check` on **every** PR.
It fails on an unlisted mismatch (a regression) *and* on a listed one that no longer reproduces
(an improvement, which has to be ratcheted in). After a change that moves a score:
`mainframe_corpus.py fetch`, then `ground_truth_ledger.py update`. New entries come in
`UNTRIAGED` and fail until you `assign` them a cause with an issue; explain the moves in the PR.
Each field is labelled with the weakest verification tier behind it (`llm_verified` <
`cross_verified` < `human_signed`, `cobol_answer_key.TIERS`), or `draft` when its key section is
unsigned. Every tier gates, but only the label says how strongly a number may be quoted.
A key reaches `cross_verified` through `tests/tools/cross_verify.py`: `brief --stage` builds a blind
packet for a fresh-context reviewer model, `grade` lists disagreements, and `sign` refuses until
each one is ruled on against the source. The runbook is in `tests/cobol_mainframe/answer_key/README.md`.
The `mainframe-ground-truth` skill covers the day-to-day work: triaging a ledger failure, merging generated
files after a squash merge, blessing snapshots, running a blind census, and the COBOL reader traps.
`answer-key-guard.yml` posts a semantic diff of key and ledger changes on PRs (`tests/tools/ground_truth_diff.py`).
The runtime-interaction channels still to build (SQL, MQ, IMS, async CICS, JCL flow, lineage) are epic #3445.

### Mainframe field testing (the defect log)

**Every engine or forge defect found on a mainframe estate is logged in
`tests/cobol_mainframe/field_testing.json`, in the same PR that finds or fixes it.** Estates include
pinned corpora, censuses, the ledger, the refraction differential and customer scans. That file is
the estate registry (public keyed corpora, and anonymised private estates) and the defect log.
`tests/tools/field_testing.py report --write` renders
`docs/language_status/cics_field_testing.md`: per ledger field, how many public and private estates
tested it, and whether it is `field-tested`. That takes 2 fresh rounds after its last engine defect,
carrying 300 facts. A round the channel was developed against is not fresh. CI fails when the record
is invalid or the report is stale. A new corpus is a new round; a new channel needs a `fields` entry
with its honest `development_rounds`; key errors are counted automatically. Quote coverage only
from that report. The full protocol is in the `mainframe-ground-truth` skill ("Field testing").

**Port-side blockers (det port, transaction forge, facade, harness, runtime) are logged the same way, in
`tests/cobol_mainframe/port_blockers.json`** (#5051), in the PR that finds or fixes them: the burned estate that
exposed it (or `estate` null with `found_by`), side, class, programs, issue / fixing PR, and whether the fix is a named
refusal. `tests/tools/port_blockers.py report --write` renders `docs/language_status/port_blockers.md`; the
`test_port_blockers.py` test fails on an invalid ledger or a stale page. Burned estates only; `new_class` is derived.

### The porting loop (automated COBOL -> Java)

`tests/tools/porting_loop.py` runs port_runner end to end on one equivalence case. A model ports the program from
its ticket, the harness proves it (outputs, CICS events or CALLs, and every fault run), and a failed proof's
feedback drives the next attempt. Use the `porting-loop` skill: it covers running it (JDK 17, the corpora cache, the
no-tools model), deciding whose a failure is (model, ticket, generator, harness, case), building cases with fault
runs and coverage, and committing a proven port with provenance. CardDemo / CBSA / crucible results are development
numbers, never first-try rates. Results and lessons so far: `docs/language_status/porting_loop.md`.

### The deterministic port (det-port)

`gitgalaxy/tools/cobol_to_java/det` translates a COBOL program to Java with no model, and `tests/tools/det_port.py`
proves the result (batch, CICS and Db2 cases). Use the `det-port` skill: it covers the environment (Docker images,
the Db2 container), debugging a differing scenario, and the checklists for a translator, runtime, harness or oracle
change. After a translator change, `det_port.py check --work DIR` lists the ports it moved against `origin/main`;
re-prove exactly those. Every known or suspected difference between our oracle (GnuCOBOL plus our CICS, Db2 and LE
models) and IBM z/OS is in `docs/language_status/oracle_assumptions.md`; a new model or refusal adds an entry file under `docs/language_status/register/` (ID from `python tests/tools/register.py next X`), and that file is all the PR commits: the page is rendered, never committed (#5057; `generated-docs.yml` publishes it to the `generated` branch, `register.py render` writes a local copy).

Recording a z/OS run (#4702 Part 2; a real z/OS only, after counsel clears it, Q16): `zos_probes.py template > filled.json`, the operator
fills `date`, `compiler` and `observed` (leaving `verdict` blank derives matched / differs against the probe's `oracle_expected`; `refused` /
`abend` are given by hand), then `zos_probes.py ingest filled.json` (a dry run that names every rejection) and `--write` to merge into
`zos_calibration.json`. A re-ingest of the same (entry, probe, date, compiler, runtime options) replaces the record. Then `register.py --check`.

---
name: det-port
description: Work on the deterministic COBOL->Java translator (det-port, gitgalaxy/tools/cobol_to_java/det) and its proofs -- translating a program with no model, proving it against GnuCOBOL (and real Db2), the readability layers (structured / typed / groups), and the checklists for a translator, runtime, harness or oracle change. Covers tests/tools/det_port.py (run, check), equivalence.py proofs, debugging a differing scenario, Db2 cases, and docs/language_status/oracle_assumptions.md. Use when the user says "translate / det-port <program>", "prove <case>", "why does <case> differ", "add Db2 / a new statement to the translator", "did my change move any port", or works on the det-port, Db2 or oracle-assumption issues. For model-written ports and the loop, use the porting-loop skill.
---

The det-port translates a COBOL program to Java with no model: byte storage plus the `cobolrt` runtime, each
statement a call, and every statement it cannot translate a named `Hole`. The equivalence harness proves it against
the COBOL run by GnuCOBOL. Read first:
- `docs/language_status/det_port_design.md`: the method, the runtime contract, and what the proofs found;
- `docs/language_status/oracle_assumptions.md`: where the oracle may differ from z/OS.

## Environment

```sh
cd /nvme-data/projects/gitgalaxy-worktrees/<worktree>
PY=../porting-loop/.venv/bin/python             # the shared venv: an EDITABLE gitgalaxy install of another checkout
export GITGALAXY_MAINFRAME_CORPORA=/nvme-data/projects/gitgalaxy/.mainframe_corpora
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 GITGALAXY_LICENSE_KEY=COMMUNITY_FREE_TIER
```

- **The venv's editable install points at another checkout.** `det_port.py` and `equivalence.py` put their own
  repository first on `sys.path`, but a one-off `python -c "import gitgalaxy"` does not. Check `gitgalaxy.__file__`.
- **Docker images.** `gitgalaxy-gnucobol:3` (batch, CICS) and `gitgalaxy-gnucobol-db2:3` (plus IBM's CLI driver)
  build on first use.
- **Db2.** The container `gitgalaxy-db2` (Db2 Community Edition, port 127.0.0.1:50000, database GGDB) starts on
  first use and stays up. The first start takes minutes.
  - Db2 cases share it, so they take a lock (`~/.cache/gitgalaxy-db2.lock`) and run one at a time.
  - The test password lives in `equivalence_db2.py` and goes to containers through `docker -e`. Never write it
    into a generated script (CodeQL flags clear-text storage).
- **Scratch.** Use the job's tmp directory for `--work` and `--keep`. A reused `--keep` directory carries state.

## Commands

| what | command |
|---|---|
| translate + prove cases | `$PY tests/tools/det_port.py run CASE... --work DIR [--style structured] [--typed [--groups]] [--jobs 2]` |
| translate every case only | `$PY tests/tools/det_port.py run --all-cases --translate-only --work DIR` |
| **did my change move a port?** | `$PY tests/tools/det_port.py check --work DIR` (base: `origin/main`; `--base-ref REF`, `--base DIR`). A runtime class counts only for the ports that name it |
| prove one port by hand | `$PY tests/tools/equivalence.py run CASE --port DIR/CASE/port --keep DIR/proof --faults all` |
| all CI gates | `$PY tests/tools/pr_gates.py` (`--fast` skips the golden masters and the suite) |
| **re-prove everything** (a runtime / harness / oracle change) | `$PY tests/tools/proof_sweep.py --work DIR` -- every det and model port, checked against the cases not proven on purpose; ~1-2 h with Db2 |

Results:
- `DIR/CASE/proof.log` ends with the coverage claim.
- `DIR/CASE/proof/report.json` holds `outputs` (per output or scenario: `records`, `equal`, `diffs`) and
  `java_failed`.
- The Java side's log is `DIR/CASE/proof/java/maven.log`.

## Debugging a differing scenario

1. **Read the diff.** `report.json` → `outputs[<scenario>].diffs` names the event, the field and both values.
2. **Find the paragraph.** Find the COBOL that sets the field. Find the same paragraph in the port, whose methods
   carry `/** <PARAGRAPH>. */` and `// <COBOL statement>` comments.
3. **Run that one scenario on the Java side,** fast, without regenerating:
   1. Keep a copy of `proof/java/in/scenarios.json`, then cut the file down to the one scenario.
   2. Add a `System.err.println("DBG ...")` to the port's copy under `proof/java/java_h2/src/main/java`.
   3. In `proof/java/java_h2`, run `mvn -q -B test -Dtest=EquivalenceRunTest "-DargLine=-Dequivalence.in=../in
      -Dequivalence.out=../dbgout -Dgitgalaxy.data.charset=ISO-8859-1 [Db2: equivalence_db2.java_props()]"`.
   4. Restore `scenarios.json` afterwards.
4. **Decide whose it is, then fix there:**

| owner | sign | fixed before |
|---|---|---|
| **translator** | the Java computes something the COBOL does not say | `WHEN NOT A AND B` negated whole; cursor host variables joined with spaces |
| **runtime** | a `cobolrt` call is wrong for a value | DIVIDE's intermediate; TRIM of all spaces |
| **harness** | the input or the comparison differs between the sides, not the logic | LOW-VALUES dropped on the way to the DTO; PROGRAM-ID read from the sequence columns |
| **case** | a scenario is not what its name says | — |
| **oracle** | GnuCOBOL or our model is not IBM | add or update an entry in `oracle_assumptions.md` |

A translator fix is never a hand edit of a port.

## Checklists

**A translator or runtime change** (`gitgalaxy/tools/cobol_to_java/det/**`):
- [ ] A failing test first: `tests/cobol_mainframe/test_det_translate.py` (translation) or `test_cobolrt.py`
      (runtime, checked against GnuCOBOL).
- [ ] `det_port.py check --work DIR`: every port that changed is re-proven with `det_port.py run`. An unchanged port
      needs no re-proof.
- [ ] A change in the runtime's behaviour: re-prove every det port (`run --all-cases`). Model ports don't use
      `cobolrt`.
- [ ] Add a line under "What the proofs found" in `det_port_design.md` when a proof found the bug.

**A harness or oracle change** (`tests/tools/equivalence*.py`, `tests/equivalence/{cics,db2,faults,le}/**`):
- [ ] Every proof leans on the harness. Re-prove the det ports (`run --all-cases`) and the model ports the change
      can reach (`equivalence.py run CASE --faults all` for each case with a committed `port/`).
- [ ] A new model, refusal or known difference gets its entry in `oracle_assumptions.md` in the same PR.
- [ ] A changed COBOL-side behaviour must also hold for the Java side's generated test (`equivalence_java.py`,
      `equivalence_cics.py` templates).

**A new case:**
- [ ] `tests/equivalence/<case>/case.json`, plus a NOTICE naming the corpus licence and what was derived.
- [ ] Scenarios that reach the error paths: file statuses, RESP conditions, SQLCODEs (+100, -803, -811,
      constraints), and faults.
- [ ] The coverage claim is quoted with the proof. Live code no scenario reaches is listed, or the case is
      strengthened (`tests/tools/strengthen.py`).
- [ ] Scenarios written by a model or a subagent are reviewed, then checked by the proof itself.
- [ ] Db2: a `"db2"` section with `ddl`, `seed`, `compare` and `include_dirs` (DCLGEN). The seed is the corpus's
      own INSERTs where it ships them.
      - A DDL or seed may be a z/OS job (`.jcl`): its in-stream SQL, z/OS-only clauses removed (CBSA, GenApp).
      - `"qualifier"`: the bind's QUALIFIER (the schema unqualified names resolve to). `"symbols"`: install symbols
        (`<DB2DBID>`).
      - `"clock_fields"`: values from `CURRENT TIMESTAMP` (register M4). Declare only what the program really takes
        from the clock.
- [ ] A LINKed program (CBSA, GenApp services): `"linked": true` compares the COMMAREA it leaves. When the generated
      DTO is the caller's record, describe the COMMAREA with the caller's record (the harness says so).
- [ ] A program that LINKs to others: `"programs": [{"program", "program_source"}]` runs them in the same task on both
      sides (no EXEC SQL in those yet). A LINK the case does not run is refused by name.

**Before the PR:**
- [ ] `pr_gates.py`, or at least the ruff audit, mypy, the dead-key audit and the full suite.
- [ ] `ruff format` again after the last edit.
- [ ] Commits and PRs are pre-authorized. Merge when CI is green: wait for `gh pr checks N` to show no pending row,
      parsing its text (no `--json`).
- [ ] Never approve a port on Joe's behalf. Never re-bless a golden master without reviewing what moved.

## Lessons (Db2 on three estates, 2026-10-02)

- **Most failures were the oracle's, not the translator's.** The oracle and the port agreed and both differed from
  IBM (TRUNC(BIN) for STD; the CLI's timestamp text; no backout on the Java side; every file treated as recoverable),
  or an output was never compared (a LINKed program's COMMAREA). Each new estate found such gaps: when a case
  "proves" too easily, ask what is not being compared. Every finding goes in `oracle_assumptions.md`.
- **Real programs carry real defects; the port keeps them.** A FETCH into more host variables than columns, a WRITEQ
  past its FROM area, a reference modification 28K past its item, a misplaced END-IF. Where the outcome depends on
  storage layout, refuse by name (exit 98 / a Hole) rather than prove a guess.
- **A subagent writing scenarios works when it must stop, not work around**: every stop it made was a real gap.
- **The bottleneck is proof throughput** (one Db2 lock, a Maven build per proof). `det_port.py check` scopes a change;
  `proof_sweep.py` re-proves everything when the runtime or harness moves.
- **Process:** format, then test, then commit -- read the test result before committing; never force-push without
  asking (push a rebased branch under a new name instead).
- **A det port declares itself to the scanner.** Its first line is `// gitgalaxy-det-port: COBOL <PROGRAM> ...`.
  GitGalaxy's aperture admits it past the generated-noise gates (wiki 02-03, "Declared ports"); without that line a
  default scan drops most ports as machine output. Keep that line first, and keep emitted lines under 500
  characters where it is free: storage images go one 400-character piece per line.

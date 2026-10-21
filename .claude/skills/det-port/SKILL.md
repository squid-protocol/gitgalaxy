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
PRIMARY=${GG_PRIMARY:-$(dirname "$(cd "$(git rev-parse --git-common-dir)" && pwd)")}   # gitgalaxy-pr-worker.md Setup 1
cd $PRIMARY/../gitgalaxy-worktrees/<worktree>
PY=../porting-loop/.venv/bin/python             # the shared venv: an EDITABLE gitgalaxy install of another checkout
export GITGALAXY_MAINFRAME_CORPORA=${GITGALAXY_MAINFRAME_CORPORA:-$PRIMARY/.mainframe_corpora}
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 GITGALAXY_LICENSE_KEY=COMMUNITY_FREE_TIER
```

- **The venv's editable install points at another checkout.** `det_port.py` and `equivalence.py` put their own
  repository first on `sys.path`, but a one-off `python -c "import gitgalaxy"` does not. Check `gitgalaxy.__file__`.
- **Docker images.** `gitgalaxy-gnucobol:3` (batch, CICS) and `gitgalaxy-gnucobol-db2:3` (plus IBM's CLI driver)
  build on first use.
- **Db2.** The container `gitgalaxy-db2` (Db2 Community Edition, port 127.0.0.1:50000, database GGDB) starts on
  first use and stays up. The first start takes minutes.
  - Db2 cases run side by side on a pool of databases in it (GGDB, GGDB1 ..; `GITGALAXY_DB2_POOL`, default 4),
    one case a database (a lock file each under `~/.cache`; GGDB's is `gitgalaxy-db2.lock`, the one older checkouts
    take). A pool database is created on first use (about 30 s). The harness keeps each database active: an
    inactive one costs about a second a connect.
  - The test password lives in `equivalence_db2.py` and goes to containers through `docker -e`. Never write it
    into a generated script (CodeQL flags clear-text storage).
- **Estate cache.** The corpus scan and the corpus refactor every case starts from are built once and kept under
  `~/.cache/gitgalaxy-equivalence` (`equivalence_cache.py`), keyed by the corpus commit and state, every engine
  file, and the `GITGALAXY_*` environment. Any engine edit is a new key. `GITGALAXY_EQUIV_CACHE=off` builds every time.
- **Scratch.** Use the job's tmp directory for `--work` and `--keep`. A reused `--keep` directory carries state.

## Commands

| what | command |
|---|---|
| translate + prove cases | `$PY tests/tools/det_port.py run CASE... --work DIR [--style structured] [--typed [--groups]] [--jobs 2]` |
| translate every case only | `$PY tests/tools/det_port.py run --all-cases --translate-only --work DIR` |
| **did my change move a port?** | `$PY tests/tools/det_port.py check --work DIR` (base: `origin/main`; `--base-ref REF`, `--base DIR`). A runtime class counts only for the ports that name it, but a change to the shared `CicsTask.java` marks every port changed in `check`: re-prove the ones that can reach the changed code and name them in the report (#5147); `check` also marks every port changed after any `DetCics.java` edit, so read the per-port diff line (`DetCics.java N lines`) before assuming behaviour moved. `CicsTask.java` is the string `CICS_TASK_JAVA` in `cobol_to_java_transaction_forge.py`: re-prove only the ports whose `*Service.java` moved, plus a sample using the touched verb (#5185, #5187, #5204) |
| structural parity of one port | printed by `run` and `check` as `parity warning:` lines (`parity_warnings` in summary.json / check.json); `tests/tools/det_parity.py`, fit and bands in `det_port_design.md` |
| **run a det case** | `det_port.py run`: only it applies the deterministic port. `equivalence.py run` uses the generated skeleton, not the deterministic port (#5147) |
| prove one port by hand | `$PY tests/tools/equivalence.py run CASE --port DIR/CASE/port --keep DIR/proof --faults all` |
| all CI gates | `$PY tests/tools/pr_gates.py` (`--fast` skips the golden masters and the suite) |
| **re-prove everything** (a runtime / harness / oracle change) | `$PY tests/tools/proof_sweep.py --work DIR` -- every det and model port, checked against the cases not proven on purpose; det ~9 min at `--jobs 4`, model ~12 min (2026-10-02) |

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
| **oracle** | GnuCOBOL or our model is not IBM | add or update an entry file in `docs/language_status/register/` (the page is rendered, not committed: #5057) |

A translator fix is never a hand edit of a port.

## Checklists

**A translator or runtime change** (`gitgalaxy/tools/cobol_to_java/det/**`):
- [ ] A failing test first: `tests/cobol_mainframe/test_det_translate.py` (translation) or `test_cobolrt.py`
      (runtime, checked against GnuCOBOL).
- [ ] `det_port.py check --work DIR`: every port that changed is re-proven with `det_port.py run`. An unchanged port
      needs no re-proof.
- [ ] Read any `parity warning:` lines from `check` before the proofs: a port whose methods or branch points left
      the estate's band dropped, duplicated or over-expanded something. A warning never fails a proof; a change
      that reshapes every port on purpose refits `det_parity.MODEL`.
- [ ] A change in the runtime's behaviour: re-prove every det port (`run --all-cases`). Model ports don't use
      `cobolrt`.
- [ ] Add a line under "What the proofs found" in `det_port_design.md` when a proof found the bug.

**A new EXEC CICS command or option (#4270 slices):** follow the `cics-command-slice` skill -- census
(`cics_census.py`), both runtimes, a hand-traced crucible case (`crucible_case.py`), the det-port proof
(`cics_case_ports.py`), before / after survey, and the crucible release / pin bump (`crucible_release.py`).

**A harness or oracle change** (`tests/tools/equivalence*.py`, `tests/equivalence/{cics,db2,faults,le}/**`):
- [ ] Every proof leans on the harness. Re-prove the det ports (`run --all-cases`) and the model ports the change
      can reach (`equivalence.py run CASE --faults all` for each case with a committed `port/`).
- [ ] A new model, refusal or known difference gets its entry file in `docs/language_status/register/` (`register.py next X` / `render`) in the same PR.
- [ ] A changed COBOL-side behaviour must also hold for the Java side's generated test (`equivalence_java.py`,
      `equivalence_cics.py` templates).

**A new case:**
- [ ] `tests/equivalence/<case>/case.json`, plus a NOTICE naming the corpus licence and what was derived.
- [ ] Scenarios that reach the error paths: file statuses, RESP conditions, SQLCODEs (+100, -803, -811,
      constraints), and faults. A Db2 case gets one SQL-fault task per statement it executes by default
      (`--sql-faults auto`, register M2); declare a scenario's own `sql_faults` (`line`, or `table` + `verb`) for a
      fault the default does not choose. Read the "not judged" lines: a path into a named hole is no proof.
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
- [ ] `pr_gates.py --fast` and `pr_gates.py --ratchets`. The full suite runs in CI, not locally (owner, 2026-10-07).
- [ ] `ruff format` again after the last edit.
- [ ] Commits and PRs are pre-authorized. Merge when CI is green: wait for `gh pr checks N` to show no pending row,
      parsing its text (no `--json`).
- [ ] Never approve a port on Joe's behalf. Never re-bless a golden master without reviewing what moved.

## Lessons (Db2 on three estates, 2026-10-02)

- **Most failures were the oracle's, not the translator's.** The oracle and the port agreed and both differed from
  IBM (TRUNC(BIN) for STD; the CLI's timestamp text; no backout on the Java side; every file treated as recoverable),
  or an output was never compared (a LINKed program's COMMAREA). Each new estate found such gaps: when a case
  "proves" too easily, ask what is not being compared. Every finding goes in the register (`docs/language_status/register/`, rendered to `oracle_assumptions.md`).
- **Real programs carry real defects; the port keeps them.** A FETCH into more host variables than columns, a WRITEQ
  past its FROM area, a reference modification 28K past its item, a misplaced END-IF. Where the outcome depends on
  storage layout, refuse by name (exit 98 / a Hole) rather than prove a guess.
- **A subagent writing scenarios works when it must stop, not work around**: every stop it made was a real gap.
- **The bottleneck is proof throughput** (one Db2 lock, a Maven build per proof). `det_port.py check` scopes a change;
  `proof_sweep.py` re-proves everything when the runtime or harness moves.
- **Process:** format, then test, then commit -- read the test result before committing; never force-push without
  asking (push a rebased branch under a new name instead).
- **Readability rules: measure the det output, not the model ports.** The construct map ranked "88 tests as named
  methods" first (~3,800 lines, from the model ports' shape); in the det output each test was already one expression,
  so naming them saved nothing (+0.4%). Counting the det lines by kind (field declarations 17.6%, storage images
  11.2%) found the real saving: one-line field declarations (-20.7%). Every rule ships only through the full sweep,
  a 3-run determinism check, and the parity / invariance tests. Typed values (B3) were measured the same way: a
  readability rule, size-neutral (+1.0%); the size lives in byte storage the proof needs, and in per-entry repetition
  (`initialState()`, −2.3%). The next count found that 10,083 of 17,436 byte `Field`s were named nowhere: views of
  copybook and map items the program never touches. Dropping a view keeps every stored byte, so it is free for the
  proof: −14.0% code lines, median ×3.21 → ×2.65 of the COBOL. Look for dead code the translator emits before
  looking for shorter spellings of live code.
- **A det port declares itself to the scanner.** Its first line is `// gitgalaxy-det-port: COBOL <PROGRAM> ...`.
  GitGalaxy's aperture admits it past the generated-noise gates (wiki 02-03, "Declared ports"); without that line a
  default scan drops most ports as machine output. Keep that line first, and keep emitted lines under 500
  characters where it is free: storage images go one 400-character piece per line.
- **Equivalence case traps.** A case's `"commarea"` is `{"segments": [{"copybook", "record"}]}` or null, never a name, and the segment's copybook field names must match the program's DFHCOMMAREA (#5185). A scenario meant to stay on a validation path must be checked in the COBOL trace (`proof/cobol/scenarios/*/trace.txt`): an EPSNBRVL error text does not zero the number it returns (#5188). When a field's justification changes, check what it does to every scenario's meaning (a NUM field with the length-typed assumption turns a short typed value into leading zeros under `<f>I(1:<f>L)`), not only which scenarios fail (#5193). In a proof run the GnuCOBOL oracle side refuses before the Java side runs, so fixing a Java failure can surface a different refusal (#5193).
- **A pointer tested for NULL needs no runtime change.** `Cobol.compareFigurative(Field, LOW_VALUES, CS)` already tests a pointer for NULL (all-zero handle) (#5203).
- **A relation involving NULL must skip `cond_relations` / `self.relation()`**, or the OSVS plan list goes out of step (#5203).
- **`docker save <name>@sha256:...` + `docker load` drops the digest name** (a digest cannot be a local tag): a
  cache-restored digest-pinned image needs a local alias; check `docker image inspect <digest-ref>` after a load (#5265).
- **Use a fresh `--work` dir for `det_port.py check`**: a reused scratch dir holds stale output that looks conclusive
  (#4884). It removes its `base-tree`; to compare against main again, re-run the base from a fresh worktree (#5290).
- **No equivalence case yet?** `det_survey.py --corpus <name> --program <path> --no-compile --work <scratch>`
  translates one program in seconds. Design-doc blocker prose can outlive the fix: confirm with a translation run
  before treating a program as blocked (#4949).
- **A facade-only runtime helper goes in the generated service, gated on a translator flag, not in `det/cobolrt/**`**:
  a `DetCics.java` edit moves ~every det port in `det_port.py check` (#5290). `FACADE_JAVA` in
  `tests/tools/equivalence_cics.py` is a plain string spliced into an f-string: use a `__PKG__` placeholder replaced at
  the call site, not `{pkg}` or doubled braces (#5290).
- **`equivalence.py run --record` writes evidence.json even when the proof fails**: check the status line says
  "proven" before committing (#5322). It prints "0/N events equal" for fault scenarios (java-facade mode, not a
  failure): `det_port.py run` is the real proof (#5324).
- **An unnamed option like `!1` aborts the whole CICS case run with an X8 bounds error**: name it in
  `bounds_refused` or leave the scenario out (#5322).
- **`proof_sweep.py --record-ledger` needs `--aggregate`**; otherwise `det_coverage_ledger.py update SWEEP_DIR`, rerun
  after any case.json edit (#5324).
- **A crucible port's overlay can contain the shared translator runtime**: sample only the port's own files or
  mutation scores measure nothing (#5326). PROVENANCE `files` counts the crucible sample (4-30 files), not the
  upstream tree (#5357).

---
name: cics-command-slice
description: Land one #4270 CICS command slice end to end -- census of the command's options over the burned and non-burned corpora, the spec entry (gitgalaxy/standards/cics) and the det translator (outcome()/condition() with RESP2), BOTH runtimes (CicsTask/DetCics and ggcics.c), an additive cics-crucible SPEC change if needed, a hand-traced crucible case, the proofs (cobol-stub and the det port), the X-register entry, the before/after survey, ratchets, the two draft PRs and the crucible release / pin bump. Also the equivalence harness's working rules (Db2 generated rows, where reports land, re-proving evidence). Use when the user says "next #4270 slice", "add EXEC CICS <verb> / <option> to the translator", "census of <verb>", "new crucible case for <command>", "cut a cics-crucible release" or "bump the cics-crucible pin".
---

A slice teaches the det translator (`gitgalaxy/tools/cobol_to_java/det`) one more slice of EXEC CICS, proves it
against a hand-traced cics-crucible case, and measures what it unlocked in real estates. The tools below replace the
scratch scripts every slice used to rebuild (env.sh, count_*.py, survey.sh + compare.py, det_overlays.py,
gen_expected.py). Merged slices to copy conventions from: #4575 (channels / containers), #4578 (START / RETRIEVE),
#4582 (ASSIGN); release flow: cics-crucible `RELEASING.md` and gitgalaxy #4581 (a pin bump).

## 0. Environment (once per worktree)

```sh
PY=/path/to/venv/bin/python        # needs the full AND translator extras
eval "$($PY tests/tools/equivalence_env.py --shell)"                      # PYTHONPATH, corpora, crucibles, JDK 17
eval "$($PY tests/tools/equivalence_env.py --shell --crucible-dir $SCRATCH/crucible --unpinned)"  # a case branch
$PY tests/tools/equivalence_env.py --check                                 # PASS / FAIL per item
export CICS_CENSUS_CORPORA=$SCRATCH/census     # clones of the non-burned census repos (see "Burned / non-burned")
```

Traps `--check` exists for:
- **JDK 17.** Under the default JDK 21 every forge-compile / java cell FALSELY fails ("release version 17 not
  supported"). The tool exports JAVA_HOME / JDK_17 = a verified JDK 17 and refuses (exit 2) when there is none.
- **LANGUAGE_CRUCIBLE_PATH** wrong or off its pin: the golden check fails falsely. Checked against
  `tests/_crucible_pin.py`.
- **cics-crucible off the pin** (`tests/_cics_crucible_pin.py`): phantom cells. A case branch or an untagged release
  commit is deliberately off-pin: `--crucible-dir DIR --unpinned` (CICS_CRUCIBLE_ALLOW_UNPINNED=1), never the shared
  pin checkout.
- **tree_sitter_language_pack missing:** the det tests SKIP silently. Say so if they skip.

## 1. Checklist for one slice

- [ ] **Census.** `$PY tests/tools/cics_census.py usage VERB [VERB ...]` -- per program the options each
      `EXEC CICS VERB` uses, totals per option, burned / non-burned. Multi-word verbs: `"SEND TEXT"` or `SEND-TEXT`.
      `--pli` adds PL/I programs (flagged: the det translator takes COBOL only). Names and counts only.
- [ ] **Pick by blockers, not by frequency** -- the `blocker-slice` skill is the loop and its rules: measure on
      the baseline first (`cics_census.py blockers --baseline`, `--unmask GAPKEY` for a `*` row) to RANK the work
      (a guide, not a gate: work needed again lands even if it moves no program today), the
      proof-level ranking (`proof_blockers.py`), the honest-refusal patterns and the brief template. A gap may be
      a CICS verb, a grammar gap (#4462) or a missing copybook; the census above is the tiebreaker. Note what you
      leave refused and why.
- [ ] **Spec entry first** (`gitgalaxy/standards/cics`): promote the command's name-only entry to a full one
      (options, refusals with reasons and register, groups, outcomes with RESP2, facts); `det/cics.py` and the stub
      read it. The runtimes stay hand-written, and no crucible log is derived from the spec. Then
      `cics_spec_status.py render`.
- [ ] **Before survey** (now, on the unchanged branch): `$PY tests/tools/cics_census.py survey --out $SCRATCH/s
      --label before --verb VERB` (det_survey.py, translation only; ~minutes per estate; background it with
      `tests/tools/box/heavy-run.sh`).
- [ ] **Translator** (`det/cics.py`): OPTIONS and the refusals come from the spec entry (spec PR 2); every option it
      does not honour refused BY NAME with the entry's reason; conditions through
      `outcome()` / `conditions()` with the RESP2 IBM documents; HANDLE CONDITION / NOHANDLE / RESP all honoured.
      A failing test first in `tests/cobol_mainframe/test_det_translate.py`.
- [ ] **BOTH runtimes**, the same semantics: the Java `CicsTask` / `DetCics` (cobolrt) AND the stub
      `tests/equivalence/cics/ggcics.c` (+ `tests/tools/equivalence_cics.py`). A fact the runtime cannot know (a
      start code, a user id, a terminal) is STATED by whoever runs the task (`CicsTask.withX`, `$GGCICS_X`), never
      guessed; an unstated fact is refused at run time.
- [ ] **SPEC** (cics-crucible): only if a log must say something new. Additive optional keys only (SPEC rule 5:
      a meaning change bumps the format major); update `schema/*.json` and `tools/validate.py` in the same PR.
- [ ] **Crucible case**, hand-traced:
  - `$PY tests/tools/crucible_case.py new <trap>/<case-id> --programs A,B --transids GT41,GT42
    --crucible $SCRATCH/crucible --gen $SCRATCH/gen_expected.py` (on a case branch of your own clone).
  - Write the programs (original code only; a breadcrumb in a TS queue or on the screen for every behaviour that is
    not an event -- ASSIGN, HANDLE, ... are not events), the CSD, NOTES.md (every section; quote IBM with URLs).
  - Trace every log BY HAND from IBM's documentation into the gen script, using `tests/tools/crucible_events.py`
    (event constructors checked against SPEC 6.2: a missing or unknown key fails in the script).
  - `$PY tests/tools/crucible_case.py check-hand-derived $SCRATCH/gen_expected.py` -- fails if the script imports
    anything beyond the stdlib + crucible_events. Then `python3 tools/validate.py cases/<trap>/<case-id>`.
- [ ] **Proofs** (with `--crucible-dir ... --unpinned`):
  - cobol-stub: `$PY tests/tools/cics_crucible.py --cases <case> --sides cobol-stub --offline --keep W1 --out O1`.
  - det port: `$PY tests/tools/cics_case_ports.py <crucible>/cases/<trap>/<case> --work W2 --forge --ports P`
    (forge-compile, then each program's det overlay + `P/summary.json`: statements / translated / holes), then
    `$PY tests/tools/cics_crucible.py --cases <case> --sides cobol-stub java-ported --offline --ports P --keep W3
    --out O3`. A hole on a path no scenario runs is not proven by a passing cell.
  - A divergence is a bug report against the runtime / translator, never a reason to edit the log.
- [ ] **Refusals registered:** a new X-number: `register.py next X` (take it when the issue is filed), then one file
      `docs/language_status/register/Xnn.md` (front matter incl. the summary-table fields; body: ASSUMED / REFUSED, what
      IBM says, which case proves it) and `register.py render`. Never edit `oracle_assumptions.md` by hand.
- [ ] **After survey:** `... survey --out $SCRATCH/s --label after --verb VERB`, then
      `$PY tests/tools/cics_census.py compare $SCRATCH/s --verb VERB`: per program translated / statements before ->
      after, the holes left (deduped, line numbers stripped), "translated whole N -> M (non-burned a -> b)" and the
      holes naming the verb. Quote the summary lines in the PR; name the next blocking holes as follow-ups.
- [ ] **Ratchets:** `tests/tools/box/heavy-run.sh $PY tests/tools/pr_gates.py --ratchets`, then
      `pr_gates.py --fast`. The full suite is CI's job (owner, 2026-10-07): never run it locally, and never two gate
      runs at once in one worktree; `pr_check.py --merge` merges only on green CI. A skip is not a pass. `proof_sweep.py --det-only --skip-db2` when the runtime changed.
- [ ] **After merge:** `pr_check.py N` before merging (`--merge` squash-merges only when green), then
      `cics_census.py history append --pr N` (blocker-slice section 4).
- [ ] **Two draft PRs:** gitgalaxy ("Part of #4270 (slice N: ...)", labels enhancement / testing /
      legacy-modernization) and the cics-crucible case PR (a "Cross-repo" note: companion PR, merge order, what
      re-runs). No tag or pin bump in either.
- [ ] **Release (when the owner batches it):** see section 3.

## 2. Traps (each cost a slice a round trip)

- **importorskip.** Any test that touches the translator (det, tree-sitter) starts with
  `pytest.importorskip("tree_sitter_language_pack")`: the ground-truth CI job installs no `translator` extra
  (#4560 / #4563 broke on it).
- **test_tool_regex_redos** (#4477) is flaky under load: rerun once before blaming your regex.
- **The full-suite OS grid does not run on PRs** (#4518). For a path- or OS-sensitive harness change dispatch it:
  `gh workflow run full-suite-gate.yml --ref <branch>`.
- **Never derive an expected log from an implementation** -- not the stub, not a port, not an emulator (crucible
  AGENTS.md rules 2-3). `check-hand-derived` guards the script; you guard the values.
- **Known local-only failure:** `test_porting_loop_tooling.py::test_the_loops_committed_ports_are_proven[*]`.
- A pin-bump PR in flight moves `tests/_cics_crucible_pin.py`, `tests/cics_crucible/{baseline,coverage}.json` and the
  port evidence: never touch those in a slice PR.

## 3. Release flow (cics-crucible RELEASING.md, done for v0.4.0 and v0.5.0)

1. Batch: several case PRs merged on the crucible's main, each green on `tools/validate.py`.
2. Draft the notes: `$PY tests/tools/crucible_release.py notes $SCRATCH/crucible --since vPREV --tag vNEXT` --
   counts and deltas, added cases by trap with scenarios, the SPEC diff flagged additive or NOT (old cases
   validated under the new validator), "no log corrected" (no file under a pre-existing case changed), validate.py,
   the RELEASING.md row. Fill in the TODO sentences.
3. **Phase A** (gitgalaxy, ledger only): with the crucible checked out at the UNTAGGED commit and
   `CICS_CRUCIBLE_ALLOW_UNPINNED=1`, run `cics_crucible.py --update-baseline` and review every moved cell (new cells
   only for new cases; a newly failing cell on an unchanged case is a gitgalaxy regression). Do not move the pin.
4. **Tag** (crucible): only after the owner approves -- `git tag -a vX.Y.Z <commit>`, push, `gh release create`.
5. **Phase B** (gitgalaxy, one PR): `PINNED_REF`, baseline / coverage, re-prove the committed ports
   (`crucible_port_provenance.py reprove`), evidence (`evidence.py prove` / `render`), then
   `$PY tests/tools/crucible_release.py pin-check vPREV` -- every mention of the old tag left, provenance history
   excluded, other repos' tags listed apart. Then the RELEASING.md row in the crucible.

## 4. Burned / non-burned

One source: `tests/tools/estate4_draw.py`. BURNED = the burned estates (`BURNED_NAMES`: CardDemo, CBSA, GenApp,
zECS, DBB MortgageApplication, the cicsdev async credit-card example); everything else is non-burned. The census repos (`INELIGIBLE_LIST` minus the burned
ones) are cloned into a scratch dir and given as `--census-corpora` / `$CICS_CENSUS_CORPORA`; they are read ONLY
through translator output and option counts, and nothing from them is ever committed (names and counts in a PR body
are fine). `cics_census.py` warns about a census-root corpus that is not on the list: reading a possible blind
4th-estate candidate through the translator burns it. Never open estate4 candidates (`estate4_candidates.json`).

## 5. Equivalence harness

- **Db2 generated rows** (#4507, #4577): a case's `"db2"` section may say `"seed": "@generate"` -- rows generated from
  the tables' declarations (columns, NOT NULL, keys, foreign keys) with each type's boundary values and NULLs --
  and `"compare_sql": true` compares, per task, what Db2 answered each side (SQLCODE, SQLSTATE, rows), not only the
  tables left behind (`tests/tools/equivalence_db2.py` docstring).
- **Where results land:** `equivalence.py run CASE --keep DIR` -> `DIR/report.json` (`outputs[<scenario>].diffs`,
  `java_failed`), the Java side's log `DIR/java/maven.log`; `det_port.py run` -> `WORK/<case>/proof/report.json` and
  `proof.log`; `cics_crucible.py --out O` -> `O/results.json` + `O/report.md`, `--report-dir R` -> `R/report.json`
  (a port proof); `--keep W` keeps `W/<case>/{forge,cobol,java}`.
- **Re-proving evidence:** `$PY tests/tools/evidence.py status` shows what is stale; re-prove with
  `evidence.py prove KEY ...` (or `refresh --stale`) and `evidence.py render`. Never hand-edit an evidence record or
  a `reproven` entry, and never drop or write an approval -- only a person runs `evidence.py approve`.
- Debugging a differing scenario, Db2 cases and the checklists for a translator / runtime / harness change: the
  `det-port` skill.

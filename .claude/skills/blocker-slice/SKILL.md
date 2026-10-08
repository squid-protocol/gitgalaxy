---
name: blocker-slice
description: The #4270 blocker-driven loop -- pick the next det-translator / harness slice by the programs it makes translate WHOLE (cics_census.py blockers) or PROVEN (proof_blockers.py), measure before and after against the baseline survey (a guide, not a gate), land it spec-first, record it in the blockers history. Covers measuring and ranking, spec-first for CICS commands, the honest-refusal patterns, the environment, the trap list and the brief template an orchestrator hands an agent. Use when the user says "next blocker", "what unlocks the most programs", "blocker slice", "rank the gaps", "what stops <program> being proven", or briefs an agent on #4270 work. For the per-command checklist (runtimes, crucible case, release) it hands over to cics-command-slice; for translator / proof debugging to det-port.
---

The unit of progress is a **program**, not a keyword: programs translated WHOLE (no hole), then programs PROVEN
equivalent. A slice is whatever moves the most programs -- a CICS command, a grammar gap (#4462), a missing
copybook, a refusal, a stated fact, a harness feature. This skill is the outer loop;
`cics-command-slice` is the checklist for a CICS-command slice inside it, `det-port` for the translator and proofs.

Why a separate skill: the loop picks non-CICS work as often as CICS work (#4588 wide characters, #4590 listing
control and cut literals, #4592 FUNCTION RANDOM -- none a CICS command), so it cannot live inside a per-command
checklist; and an orchestrator needs one page for measuring, ranking and the brief, not the release flow.

## 1. Measure first (before any code)

```sh
PY=/path/to/venv/bin/python                                   # full AND translator extras
eval "$($PY tests/tools/equivalence_env.py --provision)"     # private pinned crucible + census clones, exports
$PY tests/tools/cics_census.py blockers --baseline            # translate-level ranking on main's cached survey
$PY tests/tools/cics_census.py blockers --baseline --unmask "GAPKEY"   # for a `*` row: what hides behind it
$PY tests/tools/proof_blockers.py SURVEY_DIR --label LABEL [--sweep SWEEP_DIR]
    # proof-level ranking (below); SURVEY_DIR / LABEL: the baseline survey `survey --baseline` reports
```

- `blockers --baseline` reads the survey cached for main's SHA (`survey --baseline [--root DIR]` builds it; a
  nightly CI job keeps it fresh). Rank: `only` (the gap is all that is left, burned / non-burned), then `one_away`.
  Non-burned first: burned estates already have ports.
- A `*` row refuses the whole program, so its count is an upper bound: run `--unmask GAPKEY` to see the gaps behind
  it before promising anything.
- **The numbers guide; they do not gate** (owner, 2026-10-07). The rankings say what to do FIRST and the before /
  after numbers show progress at every rung (translated whole; executed-equivalent; 100% paragraphs; 100% branches)
  and as coverage percentages. Work that will clearly be needed again -- a harness feature, a missing event, a stated
  fact, an oracle decision -- lands even when it moves no program today; say in the PR what it unblocks next. Stop
  only for a real blocker: an owner decision, semantics you would have to guess, or a rule (the blind estate,
  census repos counts-only). The 2026-10-07 lesson: measuring only the top bar stopped four slices with reusable
  work (EIBTASKN moved 22 -> 29 programs to full paragraph coverage and still had no PR).
- Proof level: `proof_blockers.py` ranks, for the programs already WHOLE, what stops each being PROVEN: `no case`,
  `known unproven: #issue` (det_sweep_baseline.json), `scenario differs: KIND`, `not proven in CI: Db2 case`,
  `coverage: ...`, `fact: EIBTASKN` / `fact: ASSIGN USERID` (a runtime fact no harness states). Without `--sweep`
  it trusts main's CI det-sweep ratchet for non-Db2 cases; pass a local `proof_sweep.py --det-only --work DIR` for
  Db2 verdicts and coverage. A new equivalence case is the usual cure for `no case`; a fact gap needs the fact
  stated on BOTH sides first (C12 / EIBTASKN).

## 2. Land it spec-first (CICS commands)

- A new command or option goes into `gitgalaxy/standards/cics` FIRST: promote the name-only entry
  (`commands/api.py`: name, IBM URL, reason) to a full entry (options, refusals with reasons and X-register, groups,
  outcomes with RESP2, stated facts) in its family module. `det/cics.py` and the stub (`equivalence_cics.py`) read
  OPTIONS, refusals, groups and DFHRESP from it -- never add a table edit there.
- The **runtimes stay hand-written** (`CicsTask` / `DetCics`, `ggcics.c`): the spec says what we model, not how.
- **Crucible logs are never derived from the spec** (nor from a runtime or a port). The gen script is traced by
  hand from IBM's documentation; `crucible_case.py check-hand-derived` fails if it imports anything but the stdlib
  and `crucible_events`.
- `python tests/tools/cics_spec_status.py render` regenerates `docs/language_status/cics_spec_status.md` (a test
  fails on a stale page); after a slice, `refresh --census --crucible DIR` first. A spec PR adds its row to
  `SPEC_PRS_DONE` there.
- Then the `cics-command-slice` checklist: both runtimes, the hand-traced crucible case, proofs, X-register entry.

## 3. Honest refusals (the patterns that made programs whole without guessing)

- **Narrow the refusal to the statement** (#4588, D4): a wide character (UTF-8 em dash) in a PROCEDURE DIVISION
  literal used to refuse the whole program; now the statement holding it is a hole by name and the rest translates.
  A VALUE, a national / DBCS literal or a name stays refused whole.
- **Name a source defect, do not repair it** (#4590): a literal left open at column 72 with text past column 72 and
  no continuation is refused as `source text past column 72` (NexusBank's five programs). Fixed-form COBOL does not
  read past 72, so these cannot become whole honestly; they stay in the ranking as a named refusal.
- **State the oracle's behaviour as an assumption** (#4592, C12): FUNCTION RANDOM runs on the oracle's generator
  (GnuCOBOL's glibc sequence), written down as C12 -- a proof then says "given the oracle's numbers", never "z/OS's
  numbers". The seed (EIBTASKN, 0 on both sides) is a stated fact of the run; a case that varies it states it on
  both sides first. Seeds IBM does not allow are refused at run time by name.
- Every new assumption or refusal gets its `oracle_assumptions.md` entry (summary row AND `### Xnn.` / `Cnn.`
  section) in the same PR.

## 4. After it lands

- `pr_check.py N` before merging (CI, mergeability, the ratchet files a PR must touch); `pr_check.py N --merge`
  squash-merges only when green. Drafts first; the merge is the orchestrator's call.
- The purchaser-facing evidence report (#4601, `docs/language_status/evidence_report/`) reads the det-sweep and
  crucible baselines, `cics_spec_status.json`, the cases, the evidence records and `oracle_assumptions.md`: a PR that
  changes one does NOT commit the rendered report (#4703): the evidence-refresh bot regenerates it on main and PR CI
  shows the level deltas (advisory). After a slice merges, `evidence_report.py --all --baseline` re-measures the translation on the new
  baseline. Burned estates only; it never writes an evidence record.
- `cics_census.py history append --pr N` after each merged slice (`docs/language_status/blockers_history.jsonl`);
  `history show` is the trend. Quote `compare --before-baseline` ("translated whole N -> M (non-burned a -> b)") in
  the PR.

## 5. Traps

- **Shared cics-crucible checkout off the pin.** Never move it; `equivalence_env.py --provision` gives a private
  clone at `tests/_cics_crucible_pin.py`'s ref (or `git clone <shared> $SCRATCH/crucible && git checkout vX.Y.Z`).
  A case branch runs with `--crucible-dir DIR --unpinned`.
- **`gh issue view` / `gh pr edit` fail** on this repo (Projects-classic GraphQL): use `gh api` REST
  (`gh api repos/squid-protocol/gitgalaxy/issues/N`, `-X PATCH .../pulls/N -f body=...`).
- **ruff is pinned at 0.16.0** (CI's): a different local ruff reformats unrelated lines. `ruff format` only the
  files you changed; never `ruff format tests/tools/estate4_draw.py` (its hand layout is load-bearing for the draw).
- **GnuCOBOL source in tests stays within column 72**: fixed-form COBOL drops columns 73-80, so a long line in a
  test fixture silently loses its tail (and now trips the #4590 refusal).
- **A duplicate rosetta-audit run** on a PR gets cancelled by the concurrency group; the other run is the real one.
  A cancelled run is not a failure.
- `cics_census.py survey` uses `$CICS_CENSUS_CORPORA` even when `--no-census` is given: unset it for a survey of
  one extra root only.
- Census repos are read only through translator output and counts; nothing from them is committed but counts.
  Never open `docs/language_status/estate4_candidates.json`.
- JDK 17 (`equivalence_env.py` exports it), `importorskip("tree_sitter_language_pack")` in any translator test, and
  the other traps in `cics-command-slice` section 2.

## 6. Brief template (orchestrator -> agent)

The agent definition (`gitgalaxy-pr-worker`) and these skills carry the setup and rules; the brief carries only:

```
Issue: #NNNN (part of #4270). Skills: blocker-slice, cics-command-slice (if a CICS command), det-port.
Gap: `<GAPKEY>` -- only gap for A programs (burned b / non-burned n), one away for C; behind it (--unmask): ...
Acceptance: translated whole X -> >= Y (non-burned a -> >= b) by `compare --before-baseline`; refusals named, no
  guessed semantics; X-register entry; spec entry first (if CICS); ratchets green; draft PR.
Measure: before / after numbers at every rung in the PR; land the work (stop only for a real blocker).
Coordination: siblings / merge order / files not to touch (e.g. a pin bump in flight owns the crucible baseline).
```

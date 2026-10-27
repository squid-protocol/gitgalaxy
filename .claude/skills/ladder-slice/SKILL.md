---
name: ladder-slice
description: Land one evidence-ladder slice (#6072) -- lift burned programs L2->L3 (every live paragraph run) or L3->L4 (every net branch outcome taken, or a reviewed infeasible outcome) by adding equivalence scenarios. Plan with GitGalaxy itself as the scanner (galaxyscope on the program: paragraph PERFORM graph, complexity), check the slice's premise against live ledgers and open PRs, list the real gaps the way CI measures them, then the scenario / infeasible / refresh / pin-test loop and the known oracle refusals and harness limits so a run does not rediscover them. Use for any #6072 slice, "ladder climb", "L2->L3", "L3->L4", "branch coverage for PROGRAM", "infeasible outcome", or a worker brief that names #6072.
---

A ladder slice adds scenarios to a program's equivalence case (`tests/equivalence/<case>/case.json`) until the det
sweep runs every live paragraph (L3) and every net branch outcome (L4), or states, with its reason, the outcomes no
input can reach (`tests/equivalence/infeasible_outcomes.json`, #4602). Levels and bars: `tests/tools/evidence_report.py`.
Burned estates only; evidence levels, never "proven"; the oracle is GnuCOBOL + IBM documentation
(`.claude/rules/mainframe-evidence-policy.md`). Written from 33 ladder runs on 2026-10-22/23 (churn-runs/6072-*).

## 0. Environment

```sh
PY=/srv/storage_16tb/projects/gitgalaxy/venvs/selfscan/bin/python   # full + translator extras (tree-sitter-language-pack)
eval "$($PY tests/tools/equivalence_env.py --shell)"; $PY tests/tools/equivalence_env.py --check   # JDK 17, corpora, pins
```
Heavy runs (sweeps, Db2) go through `tests/tools/box/heavy-run.sh` (it needs `python` on PATH: put `$(dirname $PY)` first).
A venv without tree-sitter-language-pack gives a FALSE "not proven" -- `--check` first.

## 1. Premise check (before any plan) -- a third of stale items were already done

- `gh pr list -R squid-protocol/gitgalaxy --state all --search "6072 PROGRAM"` and the issue's latest comments: is
  the program already lifted, or in an open PR? Then stop and report "premise false" -- no PR.
- The coverage you plan from must be today's: `det_sweep_coverage/<case>.json` `measured_at`, not the issue text
  (the issue's numbers are a snapshot).
- One slice at a time touches `infeasible_outcomes.json`: if another live run's plan lists it, keep your slice to
  scenarios, or say in the plan that you need it (the gate holds overlapping plans).

## 2. Plan with GitGalaxy as the scanner

Scan the program with the product itself before reading the source by hand -- it gives the paragraph graph in a second:

```sh
mkdir -p $SCRATCH/scan/src && cp .mainframe_corpora/<estate>/<path>/PROGRAM.cbl $SCRATCH/scan/src/
$PY -m gitgalaxy.galaxyscope $SCRATCH/scan/src --db-only --output $SCRATCH/scan/out
sqlite3 -readonly $SCRATCH/scan/out/src_galaxy_master.db \
  "SELECT func_name, start_line, loc, complexity, calls_out_to, transfers_to FROM function_data ORDER BY start_line"
```
`func_name` = paragraph, `calls_out_to` = its PERFORM targets, `transfers_to` = GO TO / XCTL / LINK. Use it to:
- trace the PERFORM path from the entry paragraph to each uncovered paragraph (which scenario input steers there);
- size the slice: high-`complexity` paragraphs with many open outcomes are their own slice;
- spot paragraphs nothing PERFORMs (likely dead / after-transfer: cobol_coverage already sets true dead code apart).
Say in the plan what the scan showed. If the scan is wrong about a COBOL construct, that is an engine bug: file it.

## 3. The gaps, measured the way CI measures

`tests/tools/ladder_gaps.py CASE|PROGRAM...` prints each uncovered paragraph / branch outcome with file:line,
condition, arm, PERFORM path and existing infeasible entries (`--json` for `ladder-gaps/1`; `--sweep DIR` reads a
`proof_sweep --det-only` work dir, else the fresh ledger entry; `--no-scan` skips galaxyscope). With no fresh
measurement it prints the `heavy-run.sh ... proof_sweep.py --det-only` command to run first. By hand, the same numbers:
```sh
$PY tests/tools/proof_sweep.py --work $SCRATCH/sw --det-only --cases CASE --faults all   # CI's numbers (SQL-fault tasks count)
$PY tests/tools/proof_blockers.py --sweep $SCRATCH/sw --branches ...                       # what is open
$PY tests/tools/equivalence.py run CASE --keep $SCRATCH/k   # then $SCRATCH/k/cobol/coverage.json: branches.uncovered
```
Plain `equivalence.py run` leaves out the SQL-fault tasks (lgapdb01 read 6/7 there vs 7/7 in the sweep): never take
before/after numbers from it. `det_port.py run` does not write the ledger.
Known traps: `ladder_gaps.py` crashes on a paragraph entry from a copybook (`NAME:None`, no source line; `_split_outcome` does `int(line)`, #6364); `ladder_refresh.py`'s test `test_burned_generated_inputs_need_no_class_1_or_3_cause` can fail in a worktree with `LayoutError` (`COPY CIPAUSMY` unresolved, PAUDBLOD.CBL; uninvestigated, #6377); a bare `cics_crucible.py --ci` takes over 2 min, so run it through `heavy-run.sh` in the background (#6348).

## 4. Close each gap

- **Scenario first.** Add the input that reaches the arm. Before you add a fault, check nothing downstream resets the
  return code on the path you want measured (a later CLOSE-PCURSOR reset it once: a $1.67 run covered nothing).
- **Oracle refusals look like gaps** (X6, X8, X23, `bounds_refused`): read the refusal before calling a branch
  unreachable. Known workarounds: restate a refused ENTER input under PF7/PF8 (COCRDLIC line 518); set
  `commarea_length` for short-COMMAREA arms; invalid COMP-3 bytes via the `hex` input rule (`equivalence_inputs.py`).
- **Harness limits** (#6271 -- don't rediscover, cite it): abend injection, failing SEND MAP / RECEIVE MAP / RETURN /
  SYNCPOINT, DELAY faults, CEEDAYS, judging past the X6 WRITEQ. Leave those outcomes open, cite #6271, move on.
- **Infeasible outcomes**: only when no input can reach it (data-flow fact), each with its reason. WRITE THE ENTRY
  INTO THE FILE AS SOON AS YOU HAVE THE REASON -- reasons kept only in context were lost to a summary (0448Z). A
  scenario that reaches a stated outcome refutes it. Paragraph-level entries wait on PR #6279 (one file per
  case, add CLI; check its state before relying on it). CBPAUP0C `6000-EXIT` has been rediscovered 5+ times: check the
  infeasible entries first (`ladder_gaps.py` lists them).
- **Owner holds**: CRECUST and the CEEDAYS rulings stay refused; BANKDATA held (PR #5958); EPSMPMT callers wait
  on #5867. Not your slice.

## 5. Refresh chain (after every edit AND after every `git merge origin/main`)

`tests/tools/ladder_refresh.py CASE...` runs steps 1-3 below as one command and prints the before/after paragraph and
net-branch table for the PR body (`--dry-run` lists the chain, `--work DIR`, `--skip-tests`; burned estates only; the
ledger is updated only if every case proved). Its "before" column reads the working-tree ledger: take before numbers from `git show origin/main:tests/equivalence/det_sweep_coverage/<case>.json` (#6292). Run it again after every `git merge origin/main`. By hand, in order:
1. `proof_sweep.py --det-only --cases CASE --faults all --work DIR`, then `det_coverage_ledger.py update DIR`
   (update takes a proof_sweep work dir, not a det_port run).
2. `evidence.py prove KEY` when the case has an evidence record -- a missed re-prove is the most common CI send-back
   (`test_every_committed_record_is_current`).
3. Pin tests that name the case or program: `grep -rln "CASE\|PROGRAM" tests/ --include=test_*.py` -- e.g.
   `test_carddemo_copaus1c_5233.py` pins scenario lists and fault counts (grep BEFORE adding scenarios to an existing case, #6273); a new input rule must join `STATED_RULES` in
   `tests/tools/test_harness_report.py`.
4. A Db2 case with a new `seed.sql` needs its `-generated` twin (`test_cbsa_generated_siblings.py`, #4507).
Run targeted tests, not the whole `tests/cobol_mainframe` (it times out); CI runs the rest.

## 6. PR

- **Estate-sized, data-only (owner 2026-10-23: CI is the limit).** One estate per PR, one or both rungs, every
  program in it. Case data -- `case.json`, scenario input files, infeasible entries -- and generated files (ledgers,
  evidence records, `-generated` twins) don't count toward the 5-file cap. Data-only ladder PRs merged in 9-53 min at
  any size; the slow ones (78-158 min, 4-13 commits) all changed code.
- **No code in a ladder PR.** A harness / tool / translator change it needs is its own small PR first (this slice
  queues after it), or the outcome stays open citing #6271.
- **Never let one program hold the estate:** a program that won't close in the run is dropped to **Remaining
  slices** with what's left; ship the rest.
- No per-slice JSON-only test file: the det-sweep ratchet already checks the cases.
- Body: before/after table per program (paragraphs live/run, net branches, infeasible added with reasons), the
  outcomes left open and why (#6271 cite, owner hold), "Part of #6072".
